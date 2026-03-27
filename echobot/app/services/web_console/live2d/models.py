from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class Live2DModelCandidate:
    source: str
    source_root: Path
    model_path: Path
    runtime_root: Path

    @property
    def model_relative_path(self) -> Path:
        return self.model_path.relative_to(self.source_root)

    @property
    def runtime_relative_path(self) -> Path:
        return self.runtime_root.relative_to(self.source_root)

    @property
    def model_name(self) -> str:
        return self.model_path.name.removesuffix(".model3.json")


@dataclass(slots=True, frozen=True)
class Live2DUploadFile:
    relative_path: str
    file_bytes: bytes


@dataclass(slots=True, frozen=True)
class Live2DVTubeConfig:
    path: Path
    payload: dict[str, Any]


@dataclass(slots=True, frozen=True)
class Live2DDiscoveredExpression:
    name: str
    file: str
    asset_relative_path: str
    note: str


@dataclass(slots=True, frozen=True)
class Live2DDiscoveredMotion:
    name: str
    file: str
    asset_relative_path: str
    note: str
    group: str
    index: int
    definition: dict[str, Any]


@dataclass(slots=True, frozen=True)
class Live2DDiscoveredHotkey:
    hotkey_key: str
    hotkey_id: str
    name: str
    action: str
    file: str
    shortcut_tokens: tuple[str, ...]
    shortcut_label: str
    target_kind: str
    supported: bool


@dataclass(slots=True, frozen=True)
class Live2DDiscoveredMetadata:
    expressions: tuple[Live2DDiscoveredExpression, ...]
    motions: tuple[Live2DDiscoveredMotion, ...]
    hotkeys: tuple[Live2DDiscoveredHotkey, ...]
    annotations_writable: bool
