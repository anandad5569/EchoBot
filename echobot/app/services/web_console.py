from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

from ...asr import ASRService
from ...tts import TTSService

DEFAULT_LIP_SYNC_PARAMETER_IDS = [
    "ParamMouthOpenY",
    "PARAM_MOUTH_OPEN_Y",
    "MouthOpenY",
]
DEFAULT_MOUTH_FORM_PARAMETER_IDS = [
    "ParamMouthForm",
    "PARAM_MOUTH_FORM",
    "MouthForm",
]
LIVE2D_SOURCE_WORKSPACE = "workspace"
LIVE2D_SOURCE_BUILTIN = "builtin"
STAGE_BACKGROUND_SOURCE_WORKSPACE = "workspace"
STAGE_BACKGROUND_SOURCE_BUILTIN = "builtin"
DEFAULT_STAGE_BACKGROUND_KEY = "default"
DEFAULT_STAGE_BACKGROUND_KIND = "none"
BUILTIN_STAGE_BACKGROUND_KIND = "builtin"
UPLOADED_STAGE_BACKGROUND_KIND = "uploaded"
ALLOWED_STAGE_BACKGROUND_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".avif",
}
ALLOWED_LIVE2D_UPLOAD_SUFFIXES = {
    ".json",
    ".moc3",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".avif",
    ".wav",
    ".mp3",
    ".ogg",
    ".m4a",
}
MAX_LIVE2D_UPLOAD_FILES = 512
MAX_LIVE2D_UPLOAD_TOTAL_BYTES = 200 * 1024 * 1024
MAX_STAGE_BACKGROUND_BYTES = 10 * 1024 * 1024


@dataclass(slots=True, frozen=True)
class Live2DModelCandidate:
    source: str
    root: Path
    model_path: Path


@dataclass(slots=True, frozen=True)
class Live2DUploadFile:
    relative_path: str
    file_bytes: bytes


class WebConsoleService:
    def __init__(
        self,
        workspace: Path,
        tts_service: TTSService,
        asr_service: ASRService,
    ) -> None:
        self._workspace = workspace
        self._tts_service = tts_service
        self._asr_service = asr_service
        self._workspace_live2d_root = workspace / ".echobot" / "live2d"
        self._workspace_stage_background_root = workspace / ".echobot" / "web" / "backgrounds"
        self._builtin_live2d_root = Path(__file__).resolve().parent.parent / "builtin_live2d"
        self._builtin_stage_background_root = (
            Path(__file__).resolve().parent.parent / "builtin_stage_backgrounds"
        )

    @property
    def tts_service(self) -> TTSService:
        return self._tts_service

    @property
    def asr_service(self) -> ASRService:
        return self._asr_service

    async def build_frontend_config(
        self,
        *,
        session_name: str,
        role_name: str,
        route_mode: str,
    ) -> dict[str, Any]:
        live2d = await asyncio.to_thread(self._discover_live2d_model_sync)
        stage = await asyncio.to_thread(self._build_stage_config_sync)
        return {
            "session_name": session_name,
            "role_name": role_name,
            "route_mode": route_mode,
            "live2d": live2d or self._empty_live2d_config(),
            "stage": stage,
            "asr": asdict(await self._asr_service.status_snapshot()),
            "tts": {
                "default_provider": self._tts_service.default_provider,
                "default_voice": self._tts_service.default_voice_for(),
                "default_voices": {
                    provider_name: self._tts_service.default_voice_for(provider_name)
                    for provider_name in self._tts_service.provider_names()
                },
                "providers": self._tts_service.providers_status(),
            },
        }

    def resolve_live2d_asset(self, asset_path: str) -> Path:
        source, relative_asset_path = self._parse_live2d_asset_path(asset_path)
        base_dir = self._live2d_root_for(source).resolve()
        candidate = (base_dir / relative_asset_path).resolve()
        if candidate != base_dir and base_dir not in candidate.parents:
            raise ValueError(f"Invalid live2d asset path: {asset_path}")
        if not candidate.is_file():
            raise FileNotFoundError(asset_path)
        return candidate

    async def build_stage_config(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._build_stage_config_sync)

    def resolve_stage_background_asset(self, asset_path: str) -> Path:
        source, relative_path = self._parse_stage_background_asset_path(asset_path)
        if not relative_path.parts:
            raise ValueError("Stage background path must not be empty")

        base_dir = self._stage_background_root_for(source).resolve()
        candidate = (base_dir / relative_path).resolve()
        if candidate != base_dir and base_dir not in candidate.parents:
            raise ValueError(f"Invalid stage background path: {asset_path}")
        if not candidate.is_file():
            raise FileNotFoundError(asset_path)
        return candidate

    async def save_stage_background(
        self,
        *,
        filename: str,
        content_type: str | None,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        cleaned_name = self._clean_stage_background_filename(filename)
        if not cleaned_name:
            raise ValueError("Background file name must not be empty")
        if not file_bytes:
            raise ValueError("Background file must not be empty")
        if len(file_bytes) > MAX_STAGE_BACKGROUND_BYTES:
            raise ValueError("Background file is too large. Keep it under 10 MB.")
        if content_type and not content_type.startswith("image/"):
            raise ValueError("Background file must be an image")

        target_path = await asyncio.to_thread(
            self._prepare_stage_background_path,
            cleaned_name,
        )
        await asyncio.to_thread(target_path.write_bytes, file_bytes)
        return await asyncio.to_thread(self._build_stage_config_sync)

    async def save_live2d_directory(
        self,
        *,
        uploaded_files: list[Live2DUploadFile],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._save_live2d_directory_sync,
            uploaded_files,
        )

    def _discover_live2d_model_sync(self) -> dict[str, Any] | None:
        model_candidates = self._discover_model_candidates()
        if not model_candidates:
            return None

        model_options = [
            self._build_live2d_model_option(model_candidate)
            for model_candidate in model_candidates
        ]
        selected_model = self._select_model_candidate(model_candidates)
        selected_option = next(
            option
            for model_candidate, option in zip(model_candidates, model_options, strict=True)
            if model_candidate == selected_model
        )
        return {
            "available": True,
            **selected_option,
            "models": model_options,
        }

    def _save_live2d_directory_sync(
        self,
        uploaded_files: list[Live2DUploadFile],
    ) -> dict[str, Any]:
        root_directory_name, files_to_save = self._normalize_live2d_upload_files(uploaded_files)
        target_directory = self._prepare_live2d_upload_directory(root_directory_name)

        try:
            for relative_path, file_bytes in files_to_save:
                target_file = target_directory.joinpath(*relative_path.parts[1:])
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_bytes(file_bytes)

            live2d_config = self._discover_live2d_model_sync()
            if live2d_config is None:
                raise ValueError("No Live2D model was found after upload")
            return live2d_config
        except Exception:
            shutil.rmtree(target_directory, ignore_errors=True)
            raise

    def _build_stage_config_sync(self) -> dict[str, Any]:
        backgrounds = [self._default_stage_background_option()]
        backgrounds.extend(
            self._stage_background_option_for(path, source=STAGE_BACKGROUND_SOURCE_BUILTIN)
            for path in self._stage_background_files(self._builtin_stage_background_root)
        )
        backgrounds.extend(
            self._stage_background_option_for(path, source=STAGE_BACKGROUND_SOURCE_WORKSPACE)
            for path in self._stage_background_files(self._workspace_stage_background_root)
        )

        return {
            "default_background_key": DEFAULT_STAGE_BACKGROUND_KEY,
            "backgrounds": backgrounds,
        }

    def _discover_model_candidates(self) -> list[Live2DModelCandidate]:
        model_candidates: list[Live2DModelCandidate] = []
        for source, root in self._live2d_roots():
            if not root.exists():
                continue

            model_files = sorted(
                root.rglob("*.model3.json"),
                key=lambda path: (len(path.parts), path.as_posix()),
            )
            model_candidates.extend(
                Live2DModelCandidate(
                    source=source,
                    root=root,
                    model_path=model_path,
                )
                for model_path in model_files
            )

        return model_candidates

    def _select_model_candidate(
        self,
        model_candidates: list[Live2DModelCandidate],
    ) -> Live2DModelCandidate:
        preferred_model = os.environ.get("ECHOBOT_WEB_LIVE2D_MODEL", "").strip()
        if not preferred_model:
            return model_candidates[0]

        normalized_preference = preferred_model.replace("\\", "/").strip("/").casefold()
        for model_candidate in model_candidates:
            if self._matches_preferred_model(model_candidate, normalized_preference):
                return model_candidate

        return model_candidates[0]

    def _matches_preferred_model(
        self,
        model_candidate: Live2DModelCandidate,
        normalized_preference: str,
    ) -> bool:
        relative_path = model_candidate.model_path.relative_to(model_candidate.root)
        relative_path_text = relative_path.as_posix().casefold()
        parent_path_text = relative_path.parent.as_posix().casefold()
        top_level_directory = self._model_directory_name(
            relative_path,
            model_candidate.model_path,
        ).casefold()
        model_name = model_candidate.model_path.name.removesuffix(".model3.json").casefold()
        source_prefixed_path = f"{model_candidate.source}/{relative_path_text}"
        source_named_path = f"{model_candidate.source}:{relative_path_text}"
        source_prefixed_directory = f"{model_candidate.source}/{top_level_directory}"
        source_named_directory = f"{model_candidate.source}:{top_level_directory}"

        return normalized_preference in {
            relative_path_text,
            parent_path_text,
            top_level_directory,
            model_name,
            source_prefixed_path,
            source_named_path,
            source_prefixed_directory,
            source_named_directory,
        }

    def _build_live2d_model_option(
        self,
        model_candidate: Live2DModelCandidate,
    ) -> dict[str, Any]:
        model_path = model_candidate.model_path
        relative_path = model_path.relative_to(model_candidate.root)
        model_data = self._load_json_file(model_path)
        display_info_path = self._display_info_path(model_path, model_data)
        parameter_ids = self._load_parameter_ids(display_info_path)

        lip_sync_ids = self._load_group_parameter_ids(model_data, "LipSync") or [
            parameter_id
            for parameter_id in parameter_ids
            if "MouthOpen" in parameter_id
        ] or [
            parameter_id
            for parameter_id in DEFAULT_LIP_SYNC_PARAMETER_IDS
            if parameter_id in parameter_ids
        ] or DEFAULT_LIP_SYNC_PARAMETER_IDS[:]

        mouth_form_parameter_id = next(
            (
                parameter_id
                for parameter_id in parameter_ids
                if "MouthForm" in parameter_id
            ),
            None,
        )
        if mouth_form_parameter_id is None:
            mouth_form_parameter_id = next(
                (
                    parameter_id
                    for parameter_id in DEFAULT_MOUTH_FORM_PARAMETER_IDS
                    if parameter_id in parameter_ids
                ),
                None,
            )

        return {
            "source": model_candidate.source,
            "selection_key": self._selection_key_for(model_candidate),
            "model_name": model_path.name.removesuffix(".model3.json"),
            "model_url": (
                f"/api/web/live2d/{model_candidate.source}/"
                f"{quote(relative_path.as_posix(), safe='/')}"
            ),
            "directory_name": self._model_directory_name(relative_path, model_path),
            "lip_sync_parameter_ids": lip_sync_ids,
            "mouth_form_parameter_id": mouth_form_parameter_id,
        }

    def _live2d_roots(self) -> list[tuple[str, Path]]:
        return [
            (LIVE2D_SOURCE_WORKSPACE, self._workspace_live2d_root),
            (LIVE2D_SOURCE_BUILTIN, self._builtin_live2d_root),
        ]

    def _live2d_root_for(self, source: str) -> Path:
        if source == LIVE2D_SOURCE_BUILTIN:
            return self._builtin_live2d_root
        return self._workspace_live2d_root

    def _parse_live2d_asset_path(self, asset_path: str) -> tuple[str, Path]:
        relative_path = Path(asset_path)
        if not relative_path.parts:
            raise ValueError("Live2D asset path must not be empty")

        source = relative_path.parts[0]
        if source in {LIVE2D_SOURCE_WORKSPACE, LIVE2D_SOURCE_BUILTIN}:
            resolved_path = Path(*relative_path.parts[1:])
            if not resolved_path.parts:
                raise ValueError(f"Invalid live2d asset path: {asset_path}")
            return source, resolved_path

        return LIVE2D_SOURCE_WORKSPACE, relative_path

    def _normalize_live2d_upload_files(
        self,
        uploaded_files: list[Live2DUploadFile],
    ) -> tuple[str, list[tuple[PurePosixPath, bytes]]]:
        if not uploaded_files:
            raise ValueError("Please choose a Live2D folder to upload")
        if len(uploaded_files) > MAX_LIVE2D_UPLOAD_FILES:
            raise ValueError("Too many files in Live2D folder. Keep it under 512 files.")

        normalized_files: list[tuple[PurePosixPath, bytes]] = []
        total_bytes = 0
        root_names: set[str] = set()

        for uploaded_file in uploaded_files:
            relative_path = self._clean_live2d_upload_relative_path(uploaded_file.relative_path)
            if not self._is_supported_live2d_upload_path(relative_path):
                continue

            if not uploaded_file.file_bytes:
                raise ValueError(f"Live2D file must not be empty: {relative_path.as_posix()}")

            total_bytes += len(uploaded_file.file_bytes)
            if total_bytes > MAX_LIVE2D_UPLOAD_TOTAL_BYTES:
                raise ValueError("Live2D folder is too large. Keep it under 200 MB.")

            normalized_files.append((relative_path, uploaded_file.file_bytes))
            root_names.add(relative_path.parts[0])

        if not normalized_files:
            raise ValueError("The selected folder does not contain supported Live2D runtime files")
        if len(root_names) != 1:
            raise ValueError("Please upload exactly one Live2D folder at a time")
        if not any(path.name.endswith(".model3.json") for path, _bytes in normalized_files):
            raise ValueError("The selected folder must include at least one .model3.json file")

        return next(iter(root_names)), normalized_files

    @staticmethod
    def _clean_live2d_upload_relative_path(relative_path: str) -> PurePosixPath:
        raw_path = str(relative_path or "").replace("\\", "/").strip()
        if not raw_path:
            raise ValueError("Live2D file path must not be empty")
        if raw_path.startswith("/"):
            raise ValueError(f"Invalid Live2D file path: {relative_path}")

        normalized_path = PurePosixPath(raw_path)
        if len(normalized_path.parts) < 2:
            raise ValueError("Please upload a Live2D folder instead of individual files")
        if any(part in {"", ".", ".."} for part in normalized_path.parts):
            raise ValueError(f"Invalid Live2D file path: {relative_path}")
        if any(":" in part for part in normalized_path.parts):
            raise ValueError(f"Invalid Live2D file path: {relative_path}")
        return normalized_path

    @staticmethod
    def _is_supported_live2d_upload_path(relative_path: PurePosixPath) -> bool:
        return relative_path.suffix.lower() in ALLOWED_LIVE2D_UPLOAD_SUFFIXES

    def _prepare_live2d_upload_directory(self, directory_name: str) -> Path:
        self._workspace_live2d_root.mkdir(parents=True, exist_ok=True)

        cleaned_name = self._clean_live2d_upload_directory_name(directory_name)
        candidate = self._workspace_live2d_root / cleaned_name
        index = 2
        while candidate.exists():
            candidate = self._workspace_live2d_root / f"{cleaned_name}-{index}"
            index += 1

        candidate.mkdir(parents=True, exist_ok=False)
        return candidate

    @staticmethod
    def _clean_live2d_upload_directory_name(directory_name: str) -> str:
        raw_name = Path(str(directory_name or "")).name.strip()
        cleaned_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", raw_name).strip(" .")
        return cleaned_name or "live2d-model"

    @staticmethod
    def _model_directory_name(relative_path: Path, model_path: Path) -> str:
        if len(relative_path.parts) > 1:
            return relative_path.parts[0]
        return model_path.name.removesuffix(".model3.json")

    @staticmethod
    def _display_info_path(
        model_path: Path,
        model_data: dict[str, Any],
    ) -> Path | None:
        file_references = model_data.get("FileReferences", {})
        display_info = file_references.get("DisplayInfo")
        if not display_info:
            return None
        return model_path.parent / display_info

    def _load_parameter_ids(self, display_info_path: Path | None) -> list[str]:
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
    def _load_group_parameter_ids(
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

    @staticmethod
    def _load_json_file(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _selection_key_for(self, model_candidate: Live2DModelCandidate) -> str:
        relative_path = model_candidate.model_path.relative_to(model_candidate.root)
        return f"{model_candidate.source}:{relative_path.as_posix()}"

    @staticmethod
    def _default_stage_background_option() -> dict[str, Any]:
        return {
            "key": DEFAULT_STAGE_BACKGROUND_KEY,
            "label": "不使用背景",
            "url": "",
            "kind": DEFAULT_STAGE_BACKGROUND_KIND,
        }

    def _stage_background_option_for(self, path: Path, *, source: str) -> dict[str, Any]:
        if source == STAGE_BACKGROUND_SOURCE_BUILTIN:
            key = f"{STAGE_BACKGROUND_SOURCE_BUILTIN}:{path.name}"
            url = f"/api/web/stage/backgrounds/{STAGE_BACKGROUND_SOURCE_BUILTIN}/{quote(path.name)}"
            kind = BUILTIN_STAGE_BACKGROUND_KIND
        else:
            key = path.name
            url = f"/api/web/stage/backgrounds/{quote(path.name)}"
            kind = UPLOADED_STAGE_BACKGROUND_KIND

        return {
            "key": key,
            "label": path.stem,
            "url": url,
            "kind": kind,
        }

    @staticmethod
    def _stage_background_files(root: Path) -> list[Path]:
        if not root.exists():
            return []

        return sorted(
            (
                path
                for path in root.iterdir()
                if path.is_file() and path.suffix.lower() in ALLOWED_STAGE_BACKGROUND_SUFFIXES
            ),
            key=lambda path: path.name.casefold(),
        )

    def _stage_background_root_for(self, source: str) -> Path:
        if source == STAGE_BACKGROUND_SOURCE_BUILTIN:
            return self._builtin_stage_background_root
        return self._workspace_stage_background_root

    @staticmethod
    def _parse_stage_background_asset_path(asset_path: str) -> tuple[str, Path]:
        relative_path = Path(asset_path)
        if not relative_path.parts:
            raise ValueError("Stage background path must not be empty")

        source = relative_path.parts[0]
        if source in {STAGE_BACKGROUND_SOURCE_WORKSPACE, STAGE_BACKGROUND_SOURCE_BUILTIN}:
            resolved_path = Path(*relative_path.parts[1:])
            if not resolved_path.parts:
                raise ValueError(f"Invalid stage background path: {asset_path}")
            return source, resolved_path

        return STAGE_BACKGROUND_SOURCE_WORKSPACE, relative_path

    def _prepare_stage_background_path(self, filename: str) -> Path:
        self._workspace_stage_background_root.mkdir(parents=True, exist_ok=True)

        original_path = Path(filename)
        stem = original_path.stem
        suffix = original_path.suffix.lower()
        candidate = self._workspace_stage_background_root / f"{stem}{suffix}"
        index = 2
        while candidate.exists():
            candidate = self._workspace_stage_background_root / f"{stem}-{index}{suffix}"
            index += 1
        return candidate

    @staticmethod
    def _clean_stage_background_filename(filename: str) -> str:
        raw_name = Path(str(filename or "")).name.strip()
        if not raw_name:
            return ""

        suffix = Path(raw_name).suffix.lower()
        if suffix not in ALLOWED_STAGE_BACKGROUND_SUFFIXES:
            raise ValueError("Only png, jpg, jpeg, webp, gif, and avif backgrounds are supported")

        stem = Path(raw_name).stem.strip()
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem)
        stem = re.sub(r"\s+", "_", stem)
        stem = re.sub(r"_+", "_", stem).strip(" ._")
        if not stem:
            stem = "background"
        return f"{stem}{suffix}"

    @staticmethod
    def _empty_live2d_config() -> dict[str, Any]:
        return {
            "available": False,
            "source": "",
            "selection_key": "",
            "model_name": "",
            "model_url": "",
            "directory_name": "",
            "lip_sync_parameter_ids": DEFAULT_LIP_SYNC_PARAMETER_IDS[:],
            "mouth_form_parameter_id": None,
            "models": [],
        }
