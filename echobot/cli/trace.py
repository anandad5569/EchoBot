from __future__ import annotations

import json

from ..models import LLMMessage, message_content_to_text


SKILL_TOOL_NAMES = {
    "activate_skill",
    "list_skill_resources",
    "read_skill_resource",
}


def print_tool_trace(messages: list[LLMMessage]) -> None:
    tool_name_by_call_id: dict[str, str] = {}

    for message in messages:
        if message.role == "assistant" and message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name_by_call_id[tool_call.id] = tool_call.name
                print(build_tool_call_trace_title(tool_call.name))
                print(format_json_text(tool_call.arguments))
                print()
            continue

        if message.role == "tool" and message.tool_call_id:
            tool_name = tool_name_by_call_id.get(message.tool_call_id, "unknown-tool")
            content = message_content_to_text(message.content)
            print(build_tool_result_trace_title(tool_name, content))
            print(format_json_text(content))
            print()


def build_tool_call_trace_title(tool_name: str) -> str:
    if tool_name in SKILL_TOOL_NAMES:
        return f"[skill-call] {tool_name}"

    return f"[tool-call] {tool_name}"


def build_tool_result_trace_title(tool_name: str, content: str) -> str:
    payload = parse_json_text(content)
    if not isinstance(payload, dict):
        return f"[tool-result] {tool_name}"

    result = payload.get("result")
    if not isinstance(result, dict):
        return f"[tool-result] {tool_name}"

    kind = result.get("kind")
    skill_name = str(result.get("name", "")).strip()

    if tool_name == "activate_skill" and kind == "skill_activation":
        suffix = " (already active)" if result.get("already_active") else ""
        return f"[skill-activate] {skill_name or 'unknown-skill'}{suffix}"

    if tool_name == "list_skill_resources" and kind == "skill_resource_list":
        folder_name = str(result.get("folder", "all")).strip() or "all"
        return f"[skill-resources] {skill_name or 'unknown-skill'} ({folder_name})"

    if tool_name == "read_skill_resource" and kind == "skill_resource_content":
        resource_path = str(result.get("path", "")).strip()
        if resource_path:
            return f"[skill-resource] {skill_name or 'unknown-skill'} | {resource_path}"
        return f"[skill-resource] {skill_name or 'unknown-skill'}"

    return f"[tool-result] {tool_name}"


def format_json_text(text: str) -> str:
    parsed = parse_json_text(text)
    if parsed is None:
        return text

    return json.dumps(parsed, ensure_ascii=False, indent=2)


def parse_json_text(text: str) -> dict[str, object] | list[object] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, (dict, list)):
        return parsed

    return None
