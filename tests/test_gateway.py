from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from echobot import AgentCore, AgentRunResult, LLMMessage, LLMResponse, ToolCall
from echobot.channels import (
    ChannelAddress,
    InboundMessage,
    MessageBus,
    load_channels_config,
)
from echobot.gateway import DeliveryStore, GatewayRuntime, RouteSessionStore
from echobot.gateway.runtime import _parse_session_command
from echobot.orchestration import (
    ConversationCoordinator,
    DecisionEngine,
    RoleCardRegistry,
    RoleplayEngine,
)
from echobot.providers.base import LLMProvider
from echobot.runtime.bootstrap import RuntimeContext
from echobot.runtime.session_runner import SessionAgentRunner, SessionRunResult
from echobot.runtime.sessions import SessionStore
from echobot.scheduling.cron import CronJob, CronPayload, CronSchedule, CronService


class FakeProvider(LLMProvider):
    async def generate(
        self,
        messages,
        *,
        tools=None,
        tool_choice=None,
        temperature=None,
        max_tokens=None,
    ) -> LLMResponse:
        del tools, tool_choice, temperature, max_tokens
        system_text = "\n".join(
            message.content_text
            for message in messages
            if getattr(message, "role", "") == "system"
        )
        user_text = messages[-1].content_text if messages else ""
        if "The system decided this request needs the full agent" in system_text:
            content = "working"
        elif user_text.startswith("A cron reminder or task was scheduled for later."):
            content = "scheduled-visible"
        elif user_text.startswith("A scheduled reminder or task is due now."):
            content = "due-visible"
        elif user_text.startswith("The full agent finished the task."):
            content = "done"
        elif user_text.startswith("The full agent failed while handling the task."):
            content = "failed"
        else:
            content = "pong"
        return LLMResponse(
            message=LLMMessage(role="assistant", content=content),
            model="fake-model",
        )


class FakeCronSetupRunner:
    async def run_prompt(
        self,
        session_name: str,
        prompt: str,
        *,
        scheduled_context: bool = False,
        transient_system_messages=None,
        temperature=None,
        max_tokens=None,
    ) -> SessionRunResult:
        del scheduled_context, transient_system_messages, temperature, max_tokens
        tool_call = ToolCall(
            id="cron_add_1",
            name="cron",
            arguments=(
                '{"action":"add","content":"该去开会了！",'
                '"task_type":"text","delay_seconds":120}'
            ),
        )
        final_message = LLMMessage(
            role="assistant",
            content='已为您设置了一个2分钟后的会议提醒！2分钟后您会收到"该去开会了！"的消息提醒。',
        )
        new_messages = [
            LLMMessage(role="user", content=prompt),
            LLMMessage(
                role="assistant",
                content="我来为您设置一个2分钟后的会议提醒。",
                tool_calls=[tool_call],
            ),
            LLMMessage(
                role="tool",
                content=(
                    '{"ok":true,"result":{"created":true,"job":{"id":"job_1",'
                    '"name":"该去开会了！","enabled":true,'
                    '"schedule":"at 2030-01-01T09:00:00+08:00",'
                    '"payload_kind":"text","session_name":"'
                    + session_name
                    + '","next_run_at":"2030-01-01T09:00:00+08:00"}}}'
                ),
                tool_call_id=tool_call.id,
            ),
            final_message,
        ]
        return SessionRunResult(
            session=None,
            agent_result=AgentRunResult(
                response=LLMResponse(message=final_message, model="fake-model"),
                new_messages=new_messages,
                history=new_messages,
                steps=2,
            ),
        )


def build_test_runtime(
    workspace: Path,
) -> tuple[RuntimeContext, SessionStore]:
    agent = AgentCore(FakeProvider())
    session_store = SessionStore(workspace / "sessions")
    agent_session_store = SessionStore(workspace / "agent_sessions")
    session_runner = SessionAgentRunner(agent, agent_session_store)
    role_registry = RoleCardRegistry.discover(project_root=workspace)
    coordinator = ConversationCoordinator(
        session_store=session_store,
        agent_runner=session_runner,
        decision_engine=DecisionEngine(),
        roleplay_engine=RoleplayEngine(AgentCore(FakeProvider()), role_registry),
        role_registry=role_registry,
    )
    context = RuntimeContext(
        workspace=workspace,
        agent=agent,
        session_store=session_store,
        agent_session_store=agent_session_store,
        session=None,
        tool_registry=None,
        skill_registry=None,
        cron_service=CronService(workspace / "cron" / "jobs.json"),
        heartbeat_service=None,
        session_runner=session_runner,
        coordinator=coordinator,
        role_registry=role_registry,
        memory_support=None,
        heartbeat_file_path=workspace / "HEARTBEAT.md",
        heartbeat_interval_seconds=60,
        tool_registry_factory=lambda *_args: None,
    )
    return context, session_store


def make_inbound(
    text: str,
    *,
    message_id: int | str = 1,
    channel: str = "telegram",
    chat_id: str = "12345",
    image_urls: list[str] | None = None,
) -> InboundMessage:
    return InboundMessage(
        address=ChannelAddress(channel=channel, chat_id=chat_id),
        sender_id="u1",
        text=text,
        image_urls=list(image_urls or []),
        metadata={"message_id": message_id},
    )


class ChannelConfigTests(unittest.TestCase):
    def test_load_channels_config_creates_default_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "channels.json"

            config = load_channels_config(config_path)

            self.assertFalse(config.console.enabled)
            self.assertFalse(config.telegram.enabled)
            self.assertFalse(config.qq.enabled)
            self.assertTrue(config_path.exists())
            text = config_path.read_text(encoding="utf-8")
            self.assertIn('"telegram"', text)
            self.assertIn('"qq"', text)


class DeliveryStoreTests(unittest.TestCase):
    def test_delivery_store_persists_latest_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = DeliveryStore(Path(temp_dir) / "delivery.json")
            address = ChannelAddress(channel="telegram", chat_id="12345")

            store.remember(
                address.session_name,
                address,
                {"message_id": 9},
            )

            target = store.get_latest_target()
            self.assertIsNotNone(target)
            assert target is not None
            self.assertEqual("telegram", target.address.channel)
            self.assertEqual("12345", target.address.chat_id)
            self.assertEqual(9, target.metadata["message_id"])


class RouteSessionStoreTests(unittest.TestCase):
    def test_store_persists_switch_and_rename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "route_sessions.json"
            route_key = "telegram__12345__deadbeef"
            store = RouteSessionStore(path)

            first = store.get_current_session(route_key)
            second = store.create_session(route_key, title="Work")
            listed = store.list_sessions(route_key)

            self.assertEqual(second.session_name, listed[0].session_name)
            self.assertEqual(first.session_name, listed[1].session_name)

            switched = store.switch_session(route_key, 2)
            self.assertEqual(first.session_name, switched.session_name)

            renamed = store.rename_current_session(route_key, "Personal")
            self.assertEqual("Personal", renamed.title)

            reloaded = RouteSessionStore(path)
            current = reloaded.get_current_session(route_key)
            self.assertEqual(first.session_name, current.session_name)
            self.assertEqual("Personal", current.title)


class CommandParsingTests(unittest.TestCase):
    def test_parse_session_alias_and_telegram_style_command(self) -> None:
        command = _parse_session_command("/session switch 2")
        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual("switch", command.name)
        self.assertEqual("2", command.argument)

        command = _parse_session_command("/ls@EchoBot")
        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual("list", command.name)

    def test_parse_does_not_match_unknown_prefix(self) -> None:
        self.assertIsNone(_parse_session_command("/newyork"))
        self.assertIsNone(_parse_session_command("/switchboard"))


class GatewayRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_inbound_message_routes_response_and_remembers_delivery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            context, _session_store = build_test_runtime(workspace)
            bus = MessageBus()
            delivery_store = DeliveryStore(workspace / "delivery.json")
            route_session_store = RouteSessionStore(workspace / "route_sessions.json")
            gateway = GatewayRuntime(
                context,
                bus,
                delivery_store=delivery_store,
                route_session_store=route_session_store,
            )
            inbound = make_inbound("ping", message_id=7)

            await gateway.handle_inbound_message(inbound)
            outbound = await bus.consume_outbound()

            self.assertEqual("pong", outbound.text)
            self.assertEqual("telegram", outbound.address.channel)
            self.assertEqual("12345", outbound.address.chat_id)
            self.assertEqual(7, outbound.metadata["message_id"])

            current = route_session_store.get_current_session(inbound.route_key)
            self.assertNotEqual(inbound.session_name, current.session_name)

            target = delivery_store.get_session_target(current.session_name)
            self.assertIsNotNone(target)
            assert target is not None
            self.assertEqual(7, target.metadata["message_id"])
            self.assertIsNone(delivery_store.get_session_target(inbound.session_name))

    async def test_handle_inbound_message_supports_image_only_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            context, session_store = build_test_runtime(workspace)
            bus = MessageBus()
            delivery_store = DeliveryStore(workspace / "delivery.json")
            route_session_store = RouteSessionStore(workspace / "route_sessions.json")
            gateway = GatewayRuntime(
                context,
                bus,
                delivery_store=delivery_store,
                route_session_store=route_session_store,
            )
            inbound = make_inbound(
                "",
                message_id=17,
                image_urls=["data:image/png;base64,AAAA"],
            )

            await gateway.handle_inbound_message(inbound)
            outbound = await bus.consume_outbound()

            self.assertEqual("pong", outbound.text)
            current = route_session_store.get_current_session(inbound.route_key)
            session = session_store.load_session(current.session_name)
            self.assertIsInstance(session.history[0].content, list)
            self.assertEqual(
                "data:image/png;base64,AAAA",
                session.history[0].content[0]["image_url"]["url"],
            )

    async def test_role_commands_return_shared_role_responses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            context, _session_store = build_test_runtime(workspace)
            bus = MessageBus()
            delivery_store = DeliveryStore(workspace / "delivery.json")
            route_session_store = RouteSessionStore(workspace / "route_sessions.json")
            gateway = GatewayRuntime(
                context,
                bus,
                delivery_store=delivery_store,
                route_session_store=route_session_store,
            )

            await gateway.handle_inbound_message(
                make_inbound("/role current", message_id=21),
            )
            current = await bus.consume_outbound()

            await gateway.handle_inbound_message(
                make_inbound("/role list", message_id=22),
            )
            listed = await bus.consume_outbound()

            await gateway.handle_inbound_message(
                make_inbound("/role set default", message_id=23),
            )
            switched = await bus.consume_outbound()

            self.assertEqual("Current role: default", current.text)
            self.assertIn("Available roles:", listed.text)
            self.assertIn("* default", listed.text)
            self.assertEqual("Switched role to: default", switched.text)

    async def test_agent_style_message_returns_immediate_and_final_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            context, _session_store = build_test_runtime(workspace)
            bus = MessageBus()
            delivery_store = DeliveryStore(workspace / "delivery.json")
            route_session_store = RouteSessionStore(workspace / "route_sessions.json")
            gateway = GatewayRuntime(
                context,
                bus,
                delivery_store=delivery_store,
                route_session_store=route_session_store,
            )

            await gateway.handle_inbound_message(
                make_inbound("Please set a cron reminder", message_id=8),
            )

            first = await asyncio.wait_for(bus.consume_outbound(), timeout=0.2)
            second = await asyncio.wait_for(bus.consume_outbound(), timeout=0.2)

            self.assertEqual("working", first.text)
            self.assertEqual("done", second.text)
            self.assertTrue(second.metadata["async_result"])
            self.assertEqual("completed", second.metadata["job_status"])

    async def test_deleting_current_route_session_cancels_background_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            context, session_store = build_test_runtime(workspace)
            bus = MessageBus()
            delivery_store = DeliveryStore(workspace / "delivery.json")
            route_session_store = RouteSessionStore(workspace / "route_sessions.json")
            gateway = GatewayRuntime(
                context,
                bus,
                delivery_store=delivery_store,
                route_session_store=route_session_store,
            )

            inbound = make_inbound("Please set a cron reminder", message_id=8)
            await gateway.handle_inbound_message(inbound)
            first = await asyncio.wait_for(bus.consume_outbound(), timeout=0.2)
            self.assertEqual("working", first.text)

            current = route_session_store.get_current_session(inbound.route_key)
            visible_path = session_store.base_dir / f"{current.session_name}.jsonl"
            agent_path = (
                context.agent_session_store.base_dir / f"{current.session_name}.jsonl"
            )
            self.assertTrue(visible_path.exists())

            await gateway.handle_inbound_message(
                make_inbound("/delete", message_id=9),
            )
            deleted = await asyncio.wait_for(bus.consume_outbound(), timeout=0.2)

            self.assertIn("fresh one", deleted.text)
            self.assertFalse(visible_path.exists())
            self.assertFalse(agent_path.exists())

            await asyncio.sleep(1.3)

            self.assertFalse(visible_path.exists())
            self.assertFalse(agent_path.exists())
            replacement = route_session_store.get_current_session(inbound.route_key)
            self.assertNotEqual(current.session_name, replacement.session_name)

    async def test_same_route_messages_are_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            context, _session_store = build_test_runtime(workspace)
            bus = MessageBus()
            delivery_store = DeliveryStore(workspace / "delivery.json")
            route_session_store = RouteSessionStore(workspace / "route_sessions.json")
            gateway = GatewayRuntime(
                context,
                bus,
                delivery_store=delivery_store,
                route_session_store=route_session_store,
            )

            active = 0
            max_active = 0

            async def slow_handle(_message) -> None:
                nonlocal active, max_active
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.05)
                active -= 1

            gateway._handle_inbound_message = slow_handle  # type: ignore[method-assign]

            await asyncio.gather(
                gateway.handle_inbound_message(make_inbound("first", message_id=1)),
                gateway.handle_inbound_message(make_inbound("second", message_id=2)),
            )

            self.assertEqual(1, max_active)

    async def test_scheduling_result_uses_schedule_specific_roleplay_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            session_store = SessionStore(workspace / "sessions")
            role_registry = RoleCardRegistry.discover(project_root=workspace)
            coordinator = ConversationCoordinator(
                session_store=session_store,
                agent_runner=FakeCronSetupRunner(),
                decision_engine=DecisionEngine(),
                roleplay_engine=RoleplayEngine(AgentCore(FakeProvider()), role_registry),
                role_registry=role_registry,
            )

            result = await coordinator.handle_user_turn(
                "demo",
                "Please set a cron reminder",
            )
            await asyncio.sleep(0.05)
            session = session_store.load_session("demo")
            await coordinator.close()

            self.assertEqual("working", result.response_text)
            self.assertEqual("scheduled-visible", session.history[-1].content)

    async def test_cron_text_job_roleplays_visible_notification_and_keeps_raw_content(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            context, session_store = build_test_runtime(workspace)
            bus = MessageBus()
            delivery_store = DeliveryStore(workspace / "delivery.json")
            route_session_store = RouteSessionStore(workspace / "route_sessions.json")
            gateway = GatewayRuntime(
                context,
                bus,
                delivery_store=delivery_store,
                route_session_store=route_session_store,
            )
            delivery_store.remember(
                "demo",
                ChannelAddress(channel="telegram", chat_id="12345"),
                {"message_id": 11},
            )
            job = CronJob(
                id="job_due",
                name="Meeting reminder",
                schedule=CronSchedule(kind="at", at="2030-01-01T09:00:00+08:00"),
                payload=CronPayload(
                    kind="text",
                    content="该去开会了！",
                    session_name="demo",
                ),
            )

            content = await gateway._build_cron_job_executor()(job)
            visible_session = session_store.load_session("demo")
            raw_session = context.agent_session_store.load_session("demo")
            outbound = await bus.consume_outbound()

            self.assertEqual("due-visible", content)
            self.assertEqual("due-visible", visible_session.history[-1].content)
            self.assertEqual("该去开会了！", raw_session.history[-1].content)
            self.assertEqual("due-visible", outbound.text)
            self.assertTrue(outbound.metadata["scheduled"])
            self.assertEqual("cron", outbound.metadata["schedule_kind"])

    async def test_session_commands_create_switch_rename_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            context, session_store = build_test_runtime(workspace)
            bus = MessageBus()
            delivery_store = DeliveryStore(workspace / "delivery.json")
            route_session_store = RouteSessionStore(workspace / "route_sessions.json")
            gateway = GatewayRuntime(
                context,
                bus,
                delivery_store=delivery_store,
                route_session_store=route_session_store,
            )
            route_key = make_inbound("ping").route_key

            await gateway.handle_inbound_message(make_inbound("ping", message_id=1))
            await bus.consume_outbound()
            first = route_session_store.get_current_session(route_key)
            first_session_path = session_store.base_dir / f"{first.session_name}.jsonl"
            self.assertTrue(first_session_path.exists())

            await gateway.handle_inbound_message(
                make_inbound("/new Work", message_id=2),
            )
            outbound = await bus.consume_outbound()
            self.assertIn("Work", outbound.text)
            second = route_session_store.get_current_session(route_key)
            self.assertNotEqual(first.session_name, second.session_name)

            await gateway.handle_inbound_message(make_inbound("ping again", message_id=3))
            await bus.consume_outbound()
            second_session_path = session_store.base_dir / f"{second.session_name}.jsonl"
            self.assertTrue(second_session_path.exists())

            await gateway.handle_inbound_message(make_inbound("/ls", message_id=4))
            outbound = await bus.consume_outbound()
            self.assertIn("Sessions for this chat:", outbound.text)
            self.assertIn("Work", outbound.text)

            await gateway.handle_inbound_message(
                make_inbound("/session switch 2", message_id=5),
            )
            outbound = await bus.consume_outbound()
            self.assertIn(first.short_id, outbound.text)
            switched = route_session_store.get_current_session(route_key)
            self.assertEqual(first.session_name, switched.session_name)

            await gateway.handle_inbound_message(
                make_inbound("/rename Personal", message_id=6),
            )
            outbound = await bus.consume_outbound()
            self.assertIn("Personal", outbound.text)
            renamed = route_session_store.get_current_session(route_key)
            self.assertEqual("Personal", renamed.title)

            await gateway.handle_inbound_message(make_inbound("/delete", message_id=7))
            outbound = await bus.consume_outbound()
            self.assertIn("Now using", outbound.text)

            current = route_session_store.get_current_session(route_key)
            self.assertEqual(second.session_name, current.session_name)
            self.assertFalse(first_session_path.exists())
            self.assertIsNone(delivery_store.get_session_target(first.session_name))
            self.assertIsNotNone(delivery_store.get_session_target(second.session_name))
