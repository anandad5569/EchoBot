from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RESOURCE_FOLDERS = ("scripts", "references", "assets", "agents")


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    directory: Path
    skill_file: Path
    body: str
    frontmatter: str

    def resource_files(self, folder_name: str | None = None) -> list[str]:
        files: list[str] = []
        folder_names = [folder_name] if folder_name else list(RESOURCE_FOLDERS)

        for current_folder_name in folder_names:
            if current_folder_name not in RESOURCE_FOLDERS:
                raise ValueError(f"Unknown skill resource folder: {current_folder_name}")

            folder = self.directory / current_folder_name
            if not folder.exists():
                continue

            for path in sorted(item for item in folder.rglob("*") if item.is_file()):
                files.append(str(path.relative_to(self.directory)).replace("\\", "/"))

        return files

    def resource_summary(self) -> list[str]:
        summary: list[str] = []
        for folder_name in RESOURCE_FOLDERS:
            count = len(self.resource_files(folder_name))
            if count == 0:
                continue

            label = "file" if count == 1 else "files"
            summary.append(f"{folder_name}: {count} {label}")

        return summary

    def resolve_resource_path(self, relative_path: str) -> Path:
        cleaned_path = relative_path.strip().replace("\\", "/")
        if not cleaned_path:
            raise ValueError("path is required")

        target = (self.directory / cleaned_path).resolve()
        skill_root = self.directory.resolve()
        try:
            relative_target = target.relative_to(skill_root)
        except ValueError as exc:
            raise ValueError(f"Path is outside the skill directory: {relative_path}") from exc

        if not relative_target.parts:
            raise ValueError("path is required")
        if relative_target.parts[0] not in RESOURCE_FOLDERS:
            allowed = ", ".join(RESOURCE_FOLDERS)
            raise ValueError(f"path must be inside one of: {allowed}")

        return target

    def to_catalog_entry(self) -> str:
        return f'<skill name="{self.name}">\n{self.description}\n</skill>'

    def to_activation_text(self) -> str:
        lines = [
            f'<active_skill name="{self.name}">',
            f"Skill name: {self.name}",
            f"Skill directory: {self.directory}",
            "Skill instructions:",
            self.body.strip(),
        ]

        resource_summary = self.resource_summary()
        if resource_summary:
            lines.append("Resource summary:")
            lines.extend(f"- {item}" for item in resource_summary)
            lines.append("Bundled files are not loaded yet.")
            lines.append("Use list_skill_resources to inspect available files.")
            lines.append("Use read_skill_resource to load one specific file only when needed.")

        lines.append("</active_skill>")
        return "\n".join(lines).strip()


class SkillRuntimeState:
    def __init__(self, active_skill_names: list[str] | None = None) -> None:
        self._active_skill_names = set(active_skill_names or [])

    def activate(self, skill_name: str) -> None:
        self._active_skill_names.add(skill_name)

    def is_active(self, skill_name: str) -> bool:
        return skill_name in self._active_skill_names

    def names(self) -> list[str]:
        return sorted(self._active_skill_names)
