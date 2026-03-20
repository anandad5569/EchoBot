---
name: echobot-development
description: Use when working on the EchoBot repository itself and changing agent behavior, providers, tools, skill runtime, session or runtime wiring, routing, roleplay, channels, gateway, web API, web UI, scheduling, memory, ASR or TTS, commands, or tests. Also use for debugging, refactoring, reviewing, or extending EchoBot implementation details.
---

# EchoBot Development

Work inside the current repository layout. Favor small, readable changes that keep shared runtime paths unified.

## Start here

- Read `AGENTS.md` before large changes. Keep code beginner-friendly, prefer `pathlib`, and avoid blocking the event loop.
- Reuse the shared runtime assembly in `echobot/runtime/bootstrap.py`. Do not create separate business logic for CLI, gateway, and app entrypoints.
- Prefer extending existing registries and services over adding parallel code paths.
- Keep user-visible roleplay behavior separate from background agent execution.

## Practical workflow

1. Locate the real entrypoint for the behavior you are changing.
2. Trace the flow through `bootstrap.py`, `ConversationCoordinator`, `SessionAgentRunner`, and the relevant subsystem.
3. Make the smallest coherent change.
4. Run focused tests first, then broader tests if the change crosses subsystem boundaries.

## Shared runtime rules

- Blocking file, network, or CPU-heavy work must stay off the event loop. Use `asyncio.to_thread(...)` or an executor when needed.
- Keep one source of truth for sessions, tools, skills, and scheduling. If a feature belongs in `RuntimeContext`, wire it there once and reuse it.
- Use `json.dumps(..., ensure_ascii=False)` for JSON output.
- When behavior changes, update or add tests under `tests/`.
- When changing a project skill, validate it with `python -X utf8 echobot/skills/skill-creator/scripts/quick_validate.py skills/<skill-name>`.

## Key code areas

| Area | Path | Purpose |
|---|---|---|
| Agent loop | `echobot/agent.py` | `AgentCore` request flow and tool loop |
| Providers | `echobot/providers/` | Provider abstraction and OpenAI-compatible settings |
| Tools | `echobot/tools/` | Base registry plus filesystem, shell, web, memory, and cron tools |
| Skills | `echobot/skill_support/` | Discovery, parsing, explicit activation, and lazy resource tools |
| Runtime | `echobot/runtime/` | Bootstrap, sessions, traces, turn execution, and runtime settings |
| Orchestration | `echobot/orchestration/` | Decision layer, roleplay layer, coordinator, jobs, and route modes |
| Commands | `echobot/commands/` | CLI and gateway command parsing and dispatch |
| Channels | `echobot/channels/` | Bus, manager, channel configs, and console/qq/telegram adapters |
| Gateway | `echobot/gateway/` | Route-to-session mapping and outbound delivery |
| App | `echobot/app/` | FastAPI app, routers, services, and browser assets |
| Memory | `echobot/memory/` | ReMeLight integration |
| Scheduling | `echobot/scheduling/` | Cron and heartbeat services |
| Speech | `echobot/asr/`, `echobot/tts/` | Local ASR and TTS backends |
| Tests | `tests/` | Focused regression coverage by subsystem |

## Focused tests

- Skills or skill runtime: `python -m unittest tests.test_skill_support tests.test_chat_agent -v`
- Agent and tools: `python -m unittest tests.test_agent tests.test_tools -v`
- Routing and roleplay: `python -m unittest tests.test_decision tests.test_roleplay tests.test_coordinator -v`
- Gateway, channels, or API: `python -m unittest tests.test_gateway tests.test_app_api tests.test_commands -v`
- Sessions, scheduler, or traces: `python -m unittest tests.test_sessions tests.test_scheduler tests.test_agent_traces -v`

Read `references/architecture.md` before touching more than one subsystem or any shared runtime path.
