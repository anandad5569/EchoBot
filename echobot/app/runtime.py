from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from ..asr import ASRService, build_default_asr_service
from ..channels import ChannelManager, ChannelsConfig, MessageBus, load_channels_config
from ..gateway import (
    DeliveryStore,
    GatewayRuntime,
    GatewaySessionService,
    RouteSessionStore,
)
from ..runtime.bootstrap import RuntimeContext, RuntimeOptions, build_runtime_context
from ..runtime.session_service import SessionLifecycleService
from ..tts import TTSService, build_default_tts_service
from .services.chat import ChatService
from .services.channels import ChannelService
from .services.roles import RoleService
from .services.web_console import WebConsoleService


RuntimeContextBuilder = Callable[[RuntimeOptions], RuntimeContext]
TTSServiceBuilder = Callable[[Path], TTSService]
ASRServiceBuilder = Callable[[Path], ASRService]


class AppRuntime:
    def __init__(
        self,
        *,
        runtime_options: RuntimeOptions,
        channel_config_path: str | Path,
        context_builder: RuntimeContextBuilder | None = None,
        tts_service_builder: TTSServiceBuilder | None = None,
        asr_service_builder: ASRServiceBuilder | None = None,
    ) -> None:
        self.runtime_options = runtime_options
        self.channel_config_path = _resolve_runtime_path(
            runtime_options.workspace,
            channel_config_path,
        )
        self._context_builder = context_builder or _default_context_builder
        self._tts_service_builder = tts_service_builder or _default_tts_service_builder
        self._asr_service_builder = asr_service_builder or _default_asr_service_builder

        self.context: RuntimeContext | None = None
        self.bus: MessageBus | None = None
        self.channels_config: ChannelsConfig | None = None
        self.channel_manager: ChannelManager | None = None
        self.delivery_store: DeliveryStore | None = None
        self.route_session_store: RouteSessionStore | None = None
        self.gateway: GatewayRuntime | None = None
        self.gateway_task: asyncio.Task[None] | None = None
        self.session_service: GatewaySessionService | None = None
        self.chat_service: ChatService | None = None
        self.role_service: RoleService | None = None
        self.channel_service: ChannelService | None = None
        self.web_console_service: WebConsoleService | None = None
        self.tts_service: TTSService | None = None
        self.asr_service: ASRService | None = None
        self._started = False

    @property
    def workspace(self) -> Path:
        if self.context is None:
            raise RuntimeError("App runtime has not been started")
        return self.context.workspace

    async def start(self) -> None:
        if self._started:
            return

        self.context = self._context_builder(self.runtime_options)
        self.bus = MessageBus()
        self.channels_config = load_channels_config(self.channel_config_path)
        self.channel_manager = ChannelManager(self.channels_config, self.bus)
        self.delivery_store = DeliveryStore(
            self.context.workspace / ".echobot" / "delivery.json",
        )
        self.route_session_store = RouteSessionStore(
            self.context.workspace / ".echobot" / "route_sessions.json",
        )
        core_session_service = SessionLifecycleService(
            self.context.session_store,
            self.context.agent_session_store,
            coordinator=self.context.coordinator,
        )
        self.session_service = GatewaySessionService(
            core_session_service,
            route_session_store=self.route_session_store,
            delivery_store=self.delivery_store,
        )
        self.gateway = GatewayRuntime(
            self.context,
            self.bus,
            session_service=self.session_service,
        )
        self.chat_service = ChatService(
            self.context.coordinator,
            self.session_service,
        )
        self.role_service = RoleService(
            self.context.role_registry,
            self.context.session_store,
        )
        self.channel_service = ChannelService(
            config_path=self.channel_config_path,
            get_status=self.channel_status,
            reload_channels=self.reload_channels,
        )
        self.asr_service = self._asr_service_builder(self.context.workspace)
        self.tts_service = self._tts_service_builder(self.context.workspace)
        self.web_console_service = WebConsoleService(
            self.context.workspace,
            self.tts_service,
            self.asr_service,
        )
        await self.asr_service.on_startup()

        await self.channel_manager.start_all()
        self.gateway_task = asyncio.create_task(
            self.gateway.run(),
            name="echobot_gateway_runtime",
        )
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return

        if self.gateway_task is not None:
            self.gateway_task.cancel()
            await asyncio.gather(self.gateway_task, return_exceptions=True)
            self.gateway_task = None

        if self.channel_manager is not None:
            await self.channel_manager.stop_all()

        if self.context is not None:
            await self.context.coordinator.close()
        if self.tts_service is not None:
            await self.tts_service.close()
        if self.asr_service is not None:
            await self.asr_service.close()

        self._started = False

    async def reload_channels(
        self,
        config: ChannelsConfig | None = None,
    ) -> None:
        if self.bus is None:
            raise RuntimeError("App runtime has not been started")

        next_config = config or load_channels_config(self.channel_config_path)
        next_manager = ChannelManager(next_config, self.bus)
        await next_manager.start_all()

        previous_manager = self.channel_manager
        self.channel_manager = next_manager
        self.channels_config = next_config

        if previous_manager is not None:
            await previous_manager.stop_all()

    def channel_status(self) -> dict[str, dict[str, bool]]:
        if self.channel_manager is None:
            return {}
        return self.channel_manager.get_status()

    async def health_snapshot(self) -> dict[str, object]:
        if self.context is None or self.bus is None or self.session_service is None:
            raise RuntimeError("App runtime has not been started")

        current_session = await self.session_service.load_current_session()
        current_role = await self.context.coordinator.current_role_name(
            current_session.name,
        )
        job_counts = await self.context.coordinator.job_counts()
        return {
            "status": "ok",
            "workspace": str(self.context.workspace),
            "current_session": current_session.name,
            "current_role": current_role,
            "channels": self.channel_status(),
            "bus": {
                "inbound_size": self.bus.inbound_size,
                "outbound_size": self.bus.outbound_size,
            },
            "jobs": job_counts,
        }


def _default_context_builder(options: RuntimeOptions) -> RuntimeContext:
    return build_runtime_context(options, load_session_state=False)


def _default_tts_service_builder(workspace: Path) -> TTSService:
    return build_default_tts_service(workspace)


def _default_asr_service_builder(workspace: Path) -> ASRService:
    return build_default_asr_service(workspace)


def _resolve_runtime_path(
    workspace: Path | None,
    path: str | Path,
) -> Path:
    resolved_path = Path(path).expanduser()
    if resolved_path.is_absolute() or workspace is None:
        return resolved_path
    return workspace / resolved_path
