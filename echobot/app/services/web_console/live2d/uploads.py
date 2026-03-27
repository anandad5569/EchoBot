from __future__ import annotations

import re
import shutil
from pathlib import Path
from pathlib import PurePosixPath

from .constants import (
    ALLOWED_LIVE2D_UPLOAD_SUFFIXES,
    MAX_LIVE2D_UPLOAD_FILES,
    MAX_LIVE2D_UPLOAD_TOTAL_BYTES,
)
from .models import Live2DUploadFile


class Live2DUploadManager:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    def save_directory(self, uploaded_files: list[Live2DUploadFile]) -> Path:
        root_directory_name, files_to_save = self._normalize_upload_files(uploaded_files)
        target_directory = self._prepare_upload_directory(root_directory_name)

        try:
            for relative_path, file_bytes in files_to_save:
                target_file = target_directory.joinpath(*relative_path.parts[1:])
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_bytes(file_bytes)
        except Exception:
            shutil.rmtree(target_directory, ignore_errors=True)
            raise

        return target_directory

    def _normalize_upload_files(
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
            relative_path = self._clean_upload_relative_path(uploaded_file.relative_path)
            if not self._is_supported_upload_path(relative_path):
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
    def _clean_upload_relative_path(relative_path: str) -> PurePosixPath:
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
    def _is_supported_upload_path(relative_path: PurePosixPath) -> bool:
        return relative_path.suffix.lower() in ALLOWED_LIVE2D_UPLOAD_SUFFIXES

    def _prepare_upload_directory(self, directory_name: str) -> Path:
        self._workspace_root.mkdir(parents=True, exist_ok=True)

        cleaned_name = self._clean_upload_directory_name(directory_name)
        candidate = self._workspace_root / cleaned_name
        index = 2
        while candidate.exists():
            candidate = self._workspace_root / f"{cleaned_name}-{index}"
            index += 1

        candidate.mkdir(parents=True, exist_ok=False)
        return candidate

    @staticmethod
    def _clean_upload_directory_name(directory_name: str) -> str:
        raw_name = Path(str(directory_name or "")).name.strip()
        cleaned_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", raw_name).strip(" .")
        return cleaned_name or "live2d-model"
