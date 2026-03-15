from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from ...models import LLMMessage, LLMTool
from ...providers.base import LLMProvider


HeartbeatExecutor = Callable[[str], Awaitable[str | None]]
HeartbeatNotifier = Callable[[str], Awaitable[None]]


_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
DEFAULT_HEARTBEAT_TEMPLATE = "\n".join(
    [
        "# HEARTBEAT.md",
        "",
        "<!--",
        "Add periodic tasks here.",
        "Keep only active tasks in this file.",
        "-->",
        "",
    ]
)

_HEARTBEAT_DECISION_TOOL = LLMTool(
    name="heartbeat_decision",
    description=(
        "Decide whether HEARTBEAT.md contains active tasks. "
        "Use action=skip when there is nothing actionable."
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["skip", "run"],
            },
            "tasks": {
                "type": "string",
                "description": "Short task summary for the next full agent run.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    },
)


class HeartbeatService:
    def __init__(
        self,
        *,
        heartbeat_file: str | Path,
        provider: LLMProvider,
        on_execute: HeartbeatExecutor | None = None,
        on_notify: HeartbeatNotifier | None = None,
        interval_seconds: int = 30 * 60,
        enabled: bool = True,
    ) -> None:
        self.heartbeat_file = Path(heartbeat_file)
        self.provider = provider
        self.on_execute = on_execute
        self.on_notify = on_notify
        self.interval_seconds = interval_seconds
        self.enabled = enabled
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if not self.enabled or self._running:
            return
        await self._ensure_template_exists()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def trigger_now(self) -> str | None:
        content = await self._read_heartbeat_file()
        if not _has_meaningful_content(content):
            return None
        action, tasks = await self._decide(content)
        if action != "run" or not tasks or self.on_execute is None:
            return None
        response = await self.on_execute(tasks)
        if response and self.on_notify is not None:
            await self.on_notify(response)
        return response

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.interval_seconds)
                if not self._running:
                    break
                await self._tick()
            except asyncio.CancelledError:
                break

    async def _tick(self) -> None:
        content = await self._read_heartbeat_file()
        if not _has_meaningful_content(content):
            return
        action, tasks = await self._decide(content)
        if action != "run" or not tasks or self.on_execute is None:
            return
        response = await self.on_execute(tasks)
        if response and self.on_notify is not None:
            await self.on_notify(response)

    async def _decide(self, content: str) -> tuple[str, str]:
        response = await self.provider.generate(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "You are a heartbeat checker. "
                        "Call heartbeat_decision with action=skip or action=run."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=(
                        "Review this HEARTBEAT.md content. "
                        "If there are active periodic tasks, return action=run "
                        "with a short execution prompt. Otherwise return skip.\n\n"
                        f"{content}"
                    ),
                ),
            ],
            tools=[_HEARTBEAT_DECISION_TOOL],
            tool_choice={
                "type": "function",
                "function": {"name": "heartbeat_decision"},
            },
        )
        tool_calls = response.tool_calls or response.message.tool_calls
        if not tool_calls:
            return "skip", ""
        try:
            arguments = json.loads(tool_calls[0].arguments or "{}")
        except json.JSONDecodeError:
            return "skip", ""
        action = str(arguments.get("action", "skip")).strip().lower()
        tasks = str(arguments.get("tasks", "")).strip()
        if action not in {"skip", "run"}:
            return "skip", ""
        return action, tasks

    async def _ensure_template_exists(self) -> None:
        if self.heartbeat_file.exists():
            return
        await asyncio.to_thread(self._write_file, DEFAULT_HEARTBEAT_TEMPLATE)

    async def _read_heartbeat_file(self) -> str:
        if not self.heartbeat_file.exists():
            return ""
        return await asyncio.to_thread(
            self.heartbeat_file.read_text,
            encoding="utf-8",
        )

    def _write_file(self, content: str) -> None:
        self.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
        self.heartbeat_file.write_text(content, encoding="utf-8")


def _has_meaningful_content(content: str) -> bool:
    without_comments = _COMMENT_PATTERN.sub("", content)
    for raw_line in without_comments.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return True
    return False


def has_meaningful_heartbeat_content(content: str) -> bool:
    return _has_meaningful_content(content)


async def read_or_create_heartbeat_file(heartbeat_file: str | Path) -> str:
    path = Path(heartbeat_file)
    if path.exists():
        return await asyncio.to_thread(path.read_text, encoding="utf-8")
    await write_heartbeat_file(path, DEFAULT_HEARTBEAT_TEMPLATE)
    return DEFAULT_HEARTBEAT_TEMPLATE


async def write_heartbeat_file(
    heartbeat_file: str | Path,
    content: str,
) -> None:
    path = Path(heartbeat_file)
    await asyncio.to_thread(_write_heartbeat_file_sync, path, content)


def _write_heartbeat_file_sync(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
