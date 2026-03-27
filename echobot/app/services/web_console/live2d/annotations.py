from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any
from typing import Callable

from .constants import LIVE2D_ANNOTATIONS_FILENAME


class Live2DAnnotationsRepository:
    def __init__(self, filename: str = LIVE2D_ANNOTATIONS_FILENAME) -> None:
        self._filename = filename
        self._guard_lock = threading.Lock()
        self._path_locks: dict[Path, threading.Lock] = {}

    def load(self, runtime_root: Path) -> dict[str, Any]:
        return self._load_from_path(runtime_root / self._filename)

    def save_annotation(
        self,
        runtime_root: Path,
        *,
        kind: str,
        file: str,
        note: str,
    ) -> None:
        annotations_key = f"{kind}s"

        def update(payload: dict[str, Any]) -> bool:
            annotations_map = payload.get(annotations_key)
            if not isinstance(annotations_map, dict):
                annotations_map = {}
                payload[annotations_key] = annotations_map

            normalized_note = str(note or "").strip()
            previous_note = annotations_map.get(file)
            if normalized_note:
                annotations_map[file] = normalized_note
            else:
                annotations_map.pop(file, None)

            return previous_note != normalized_note

        self._update_payload(runtime_root, update)

    def save_hotkey(
        self,
        runtime_root: Path,
        *,
        hotkey_key: str,
        shortcut_tokens: list[str],
        restore_default: bool,
    ) -> None:
        def update(payload: dict[str, Any]) -> bool:
            hotkeys_map = payload.get("hotkeys")
            if not isinstance(hotkeys_map, dict):
                hotkeys_map = {}
                payload["hotkeys"] = hotkeys_map

            if restore_default:
                return hotkeys_map.pop(hotkey_key, None) is not None

            next_payload = {
                "shortcut_tokens": list(shortcut_tokens),
            }
            previous_payload = hotkeys_map.get(hotkey_key)
            hotkeys_map[hotkey_key] = next_payload
            return previous_payload != next_payload

        self._update_payload(runtime_root, update)

    def _update_payload(
        self,
        runtime_root: Path,
        update: Callable[[dict[str, Any]], bool],
    ) -> None:
        annotations_path = runtime_root / self._filename
        path_lock = self._lock_for(annotations_path)
        with path_lock:
            payload = self._load_from_path(annotations_path)
            changed = update(payload)
            if not changed:
                return

            payload["version"] = 1
            self._write_payload(annotations_path, payload)

    def _lock_for(self, annotations_path: Path) -> threading.Lock:
        with self._guard_lock:
            path_lock = self._path_locks.get(annotations_path)
            if path_lock is None:
                path_lock = threading.Lock()
                self._path_locks[annotations_path] = path_lock
            return path_lock

    @staticmethod
    def _empty_payload() -> dict[str, Any]:
        return {
            "version": 1,
            "expressions": {},
            "motions": {},
            "hotkeys": {},
        }

    def _load_from_path(self, annotations_path: Path) -> dict[str, Any]:
        if not annotations_path.exists():
            return self._empty_payload()

        try:
            payload = json.loads(annotations_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty_payload()

        if not isinstance(payload, dict):
            return self._empty_payload()

        expressions = payload.get("expressions")
        motions = payload.get("motions")
        hotkeys = payload.get("hotkeys")
        return {
            "version": 1,
            "expressions": expressions if isinstance(expressions, dict) else {},
            "motions": motions if isinstance(motions, dict) else {},
            "hotkeys": hotkeys if isinstance(hotkeys, dict) else {},
        }

    def _write_payload(self, annotations_path: Path, payload: dict[str, Any]) -> None:
        annotations_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = annotations_path.parent / (
            f".{annotations_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, annotations_path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
