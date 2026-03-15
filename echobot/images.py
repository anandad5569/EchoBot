from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


JPEG_CONTENT_TYPE = "image/jpeg"


def normalize_image_data_urls_to_jpeg(data_urls: Sequence[str] | None) -> list[str]:
    return [
        normalize_image_data_url_to_jpeg(data_url)
        for data_url in data_urls or []
        if str(data_url).strip()
    ]


def normalize_image_data_url_to_jpeg(data_url: str) -> str:
    _content_type, image_bytes = decode_image_data_url(data_url)
    return image_bytes_to_jpeg_data_url(image_bytes)


def image_bytes_to_jpeg_data_url(image_bytes: bytes) -> str:
    jpeg_bytes = convert_image_bytes_to_jpeg(image_bytes)
    encoded_bytes = base64.b64encode(jpeg_bytes).decode("ascii")
    return f"data:{JPEG_CONTENT_TYPE};base64,{encoded_bytes}"


def decode_image_data_url(data_url: str) -> tuple[str, bytes]:
    cleaned_data_url = str(data_url or "").strip()
    if not cleaned_data_url:
        raise ValueError("Chat image data URL must not be empty")
    if not cleaned_data_url.startswith("data:"):
        raise ValueError("Chat image must use a data URL")

    header, separator, encoded_bytes = cleaned_data_url.partition(",")
    if separator != ",":
        raise ValueError("Chat image data URL is missing encoded content")

    mime_section = header[5:]
    content_type, marker, _parameters = mime_section.partition(";")
    cleaned_content_type = content_type.strip().lower()
    if not cleaned_content_type.startswith("image/"):
        raise ValueError("Chat image data URL must use an image content type")
    if marker != ";" or "base64" not in _parameters.casefold():
        raise ValueError("Chat image data URL must use base64 encoding")

    try:
        image_bytes = base64.b64decode(encoded_bytes, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Chat image data URL contains invalid base64 data") from exc

    if not image_bytes:
        raise ValueError("Chat image must not be empty")

    return cleaned_content_type, image_bytes


def convert_image_bytes_to_jpeg(image_bytes: bytes) -> bytes:
    if not image_bytes:
        raise ValueError("Chat image must not be empty")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            normalized_image = ImageOps.exif_transpose(image)
            rgb_image = _convert_image_to_rgb(normalized_image)
            output_buffer = BytesIO()
            rgb_image.save(output_buffer, format="JPEG", quality=90)
            return output_buffer.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Unsupported chat image format") from exc


def _convert_image_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"}:
        return _flatten_alpha_image(image.convert("RGBA"))

    if image.mode == "P" and "transparency" in image.info:
        return _flatten_alpha_image(image.convert("RGBA"))

    return image.convert("RGB")


def _flatten_alpha_image(image: Image.Image) -> Image.Image:
    background = Image.new("RGB", image.size, (255, 255, 255))
    background.paste(image, mask=image.getchannel("A"))
    return background
