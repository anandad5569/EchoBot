from __future__ import annotations

import unittest

from echobot import AgentCore, LLMMessage, LLMResponse
from echobot.orchestration.decision import (
    DecisionEngine,
    _parse_decision_response,
    _rule_based_decision,
)
from echobot.providers.base import LLMProvider


class StaticProvider(LLMProvider):
    def __init__(self, content: str, *, finish_reason: str | None = None) -> None:
        self._content = content
        self._finish_reason = finish_reason

    async def generate(
        self,
        messages,
        *,
        tools=None,
        tool_choice=None,
        temperature=None,
        max_tokens=None,
    ) -> LLMResponse:
        del messages, tools, tool_choice, temperature, max_tokens
        return LLMResponse(
            message=LLMMessage(role="assistant", content=self._content),
            model="fake-model",
            finish_reason=self._finish_reason,
        )


class RuleBasedDecisionTests(unittest.TestCase):
    def test_explicit_agent_requests_route_to_agent(self) -> None:
        samples = [
            "Please set a cron reminder",
            "Open the file config.json",
            "帮我修改代码",
            "请运行测试",
        ]

        for text in samples:
            with self.subTest(text=text):
                decision = _rule_based_decision(text)

                self.assertIsNotNone(decision)
                assert decision is not None
                self.assertEqual("agent", decision.route)

    def test_general_discussion_with_agent_like_words_does_not_force_agent(self) -> None:
        samples = [
            "What do you think about shell sort?",
            "How does human memory work?",
            "Can you help me brainstorm project naming ideas?",
            "Please translate this article about coding skills.",
            "How do I edit code in Python?",
            "How do I use tools effectively?",
        ]

        for text in samples:
            with self.subTest(text=text):
                self.assertIsNone(_rule_based_decision(text))

    def test_relative_time_without_scheduler_intent_does_not_force_agent(self) -> None:
        samples = [
            "Translate this: I will call you in 2 days.",
            'In a story, what does "3 days later" imply?',
            "What happens to bread in 2 days at room temperature?",
        ]

        for text in samples:
            with self.subTest(text=text):
                self.assertIsNone(_rule_based_decision(text))


class ParseDecisionResponseTests(unittest.TestCase):
    def test_non_json_chat_responses_do_not_flip_to_agent(self) -> None:
        samples = [
            "chat - no agent needed",
            '{"route":"chat","reason":"does not need agent"',
            "I think this should be chat because no agent is required.",
        ]

        for text in samples:
            with self.subTest(text=text):
                decision = _parse_decision_response(text)

                self.assertEqual("chat", decision.route)

    def test_fallback_parser_accepts_explicit_route_field(self) -> None:
        decision = _parse_decision_response("route: agent\nreason: needs tools")

        self.assertEqual("agent", decision.route)


class DecisionEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_defaults_to_chat_when_rules_do_not_match(self) -> None:
        decision = await DecisionEngine().decide("How does human memory work?")

        self.assertEqual("chat", decision.route)

    async def test_engine_honors_chat_only_route_mode(self) -> None:
        decision = await DecisionEngine().decide(
            "Please set a cron reminder",
            route_mode="chat_only",
        )

        self.assertEqual("chat", decision.route)

    async def test_engine_honors_force_agent_route_mode(self) -> None:
        decision = await DecisionEngine().decide(
            "How does human memory work?",
            route_mode="force_agent",
        )

        self.assertEqual("agent", decision.route)

    async def test_engine_uses_safe_fallback_for_malformed_decider_output(self) -> None:
        engine = DecisionEngine(AgentCore(StaticProvider("chat - no agent needed")))

        decision = await engine.decide("Can you explain shell sort?")

        self.assertEqual("chat", decision.route)

    async def test_engine_logs_warning_when_decider_hits_max_tokens(self) -> None:
        engine = DecisionEngine(
            AgentCore(
                StaticProvider(
                    '{"route":"chat"',
                    finish_reason="length",
                )
            )
        )

        with self.assertLogs("echobot.orchestration.decision", level="WARNING") as logs:
            decision = await engine.decide("Please run that in the background")

        self.assertEqual("chat", decision.route)
        self.assertIn("Decision layer hit max_tokens limit", logs.output[0])
