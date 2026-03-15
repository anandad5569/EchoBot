from __future__ import annotations

import asyncio
import gc
import tempfile
import unittest
import warnings
from pathlib import Path

from echobot import AgentCore, LLMMessage, LLMResponse
from echobot.orchestration import (
    ConversationCoordinator,
    DecisionEngine,
    RoleCardRegistry,
    RoleplayEngine,
)
from echobot.orchestration.jobs import JOB_CANCELLED_TEXT
from echobot.providers.base import LLMProvider
from echobot.runtime.session_runner import SessionAgentRunner
from echobot.runtime.sessions import SessionStore


class FakeRoleplayProvider(LLMProvider):
    async def generate(
        self,
        messages,
        *,
        tools=None,
        tool_choice=None,
        temperature=None,
        max_tokens=None,
    ) -> LLMResponse:
        del tools, tool_choice, temperature, max_tokens
        system_text = "\n".join(
            message.content_text
            for message in messages
            if getattr(message, "role", "") == "system"
        )
        user_text = messages[-1].content_text if messages else ""
        if "The system decided this request needs the full agent" in system_text:
            content = "working"
        elif user_text.startswith("The full agent finished the task."):
            content = "done"
        elif user_text.startswith("The full agent failed while handling the task."):
            content = "failed"
        else:
            content = "pong"
        return LLMResponse(
            message=LLMMessage(role="assistant", content=content),
            model="fake-roleplay-model",
        )

    async def stream_generate(
        self,
        messages,
        *,
        tools=None,
        tool_choice=None,
        temperature=None,
        max_tokens=None,
    ):
        response = await self.generate(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield response.message.content


class SlowAgentProvider(LLMProvider):
    async def generate(
        self,
        messages,
        *,
        tools=None,
        tool_choice=None,
        temperature=None,
        max_tokens=None,
    ) -> LLMResponse:
        del messages, tools, tool_choice, temperature, max_tokens
        await asyncio.sleep(5)
        return LLMResponse(
            message=LLMMessage(role="assistant", content="done-late"),
            model="slow-agent-model",
        )


class ConversationCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_cancels_pending_job_without_runtime_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator, session_store = self._build_coordinator(Path(temp_dir))

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = await coordinator.handle_user_turn(
                    "demo",
                    "Please set a cron reminder",
                )
                await coordinator.close()
                job = await coordinator.get_job(result.job_id or "")

                self.assertIsNotNone(job)
                assert job is not None
                self.assertEqual("cancelled", job.status)
                self.assertEqual(JOB_CANCELLED_TEXT, job.final_response)

                session = session_store.load_session("demo")
                self.assertEqual(
                    ["Please set a cron reminder", "working"],
                    [message.content for message in session.history],
                )

                coordinator = None
                gc.collect()

            self.assertEqual([], self._never_awaited_warnings(caught))

    async def test_cancel_job_before_runner_starts_does_not_leave_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            coordinator, session_store = self._build_coordinator(Path(temp_dir))

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = await coordinator.handle_user_turn(
                    "demo",
                    "Please set a cron reminder",
                )
                job = await coordinator.cancel_job(result.job_id or "")

                self.assertIsNotNone(job)
                assert job is not None
                self.assertEqual("cancelled", job.status)
                self.assertEqual(JOB_CANCELLED_TEXT, job.final_response)

                session = session_store.load_session("demo")
                self.assertEqual(
                    [
                        "Please set a cron reminder",
                        "working",
                        JOB_CANCELLED_TEXT,
                    ],
                    [message.content for message in session.history],
                )

                await coordinator.close()
                coordinator = None
                gc.collect()

            self.assertEqual([], self._never_awaited_warnings(caught))

    def _build_coordinator(
        self,
        workspace: Path,
    ) -> tuple[ConversationCoordinator, SessionStore]:
        session_store = SessionStore(workspace / "sessions")
        agent_session_store = SessionStore(workspace / "agent_sessions")
        role_registry = RoleCardRegistry.discover(project_root=workspace)
        coordinator = ConversationCoordinator(
            session_store=session_store,
            agent_runner=SessionAgentRunner(
                AgentCore(SlowAgentProvider()),
                agent_session_store,
            ),
            decision_engine=DecisionEngine(),
            roleplay_engine=RoleplayEngine(
                AgentCore(FakeRoleplayProvider()),
                role_registry,
            ),
            role_registry=role_registry,
        )
        return coordinator, session_store

    def _never_awaited_warnings(
        self,
        caught: list[warnings.WarningMessage],
    ) -> list[warnings.WarningMessage]:
        return [
            warning
            for warning in caught
            if issubclass(warning.category, RuntimeWarning)
            and "was never awaited" in str(warning.message)
        ]
