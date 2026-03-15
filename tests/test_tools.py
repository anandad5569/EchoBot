from __future__ import annotations

import json
import threading
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from echobot import AgentCore, LLMMessage, WebRequestTool, create_basic_tool_registry
from echobot.models import LLMResponse, ToolCall
from echobot.providers.base import LLMProvider
from echobot.tools import BaseTool, ToolRegistry
from echobot.tools.builtin import _decode_command_output


class EchoTool(BaseTool):
    name = "echo_tool"
    description = "Return the same text."
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


class _StaticResponseHandler(BaseHTTPRequestHandler):
    response_body = b"hello"
    content_type = "text/plain; charset=utf-8"
    status = 200

    def do_GET(self) -> None:  # noqa: N802
        body = self.response_body
        self.send_response(self.status)
        self.send_header("Content-Type", self.content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class LocalHttpServer:
    def __init__(
        self,
        body: str | bytes,
        *,
        content_type: str = "text/plain; charset=utf-8",
        status: int = 200,
    ) -> None:
        self.body = body
        self.content_type = content_type
        self.status = status
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "LocalHttpServer":
        if isinstance(self.body, bytes):
            response_body = self.body
        else:
            response_body = self.body.encode("utf-8")

        handler_class = type(
            "TestHandler",
            (_StaticResponseHandler,),
            {
                "response_body": response_body,
                "content_type": self.content_type,
                "status": self.status,
            },
        )
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("Server is not running")

        host, port = self._server.server_address
        return f"http://{host}:{port}/"


class FakeToolProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages: list[list[LLMMessage]] = []

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
        self.calls += 1
        self.seen_messages.append(list(messages))

        if self.calls == 1:
            tool_calls = [
                ToolCall(
                    id="call_1",
                    name="echo_tool",
                    arguments='{"text": "hello"}',
                )
            ]
            return LLMResponse(
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=tool_calls,
                ),
                model="fake-model",
                finish_reason="tool_calls",
                tool_calls=tool_calls,
            )

        return LLMResponse(
            message=LLMMessage(role="assistant", content="done"),
            model="fake-model",
            finish_reason="stop",
        )


class FakeMemorySearchSupport:
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        min_score: float = 0.1,
    ) -> dict[str, object]:
        return {
            "query": query,
            "max_results": max_results,
            "min_score": min_score,
            "results": [{"path": "MEMORY.md", "content": "saved note"}],
        }


class AgentToolLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_ask_with_tools_runs_tool_loop(self) -> None:
        provider = FakeToolProvider()
        agent = AgentCore(provider)
        registry = ToolRegistry([EchoTool()])

        result = await agent.ask_with_tools("test", tool_registry=registry)

        self.assertEqual("done", result.response.message.content)
        self.assertEqual(2, provider.calls)
        self.assertEqual("tool", provider.seen_messages[1][-1].role)
        tool_payload = json.loads(provider.seen_messages[1][-1].content)
        self.assertTrue(tool_payload["ok"])
        self.assertEqual("hello", tool_payload["result"]["echo"])


class BasicToolRegistryTests(unittest.IsolatedAsyncioTestCase):
    def test_decode_command_output_prefers_utf8_when_locale_is_not_utf8(self) -> None:
        raw_bytes = "Beijing: 🌫  +34°F\n".encode("utf-8")

        with patch(
            "echobot.tools.builtin.locale.getpreferredencoding",
            return_value="cp936",
        ):
            decoded = _decode_command_output(raw_bytes)

        self.assertEqual("Beijing: 🌫  +34°F\n", decoded)

    def test_decode_command_output_falls_back_to_locale_encoding(self) -> None:
        raw_bytes = "天气晴".encode("gbk")

        with patch(
            "echobot.tools.builtin.locale.getpreferredencoding",
            return_value="cp936",
        ):
            decoded = _decode_command_output(raw_bytes)

        self.assertEqual("天气晴", decoded)

    async def test_file_tools_stay_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            registry = create_basic_tool_registry(workspace)

            write_result = await registry.execute(
                ToolCall(
                    id="call_write",
                    name="write_text_file",
                    arguments='{"path": "notes/test.txt", "content": "hello"}',
                )
            )
            read_result = await registry.execute(
                ToolCall(
                    id="call_read",
                    name="read_text_file",
                    arguments='{"path": "notes/test.txt"}',
                )
            )
            bad_result = await registry.execute(
                ToolCall(
                    id="call_bad",
                    name="read_text_file",
                    arguments='{"path": "../secret.txt"}',
                )
            )

            write_payload = json.loads(write_result.content)
            read_payload = json.loads(read_result.content)
            bad_payload = json.loads(bad_result.content)

            self.assertTrue(write_payload["ok"])
            self.assertEqual("hello", read_payload["result"]["content"])
            self.assertFalse(bad_payload["ok"])

    async def test_web_request_tool_reads_local_page_when_private_access_is_enabled(self) -> None:
        registry = ToolRegistry([WebRequestTool(allow_private_network=True)])
        with LocalHttpServer("hello web tool") as server:
            result = await registry.execute(
                ToolCall(
                    id="call_web",
                    name="fetch_web_page",
                    arguments=json.dumps({"url": server.url}, ensure_ascii=False),
                )
            )

        payload = json.loads(result.content)
        self.assertTrue(payload["ok"])
        self.assertEqual(200, payload["result"]["status"])
        self.assertIn("hello web tool", payload["result"]["content"])
        self.assertEqual("text", payload["result"]["content_kind"])

    async def test_web_request_tool_blocks_private_network_by_default(self) -> None:
        registry = create_basic_tool_registry()
        result = await registry.execute(
            ToolCall(
                id="call_web_private",
                name="fetch_web_page",
                arguments=json.dumps({"url": "http://127.0.0.1/"}, ensure_ascii=False),
            )
        )

        payload = json.loads(result.content)
        self.assertFalse(payload["ok"])
        self.assertIn("Private network addresses are not allowed", payload["error"])

    async def test_web_request_tool_extracts_html_text(self) -> None:
        registry = ToolRegistry([WebRequestTool(allow_private_network=True)])
        html_page = (
            "<html><head><title>Example</title><style>.hidden{display:none;}</style></head>"
            "<body><h1>Hello</h1><p>World</p><script>ignore_me()</script></body></html>"
        )

        with LocalHttpServer(html_page, content_type="text/html; charset=utf-8") as server:
            result = await registry.execute(
                ToolCall(
                    id="call_web_html",
                    name="fetch_web_page",
                    arguments=json.dumps({"url": server.url}, ensure_ascii=False),
                )
            )

        payload = json.loads(result.content)
        self.assertTrue(payload["ok"])
        self.assertEqual("html", payload["result"]["content_kind"])
        self.assertIn("Hello", payload["result"]["content"])
        self.assertIn("World", payload["result"]["content"])
        self.assertNotIn("ignore_me()", payload["result"]["content"])

    async def test_web_request_tool_rejects_binary_content(self) -> None:
        registry = ToolRegistry([WebRequestTool(allow_private_network=True)])
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

        with LocalHttpServer(png_header, content_type="image/png") as server:
            result = await registry.execute(
                ToolCall(
                    id="call_web_binary",
                    name="fetch_web_page",
                    arguments=json.dumps({"url": server.url}, ensure_ascii=False),
                )
            )

        payload = json.loads(result.content)
        self.assertFalse(payload["ok"])
        self.assertIn("Only text responses are supported", payload["error"])

    async def test_command_execution_tool_runs_in_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "subdir").mkdir()
            registry = create_basic_tool_registry(workspace)

            result = await registry.execute(
                ToolCall(
                    id="call_shell",
                    name="run_shell_command",
                    arguments=json.dumps(
                        {
                            "command": 'python -c "from pathlib import Path; print(Path.cwd().name)"',
                            "workdir": "subdir",
                        },
                        ensure_ascii=False,
                    ),
                )
            )

            payload = json.loads(result.content)
            self.assertTrue(payload["ok"])
            self.assertEqual(0, payload["result"]["return_code"])
            self.assertIn("subdir", payload["result"]["stdout"])

    async def test_basic_tool_registry_can_register_memory_search(self) -> None:
        registry = create_basic_tool_registry(
            memory_support=FakeMemorySearchSupport(),
        )

        result = await registry.execute(
            ToolCall(
                id="call_memory",
                name="memory_search",
                arguments=json.dumps(
                    {
                        "query": "user preference",
                        "max_results": 2,
                        "min_score": 0.2,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        payload = json.loads(result.content)
        self.assertTrue(payload["ok"])
        self.assertEqual("user preference", payload["result"]["query"])
        self.assertEqual(2, payload["result"]["max_results"])
        self.assertEqual(0.2, payload["result"]["min_score"])
        self.assertEqual("MEMORY.md", payload["result"]["results"][0]["path"])
