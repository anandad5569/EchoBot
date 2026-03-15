from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from ..tools.base import BaseTool, ToolOutput
from .models import RESOURCE_FOLDERS, Skill, SkillRuntimeState

if TYPE_CHECKING:
    from .registry import SkillRegistry


class ActivateSkillTool(BaseTool):
    name = "activate_skill"
    description = (
        "Load a skill's core instructions by name. This only loads the main skill text. "
        "Bundled resource files stay unloaded until you inspect or read them explicitly."
    )

    def __init__(
        self,
        skill_registry: SkillRegistry,
        runtime_state: SkillRuntimeState,
    ) -> None:
        self.skill_registry = skill_registry
        self.runtime_state = runtime_state
        self.parameters = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The exact skill name to activate.",
                    "enum": self.skill_registry.names(),
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        }

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        skill = self.skill_registry.require_skill(arguments.get("name"))
        already_active = self.runtime_state.is_active(skill.name)
        if not already_active:
            self.runtime_state.activate(skill.name)

        return {
            "kind": "skill_activation",
            "name": skill.name,
            "description": skill.description,
            "directory": str(skill.directory),
            "already_active": already_active,
            "resource_summary": skill.resource_summary(),
            "content": skill.to_activation_text(),
        }


class ListSkillResourcesTool(BaseTool):
    name = "list_skill_resources"
    description = (
        "List bundled files for an activated skill. Use this after activate_skill when you "
        "need to inspect which scripts, references, assets, or agents are available."
    )

    def __init__(
        self,
        skill_registry: SkillRegistry,
        runtime_state: SkillRuntimeState,
    ) -> None:
        self.skill_registry = skill_registry
        self.runtime_state = runtime_state
        self.parameters = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The exact activated skill name.",
                    "enum": self.skill_registry.names(),
                },
                "folder": {
                    "type": "string",
                    "description": "Optional resource folder: scripts, references, assets, or agents.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of file paths to return.",
                    "default": 50,
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        }

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        skill = self.skill_registry.require_active_skill(
            arguments.get("name"),
            runtime_state=self.runtime_state,
        )
        folder_name = _read_optional_folder_name(arguments.get("folder"))
        limit = _read_positive_int(arguments.get("limit", 50), name="limit")
        resource_files = skill.resource_files(folder_name)

        return {
            "kind": "skill_resource_list",
            "name": skill.name,
            "folder": folder_name or "all",
            "entries": resource_files[:limit],
            "total_files": len(resource_files),
            "truncated": len(resource_files) > limit,
        }


class ReadSkillResourceTool(BaseTool):
    name = "read_skill_resource"
    description = (
        "Read one UTF-8 resource file from an activated skill. This is for loading a single "
        "reference or script only when the task actually needs it."
    )

    def __init__(
        self,
        skill_registry: SkillRegistry,
        runtime_state: SkillRuntimeState,
    ) -> None:
        self.skill_registry = skill_registry
        self.runtime_state = runtime_state
        self.parameters = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The exact activated skill name.",
                    "enum": self.skill_registry.names(),
                },
                "path": {
                    "type": "string",
                    "description": "Relative file path inside the skill's scripts, references, assets, or agents folders.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of characters to return.",
                    "default": 4000,
                },
            },
            "required": ["name", "path"],
            "additionalProperties": False,
        }

    async def run(self, arguments: dict[str, Any]) -> ToolOutput:
        skill = self.skill_registry.require_active_skill(
            arguments.get("name"),
            runtime_state=self.runtime_state,
        )
        relative_path = str(arguments.get("path", "")).strip()
        if not relative_path:
            raise ValueError("path is required")

        max_chars = _read_positive_int(arguments.get("max_chars", 4000), name="max_chars")
        return await asyncio.to_thread(
            self._read_resource_file,
            skill,
            relative_path,
            max_chars,
        )

    def _read_resource_file(
        self,
        skill: Skill,
        relative_path: str,
        max_chars: int,
    ) -> dict[str, Any]:
        target = skill.resolve_resource_path(relative_path)
        if not target.exists():
            raise ValueError(f"File does not exist: {relative_path}")
        if not target.is_file():
            raise ValueError(f"Path is not a file: {relative_path}")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Only UTF-8 text skill resources are supported") from exc

        return {
            "kind": "skill_resource_content",
            "name": skill.name,
            "path": str(target.relative_to(skill.directory)).replace("\\", "/"),
            "content": content[:max_chars],
            "total_chars": len(content),
            "truncated": len(content) > max_chars,
        }


def _read_optional_folder_name(value: Any) -> str | None:
    if value is None:
        return None

    folder_name = str(value).strip()
    if not folder_name:
        return None
    if folder_name not in RESOURCE_FOLDERS:
        allowed = ", ".join(RESOURCE_FOLDERS)
        raise ValueError(f"folder must be one of: {allowed}")

    return folder_name


def _read_positive_int(value: Any, *, name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if number <= 0:
        raise ValueError(f"{name} must be greater than 0")

    return number
