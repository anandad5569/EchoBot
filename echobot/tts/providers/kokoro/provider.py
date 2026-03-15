from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from ...base import SynthesizedSpeech, TTSProvider, VoiceOption
from .model_manager import DEFAULT_KOKORO_URL, KokoroModelManager
from .runtime import KokoroRuntime, kokoro_dependency_error_message
from .voices import (
    KOKORO_SPEAKER_NAMES,
    kokoro_voice_options,
    normalize_kokoro_voice_name,
    speaker_id_for_voice,
)


@dataclass(slots=True)
class _StatusState:
    state: str
    detail: str


class KokoroTTSProvider(TTSProvider):
    name = "kokoro"
    label = "Sherpa Kokoro"

    def __init__(
        self,
        workspace: Path,
        *,
        auto_download: bool = True,
        model_root_dir: Path | None = None,
        provider: str = "cpu",
        num_threads: int = 2,
        default_voice: str = "zf_001",
        model_url: str = DEFAULT_KOKORO_URL,
        download_timeout_seconds: float = 600.0,
        length_scale: float = 1.0,
        lang: str = "",
    ) -> None:
        self._default_voice = normalize_kokoro_voice_name(default_voice)
        self._auto_download = auto_download
        self._length_scale = max(0.1, length_scale)
        self._model_manager = KokoroModelManager(
            workspace,
            model_root_dir=model_root_dir,
            model_url=model_url,
            timeout_seconds=download_timeout_seconds,
        )
        self._status_lock = asyncio.Lock()
        self._prepare_task: asyncio.Task[None] | None = None
        self._runtime = KokoroRuntime(
            provider=provider,
            num_threads=max(1, num_threads),
            length_scale=self._length_scale,
            lang=lang,
        )
        self._state = _StatusState(state="missing", detail="")
        self._dependency_error = kokoro_dependency_error_message()
        self._refresh_state_from_disk()

    @property
    def default_voice(self) -> str:
        return self._default_voice

    def availability(self) -> tuple[bool, str]:
        self._refresh_state_from_disk()
        return self._state.state == "ready", self._state.detail

    async def list_voices(self) -> list[VoiceOption]:
        if self._dependency_error is not None:
            raise RuntimeError(self._dependency_error)
        await self._maybe_start_prepare()
        return kokoro_voice_options()

    async def synthesize(
        self,
        *,
        text: str,
        voice: str | None = None,
        rate: str | None = None,
        volume: str | None = None,
        pitch: str | None = None,
    ) -> SynthesizedSpeech:
        del volume, pitch
        await self._require_runtime_ready()

        selected_voice = (voice or self._default_voice).strip()
        speaker_id = speaker_id_for_voice(selected_voice)
        speed = _speed_from_rate(rate)
        audio_bytes = await asyncio.to_thread(
            self._synthesize_sync,
            text,
            speaker_id,
            speed,
        )
        return SynthesizedSpeech(
            audio_bytes=audio_bytes,
            content_type="audio/wav",
            file_extension="wav",
            provider=self.name,
            voice=KOKORO_SPEAKER_NAMES[speaker_id],
        )

    async def close(self) -> None:
        task = self._prepare_task
        if task is None or task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _require_runtime_ready(self) -> None:
        await self._maybe_start_prepare()
        self._refresh_state_from_disk()
        if self._state.state != "ready":
            raise RuntimeError(self._state.detail)
        await asyncio.to_thread(self._ensure_runtime_loaded)

    async def _maybe_start_prepare(self) -> None:
        async with self._status_lock:
            self._refresh_state_from_disk()
            if self._dependency_error is not None:
                return
            if self._state.state == "ready":
                return
            if not self._auto_download:
                return
            if self._prepare_task is not None and not self._prepare_task.done():
                return

            self._prepare_task = asyncio.create_task(
                self._prepare_model(),
                name="echobot_kokoro_tts_model_prepare",
            )

    async def _prepare_model(self) -> None:
        self._set_state("downloading", "姝ｅ湪鑷姩涓嬭浇 Kokoro 璇煶妯″瀷锛岃绋嶅€?")
        try:
            await asyncio.to_thread(self._model_manager.prepare_required_files)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._set_state("error", f"Kokoro 璇煶妯″瀷涓嬭浇澶辫触: {exc}")
            return

        self._reset_runtime_objects()
        self._refresh_state_from_disk()

    def _refresh_state_from_disk(self) -> None:
        if self._dependency_error is not None:
            self._set_state("unavailable", self._dependency_error)
            return

        missing_files = self._model_manager.missing_files()
        if not missing_files:
            self._set_state("ready", "Kokoro 璇煶妯″瀷宸插氨缁?")
            return

        if self._prepare_task is not None and not self._prepare_task.done():
            self._set_state("downloading", "姝ｅ湪鑷姩涓嬭浇 Kokoro 璇煶妯″瀷锛岃绋嶅€?")
            return

        relative_paths = ", ".join(
            _relative_to_root(path, self._model_manager.paths.root_dir)
            for path in missing_files
        )
        if self._auto_download:
            self._set_state(
                "missing",
                f"Kokoro 璇煶妯″瀷灏氭湭鍑嗗濂斤紝棣栨浣跨敤鏃朵細鑷姩涓嬭浇: {relative_paths}",
            )
        else:
            self._set_state(
                "missing",
                f"缂哄皯 Kokoro 璇煶妯″瀷鏂囦欢: {relative_paths}",
            )

    def _set_state(self, state: str, detail: str) -> None:
        self._state = _StatusState(state=state, detail=detail)

    def _reset_runtime_objects(self) -> None:
        self._runtime.reset()

    def _ensure_runtime_loaded(self) -> None:
        try:
            self._runtime.ensure_loaded(
                self._model_manager.paths,
                self._model_manager.lexicon_files(),
            )
        except Exception as exc:
            self._set_state("error", f"Kokoro TTS 初始化失败: {exc}")
            raise

    def _synthesize_sync(self, text: str, speaker_id: int, speed: float) -> bytes:
        self._ensure_runtime_loaded()
        return self._runtime.synthesize(
            text=text,
            speaker_id=speaker_id,
            speed=speed,
        )


def _relative_to_root(path: Path, root_dir: Path) -> str:
    try:
        return path.relative_to(root_dir).as_posix()
    except ValueError:
        return path.name


def _speed_from_rate(rate: str | None) -> float:
    if not rate:
        return 1.0

    normalized_rate = rate.strip()
    if not normalized_rate:
        return 1.0

    if normalized_rate.endswith("%"):
        try:
            percentage = float(normalized_rate[:-1])
        except ValueError:
            return 1.0
        return max(0.1, 1.0 + (percentage / 100.0))

    try:
        return max(0.1, float(normalized_rate))
    except ValueError:
        return 1.0
