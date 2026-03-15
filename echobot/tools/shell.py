from __future__ import annotations

import asyncio
import locale
import os
from pathlib import Path
from typing import Any

from .base import ToolOutput
from .filesystem import WorkspaceTool


class CommandExecutionTool(WorkspaceTool):
    name = "run_shell_command"
    description = "Run a shell command in the workspace and return stdout and stderr."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to run.",
            },
            "workdir": {
                "type": "string",
                "description": "Relative working directory inside the workspace.",
                "default": ".",
            },
            "timeout": {
                "type": "number",
                "description": "Command timeout in seconds.",
                "default": 20,
            },
            "max_output_chars": {
                "type": "integer",
                "description": "Maximum characters kept for stdout and stderr.",
                "default": 4000,
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        command = str(arguments.get("command", "")).strip()
        if not command:
            raise ValueError("command is required")

        relative_workdir = str(arguments.get("workdir", ".")).strip() or "."
        timeout = _read_positive_float(arguments.get("timeout", 20), name="timeout")
        max_output_chars = _read_positive_int(
            arguments.get("max_output_chars", 4000),
            name="max_output_chars",
        )

        workdir = self._resolve_workspace_path(relative_workdir)
        if not workdir.exists():
            raise ValueError(f"Path does not exist: {relative_workdir}")
        if not workdir.is_dir():
            raise ValueError(f"Path is not a directory: {relative_workdir}")

        return await self._run_command(
            command,
            workdir,
            relative_workdir,
            timeout,
            max_output_chars,
        )

    async def _run_command(
        self,
        command: str,
        workdir: Path,
        relative_workdir: str,
        timeout: float,
        max_output_chars: int,
    ) -> dict[str, Any]:
        shell_command = _build_shell_command(command)
        process = await asyncio.create_subprocess_exec(
            *shell_command,
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise RuntimeError(f"Command timed out after {timeout} seconds") from exc

        stdout_text = _decode_command_output(stdout_bytes)
        stderr_text = _decode_command_output(stderr_bytes)
        stdout, stdout_truncated = _truncate_text(stdout_text, max_output_chars)
        stderr, stderr_truncated = _truncate_text(stderr_text, max_output_chars)

        return {
            "command": command,
            "workdir": relative_workdir,
            "return_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }


def _read_positive_int(value: Any, *, name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if number <= 0:
        raise ValueError(f"{name} must be greater than 0")

    return number


def _read_positive_float(value: Any, *, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc

    if number <= 0:
        raise ValueError(f"{name} must be greater than 0")

    return number


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False

    return text[:max_chars], True


def _decode_command_output(raw_bytes: bytes) -> str:
    if not raw_bytes:
        return ""

    preferred_encoding = locale.getpreferredencoding(False) or "utf-8"
    candidate_encodings = ["utf-8"]
    if preferred_encoding.lower() not in {"utf-8", "utf_8"}:
        candidate_encodings.append(preferred_encoding)

    for encoding in candidate_encodings:
        try:
            return raw_bytes.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue

    try:
        return raw_bytes.decode(preferred_encoding, errors="replace")
    except LookupError:
        return raw_bytes.decode("utf-8", errors="replace")


def _build_shell_command(command: str) -> list[str]:
    if os.name == "nt":
        return ["powershell.exe", "-NoProfile", "-Command", command]

    return ["/bin/sh", "-lc", command]
