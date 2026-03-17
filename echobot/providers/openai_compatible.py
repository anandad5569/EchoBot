from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from ..models import (
    LLMMessage,
    LLMResponse,
    LLMTool,
    LLMUsage,
    ToolCall,
    message_content_to_text,
    normalize_message_content,
)
from .base import LLMProvider


@dataclass(slots=True)
class OpenAICompatibleSettings:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout: float = 60.0
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        prefix: str = "LLM_",
    ) -> "OpenAICompatibleSettings":
        source = os.environ if env is None else env
        api_key_name = f"{prefix}API_KEY"
        model_name = f"{prefix}MODEL"
        base_url_name = f"{prefix}BASE_URL"
        timeout_name = f"{prefix}TIMEOUT"

        extra_body_name = f"{prefix}EXTRA_BODY"

        api_key = _get_required_env(source, api_key_name)
        model = _get_required_env(source, model_name)
        base_url = _get_optional_env(source, base_url_name, default=cls.base_url)
        timeout_text = _get_optional_env(source, timeout_name, default=str(cls.timeout))
        extra_body_text = _get_optional_env(source, extra_body_name)

        try:
            timeout = float(timeout_text)
        except ValueError as exc:
            raise ValueError(f"{timeout_name} must be a number") from exc

        extra_body: dict[str, Any] = {}
        if extra_body_text is not None:
            try:
                parsed = json.loads(extra_body_text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{extra_body_name} must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError(f"{extra_body_name} must be a JSON object")
            extra_body = parsed

        return cls(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            extra_body=extra_body,
        )


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, settings: OpenAICompatibleSettings) -> None:
        self.settings = settings

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[LLMTool] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        payload = self._build_payload(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response_data = await asyncio.to_thread(self._post_json, payload)
        return self._parse_response(response_data)

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        *,
        tools: list[LLMTool] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        if tools:
            response = await self.generate(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = message_content_to_text(response.message.content)
            if content:
                yield content
            return

        payload = self._build_payload(
            messages=messages,
            tools=None,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        payload["stream"] = True

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[object] = asyncio.Queue()
        stream_end = object()

        def worker() -> None:
            try:
                for chunk in self._stream_text_chunks(payload):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as exc:  # pragma: no cover - thread forwarding
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, stream_end)

        thread = threading.Thread(
            target=worker,
            name="echobot-openai-stream",
            daemon=True,
        )
        thread.start()

        while True:
            item = await queue.get()
            if item is stream_end:
                break
            if isinstance(item, Exception):
                raise item
            yield str(item)

    def _build_payload(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMTool] | None,
        tool_choice: str | dict[str, Any] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [message.to_dict() for message in _merge_system_messages(messages)],
        }

        if tools:
            payload["tools"] = [tool.to_dict() for tool in tools]
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if self.settings.extra_body:
            payload.update(self.settings.extra_body)

        return payload

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        http_request = request.Request(
            url=url,
            data=body,
            headers=self._request_headers(),
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.settings.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"LLM provider request failed: status={exc.code}, detail={detail}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM provider network error: {exc.reason}") from exc

    def _stream_text_chunks(self, payload: dict[str, Any]) -> Iterator[str]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        http_request = request.Request(
            url=url,
            data=body,
            headers=self._request_headers(),
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.settings.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue

                    payload_text = line[5:].strip()
                    if not payload_text:
                        continue
                    if payload_text == "[DONE]":
                        break

                    chunk_text = self._parse_stream_chunk(payload_text)
                    if chunk_text:
                        yield chunk_text
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"LLM provider request failed: status={exc.code}, detail={detail}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM provider network error: {exc.reason}") from exc

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices")
        if not choices:
            raise RuntimeError("LLM provider response is missing choices")

        choice = choices[0]
        message_data = choice.get("message", {})
        tool_calls: list[ToolCall] = []
        for item in message_data.get("tool_calls", []):
            function_data = item.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=item.get("id", ""),
                    name=function_data.get("name", ""),
                    arguments=function_data.get("arguments", ""),
                )
            )

        assistant_message = LLMMessage(
            role=message_data.get("role", "assistant"),
            content=normalize_message_content(message_data.get("content") or ""),
            tool_calls=tool_calls,
        )

        return LLMResponse(
            message=assistant_message,
            model=data.get("model", self.settings.model),
            finish_reason=choice.get("finish_reason"),
            usage=LLMUsage.from_dict(data.get("usage")),
            tool_calls=tool_calls,
            raw_response=data,
        )

    def _request_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            **self.settings.extra_headers,
        }

    def _parse_stream_chunk(self, payload_text: str) -> str:
        try:
            data = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"LLM provider stream returned invalid JSON: {payload_text}"
            ) from exc

        error_payload = data.get("error")
        if isinstance(error_payload, dict):
            detail = error_payload.get("message") or payload_text
            raise RuntimeError(f"LLM provider stream error: {detail}")

        choices = data.get("choices")
        if not choices:
            return ""

        choice = choices[0]
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            return ""

        content = delta.get("content")
        if isinstance(content, str):
            return content
        return ""


def _merge_system_messages(messages: list[LLMMessage]) -> list[LLMMessage]:
    """Merge consecutive leading system messages into one.

    Some backends (e.g. vLLM) reject requests that contain more than one
    system message or a system message that is not at position 0.
    """
    if not messages:
        return messages

    system_parts: list[str] = []
    rest_start = 0
    for i, msg in enumerate(messages):
        if msg.role == "system":
            system_parts.append(message_content_to_text(msg.content))
            rest_start = i + 1
        else:
            break

    if len(system_parts) <= 1:
        return messages

    merged = LLMMessage(role="system", content="\n\n".join(system_parts))
    return [merged, *messages[rest_start:]]


def _get_required_env(source: Mapping[str, str], name: str) -> str:
    value = _get_optional_env(source, name)
    if value is None:
        raise ValueError(f"Missing required environment variable: {name}")

    return value


def _get_optional_env(
    source: Mapping[str, str],
    name: str,
    default: str | None = None,
) -> str | None:
    value = source.get(name)
    if value is None:
        return default

    cleaned = value.strip()
    if not cleaned:
        return default

    return cleaned
