from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .sessions import normalize_session_name


class AgentTraceStore:
    def __init__(
        self,
        base_dir: str | Path = ".echobot/agent_traces",
    ) -> None:
        self.base_dir = Path(base_dir)

    def create_run_id(self) -> str:
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        return f"{timestamp}-{uuid.uuid4().hex[:8]}"

    def trace_path(
        self,
        session_name: str,
        run_id: str,
    ) -> Path:
        normalized_name = normalize_session_name(session_name)
        return self.base_dir / normalized_name / f"{run_id}.jsonl"

    def append_event(
        self,
        session_name: str,
        run_id: str,
        event: str,
        data: dict[str, Any] | None = None,
    ) -> Path:
        path = self.trace_path(session_name, run_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        record: dict[str, Any] = {
            "event": event,
            "session_name": normalize_session_name(session_name),
            "run_id": run_id,
            "created_at": _now_text(),
        }
        if data:
            record.update(data)

        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    def read_events(
        self,
        session_name: str,
        run_id: str,
    ) -> list[dict[str, Any]]:
        path = self.trace_path(session_name, run_id)
        if not path.exists():
            return []

        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    events.append(payload)
        return events


def _now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
