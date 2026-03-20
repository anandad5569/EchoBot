# Architecture

Read this file when a change crosses module boundaries or when you need to trace a request end to end.

## Top-level entrypoints

- `echobot/cli/main.py` is the unified CLI. With no subcommand it falls back to `chat`.
- `echobot/cli/chat.py`, `echobot/cli/gateway.py`, and `echobot/cli/app.py` all build the shared runtime through `echobot/runtime/bootstrap.py`.
- `echobot/app/create_app.py` builds the FastAPI app and serves the browser UI from `echobot/app/web/`.

## Shared runtime assembly

`build_runtime_context(...)` in `echobot/runtime/bootstrap.py` is the single assembly point. It creates:

- provider instances
- `AgentCore`
- session stores for user sessions and agent sessions
- a `ToolRegistry` factory
- `SkillRegistry`
- `CronService` and optional `HeartbeatService`
- `SessionAgentRunner`
- `RoleCardRegistry`
- `DecisionEngine`
- `RoleplayEngine`
- `ConversationCoordinator`
- `AgentTraceStore`

If a feature should exist in chat, gateway, and app, wire it here once.

## User turn flow

1. A CLI command, gateway event, or API handler resolves a session and calls the coordinator.
2. `ConversationCoordinator.handle_user_turn_stream(...)` loads session state, role, and route mode.
3. `DecisionEngine.decide(...)` picks `chat` or `agent`.
4. Chat route goes straight to `RoleplayEngine.stream_chat_reply(...)`.
5. Agent route optionally creates a short delegated acknowledgement, stores visible history, and starts a background job.
6. The background job calls `SessionAgentRunner.run_prompt(...)`.
7. `run_agent_turn(...)` injects base tools and skill tools into `AgentCore`.
8. The raw agent result is wrapped back through `RoleplayEngine.present_agent_result(...)`, `present_agent_failure(...)`, or the scheduled-task presenters before it is shown to the user.

## Separation of concerns

### Decision layer

- `echobot/orchestration/decision.py`
- Rule-based routing handles obvious tool, workspace, memory, and scheduling requests.
- The lightweight decider LLM handles ambiguous turns.
- Route modes are defined in `echobot/orchestration/route_modes.py`.

### Roleplay layer

- `echobot/orchestration/roleplay.py`
- Only uses visible conversation context plus explicit system instructions.
- Must not inspect files, tools, memory, or schedules directly.
- Presents chat replies, delegated acknowledgements, final agent results, failures, and scheduled notifications.

### Agent layer

- `echobot/agent.py`
- `echobot/runtime/session_runner.py`
- `echobot/runtime/turns.py`
- Owns tool use, skill use, file access, memory lookup, scheduling changes, and other background work.

## Skills and tools

- `SkillRegistry.discover(...)` searches project skills first, then built-in and user roots.
- Skill activation can happen via explicit `/skill-name` or `$skill-name`, or through the `activate_skill` tool.
- Bundled resource files stay unloaded until the agent calls `list_skill_resources` or `read_skill_resource`.
- Base tools come from `create_basic_tool_registry(...)` in `echobot/tools/builtin.py`.

## Session and state files

- Sessions: `.echobot/sessions/`
- Agent-side session history: `.echobot/agent_sessions/`
- Agent traces: `.echobot/agent_traces/`
- Cron store: `.echobot/cron/jobs.json`
- Heartbeat file: `.echobot/HEARTBEAT.md`
- Runtime settings: `.echobot/runtime_settings.json`

## Current module map

- `echobot/commands/`: user command parsing and execution for CLI and gateway flows
- `echobot/channels/`: channel configs, message bus, manager, and platform adapters
- `echobot/gateway/`: inbound route-to-session mapping and outbound delivery
- `echobot/app/routers/`: HTTP endpoints for chat, sessions, roles, cron, heartbeat, channels, and web
- `echobot/app/services/`: server-side helpers used by the API layer
- `echobot/app/web/`: static browser UI assets
- `echobot/memory/`: ReMeLight support
- `echobot/asr/` and `echobot/tts/`: speech services

## Test map

- `tests/test_skill_support.py`: skill discovery, activation, and lazy resource loading
- `tests/test_agent.py` and `tests/test_tools.py`: agent loop and tool execution
- `tests/test_decision.py`, `tests/test_roleplay.py`, and `tests/test_coordinator.py`: routing and orchestration
- `tests/test_commands.py`, `tests/test_gateway.py`, and `tests/test_app_api.py`: command and API surfaces
- `tests/test_sessions.py`, `tests/test_scheduler.py`, and `tests/test_agent_traces.py`: persisted runtime state
