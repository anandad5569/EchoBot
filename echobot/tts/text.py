from __future__ import annotations

_EMOJI_CODEPOINTS = {
    0x200D,  # zero width joiner
    0x20E3,  # combining enclosing keycap
    0xFE0E,  # variation selector-15
    0xFE0F,  # variation selector-16
}

_EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F1E6, 0x1F1FF),  # flags
    (0x1F300, 0x1F5FF),  # symbols and pictographs
    (0x1F600, 0x1F64F),  # emoticons
    (0x1F680, 0x1F6FF),  # transport and map
    (0x1F700, 0x1F77F),  # alchemical symbols
    (0x1F780, 0x1F7FF),  # geometric shapes extended
    (0x1F800, 0x1F8FF),  # supplemental arrows-c
    (0x1F900, 0x1F9FF),  # supplemental symbols and pictographs
    (0x1FA70, 0x1FAFF),  # symbols and pictographs extended-a
    (0x2600, 0x26FF),  # miscellaneous symbols
    (0x2700, 0x27BF),  # dingbats
)


def normalize_text_for_tts(text: str) -> str:
    cleaned_text = "".join(
        " " if _is_emoji_character(character) else character
        for character in text
    )
    return " ".join(cleaned_text.split())


def _is_emoji_character(character: str) -> bool:
    codepoint = ord(character)
    if codepoint in _EMOJI_CODEPOINTS:
        return True
    return any(start <= codepoint <= end for start, end in _EMOJI_RANGES)
