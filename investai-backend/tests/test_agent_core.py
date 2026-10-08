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
    # These tests are about the agent loop, i.e. step 3 of the follow-up flow:
    # the user has already answered the bot's follow-up question.
    monkeypatch.setattr(core, "pending_followup", lambda db, sid: ("hi", "Which one?\nOPTIONS: a | b"))

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


# ── Follow-up flow (app/services/agent/followup.py) ─────────────────────────────

def test_new_question_gets_one_followup_first(monkeypatch):
    """Step 1: no follow-up pending -> the bot asks one, tagged, and stops."""
    saved = {}

    class Mem(FakeMemory):
        def save_assistant_message(self, text, label):
            saved["text"], saved["label"] = text, label
            return 7

    async def fake_followup(question, lang):
        return "What is your goal?\nOPTIONS: Growth | Income"

    async def no_agent(**kw):
        raise AssertionError("the agent must not answer before the follow-up")

    monkeypatch.setattr(core, "ConversationMemory", Mem)
    monkeypatch.setattr(core, "pending_followup", lambda db, sid: None)
    monkeypatch.setattr(core, "ask_followup", fake_followup)
    monkeypatch.setattr(core.llm, "acreate", no_agent)

    async def collect():
        return [json.loads(e[6:]) async for e in core.stream_agent("Which stock?", 1, None, NS(user_id="u"))]

    events = asyncio.run(collect())
    assert saved == {"text": "What is your goal?\nOPTIONS: Growth | Income", "label": core.FOLLOWUP_TAG}
    assert [e["type"] for e in events] == ["token", "done"]


def test_answer_is_combined_with_the_original_question(monkeypatch):
    """Steps 2-3: the agent receives question + follow-up + answer, without OPTIONS."""
    seen = {}

    async def fake_acreate(*, messages, tools=None, stream=False, **kw):
        seen["prompt"] = messages[-1]["content"]
        return _aiter([_chunk("Answer.")]), NS(label="fake")

    monkeypatch.setattr(core.llm, "acreate", fake_acreate)
    monkeypatch.setattr(core, "ConversationMemory", FakeMemory)
    monkeypatch.setattr(core, "ToolExecutor", FakeTools)
    monkeypatch.setattr(core, "pending_followup",
                        lambda db, sid: ("Which stock?", "What is your goal?\nOPTIONS: Growth | Income"))

    async def collect():
        return [e async for e in core.stream_agent("Income", 1, None, NS(user_id="u"))]

    asyncio.run(collect())
    p = seen["prompt"]
    assert "My question: Which stock?" in p and "You asked me: What is your goal?" in p
    assert "My answer: Income" in p and "OPTIONS" not in p
