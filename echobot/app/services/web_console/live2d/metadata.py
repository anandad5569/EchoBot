from __future__ import annotations

import json
import re
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from .annotations import Live2DAnnotationsRepository
from .constants import (
    HOTKEY_TOKEN_MAP,
    LIVE2D_AUTO_MOTION_GROUP,
    LIVE2D_IDLE_MOTION_GROUP,
    LIVE2D_SOURCE_WORKSPACE,
    SUPPORTED_HOTKEY_ACTIONS,
)
from .models import (
    Live2DDiscoveredExpression,
    Live2DDiscoveredHotkey,
    Live2DDiscoveredMetadata,
    Live2DDiscoveredMotion,
    Live2DModelCandidate,
    Live2DVTubeConfig,
)


class Live2DMetadataService:
    def __init__(self, annotations_repository: Live2DAnnotationsRepository) -> None:
        self._annotations_repository = annotations_repository

    def load_model_data(self, candidate: Live2DModelCandidate) -> dict[str, Any]:
        return self._load_json_file(candidate.model_path)

    def load_parameter_ids(
        self,
        candidate: Live2DModelCandidate,
        model_data: dict[str, Any],
    ) -> list[str]:
        display_info_path = self._display_info_path(candidate, model_data)
        if display_info_path is None or not display_info_path.exists():
            return []

        display_info = self._load_json_file(display_info_path)
        parameters = display_info.get("Parameters", [])
        return [
            item["Id"]
            for item in parameters
            if isinstance(item, dict) and isinstance(item.get("Id"), str)
        ]

    @staticmethod
    def load_group_parameter_ids(
        model_data: dict[str, Any],
        group_name: str,
    ) -> list[str]:
        groups = model_data.get("Groups", [])
        for group in groups:
            if not isinstance(group, dict):
                continue
            if group.get("Target") != "Parameter":
                continue
            if group.get("Name") != group_name:
                continue

            return [
                parameter_id
                for parameter_id in group.get("Ids", [])
                if isinstance(parameter_id, str)
            ]

        return []

    def discover_metadata(
        self,
        candidate: Live2DModelCandidate,
        model_data: dict[str, Any],
    ) -> Live2DDiscoveredMetadata:
        annotations_payload = self._annotations_repository.load(candidate.runtime_root)
        vtube_config = self._load_matching_vtube_config(candidate)
        expressions = self._discover_expressions(
            candidate,
            model_data,
            vtube_config,
            annotations_payload,
        )
        motions = self._discover_motions(
            candidate,
            model_data,
            vtube_config,
            annotations_payload,
        )
        hotkeys = self._discover_hotkeys(
            candidate,
            vtube_config,
            expressions,
            motions,
            annotations_payload,
        )

        return Live2DDiscoveredMetadata(
            expressions=tuple(expressions),
            motions=tuple(motions),
            hotkeys=tuple(hotkeys),
            annotations_writable=candidate.source == LIVE2D_SOURCE_WORKSPACE,
        )

    def patch_model_data(
        self,
        candidate: Live2DModelCandidate,
        model_data: dict[str, Any],
        metadata: Live2DDiscoveredMetadata,
    ) -> dict[str, Any]:
        patched_model = json.loads(json.dumps(model_data))
        file_references = patched_model.setdefault("FileReferences", {})
        if not isinstance(file_references, dict):
            file_references = {}
            patched_model["FileReferences"] = file_references

        relative_expressions = [
            {
                "Name": expression.name,
                "File": self._relative_file_to_model_parent(
                    candidate,
                    expression.asset_relative_path,
                ),
            }
            for expression in metadata.expressions
        ]
        if relative_expressions:
            file_references["Expressions"] = relative_expressions

        existing_motions = file_references.get("Motions", {})
        if not isinstance(existing_motions, dict):
            existing_motions = {}
        patched_motions: dict[str, list[dict[str, Any]]] = {
            group_name: [
                dict(item)
                for item in entries
                if isinstance(item, dict)
            ]
            for group_name, entries in existing_motions.items()
            if isinstance(group_name, str) and isinstance(entries, list)
        }

        for motion in metadata.motions:
            motion_entry = dict(motion.definition)
            motion_entry["File"] = self._relative_file_to_model_parent(
                candidate,
                motion.asset_relative_path,
            )
            group_entries = patched_motions.setdefault(motion.group, [])
            while len(group_entries) <= motion.index:
                group_entries.append({})

            existing_file = group_entries[motion.index].get("File")
            if isinstance(existing_file, str) and existing_file.strip():
                continue
            group_entries[motion.index] = motion_entry

        if patched_motions:
            file_references["Motions"] = patched_motions

        return patched_model

    @staticmethod
    def hotkey_payload(hotkey: Live2DDiscoveredHotkey) -> dict[str, Any]:
        return {
            "hotkey_key": hotkey.hotkey_key,
            "hotkey_id": hotkey.hotkey_id,
            "name": hotkey.name,
            "action": hotkey.action,
            "file": hotkey.file,
            "shortcut_tokens": list(hotkey.shortcut_tokens),
            "shortcut_label": hotkey.shortcut_label,
            "target_kind": hotkey.target_kind,
            "supported": hotkey.supported,
        }

    @staticmethod
    def normalize_annotation_file(file: str) -> str:
        normalized_file = str(file or "").replace("\\", "/").strip().lstrip("./")
        if not normalized_file:
            raise ValueError("Live2D annotation file must not be empty")
        if normalized_file.startswith("/"):
            raise ValueError(f"Invalid Live2D annotation file: {file}")

        file_path = PurePosixPath(normalized_file)
        if any(part in {"", ".", ".."} for part in file_path.parts):
            raise ValueError(f"Invalid Live2D annotation file: {file}")
        return file_path.as_posix()

    def normalize_shortcut_tokens(self, shortcut_tokens: list[str]) -> list[str]:
        normalized_tokens: list[str] = []
        for token in shortcut_tokens[:3]:
            normalized_token = self._normalize_hotkey_token(token)
            if normalized_token and normalized_token not in normalized_tokens:
                normalized_tokens.append(normalized_token)
        return normalized_tokens

    def _load_matching_vtube_config(
        self,
        candidate: Live2DModelCandidate,
    ) -> Live2DVTubeConfig | None:
        vtube_paths = sorted(
            candidate.runtime_root.rglob("*.vtube.json"),
            key=lambda path: (len(path.parts), path.as_posix()),
        )
        if not vtube_paths:
            return None

        resolved_model_path = candidate.model_path.resolve()
        matching_configs: list[Live2DVTubeConfig] = []
        fallback_configs: list[Live2DVTubeConfig] = []

        for vtube_path in vtube_paths:
            try:
                payload = self._load_json_file(vtube_path)
            except (OSError, json.JSONDecodeError):
                continue

            vtube_config = Live2DVTubeConfig(
                path=vtube_path.resolve(),
                payload=payload,
            )
            file_references = payload.get("FileReferences", {})
            model_reference = file_references.get("Model")
            if isinstance(model_reference, str) and model_reference.strip():
                reference_path = (vtube_path.parent / model_reference).resolve()
                if reference_path == resolved_model_path:
                    matching_configs.append(vtube_config)
                    continue
            fallback_configs.append(vtube_config)

        if matching_configs:
            return min(
                matching_configs,
                key=lambda item: len(item.path.relative_to(candidate.runtime_root).parts),
            )
        if len(fallback_configs) == 1:
            return fallback_configs[0]
        return None

    def _discover_expressions(
        self,
        candidate: Live2DModelCandidate,
        model_data: dict[str, Any],
        vtube_config: Live2DVTubeConfig | None,
        annotations_payload: dict[str, Any],
    ) -> list[Live2DDiscoveredExpression]:
        expression_map: dict[str, Live2DDiscoveredExpression] = {}
        note_map = annotations_payload.get("expressions", {})

        file_references = model_data.get("FileReferences", {})
        expressions = file_references.get("Expressions", [])
        if isinstance(expressions, list):
            for expression in expressions:
                if not isinstance(expression, dict):
                    continue
                self._add_expression_reference(
                    expression_map,
                    candidate=candidate,
                    base_directory=candidate.model_path.parent,
                    file_reference=expression.get("File"),
                    name_hint=expression.get("Name"),
                    note_map=note_map,
                )

        if vtube_config is not None:
            hotkeys = vtube_config.payload.get("Hotkeys", [])
            if isinstance(hotkeys, list):
                for hotkey in hotkeys:
                    if not isinstance(hotkey, dict):
                        continue
                    if hotkey.get("Action") != "ToggleExpression":
                        continue
                    self._add_expression_reference(
                        expression_map,
                        candidate=candidate,
                        base_directory=vtube_config.path.parent,
                        file_reference=hotkey.get("File"),
                        name_hint=hotkey.get("Name"),
                        note_map=note_map,
                    )

        for expression_path in sorted(candidate.runtime_root.rglob("*.exp3.json")):
            note_key = expression_path.relative_to(candidate.runtime_root).as_posix()
            if note_key in expression_map:
                continue

            expression_map[note_key] = Live2DDiscoveredExpression(
                name=self._asset_name_from_file(expression_path.name, ".exp3.json"),
                file=note_key,
                asset_relative_path=expression_path.relative_to(candidate.source_root).as_posix(),
                note=self._annotation_note_for(note_map, note_key),
            )

        return list(expression_map.values())

    def _add_expression_reference(
        self,
        expression_map: dict[str, Live2DDiscoveredExpression],
        *,
        candidate: Live2DModelCandidate,
        base_directory: Path,
        file_reference: Any,
        name_hint: Any,
        note_map: dict[str, Any],
    ) -> None:
        asset_path = self._resolve_runtime_reference(
            runtime_root=candidate.runtime_root,
            base_directory=base_directory,
            file_reference=file_reference,
        )
        if asset_path is None:
            return

        note_key = asset_path.relative_to(candidate.runtime_root).as_posix()
        if note_key in expression_map:
            return

        expression_map[note_key] = Live2DDiscoveredExpression(
            name=str(name_hint or "").strip()
            or self._asset_name_from_file(asset_path.name, ".exp3.json"),
            file=note_key,
            asset_relative_path=asset_path.relative_to(candidate.source_root).as_posix(),
            note=self._annotation_note_for(note_map, note_key),
        )

    def _discover_motions(
        self,
        candidate: Live2DModelCandidate,
        model_data: dict[str, Any],
        vtube_config: Live2DVTubeConfig | None,
        annotations_payload: dict[str, Any],
    ) -> list[Live2DDiscoveredMotion]:
        pending_motions: list[dict[str, Any]] = []
        note_map = annotations_payload.get("motions", {})

        file_references = model_data.get("FileReferences", {})
        motions = file_references.get("Motions", {})
        if isinstance(motions, dict):
            for group_name, entries in motions.items():
                if not isinstance(group_name, str) or not isinstance(entries, list):
                    continue
                for index, motion_entry in enumerate(entries):
                    if not isinstance(motion_entry, dict):
                        continue
                    self._append_motion_reference(
                        pending_motions,
                        candidate=candidate,
                        base_directory=candidate.model_path.parent,
                        file_reference=motion_entry.get("File"),
                        group=group_name,
                        index=index,
                        name_hint=motion_entry.get("Name"),
                        note_map=note_map,
                        definition=motion_entry,
                    )

        if vtube_config is not None:
            vtube_file_references = vtube_config.payload.get("FileReferences", {})
            idle_animation = vtube_file_references.get("IdleAnimation")
            if isinstance(idle_animation, str) and idle_animation.strip():
                self._append_motion_reference(
                    pending_motions,
                    candidate=candidate,
                    base_directory=vtube_config.path.parent,
                    file_reference=idle_animation,
                    group=LIVE2D_IDLE_MOTION_GROUP,
                    index=-1,
                    name_hint="Idle",
                    note_map=note_map,
                    definition={"File": idle_animation},
                )

            hotkeys = vtube_config.payload.get("Hotkeys", [])
            if isinstance(hotkeys, list):
                for hotkey in hotkeys:
                    if not isinstance(hotkey, dict):
                        continue
                    if hotkey.get("Action") != "TriggerAnimation":
                        continue
                    self._append_motion_reference(
                        pending_motions,
                        candidate=candidate,
                        base_directory=vtube_config.path.parent,
                        file_reference=hotkey.get("File"),
                        group=LIVE2D_AUTO_MOTION_GROUP,
                        index=-1,
                        name_hint=hotkey.get("Name"),
                        note_map=note_map,
                        definition={"File": hotkey.get("File")},
                    )

        for motion_path in sorted(candidate.runtime_root.rglob("*.motion3.json")):
            note_key = motion_path.relative_to(candidate.runtime_root).as_posix()
            if any(item["file"] == note_key for item in pending_motions):
                continue

            pending_motions.append(
                {
                    "name": self._asset_name_from_file(motion_path.name, ".motion3.json"),
                    "file": note_key,
                    "asset_relative_path": motion_path.relative_to(candidate.source_root).as_posix(),
                    "note": self._annotation_note_for(note_map, note_key),
                    "group": LIVE2D_AUTO_MOTION_GROUP,
                    "index": -1,
                    "definition": {"File": note_key},
                }
            )

        grouped_indexes: dict[str, int] = {}
        seen_files: set[str] = set()
        discovered_motions: list[Live2DDiscoveredMotion] = []

        for motion in pending_motions:
            file_key = motion["file"]
            if file_key in seen_files:
                continue
            seen_files.add(file_key)

            group_name = motion["group"]
            index = motion["index"]
            if index < 0:
                next_index = grouped_indexes.get(group_name, 0)
                grouped_indexes[group_name] = next_index + 1
                index = next_index
            else:
                grouped_indexes[group_name] = max(
                    grouped_indexes.get(group_name, 0),
                    index + 1,
                )

            discovered_motions.append(
                Live2DDiscoveredMotion(
                    name=motion["name"],
                    file=file_key,
                    asset_relative_path=motion["asset_relative_path"],
                    note=motion["note"],
                    group=group_name,
                    index=index,
                    definition=motion["definition"],
                )
            )

        return discovered_motions

    def _append_motion_reference(
        self,
        pending_motions: list[dict[str, Any]],
        *,
        candidate: Live2DModelCandidate,
        base_directory: Path,
        file_reference: Any,
        group: str,
        index: int,
        name_hint: Any,
        note_map: dict[str, Any],
        definition: dict[str, Any],
    ) -> None:
        asset_path = self._resolve_runtime_reference(
            runtime_root=candidate.runtime_root,
            base_directory=base_directory,
            file_reference=file_reference,
        )
        if asset_path is None:
            return

        note_key = asset_path.relative_to(candidate.runtime_root).as_posix()
        if any(item["file"] == note_key for item in pending_motions):
            return

        motion_definition = dict(definition)
        motion_definition["File"] = note_key
        pending_motions.append(
            {
                "name": str(name_hint or "").strip()
                or self._asset_name_from_file(asset_path.name, ".motion3.json"),
                "file": note_key,
                "asset_relative_path": asset_path.relative_to(candidate.source_root).as_posix(),
                "note": self._annotation_note_for(note_map, note_key),
                "group": group,
                "index": index,
                "definition": motion_definition,
            }
        )

    def _discover_hotkeys(
        self,
        candidate: Live2DModelCandidate,
        vtube_config: Live2DVTubeConfig | None,
        expressions: list[Live2DDiscoveredExpression],
        motions: list[Live2DDiscoveredMotion],
        annotations_payload: dict[str, Any],
    ) -> list[Live2DDiscoveredHotkey]:
        if vtube_config is None:
            return []

        hotkeys = vtube_config.payload.get("Hotkeys", [])
        if not isinstance(hotkeys, list):
            return []

        expression_files = {item.file for item in expressions}
        motion_files = {item.file for item in motions}
        hotkey_overrides = annotations_payload.get("hotkeys", {})
        discovered_hotkeys: list[Live2DDiscoveredHotkey] = []

        for hotkey in hotkeys:
            if not isinstance(hotkey, dict):
                continue

            action = str(hotkey.get("Action") or "").strip()
            normalized_file = self._hotkey_target_file(
                candidate,
                vtube_config.path.parent,
                hotkey,
                expression_files=expression_files,
                motion_files=motion_files,
            )
            hotkey_id = str(hotkey.get("HotkeyID") or "").strip()
            hotkey_key = self._hotkey_key_for(
                hotkey_id=hotkey_id,
                action=action,
                file=normalized_file,
            )

            shortcut_override = self._annotation_shortcut_tokens(
                hotkey_overrides,
                hotkey_key,
            )
            shortcut_tokens = (
                shortcut_override
                if shortcut_override is not None
                else self._extract_shortcut_tokens(hotkey)
            )
            shortcut_label = self._shortcut_label_for(hotkey, shortcut_tokens)

            target_kind = ""
            if action == "ToggleExpression":
                target_kind = "expression"
            elif action == "TriggerAnimation":
                target_kind = "motion"
            elif action == "RemoveAllExpressions":
                target_kind = "system"

            supported = action in SUPPORTED_HOTKEY_ACTIONS
            if action == "ToggleExpression":
                supported = supported and normalized_file in expression_files
            elif action == "TriggerAnimation":
                supported = supported and normalized_file in motion_files

            discovered_hotkeys.append(
                Live2DDiscoveredHotkey(
                    hotkey_key=hotkey_key,
                    hotkey_id=hotkey_id,
                    name=str(hotkey.get("Name") or action or "Hotkey").strip() or "Hotkey",
                    action=action,
                    file=normalized_file,
                    shortcut_tokens=tuple(shortcut_tokens),
                    shortcut_label=shortcut_label,
                    target_kind=target_kind,
                    supported=supported,
                )
            )

        return discovered_hotkeys

    def _hotkey_target_file(
        self,
        candidate: Live2DModelCandidate,
        base_directory: Path,
        hotkey: dict[str, Any],
        *,
        expression_files: set[str],
        motion_files: set[str],
    ) -> str:
        action = str(hotkey.get("Action") or "").strip()
        file_reference = str(hotkey.get("File") or "").replace("\\", "/").strip().lstrip("./")
        if not file_reference:
            return ""

        asset_path = self._resolve_runtime_reference(
            runtime_root=candidate.runtime_root,
            base_directory=base_directory,
            file_reference=file_reference,
        )
        if asset_path is not None:
            return asset_path.relative_to(candidate.runtime_root).as_posix()

        if action == "ToggleExpression":
            return self._match_file_by_suffix(expression_files, file_reference)
        if action == "TriggerAnimation":
            return self._match_file_by_suffix(motion_files, file_reference)
        return file_reference

    def _extract_shortcut_tokens(self, hotkey: dict[str, Any]) -> list[str]:
        triggers = hotkey.get("Triggers", {})
        if not isinstance(triggers, dict):
            return []

        tokens: list[str] = []
        for trigger_name in ("Trigger1", "Trigger2", "Trigger3"):
            normalized_token = self._normalize_hotkey_token(triggers.get(trigger_name))
            if normalized_token and normalized_token not in tokens:
                tokens.append(normalized_token)
        return tokens

    def _annotation_shortcut_tokens(
        self,
        hotkeys_map: dict[str, Any],
        hotkey_key: str,
    ) -> list[str] | None:
        hotkey_payload = hotkeys_map.get(hotkey_key)
        if not isinstance(hotkey_payload, dict):
            return None

        shortcut_tokens = hotkey_payload.get("shortcut_tokens")
        if not isinstance(shortcut_tokens, list):
            return None
        return self.normalize_shortcut_tokens(shortcut_tokens)

    def _shortcut_label_for(
        self,
        hotkey: dict[str, Any],
        shortcut_tokens: list[str],
    ) -> str:
        if shortcut_tokens:
            return self._shortcut_label_from_tokens(shortcut_tokens)

        triggers = hotkey.get("Triggers", {})
        if isinstance(triggers, dict) and int(triggers.get("ScreenButton", -1) or -1) >= 0:
            return "Screen Button"
        return "Unassigned"

    def _shortcut_label_from_tokens(self, shortcut_tokens: list[str]) -> str:
        if shortcut_tokens:
            return " + ".join(self._display_hotkey_token(token) for token in shortcut_tokens)
        return "Unassigned"

    def _normalize_hotkey_token(self, token: Any) -> str:
        token_text = str(token or "").strip()
        if not token_text:
            return ""

        mapped_token = HOTKEY_TOKEN_MAP.get(token_text.casefold())
        if mapped_token:
            return mapped_token

        if re.fullmatch(r"N\d", token_text):
            return f"digit{token_text[-1]}"
        if re.fullmatch(r"F\d{1,2}", token_text, flags=re.IGNORECASE):
            return token_text.casefold()
        if re.fullmatch(r"[A-Z]", token_text, flags=re.IGNORECASE):
            return f"key{token_text.casefold()}"
        if re.fullmatch(r"NumPad\d", token_text, flags=re.IGNORECASE):
            return f"numpad{token_text[-1]}"
        if re.fullmatch(
            r"NumPad(Add|Subtract|Multiply|Divide|Decimal)",
            token_text,
            flags=re.IGNORECASE,
        ):
            return f"numpad{token_text[6:].casefold()}"

        return token_text.casefold()

    @staticmethod
    def _display_hotkey_token(token: str) -> str:
        display_map = {
            "alt": "Alt",
            "control": "Ctrl",
            "shift": "Shift",
            "meta": "Meta",
            "space": "Space",
            "tab": "Tab",
            "enter": "Enter",
            "escape": "Esc",
            "backspace": "Backspace",
            "delete": "Delete",
            "insert": "Insert",
            "home": "Home",
            "end": "End",
            "pageup": "PageUp",
            "pagedown": "PageDown",
            "arrowup": "Up",
            "arrowdown": "Down",
            "arrowleft": "Left",
            "arrowright": "Right",
            "minus": "-",
            "equal": "=",
            "comma": ",",
            "period": ".",
            "slash": "/",
            "backslash": "\\",
            "semicolon": ";",
            "quote": "'",
            "backquote": "`",
            "capslock": "CapsLock",
        }
        if token in display_map:
            return display_map[token]
        if token.startswith("digit"):
            return token.removeprefix("digit")
        if token.startswith("key"):
            return token.removeprefix("key").upper()
        if token.startswith("numpad"):
            return f"Numpad {token.removeprefix('numpad').title()}"
        if re.fullmatch(r"f\d{1,2}", token):
            return token.upper()
        return token

    def _resolve_runtime_reference(
        self,
        *,
        runtime_root: Path,
        base_directory: Path,
        file_reference: Any,
    ) -> Path | None:
        reference_path = self._normalize_reference_path(file_reference)
        if reference_path is None:
            return None

        resolved_path = (base_directory / reference_path).resolve()
        resolved_runtime_root = runtime_root.resolve()
        if resolved_path != resolved_runtime_root and resolved_runtime_root not in resolved_path.parents:
            return None
        if not resolved_path.is_file():
            return None
        return resolved_path

    @staticmethod
    def _normalize_reference_path(file_reference: Any) -> Path | None:
        normalized_reference = str(file_reference or "").replace("\\", "/").strip()
        if not normalized_reference:
            return None

        reference_path = Path(normalized_reference)
        if reference_path.is_absolute():
            return None
        if any(part == "" for part in reference_path.parts):
            return None
        if any(":" in part for part in reference_path.parts):
            return None
        return reference_path

    def _display_info_path(
        self,
        candidate: Live2DModelCandidate,
        model_data: dict[str, Any],
    ) -> Path | None:
        file_references = model_data.get("FileReferences", {})
        display_info = file_references.get("DisplayInfo")
        if not display_info:
            return None
        return candidate.model_path.parent / display_info

    @staticmethod
    def _load_json_file(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _annotation_note_for(note_map: dict[str, Any], note_key: str) -> str:
        note_value = note_map.get(note_key)
        if isinstance(note_value, str):
            return note_value.strip()
        return ""

    @staticmethod
    def _asset_name_from_file(filename: str, suffix: str) -> str:
        if filename.endswith(suffix):
            return filename.removesuffix(suffix)
        return Path(filename).stem

    @staticmethod
    def _match_file_by_suffix(available_files: set[str], file_reference: str) -> str:
        normalized_reference = str(file_reference or "").replace("\\", "/").strip().lstrip("./")
        if not normalized_reference:
            return ""
        if normalized_reference in available_files:
            return normalized_reference

        matches = [
            item
            for item in available_files
            if item == normalized_reference or item.endswith(f"/{normalized_reference}")
        ]
        if len(matches) == 1:
            return matches[0]
        return normalized_reference

    @staticmethod
    def _hotkey_key_for(*, hotkey_id: str, action: str, file: str) -> str:
        normalized_hotkey_id = str(hotkey_id or "").strip()
        if normalized_hotkey_id:
            return normalized_hotkey_id

        normalized_action = str(action or "").strip()
        normalized_file = str(file or "").replace("\\", "/").strip().lstrip("./")
        if normalized_file:
            return f"{normalized_action}:{normalized_file}"
        return normalized_action

    def _relative_file_to_model_parent(
        self,
        candidate: Live2DModelCandidate,
        asset_relative_path: str,
    ) -> str:
        asset_path = candidate.source_root / asset_relative_path
        return asset_path.relative_to(candidate.model_path.parent).as_posix()
