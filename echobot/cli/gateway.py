from __future__ import annotations

import argparse
import asyncio

from ..app.runtime import AppRuntime
from .common import add_runtime_arguments, resolve_runtime_path, runtime_options_from_args


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    add_runtime_arguments(parser)
    parser.add_argument(
        "--channel-config",
        default=".echobot/channels.json",
        help="Path to the channel config file. Default: .echobot/channels.json",
    )
    parser.set_defaults(handler=run)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the EchoBot multi-platform gateway.",
    )
    return configure_parser(parser)


async def _main_async(args: argparse.Namespace) -> None:
    options = runtime_options_from_args(args)
    channel_config_path = resolve_runtime_path(
        args.channel_config,
        options.workspace,
    )
    runtime = AppRuntime(
        runtime_options=options,
        channel_config_path=channel_config_path,
    )
    await runtime.start()
    try:
        enabled_channels = []
        if runtime.channel_manager is not None:
            enabled_channels = runtime.channel_manager.enabled_channels()

        print("Gateway started.")
        print(f"Channel config: {channel_config_path}")
        print(
            "Enabled channels: "
            + (", ".join(enabled_channels) if enabled_channels else "(none)")
        )
        print()
        if not enabled_channels:
            print("No channels are enabled. Update the channel config and try again.")
            return

        if runtime.gateway_task is not None:
            await runtime.gateway_task
    finally:
        await runtime.stop()


def run(args: argparse.Namespace) -> None:
    asyncio.run(_main_async(args))


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run(args)
