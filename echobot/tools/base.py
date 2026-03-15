from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..models import LLMMessage, LLMTool, ToolCall


ToolOutput = str | int | float | bool | None | dict[str, Any] | list[Any]


@dataclass(slots=True)
class ToolResult:
    call_id: str
    tool_name: str
    content: str
    is_error: bool = False

    def to_message(self) -> LLMMessage:
        return LLMMessage(
            role="tool",
            content=self.content,
            tool_call_id=self.call_id,
        )


class BaseTool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]

    def to_llm_tool(self) -> LLMTool:
        return LLMTool(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    @abstractmethod
    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self, tools: Sequence[BaseTool] | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}

        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")

        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def copy(self) -> "ToolRegistry":
        return ToolRegistry(list(self._tools.values()))

    def register_many(self, tools: Sequence[BaseTool]) -> None:
        for tool in tools:
            self.register(tool)

    def to_llm_tools(self) -> list[LLMTool]:
        return [tool.to_llm_tool() for tool in self._tools.values()]

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        tool = self.get(tool_call.name)
        if tool is None:
            return self._error_result(tool_call, f"Tool not found: {tool_call.name}")

        try:
            arguments = _parse_arguments(tool_call.arguments)
        except ValueError as exc:
            return self._error_result(tool_call, str(exc))

        try:
            output = await tool.run(arguments)
        except Exception as exc:
            return self._error_result(tool_call, str(exc))

        return ToolResult(
            call_id=tool_call.id,
            tool_name=tool_call.name,
            content=_build_payload(output),
        )

    async def execute_tool_calls(
        self,
        tool_calls: Sequence[ToolCall],
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        for tool_call in tool_calls:
            results.append(await self.execute(tool_call))

        return results

    def _error_result(self, tool_call: ToolCall, message: str) -> ToolResult:
        return ToolResult(
            call_id=tool_call.id,
            tool_name=tool_call.name,
            content=_build_payload({"error": message}, is_error=True),
            is_error=True,
        )


def _parse_arguments(raw_arguments: str) -> dict[str, Any]:
    cleaned = raw_arguments.strip()
    if not cleaned:
        return {}

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON tool arguments: {exc.msg}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must be a JSON object")

    return parsed


def _build_payload(data: ToolOutput, *, is_error: bool = False) -> str:
    payload: dict[str, Any] = {
        "ok": not is_error,
        "result": data,
    }

    if is_error and isinstance(data, dict) and "error" in data:
        payload = {
            "ok": False,
            "error": data["error"],
        }

    return json.dumps(payload, ensure_ascii=False)
