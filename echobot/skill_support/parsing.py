from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from ..models import LLMMessage, message_content_to_text
from .models import Skill


ACTIVE_SKILL_PATTERN = re.compile(r'<active_skill name="([^"]+)">')
LEGACY_SKILL_NAME_PATTERN = re.compile(r"(?m)^Skill name:\s*(.+?)\s*$")
MULTILINE_FRONTMATTER_MARKERS = {"|", "|-", "|+", ">", ">-", ">+"}


def parse_skill_file(path: str | Path) -> Skill:
    skill_file = Path(path)
    content = skill_file.read_text(encoding="utf-8-sig")
    frontmatter_lines, body = _split_frontmatter(content)
    name = _read_frontmatter_value(frontmatter_lines, "name")
    description = _read_frontmatter_value(
        frontmatter_lines,
        "description",
        allow_multiline=True,
    )

    if not name:
        raise ValueError("Missing name in frontmatter")
    if not description:
        raise ValueError("Missing description in frontmatter")

    return Skill(
        name=name,
        description=description,
        directory=skill_file.parent,
        skill_file=skill_file,
        body=body.strip(),
        frontmatter="\n".join(frontmatter_lines).strip(),
    )


def extract_explicit_skill_tokens(text: str) -> list[str]:
    return re.findall(
        r"(?:^|[\s(])(?:/|\$)([a-z0-9_-]{1,64})(?=$|[\s),.!?])",
        text,
    )


def extract_active_skill_names_from_history(
    history: Sequence[LLMMessage] | None,
    *,
    available_skill_names: set[str],
) -> list[str]:
    if not history:
        return []

    found_names: list[str] = []
    for message in history:
        for skill_name in _extract_active_skill_names_from_message(message):
            if skill_name in available_skill_names and skill_name not in found_names:
                found_names.append(skill_name)

    return found_names


def _split_frontmatter(content: str) -> tuple[list[str], str]:
    normalized = content.replace("\r\n", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("Invalid SKILL.md frontmatter")

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        raise ValueError("Invalid SKILL.md frontmatter")

    frontmatter_lines = lines[1:end_index]
    body = "\n".join(lines[end_index + 1 :])
    return frontmatter_lines, body


def _read_frontmatter_value(
    frontmatter_lines: Sequence[str],
    key: str,
    *,
    allow_multiline: bool = False,
) -> str:
    index = 0
    while index < len(frontmatter_lines):
        entry = _parse_frontmatter_entry(frontmatter_lines[index])
        if entry is None:
            index += 1
            continue

        current_key, raw_value = entry
        if current_key != key:
            index += 1
            continue

        if raw_value in MULTILINE_FRONTMATTER_MARKERS:
            if not allow_multiline:
                raise ValueError(f"{key} must be a single-line value")
            return _read_multiline_frontmatter_value(
                frontmatter_lines,
                start_index=index + 1,
            )

        return _strip_optional_quotes(raw_value)

    return ""


def _parse_frontmatter_entry(line: str) -> tuple[str, str] | None:
    if not line.strip():
        return None
    if line.startswith((" ", "\t")):
        return None
    if ":" not in line:
        return None

    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _read_multiline_frontmatter_value(
    frontmatter_lines: Sequence[str],
    *,
    start_index: int,
) -> str:
    parts: list[str] = []
    index = start_index
    while index < len(frontmatter_lines):
        line = frontmatter_lines[index]
        if line.startswith((" ", "\t")):
            cleaned = line.strip()
            if cleaned:
                parts.append(cleaned)
            index += 1
            continue
        if not line.strip():
            index += 1
            continue
        break

    return " ".join(parts).strip()


def _strip_optional_quotes(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1]

    return cleaned.strip()


def _extract_active_skill_names_from_message(message: LLMMessage) -> list[str]:
    if message.role == "system":
        return _extract_active_skill_names_from_text(
            message_content_to_text(message.content),
        )

    if message.role == "tool":
        return _extract_active_skill_names_from_tool_payload(
            message_content_to_text(message.content),
        )

    return []


def _extract_active_skill_names_from_text(text: str) -> list[str]:
    names: list[str] = []

    for match in ACTIVE_SKILL_PATTERN.findall(text):
        cleaned_name = match.strip()
        if cleaned_name and cleaned_name not in names:
            names.append(cleaned_name)

    for match in LEGACY_SKILL_NAME_PATTERN.findall(text):
        cleaned_name = match.strip()
        if cleaned_name and cleaned_name not in names:
            names.append(cleaned_name)

    return names


def _extract_active_skill_names_from_tool_payload(text: str) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, dict) or not payload.get("ok"):
        return []

    result = payload.get("result")
    if not isinstance(result, dict):
        return []

    names: list[str] = []
    skill_name = result.get("name")
    if isinstance(skill_name, str):
        if result.get("kind") == "skill_activation":
            names.append(skill_name)
        elif "directory" in result and "content" in result:
            names.append(skill_name)

    return names
