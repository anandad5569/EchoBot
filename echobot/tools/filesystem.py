from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolOutput


class WorkspaceTool(BaseTool):
    def __init__(self, workspace: str | Path = ".") -> None:
        self.workspace = Path(workspace)

    def _resolve_workspace_path(self, relative_path: str) -> Path:
        workspace_root = self.workspace.resolve()
        target = (workspace_root / relative_path).resolve()

        try:
            target.relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError(f"Path is outside the workspace: {relative_path}") from exc

        return target

    def _to_relative_path(self, target: Path) -> str:
        return str(target.resolve().relative_to(self.workspace.resolve())).replace("\\", "/")


class ListDirectoryTool(WorkspaceTool):
    name = "list_directory"
    description = "List files and folders under the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path inside the workspace.",
                "default": ".",
            }
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        relative_path = str(arguments.get("path", ".")).strip() or "."
        return await asyncio.to_thread(self._list_directory, relative_path)

    def _list_directory(self, relative_path: str) -> dict[str, Any]:
        target = self._resolve_workspace_path(relative_path)
        if not target.exists():
            raise ValueError(f"Path does not exist: {relative_path}")
        if not target.is_dir():
            raise ValueError(f"Path is not a directory: {relative_path}")

        entries = []
        for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            entries.append(
                {
                    "name": child.name,
                    "type": "file" if child.is_file() else "directory",
                }
            )

        return {
            "path": self._to_relative_path(target),
            "entries": entries[:200],
            "truncated": len(entries) > 200,
        }


class ReadTextFileTool(WorkspaceTool):
    name = "read_text_file"
    description = "Read a UTF-8 text file from the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path inside the workspace.",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum number of characters to return.",
                "default": 4000,
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        relative_path = str(arguments.get("path", "")).strip()
        if not relative_path:
            raise ValueError("path is required")

        max_chars = _read_positive_int(arguments.get("max_chars", 4000), name="max_chars")
        return await asyncio.to_thread(self._read_text_file, relative_path, max_chars)

    def _read_text_file(self, relative_path: str, max_chars: int) -> dict[str, Any]:
        target = self._resolve_workspace_path(relative_path)
        if not target.exists():
            raise ValueError(f"File does not exist: {relative_path}")
        if not target.is_file():
            raise ValueError(f"Path is not a file: {relative_path}")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Only UTF-8 text files are supported") from exc

        return {
            "path": self._to_relative_path(target),
            "content": content[:max_chars],
            "total_chars": len(content),
            "truncated": len(content) > max_chars,
        }


class WriteTextFileTool(WorkspaceTool):
    name = "write_text_file"
    description = "Write a UTF-8 text file inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path inside the workspace.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write.",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Overwrite the file if it already exists.",
                "default": False,
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        relative_path = str(arguments.get("path", "")).strip()
        if not relative_path:
            raise ValueError("path is required")

        content = str(arguments.get("content", ""))
        overwrite = bool(arguments.get("overwrite", False))
        return await asyncio.to_thread(
            self._write_text_file,
            relative_path,
            content,
            overwrite,
        )

    def _write_text_file(
        self,
        relative_path: str,
        content: str,
        overwrite: bool,
    ) -> dict[str, Any]:
        target = self._resolve_workspace_path(relative_path)
        file_existed = target.exists()
        if file_existed and not overwrite:
            raise ValueError(f"File already exists: {relative_path}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        return {
            "path": self._to_relative_path(target),
            "written_chars": len(content),
            "overwritten": file_existed and overwrite,
        }


def _read_positive_int(value: Any, *, name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if number <= 0:
        raise ValueError(f"{name} must be greater than 0")

    return number
