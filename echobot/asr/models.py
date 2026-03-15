from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class ASRModelPaths:
    root_dir: Path
    sense_voice_dir: Path
    sense_voice_model: Path
    sense_voice_tokens: Path
    vad_dir: Path
    vad_model: Path


@dataclass(slots=True, frozen=True)
class ASRStatusSnapshot:
    available: bool
    state: str
    detail: str
    auto_download: bool
    model_directory: str
    sample_rate: int
    provider: str
    always_listen_supported: bool = True


@dataclass(slots=True, frozen=True)
class TranscriptionResult:
    text: str
    language: str = ""
