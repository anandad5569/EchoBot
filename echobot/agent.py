from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .models import (
    LLMMessage,
    LLMResponse,
    LLMTool,
    build_user_message_content,
    message_content_to_text,
)
from .providers.base import LLMProvider
from .skill_support import SkillRegistry
from .tools.base import ToolRegistry


@dataclass(slots=True)
class AgentRunResult:
    response: LLMResponse
    new_messages: list[LLMMessage]
    history: list[LLMMessage]
    steps: int
    compressed_summary: str = ""


TraceCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class AgentCore:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        system_prompt: str | None = None,
        memory_support: Any | None = None,
    ) -> None:
        self.provider = provider
        self.system_prompt = system_prompt
        self.memory_support = memory_support

    async def ask(
        self,
        user_input: str,
        *,
        image_urls: Sequence[str] | None = None,
        history: Sequence[LLMMessage] | None = None,
        tools: Sequence[LLMTool] | None = None,
        extra_system_messages: Sequence[str] | None = None,
        transient_system_messages: Sequence[str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        persistent_messages = self._build_persistent_messages(
            user_input,
            image_urls=image_urls,
            history=history,
        )
        messages = self._build_request_messages(
            persistent_messages,
            extra_system_messages=extra_system_messages,
            transient_system_messages=transient_system_messages,
        )

        return await self.provider.generate(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def ask_stream(
        self,
        user_input: str,
        *,
        image_urls: Sequence[str] | None = None,
        history: Sequence[LLMMessage] | None = None,
        tools: Sequence[LLMTool] | None = None,
        extra_system_messages: Sequence[str] | None = None,
        transient_system_messages: Sequence[str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        persistent_messages = self._build_persistent_messages(
            user_input,
            image_urls=image_urls,
            history=history,
        )
        messages = self._build_request_messages(
            persistent_messages,
            extra_system_messages=extra_system_messages,
            transient_system_messages=transient_system_messages,
        )

        async for chunk in self.provider.stream_generate(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    async def ask_with_memory(
        self,
        user_input: str,
        *,
        image_urls: Sequence[str] | None = None,
        history: Sequence[LLMMessage] | None = None,
        compressed_summary: str = "",
        extra_system_messages: Sequence[str] | None = None,
        transient_system_messages: Sequence[str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        trace_callback: TraceCallback | None = None,
    ) -> AgentRunResult:
        persistent_messages = self._build_persistent_messages(
            user_input,
            image_urls=image_urls,
            history=history,
        )
        request_messages, persistent_messages, compressed_summary = (
            await self._prepare_request_messages(
                persistent_messages,
                extra_system_messages=extra_system_messages,
                transient_system_messages=transient_system_messages,
                compressed_summary=compressed_summary,
            )
        )
        response = await self.provider.generate(
            request_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        persistent_messages.append(response.message)
        await _emit_trace(
            trace_callback,
            "assistant_message",
            step=1,
            message=_message_to_trace_dict(response.message),
        )
        new_messages = [
            LLMMessage(
                role="user",
                content=build_user_message_content(user_input, image_urls),
            ),
            response.message,
        ]
        await self._remember_turn(new_messages)
        return AgentRunResult(
            response=response,
            new_messages=new_messages,
            history=persistent_messages,
            steps=1,
            compressed_summary=compressed_summary,
        )

    async def ask_with_tools(
        self,
        user_input: str,
        *,
        tool_registry: ToolRegistry,
        image_urls: Sequence[str] | None = None,
        history: Sequence[LLMMessage] | None = None,
        compressed_summary: str = "",
        tool_choice: str | dict[str, Any] | None = None,
        extra_system_messages: Sequence[str] | None = None,
        transient_system_messages: Sequence[str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_steps: int = 8,
        trace_callback: TraceCallback | None = None,
    ) -> AgentRunResult:
        persistent_messages = self._build_persistent_messages(
            user_input,
            image_urls=image_urls,
            history=history,
        )
        new_messages = [
            LLMMessage(
                role="user",
                content=build_user_message_content(user_input, image_urls),
            )
        ]
        llm_tools = tool_registry.to_llm_tools()

        for step in range(1, max_steps + 1):
            request_messages, persistent_messages, compressed_summary = (
                await self._prepare_request_messages(
                    persistent_messages,
                    extra_system_messages=extra_system_messages,
                    transient_system_messages=transient_system_messages,
                    compressed_summary=compressed_summary,
                )
            )
            response = await self.provider.generate(
                request_messages,
                tools=llm_tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            persistent_messages.append(response.message)
            new_messages.append(response.message)
            await _emit_trace(
                trace_callback,
                "assistant_message",
                step=step,
                message=_message_to_trace_dict(response.message),
            )

            if not response.tool_calls:
                await self._remember_turn(new_messages)
                return AgentRunResult(
                    response=response,
                    new_messages=new_messages,
                    history=persistent_messages,
                    steps=step,
                    compressed_summary=compressed_summary,
                )

            tool_results = await tool_registry.execute_tool_calls(response.tool_calls)
            for result in tool_results:
                tool_message = result.to_message()
                persistent_messages.append(tool_message)
                new_messages.append(tool_message)
                await _emit_trace(
                    trace_callback,
                    "tool_result",
                    step=step,
                    tool_name=result.tool_name,
                    tool_call_id=result.call_id,
                    is_error=result.is_error,
                    message=_message_to_trace_dict(tool_message),
                )

        raise RuntimeError(f"Tool loop exceeded max_steps={max_steps}")

    async def ask_with_skills(
        self,
        user_input: str,
        *,
        skill_registry: SkillRegistry,
        tool_registry: ToolRegistry | None = None,
        image_urls: Sequence[str] | None = None,
        history: Sequence[LLMMessage] | None = None,
        compressed_summary: str = "",
        tool_choice: str | dict[str, Any] | None = None,
        extra_system_messages: Sequence[str] | None = None,
        transient_system_messages: Sequence[str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_steps: int = 30,
        trace_callback: TraceCallback | None = None,
    ) -> AgentRunResult:
        active_skill_names = skill_registry.active_skill_names_from_history(history)
        combined_system_messages = list(extra_system_messages or [])
        explicit_activation_messages = skill_registry.build_explicit_activation_messages(
            user_input,
            active_skill_names=active_skill_names,
        )
        explicit_skill_names = skill_registry.explicit_skill_names(user_input)
        catalog_prompt = skill_registry.build_catalog_prompt(
            active_skill_names=active_skill_names + explicit_skill_names,
        )
        if catalog_prompt:
            combined_system_messages.append(catalog_prompt)
        combined_system_messages.extend(explicit_activation_messages)
        persisted_skill_messages = [
            LLMMessage(role="system", content=content)
            for content in explicit_activation_messages
        ]
        initial_active_skill_names = list(active_skill_names)
        for skill_name in explicit_skill_names:
            if skill_name not in initial_active_skill_names:
                initial_active_skill_names.append(skill_name)

        combined_registry = tool_registry.copy() if tool_registry else ToolRegistry()
        combined_registry.register_many(
            skill_registry.create_tools(active_skill_names=initial_active_skill_names)
        )

        if combined_registry.names():
            result = await self.ask_with_tools(
                user_input,
                tool_registry=combined_registry,
                image_urls=image_urls,
                history=history,
                compressed_summary=compressed_summary,
                tool_choice=tool_choice,
                extra_system_messages=combined_system_messages,
                transient_system_messages=transient_system_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                max_steps=max_steps,
                trace_callback=trace_callback,
            )
            return AgentRunResult(
                response=result.response,
                new_messages=persisted_skill_messages + result.new_messages,
                history=persisted_skill_messages + result.history,
                steps=result.steps,
                compressed_summary=result.compressed_summary,
            )

        result = await self.ask_with_memory(
            user_input,
            image_urls=image_urls,
            history=history,
            compressed_summary=compressed_summary,
            extra_system_messages=combined_system_messages,
            transient_system_messages=transient_system_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_callback=trace_callback,
        )
        return AgentRunResult(
            response=result.response,
            new_messages=persisted_skill_messages
            + result.new_messages,
            history=persisted_skill_messages + result.history,
            steps=1,
            compressed_summary=result.compressed_summary,
        )

    def _build_persistent_messages(
        self,
        user_input: str,
        *,
        image_urls: Sequence[str] | None = None,
        history: Sequence[LLMMessage] | None = None,
    ) -> list[LLMMessage]:
        persistent_messages = list(history or [])
        persistent_messages.append(
            LLMMessage(
                role="user",
                content=build_user_message_content(user_input, image_urls),
            )
        )
        return persistent_messages

    def _build_request_messages(
        self,
        persistent_messages: Sequence[LLMMessage],
        *,
        extra_system_messages: Sequence[str] | None = None,
        transient_system_messages: Sequence[str] | None = None,
        compressed_summary: str = "",
    ) -> list[LLMMessage]:
        messages: list[LLMMessage] = []
        for content in self._system_message_contents(extra_system_messages):
            messages.append(LLMMessage(role="system", content=content))

        if self.memory_support is not None:
            summary_message = self.memory_support.build_summary_message(
                compressed_summary,
            )
            if summary_message:
                messages.append(LLMMessage(role="system", content=summary_message))

        for content in transient_system_messages or []:
            if content.strip():
                messages.append(LLMMessage(role="system", content=content))

        history_prefix, current_turn_messages = _split_messages_for_transient_context(
            persistent_messages
        )
        messages.extend(history_prefix)
        messages.extend(current_turn_messages)
        return messages

    async def _prepare_request_messages(
        self,
        persistent_messages: list[LLMMessage],
        *,
        extra_system_messages: Sequence[str] | None = None,
        transient_system_messages: Sequence[str] | None = None,
        compressed_summary: str,
    ) -> tuple[list[LLMMessage], list[LLMMessage], str]:
        if self.memory_support is not None:
            prepared = await self.memory_support.compact_history(
                persistent_messages,
                system_prompt=self._system_prompt_text(extra_system_messages),
                compressed_summary=compressed_summary,
            )
            persistent_messages = prepared.messages
            compressed_summary = prepared.compressed_summary

        request_messages = self._build_request_messages(
            persistent_messages,
            extra_system_messages=extra_system_messages,
            transient_system_messages=transient_system_messages,
            compressed_summary=compressed_summary,
        )
        return request_messages, persistent_messages, compressed_summary

    async def _remember_turn(self, messages: list[LLMMessage]) -> None:
        if self.memory_support is None:
            return

        await self.memory_support.remember_turn(messages)

    def _system_message_contents(
        self,
        extra_system_messages: Sequence[str] | None = None,
    ) -> list[str]:
        contents: list[str] = []
        if self.system_prompt:
            contents.append(self.system_prompt)
        if extra_system_messages:
            contents.extend(extra_system_messages)
        return contents

    def _system_prompt_text(
        self,
        extra_system_messages: Sequence[str] | None = None,
    ) -> str:
        return "\n\n".join(self._system_message_contents(extra_system_messages))


async def _emit_trace(
    trace_callback: TraceCallback | None,
    event: str,
    **data: Any,
) -> None:
    if trace_callback is None:
        return
    await trace_callback(event, dict(data))


def _message_to_trace_dict(message: LLMMessage) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
        "content_text": message_content_to_text(message.content),
        "name": message.name,
        "tool_call_id": message.tool_call_id,
        "tool_calls": [
            {
                "id": tool_call.id,
                "name": tool_call.name,
                "arguments": tool_call.arguments,
            }
            for tool_call in message.tool_calls
        ],
    }


def _split_messages_for_transient_context(
    persistent_messages: Sequence[LLMMessage],
) -> tuple[list[LLMMessage], list[LLMMessage]]:
    last_user_index = None
    for index in range(len(persistent_messages) - 1, -1, -1):
        if persistent_messages[index].role == "user":
            last_user_index = index
            break

    if last_user_index is None:
        return list(persistent_messages), []

    return (
        list(persistent_messages[:last_user_index]),
        list(persistent_messages[last_user_index:]),
    )
