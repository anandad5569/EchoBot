from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from ..channels import InboundMessage, MessageBus, OutboundMessage
from ..channels.types import DeliveryTarget
from ..orchestration import RoleCommand, execute_role_command, parse_role_command
from ..runtime.scheduled_tasks import (
    build_cron_job_executor as build_shared_cron_job_executor,
    build_heartbeat_executor as build_shared_heartbeat_executor,
)
from ..runtime.bootstrap import RuntimeContext
from ..runtime.session_service import SessionLifecycleService
from .delivery import DeliveryStore
from .route_sessions import RouteSessionStore, RouteSessionSummary
from .session_service import GatewaySessionService


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionCommand:
    name: str
    argument: str = ""


class GatewayRuntime:
    def __init__(
        self,
        context: RuntimeContext,
        bus: MessageBus,
        session_service: GatewaySessionService | None = None,
        delivery_store: DeliveryStore | None = None,
        route_session_store: RouteSessionStore | None = None,
        *,
        max_inflight_messages: int = 32,
    ) -> None:
        self._context = context
        self._bus = bus
        if session_service is None:
            delivery_store = delivery_store or DeliveryStore(
                context.workspace / ".echobot" / "delivery.json",
            )
            route_session_store = route_session_store or RouteSessionStore(
                context.workspace / ".echobot" / "route_sessions.json",
            )
            core_session_service = SessionLifecycleService(
                context.session_store,
                context.agent_session_store,
                coordinator=context.coordinator,
            )
            session_service = GatewaySessionService(
                core_session_service,
                route_session_store=route_session_store,
                delivery_store=delivery_store,
            )
        self._session_service = session_service
        self._inflight_tasks: set[asyncio.Task[None]] = set()
        self._inflight_semaphore = asyncio.Semaphore(max(max_inflight_messages, 1))
        self._route_locks: dict[str, asyncio.Lock] = {}
        self._route_locks_guard = asyncio.Lock()

    async def run(self) -> None:
        self._context.cron_service.on_job = self._build_cron_job_executor()
        if self._context.heartbeat_service is not None:
            self._context.heartbeat_service.on_execute = (
                self._build_heartbeat_executor()
            )
            self._context.heartbeat_service.on_notify = self._notify_latest

        await self._context.cron_service.start()
        if self._context.heartbeat_service is not None:
            await self._context.heartbeat_service.start()

        logger.info("Gateway runtime started")
        try:
            while True:
                await self._inflight_semaphore.acquire()
                message = await self._bus.consume_inbound()
                task = asyncio.create_task(self._handle_inbound_message_task(message))
                self._inflight_tasks.add(task)
                task.add_done_callback(self._inflight_tasks.discard)
        finally:
            await self._shutdown()

    async def handle_inbound_message(self, message: InboundMessage) -> None:
        route_lock = await self._route_lock(message.route_key)
        async with route_lock:
            await self._handle_inbound_message(message)

    async def _handle_inbound_message_task(self, message: InboundMessage) -> None:
        try:
            await self.handle_inbound_message(message)
        finally:
            self._inflight_semaphore.release()

    async def _handle_inbound_message(self, message: InboundMessage) -> None:
        route_key = message.route_key
        role_command = parse_role_command(message.text)
        if role_command is not None:
            response_text = await self._handle_role_command(
                route_key,
                message,
                role_command.action,
                role_command.argument,
            )
            await self._bus.publish_outbound(
                OutboundMessage(
                    address=message.address,
                    text=response_text,
                    metadata=dict(message.metadata),
                )
            )
            return

        command = _parse_session_command(message.text)
        if command is not None:
            response_text = await self._handle_session_command(
                route_key,
                message,
                command,
            )
            await self._bus.publish_outbound(
                OutboundMessage(
                    address=message.address,
                    text=response_text,
                    metadata=dict(message.metadata),
                )
            )
            return

        route_session = await self._session_service.current_route_session(
            route_key,
        )
        await self._session_service.remember_delivery_target(
            route_session.session_name,
            message.address,
            message.metadata,
        )
        try:
            execution = await self._context.coordinator.handle_user_turn(
                route_session.session_name,
                message.text,
                image_urls=message.image_urls,
                completion_callback=self._completion_callback_for_session(
                    route_session.session_name,
                ),
            )
            content = execution.response_text.strip()
            if not content:
                content = "Model returned no text content."
            await self._session_service.touch_route_session(
                route_key,
                route_session.session_name,
                updated_at=execution.session.updated_at,
            )
        except ValueError as exc:
            content = str(exc)
        except RuntimeError as exc:
            content = f"Request failed: {exc}"
        await self._bus.publish_outbound(
            OutboundMessage(
                address=message.address,
                text=content,
                metadata=dict(message.metadata),
            )
        )

    async def _handle_role_command(
        self,
        route_key: str,
        message: InboundMessage,
        action: str,
        argument: str,
    ) -> str:
        route_session = await self._session_service.current_route_session(
            route_key,
        )
        await self._session_service.remember_delivery_target(
            route_session.session_name,
            message.address,
            message.metadata,
        )
        try:
            return await execute_role_command(
                self._context.coordinator,
                route_session.session_name,
                RoleCommand(action=action, argument=argument),
            )
        except ValueError as exc:
            return str(exc)

    async def _handle_session_command(
        self,
        route_key: str,
        message: InboundMessage,
        command: SessionCommand,
    ) -> str:
        if command.name == "help":
            current = await self._session_service.current_route_session(
                route_key,
            )
            await self._session_service.remember_delivery_target(
                current.session_name,
                message.address,
                message.metadata,
            )
            return _session_help_text()

        if command.name == "list":
            sessions = await self._session_service.list_route_sessions(
                route_key,
            )
            await self._session_service.remember_delivery_target(
                sessions[0].session_name,
                message.address,
                message.metadata,
            )
            return _format_route_session_list(sessions)

        if command.name == "current":
            current = await self._session_service.current_route_session(
                route_key,
            )
            await self._session_service.remember_delivery_target(
                current.session_name,
                message.address,
                message.metadata,
            )
            return _format_current_route_session(current)

        if command.name == "new":
            created = await self._session_service.create_route_session(
                route_key,
                title=(command.argument or None),
            )
            await self._session_service.remember_delivery_target(
                created.session_name,
                message.address,
                message.metadata,
            )
            return (
                "Switched to a new session: "
                f"{created.title} [{created.short_id}]"
            )

        if command.name == "switch":
            if not command.argument:
                return "Usage: /switch <number>"
            try:
                index = int(command.argument)
            except ValueError:
                return "Session number must be an integer."
            try:
                selected = await self._session_service.switch_route_session(
                    route_key,
                    index,
                )
            except ValueError as exc:
                return str(exc)
            await self._session_service.remember_delivery_target(
                selected.session_name,
                message.address,
                message.metadata,
            )
            return (
                "Switched to session "
                f"{index}: {selected.title} [{selected.short_id}]"
            )

        if command.name == "rename":
            if not command.argument:
                return "Usage: /rename <title>"
            try:
                renamed = await self._session_service.rename_current_route_session(
                    route_key,
                    command.argument,
                )
            except ValueError as exc:
                return str(exc)
            await self._session_service.remember_delivery_target(
                renamed.session_name,
                message.address,
                message.metadata,
            )
            return (
                "Renamed current session to "
                f"{renamed.title} [{renamed.short_id}]"
            )

        if command.name == "delete":
            result = await self._session_service.delete_current_route_session(
                route_key,
            )
            await self._session_service.remember_delivery_target(
                result.current.session_name,
                message.address,
                message.metadata,
            )
            if result.created_replacement:
                return (
                    "Deleted the last session and created a fresh one: "
                    f"{result.current.title} [{result.current.short_id}]"
                )
            return (
                "Deleted the current session. "
                f"Now using {result.current.title} [{result.current.short_id}]"
            )

        return _session_help_text()

    def _completion_callback_for_session(
        self,
        session_name: str,
    ):
        async def notify(job) -> None:
            await self._publish_session_response(
                session_name,
                job.final_response,
                metadata={
                    "async_result": True,
                    "job_id": job.job_id,
                    "job_status": job.status,
                },
            )

        return notify

    def _build_cron_job_executor(self):
        return build_shared_cron_job_executor(
            self._context.session_runner,
            self._context.coordinator,
            self._notify_schedule,
        )

    def _build_heartbeat_executor(self):
        return build_shared_heartbeat_executor(self._context.session_runner)

    async def _notify_session(
        self,
        session_name: str,
        content: str,
        *,
        kind: str,
        title: str,
    ) -> None:
        target = await self._session_service.get_session_target(session_name)
        await self._publish_notification(
            target,
            content,
            kind=kind,
            title=title,
        )

    async def _publish_session_response(
        self,
        session_name: str,
        content: str,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        target = await self._session_service.get_session_target(session_name)
        if target is None:
            logger.info("[reply] %s", content)
            return
        next_metadata = dict(target.metadata)
        if metadata is not None:
            next_metadata.update(metadata)
        await self._bus.publish_outbound(
            OutboundMessage(
                address=target.address,
                text=content,
                metadata=next_metadata,
            )
        )

    async def _notify_latest(self, content: str) -> None:
        target = await self._session_service.get_latest_target()
        await self._publish_notification(
            target,
            content,
            kind="heartbeat",
            title="Periodic check-in",
        )

    async def _publish_notification(
        self,
        target: DeliveryTarget | None,
        content: str,
        *,
        kind: str,
        title: str,
    ) -> None:
        if target is None:
            logger.info("[%s] %s", kind, title)
            for line in content.splitlines() or [content]:
                logger.info("[%s] %s", kind, line)
            return
        metadata = dict(target.metadata)
        metadata["scheduled"] = True
        metadata["schedule_kind"] = kind
        metadata["schedule_title"] = title
        await self._bus.publish_outbound(
            OutboundMessage(
                address=target.address,
                text=content,
                metadata=metadata,
            )
        )

    async def _notify_schedule(
        self,
        session_name: str,
        kind: str,
        title: str,
        content: str,
    ) -> None:
        await self._notify_session(
            session_name,
            content,
            kind=kind,
            title=title,
        )

    async def _shutdown(self) -> None:
        tasks = list(self._inflight_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._context.cron_service.stop()
        if self._context.heartbeat_service is not None:
            await self._context.heartbeat_service.stop()
        await self._context.coordinator.close()
        if self._context.memory_support is not None:
            await self._context.memory_support.close()

    async def _route_lock(self, route_key: str) -> asyncio.Lock:
        async with self._route_locks_guard:
            lock = self._route_locks.get(route_key)
            if lock is None:
                lock = asyncio.Lock()
                self._route_locks[route_key] = lock
            return lock



def _parse_session_command(text: str) -> SessionCommand | None:
    cleaned = text.strip()
    if not cleaned.startswith("/"):
        return None

    command_token, remainder = _split_command_parts(cleaned)

    if command_token == "/session":
        subcommand, remainder = _split_command_parts(remainder)
        mapping = {
            "help": "help",
            "list": "list",
            "ls": "list",
            "current": "current",
            "new": "new",
            "switch": "switch",
            "rename": "rename",
            "delete": "delete",
        }
        mapped = mapping.get(subcommand.lstrip("/"))
        if mapped is None:
            return SessionCommand("help")
        return SessionCommand(mapped, remainder)

    if command_token == "/new":
        return SessionCommand("new", remainder)
    if command_token == "/ls":
        return SessionCommand("list")
    if command_token == "/current":
        return SessionCommand("current")
    if command_token == "/switch":
        return SessionCommand("switch", remainder)
    if command_token == "/rename":
        return SessionCommand("rename", remainder)
    if command_token == "/delete":
        return SessionCommand("delete")
    if command_token == "/help":
        return SessionCommand("help")
    return None


def _split_command_parts(text: str) -> tuple[str, str]:
    cleaned = text.strip()
    if not cleaned:
        return "", ""

    parts = cleaned.split(maxsplit=1)
    raw_token = parts[0].strip().lower()
    remainder = parts[1].strip() if len(parts) >= 2 else ""
    command_token = raw_token.split("@", 1)[0]
    return command_token, remainder


def _session_help_text() -> str:
    return "\n".join(
        [
            "Session commands:",
            "/new [title] - Start a new session",
            "/ls - List sessions in this chat",
            "/switch <number> - Switch to a session",
            "/rename <title> - Rename the current session",
            "/delete - Delete the current session",
            "/current - Show the current session",
            "/session ... - Alias for the same commands",
        ]
    )


def _format_current_route_session(route_session: RouteSessionSummary) -> str:
    return (
        "Current session: "
        f"{route_session.title} [{route_session.short_id}]"
    )


def _format_route_session_list(
    sessions: list[RouteSessionSummary],
) -> str:
    lines = ["Sessions for this chat:"]
    for index, route_session in enumerate(sessions, start=1):
        marker = "*" if index == 1 else " "
        lines.append(
            f"{marker} {index}. {route_session.title} [{route_session.short_id}]"
        )
    lines.append("Use /switch <number> to change the current session.")
    return "\n".join(lines)
