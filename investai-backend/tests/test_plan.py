"""GET /me/plan rules (offline, in-memory SQLite)."""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.content.lessons import LESSONS
from app.database import Base
from app.models.chat import ChatMessage, ChatSession
from app.models.evaluation import LessonView
from app.models.portfolio import InvestmentRule, Portfolio, PortfolioHolding, Watchlist
from app.routers.user import PlanOut
from app.services import risk_scoring as rs
from app.services.plan import PROMPT_KEYS, STEP_LESSON, build_plan

TABLES = [LessonView, Watchlist, InvestmentRule, Portfolio, PortfolioHolding, ChatSession, ChatMessage]


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine, tables=[m.__table__ for m in TABLES])
    return sessionmaker(bind=engine)()


USER = uuid.uuid4()
RIGHT = {str(q.id): q.correct for q in rs.KNOWLEDGE}
WRONG = {str(q.id): next(o for o in q.options if o != q.correct) for q in rs.KNOWLEDGE}


def ids(plan):
    return [s['id'] for s in plan['steps']]


def test_contract_shape(db):
    plan = build_plan(db, USER, 'Medium', 3, {})
    PlanOut(**plan)  # the response model accepts it
    assert plan['persona'] == 'steady_builder'
    assert plan['knowledge_total'] == 5
    assert 4 <= len(plan['steps']) <= 6
    assert all(s['id'] in STEP_LESSON and s['lesson_id'] == STEP_LESSON[s['id']] for s in plan['steps'])
    assert sorted(plan['lesson_ids']) == sorted(l['id'] for l in LESSONS)
    assert len(plan['prompts']) == 3 and set(plan['prompts']) <= set(PROMPT_KEYS)
    lesson_ids = {l['id'] for l in LESSONS}
    assert all(v in lesson_ids for v in STEP_LESSON.values() if v)


@pytest.mark.parametrize('category,persona', [
    ('Low', 'cautious_starter'), ('Medium', 'steady_builder'),
    ('High', 'growth_explorer'), (None, 'cautious_starter'),
])
def test_persona_follows_risk_category(db, category, persona):
    assert build_plan(db, USER, category, None, None)['persona'] == persona


def test_low_knowledge_starts_with_the_basics(db):
    plan = build_plan(db, USER, 'High', 1, {**WRONG})
    assert ids(plan)[0] == 'learn_basics'
    assert plan['lesson_ids'][0] == 'what-is-a-share'
    # Missed checks come first among the chat starters.
    assert plan['prompts'] == ['prompt_what_is_share', 'prompt_what_is_aspi', 'prompt_why_diversify']


def test_no_quiz_result_is_treated_as_a_beginner(db):
    assert ids(build_plan(db, USER, None, None, None))[0] == 'learn_basics'


def test_strong_knowledge_skips_basics_and_experience_adds_holdings(db):
    plan = build_plan(db, USER, 'High', 5, {'4': 'Regularly', **RIGHT})
    assert 'learn_basics' not in ids(plan)
    assert ids(plan)[0] == 'learn_diversification'
    assert 'add_first_holding' in ids(plan)
    assert plan['prompts'] == ['prompt_explain_pe', 'prompt_compare_sectors', 'prompt_market_today']


def test_low_risk_tolerance_always_includes_learning_risk(db):
    plan = build_plan(db, USER, 'Low', 5, {'4': 'Regularly'})
    assert 'learn_risk' in ids(plan)
    assert len(plan['steps']) <= 6


def test_done_flags_come_from_real_rows(db):
    other = uuid.uuid4()
    plan = build_plan(db, USER, 'Medium', 3, {'4': 'Occasionally'})
    assert not any(s['done'] for s in plan['steps'])

    db.add_all([
        LessonView(user_id=USER, lesson_id='risk-and-return'),
        Watchlist(user_id=USER, symbol='JKH.N0000'),
        InvestmentRule(user_id=other, symbol='JKH.N0000', condition_type='price_above', threshold=1),
    ])
    session = ChatSession(user_id=USER)
    portfolio = Portfolio(user_id=USER, name='Main')
    db.add_all([session, portfolio])
    db.flush()
    db.add_all([
        ChatMessage(session_id=session.session_id, sender_type='assistant', content='hi'),
        PortfolioHolding(portfolio_id=portfolio.portfolio_id, symbol='JKH.N0000', quantity=1, avg_buy_price=1),
    ])
    db.commit()

    done = {s['id']: s['done'] for s in build_plan(db, USER, 'Medium', 3, {'4': 'Occasionally'})['steps']}
    assert done == {
        'learn_risk': True, 'learn_diversification': False, 'watch_first_stock': True,
        'set_first_alert': False,   # the rule belongs to someone else
        'add_first_holding': True,
        'ask_ai_first': False,      # only the assistant has spoken
    }

    db.add(ChatMessage(session_id=session.session_id, sender_type='user', content='what is ASPI?'))
    db.commit()
    plan = build_plan(db, USER, 'Medium', 3, {})
    assert next(s for s in plan['steps'] if s['id'] == 'ask_ai_first')['done']
    # A lesson already read drops to the end of the reading order.
    assert plan['lesson_ids'][-1] == 'risk-and-return'


class _FakeDB:
    """Just enough Session for POST /me/risk-profile (risk_profiles is JSONB, not SQLite-able)."""
    def __init__(self):
        self.added = []

    def query(self, *a):
        return self

    def filter(self, *a):
        return self

    def first(self):
        return self.added[0] if self.added else None

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_risk_profile_endpoint_returns_and_stores_knowledge_score():
    from types import SimpleNamespace as NS

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.dependencies import get_current_user, get_db
    from app.routers import user as user_router
    from tests.test_risk_scoring import MOST_TOLERANT

    db = _FakeDB()
    app = FastAPI()
    app.include_router(user_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: NS(user_id=USER)
    client = TestClient(app)

    answers = {**MOST_TOLERANT, **RIGHT, '101': WRONG['101']}
    body = client.post('/me/risk-profile', json={'answers': answers}).json()
    assert (body['knowledge_score'], body['knowledge_total'], body['category']) == (4, 5, 'High')
    assert db.added[0].knowledge_score == 4

    # An older client (no knowledge checks) keeps the stored result.
    body = client.post('/me/risk-profile', json={'answers': MOST_TOLERANT}).json()
    assert body['knowledge_score'] == 4

    bank = client.get('/me/assessment/questions').json()
    assert [q['kind'] for q in bank].count('knowledge') == 5
