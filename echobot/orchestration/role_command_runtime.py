from __future__ import annotations

from typing import TYPE_CHECKING

from .commands import RoleCommand, format_role_help, format_role_list

if TYPE_CHECKING:
    from .coordinator import ConversationCoordinator


async def execute_role_command(
    coordinator: ConversationCoordinator,
    session_name: str,
    command: RoleCommand,
) -> str:
    if command.action == "help":
        return format_role_help()

    if command.action == "list":
        current_role = await coordinator.current_role_name(session_name)
        return format_role_list(
            coordinator.available_roles(),
            current_role_name=current_role,
        )

    if command.action == "current":
        current_role = await coordinator.current_role_name(session_name)
        return f"Current role: {current_role}"

    if command.action == "set":
        if not command.argument:
            return "Usage: /role set <name>"
        session = await coordinator.set_session_role(
            session_name,
            command.argument,
        )
        role_name = session.metadata.get("role_name", "default")
        return f"Switched role to: {role_name}"

    return format_role_help()
