from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..agent import AgentCore
from ..config import configure_runtime_logging, load_env_file
from ..memory import ReMeLightSettings, ReMeLightSupport
from ..orchestration import (
    ConversationCoordinator,
    DecisionEngine,
    RoleCardRegistry,
    RoleplayEngine,
)
from ..providers.openai_compatible import (
    OpenAICompatibleProvider,
    OpenAICompatibleSettings,
)
from ..runtime.session_runner import SessionAgentRunner
from ..runtime.agent_traces import AgentTraceStore
from ..runtime.sessions import ChatSession, SessionStore
from ..runtime.system_prompt import build_default_system_prompt
from ..scheduling.cron import CronService
from ..scheduling.heartbeat import HeartbeatService
from ..skill_support import SkillRegistry
from ..tools import ToolRegistry, create_basic_tool_registry


ToolRegistryFactory = Callable[[str, bool], ToolRegistry | None]


@dataclass(slots=True)
class RuntimeOptions:
    env_file: str = ".env"
    workspace: Path | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    no_tools: bool = False
    no_skills: bool = False
    no_memory: bool = False
    no_heartbeat: bool = False
    heartbeat_interval: int | None = None
    session: str | None = None
    new_session: str | None = None


@dataclass(slots=True)
class RuntimeContext:
    workspace: Path
    agent: AgentCore
    session_store: SessionStore
    agent_session_store: SessionStore
    session: ChatSession | None
    tool_registry: ToolRegistry | None
    skill_registry: SkillRegistry | None
    cron_service: CronService
    heartbeat_service: HeartbeatService | None
    session_runner: SessionAgentRunner
    coordinator: ConversationCoordinator
    role_registry: RoleCardRegistry
    memory_support: ReMeLightSupport | None
    heartbeat_file_path: Path
    heartbeat_interval_seconds: int
    tool_registry_factory: ToolRegistryFactory


def build_runtime_context(
    options: RuntimeOptions,
    *,
    load_session_state: bool,
) -> RuntimeContext:
    workspace = (options.workspace or Path(".")).resolve()
    env_file_path = _resolve_runtime_path(workspace, options.env_file)
    load_env_file(str(env_file_path))
    configure_runtime_logging()
    lightweight_max_tokens = _env_int("ECHOBOT_LIGHTWEIGHT_MAX_TOKENS", 4096)
    settings = OpenAICompatibleSettings.from_env()
    decider_provider = _build_provider_from_env(
        prefix="DECIDER_LLM_",
        fallback_settings=settings,
    )
    role_provider = _build_provider_from_env(
        prefix="ROLE_LLM_",
        fallback_settings=settings,
    )

    memory_support = None
    if not options.no_memory and ReMeLightSupport.is_available():
        memory_settings = ReMeLightSettings.from_provider_settings(
            workspace,
            settings,
        )
        memory_support = ReMeLightSupport(memory_settings)

    provider = OpenAICompatibleProvider(settings)
    cron_store_path = workspace / ".echobot" / "cron" / "jobs.json"
    heartbeat_file_path = _heartbeat_file_path(workspace)
    heartbeat_interval_seconds = _heartbeat_interval_seconds(options)
    agent = AgentCore(
        provider,
        system_prompt=build_default_system_prompt(
            workspace,
            enable_project_memory=memory_support is not None,
            memory_workspace=(
                memory_support.working_dir
                if memory_support is not None
                else None
            ),
            enable_scheduling=True,
            cron_store_path=cron_store_path,
            heartbeat_file_path=heartbeat_file_path,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        ),
        memory_support=memory_support,
    )
    session_store = SessionStore(workspace / ".echobot" / "sessions")
    agent_session_store = SessionStore(workspace / ".echobot" / "agent_sessions")
    agent_trace_store = AgentTraceStore(workspace / ".echobot" / "agent_traces")
    session = _load_session(session_store, options) if load_session_state else None
    cron_service = CronService(cron_store_path)
    tool_registry_factory = _build_tool_registry_factory(
        options,
        workspace=workspace,
        memory_support=memory_support,
        cron_service=cron_service,
    )
    tool_registry = None
    if session is not None:
        tool_registry = tool_registry_factory(session.name, False)
    skill_registry = None if options.no_skills else SkillRegistry.discover()
    session_runner = SessionAgentRunner(
        agent,
        agent_session_store,
        skill_registry=skill_registry,
        tool_registry_factory=tool_registry_factory,
        default_temperature=options.temperature,
        default_max_tokens=options.max_tokens,
        trace_store=agent_trace_store,
    )
    role_registry = RoleCardRegistry.discover(project_root=workspace)
    decision_engine = DecisionEngine(
        AgentCore(decider_provider),
        max_tokens=lightweight_max_tokens,
    )
    roleplay_engine = RoleplayEngine(
        AgentCore(role_provider),
        role_registry,
        default_temperature=options.temperature,
        default_max_tokens=options.max_tokens,
        lightweight_max_tokens=lightweight_max_tokens,
    )
    coordinator = ConversationCoordinator(
        session_store=session_store,
        agent_runner=session_runner,
        decision_engine=decision_engine,
        roleplay_engine=roleplay_engine,
        role_registry=role_registry,
    )
    heartbeat_service = None
    if not options.no_heartbeat and _heartbeat_enabled():
        heartbeat_service = HeartbeatService(
            heartbeat_file=heartbeat_file_path,
            provider=provider,
            interval_seconds=heartbeat_interval_seconds,
            enabled=True,
        )

    return RuntimeContext(
        workspace=workspace,
        agent=agent,
        session_store=session_store,
        agent_session_store=agent_session_store,
        session=session,
        tool_registry=tool_registry,
        skill_registry=skill_registry,
        cron_service=cron_service,
        heartbeat_service=heartbeat_service,
        session_runner=session_runner,
        coordinator=coordinator,
        role_registry=role_registry,
        memory_support=memory_support,
        heartbeat_file_path=heartbeat_file_path,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        tool_registry_factory=tool_registry_factory,
    )


def _build_tool_registry_factory(
    options: RuntimeOptions,
    *,
    workspace: Path,
    memory_support: ReMeLightSupport | None,
    cron_service: CronService,
) -> ToolRegistryFactory:
    def factory(session_name: str, scheduled_context: bool) -> ToolRegistry | None:
        if options.no_tools:
            return None
        return create_basic_tool_registry(
            workspace,
            memory_support=memory_support,
            cron_service=cron_service,
            session_name=session_name,
            allow_cron_mutations=not scheduled_context,
        )

    return factory


def _load_session(
    session_store: SessionStore,
    options: RuntimeOptions,
) -> ChatSession:
    if options.new_session:
        return session_store.create_session(options.new_session)

    if options.session:
        session = session_store.load_or_create_session(options.session)
        session_store.set_current_session(session.name)
        return session

    return session_store.load_current_session()


def _heartbeat_file_path(workspace: Path) -> Path:
    file_name = os.environ.get(
        "ECHOBOT_HEARTBEAT_FILE",
        ".echobot/HEARTBEAT.md",
    )
    return workspace / file_name


def _heartbeat_interval_seconds(options: RuntimeOptions) -> int:
    if options.heartbeat_interval is not None:
        return max(int(options.heartbeat_interval), 1)
    raw_value = os.environ.get("ECHOBOT_HEARTBEAT_INTERVAL_SECONDS", "1800")
    try:
        value = int(raw_value)
    except ValueError:
        value = 1800
    return max(value, 1)


def _heartbeat_enabled() -> bool:
    raw_value = os.environ.get("ECHOBOT_HEARTBEAT_ENABLED", "true").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        return max(int(raw_value), 1)
    except ValueError:
        return default


def _resolve_runtime_path(workspace: Path, path: str | Path) -> Path:
    resolved_path = Path(path).expanduser()
    if resolved_path.is_absolute():
        return resolved_path
    return workspace / resolved_path


def _build_provider_from_env(
    *,
    prefix: str,
    fallback_settings: OpenAICompatibleSettings,
) -> OpenAICompatibleProvider:
    if _has_provider_env(prefix):
        return OpenAICompatibleProvider(
            OpenAICompatibleSettings.from_env(prefix=prefix),
        )
    return OpenAICompatibleProvider(fallback_settings)


def _has_provider_env(prefix: str) -> bool:
    api_key_name = f"{prefix}API_KEY"
    model_name = f"{prefix}MODEL"
    return bool(os.environ.get(api_key_name, "").strip()) and bool(
        os.environ.get(model_name, "").strip()
    )
