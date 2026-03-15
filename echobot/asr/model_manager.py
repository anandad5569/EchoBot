from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from .models import ASRModelPaths


DEFAULT_SENSE_VOICE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09.tar.bz2"
)
DEFAULT_VAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "silero_vad.onnx"
)


@dataclass(slots=True, frozen=True)
class DownloadSettings:
    sense_voice_url: str
    vad_url: str
    timeout_seconds: float


class SherpaModelManager:
    def __init__(
        self,
        workspace: Path,
        *,
        model_root_dir: Path | None = None,
        sense_voice_url: str = DEFAULT_SENSE_VOICE_URL,
        vad_url: str = DEFAULT_VAD_URL,
        timeout_seconds: float = 600.0,
    ) -> None:
        root_dir = model_root_dir or (workspace / ".echobot" / "models" / "sherpa-onnx")
        self._paths = ASRModelPaths(
            root_dir=root_dir,
            sense_voice_dir=root_dir / "sense-voice",
            sense_voice_model=root_dir / "sense-voice" / "model.int8.onnx",
            sense_voice_tokens=root_dir / "sense-voice" / "tokens.txt",
            vad_dir=root_dir / "silero-vad",
            vad_model=root_dir / "silero-vad" / "silero_vad.onnx",
        )
        self._settings = DownloadSettings(
            sense_voice_url=sense_voice_url,
            vad_url=vad_url,
            timeout_seconds=timeout_seconds,
        )

    @property
    def paths(self) -> ASRModelPaths:
        return self._paths

    @property
    def settings(self) -> DownloadSettings:
        return self._settings

    def models_ready(self) -> bool:
        return not self.missing_files()

    def missing_files(self) -> list[Path]:
        required_files = [
            self._paths.sense_voice_model,
            self._paths.sense_voice_tokens,
            self._paths.vad_model,
        ]
        return [path for path in required_files if not path.is_file()]

    def prepare_required_files(self) -> ASRModelPaths:
        if self.models_ready():
            return self._paths

        self._paths.root_dir.mkdir(parents=True, exist_ok=True)
        with self._acquire_download_lock():
            if not self._paths.sense_voice_model.is_file() or not self._paths.sense_voice_tokens.is_file():
                self._install_sense_voice()
            if not self._paths.vad_model.is_file():
                self._install_vad()
        return self._paths

    def _install_sense_voice(self) -> None:
        with tempfile.TemporaryDirectory(prefix="echobot_sense_voice_") as temp_dir:
            temp_root = Path(temp_dir)
            archive_name = self._file_name_from_url(self._settings.sense_voice_url)
            archive_path = temp_root / archive_name
            extract_dir = temp_root / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            self._download_file(self._settings.sense_voice_url, archive_path)
            with tarfile.open(archive_path, "r:bz2") as archive:
                archive.extractall(extract_dir)

            source_dir = self._find_directory_with_files(
                extract_dir,
                required_file_names=["model.int8.onnx", "tokens.txt"],
            )
            temp_install_dir = self._paths.root_dir / "sense-voice.tmp"
            if temp_install_dir.exists():
                shutil.rmtree(temp_install_dir)
            temp_install_dir.mkdir(parents=True, exist_ok=True)

            shutil.copy2(source_dir / "model.int8.onnx", temp_install_dir / "model.int8.onnx")
            shutil.copy2(source_dir / "tokens.txt", temp_install_dir / "tokens.txt")
            self._write_metadata(
                temp_install_dir / "metadata.json",
                name="sense-voice",
                source_url=self._settings.sense_voice_url,
            )
            self._replace_directory(temp_install_dir, self._paths.sense_voice_dir)

    def _install_vad(self) -> None:
        with tempfile.TemporaryDirectory(prefix="echobot_silero_vad_") as temp_dir:
            temp_root = Path(temp_dir)
            temp_install_dir = self._paths.root_dir / "silero-vad.tmp"
            if temp_install_dir.exists():
                shutil.rmtree(temp_install_dir)
            temp_install_dir.mkdir(parents=True, exist_ok=True)

            target_path = temp_install_dir / "silero_vad.onnx"
            self._download_file(self._settings.vad_url, target_path)
            self._write_metadata(
                temp_install_dir / "metadata.json",
                name="silero-vad",
                source_url=self._settings.vad_url,
            )
            self._replace_directory(temp_install_dir, self._paths.vad_dir)

    def _download_file(self, url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(url, timeout=self._settings.timeout_seconds) as response:
            with destination.open("wb") as handle:
                shutil.copyfileobj(response, handle)

    @staticmethod
    def _find_directory_with_files(
        root: Path,
        *,
        required_file_names: list[str],
    ) -> Path:
        for directory in [root, *sorted(path for path in root.rglob("*") if path.is_dir())]:
            if all((directory / file_name).is_file() for file_name in required_file_names):
                return directory
        raise FileNotFoundError(
            f"Unable to locate required files: {', '.join(required_file_names)}"
        )

    @staticmethod
    def _replace_directory(source_dir: Path, target_dir: Path) -> None:
        backup_dir = target_dir.with_name(f"{target_dir.name}.backup")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if target_dir.exists():
            target_dir.replace(backup_dir)
        source_dir.replace(target_dir)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

    @staticmethod
    def _write_metadata(path: Path, *, name: str, source_url: str) -> None:
        payload = {
            "name": name,
            "source_url": source_url,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _file_name_from_url(url: str) -> str:
        parsed = urlparse(url)
        file_name = Path(parsed.path).name
        if not file_name:
            raise ValueError(f"Unable to determine file name from URL: {url}")
        return file_name

    @contextmanager
    def _acquire_download_lock(self):
        lock_path = self._paths.root_dir / ".download.lock"
        deadline = time.monotonic() + self._settings.timeout_seconds
        self._paths.root_dir.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._remove_stale_lock(lock_path):
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError("Timed out while waiting for ASR model download lock")
                time.sleep(0.25)
                continue

            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"pid": os.getpid()}, ensure_ascii=False))
            break

        try:
            yield
        finally:
            lock_path.unlink(missing_ok=True)

    @staticmethod
    def _remove_stale_lock(lock_path: Path) -> bool:
        try:
            modified_at = lock_path.stat().st_mtime
        except FileNotFoundError:
            return False

        if time.time() - modified_at < 3600:
            return False

        try:
            lock_path.unlink()
        except FileNotFoundError:
            return False
        return True
