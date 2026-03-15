from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from ..runtime.session_service import SessionService
from ..runtime.sessions import ChatSession, SessionInfo, SessionStore


SESSION_COMMANDS = {"/session", "session"}


@dataclass(slots=True)
class SessionCommandResult:
    session: ChatSession
    lines: list[str]


def load_initial_session(
    session_store: SessionStore,
    args: argparse.Namespace,
) -> ChatSession:
    if args.new_session:
        return session_store.create_session(args.new_session)

    if args.session:
        session = session_store.load_or_create_session(args.session)
        session_store.set_current_session(session.name)
        return session

    return session_store.load_current_session()


def is_session_command(prompt: str) -> bool:
    return prompt.split(maxsplit=1)[0] in SESSION_COMMANDS


async def handle_session_command_async(
    prompt: str,
    *,
    session_service: SessionService,
    current_session: ChatSession,
) -> SessionCommandResult:
    parts = prompt.split()
    if len(parts) == 1 or parts[1] == "help":
        return SessionCommandResult(
            session=current_session,
            lines=_session_help_lines(),
        )

    action = parts[1]

    if action == "list":
        sessions = await session_service.list_sessions()
        return SessionCommandResult(
            session=current_session,
            lines=_format_session_list_lines(
                sessions,
                current_session_name=current_session.name,
            ),
        )

    if action == "current":
        return SessionCommandResult(
            session=current_session,
            lines=[
                (
                    f"Current session: {current_session.name} "
                    f"({len(current_session.history)} messages)"
                )
            ],
        )

    if action == "new":
        name = parts[2] if len(parts) >= 3 else None
        next_session = await session_service.create_session(name)
        return SessionCommandResult(
            session=next_session,
            lines=[f"Switched to new session: {next_session.name}"],
        )

    if action == "switch":
        if len(parts) < 3:
            raise ValueError("Usage: /session switch <name>")

        next_session = await session_service.switch_session(parts[2])
        return SessionCommandResult(
            session=next_session,
            lines=[
                (
                    f"Switched to session: {next_session.name} "
                    f"({len(next_session.history)} messages)"
                )
            ],
        )

    raise ValueError("Unknown session command. Use /session help")


def handle_session_command(
    prompt: str,
    *,
    session_store: SessionStore,
    current_session: ChatSession,
) -> ChatSession:
    result = asyncio.run(
        handle_session_command_async(
            prompt,
            session_service=SessionService(session_store),
            current_session=current_session,
        )
    )
    print_session_command_result(result)
    return result.session


def print_session_help() -> None:
    _print_lines(_session_help_lines())


def print_sessions(
    session_store: SessionStore,
    *,
    current_session_name: str,
) -> None:
    _print_lines(
        _format_session_list_lines(
            session_store.list_sessions(),
            current_session_name=current_session_name,
        )
    )


def print_session_command_result(result: SessionCommandResult) -> None:
    _print_lines(result.lines)


def save_session_state(session_store: SessionStore, session: ChatSession) -> None:
    session_store.save_session(session)
    session_store.set_current_session(session.name)


def clear_history(session_store: SessionStore, session: ChatSession) -> None:
    session.history.clear()
    session.compressed_summary = ""
    save_session_state(session_store, session)


def _session_help_lines() -> list[str]:
    return [
        "Session commands:",
        "- /session list",
        "- /session current",
        "- /session new [name]",
        "- /session switch <name>",
    ]


def _format_session_list_lines(
    sessions: list[SessionInfo],
    *,
    current_session_name: str,
) -> list[str]:
    if not sessions:
        return ["No saved sessions."]

    lines = ["Saved sessions:"]
    for session in sessions:
        marker = "*" if session.name == current_session_name else " "
        lines.append(
            f"{marker} {session.name} | "
            f"{session.message_count} messages | "
            f"{session.updated_at}"
        )
    return lines


def _print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)
