from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import LLMMessage

if TYPE_CHECKING:
    from ..providers.openai_compatible import OpenAICompatibleSettings


DEFAULT_MAX_INPUT_LENGTH = 128 * 1024
DEFAULT_REME_WORKING_DIR = Path(".echobot") / "reme"
DEFAULT_REME_CONSOLE_OUTPUT = False


@dataclass(slots=True)
class MemoryPreparationResult:
    messages: list[LLMMessage]
    compressed_summary: str


@dataclass(slots=True)
class ReMeLightSettings:
    working_dir: Path
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    language: str = "zh"
    console_output_enabled: bool = DEFAULT_REME_CONSOLE_OUTPUT
    max_input_length: int = DEFAULT_MAX_INPUT_LENGTH
    compact_ratio: float = 0.7
    memory_compact_reserve: int = 10_000
    tool_result_compact_keep_n: int = 3
    tool_result_threshold: int = 1000
    retention_days: int = 7
    fts_enabled: bool = True
    vector_enabled: bool = False
    vector_weight: float = 0.7
    candidate_multiplier: float = 3.0

    @classmethod
    def from_provider_settings(
        cls,
        workspace: str | Path,
        provider_settings: "OpenAICompatibleSettings",
    ) -> "ReMeLightSettings":
        workspace_path = Path(workspace).resolve()
        env = os.environ
        working_dir = _resolve_optional_path(
            env.get("REME_WORKING_DIR"),
            base_dir=workspace_path,
            default=default_reme_working_dir(workspace_path),
        )

        return cls(
            working_dir=working_dir,
            llm_api_key=provider_settings.api_key,
            llm_base_url=provider_settings.base_url,
            llm_model=provider_settings.model,
            language=(env.get("REME_LANGUAGE") or "zh").strip() or "zh",
            console_output_enabled=_read_bool_env(
                env,
                "REME_CONSOLE_OUTPUT",
                default=DEFAULT_REME_CONSOLE_OUTPUT,
            ),
            max_input_length=_read_int_env(
                env,
                "REME_MAX_INPUT_LENGTH",
                default=DEFAULT_MAX_INPUT_LENGTH,
                minimum=1024,
            ),
            compact_ratio=_read_float_env(
                env,
                "REME_COMPACT_RATIO",
                default=0.7,
                minimum=0.1,
                maximum=0.95,
            ),
            memory_compact_reserve=_read_int_env(
                env,
                "REME_MEMORY_COMPACT_RESERVE",
                default=10_000,
                minimum=0,
            ),
            tool_result_compact_keep_n=_read_int_env(
                env,
                "REME_TOOL_RESULT_KEEP_N",
                default=3,
                minimum=0,
            ),
            tool_result_threshold=_read_int_env(
                env,
                "REME_TOOL_RESULT_THRESHOLD",
                default=1000,
                minimum=32,
            ),
            retention_days=_read_int_env(
                env,
                "REME_RETENTION_DAYS",
                default=7,
                minimum=1,
            ),
            fts_enabled=_read_bool_env(env, "REME_FTS_ENABLED", default=True),
            vector_enabled=_read_bool_env(env, "REME_VECTOR_ENABLED", default=False),
            vector_weight=_read_float_env(
                env,
                "REME_VECTOR_WEIGHT",
                default=0.7,
                minimum=0.0,
                maximum=1.0,
            ),
            candidate_multiplier=_read_float_env(
                env,
                "REME_CANDIDATE_MULTIPLIER",
                default=3.0,
                minimum=1.0,
                maximum=10.0,
            ),
        )


def default_reme_working_dir(workspace: str | Path) -> Path:
    workspace_path = Path(workspace).resolve()
    return workspace_path / DEFAULT_REME_WORKING_DIR


def _resolve_optional_path(
    value: str | None,
    *,
    base_dir: Path,
    default: Path,
) -> Path:
    if value is None or not value.strip():
        return default

    path = Path(value.strip())
    if not path.is_absolute():
        path = base_dir / path

    return path.resolve()


def _read_bool_env(source: dict[str, str], name: str, *, default: bool) -> bool:
    value = source.get(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int_env(
    source: dict[str, str],
    name: str,
    *,
    default: int,
    minimum: int,
) -> int:
    value = source.get(name)
    if value is None or not value.strip():
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    return max(parsed, minimum)


def _read_float_env(
    source: dict[str, str],
    name: str,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    value = source.get(name)
    if value is None or not value.strip():
        return default

    try:
        parsed = float(value)
    except ValueError:
        return default

    return min(max(parsed, minimum), maximum)
