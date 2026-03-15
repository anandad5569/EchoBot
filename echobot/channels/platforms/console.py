from __future__ import annotations

import asyncio

from ..base import BaseChannel
from ..types import OutboundMessage


class ConsoleChannel(BaseChannel):
    name = "console"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, message: OutboundMessage) -> None:
        text = message.text.strip()
        if not text:
            return
        await asyncio.to_thread(print, f"[console] {text}")
