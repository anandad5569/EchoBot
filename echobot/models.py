from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal


MessageRole = Literal["system", "user", "assistant", "tool"]
MessageContentBlock = dict[str, Any]
MessageContent = str | list[MessageContentBlock]

TEXT_CONTENT_BLOCK_TYPE = "text"
IMAGE_URL_CONTENT_BLOCK_TYPE = "image_url"


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


@dataclass(slots=True)
class LLMMessage:
    role: MessageRole
    content: MessageContent = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "role": self.role,
            "content": normalize_message_content(self.content),
        }

        if self.name:
            data["name"] = self.name
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            data["tool_calls"] = [tool_call.to_dict() for tool_call in self.tool_calls]

        return data

    @property
    def content_text(self) -> str:
        return message_content_to_text(self.content)


@dataclass(slots=True)
class LLMTool:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(slots=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LLMUsage":
        if not data:
            return cls()

        prompt_tokens = _first_usage_int(data, "prompt_tokens", "input_tokens") or 0
        completion_tokens = (
            _first_usage_int(data, "completion_tokens", "output_tokens") or 0
        )
        total_tokens = _usage_int(data, "total_tokens")
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens

        prompt_cache_hit_tokens = _usage_int(data, "prompt_cache_hit_tokens")
        if prompt_cache_hit_tokens is None:
            prompt_cache_hit_tokens = (
                _nested_usage_int(data, "prompt_tokens_details", "cached_tokens")
                or _nested_usage_int(data, "input_tokens_details", "cached_tokens")
                or 0
            )

        prompt_cache_miss_tokens = _usage_int(data, "prompt_cache_miss_tokens")
        if prompt_cache_miss_tokens is None:
            prompt_cache_miss_tokens = max(
                prompt_tokens - prompt_cache_hit_tokens,
                0,
            )

        return cls(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            prompt_cache_hit_tokens=prompt_cache_hit_tokens,
            prompt_cache_miss_tokens=prompt_cache_miss_tokens,
        )

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "prompt_cache_hit_tokens": self.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": self.prompt_cache_miss_tokens,
            "prompt_cache_hit_rate_percent": self.prompt_cache_hit_rate_percent(),
        }

    def prompt_cache_hit_rate_percent(self) -> float | None:
        if self.prompt_tokens <= 0:
            return None

        rate = (self.prompt_cache_hit_tokens / self.prompt_tokens) * 100
        return round(rate, 2)


@dataclass(slots=True)
class LLMResponse:
    message: LLMMessage
    model: str
    finish_reason: str | None = None
    usage: LLMUsage = field(default_factory=LLMUsage)
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)


def _first_usage_int(data: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = _usage_int(data, key)
        if value is not None:
            return value
    return None


def _usage_int(data: dict[str, Any], key: str) -> int | None:
    if key not in data:
        return None

    try:
        return int(data[key])
    except (TypeError, ValueError):
        return None


def _nested_usage_int(
    data: dict[str, Any],
    outer_key: str,
    inner_key: str,
) -> int | None:
    nested = data.get(outer_key)
    if not isinstance(nested, dict):
        return None
    return _usage_int(nested, inner_key)


def build_user_message_content(
    text: str,
    image_urls: Sequence[str] | None = None,
) -> MessageContent:
    cleaned_text = str(text or "").strip()
    cleaned_image_urls = [
        str(url).strip()
        for url in image_urls or []
        if str(url).strip()
    ]
    if not cleaned_image_urls:
        return cleaned_text

    content_blocks: list[MessageContentBlock] = []
    if cleaned_text:
        content_blocks.append(
            {
                "type": TEXT_CONTENT_BLOCK_TYPE,
                "text": cleaned_text,
            }
        )
    for image_url in cleaned_image_urls:
        content_blocks.append(
            {
                "type": IMAGE_URL_CONTENT_BLOCK_TYPE,
                "image_url": {
                    "url": image_url,
                },
            }
        )
    return content_blocks


def normalize_message_content(value: Any) -> MessageContent:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return str(value or "")

    blocks: list[MessageContentBlock] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        blocks.append(dict(item))
    return blocks


def message_content_to_text(content: MessageContent) -> str:
    if isinstance(content, str):
        return content

    text_parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue

        block_type = str(block.get("type", "")).strip()
        if block_type == TEXT_CONTENT_BLOCK_TYPE:
            text = str(block.get("text", "")).strip()
            if text:
                text_parts.append(text)
            continue

        if block_type == IMAGE_URL_CONTENT_BLOCK_TYPE:
            text_parts.append("[image]")
            continue

        if block_type:
            text_parts.append(f"[{block_type}]")

    return "\n\n".join(part for part in text_parts if part)


def message_content_image_urls(content: MessageContent) -> list[str]:
    if isinstance(content, str):
        return []

    image_urls: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if str(block.get("type", "")).strip() != IMAGE_URL_CONTENT_BLOCK_TYPE:
            continue

        image_url = block.get("image_url")
        if not isinstance(image_url, dict):
            continue

        url = str(image_url.get("url", "")).strip()
        if url:
            image_urls.append(url)

    return image_urls


def is_message_content_empty(content: MessageContent) -> bool:
    if isinstance(content, str):
        return not content.strip()

    return len(message_content_image_urls(content)) == 0 and not message_content_to_text(
        content
    ).strip()
