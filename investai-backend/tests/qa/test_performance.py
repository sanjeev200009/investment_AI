"""QA performance budgets (offline: TestClient + in-memory SQLite, LLM mocked).

Seeds a realistic volume -- 300 quoted symbols, 40 trading days of daily_close
(12,000 rows), 2,000 news rows, 22 indices -- and times the hot read paths.
Budgets are deliberately generous (roughly 5-10x the measured laptop time) so
they only trip on a real regression, e.g. an N+1 query or an O(n^2) loop
growing with the market. Measured medians are printed (run with -s) and
recorded in qa/reports/performance.md.

No network, no production database: get_db and get_current_user are overridden.
"""
import random
import statistics
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool


@compiles(JSONB, "sqlite")
def _jsonb_on_sqlite(type_, compiler, **kw):  # risk_profiles.answers is JSONB
    return "JSON"

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.evaluation import LessonView
from app.models.portfolio import (InvestmentRule, Portfolio, PortfolioHolding,
                                  PortfolioSnapshot, Watchlist)
from app.models.chat import ChatMessage, ChatSession
from app.models.stock import (CompanyInfo, DailyClose, MarketDataLatest,
                              MarketIndexLatest, NewsSentiment)
from app.models.user import RiskProfile, User, UserProfile
from app.services.recommendations import build_recommendations
from app.services.risk_scoring import question_bank
from app.services.agent.tools import resolve_symbols

N_SYMBOLS, N_DAYS, N_NEWS = 300, 40, 2000
TABLES = [User, UserProfile, RiskProfile, Portfolio, PortfolioHolding, PortfolioSnapshot,
          Watchlist, InvestmentRule, LessonView, ChatSession, ChatMessage,
          MarketDataLatest, MarketIndexLatest, DailyClose, CompanyInfo, NewsSentiment]
RESULTS: dict[str, float] = {}


def timed(fn, runs=5):
    """Median wall time in ms over `runs` (one warm-up call first)."""
    fn()
    samples = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000)
    return statistics.median(samples)


def record(name, ms, budget_ms):
    RESULTS[name] = round(ms, 1)
    print(f"\nPERF {name}: median {ms:.1f} ms (budget {budget_ms} ms)")
    assert ms < budget_ms, f"{name} took {ms:.0f} ms, budget {budget_ms} ms"


@pytest.fixture(scope="module")
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[m.__table__ for m in TABLES])
    Session = sessionmaker(bind=engine, autoflush=False)
    db = Session()
    rnd = random.Random(42)
    now = datetime.now(timezone.utc)
    today = date.today()

    symbols = [f"S{i:03d}.N0000" for i in range(N_SYMBOLS)]
    for i, s in enumerate(symbols):
        price = rnd.uniform(0.5, 400)
        db.add(MarketDataLatest(symbol=s, price=price, change=0.1, change_pct=rnd.uniform(-6, 6),
                                volume=rnd.randint(0, 2_000_000), recorded_at=now, updated_at=now))
        db.add(CompanyInfo(symbol=s, name=f"COMPANY {i:03d} HOLDINGS PLC",
                           sector_group=f"Sector {i % 20}", refreshed_at=now))
        close = price
        for d in range(N_DAYS):
            close *= 1 + rnd.uniform(-0.03, 0.03)
            day = today - timedelta(days=N_DAYS - d)
            db.add(DailyClose(symbol=s, trade_date=day, close=close,
                              last_traded_at=datetime.combine(day, datetime.min.time(), timezone.utc)))
    for n in range(N_NEWS):
        db.add(NewsSentiment(symbol=rnd.choice(symbols), headline=f"Headline {n}",
                             url=f"https://example.test/{n}", summary="Summary text.",
                             sentiment_score=rnd.uniform(-1, 1), sentiment_label="neutral",
                             published_at=now - timedelta(hours=n), scraped_at=now - timedelta(hours=n)))
    db.add(MarketIndexLatest(index_code="ASPI", name="All Share Price Index", value=20000.0,
                             change_pct=0.3, recorded_at=now, updated_at=now))
    for g in range(21):
        db.add(MarketIndexLatest(index_code=f"G{g:02d}", name=f"Group {g}", value=1000.0 + g,
                                 change_pct=0.1, recorded_at=now, updated_at=now))

    user = User(user_id=uuid.uuid4(), email="perf@example.test", password_hash="x", role="user")
    db.add(user)
    db.add(RiskProfile(user_id=user.user_id, score=50, category="Medium"))
    pf = Portfolio(user_id=user.user_id, name="Main")
    db.add(pf)
    db.flush()
    for s in symbols[:20]:
        db.add(PortfolioHolding(portfolio_id=pf.portfolio_id, symbol=s, quantity=100, avg_buy_price=10))
        db.add(Watchlist(user_id=user.user_id, symbol=s))
    for d in range(90):
        db.add(PortfolioSnapshot(portfolio_id=pf.portfolio_id, snapshot_date=today - timedelta(days=d),
                                 total_value=1000 + d, total_cost=1000, holdings_count=20, priced_count=20))
    db.commit()

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    def _user():
        return db.get(User, user.user_id)

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    yield {"db": db, "client": TestClient(app), "symbols": symbols, "user": user}
    app.dependency_overrides.clear()
    if RESULTS:
        print("\nPERF SUMMARY (median ms): " + ", ".join(f"{k}={v}" for k, v in RESULTS.items()))


@pytest.mark.parametrize("category", ["Low", "Medium", "High", None])
def test_build_recommendations_per_risk_category(env, category):
    db, user = env["db"], env["user"]
    out = build_recommendations(db, user_id=user.user_id, limit=10, risk_category=category)
    assert out["count"] > 0 and len(out["items"]) == 10
    assert not {i["symbol"] for i in out["items"]} & set(env["symbols"][:20]), "held symbols excluded"
    ms = timed(lambda: build_recommendations(db, user_id=user.user_id, limit=10, risk_category=category))
    record(f"build_recommendations[{category}]", ms, 1500)


def test_recommendations_endpoint(env):
    c = env["client"]
    assert c.get("/api/v1/recommendations?limit=10").status_code == 200
    record("GET /recommendations", timed(lambda: c.get("/api/v1/recommendations?limit=10")), 1500)


def test_resolve_symbols(env):
    db = env["db"]
    terms = ["S001", "s150.n0000", "Company 042 Holdings", "COMPANY 299", "ZZZZ", "S250"]
    got = resolve_symbols(db, terms)
    assert got["S001"] == "S001.N0000" and got["ZZZZ"] is None
    record("resolve_symbols[6 terms]", timed(lambda: resolve_symbols(db, terms)), 500)


def test_risk_scoring_and_plan(env):
    c = env["client"]
    answers = {str(q["id"]): q["options"][0] for q in question_bank()}

    def flow():
        assert c.post("/api/v1/me/risk-profile", json={"answers": answers}).status_code == 200
        assert c.get("/api/v1/me/plan").status_code == 200

    record("POST /me/risk-profile + GET /me/plan", timed(flow), 500)


def test_lessons_endpoints(env):
    c = env["client"]
    lessons = c.get("/api/v1/learn/lessons").json()
    assert len(lessons) >= 9
    record("GET /learn/lessons", timed(lambda: c.get("/api/v1/learn/lessons")), 200)
    lid = lessons[0]["id"]
    assert c.get(f"/api/v1/learn/lessons/{lid}").status_code == 200
    record("GET /learn/lessons/{id}", timed(lambda: c.get(f"/api/v1/learn/lessons/{lid}")), 300)


def test_dashboard_endpoint_never_waits_for_llm(env, monkeypatch):
    from app.routers import dashboard
    from app.services import llm

    def slow_llm(*a, **k):  # a hung provider must not reach the response time
        time.sleep(2)
        return None

    monkeypatch.setattr(llm, "complete_text_sync", slow_llm)
    monkeypatch.setitem(dashboard._insight_cache, "key", None)
    monkeypatch.setitem(dashboard._insight_cache, "insights", None)
    c = env["client"]
    r = c.get("/api/v1/dashboard/")
    assert r.status_code == 200 and r.json()["aspi"]["value"] == 20000.0
    record("GET /dashboard (LLM hung 2 s)", timed(lambda: c.get("/api/v1/dashboard/")), 800)
