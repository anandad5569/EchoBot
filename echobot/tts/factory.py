from __future__ import annotations

import os
from pathlib import Path

from .providers.edge import EdgeTTSProvider
from .providers.kokoro import DEFAULT_KOKORO_URL, KokoroTTSProvider
from .service import TTSService

DEFAULT_TTS_PROVIDER = "edge"
DEFAULT_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"


def build_default_tts_service(workspace: Path) -> TTSService:
    return TTSService(
        {
            "edge": EdgeTTSProvider(default_voice=DEFAULT_EDGE_VOICE),
            "kokoro": build_default_kokoro_tts_provider(workspace),
        },
        default_provider=DEFAULT_TTS_PROVIDER,
    )


def build_default_kokoro_tts_provider(workspace: Path) -> KokoroTTSProvider:
    return KokoroTTSProvider(
        workspace,
        auto_download=_env_flag("ECHOBOT_TTS_KOKORO_AUTO_DOWNLOAD", True),
        model_root_dir=_resolve_optional_path(
            workspace,
            _env_text("ECHOBOT_TTS_KOKORO_MODEL_DIR", ""),
        ),
        provider=_env_text("ECHOBOT_TTS_KOKORO_PROVIDER", "cpu"),
        num_threads=max(1, _env_int("ECHOBOT_TTS_KOKORO_NUM_THREADS", 2)),
        default_voice=_env_text("ECHOBOT_TTS_KOKORO_DEFAULT_VOICE", "zf_001"),
        model_url=_env_text("ECHOBOT_TTS_KOKORO_URL", DEFAULT_KOKORO_URL),
        download_timeout_seconds=max(
            30.0,
            _env_float("ECHOBOT_TTS_KOKORO_DOWNLOAD_TIMEOUT_SECONDS", 600.0),
        ),
        length_scale=max(0.1, _env_float("ECHOBOT_TTS_KOKORO_LENGTH_SCALE", 1.0)),
        lang=_env_text("ECHOBOT_TTS_KOKORO_LANG", ""),
    )


def _resolve_optional_path(workspace: Path, raw_path: str) -> Path | None:
    normalized_path = raw_path.strip()
    if not normalized_path:
        return None

    candidate = Path(normalized_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return workspace / candidate


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
