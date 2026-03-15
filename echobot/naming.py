from __future__ import annotations

_ALLOWED_NAME_PUNCTUATION = "-_"


def normalize_name_token(value: str) -> str:
    parts = str(value or "").strip().lower().split()
    cleaned = "-".join(parts)
    return "".join(
        character
        for character in cleaned
        if _is_allowed_name_character(character)
    )


def _is_allowed_name_character(character: str) -> bool:
    return character.isalnum() or character in _ALLOWED_NAME_PUNCTUATION
