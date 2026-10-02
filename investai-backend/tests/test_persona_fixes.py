"""Fixes from the five-persona walkthrough (Oct 2026)."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.agent import memory
from app.services.agent.tools import TOOL_SCHEMAS, _int_arg, _local
from app.services.sentiment import analyse_text


def test_string_limit_no_longer_crashes_tools():
    assert _int_arg("5", 5, 10) == 5
    assert _int_arg("50", 5, 10) == 10
    assert _int_arg("lots", 5, 10) == 5
    assert _int_arg(None, 5, 10) == 5


def test_tool_times_are_sri_lanka_time():
    assert _local(datetime(2026, 10, 2, 7, 45, tzinfo=timezone.utc)) == "2026-10-02 13:15 Sri Lanka time"
    assert _local(datetime(2026, 10, 2, 7, 45)) == "2026-10-02 13:15 Sri Lanka time"  # naive = UTC


def test_explain_recommendation_tool_is_offered():
    assert "explain_recommendation" in {t["function"]["name"] for t in TOOL_SCHEMAS}


def test_message_script_sets_reply_language():
    assert memory.detect_language("டிவிடெண்ட் என்றால் என்ன?") == "ta"
    assert memory.detect_language("ලාභාංශය කුමක්ද?") == "si"
    assert memory.detect_language("what is a dividend?") is None
    assert "Tamil script" in memory.language_instruction("ta")


def test_mixed_script_words_are_dropped_whole_not_letter_by_letter():
    # Whole words go, so no broken fragments like "ஒரு‑" are left behind.
    assert memory.clean_script("ஒரு두‑మూడు ஆண்டுகள் しているASPI ASPI", "ta") == " ஆண்டுகள்  ASPI"
    assert memory.clean_script("ලාභාංශ 之一 (dividend)。", "si") == "ලාභාංශ  "
    assert memory.clean_script("日本 is Japan", None) == "日本 is Japan"


def test_stream_cleaner_never_cuts_a_word_split_across_chunks():
    c = memory.ScriptCleaner("ta")
    out = c.feed("பங்கு என்ப") + c.feed("து ஒரு") + c.feed("두 பகுதி") + c.flush()
    assert out == "பங்கு என்பது  பகுதி"
    assert memory.ScriptCleaner(None).feed("日本") == "日本"


def test_prompt_lists_only_real_lessons():
    assert "{lesson_titles}" not in memory.SYSTEM_PROMPT
    assert '"What is a share?"' in memory.SYSTEM_PROMPT


def test_risk_context_carries_the_users_horizon():
    user = SimpleNamespace(risk_profile=SimpleNamespace(
        category="Low", score=29, answers={"1": "Retirement", "3": "5+ years"}))
    ctx = memory._risk_context(user)
    assert "investment horizon: 5+ years" in ctx and "goal: Retirement" in ctx


def test_falling_market_headline_is_negative():
    score, label = asyncio.run(analyse_text(
        "CSE continues slide, falls 0.6% to new six-month low. The ASPI was down with "
        "losers outpacing winners 163 to 31, and the active S&P SL20 was down 0.41%."))
    assert label == "negative", score
    assert asyncio.run(analyse_text("Bourse gains on strong earnings"))[1] == "positive"
