from __future__ import annotations

from typing import Any

from .imports import ReActAgent
from .settings import DEFAULT_REME_CONSOLE_OUTPUT


_reme_internal_console_output_enabled = DEFAULT_REME_CONSOLE_OUTPUT


def _configure_reme_internal_console_output(
    enabled: bool,
    react_agent_cls: type[Any] | None = None,
) -> None:
    global _reme_internal_console_output_enabled

    _reme_internal_console_output_enabled = enabled
    target_cls = react_agent_cls or ReActAgent
    if target_cls is None:
        return

    _install_reme_console_output_patch(target_cls)


def _install_reme_console_output_patch(react_agent_cls: type[Any]) -> None:
    if getattr(react_agent_cls, "_echobot_reme_console_patch_applied", False):
        return

    original_init = react_agent_cls.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        _apply_reme_console_output_setting(self)

    react_agent_cls.__init__ = patched_init  # type: ignore[method-assign]
    react_agent_cls._echobot_reme_console_patch_applied = True  # type: ignore[attr-defined]


def _apply_reme_console_output_setting(agent: Any) -> None:
    agent_name = getattr(agent, "name", "")
    if not isinstance(agent_name, str) or not agent_name.startswith("reme_"):
        return

    set_console_output_enabled = getattr(agent, "set_console_output_enabled", None)
    if callable(set_console_output_enabled):
        set_console_output_enabled(_reme_internal_console_output_enabled)
