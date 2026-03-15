from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import BaseChannel
from .bus import MessageBus
from .config import ChannelsConfig
from .registry import get_channel_registry
from .types import OutboundMessage


logger = logging.getLogger(__name__)


class ChannelManager:
    def __init__(self, config: ChannelsConfig, bus: MessageBus) -> None:
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._channel_tasks: dict[str, asyncio.Task[None]] = {}
        self._dispatch_task: asyncio.Task[None] | None = None
        self._started = False
        self._build_channels()

    async def start_all(self) -> None:
        if self._started:
            return
        self._started = True
        self._dispatch_task = asyncio.create_task(
            self._dispatch_outbound(),
            name="echobot_outbound_dispatcher",
        )
        for name, channel in self.channels.items():
            self._channel_tasks[name] = asyncio.create_task(
                self._run_channel(name, channel),
                name=f"echobot_channel_{name}",
            )

    async def stop_all(self) -> None:
        for channel in self.channels.values():
            try:
                await channel.stop()
            except Exception:
                logger.exception("Failed to stop channel %s", channel.name)

        for task in self._channel_tasks.values():
            task.cancel()
        if self._channel_tasks:
            await asyncio.gather(
                *self._channel_tasks.values(),
                return_exceptions=True,
            )
        self._channel_tasks.clear()

        if self._dispatch_task is not None:
            self._dispatch_task.cancel()
            await asyncio.gather(self._dispatch_task, return_exceptions=True)
            self._dispatch_task = None
        self._started = False

    def enabled_channels(self) -> list[str]:
        return list(self.channels)

    def get_status(self) -> dict[str, dict[str, bool]]:
        return {
            name: {
                "enabled": True,
                "running": channel.is_running,
            }
            for name, channel in self.channels.items()
        }

    def _build_channels(self) -> None:
        registry = get_channel_registry()
        for name in self.config.enabled_channel_names():
            definition = registry.get(name)
            if definition is None:
                logger.warning("Unknown channel config: %s", name)
                continue
            channel_config = self.config.get(name)
            if channel_config is None:
                continue
            self.channels[name] = definition.channel_cls(
                channel_config,
                self.bus,
            )

    async def _run_channel(self, name: str, channel: BaseChannel) -> None:
        try:
            await channel.start()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Channel %s crashed", name)

    async def _dispatch_outbound(self) -> None:
        while True:
            try:
                message = await self.bus.consume_outbound()
            except asyncio.CancelledError:
                break
            await self._send_outbound(message)

    async def _send_outbound(self, message: OutboundMessage) -> None:
        channel = self.channels.get(message.address.channel)
        if channel is None:
            logger.warning("Unknown outbound channel: %s", message.address.channel)
            return
        try:
            await channel.send(message)
        except Exception:
            logger.exception(
                "Failed to send message via channel %s",
                message.address.channel,
            )
