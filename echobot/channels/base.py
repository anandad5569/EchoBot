from __future__ import annotations

import base64
import logging
import mimetypes
from abc import ABC, abstractmethod
from typing import Any

from .bus import MessageBus
from .types import ChannelAddress, InboundMessage, OutboundMessage


logger = logging.getLogger(__name__)


class BaseChannel(ABC):
    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus) -> None:
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send(self, message: OutboundMessage) -> None:
        raise NotImplementedError

    @property
    def is_running(self) -> bool:
        return self._running

    def is_allowed(self, sender_id: str) -> bool:
        allow_list = list(getattr(self.config, "allow_from", []) or [])
        if not allow_list or "*" in allow_list:
            return True
        sender_text = str(sender_id)
        return sender_text in allow_list or any(
            part in allow_list
            for part in sender_text.split("|")
            if part
        )

    async def _publish_inbound_message(
        self,
        *,
        sender_id: str,
        chat_id: str,
        text: str,
        image_urls: list[str] | None = None,
        thread_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_allowed(sender_id):
            logger.warning(
                "Ignoring message from %s on channel %s: not allowed",
                sender_id,
                self.name,
            )
            return
        cleaned_text = text.strip()
        cleaned_image_urls = [
            str(url).strip()
            for url in image_urls or []
            if str(url).strip()
        ]
        if not cleaned_text and not cleaned_image_urls:
            return
        address = ChannelAddress(
            channel=self.name,
            chat_id=str(chat_id),
            thread_id=thread_id,
            user_id=user_id,
        )
        await self.bus.publish_inbound(
            InboundMessage(
                address=address,
                sender_id=str(sender_id),
                text=cleaned_text,
                image_urls=cleaned_image_urls,
                metadata=dict(metadata or {}),
            )
        )

    async def _publish_inbound_text(
        self,
        *,
        sender_id: str,
        chat_id: str,
        text: str,
        thread_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._publish_inbound_message(
            sender_id=sender_id,
            chat_id=chat_id,
            text=text,
            thread_id=thread_id,
            user_id=user_id,
            metadata=metadata,
        )


def build_image_data_url(
    image_bytes: bytes,
    *,
    content_type: str | None = None,
    filename: str | None = None,
) -> str:
    resolved_content_type = guess_image_content_type(
        content_type=content_type,
        filename=filename,
    )
    encoded_bytes = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{resolved_content_type};base64,{encoded_bytes}"


def guess_image_content_type(
    *,
    content_type: str | None = None,
    filename: str | None = None,
) -> str:
    cleaned_content_type = str(content_type or "").strip().lower()
    if cleaned_content_type.startswith("image/"):
        return cleaned_content_type

    guessed_type, _encoding = mimetypes.guess_type(str(filename or ""))
    if guessed_type and guessed_type.startswith("image/"):
        return guessed_type

    return "image/jpeg"
