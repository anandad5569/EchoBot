from __future__ import annotations

from typing import Any

try:
    from agentscope.agent import ReActAgent
    from agentscope.message import Msg
    from reme.reme_light import ReMeLight
except ImportError:  # pragma: no cover - optional dependency
    ReActAgent = None  # type: ignore[assignment]
    Msg = Any  # type: ignore[assignment]
    ReMeLight = None  # type: ignore[assignment]


__all__ = ["Msg", "ReActAgent", "ReMeLight"]
