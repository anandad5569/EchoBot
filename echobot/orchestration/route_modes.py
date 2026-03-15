from __future__ import annotations

from typing import Literal, cast


DEFAULT_ROUTE_MODE = "auto"
ROUTE_MODE_VALUES = ("auto", "chat_only", "force_agent")
RouteMode = Literal["auto", "chat_only", "force_agent"]


def normalize_route_mode(value: str | None) -> RouteMode:
    cleaned = str(value or "").strip().lower()
    if cleaned in ROUTE_MODE_VALUES:
        return cast(RouteMode, cleaned)
    return DEFAULT_ROUTE_MODE


def route_mode_from_metadata(metadata: dict[str, object] | None) -> RouteMode:
    if not metadata:
        return DEFAULT_ROUTE_MODE
    value = metadata.get("route_mode")
    if not isinstance(value, str):
        return DEFAULT_ROUTE_MODE
    return normalize_route_mode(value)


def set_route_mode(
    metadata: dict[str, object],
    route_mode: str,
) -> dict[str, object]:
    next_metadata = dict(metadata)
    next_metadata["route_mode"] = normalize_route_mode(route_mode)
    return next_metadata
