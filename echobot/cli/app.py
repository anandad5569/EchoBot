from __future__ import annotations

import argparse

from .common import add_runtime_arguments, resolve_runtime_path, runtime_options_from_args


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    add_runtime_arguments(parser)
    parser.add_argument(
        "--channel-config",
        default=".echobot/channels.json",
        help="Path to the channel config file. Default: .echobot/channels.json",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for the API server. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port for the API server. Default: 8000",
    )
    parser.set_defaults(handler=run)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the EchoBot API daemon.",
    )
    return configure_parser(parser)


def build_application(args: argparse.Namespace):
    from ..app import create_app

    options = runtime_options_from_args(args)
    channel_config_path = resolve_runtime_path(
        args.channel_config,
        options.workspace,
    )
    return create_app(
        runtime_options=options,
        channel_config_path=channel_config_path,
    )


def run(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise SystemExit(
            "App server requires uvicorn. Install it with: pip install uvicorn",
        ) from exc

    uvicorn.run(
        build_application(args),
        host=args.host,
        port=args.port,
    )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run(args)
