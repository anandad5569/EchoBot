from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from ..runtime.sessions import ChatSession


JOB_CANCELLED_TEXT = "后台任务已停止。"


@dataclass(slots=True)
class OrchestratedTurnResult:
    session: ChatSession
    response_text: str
    delegated: bool
    completed: bool
    job_id: str | None = None
    status: str = "completed"
    role_name: str = "default"
    steps: int = 1
    compressed_summary: str = ""


@dataclass(slots=True)
class ConversationJob:
    job_id: str
    session_name: str
    prompt: str
    immediate_response: str
    role_name: str
    status: str
    created_at: str
    updated_at: str
    trace_run_id: str | None = None
    final_response: str = ""
    error: str = ""
    steps: int = 0


CompletionCallback = Callable[[ConversationJob], Awaitable[None]]


class ConversationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ConversationJob] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        *,
        session_name: str,
        prompt: str,
        immediate_response: str,
        role_name: str,
        trace_run_id: str | None = None,
    ) -> ConversationJob:
        async with self._lock:
            now_text = _now_text()
            job = ConversationJob(
                job_id=uuid.uuid4().hex,
                session_name=session_name,
                prompt=prompt,
                immediate_response=immediate_response,
                role_name=role_name,
                status="running",
                created_at=now_text,
                updated_at=now_text,
                trace_run_id=trace_run_id,
            )
            self._jobs[job.job_id] = job
            return _copy_job(job)

    async def get(self, job_id: str) -> ConversationJob | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return _copy_job(job)

    async def set_completed(
        self,
        job_id: str,
        *,
        final_response: str,
        steps: int,
    ) -> ConversationJob | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.status = "completed"
            job.updated_at = _now_text()
            job.final_response = final_response
            job.steps = steps
            job.error = ""
            return _copy_job(job)

    async def set_failed(
        self,
        job_id: str,
        *,
        final_response: str,
        error: str,
        steps: int = 0,
    ) -> ConversationJob | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.status = "failed"
            job.updated_at = _now_text()
            job.final_response = final_response
            job.error = error
            job.steps = steps
            return _copy_job(job)

    async def set_cancelled(
        self,
        job_id: str,
        *,
        final_response: str,
        steps: int = 0,
    ) -> ConversationJob | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.status = "cancelled"
            job.updated_at = _now_text()
            job.final_response = final_response
            job.error = ""
            job.steps = steps
            return _copy_job(job)

    async def counts(self) -> dict[str, int]:
        async with self._lock:
            result = {"running": 0, "completed": 0, "failed": 0, "cancelled": 0}
            for job in self._jobs.values():
                result[job.status] = result.get(job.status, 0) + 1
            return result

    async def list_for_session(
        self,
        session_name: str,
        *,
        status: str | None = None,
    ) -> list[ConversationJob]:
        async with self._lock:
            jobs = [
                _copy_job(job)
                for job in self._jobs.values()
                if job.session_name == session_name
                and (status is None or job.status == status)
            ]
        jobs.sort(key=lambda item: item.created_at)
        return jobs


def _now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _copy_job(job: ConversationJob) -> ConversationJob:
    return ConversationJob(
        job_id=job.job_id,
        session_name=job.session_name,
        prompt=job.prompt,
        immediate_response=job.immediate_response,
        role_name=job.role_name,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        trace_run_id=job.trace_run_id,
        final_response=job.final_response,
        error=job.error,
        steps=job.steps,
    )
