from __future__ import annotations


DEFAULT_LIP_SYNC_PARAMETER_IDS = [
    "ParamMouthOpenY",
    "PARAM_MOUTH_OPEN_Y",
    "MouthOpenY",
]
DEFAULT_MOUTH_FORM_PARAMETER_IDS = [
    "ParamMouthForm",
    "PARAM_MOUTH_FORM",
    "MouthForm",
]

LIVE2D_SOURCE_WORKSPACE = "workspace"
LIVE2D_SOURCE_BUILTIN = "builtin"
LIVE2D_ANNOTATIONS_FILENAME = "echobot.live2d.json"
LIVE2D_AUTO_MOTION_GROUP = "EchoBotAuto"
LIVE2D_IDLE_MOTION_GROUP = "EchoBotIdle"

ALLOWED_LIVE2D_UPLOAD_SUFFIXES = {
    ".json",
    ".moc3",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".avif",
    ".wav",
    ".mp3",
    ".ogg",
    ".m4a",
}
MAX_LIVE2D_UPLOAD_FILES = 512
MAX_LIVE2D_UPLOAD_TOTAL_BYTES = 200 * 1024 * 1024

SUPPORTED_HOTKEY_ACTIONS = {
    "ToggleExpression",
    "TriggerAnimation",
    "RemoveAllExpressions",
}

HOTKEY_TOKEN_MAP = {
    "alt": "alt",
    "leftalt": "alt",
    "rightalt": "alt",
    "shift": "shift",
    "leftshift": "shift",
    "rightshift": "shift",
    "control": "control",
    "ctrl": "control",
    "leftcontrol": "control",
    "rightcontrol": "control",
    "command": "meta",
    "leftcommand": "meta",
    "rightcommand": "meta",
    "win": "meta",
    "leftwin": "meta",
    "rightwin": "meta",
    "meta": "meta",
    "tab": "tab",
    "space": "space",
    "spacebar": "space",
    "enter": "enter",
    "return": "enter",
    "escape": "escape",
    "esc": "escape",
    "backspace": "backspace",
    "delete": "delete",
    "insert": "insert",
    "home": "home",
    "end": "end",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "arrowup": "arrowup",
    "uparrow": "arrowup",
    "arrowdown": "arrowdown",
    "downarrow": "arrowdown",
    "arrowleft": "arrowleft",
    "leftarrow": "arrowleft",
    "arrowright": "arrowright",
    "rightarrow": "arrowright",
    "minus": "minus",
    "equal": "equal",
    "comma": "comma",
    "period": "period",
    "slash": "slash",
    "backslash": "backslash",
    "semicolon": "semicolon",
    "quote": "quote",
    "backquote": "backquote",
    "capslock": "capslock",
}
