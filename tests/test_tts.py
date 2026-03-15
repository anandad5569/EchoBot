from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from echobot.tts import build_default_kokoro_tts_provider, build_default_tts_service
from echobot.tts.providers.edge import EdgeTTSProvider
from echobot.tts.providers.kokoro import (
    DEFAULT_KOKORO_VOICE,
    KokoroTTSProvider,
    kokoro_voice_options,
    speaker_id_for_voice,
)


class TTSFactoryTests(unittest.TestCase):
    def test_provider_modules_are_grouped_under_providers_package(self) -> None:
        self.assertEqual("echobot.tts.providers.edge", EdgeTTSProvider.__module__)
        self.assertEqual(
            "echobot.tts.providers.kokoro.provider",
            KokoroTTSProvider.__module__,
        )

    def test_build_default_tts_service_registers_edge_and_kokoro(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = build_default_tts_service(Path(temp_dir))

        self.assertEqual("edge", service.default_provider)
        self.assertEqual(["edge", "kokoro"], service.provider_names())
        self.assertEqual("zh-CN-XiaoxiaoNeural", service.default_voice_for("edge"))
        self.assertEqual(DEFAULT_KOKORO_VOICE, service.default_voice_for("kokoro"))

    def test_build_default_kokoro_tts_provider_reads_default_voice_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            with patch.dict(
                os.environ,
                {
                    "ECHOBOT_TTS_KOKORO_AUTO_DOWNLOAD": "false",
                    "ECHOBOT_TTS_KOKORO_DEFAULT_VOICE": "af_maple",
                },
                clear=False,
            ):
                provider = build_default_kokoro_tts_provider(workspace)

        self.assertEqual("af_maple", provider.default_voice)

    def test_build_default_kokoro_tts_provider_falls_back_for_unknown_voice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            with patch.dict(
                os.environ,
                {
                    "ECHOBOT_TTS_KOKORO_AUTO_DOWNLOAD": "false",
                    "ECHOBOT_TTS_KOKORO_DEFAULT_VOICE": "missing-voice",
                },
                clear=False,
            ):
                provider = build_default_kokoro_tts_provider(workspace)

        self.assertEqual(DEFAULT_KOKORO_VOICE, provider.default_voice)


class KokoroVoiceTests(unittest.TestCase):
    def test_speaker_id_for_voice_accepts_name_and_numeric_id(self) -> None:
        self.assertEqual(3, speaker_id_for_voice("zf_001"))
        self.assertEqual(3, speaker_id_for_voice("3"))

    def test_speaker_id_for_voice_rejects_unknown_voice(self) -> None:
        with self.assertRaises(ValueError):
            speaker_id_for_voice("missing-voice")

    def test_kokoro_voice_options_expose_known_voice(self) -> None:
        voices = kokoro_voice_options()
        zf_voice = next(
            voice
            for voice in voices
            if voice.short_name == DEFAULT_KOKORO_VOICE
        )

        self.assertEqual("zh-CN", zf_voice.locale)
        self.assertEqual("Female", zf_voice.gender)
