from __future__ import annotations

import asyncio
import logging
from collections import deque
import mimetypes
from typing import TYPE_CHECKING, Any
from urllib import error, request

from ...images import image_bytes_to_jpeg_data_url
from ..base import BaseChannel
from ..types import OutboundMessage

try:
    import botpy
    from botpy.message import C2CMessage

    QQ_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in runtime environments
    botpy = None
    C2CMessage = Any
    QQ_AVAILABLE = False

if TYPE_CHECKING:  # pragma: no cover
    from botpy.message import C2CMessage


logger = logging.getLogger(__name__)


def _make_bot_class(channel: "QQChannel") -> "type[botpy.Client]":
    intents = botpy.Intents(public_messages=True, direct_message=True)

    class _Bot(botpy.Client):
        def __init__(self) -> None:
            super().__init__(intents=intents, ext_handlers=False)

        async def on_ready(self) -> None:
            logger.info("QQ bot is ready")

        async def on_c2c_message_create(self, message: "C2CMessage") -> None:
            await channel._on_message(message)

        async def on_direct_message_create(self, message: Any) -> None:
            await channel._on_message(message)

    return _Bot


class QQChannel(BaseChannel):
    name = "qq"

    def __init__(self, config: Any, bus) -> None:
        super().__init__(config, bus)
        self._client: "botpy.Client | None" = None
        self._processed_ids: deque[str] = deque(maxlen=1000)
        self._message_sequence = 1

    async def start(self) -> None:
        if not QQ_AVAILABLE:
            logger.error(
                "QQ channel requires qq-botpy. Install it before enabling qq.",
            )
            return
        if not self.config.app_id or not self.config.client_secret:
            logger.error("QQ channel requires app_id and client_secret")
            return

        self._running = True
        bot_class = _make_bot_class(self)
        self._client = bot_class()
        logger.info("QQ channel started")
        try:
            while self._running:
                try:
                    await self._client.start(
                        appid=self.config.app_id,
                        secret=self.config.client_secret,
                    )
                except Exception:
                    logger.exception("QQ client stopped unexpectedly")
                if self._running:
                    await asyncio.sleep(5)
        finally:
            await self.stop()

    async def stop(self) -> None:
        self._running = False
        if self._client is None:
            return
        logger.info("Stopping QQ channel")
        try:
            await self._client.close()
        except Exception:
            logger.debug("QQ client close failed", exc_info=True)
        self._client = None

    async def send(self, message: OutboundMessage) -> None:
        if self._client is None:
            logger.warning("QQ channel is not running")
            return
        self._message_sequence += 1
        msg_id = message.metadata.get("message_id")
        await self._client.api.post_c2c_message(
            openid=message.address.chat_id,
            msg_type=0,
            content=message.text,
            msg_id=msg_id,
            msg_seq=self._message_sequence,
        )

    async def _on_message(self, data: "C2CMessage") -> None:
        message_id = str(getattr(data, "id", "")).strip()
        if not message_id:
            return
        if message_id in self._processed_ids:
            return
        self._processed_ids.append(message_id)

        author = getattr(data, "author", None)
        raw_openid = getattr(author, "user_openid", None) or getattr(author, "id", None)
        user_id = str(raw_openid or "").strip()
        content = str(getattr(data, "content", "") or "").strip()
        image_urls = await self._extract_image_urls(data)
        if not user_id or (not content and not image_urls):
            return

        await self._publish_inbound_message(
            sender_id=user_id,
            chat_id=user_id,
            user_id=user_id,
            text=content,
            image_urls=image_urls,
            metadata={"message_id": message_id},
        )

    async def _extract_image_urls(self, data: "C2CMessage") -> list[str]:
        image_urls: list[str] = []
        for attachment in list(getattr(data, "attachments", []) or []):
            content_type = str(getattr(attachment, "content_type", "") or "").strip()
            url = str(getattr(attachment, "url", "") or "").strip()
            filename = str(getattr(attachment, "filename", "") or "").strip()
            if not url:
                continue
            if not _looks_like_image_attachment(content_type, filename, url):
                continue

            image_url = await asyncio.to_thread(
                _download_image_as_data_url,
                url,
                content_type,
                filename or url,
            )
            if image_url:
                image_urls.append(image_url)

        return image_urls


def _looks_like_image_attachment(
    content_type: str,
    filename: str,
    fallback_url: str,
) -> bool:
    if str(content_type or "").strip().lower().startswith("image/"):
        return True

    guessed_type, _encoding = mimetypes.guess_type(filename or fallback_url)
    return bool(guessed_type and guessed_type.startswith("image/"))


def _download_image_as_data_url(
    url: str,
    content_type: str,
    filename: str,
) -> str | None:
    del content_type, filename
    try:
        with request.urlopen(url, timeout=30.0) as response:
            image_bytes = response.read()
    except (error.URLError, ValueError):
        logger.warning("Failed to download QQ image attachment: %s", url, exc_info=True)
        return None

    if not image_bytes:
        return None

    try:
        return image_bytes_to_jpeg_data_url(image_bytes)
    except ValueError:
        logger.warning("Failed to normalize QQ image attachment: %s", url, exc_info=True)
        return None
