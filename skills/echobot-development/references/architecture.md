# Architecture

## Core flow

1. A CLI entrypoint (`echobot/cli/`) or the FastAPI app (`echobot/app/`) calls `bootstrap.py`.
2. `bootstrap.py` reads `RuntimeOptions`, loads env/config, and builds a `RuntimeContext` containing:
   - `AgentCore` (wraps an `LLMProvider`)
   - `SessionStore` + `ChatSession` (conversation history)
   - `ToolRegistry` (built-in tools)
   - `SkillRegistry` (project and user skills)
   - `CronService` + optional `HeartbeatService`
   - `SessionAgentRunner` (executes one conversation turn)
3. Inbound messages arrive via a `Channel` (console, webhook, …), are routed through the `ChannelManager` and `MessageBus`, and dispatched to a session.
4. `SessionAgentRunner.run(...)` calls `AgentCore.ask(...)` with tools and skill context injected.
5. `AgentCore` drives the LLM + tool loop; results are returned as `AgentRunResult`.
6. Outbound responses are put back on `MessageBus` and dispatched by the channel's outbound path.

## Agent core

- `echobot/agent.py`: `AgentCore` holds a provider, optional system prompt, and optional memory support. `ask(...)` drives one LLM call; `ask_with_tools(...)` runs the multi-step tool loop.
- `echobot/models.py`: canonical data types shared across the codebase (`LLMMessage`, `LLMResponse`, `LLMTool`).

## Tool system

- `echobot/tools/base.py`: `BaseTool`, `ToolRegistry`, tool execution helpers.
- `echobot/tools/builtin.py`: file access, web fetch, shell commands.
- `echobot/tools/memory.py`, `cron.py`: memory search and cron management tools.

## Skill system

- `echobot/skill_support/registry.py`: discovers skills from `skills/`, `.<client>/skills/`, `.agents/skills/`, `echobot/skills/`, and user-level mirrors.
- Each skill is a folder with a required `SKILL.md` (frontmatter: `name`, `description`).
- The runtime adds a skill catalog to the system context; explicit `/skill-name` or `$skill-name` activates immediately; otherwise the model calls `activate_skill`.

## Runtime / sessions

- `echobot/runtime/sessions.py`: `ChatSession` (message history) and `SessionStore`.
- `echobot/runtime/session_runner.py`: `SessionAgentRunner` — executes one turn, injecting tools and skill context.
- `echobot/runtime/system_prompt.py`: builds the default system prompt.
- `echobot/runtime/agent_traces.py`: `AgentTraceStore` — records per-turn traces for debugging.
- `echobot/runtime/bootstrap.py`: `RuntimeContext` + `RuntimeOptions` — the single assembly point.

## Orchestration

- `echobot/orchestration/roles.py`: `RoleCard`, `RoleCardRegistry` — named persona definitions.
- `echobot/orchestration/roles.py` (default): built-in cat-girl assistant persona.
- `echobot/orchestration/route_modes.py`: routing mode selection logic.
- `echobot/orchestration/commands.py`: session command dispatch.
- `echobot/orchestration/role_command_runtime.py`: per-session role + command runtime.

## Channels

- `echobot/channels/manager.py`: `ChannelManager` — starts/stops all channel tasks and the outbound dispatcher.
- `echobot/channels/bus.py`: `MessageBus` — async pub/sub between channels and the session layer.
- `echobot/channels/registry.py`: channel type registry.
- `echobot/channels/platforms/console.py`: stdin/stdout channel (used by CLI chat).

## Gateway

- `echobot/gateway/route_sessions.py`: maps incoming messages to sessions.
- `echobot/gateway/delivery.py`: outbound message delivery.

## Memory

- `echobot/memory/`: `ReMeLightSupport` wraps a lightweight retrieval-augmented memory store.
- Enabled by default; disable with `--no-memory`.

## Scheduling

- `echobot/scheduling/cron/service.py`: `CronService` — stores and fires cron jobs.
- `echobot/scheduling/heartbeat/service.py`: `HeartbeatService` — sends periodic tick events to a session.

## ASR / TTS

- `echobot/asr/`: `ASRService` + `ModelManager` — speech-to-text (local models via sherpa-onnx).
- `echobot/tts/`: `TTSService` + `TTSFactory`; providers: `edge` (Microsoft Edge TTS), `kokoro` (local Kokoro model).

## FastAPI app

- `echobot/app/create_app.py`: creates the FastAPI instance and registers routers.
- Routers: `health`, `channels`, `sessions`, `roles`, `cron`, `heartbeat`, `web`.
- `echobot/app/runtime.py`: shares the `RuntimeContext` with the app.

## Tests

- `tests/test_agent.py`: provider and `AgentCore` behavior.
- `tests/test_tools.py`: tool execution.
- `tests/test_skill_support.py`: skill discovery and activation.
