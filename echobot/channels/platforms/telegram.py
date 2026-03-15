from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ...images import image_bytes_to_jpeg_data_url
from ..base import BaseChannel
from ..types import OutboundMessage

try:
    from telegram import BotCommand, Update
    from telegram.error import Conflict, TelegramError
    from telegram.ext import Application, ContextTypes, MessageHandler, filters
    from telegram.request import HTTPXRequest

    TELEGRAM_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in runtime environments
    BotCommand = Any
    Conflict = Any
    TelegramError = Any
    Application = Any
    ContextTypes = Any
    HTTPXRequest = Any
    MessageHandler = Any
    Update = Any
    filters = None
    TELEGRAM_AVAILABLE = False

if TYPE_CHECKING:  # pragma: no cover
    from telegram.ext import Application as TelegramApplication


logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 4000
_BOT_COMMANDS = [
    BotCommand("new", "Start a new session"),
    BotCommand("ls", "List sessions"),
    BotCommand("switch", "Switch to another session"),
    BotCommand("rename", "Rename the current session"),
    BotCommand("delete", "Delete the current session"),
    BotCommand("current", "Show current session"),
    BotCommand("help", "Show session commands"),
]


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, config: Any, bus) -> None:
        super().__init__(config, bus)
        self._app: "TelegramApplication | None" = None

    async def start(self) -> None:
        if not TELEGRAM_AVAILABLE:
            logger.error(
                "Telegram channel requires python-telegram-bot. "
                "Install it before enabling telegram.",
            )
            return
        if not self.config.bot_token:
            logger.error("Telegram channel is missing bot_token")
            return

        self._running = True
        request = HTTPXRequest(
            connection_pool_size=16,
            pool_timeout=5.0,
            connect_timeout=30.0,
            read_timeout=30.0,
        )
        builder = (
            Application.builder()
            .token(self.config.bot_token)
            .request(request)
            .get_updates_request(request)
        )
        if self.config.proxy:
            builder = builder.proxy(self.config.proxy).get_updates_proxy(
                self.config.proxy,
            )
        self._app = builder.build()
        self._app.add_error_handler(self._on_error)
        self._app.add_handler(
            MessageHandler(
                filters.ALL,
                self._on_message,
            ),
        )
        await self._app.initialize()
        await self._app.start()
        try:
            await self._app.bot.set_my_commands(_BOT_COMMANDS)
        except Exception:
            logger.debug("Telegram command registration failed", exc_info=True)
        await self._app.updater.start_polling(
            allowed_updates=["message"],
            drop_pending_updates=True,
            error_callback=self._on_polling_error,
        )
        logger.info("Telegram channel started")
        try:
            while self._running:
                await asyncio.sleep(1)
        finally:
            await self.stop()

    async def stop(self) -> None:
        self._running = False
        if self._app is None:
            return
        logger.info("Stopping Telegram channel")
        updater = getattr(self._app, "updater", None)
        try:
            if updater is not None:
                await updater.stop()
        except Exception:
            logger.debug("Telegram updater stop failed", exc_info=True)
        try:
            await self._app.stop()
        except Exception:
            logger.debug("Telegram app stop failed", exc_info=True)
        try:
            await self._app.shutdown()
        except Exception:
            logger.debug("Telegram app shutdown failed", exc_info=True)
        self._app = None

    async def send(self, message: OutboundMessage) -> None:
        if self._app is None:
            logger.warning("Telegram channel is not running")
            return
        chat_id = _as_chat_id(message.address.chat_id)
        reply_to_message_id = None
        if self.config.reply_to_message and not message.metadata.get("scheduled"):
            raw_message_id = message.metadata.get("message_id")
            if raw_message_id is not None:
                try:
                    reply_to_message_id = int(raw_message_id)
                except (TypeError, ValueError):
                    reply_to_message_id = None
        for chunk in _split_text(message.text):
            kwargs: dict[str, Any] = {}
            if reply_to_message_id is not None:
                kwargs["reply_to_message_id"] = reply_to_message_id
            await self._app.bot.send_message(
                chat_id=chat_id,
                text=chunk,
                **kwargs,
            )

    async def _on_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        del context
        if not update.message or not update.effective_user:
            return
        user = update.effective_user
        if getattr(user, "is_bot", False):
            return
        text = (update.message.text or update.message.caption or "").strip()
        image_urls = await self._extract_image_urls(update.message)
        if not text and not image_urls:
            return
        sender_id = _sender_id(user)
        await self._publish_inbound_message(
            sender_id=sender_id,
            chat_id=str(update.message.chat_id),
            user_id=str(user.id),
            text=text,
            image_urls=image_urls,
            metadata={
                "message_id": update.message.message_id,
                "username": user.username,
                "first_name": user.first_name,
                "is_group": update.message.chat.type != "private",
            },
        )

    async def _on_error(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        del update
        logger.error("Telegram error: %s", context.error)

    def _on_polling_error(self, error: TelegramError) -> None:
        if isinstance(error, Conflict):
            logger.error(
                "Telegram polling conflict: another bot instance is already "
                "using getUpdates for this token. Stop the other instance or "
                "run only one gateway process.",
            )
            if self._running:
                asyncio.get_running_loop().create_task(self.stop())
            return
        logger.error(
            "Telegram polling error: %s",
            error,
            exc_info=(type(error), error, error.__traceback__),
        )

    async def _extract_image_urls(self, message: Any) -> list[str]:
        image_urls: list[str] = []

        photo_sizes = list(getattr(message, "photo", []) or [])
        if photo_sizes:
            image_url = await self._download_telegram_image(
                photo_sizes[-1],
                content_type="image/jpeg",
                filename="telegram-photo.jpg",
            )
            if image_url:
                image_urls.append(image_url)

        document = getattr(message, "document", None)
        document_content_type = str(getattr(document, "mime_type", "") or "").strip()
        if document is not None and document_content_type.startswith("image/"):
            image_url = await self._download_telegram_image(
                document,
                content_type=document_content_type,
                filename=getattr(document, "file_name", None),
            )
            if image_url:
                image_urls.append(image_url)

        return image_urls

    async def _download_telegram_image(
        self,
        attachment: Any,
        *,
        content_type: str | None,
        filename: str | None,
    ) -> str | None:
        del content_type, filename
        try:
            telegram_file = await attachment.get_file()
            image_bytes = bytes(await telegram_file.download_as_bytearray())
        except Exception:
            logger.warning("Failed to download Telegram image attachment", exc_info=True)
            return None

        if not image_bytes:
            return None

        try:
            return image_bytes_to_jpeg_data_url(image_bytes)
        except ValueError:
            logger.warning("Failed to normalize Telegram image attachment", exc_info=True)
            return None


def _split_text(text: str) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= _MAX_MESSAGE_LENGTH:
        return [cleaned]

    chunks: list[str] = []
    remaining = cleaned
    while remaining:
        if len(remaining) <= _MAX_MESSAGE_LENGTH:
            chunks.append(remaining)
            break
        boundary = remaining.rfind("\n", 0, _MAX_MESSAGE_LENGTH)
        if boundary < _MAX_MESSAGE_LENGTH // 2:
            boundary = remaining.rfind(" ", 0, _MAX_MESSAGE_LENGTH)
        if boundary < _MAX_MESSAGE_LENGTH // 2:
            boundary = _MAX_MESSAGE_LENGTH
        chunks.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    return [chunk for chunk in chunks if chunk]


def _sender_id(user: Any) -> str:
    sender_id = str(getattr(user, "id", "")).strip() or "unknown"
    username = str(getattr(user, "username", "") or "").strip()
    if username:
        return f"{sender_id}|{username}"
    return sender_id


def _as_chat_id(raw_value: str) -> int | str:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return raw_value
