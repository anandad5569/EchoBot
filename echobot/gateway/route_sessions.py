from __future__ import annotations

import copy
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


DEFAULT_ROUTE_SESSION_STORE_PATH = Path(".echobot/route_sessions.json")
_LEGACY_ROUTE_SESSION_STORE_NAME = "conversations.json"
_ROUTE_SESSION_DELIMITER = "__session__"
_LEGACY_ROUTE_SESSION_DELIMITER = "__conversation__"


def _now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


@dataclass(slots=True)
class RouteSessionSummary:
    session_name: str
    title: str
    created_at: str
    updated_at: str

    @property
    def short_id(self) -> str:
        for delimiter in (
            _ROUTE_SESSION_DELIMITER,
            _LEGACY_ROUTE_SESSION_DELIMITER,
        ):
            if delimiter in self.session_name:
                return self.session_name.split(delimiter, 1)[-1]
        return self.session_name[-8:]

    def to_dict(self) -> dict[str, str]:
        return {
            "session_name": self.session_name,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RouteSessionSummary":
        return cls(
            session_name=str(data.get("session_name", "")).strip(),
            title=str(data.get("title", "")).strip() or "Session",
            created_at=str(data.get("created_at", "")).strip() or _now_text(),
            updated_at=str(data.get("updated_at", "")).strip() or _now_text(),
        )


@dataclass(slots=True)
class RouteSessionState:
    current_session_name: str | None = None
    sessions: list[RouteSessionSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "current_session_name": self.current_session_name,
            "sessions": [item.to_dict() for item in self.sessions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RouteSessionState":
        current_session_name = data.get("current_session_name")
        if not isinstance(current_session_name, str):
            current_session_name = None

        raw_sessions = data.get("sessions", data.get("conversations", []))
        sessions: list[RouteSessionSummary] = []
        if isinstance(raw_sessions, list):
            for item in raw_sessions:
                if isinstance(item, dict):
                    sessions.append(RouteSessionSummary.from_dict(item))

        return cls(
            current_session_name=current_session_name,
            sessions=sessions,
        )


@dataclass(slots=True)
class RouteSessionsState:
    routes: dict[str, RouteSessionState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "routes": {
                route_key: route_state.to_dict()
                for route_key, route_state in self.routes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RouteSessionsState":
        routes: dict[str, RouteSessionState] = {}
        raw_routes = data.get("routes", {})
        if isinstance(raw_routes, dict):
            for route_key, route_data in raw_routes.items():
                if isinstance(route_key, str) and isinstance(route_data, dict):
                    routes[route_key] = RouteSessionState.from_dict(route_data)
        return cls(routes=routes)


@dataclass(slots=True)
class DeleteRouteSessionResult:
    deleted: RouteSessionSummary
    current: RouteSessionSummary
    created_replacement: bool = False


class RouteSessionStore:
    def __init__(
        self,
        path: str | Path = DEFAULT_ROUTE_SESSION_STORE_PATH,
    ) -> None:
        self.path = Path(path)
        self._state = RouteSessionsState()
        self._loaded = False
        self._lock = threading.RLock()

    def get_current_session(self, route_key: str) -> RouteSessionSummary:
        with self._lock:
            self._ensure_loaded()
            route_state = self._get_or_create_route_state(route_key)
            current = self._get_current_summary(route_state)
            if current is None:
                current = self._append_session(route_key, route_state, title=None)
                self._save()
            return copy.deepcopy(current)

    def list_sessions(self, route_key: str) -> list[RouteSessionSummary]:
        with self._lock:
            self._ensure_loaded()
            route_state = self._get_or_create_route_state(route_key)
            if self._get_current_summary(route_state) is None:
                self._append_session(route_key, route_state, title=None)
                self._save()
            return [
                copy.deepcopy(item)
                for item in self._ordered_sessions(route_state)
            ]

    def create_session(
        self,
        route_key: str,
        *,
        title: str | None = None,
    ) -> RouteSessionSummary:
        with self._lock:
            self._ensure_loaded()
            route_state = self._get_or_create_route_state(route_key)
            created = self._append_session(route_key, route_state, title=title)
            self._save()
            return copy.deepcopy(created)

    def switch_session(
        self,
        route_key: str,
        index: int,
    ) -> RouteSessionSummary:
        with self._lock:
            self._ensure_loaded()
            route_state = self._get_or_create_route_state(route_key)
            ordered = self._ordered_sessions(route_state)
            if index < 1 or index > len(ordered):
                raise ValueError("Session number is out of range")
            selected = ordered[index - 1]
            route_state.current_session_name = selected.session_name
            selected.updated_at = _now_text()
            self._save()
            return copy.deepcopy(selected)

    def rename_current_session(
        self,
        route_key: str,
        title: str,
    ) -> RouteSessionSummary:
        with self._lock:
            cleaned_title = title.strip()
            if not cleaned_title:
                raise ValueError("Session title cannot be empty")
            self._ensure_loaded()
            route_state = self._get_or_create_route_state(route_key)
            current = self._get_current_summary(route_state)
            if current is None:
                current = self._append_session(route_key, route_state, title=None)
            current.title = cleaned_title
            current.updated_at = _now_text()
            self._save()
            return copy.deepcopy(current)

    def delete_current_session(self, route_key: str) -> DeleteRouteSessionResult:
        with self._lock:
            self._ensure_loaded()
            route_state = self._get_or_create_route_state(route_key)
            current = self._get_current_summary(route_state)
            if current is None:
                current = self._append_session(route_key, route_state, title=None)
            deleted = copy.deepcopy(current)
            route_state.sessions = [
                item
                for item in route_state.sessions
                if item.session_name != current.session_name
            ]

            created_replacement = False
            if not route_state.sessions:
                replacement = self._append_session(route_key, route_state, title=None)
                created_replacement = True
            else:
                replacement = self._ordered_sessions(route_state)[0]
                route_state.current_session_name = replacement.session_name
                replacement.updated_at = _now_text()

            self._save()
            return DeleteRouteSessionResult(
                deleted=deleted,
                current=copy.deepcopy(replacement),
                created_replacement=created_replacement,
            )

    def touch_session(
        self,
        route_key: str,
        session_name: str,
        *,
        updated_at: str | None = None,
    ) -> None:
        with self._lock:
            self._ensure_loaded()
            route_state = self._get_or_create_route_state(route_key)
            summary = self._find_session(route_state, session_name)
            if summary is None:
                return
            summary.updated_at = updated_at or _now_text()
            self._save()

    def remove_session(self, session_name: str) -> bool:
        with self._lock:
            self._ensure_loaded()
            changed = False
            for route_key, route_state in self._state.routes.items():
                if not any(
                    item.session_name == session_name
                    for item in route_state.sessions
                ):
                    continue

                changed = True
                route_state.sessions = [
                    item
                    for item in route_state.sessions
                    if item.session_name != session_name
                ]
                current = self._get_current_summary(route_state)
                if current is not None:
                    continue
                if route_state.sessions:
                    replacement = max(
                        route_state.sessions,
                        key=lambda item: item.updated_at,
                    )
                    route_state.current_session_name = replacement.session_name
                    continue
                self._append_session(route_key, route_state, title=None)

            if changed:
                self._save()
            return changed

    def replace_session_name(self, old_name: str, new_name: str) -> bool:
        with self._lock:
            self._ensure_loaded()
            changed = False
            for route_state in self._state.routes.values():
                if route_state.current_session_name == old_name:
                    route_state.current_session_name = new_name
                    changed = True
                for item in route_state.sessions:
                    if item.session_name != old_name:
                        continue
                    item.session_name = new_name
                    changed = True
            if changed:
                self._save()
            return changed

    def _get_or_create_route_state(self, route_key: str) -> RouteSessionState:
        route_state = self._state.routes.get(route_key)
        if route_state is None:
            route_state = RouteSessionState()
            self._state.routes[route_key] = route_state
        current = self._get_current_summary(route_state)
        if current is None and route_state.sessions:
            current = max(
                route_state.sessions,
                key=lambda item: item.updated_at,
            )
            route_state.current_session_name = current.session_name
        return route_state

    def _get_current_summary(
        self,
        route_state: RouteSessionState,
    ) -> RouteSessionSummary | None:
        if not route_state.current_session_name:
            return None
        return self._find_session(
            route_state,
            route_state.current_session_name,
        )

    def _find_session(
        self,
        route_state: RouteSessionState,
        session_name: str,
    ) -> RouteSessionSummary | None:
        for item in route_state.sessions:
            if item.session_name == session_name:
                return item
        return None

    def _ordered_sessions(
        self,
        route_state: RouteSessionState,
    ) -> list[RouteSessionSummary]:
        current = self._get_current_summary(route_state)
        remaining = [
            item
            for item in route_state.sessions
            if current is None or item.session_name != current.session_name
        ]
        remaining.sort(key=lambda item: item.updated_at, reverse=True)
        if current is None:
            return remaining
        return [current, *remaining]

    def _append_session(
        self,
        route_key: str,
        route_state: RouteSessionState,
        *,
        title: str | None,
    ) -> RouteSessionSummary:
        now_text = _now_text()
        next_number = len(route_state.sessions) + 1
        summary = RouteSessionSummary(
            session_name=f"{route_key}{_ROUTE_SESSION_DELIMITER}{uuid.uuid4().hex[:8]}",
            title=title.strip() if title and title.strip() else f"Session {next_number}",
            created_at=now_text,
            updated_at=now_text,
        )
        route_state.sessions.append(summary)
        route_state.current_session_name = summary.session_name
        return summary

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        source_path = self.path
        if not source_path.exists():
            legacy_path = self._legacy_path()
            if legacy_path is None or not legacy_path.exists():
                self._state = RouteSessionsState()
                return
            source_path = legacy_path

        try:
            data = json.loads(source_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._state = RouteSessionsState()
            return
        if not isinstance(data, dict):
            self._state = RouteSessionsState()
            return
        self._state = RouteSessionsState.from_dict(data)

    def _legacy_path(self) -> Path | None:
        if self.path.name == DEFAULT_ROUTE_SESSION_STORE_PATH.name:
            return self.path.with_name(_LEGACY_ROUTE_SESSION_STORE_NAME)
        return None

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                self._state.to_dict(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
