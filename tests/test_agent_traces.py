from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from echobot import (
    AgentCore,
    AgentTraceStore,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    SessionAgentRunner,
    SessionStore,
)
from echobot.models import ToolCall
from echobot.providers.base import LLMProvider
from echobot.tools import BaseTool, ToolRegistry


class EchoTool(BaseTool):
    name = "echo_tool"
    description = "Echo text back."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
        },
        "required": ["text"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, str]) -> dict[str, str]:
        return {"echo": arguments["text"]}


class ToolThenAnswerProvider(LLMProvider):
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

        if messages and messages[-1].role == "tool":
            return LLMResponse(
                message=LLMMessage(role="assistant", content="all done"),
                model="fake-model",
                usage=LLMUsage(
                    prompt_tokens=120,
                    completion_tokens=10,
                    total_tokens=130,
                    prompt_cache_hit_tokens=80,
                    prompt_cache_miss_tokens=40,
                ),
            )

        tool_calls = [
            ToolCall(
                id="call_1",
                name="echo_tool",
                arguments='{"text":"hello"}',
            )
        ]
        return LLMResponse(
            message=LLMMessage(
                role="assistant",
                content="",
                tool_calls=tool_calls,
            ),
            model="fake-model",
            tool_calls=tool_calls,
        )


class ToolThenFailProvider(LLMProvider):
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

        if messages and messages[-1].role == "tool":
            raise RuntimeError("provider exploded")

        tool_calls = [
            ToolCall(
                id="call_1",
                name="echo_tool",
                arguments='{"text":"hello"}',
            )
        ]
        return LLMResponse(
            message=LLMMessage(
                role="assistant",
                content="",
                tool_calls=tool_calls,
            ),
            model="fake-model",
            tool_calls=tool_calls,
        )


def build_runner(
    workspace: Path,
    provider: LLMProvider,
) -> tuple[SessionAgentRunner, SessionStore, AgentTraceStore]:
    session_store = SessionStore(workspace / "agent_sessions")
    trace_store = AgentTraceStore(workspace / "agent_traces")
    runner = SessionAgentRunner(
        AgentCore(provider),
        session_store,
        tool_registry_factory=lambda *_args: ToolRegistry([EchoTool()]),
        trace_store=trace_store,
    )
    return runner, session_store, trace_store


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class AgentTraceStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_run_writes_trace_events_per_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            runner, session_store, trace_store = build_runner(
                workspace,
                ToolThenAnswerProvider(),
            )

            result = await runner.run_prompt("demo", "hello")

            trace_dir = workspace / "agent_traces" / "demo"
            trace_files = list(trace_dir.glob("*.jsonl"))
            self.assertEqual(1, len(trace_files))

            records = read_jsonl(trace_files[0])
            self.assertEqual(
                [
                    "turn_started",
                    "assistant_message",
                    "tool_result",
                    "assistant_message",
                    "turn_completed",
                ],
                [str(record["event"]) for record in records],
            )
            self.assertEqual("echo_tool", records[2]["tool_name"])
            self.assertEqual("all done", records[3]["message"]["content"])
            self.assertEqual("all done", records[4]["final_message"]["content"])
            self.assertEqual(80, records[4]["usage"]["prompt_cache_hit_tokens"])
            self.assertEqual(40, records[4]["usage"]["prompt_cache_miss_tokens"])
            self.assertEqual(66.67, records[4]["usage"]["prompt_cache_hit_rate_percent"])

            saved_session = session_store.load_session("demo")
            self.assertEqual("all done", saved_session.history[-1].content)
            self.assertEqual("all done", result.agent_result.response.message.content)

            trace_path = trace_store.trace_path("demo", str(records[0]["run_id"]))
            self.assertEqual(trace_files[0], trace_path)

    async def test_failed_run_keeps_trace_even_without_final_session_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            runner, session_store, _trace_store = build_runner(
                workspace,
                ToolThenFailProvider(),
            )

            with self.assertRaisesRegex(RuntimeError, "provider exploded"):
                await runner.run_prompt("demo", "hello")

            trace_dir = workspace / "agent_traces" / "demo"
            trace_files = list(trace_dir.glob("*.jsonl"))
            self.assertEqual(1, len(trace_files))

            records = read_jsonl(trace_files[0])
            self.assertEqual(
                [
                    "turn_started",
                    "assistant_message",
                    "tool_result",
                    "turn_failed",
                ],
                [str(record["event"]) for record in records],
            )
            self.assertEqual("RuntimeError", records[-1]["error_type"])
            self.assertEqual("provider exploded", records[-1]["error"])

            saved_session = session_store.load_session("demo")
            self.assertEqual([], saved_session.history)
