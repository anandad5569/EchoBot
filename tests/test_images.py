from __future__ import annotations

import base64
import unittest
from io import BytesIO

from PIL import Image

from echobot.images import image_bytes_to_jpeg_data_url, normalize_image_data_url_to_jpeg


def make_png_bytes(*, size: tuple[int, int] = (2, 2)) -> bytes:
    image = Image.new("RGBA", size, (255, 0, 0, 128))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def make_png_data_url() -> str:
    encoded_bytes = base64.b64encode(make_png_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded_bytes}"


class ImageNormalizationTests(unittest.TestCase):
    def test_normalize_image_data_url_to_jpeg_returns_jpeg_data_url(self) -> None:
        jpeg_data_url = normalize_image_data_url_to_jpeg(make_png_data_url())

        self.assertTrue(jpeg_data_url.startswith("data:image/jpeg;base64,"))

        encoded_bytes = jpeg_data_url.split(",", 1)[1]
        jpeg_bytes = base64.b64decode(encoded_bytes)
        with Image.open(BytesIO(jpeg_bytes)) as image:
            self.assertEqual("JPEG", image.format)
            self.assertEqual("RGB", image.mode)
            self.assertEqual((2, 2), image.size)

    def test_image_bytes_to_jpeg_data_url_returns_jpeg_data_url(self) -> None:
        jpeg_data_url = image_bytes_to_jpeg_data_url(make_png_bytes(size=(3, 1)))

        self.assertTrue(jpeg_data_url.startswith("data:image/jpeg;base64,"))

        encoded_bytes = jpeg_data_url.split(",", 1)[1]
        jpeg_bytes = base64.b64decode(encoded_bytes)
        with Image.open(BytesIO(jpeg_bytes)) as image:
            self.assertEqual("JPEG", image.format)
            self.assertEqual((3, 1), image.size)
