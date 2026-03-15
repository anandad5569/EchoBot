from __future__ import annotations

from ...base import VoiceOption

DEFAULT_KOKORO_VOICE = "zf_001"

KOKORO_SPEAKER_NAMES = {
    0: "af_maple",
    1: "af_sol",
    2: "bf_vale",
    3: "zf_001",
    4: "zf_002",
    5: "zf_003",
    6: "zf_004",
    7: "zf_005",
    8: "zf_006",
    9: "zf_007",
    10: "zf_008",
    11: "zf_017",
    12: "zf_018",
    13: "zf_019",
    14: "zf_021",
    15: "zf_022",
    16: "zf_023",
    17: "zf_024",
    18: "zf_026",
    19: "zf_027",
    20: "zf_028",
    21: "zf_032",
    22: "zf_036",
    23: "zf_038",
    24: "zf_039",
    25: "zf_040",
    26: "zf_042",
    27: "zf_043",
    28: "zf_044",
    29: "zf_046",
    30: "zf_047",
    31: "zf_048",
    32: "zf_049",
    33: "zf_051",
    34: "zf_059",
    35: "zf_060",
    36: "zf_067",
    37: "zf_070",
    38: "zf_071",
    39: "zf_072",
    40: "zf_073",
    41: "zf_074",
    42: "zf_075",
    43: "zf_076",
    44: "zf_077",
    45: "zf_078",
    46: "zf_079",
    47: "zf_083",
    48: "zf_084",
    49: "zf_085",
    50: "zf_086",
    51: "zf_087",
    52: "zf_088",
    53: "zf_090",
    54: "zf_092",
    55: "zf_093",
    56: "zf_094",
    57: "zf_099",
    58: "zm_009",
    59: "zm_010",
    60: "zm_011",
    61: "zm_012",
    62: "zm_013",
    63: "zm_014",
    64: "zm_015",
    65: "zm_016",
    66: "zm_020",
    67: "zm_025",
    68: "zm_029",
    69: "zm_030",
    70: "zm_031",
    71: "zm_033",
    72: "zm_034",
    73: "zm_035",
    74: "zm_037",
    75: "zm_041",
    76: "zm_045",
    77: "zm_050",
    78: "zm_052",
    79: "zm_053",
    80: "zm_054",
    81: "zm_055",
    82: "zm_056",
    83: "zm_057",
    84: "zm_058",
    85: "zm_061",
    86: "zm_062",
    87: "zm_063",
    88: "zm_064",
    89: "zm_065",
    90: "zm_066",
    91: "zm_068",
    92: "zm_069",
    93: "zm_080",
    94: "zm_081",
    95: "zm_082",
    96: "zm_089",
    97: "zm_091",
    98: "zm_095",
    99: "zm_096",
    100: "zm_097",
    101: "zm_098",
    102: "zm_100",
}

KOKORO_SPEAKER_IDS = {
    speaker_name: speaker_id
    for speaker_id, speaker_name in KOKORO_SPEAKER_NAMES.items()
}


def normalize_kokoro_voice_name(
    voice_name: str,
    *,
    fallback: str = DEFAULT_KOKORO_VOICE,
) -> str:
    normalized_voice_name = voice_name.strip()
    if normalized_voice_name in KOKORO_SPEAKER_IDS:
        return normalized_voice_name
    return fallback


def speaker_id_for_voice(voice_name: str) -> int:
    normalized_voice_name = voice_name.strip()
    if normalized_voice_name in KOKORO_SPEAKER_IDS:
        return KOKORO_SPEAKER_IDS[normalized_voice_name]

    try:
        speaker_id = int(normalized_voice_name)
    except ValueError as exc:
        raise ValueError(f"Unknown Kokoro voice: {voice_name}") from exc

    if speaker_id not in KOKORO_SPEAKER_NAMES:
        raise ValueError(f"Unknown Kokoro voice: {voice_name}")
    return speaker_id


def kokoro_voice_options() -> list[VoiceOption]:
    voices: list[VoiceOption] = []
    for speaker_id, speaker_name in KOKORO_SPEAKER_NAMES.items():
        locale, gender, display_prefix = _voice_metadata_for_name(speaker_name)
        voices.append(
            VoiceOption(
                name=f"{speaker_name} ({speaker_id})",
                short_name=speaker_name,
                locale=locale,
                gender=gender,
                display_name=f"{display_prefix} {speaker_name}",
            )
        )
    return voices


def _voice_metadata_for_name(speaker_name: str) -> tuple[str, str, str]:
    prefix = speaker_name.split("_", 1)[0]
    if prefix == "af":
        return "en-US", "Female", "American"
    if prefix == "bf":
        return "en-GB", "Female", "British"
    if prefix == "zf":
        return "zh-CN", "Female", "Chinese"
    if prefix == "zm":
        return "zh-CN", "Male", "Chinese"
    return "", "", "Kokoro"
