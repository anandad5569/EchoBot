from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RoleCommand:
    action: str
    argument: str = ""


def parse_role_command(text: str) -> RoleCommand | None:
    cleaned = text.strip()
    if not cleaned.startswith("/role"):
        return None

    parts = cleaned.split(maxsplit=2)
    command_token = parts[0].split("@", 1)[0]
    if command_token != "/role":
        return None
    if len(parts) == 1:
        return RoleCommand(action="current")
    action = parts[1].strip().lower()
    argument = parts[2].strip() if len(parts) >= 3 else ""
    if action in {"help", "list", "current", "set"}:
        return RoleCommand(action=action, argument=argument)
    return RoleCommand(action="help")


def format_role_help() -> str:
    return "\n".join(
        [
            "Role commands:",
            "/role current - Show the current role card",
            "/role list - List available role cards",
            "/role set <name> - Switch to a role card",
        ]
    )


def format_role_list(role_names: list[str], *, current_role_name: str) -> str:
    if not role_names:
        return "No role cards are available."

    lines = ["Available roles:"]
    for name in role_names:
        marker = "*" if name == current_role_name else " "
        lines.append(f"{marker} {name}")
    return "\n".join(lines)
