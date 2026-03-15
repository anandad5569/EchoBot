from __future__ import annotations

import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from echobot.channels.platforms.qq import _download_image_as_data_url
from echobot.channels.platforms.telegram import TelegramChannel


def make_png_bytes() -> bytes:
    image = Image.new("RGBA", (2, 2), (0, 128, 255, 128))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class _FakeUrlResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeUrlResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class ChannelImageNormalizationTests(unittest.IsolatedAsyncioTestCase):
    def test_qq_image_download_is_normalized_to_jpeg(self) -> None:
        with patch(
            "echobot.channels.platforms.qq.request.urlopen",
            return_value=_FakeUrlResponse(make_png_bytes()),
        ):
            image_data_url = _download_image_as_data_url(
                "https://example.com/cat.png",
                "image/png",
                "cat.png",
            )

        self.assertIsNotNone(image_data_url)
        self.assertTrue(str(image_data_url).startswith("data:image/jpeg;base64,"))

    async def test_telegram_image_download_is_normalized_to_jpeg(self) -> None:
        class FakeTelegramFile:
            async def download_as_bytearray(self) -> bytearray:
                return bytearray(make_png_bytes())

        class FakeAttachment:
            async def get_file(self) -> FakeTelegramFile:
                return FakeTelegramFile()

        channel = TelegramChannel(config=SimpleNamespace(), bus=None)
        image_data_url = await channel._download_telegram_image(
            FakeAttachment(),
            content_type="image/png",
            filename="cat.png",
        )

        self.assertIsNotNone(image_data_url)
        self.assertTrue(str(image_data_url).startswith("data:image/jpeg;base64,"))
