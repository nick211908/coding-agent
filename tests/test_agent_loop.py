from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent.agent import Agent
from agent.events import AgentEventType
from client.response import StreamEvent, StreamEventType, TextDelta, ToolCall
from config.config import Config


class AgentLoopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        (self.cwd / "sample.txt").write_text("file content", encoding="utf-8")

    async def asyncTearDown(self) -> None:
        self.tmp.cleanup()

    async def test_tool_call_turn_does_not_emit_max_turns_error(self) -> None:
        """Verify that executing a tool call on turn 1 does NOT falsely emit max turns reached."""
        config = Config(cwd=self.cwd, max_turns=10)
        agent = Agent(config)
        await agent.session.initialize()

        # Mock the chat_completion stream for two turns:
        # Turn 1: LLM returns a tool call (read_file)
        # Turn 2: LLM returns text response
        turn1_events = [
            StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    name="read_file",
                    call_id="call_1",
                    arguments={"path": "sample.txt"},
                ),
            ),
            StreamEvent(type=StreamEventType.MESSAGE_COMPLETE),
        ]

        turn2_events = [
            StreamEvent(
                type=StreamEventType.TEXT_DELTA,
                text_delta=TextDelta(content="Here is the content"),
            ),
            StreamEvent(type=StreamEventType.MESSAGE_COMPLETE),
        ]

        async def fake_chat_completion(*args, **kwargs):
            if not hasattr(fake_chat_completion, "calls"):
                fake_chat_completion.calls = 0
            fake_chat_completion.calls += 1

            events = turn1_events if fake_chat_completion.calls == 1 else turn2_events
            for ev in events:
                yield ev

        agent.session.client.chat_completion = fake_chat_completion

        collected_events = []
        async for event in agent._agentic_loop("read sample.txt"):
            collected_events.append(event)

        error_events = [
            ev for ev in collected_events if ev.type == AgentEventType.AGENT_ERROR
        ]
        self.assertEqual(
            error_events,
            [],
            f"Expected no agent errors, but got: {[e.data for e in error_events]}",
        )

    async def test_max_turns_emitted_only_when_limit_exhausted(self) -> None:
        """Verify max turns error is emitted ONLY when all turns are exhausted."""
        config = Config(cwd=self.cwd, max_turns=2)
        agent = Agent(config)
        await agent.session.initialize()

        # Stream that continuously returns tool calls
        async def continuous_tool_calls(*args, **kwargs):
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    name="read_file",
                    call_id="call_x",
                    arguments={"path": "sample.txt"},
                ),
            )
            yield StreamEvent(type=StreamEventType.MESSAGE_COMPLETE)

        agent.session.client.chat_completion = continuous_tool_calls

        collected_events = []
        async for event in agent._agentic_loop("keep looping"):
            collected_events.append(event)

        error_events = [
            ev for ev in collected_events if ev.type == AgentEventType.AGENT_ERROR
        ]
        self.assertEqual(len(error_events), 1)
        self.assertIn("Maximum turns (2) reached", error_events[0].data.get("error", ""))
