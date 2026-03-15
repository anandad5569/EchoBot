from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..scheduling.cron import CronService
from .base import BaseTool, ToolOutput, ToolRegistry
from .cron import CronTool
from .filesystem import ListDirectoryTool, ReadTextFileTool, WriteTextFileTool
from .memory import MemorySearchTool
from .shell import CommandExecutionTool, _decode_command_output, locale
from .web import WebRequestTool


class CurrentTimeTool(BaseTool):
    name = "get_current_time"
    description = "Get the current local time."
    parameters = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        del arguments
        now = datetime.now().astimezone()
        return {
            "current_time": now.isoformat(timespec="seconds"),
            "timezone": str(now.tzinfo),
        }


def create_basic_tool_registry(
    workspace: str | Path = ".",
    *,
    memory_support: Any | None = None,
    cron_service: CronService | None = None,
    session_name: str = "default",
    allow_cron_mutations: bool = True,
) -> ToolRegistry:
    tools: list[BaseTool] = [
        CurrentTimeTool(),
        ListDirectoryTool(workspace),
        ReadTextFileTool(workspace),
        WriteTextFileTool(workspace),
        WebRequestTool(),
        CommandExecutionTool(workspace),
    ]
    if memory_support is not None:
        tools.append(MemorySearchTool(memory_support))
    if cron_service is not None:
        tools.append(
            CronTool(
                cron_service,
                session_name=session_name,
                allow_mutations=allow_cron_mutations,
            )
        )

    return ToolRegistry(tools)


__all__ = [
    "CommandExecutionTool",
    "CronTool",
    "CurrentTimeTool",
    "ListDirectoryTool",
    "MemorySearchTool",
    "ReadTextFileTool",
    "WebRequestTool",
    "WriteTextFileTool",
    "_decode_command_output",
    "create_basic_tool_registry",
    "locale",
]
