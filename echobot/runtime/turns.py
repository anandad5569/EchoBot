from __future__ import annotations

from ..agent import AgentCore, AgentRunResult, TraceCallback
from ..models import LLMMessage
from ..skill_support import SkillRegistry
from ..tools import ToolRegistry
from collections.abc import Sequence


async def run_agent_turn(
    agent: AgentCore,
    prompt: str,
    history: list[LLMMessage],
    *,
    image_urls: Sequence[str] | None = None,
    compressed_summary: str,
    skill_registry: SkillRegistry | None,
    tool_registry: ToolRegistry | None,
    extra_system_messages: Sequence[str] | None = None,
    transient_system_messages: Sequence[str] | None = None,
    temperature: float | None,
    max_tokens: int | None,
    trace_callback: TraceCallback | None = None,
) -> AgentRunResult:
    if skill_registry is not None:
        return await agent.ask_with_skills(
            prompt,
            image_urls=image_urls,
            history=history,
            compressed_summary=compressed_summary,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
            extra_system_messages=extra_system_messages,
            transient_system_messages=transient_system_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_callback=trace_callback,
        )

    if tool_registry is not None:
        return await agent.ask_with_tools(
            prompt,
            image_urls=image_urls,
            history=history,
            compressed_summary=compressed_summary,
            tool_registry=tool_registry,
            extra_system_messages=extra_system_messages,
            transient_system_messages=transient_system_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_callback=trace_callback,
        )

    return await agent.ask_with_memory(
        prompt,
        image_urls=image_urls,
        history=history,
        compressed_summary=compressed_summary,
        extra_system_messages=extra_system_messages,
        transient_system_messages=transient_system_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        trace_callback=trace_callback,
    )
