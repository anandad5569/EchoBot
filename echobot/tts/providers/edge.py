from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from ..base import SynthesizedSpeech, TTSProvider, VoiceOption


class EdgeTTSProvider(TTSProvider):
    name = "edge"
    label = "Edge TTS"

    def __init__(
        self,
        *,
        default_voice: str = "zh-CN-XiaoxiaoNeural",
    ) -> None:
        self._default_voice = default_voice

    @property
    def default_voice(self) -> str:
        return self._default_voice

    def availability(self) -> tuple[bool, str]:
        try:
            self._load_module()
        except RuntimeError as exc:
            return False, str(exc)
        return True, ""

    async def list_voices(self) -> list[VoiceOption]:
        edge_tts = self._load_module()
        raw_voices = await edge_tts.list_voices()
        voices = [
            VoiceOption(
                name=item.get("Name", item.get("ShortName", "")),
                short_name=item.get("ShortName", item.get("Name", "")),
                locale=item.get("Locale", ""),
                gender=item.get("Gender", ""),
                display_name=item.get("FriendlyName", item.get("ShortName", "")),
            )
            for item in raw_voices
        ]
        return sorted(voices, key=lambda item: (item.locale, item.short_name))

    async def synthesize(
        self,
        *,
        text: str,
        voice: str | None = None,
        rate: str | None = None,
        volume: str | None = None,
        pitch: str | None = None,
    ) -> SynthesizedSpeech:
        edge_tts = self._load_module()
        selected_voice = voice or self._default_voice

        kwargs = {
            "text": text,
            "voice": selected_voice,
        }
        if rate:
            kwargs["rate"] = rate
        if volume:
            kwargs["volume"] = volume
        if pitch:
            kwargs["pitch"] = pitch

        with tempfile.TemporaryDirectory(prefix="echobot_tts_") as temp_dir:
            output_path = Path(temp_dir) / "speech.mp3"
            communicator = edge_tts.Communicate(**kwargs)
            await communicator.save(str(output_path))
            audio_bytes = await asyncio.to_thread(output_path.read_bytes)

        return SynthesizedSpeech(
            audio_bytes=audio_bytes,
            content_type="audio/mpeg",
            file_extension="mp3",
            provider=self.name,
            voice=selected_voice,
        )

    @staticmethod
    def _load_module():
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "Edge TTS is unavailable. Install it with: pip install edge-tts",
            ) from exc
        return edge_tts
