from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class VoiceOption:
    name: str
    short_name: str
    locale: str = ""
    gender: str = ""
    display_name: str = ""


@dataclass(slots=True)
class SynthesizedSpeech:
    audio_bytes: bytes
    content_type: str
    file_extension: str
    provider: str
    voice: str


class TTSProvider(ABC):
    name: str
    label: str

    @property
    @abstractmethod
    def default_voice(self) -> str:
        raise NotImplementedError

    def availability(self) -> tuple[bool, str]:
        return True, ""

    async def list_voices(self) -> list[VoiceOption]:
        return []

    async def close(self) -> None:
        return None

    @abstractmethod
    async def synthesize(
        self,
        *,
        text: str,
        voice: str | None = None,
        rate: str | None = None,
        volume: str | None = None,
        pitch: str | None = None,
    ) -> SynthesizedSpeech:
        raise NotImplementedError
