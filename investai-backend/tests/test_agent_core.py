"""Agent loop regressions: empty reply after max_loops, and prose dropped once a
tool call starts. The LLM, memory and tools are faked; nothing leaves the process."""

import asyncio
import json
from types import SimpleNamespace as NS

from app.services.agent import core


class FakeMemory:
    saved = None

    def __init__(self, *a):
        pass

    def save_user_message(self, m):
        pass

    def build_context(self, m):
        return [{"role": "user", "content": m}]

    def save_assistant_message(self, text, label):
        FakeMemory.saved = text
        return 1


class FakeTools:
    def __init__(self, *a):
        pass

    async def execute(self, name, args):
        return "{}"


def _chunk(content=None, tool=False):
    tcs = [NS(index=0, id="c1", function=NS(name="get_stock_data", arguments="{}"))] if tool else None
    return NS(choices=[NS(delta=NS(content=content, tool_calls=tcs))])


async def _aiter(items):
    for i in items:
        yield i


def _run(monkeypatch, tool_chunks):
    calls = []

    async def fake_acreate(*, messages, tools=None, stream=False, **kw):
        calls.append(tools)
        chunks = tool_chunks if tools else [_chunk("Final answer.")]
        return _aiter(chunks), NS(label="fake")

    monkeypatch.setattr(core.llm, "acreate", fake_acreate)
    monkeypatch.setattr(core, "ConversationMemory", FakeMemory)
    monkeypatch.setattr(core, "ToolExecutor", FakeTools)

    async def collect():
        return [e async for e in core.stream_agent("hi", 1, None, NS(user_id="u"))]

    events = [json.loads(e[len("data: "):]) for e in asyncio.run(collect())]
    return calls, events


def test_model_that_always_calls_tools_still_gets_an_answer(monkeypatch):
    calls, _ = _run(monkeypatch, [_chunk(tool=True)])
    assert calls[-1] is None and all(calls[:-1])
    assert FakeMemory.saved == "Final answer."


def test_prose_alongside_tool_call_is_streamed_and_saved(monkeypatch):
    _, events = _run(monkeypatch, [_chunk(tool=True), _chunk("Checking. ")])
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert tokens.startswith("Checking. ")
    assert FakeMemory.saved.startswith("Checking. ")
