from __future__ import annotations

import sys
import logging
import os
from pathlib import Path
from typing import Mapping


VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def load_env_file(path: str | Path = ".env", *, override: bool = False) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for line_number, raw_line in enumerate(
        env_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError(f"Invalid env line {line_number} in {env_path}")

        key = key.strip()
        value = value.strip()

        if not key:
            raise ValueError(f"Missing env key on line {line_number} in {env_path}")

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        if override or key not in os.environ:
            os.environ[key] = value


def configure_runtime_logging(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env

    reme_level = _read_log_level(source, "REME_LOG_LEVEL")
    if reme_level is not None:
        _set_logger_level("reme", reme_level)
        _configure_loguru_reme_logging(reme_level)

    agentscope_level = _read_log_level(source, "AGENTSCOPE_LOG_LEVEL")
    if agentscope_level is not None:
        _set_logger_level("as", agentscope_level)


def _read_log_level(source: Mapping[str, str], name: str) -> str | None:
    value = source.get(name)
    if value is None:
        return None

    level = value.strip().upper()
    if not level:
        return None

    if level not in VALID_LOG_LEVELS:
        valid_levels = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ValueError(f"{name} must be one of: {valid_levels}")

    return level


def _set_logger_level(name: str, level: str) -> None:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


def _configure_loguru_reme_logging(level: str, *, sink: object | None = None) -> None:
    try:
        from loguru import logger
    except ImportError:
        return

    target_sink = sys.stderr if sink is None else sink

    logger.remove()
    logger.add(
        target_sink,
        level="INFO",
        filter=_is_not_reme_loguru_record,
    )
    logger.add(
        target_sink,
        level=level,
        filter=_is_reme_loguru_record,
    )


def _is_reme_loguru_record(record: dict[str, object]) -> bool:
    name = record.get("name", "")
    return isinstance(name, str) and name.startswith("reme")


def _is_not_reme_loguru_record(record: dict[str, object]) -> bool:
    return not _is_reme_loguru_record(record)
