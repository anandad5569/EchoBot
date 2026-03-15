from __future__ import annotations

from typing import Any

from .base import BaseTool, ToolOutput


class MemorySearchTool(BaseTool):
    name = "memory_search"
    description = (
        "Search MEMORY.md and memory/*.md for prior work, user preferences, decisions, dates, or todos."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Semantic search query for stored memory.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return.",
                "default": 5,
            },
            "min_score": {
                "type": "number",
                "description": "Minimum match score between 0 and 1.",
                "default": 0.1,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, memory_support: Any) -> None:
        self.memory_support = memory_support

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        if self.memory_support is None:
            raise ValueError("memory support is not enabled")

        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")

        max_results = _read_int(arguments.get("max_results", 5), name="max_results", minimum=1)
        min_score = _read_float(arguments.get("min_score", 0.1), name="min_score")

        return await self.memory_support.search(
            query,
            max_results=max_results,
            min_score=min_score,
        )


def _read_int(value: Any, *, name: str, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if parsed < minimum:
        raise ValueError(f"{name} must be greater than or equal to {minimum}")

    return parsed


def _read_float(value: Any, *, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc

    if not 0.0 <= parsed <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")

    return parsed
