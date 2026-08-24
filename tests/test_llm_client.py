from __future__ import annotations

from types import SimpleNamespace
import unittest

from client.llm_client import LLMClient
from client.response import StreamEventType
from config.config import Config


class _FakeStream:
    def __init__(self, chunks: list[object]) -> None:
        self._chunks = chunks

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class _FakeCompletions:
    def __init__(self, chunks: list[object]) -> None:
        self._chunks = chunks

    async def create(self, **kwargs):
        return _FakeStream(self._chunks.copy())


class _FakeClient:
    def __init__(self, chunks: list[object]) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(chunks))


def _tool_chunk(call_id: str | None, name: str | None, arguments: str | None):
    function = SimpleNamespace(name=name, arguments=arguments)
    tool_call = SimpleNamespace(index=0, id=call_id, function=function)
    delta = SimpleNamespace(content=None, tool_calls=[tool_call])
    choice = SimpleNamespace(delta=delta, finish_reason=None)
    return SimpleNamespace(usage=None, choices=[choice])


def _completion_chunk():
    delta = SimpleNamespace(content=None, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason="tool_calls")
    return SimpleNamespace(usage=None, choices=[choice])


class LLMClientStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_accumulates_tool_arguments_from_multiple_chunks(self) -> None:
        client = LLMClient(Config())
        fake_client = _FakeClient(
            [
                _tool_chunk("call_123", "read_file", '{"path":"src'),
                _tool_chunk(None, None, '/main.py"}'),
                _completion_chunk(),
            ]
        )

        events = [
            event
            async for event in client._stream_response(fake_client, {"model": "test"})
        ]

        completed = [
            event for event in events if event.type == StreamEventType.TOOL_CALL_COMPLETE
        ]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].tool_call.call_id, "call_123")
        self.assertEqual(completed[0].tool_call.name, "read_file")
        self.assertEqual(completed[0].tool_call.arguments, {"path": "src/main.py"})
