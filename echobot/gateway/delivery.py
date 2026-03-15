from __future__ import annotations

import copy
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..channels.types import ChannelAddress, DeliveryTarget


DEFAULT_DELIVERY_STORE_PATH = Path(".echobot/delivery.json")


@dataclass(slots=True)
class DeliveryState:
    routes: dict[str, DeliveryTarget] = field(default_factory=dict)
    latest_session_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "routes": {
                session_name: target.to_dict()
                for session_name, target in self.routes.items()
            },
            "latest_session_name": self.latest_session_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "DeliveryState":
        raw_routes = data.get("routes", {})
        routes: dict[str, DeliveryTarget] = {}
        if isinstance(raw_routes, dict):
            for session_name, target_data in raw_routes.items():
                if isinstance(session_name, str) and isinstance(target_data, dict):
                    routes[session_name] = DeliveryTarget.from_dict(target_data)
        latest_session_name = data.get("latest_session_name")
        if not isinstance(latest_session_name, str):
            latest_session_name = None
        return cls(
            routes=routes,
            latest_session_name=latest_session_name,
        )


class DeliveryStore:
    def __init__(
        self,
        path: str | Path = DEFAULT_DELIVERY_STORE_PATH,
    ) -> None:
        self.path = Path(path)
        self._state = DeliveryState()
        self._loaded = False
        self._lock = threading.RLock()

    def remember(
        self,
        session_name: str,
        address: ChannelAddress,
        metadata: dict[str, object] | None = None,
    ) -> None:
        with self._lock:
            self._ensure_loaded()
            self._state.routes[session_name] = DeliveryTarget(
                address=copy.deepcopy(address),
                metadata=dict(metadata or {}),
            )
            self._state.latest_session_name = session_name
            self._save()

    def get_session_target(self, session_name: str) -> DeliveryTarget | None:
        with self._lock:
            self._ensure_loaded()
            target = self._state.routes.get(session_name)
            return copy.deepcopy(target) if target is not None else None

    def get_latest_target(self) -> DeliveryTarget | None:
        with self._lock:
            self._ensure_loaded()
            if not self._state.latest_session_name:
                return None
            return self.get_session_target(self._state.latest_session_name)

    def forget(self, session_name: str) -> None:
        with self._lock:
            self._ensure_loaded()
            removed = self._state.routes.pop(session_name, None)
            if removed is None:
                return
            if self._state.latest_session_name == session_name:
                if self._state.routes:
                    self._state.latest_session_name = list(self._state.routes)[-1]
                else:
                    self._state.latest_session_name = None
            self._save()

    def replace_session_name(self, old_name: str, new_name: str) -> bool:
        with self._lock:
            self._ensure_loaded()
            target = self._state.routes.pop(old_name, None)
            if target is None:
                return False
            self._state.routes[new_name] = target
            if self._state.latest_session_name == old_name:
                self._state.latest_session_name = new_name
            self._save()
            return True

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            self._state = DeliveryState()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._state = DeliveryState()
            return
        if not isinstance(data, dict):
            self._state = DeliveryState()
            return
        self._state = DeliveryState.from_dict(data)

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
