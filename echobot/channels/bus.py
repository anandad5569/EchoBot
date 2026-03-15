from __future__ import annotations

import asyncio

from .types import InboundMessage, OutboundMessage


class MessageBus:
    def __init__(self) -> None:
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, message: InboundMessage) -> None:
        await self._inbound.put(message)

    async def consume_inbound(self) -> InboundMessage:
        return await self._inbound.get()

    async def publish_outbound(self, message: OutboundMessage) -> None:
        await self._outbound.put(message)

    async def consume_outbound(self) -> OutboundMessage:
        return await self._outbound.get()

    @property
    def inbound_size(self) -> int:
        return self._inbound.qsize()

    @property
    def outbound_size(self) -> int:
        return self._outbound.qsize()
