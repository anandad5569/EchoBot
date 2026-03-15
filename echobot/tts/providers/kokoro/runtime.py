from __future__ import annotations

import io
import sys
import threading
import wave
from array import array
from pathlib import Path
from typing import Any

from .model_manager import KokoroModelPaths


class KokoroRuntime:
    def __init__(
        self,
        *,
        provider: str,
        num_threads: int,
        length_scale: float,
        lang: str,
    ) -> None:
        self._provider = provider
        self._num_threads = num_threads
        self._length_scale = length_scale
        self._lang = lang
        self._runtime_lock = threading.Lock()
        self._tts: Any = None
        self._sherpa_module: Any = None

    def reset(self) -> None:
        with self._runtime_lock:
            self._tts = None
            self._sherpa_module = None

    def ensure_loaded(
        self,
        paths: KokoroModelPaths,
        lexicon_files: tuple[Path, ...],
    ) -> None:
        with self._runtime_lock:
            if self._tts is not None:
                return

            sherpa_onnx = self._load_sherpa_module()
            kokoro_config = sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=str(paths.model_file),
                voices=str(paths.voices_file),
                tokens=str(paths.tokens_file),
                lexicon=",".join(str(path) for path in lexicon_files),
                data_dir=str(paths.data_dir),
                dict_dir=str(paths.dict_dir) if paths.dict_dir.is_dir() else "",
                length_scale=self._length_scale,
                lang=self._lang,
            )
            model_config = sherpa_onnx.OfflineTtsModelConfig(
                kokoro=kokoro_config,
                num_threads=self._num_threads,
                provider=self._provider,
            )
            config = sherpa_onnx.OfflineTtsConfig(model=model_config)
            if not config.validate():
                raise RuntimeError("Kokoro TTS configuration is invalid")
            self._tts = sherpa_onnx.OfflineTts(config)

    def synthesize(
        self,
        *,
        text: str,
        speaker_id: int,
        speed: float,
    ) -> bytes:
        if self._tts is None:
            raise RuntimeError("Kokoro TTS runtime is not loaded")

        generated_audio = self._tts.generate(text, speaker_id, speed)
        samples = getattr(generated_audio, "samples", None)
        if samples is None:
            raise RuntimeError("sherpa-onnx did not return any audio samples")

        sample_rate = int(
            getattr(generated_audio, "sample_rate", 0) or self._tts.sample_rate
        )
        return _wav_bytes_from_samples(samples, sample_rate)

    def _load_sherpa_module(self):
        if self._sherpa_module is not None:
            return self._sherpa_module

        try:
            import sherpa_onnx
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise RuntimeError(
                "sherpa-onnx is unavailable. Install it with: pip install sherpa-onnx"
            ) from exc

        self._sherpa_module = sherpa_onnx
        return sherpa_onnx


def kokoro_dependency_error_message() -> str | None:
    try:
        import sherpa_onnx  # noqa: F401
    except ImportError:
        return "sherpa-onnx is unavailable. Install it with: pip install sherpa-onnx"
    return None


def _wav_bytes_from_samples(samples: Any, sample_rate: int) -> bytes:
    pcm_samples = array("h")
    for sample in samples:
        value = max(-1.0, min(1.0, float(sample)))
        scaled = int(value * 32767.0) if value >= 0 else int(value * 32768.0)
        pcm_samples.append(max(-32768, min(32767, scaled)))

    if sys.byteorder != "little":
        pcm_samples.byteswap()

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_samples.tobytes())
    return buffer.getvalue()
