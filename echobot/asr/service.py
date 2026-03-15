from __future__ import annotations

import asyncio
import io
import os
import sys
import threading
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model_manager import (
    DEFAULT_SENSE_VOICE_URL,
    DEFAULT_VAD_URL,
    SherpaModelManager,
)
from .models import ASRStatusSnapshot, TranscriptionResult


def _env_flag(name: str, default: bool) -> bool:
    raw_value = str(os.environ.get(name, "")).strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "on"}


def _env_text(name: str, default: str) -> str:
    raw_value = str(os.environ.get(name, "")).strip()
    return raw_value or default


def _env_int(name: str, default: int) -> int:
    raw_value = str(os.environ.get(name, "")).strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw_value = str(os.environ.get(name, "")).strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


@dataclass(slots=True)
class _StatusState:
    state: str
    detail: str


class RealtimeASRSession:
    def __init__(self, service: ASRService, detector: Any) -> None:
        self._service = service
        self._detector = detector

    def accept_audio_bytes(self, audio_bytes: bytes) -> list[dict[str, Any]]:
        samples = _pcm16le_bytes_to_floats(audio_bytes)
        if not samples:
            return []

        was_speech_detected = bool(self._detector.is_speech_detected())
        self._detector.accept_waveform(samples)
        is_speech_detected = bool(self._detector.is_speech_detected())

        events: list[dict[str, Any]] = []
        if not was_speech_detected and is_speech_detected:
            events.append({"type": "speech_start"})

        segment_events = self._consume_segments()
        if was_speech_detected and not is_speech_detected and segment_events:
            events.append({"type": "speech_end"})
        events.extend(segment_events)
        return events

    def flush(self) -> list[dict[str, Any]]:
        was_speech_detected = bool(self._detector.is_speech_detected())
        self._detector.flush()

        events: list[dict[str, Any]] = []
        segment_events = self._consume_segments()
        if was_speech_detected and segment_events:
            events.append({"type": "speech_end"})
        events.extend(segment_events)
        return events

    def reset(self) -> None:
        self._detector.reset()

    def _consume_segments(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while not self._detector.empty():
            segment = self._detector.front
            segment_samples = list(segment.samples)
            segment_start_ms = round((float(segment.start) / self._service.sample_rate) * 1000)
            self._detector.pop()

            result = self._service.transcribe_samples_sync(segment_samples)
            if not result.text:
                continue

            events.append(
                {
                    "type": "transcript",
                    "text": result.text,
                    "language": result.language,
                    "final": True,
                    "start_ms": segment_start_ms,
                }
            )
        return events


class ASRService:
    def __init__(
        self,
        workspace: Path,
        *,
        auto_download: bool = True,
        model_root_dir: Path | None = None,
        sample_rate: int = 16000,
        provider: str = "cpu",
        num_threads: int = 2,
        language: str = "auto",
        use_itn: bool = False,
        sense_voice_url: str = DEFAULT_SENSE_VOICE_URL,
        vad_url: str = DEFAULT_VAD_URL,
        download_timeout_seconds: float = 600.0,
    ) -> None:
        self._sample_rate = sample_rate
        self._provider = provider
        self._num_threads = num_threads
        self._language = language
        self._use_itn = use_itn
        self._auto_download = auto_download
        self._model_manager = SherpaModelManager(
            workspace,
            model_root_dir=model_root_dir,
            sense_voice_url=sense_voice_url,
            vad_url=vad_url,
            timeout_seconds=download_timeout_seconds,
        )
        self._status_lock = asyncio.Lock()
        self._runtime_lock = threading.Lock()
        self._recognizer_lock = threading.Lock()
        self._prepare_task: asyncio.Task[None] | None = None
        self._recognizer: Any = None
        self._sherpa_module: Any = None
        self._state = _StatusState(state="missing", detail="")
        self._dependency_error = self._dependency_error_message()
        self._refresh_state_from_disk()

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    async def on_startup(self) -> None:
        self._refresh_state_from_disk()
        await self._maybe_start_prepare()

    async def close(self) -> None:
        task = self._prepare_task
        if task is None or task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def status_snapshot(self) -> ASRStatusSnapshot:
        await self._maybe_start_prepare()
        return ASRStatusSnapshot(
            available=self._state.state == "ready",
            state=self._state.state,
            detail=self._state.detail,
            auto_download=self._auto_download,
            model_directory=str(self._model_manager.paths.root_dir),
            sample_rate=self._sample_rate,
            provider=self._provider,
        )

    async def transcribe_wav_bytes(self, audio_bytes: bytes) -> TranscriptionResult:
        await self._require_runtime_ready()
        samples = await asyncio.to_thread(_read_wav_bytes, audio_bytes, self._sample_rate)
        return await asyncio.to_thread(self.transcribe_samples_sync, samples)

    async def create_realtime_session(self) -> RealtimeASRSession:
        await self._require_runtime_ready()
        return await asyncio.to_thread(self._create_realtime_session_sync)

    def transcribe_samples_sync(self, samples: list[float]) -> TranscriptionResult:
        if not samples:
            return TranscriptionResult(text="")

        self._ensure_runtime_objects_loaded()
        with self._recognizer_lock:
            stream = self._recognizer.create_stream()
            stream.accept_waveform(self._sample_rate, samples)
            self._recognizer.decode_stream(stream)
            result = stream.result

        text = str(getattr(result, "text", "") or "").strip()
        language = str(getattr(result, "lang", "") or "").strip()
        return TranscriptionResult(text=text, language=language)

    def _create_realtime_session_sync(self) -> RealtimeASRSession:
        sherpa_onnx = self._load_sherpa_module()
        detector = sherpa_onnx.VoiceActivityDetector(
            sherpa_onnx.VadModelConfig(
                silero_vad=sherpa_onnx.SileroVadModelConfig(
                    model=str(self._model_manager.paths.vad_model),
                    threshold=0.5,
                    min_silence_duration=0.4,
                    min_speech_duration=0.2,
                    window_size=512,
                    max_speech_duration=30,
                ),
                sample_rate=self._sample_rate,
                num_threads=1,
                provider=self._provider,
                debug=False,
            ),
            60,
        )
        return RealtimeASRSession(self, detector)

    async def _require_runtime_ready(self) -> None:
        await self._maybe_start_prepare()
        if self._state.state != "ready":
            raise RuntimeError(self._state.detail)
        await asyncio.to_thread(self._ensure_runtime_objects_loaded)

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
                self._prepare_models(),
                name="echobot_asr_model_prepare",
            )

    async def _prepare_models(self) -> None:
        self._set_state("downloading", "正在自动下载语音模型，请稍候。")
        try:
            await asyncio.to_thread(self._model_manager.prepare_required_files)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._set_state("error", f"语音模型下载失败: {exc}")
            return

        self._reset_runtime_objects()
        self._refresh_state_from_disk()

    def _refresh_state_from_disk(self) -> None:
        if self._dependency_error is not None:
            self._set_state("unavailable", self._dependency_error)
            return

        missing_files = self._model_manager.missing_files()
        if not missing_files:
            self._set_state("ready", "语音识别已就绪。")
            return

        if self._prepare_task is not None and not self._prepare_task.done():
            self._set_state("downloading", "正在自动下载语音模型，请稍候。")
            return

        relative_paths = ", ".join(
            path.relative_to(self._model_manager.paths.root_dir).as_posix()
            for path in missing_files
        )
        if self._auto_download:
            self._set_state(
                "missing",
                f"语音模型尚未准备好，正在等待下载: {relative_paths}",
            )
        else:
            self._set_state(
                "missing",
                f"缺少语音模型文件: {relative_paths}",
            )

    def _set_state(self, state: str, detail: str) -> None:
        self._state = _StatusState(state=state, detail=detail)

    def _reset_runtime_objects(self) -> None:
        with self._runtime_lock:
            self._recognizer = None
            self._sherpa_module = None

    def _ensure_runtime_objects_loaded(self) -> None:
        with self._runtime_lock:
            if self._recognizer is not None:
                return

            try:
                sherpa_onnx = self._load_sherpa_module()
                paths = self._model_manager.paths
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                    model=str(paths.sense_voice_model),
                    tokens=str(paths.sense_voice_tokens),
                    num_threads=self._num_threads,
                    sample_rate=self._sample_rate,
                    provider=self._provider,
                    language=self._language,
                    use_itn=self._use_itn,
                )
            except Exception as exc:
                self._set_state("error", f"语音识别初始化失败: {exc}")
                raise

    def _load_sherpa_module(self):
        if self._sherpa_module is not None:
            return self._sherpa_module

        try:
            import sherpa_onnx
        except ImportError as exc:  # pragma: no cover - handled by status route
            raise RuntimeError(
                "sherpa-onnx 不可用，请先安装: pip install sherpa-onnx"
            ) from exc

        self._sherpa_module = sherpa_onnx
        return sherpa_onnx

    @staticmethod
    def _dependency_error_message() -> str | None:
        try:
            import sherpa_onnx  # noqa: F401
        except ImportError:
            return "sherpa-onnx 不可用，请先安装: pip install sherpa-onnx"
        return None


def build_default_asr_service(workspace: Path) -> ASRService:
    model_root_override = _env_text("ECHOBOT_ASR_MODEL_DIR", "")
    model_root_dir = None
    if model_root_override:
        candidate = Path(model_root_override).expanduser()
        model_root_dir = candidate if candidate.is_absolute() else workspace / candidate
    return ASRService(
        workspace,
        auto_download=_env_flag("ECHOBOT_ASR_AUTO_DOWNLOAD", True),
        model_root_dir=model_root_dir,
        sample_rate=_env_int("ECHOBOT_ASR_SAMPLE_RATE", 16000),
        provider=_env_text("ECHOBOT_ASR_PROVIDER", "cpu"),
        num_threads=max(1, _env_int("ECHOBOT_ASR_NUM_THREADS", 2)),
        language=_env_text("ECHOBOT_ASR_LANGUAGE", "auto"),
        use_itn=_env_flag("ECHOBOT_ASR_USE_ITN", False),
        sense_voice_url=_env_text("ECHOBOT_ASR_SENSEVOICE_URL", DEFAULT_SENSE_VOICE_URL),
        vad_url=_env_text("ECHOBOT_ASR_VAD_URL", DEFAULT_VAD_URL),
        download_timeout_seconds=max(30.0, _env_float("ECHOBOT_ASR_DOWNLOAD_TIMEOUT_SECONDS", 600.0)),
    )


def _read_wav_bytes(audio_bytes: bytes, target_sample_rate: int) -> list[float]:
    if not audio_bytes:
        raise ValueError("ASR audio body must not be empty")

    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        channel_count = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        if frame_count <= 0:
            return []
        raw_frames = wav_file.readframes(frame_count)

    samples = _decode_pcm_frames(raw_frames, channel_count, sample_width)
    if sample_rate != target_sample_rate:
        samples = _resample_samples(samples, sample_rate, target_sample_rate)
    return samples


def _decode_pcm_frames(raw_frames: bytes, channel_count: int, sample_width: int) -> list[float]:
    if channel_count <= 0:
        raise ValueError("WAV file must have at least one channel")

    if sample_width == 1:
        mono_samples = [(sample - 128) / 128.0 for sample in raw_frames]
    elif sample_width == 2:
        pcm_samples = array("h")
        pcm_samples.frombytes(raw_frames)
        if sys.byteorder != "little":
            pcm_samples.byteswap()
        mono_samples = [sample / 32768.0 for sample in pcm_samples]
    elif sample_width == 4:
        pcm_samples = array("i")
        pcm_samples.frombytes(raw_frames)
        if sys.byteorder != "little":
            pcm_samples.byteswap()
        mono_samples = [sample / 2147483648.0 for sample in pcm_samples]
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    if channel_count == 1:
        return mono_samples

    downmixed: list[float] = []
    for index in range(0, len(mono_samples), channel_count):
        frame = mono_samples[index:index + channel_count]
        if not frame:
            continue
        downmixed.append(sum(frame) / len(frame))
    return downmixed


def _resample_samples(samples: list[float], input_sample_rate: int, output_sample_rate: int) -> list[float]:
    if not samples or input_sample_rate == output_sample_rate:
        return samples
    if len(samples) == 1:
        return samples[:]

    output_length = max(1, round(len(samples) * output_sample_rate / input_sample_rate))
    if output_length == 1:
        return [samples[0]]

    position_scale = (len(samples) - 1) / (output_length - 1)
    resampled: list[float] = []
    for output_index in range(output_length):
        position = output_index * position_scale
        left_index = int(position)
        right_index = min(left_index + 1, len(samples) - 1)
        fraction = position - left_index
        value = (
            samples[left_index] * (1.0 - fraction)
            + samples[right_index] * fraction
        )
        resampled.append(value)
    return resampled


def _pcm16le_bytes_to_floats(audio_bytes: bytes) -> list[float]:
    if not audio_bytes:
        return []

    trimmed_length = len(audio_bytes) - (len(audio_bytes) % 2)
    if trimmed_length <= 0:
        return []

    pcm_samples = array("h")
    pcm_samples.frombytes(audio_bytes[:trimmed_length])
    if sys.byteorder != "little":
        pcm_samples.byteswap()
    return [sample / 32768.0 for sample in pcm_samples]
