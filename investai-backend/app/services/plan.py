"""A beginner's first-steps plan, built by fixed rules (no LLM).

Served by ``GET /me/plan`` and rendered on Home. The shape is a contract with
the app; keep the ids and prompt keys stable, the app looks up their text as
``plan_step_<id>_title`` / ``_body`` and ``prompt_<key>``.

    persona         from the risk category
    steps           4-6, ordered by knowledge score and stock experience
                    (low knowledge -> basics first); ``done`` from real rows
    lesson_ids      every lesson, the plan's lessons first, unread before read
    prompts         three chat starters, missed knowledge checks first
"""
from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.content.lessons import LESSONS
from app.models.chat import ChatMessage, ChatSession
from app.models.evaluation import LessonView
from app.models.portfolio import InvestmentRule, Portfolio, PortfolioHolding, Watchlist
from app.services.risk_scoring import _BY_ID, KNOWLEDGE_TOTAL

PERSONAS = {'Low': 'cautious_starter', 'Medium': 'steady_builder', 'High': 'growth_explorer'}

STEP_LESSON = {
    'learn_basics': 'what-is-a-share',
    'learn_indices': 'market-indices',
    'learn_risk': 'risk-and-return',
    'learn_diversification': 'diversification',
    'learn_fundamentals': 'fundamentals-basics',
    'watch_first_stock': None,
    'set_first_alert': None,
    'add_first_holding': None,
    'ask_ai_first': None,
}

PROMPT_KEYS = (
    'prompt_what_is_share',
    'prompt_how_to_start_cse',
    'prompt_what_is_aspi',
    'prompt_explain_risk',
    'prompt_why_diversify',
    'prompt_what_is_dividend',
    'prompt_explain_pe',
    'prompt_compare_sectors',
    'prompt_market_today',
)

# A missed knowledge check -> the chat starter that covers it.
_MISSED_PROMPT = {
    '101': 'prompt_what_is_share',
    '102': 'prompt_what_is_aspi',
    '103': 'prompt_why_diversify',
    '104': 'prompt_explain_pe',
    '105': 'prompt_what_is_dividend',
}

# By knowledge tier: steps and default prompts.
_TIERS = {
    'low': (
        ['learn_basics', 'learn_indices', 'learn_risk', 'watch_first_stock', 'ask_ai_first'],
        ['prompt_what_is_share', 'prompt_how_to_start_cse', 'prompt_what_is_aspi'],
    ),
    'mid': (
        ['learn_risk', 'learn_diversification', 'watch_first_stock', 'set_first_alert', 'ask_ai_first'],
        ['prompt_explain_risk', 'prompt_why_diversify', 'prompt_what_is_dividend'],
    ),
    'high': (
        ['learn_diversification', 'learn_fundamentals', 'watch_first_stock', 'set_first_alert', 'ask_ai_first'],
        ['prompt_explain_pe', 'prompt_compare_sectors', 'prompt_market_today'],
    ),
}

_EXPERIENCED = {'Occasionally', 'Regularly'}


def _tier(knowledge_score: int | None) -> str:
    if knowledge_score is None or knowledge_score <= 2:
        return 'low'
    return 'mid' if knowledge_score <= 4 else 'high'


def _done_flags(db: Session, user_id: Any) -> tuple[dict[str, bool], set[str]]:
    viewed = {row[0] for row in db.query(LessonView.lesson_id).filter(LessonView.user_id == user_id).distinct()}

    def exists(query) -> bool:
        return query.first() is not None

    flags = {step: lesson in viewed for step, lesson in STEP_LESSON.items() if lesson}
    flags['watch_first_stock'] = exists(db.query(Watchlist.watchlist_id).filter(Watchlist.user_id == user_id))
    flags['set_first_alert'] = exists(db.query(InvestmentRule.rule_id).filter(InvestmentRule.user_id == user_id))
    flags['add_first_holding'] = exists(
        db.query(PortfolioHolding.holding_id).join(Portfolio).filter(Portfolio.user_id == user_id))
    flags['ask_ai_first'] = exists(
        db.query(ChatMessage.message_id).join(ChatSession)
        .filter(ChatSession.user_id == user_id, ChatMessage.sender_type == 'user'))
    return flags, viewed


def build_plan(
    db: Session,
    user_id: Any,
    category: str | None,
    knowledge_score: int | None,
    answers: Mapping[str, Any] | None,
) -> dict[str, Any]:
    answers = answers or {}
    tier = _tier(knowledge_score)
    steps, default_prompts = (list(x) for x in _TIERS[tier])

    # Low risk tolerance: understand risk before anything else practical.
    if category == 'Low' and 'learn_risk' not in steps:
        steps.insert(1, 'learn_risk')
    # Someone who has bought shares before is ready to track real holdings.
    if answers.get('4') in _EXPERIENCED and tier != 'low':
        steps.insert(len(steps) - 1, 'add_first_holding')
    steps = steps[:6]

    flags, viewed = _done_flags(db, user_id)

    plan_lessons = [STEP_LESSON[s] for s in steps if STEP_LESSON[s]]
    # An income investor's first question is dividends; the dividend-yield lesson
    # was seventh of nine for them.
    if answers.get('1') == 'Income Generation' and 'fundamentals-basics' not in plan_lessons:
        plan_lessons.append('fundamentals-basics')
        default_prompts.insert(0, 'prompt_what_is_dividend')
    rest = [lesson['id'] for lesson in LESSONS if lesson['id'] not in plan_lessons]
    ordered = plan_lessons + rest
    lesson_ids = [l for l in ordered if l not in viewed] + [l for l in ordered if l in viewed]

    missed = [_MISSED_PROMPT[qid] for qid in sorted(_MISSED_PROMPT)
              if qid in answers and answers[qid] != _BY_ID[int(qid)].correct]
    prompts = list(dict.fromkeys(missed + default_prompts))[:3]

    return {
        'persona': PERSONAS.get(category or '', 'cautious_starter'),
        'risk_category': category,
        'knowledge_score': knowledge_score,
        'knowledge_total': KNOWLEDGE_TOTAL,
        'steps': [{'id': s, 'lesson_id': STEP_LESSON[s], 'done': bool(flags[s])} for s in steps],
        'lesson_ids': lesson_ids,
        'prompts': prompts,
    }

