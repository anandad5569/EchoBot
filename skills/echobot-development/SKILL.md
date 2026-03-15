---
name: echobot-development
description: Maintain and extend the EchoBot codebase. Use when changing this repository's agent core, LLM providers, tool system, skill runtime, channels, gateway, orchestration, runtime/session management, memory, scheduling, ASR/TTS, CLI, FastAPI app, or tests, and whenever the user asks to add, refactor, debug, or review EchoBot implementation details.
---

# EchoBot Development

Work directly in the existing project structure.

## Rules

- Read `AGENTS.md` before large changes; keep code beginner-friendly and follow its principles.
- Reuse the shared `AgentCore` instead of duplicating LLM logic elsewhere.
- Never block the event loop — use `asyncio.to_thread(...)` for blocking I/O.
- Prefer `pathlib` and the standard library.
- Use `json.dumps(..., ensure_ascii=False)` for all JSON output.
- Add or update tests under `tests/` whenever behavior changes.
- Validate new or changed skills with `echobot/skills/skill-creator/scripts/quick_validate.py`.

## Main code areas

| Area | Path | Purpose |
|---|---|---|
| Agent core | `echobot/agent.py` | `AgentCore` — bare LLM invocation and tool loop |
| Data models | `echobot/models.py` | Shared `LLMMessage`, `LLMResponse`, `LLMTool` |
| Config | `echobot/config.py` | Env loading and runtime logging |
| Providers | `echobot/providers/` | LLM provider abstractions; `openai_compatible.py` |
| Tools | `echobot/tools/` | `BaseTool`, `ToolRegistry`; builtins: filesystem, shell, web, memory, cron |
| Skill support | `echobot/skill_support/` | Skill discovery, activation, prompting, `SkillRegistry` |
| Runtime | `echobot/runtime/` | `SessionStore`, `ChatSession`, `SessionAgentRunner`, `AgentTraceStore`, system prompt, `bootstrap.py` (`RuntimeContext`) |
| Orchestration | `echobot/orchestration/` | `RoleCardRegistry`, `RoleplayEngine`, `DecisionEngine`, `ConversationCoordinator`, route modes |
| Channels | `echobot/channels/` | `ChannelManager`, `MessageBus`, channel registry, platform adapters (console, …) |
| Gateway | `echobot/gateway/` | Message delivery, session routing |
| Memory | `echobot/memory/` | `ReMeLightSupport` — persistent conversation memory |
| Scheduling | `echobot/scheduling/` | `CronService` (cron jobs), `HeartbeatService` (periodic ticks) |
| ASR | `echobot/asr/` | Speech-to-text service and model manager |
| TTS | `echobot/tts/` | Text-to-speech service; providers: edge, kokoro |
| CLI | `echobot/cli/` | Entrypoints: `chat`, `gateway`, `app`, `main` |
| App | `echobot/app/` | FastAPI web app, routers, services |

## Runtime bootstrap

`RuntimeContext` (in `echobot/runtime/bootstrap.py`) wires everything together:
it creates the provider, `AgentCore`, `SessionStore`, `ToolRegistry`, `SkillRegistry`, `CronService`, `HeartbeatService`, and `SessionAgentRunner` from a single `RuntimeOptions` dataclass.
All CLI entrypoints and the FastAPI app start from `bootstrap.py`.

## Validation

Run `python -m unittest discover -s tests -v` after changes.

Read `references/architecture.md` for a deeper map of how the parts fit together.
