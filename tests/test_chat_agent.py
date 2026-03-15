from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from echobot.cli.chat import _build_streamed_assistant_writer, run_turn
from echobot.cli.session_commands import (
    handle_session_command,
    is_session_command,
)
from echobot.cli.trace import (
    build_tool_call_trace_title,
    build_tool_result_trace_title,
    format_json_text,
    print_tool_trace,
)
from echobot import AgentCore, ChatSession, LLMMessage, LLMResponse, SessionStore, ToolCall
from echobot.providers.base import LLMProvider


class ChatAgentTraceTests(unittest.TestCase):
    def test_format_json_text_pretty_prints_json(self) -> None:
        formatted = format_json_text('{"ok":true,"result":{"name":"demo"}}')

        self.assertIn('"ok": true', formatted)
        self.assertIn('"name": "demo"', formatted)

    def test_print_tool_trace_outputs_skill_specific_labels(self) -> None:
        messages = [
            LLMMessage(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="activate_skill",
                        arguments='{"name":"demo-skill"}',
                    ),
                    ToolCall(
                        id="call_2",
                        name="list_skill_resources",
                        arguments='{"name":"demo-skill","folder":"references"}',
                    ),
                    ToolCall(
                        id="call_3",
                        name="read_skill_resource",
                        arguments='{"name":"demo-skill","path":"references/guide.md"}',
                    ),
                    ToolCall(
                        id="call_4",
                        name="read_text_file",
                        arguments='{"path":"README.md"}',
                    )
                ],
            ),
            LLMMessage(
                role="tool",
                content=(
                    '{"ok":true,"result":{"kind":"skill_activation","name":"demo-skill",'
                    '"already_active":false}}'
                ),
                tool_call_id="call_1",
            ),
            LLMMessage(
                role="tool",
                content=(
                    '{"ok":true,"result":{"kind":"skill_resource_list","name":"demo-skill",'
                    '"folder":"references","entries":["references/guide.md"]}}'
                ),
                tool_call_id="call_2",
            ),
            LLMMessage(
                role="tool",
                content=(
                    '{"ok":true,"result":{"kind":"skill_resource_content","name":"demo-skill",'
                    '"path":"references/guide.md","content":"guide"}}'
                ),
                tool_call_id="call_3",
            ),
            LLMMessage(
                role="tool",
                content='{"ok":true,"result":{"path":"README.md"}}',
                tool_call_id="call_4",
            ),
        ]

        stream = io.StringIO()
        with redirect_stdout(stream):
            print_tool_trace(messages)

        output = stream.getvalue()
        self.assertIn("[skill-call] activate_skill", output)
        self.assertIn("[skill-call] list_skill_resources", output)
        self.assertIn("[skill-call] read_skill_resource", output)
        self.assertIn("[tool-call] read_text_file", output)
        self.assertIn('"name": "demo-skill"', output)
        self.assertIn("[skill-activate] demo-skill", output)
        self.assertIn("[skill-resources] demo-skill (references)", output)
        self.assertIn("[skill-resource] demo-skill | references/guide.md", output)
        self.assertIn("[tool-result] read_text_file", output)

    def test_build_tool_trace_titles_detect_skill_results(self) -> None:
        self.assertEqual("[skill-call] activate_skill", build_tool_call_trace_title("activate_skill"))
        self.assertEqual("[tool-call] read_text_file", build_tool_call_trace_title("read_text_file"))
        self.assertEqual(
            "[skill-activate] demo-skill (already active)",
            build_tool_result_trace_title(
                "activate_skill",
                (
                    '{"ok":true,"result":{"kind":"skill_activation","name":"demo-skill",'
                    '"already_active":true}}'
                ),
            ),
        )
        self.assertEqual(
            "[skill-resource] demo-skill | references/guide.md",
            build_tool_result_trace_title(
                "read_skill_resource",
                (
                    '{"ok":true,"result":{"kind":"skill_resource_content","name":"demo-skill",'
                    '"path":"references/guide.md"}}'
                ),
            ),
        )


class ChatAgentSessionTests(unittest.TestCase):
    def test_is_session_command_recognizes_session_prefix(self) -> None:
        self.assertTrue(is_session_command("/session list"))
        self.assertTrue(is_session_command("session current"))
        self.assertFalse(is_session_command("/session-list"))

    def test_handle_session_command_current_prints_current_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_store = SessionStore(Path(temp_dir) / "sessions")
            session = ChatSession(
                name="demo",
                history=[LLMMessage(role="user", content="hello")],
                updated_at="",
            )
            session_store.save_session(session)
            session_store.set_current_session(session.name)

            stream = io.StringIO()
            with redirect_stdout(stream):
                current_session = handle_session_command(
                    "/session current",
                    session_store=session_store,
                    current_session=session,
                )

            output = stream.getvalue()
            self.assertEqual("demo", current_session.name)
            self.assertIn("Current session: demo", output)
            self.assertIn("(1 messages)", output)

    def test_handle_session_command_new_creates_and_switches_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_store = SessionStore(Path(temp_dir) / "sessions")
            current_session = session_store.create_session("first")
            current_session.history.append(LLMMessage(role="user", content="hello"))
            session_store.save_session(current_session)

            stream = io.StringIO()
            with redirect_stdout(stream):
                next_session = handle_session_command(
                    "/session new next",
                    session_store=session_store,
                    current_session=current_session,
                )

            output = stream.getvalue()
            self.assertEqual("next", next_session.name)
            self.assertEqual("next", session_store.get_current_session_name())
            self.assertEqual([], next_session.history)
            self.assertIn("Switched to new session: next", output)

    def test_handle_session_command_switch_loads_existing_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_store = SessionStore(Path(temp_dir) / "sessions")
            current_session = session_store.create_session("first")
            target_session = session_store.create_session("second")
            target_session.history = [LLMMessage(role="assistant", content="saved")]
            session_store.save_session(target_session)
            session_store.set_current_session(current_session.name)

            stream = io.StringIO()
            with redirect_stdout(stream):
                loaded_session = handle_session_command(
                    "/session switch second",
                    session_store=session_store,
                    current_session=current_session,
                )

            output = stream.getvalue()
            self.assertEqual("second", loaded_session.name)
            self.assertEqual("second", session_store.get_current_session_name())
            self.assertEqual("saved", loaded_session.history[0].content)
            self.assertIn("Switched to session: second", output)

    def test_handle_session_command_rejects_missing_switch_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_store = SessionStore(Path(temp_dir) / "sessions")
            current_session = session_store.create_session("demo")

            with self.assertRaisesRegex(ValueError, "Usage: /session switch <name>"):
                handle_session_command(
                    "/session switch",
                    session_store=session_store,
                    current_session=current_session,
                )


class FakeProvider(LLMProvider):
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
        return LLMResponse(
            message=LLMMessage(role="assistant", content="ok"),
            model="fake-model",
        )


class ChatAgentAsyncTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_turn_can_be_awaited_inside_existing_event_loop(self) -> None:
        agent = AgentCore(FakeProvider())

        result = await run_turn(
            agent,
            "hello",
            [],
            compressed_summary="",
            skill_registry=None,
            tool_registry=None,
            temperature=None,
            max_tokens=None,
        )

        self.assertEqual("ok", result.response.message.content)

    async def test_streamed_assistant_writer_prints_prefix_once(self) -> None:
        on_chunk, started = _build_streamed_assistant_writer()

        stream = io.StringIO()
        with redirect_stdout(stream):
            await on_chunk("Hel")
            await on_chunk("lo")

        self.assertTrue(started())
        self.assertEqual("Assistant> Hello", stream.getvalue())
