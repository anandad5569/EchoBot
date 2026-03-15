from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from ...channels import (
    ChannelsConfig,
    describe_channel_registry,
    load_channels_config,
    save_channels_config,
)


ChannelReloadCallback = Callable[[ChannelsConfig], Awaitable[None]]
ChannelStatusCallback = Callable[[], dict[str, dict[str, bool]]]


class ChannelService:
    def __init__(
        self,
        *,
        config_path: str | Path,
        get_status: ChannelStatusCallback,
        reload_channels: ChannelReloadCallback,
    ) -> None:
        self._config_path = Path(config_path)
        self._get_status = get_status
        self._reload_channels = reload_channels

    async def get_config(self) -> dict[str, Any]:
        config = await asyncio.to_thread(
            load_channels_config,
            self._config_path,
        )
        return config.to_dict()

    async def update_config(self, raw_config: dict[str, Any]) -> dict[str, Any]:
        config = ChannelsConfig.from_dict(raw_config)
        await asyncio.to_thread(
            save_channels_config,
            config,
            self._config_path,
        )
        await self._reload_channels(config)
        return config.to_dict()

    async def get_status(self) -> dict[str, dict[str, bool]]:
        return self._get_status()

    def get_definitions(self) -> list[dict[str, Any]]:
        return describe_channel_registry()
