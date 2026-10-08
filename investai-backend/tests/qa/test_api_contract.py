"""QA: API & contract tests for every InvestAI router.

Drives the REAL FastAPI app (app.main.app) through TestClient against an
in-memory SQLite database. Offline by construction:

* env vars below point DATABASE_URL / SUPABASE_URL at a dead loopback port
  before the app is imported, so no real credentials are used;
* an autouse fixture blocks every non-loopback socket connect, so any code
  path that tries to reach Supabase, an LLM, FCM, cse.lk or Redis fails loudly
  instead of touching a real service;
* LLM, push, Celery and Supabase entry points are monkeypatched per test.

JWTs are signed with a throwaway test secret, never the real one.
Tests marked xfail(strict=True) are FINDINGS: they assert the correct
behaviour and currently fail because the app is wrong.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List

# Must run before anything imports app.config / app.database.
os.environ["DATABASE_URL"] = "postgresql://qa:qa@127.0.0.1:1/qa_offline"
os.environ["SUPABASE_URL"] = "http://127.0.0.1:1"
os.environ["SUPABASE_ANON_KEY"] = "qa-anon"
os.environ["SUPABASE_SERVICE_KEY"] = "qa-service"
os.environ["SECRET_KEY"] = "qa-not-the-real-secret"
os.environ["ENVIRONMENT"] = "development"

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import TypeAdapter
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app import dependencies as deps
from app import rate_limit
from app.database import Base
from app.main import app
from app.models.chat import ChatMessage, ChatSession
from app.models.evaluation import LessonView
from app.models.notification import Notification
from app.models.portfolio import InvestmentRule, Portfolio, PortfolioHolding, Watchlist
from app.models.stock import (CompanyInfo, DailyClose, MarketDataLatest,
                              MarketIndexLatest, NewsSentiment)
from app.models.user import RiskProfile, User, UserProfile
from app.routers import chat as chat_router
from app.routers import dashboard as dashboard_router
from app.routers.chat import MessageOut, SessionOut, SendMessageResponse
from app.routers.notifications import NotificationOut
from app.routers.rules import RuleOut
from app.routers.user import PlanOut, QuestionOut, RiskProfileResponse
from app.routers.watchlist import WatchlistItem
from app.schemas.auth import UserOut
from app.schemas.portfolio import HoldingOut, PortfolioHistory, PortfolioOut
from app.schemas.stock import (CompanyInfo as CompanyInfoOut, MarketData,
                               MarketIndex, NewsSentiment as NewsOut,
                               PriceHistory, ScrapeResponse, SectorSummary,
                               SentimentSummary)
from app.services import notification_service
from tests.test_risk_scoring import MOST_TOLERANT


@compiles(JSONB, "sqlite")
def _jsonb_on_sqlite(type_, compiler, **kw):  # risk_profiles.answers
    return "JSON"


API = "/api/v1"
TEST_SECRET = "qa-only-hs256-secret-not-used-anywhere-else"
TEST_ISSUER = "https://example.com/auth/v1"
NOW = datetime.now(timezone.utc)

USER_A = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
USER_B = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000002")
USER_UNVERIFIED = uuid.UUID("cccccccc-0000-4000-8000-000000000003")


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Fail any outbound connection that is not loopback (and the fake DB port)."""
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        port = address[1] if isinstance(address, tuple) else None
        if host not in ("127.0.0.1", "::1", "localhost") or port in (1, 5432, 6543, 6379):
            raise OSError(f"QA offline guard blocked connect to {address!r}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    rate_limit._hits.clear()
    dashboard_router._insight_cache.update(key=None, at=0.0, insights=None)
    # Never let a background LLM refresh or push start.
    monkeypatch.setattr(dashboard_router, "_generate_insights", lambda *a, **k: None)
    monkeypatch.setattr(notification_service, "_dispatch_push", lambda *a, **k: None)
    yield


@pytest.fixture
def Session_(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    # Anything that opens its own session (chat stream, /health) gets SQLite too.
    monkeypatch.setattr("app.database.SessionLocal", factory)
    monkeypatch.setattr(chat_router, "SessionLocal", factory)
    seed(factory())
    return factory


class Api:
    """TestClient wrapper; `as_user(uid)` sets who get_current_user returns."""

    def __init__(self, factory):
        self.factory = factory
        self.uid = USER_A
        self.client = TestClient(app, raise_server_exceptions=False)

    def as_user(self, uid):
        self.uid = uid
        return self

    def __getattr__(self, name):  # get/post/patch/delete/request
        return getattr(self.client, name)

    def db(self):
        return self.factory()


@pytest.fixture
def api(Session_):
    a = Api(Session_)

    def get_db():
        db = Session_()
        try:
            yield db
        finally:
            db.close()

    def current_user(db=deps.Depends(deps.get_db)):
        user = db.get(User, a.uid)
        assert user is not None
        return user

    app.dependency_overrides[deps.get_db] = get_db
    app.dependency_overrides[deps.get_current_user] = current_user
    yield a
    app.dependency_overrides.clear()


@pytest.fixture
def anon(Session_):
    """Real get_current_user (only get_db overridden)."""
    def get_db():
        db = Session_()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[deps.get_db] = get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def jwt_settings(monkeypatch):
    patched = deps.get_settings().model_copy(update={
        "SUPABASE_JWT_SECRET": TEST_SECRET,
        "SUPABASE_JWT_ISSUER": TEST_ISSUER,
        "SUPABASE_JWT_AUDIENCE": "authenticated",
    })
    monkeypatch.setattr(deps, "get_settings", lambda: patched)
    # JWKS would be a network call; the project "publishes" no asymmetric keys.
    monkeypatch.setattr(deps, "_fetch_jwks", lambda force=False: {"keys": []})


def seed(db):
    db.add_all([
        User(user_id=USER_A, email="a@example.com", full_name="Alice QA",
             password_hash="x", is_email_verified=True),
        User(user_id=USER_B, email="b@example.com", full_name="Bob QA",
             password_hash="x", is_email_verified=True),
        User(user_id=USER_UNVERIFIED, email="c@example.com", full_name="Carol QA",
             password_hash="x", is_email_verified=False),
    ])
    quotes = [("JKH.N0000", 200.0, 1.5, 10000), ("HNB.N0000", 250.0, -0.5, 5000),
              ("COMB.N0000", 100.0, 0.3, 2000), ("PENNY.N0000", 0.5, 2.0, 900000)]
    for i, (sym, price, pct, vol) in enumerate(quotes):
        db.add(MarketDataLatest(symbol=sym, market_id=i + 1, price=price, change=price * pct / 100,
                                change_pct=pct, volume=vol, recorded_at=NOW))
        db.add(CompanyInfo(symbol=sym, name=f"{sym.split('.')[0]} PLC", sector="Banks",
                           sector_group="Banks" if sym != "JKH.N0000" else "Capital Goods",
                           refreshed_at=NOW))
        db.add(NewsSentiment(symbol=sym, headline=f"{sym} news", url=f"https://news.invalid/{i}",
                             sentiment_score=0.2 * (i - 1), sentiment_label="neutral",
                             published_at=NOW - timedelta(days=1), scraped_at=NOW))
    for d in range(5):
        db.add(DailyClose(symbol="JKH.N0000", trade_date=date.today() - timedelta(days=d + 1),
                          close=190.0 + d, last_traded_at=NOW))
    db.add_all([
        MarketIndexLatest(index_code="BNK", name="Banks", value=900.0, turnover=5e8, recorded_at=NOW),
        MarketIndexLatest(index_code="SPSL20", name="S&P SL20", value=6000.0, recorded_at=NOW),
        MarketIndexLatest(index_code="ASPI", name="All Share", value=21000.0, change_pct=-0.3, recorded_at=NOW),
    ])
    db.commit()
    db.close()


# ─── helpers ─────────────────────────────────────────────────────────────────

def contract(model, data):
    """The body validates against the declared model and carries no extra keys."""
    TypeAdapter(model).validate_python(data)
    rows = data if isinstance(data, list) else [data]
    inner = model.__args__[0] if getattr(model, "__args__", None) else model
    for row in rows:
        assert set(row) == set(inner.model_fields), (set(row) ^ set(inner.model_fields))


def make_token(sub=USER_A, *, secret=TEST_SECRET, exp_delta=3600, aud="authenticated",
               iss=TEST_ISSUER, **extra):
    claims = {"sub": str(sub), "exp": int(time.time()) + exp_delta, "aud": aud, "iss": iss, **extra}
    return jwt.encode(claims, secret, algorithm="HS256")


def b64(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def _uses(dependant, target):
    return any(d.call is target or _uses(d, target) for d in dependant.dependencies)


PROTECTED = sorted(
    ((m, r.path) for r in app.routes if isinstance(r, APIRoute)
     and _uses(r.dependant, deps.get_current_user) for m in r.methods),
    key=lambda x: (x[1], x[0]))

PUBLIC_ALLOWLIST = {
    ("POST", f"{API}/auth/register"), ("POST", f"{API}/auth/verify-otp"),
    ("POST", f"{API}/auth/resend-otp"), ("POST", f"{API}/auth/login"),
    ("POST", f"{API}/auth/refresh"), ("POST", f"{API}/auth/forgot-password"),
    ("POST", f"{API}/auth/verify-reset-otp"), ("POST", f"{API}/auth/reset-password"),
    ("POST", f"{API}/auth/logout"), ("GET", f"{API}/me/assessment/questions"),
    ("GET", "/health"), ("GET", "/docs"), ("GET", "/redoc"),
}


def fill(path):
    import re
    return re.sub(r"\{[^}]+\}", "1", path)


# ─── 1. authentication boundary ──────────────────────────────────────────────

def test_route_inventory_public_routes_are_exactly_the_allowlist():
    public = {(m, r.path) for r in app.routes if isinstance(r, APIRoute)
              and not _uses(r.dependant, deps.get_current_user) for m in r.methods}
    assert public == PUBLIC_ALLOWLIST
    assert len(PROTECTED) == 43


@pytest.mark.parametrize("method,path", PROTECTED, ids=[f"{m} {p}" for m, p in PROTECTED])
def test_protected_route_without_token_is_401(anon, method, path):
    r = anon.request(method, fill(path), json={})
    assert r.status_code == 401, r.text
    assert r.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize("method,path", PROTECTED, ids=[f"{m} {p}" for m, p in PROTECTED])
def test_protected_route_with_garbage_token_is_401(anon, jwt_settings, method, path):
    r = anon.request(method, fill(path), json={}, headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401, r.text


def test_valid_test_signed_token_reaches_handler(anon, jwt_settings):
    r = anon.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200
    contract(UserOut, r.json())
    assert r.json()["user_id"] == str(USER_A)


@pytest.mark.parametrize("case,token", [
    ("expired", lambda: make_token(exp_delta=-10)),
    ("wrong_secret", lambda: make_token(secret="attacker-secret")),
    ("wrong_audience", lambda: make_token(aud="anon")),
    ("wrong_issuer", lambda: make_token(iss="https://evil.invalid/auth/v1")),
    ("non_uuid_sub", lambda: make_token(sub="admin")),
    ("unprovisioned_user", lambda: make_token(sub=uuid.uuid4())),
    ("alg_none", lambda: f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': str(USER_A), 'exp': int(time.time()) + 600})}."),
    ("rs256_unknown_kid", lambda: f"{b64({'alg': 'RS256', 'kid': 'x'})}.{b64({'sub': str(USER_A)})}.c2ln"),
    ("empty_bearer", lambda: " "),
])
def test_bad_tokens_are_rejected_with_401(anon, jwt_settings, case, token):
    r = anon.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token()}"})
    assert r.status_code == 401, (case, r.status_code, r.text)
    assert "Traceback" not in r.text


def test_missing_exp_claim_is_rejected(anon, jwt_settings):
    tok = jwt.encode({"sub": str(USER_A), "aud": "authenticated", "iss": TEST_ISSUER},
                     TEST_SECRET, algorithm="HS256")
    assert anon.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


# ─── 2. validation: bad input is 422, never 500 ──────────────────────────────

BAD_BODIES = [
    ("POST", "/portfolio/", {}),
    ("POST", "/portfolio/", {"name": 123}),
    ("POST", "/portfolio/1/holdings", {"symbol": "JKH.N0000", "quantity": 0, "avg_buy_price": 10}),
    ("POST", "/portfolio/1/holdings", {"symbol": "JKH.N0000", "quantity": 1, "avg_buy_price": -1}),
    ("POST", "/portfolio/1/holdings", {"symbol": "JKH.N0000", "quantity": "lots", "avg_buy_price": 1}),
    ("POST", "/portfolio/1/holdings", {"symbol": "X" * 21, "quantity": 1, "avg_buy_price": 1}),
    ("POST", "/portfolio/1/holdings", {"quantity": 1, "avg_buy_price": 1}),
    ("POST", "/portfolio/abc/holdings", {"symbol": "JKH.N0000", "quantity": 1, "avg_buy_price": 1}),
    ("POST", "/watchlist", {"symbol": ""}),
    ("POST", "/watchlist", {"symbol": "X" * 21}),
    ("POST", "/watchlist", {"symbol": "   "}),
    ("POST", "/watchlist", {}),
    ("POST", "/rules", {"symbol": "JKH.N0000", "condition_type": "moon_phase", "threshold": 1}),
    ("POST", "/rules", {"symbol": "JKH.N0000", "condition_type": "price_above", "threshold": "high"}),
    ("POST", "/rules", {"symbol": "JKH.N0000", "condition_type": "price_above"}),
    ("PATCH", "/rules/1", {"threshold": "x"}),
    ("PATCH", "/rules/abc", {"threshold": 1}),
    ("POST", "/chat/stream", {"message": ""}),
    ("POST", "/chat/stream", {"message": "x" * 2001}),
    ("POST", "/chat/stream", {"message": "hi", "session_id": "abc"}),
    ("POST", "/chat/message", {}),
    ("PATCH", "/me", {"full_name": "A"}),
    ("PATCH", "/me", {}),
    ("POST", "/me/risk-profile", {"answers": {}}),
    ("POST", "/me/risk-profile", {"answers": {"1": "Not an option"}}),
    ("POST", "/me/risk-profile", {"answers": "nope"}),
    ("POST", "/me/language", {"language": "fr"}),
    ("POST", "/me/language", {"language": "x"}),
    ("POST", "/me/device-token", {"device_token": "short"}),
    ("PATCH", "/notifications/abc/read", None),
    ("DELETE", "/notifications/abc", None),
    ("GET", "/chat/sessions/abc/messages", None),
    ("GET", "/portfolio/1/history?range=5Y", None),
    ("GET", "/stocks/history/JKH.N0000?range=forever", None),
    ("GET", "/stocks/market?limit=0", None),
    ("GET", "/stocks/market?limit=501", None),
    ("GET", "/stocks/news/JKH.N0000?limit=101", None),
    ("POST", "/stocks/scrape?symbol=DROP%20TABLE", None),
    ("GET", "/recommendations?limit=0", None),
    ("GET", "/recommendations?limit=51", None),
    ("GET", "/recommendations?limit=ten", None),
]


@pytest.mark.parametrize("method,path,body", BAD_BODIES, ids=[f"{m} {p} {b}"[:90] for m, p, b in BAD_BODIES])
def test_invalid_input_is_422(api, method, path, body):
    db = api.db()
    db.add(Portfolio(portfolio_id=1, user_id=USER_A, name="P"))
    db.add(InvestmentRule(rule_id=1, user_id=USER_A, symbol="JKH.N0000", condition_type="price_above", threshold=1))
    db.commit()
    r = api.request(method, API + path, json=body) if body is not None else api.request(method, API + path)
    assert r.status_code == 422, (r.status_code, r.text)


PUBLIC_BAD = [
    ("/auth/register", {"email": "not-an-email", "password": "longenough", "full_name": "QA"}),
    ("/auth/register", {"email": "q@example.com", "password": "short", "full_name": "QA"}),
    ("/auth/login", {"email": "q@example.com"}),
    ("/auth/verify-otp", {"email": "q@example.com", "otp_code": "12345", "password": "longenough"}),
    ("/auth/refresh", {"refresh_token": ""}),
    ("/auth/forgot-password", {"email": "nope"}),
    ("/auth/verify-reset-otp", {"email": "q@example.com", "otp_code": "1234567"}),
    ("/auth/reset-password", {"email": "q@example.com", "reset_token": "t", "new_password": "short"}),
]


@pytest.mark.parametrize("path,body", PUBLIC_BAD, ids=[p for p, _ in PUBLIC_BAD])
def test_public_auth_validation_is_422(anon, path, body):
    assert anon.post(API + path, json=body).status_code == 422


def test_chat_whitespace_message_is_400(api):
    assert api.post(f"{API}/chat/stream", json={"message": "   "}).status_code == 400


def test_chat_messages_negative_limit_is_422(api):
    sid = api.post(f"{API}/chat/sessions").json()["session_id"]
    assert api.get(f"{API}/chat/sessions/{sid}/messages?limit=-1").status_code == 422


def test_holding_with_infinite_quantity_is_422(api):
    pid = api.post(f"{API}/portfolio/", json={"name": "P"}).json()["portfolio_id"]
    r = api.post(f"{API}/portfolio/{pid}/holdings",
                 content='{"symbol": "JKH.N0000", "quantity": Infinity, "avg_buy_price": 10}',
                 headers={"content-type": "application/json"})
    assert r.status_code == 422, r.status_code


def test_rule_with_nan_threshold_is_422(api):
    r = api.post(f"{API}/rules",
                 content='{"symbol": "JKH.N0000", "condition_type": "price_above", "threshold": NaN}',
                 headers={"content-type": "application/json"})
    assert r.status_code == 422, r.status_code


@pytest.mark.parametrize("name", ["", "x" * 121])
def test_portfolio_name_bounds_are_validated(api, name):
    assert api.post(f"{API}/portfolio/", json={"name": name}).status_code == 422


UNTYPED = ["/recommendations", "/learn/lessons", "/learn/lessons/{lesson_id}", "/dashboard/"]


@pytest.mark.xfail(strict=True, reason="BUG (contract): core mobile endpoints declare no response_model, so the "
                                        "OpenAPI schema is an untyped object/empty and shape drift is undetectable")
@pytest.mark.parametrize("path", UNTYPED)
def test_core_endpoints_publish_a_typed_response_schema(anon, path):
    op = anon.get("/openapi.json").json()["paths"][API + path]["get"]
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in schema or "properties" in schema or "items" in schema, schema


# ─── 3. happy paths + response contracts ─────────────────────────────────────

def test_risk_profile_submit_then_plan(api):
    qs = api.get(f"{API}/me/assessment/questions")
    assert qs.status_code == 200
    contract(List[QuestionOut], qs.json())

    r = api.post(f"{API}/me/risk-profile", json={"answers": MOST_TOLERANT})
    assert r.status_code == 200, r.text
    contract(RiskProfileResponse, r.json())
    assert r.json()["category"] == "High"
    assert 0 <= r.json()["score"] <= 100

    plan = api.get(f"{API}/me/plan")
    assert plan.status_code == 200
    contract(PlanOut, plan.json())
    assert plan.json()["persona"] == "growth_explorer"
    assert plan.json()["risk_category"] == "High"

    # Resubmitting updates the single row, never a second one.
    api.post(f"{API}/me/risk-profile", json={"answers": MOST_TOLERANT})
    assert api.db().query(RiskProfile).filter_by(user_id=USER_A).count() == 1


def test_plan_without_profile_is_beginner(api):
    plan = api.get(f"{API}/me/plan").json()
    contract(PlanOut, plan)
    assert plan["persona"] == "cautious_starter" and plan["risk_category"] is None


def test_portfolio_create_add_list_delete_holding(api):
    r = api.post(f"{API}/portfolio/", json={"name": "Main"})
    assert r.status_code == 201
    contract(PortfolioOut, r.json())
    pid = r.json()["portfolio_id"]

    h = api.post(f"{API}/portfolio/{pid}/holdings",
                 json={"symbol": " jkh.n0000 ", "quantity": 10, "avg_buy_price": 180})
    assert h.status_code == 201, h.text
    contract(HoldingOut, h.json())
    assert h.json()["symbol"] == "JKH.N0000"  # normalised

    unknown = api.post(f"{API}/portfolio/{pid}/holdings",
                       json={"symbol": "NOPE.N0000", "quantity": 1, "avg_buy_price": 1})
    assert unknown.status_code == 422

    lst = api.get(f"{API}/portfolio/")
    contract(List[PortfolioOut], lst.json())
    assert [x["symbol"] for x in lst.json()[0]["holdings"]] == ["JKH.N0000"]

    hist = api.get(f"{API}/portfolio/{pid}/history?range=1w")
    assert hist.status_code == 200
    contract(PortfolioHistory, hist.json())
    assert hist.json()["point_count"] == 0

    hid = h.json()["holding_id"]
    assert api.delete(f"{API}/portfolio/{pid}/holdings/{hid}").status_code == 204
    assert api.delete(f"{API}/portfolio/{pid}/holdings/{hid}").status_code == 404
    assert api.get(f"{API}/portfolio/").json()[0]["holdings"] == []


def test_watchlist_add_idempotent_list_remove(api):
    r = api.post(f"{API}/watchlist", json={"symbol": "jkh.n0000"})
    assert r.status_code == 201
    contract(WatchlistItem, r.json())
    assert r.json()["price"] == 200.0 and r.json()["name"] == "JKH PLC"
    api.post(f"{API}/watchlist", json={"symbol": "JKH.N0000"})
    lst = api.get(f"{API}/watchlist").json()
    contract(List[WatchlistItem], lst)
    assert [x["symbol"] for x in lst] == ["JKH.N0000"]

    assert api.post(f"{API}/watchlist", json={"symbol": "NOPE.N0000"}).status_code == 404
    assert api.delete(f"{API}/watchlist/jkh.n0000").status_code == 204
    assert api.get(f"{API}/watchlist").json() == []
    assert api.delete(f"{API}/watchlist/JKH.N0000").status_code == 204  # idempotent


def test_rules_crud(api):
    r = api.post(f"{API}/rules", json={"symbol": "hnb.n0000", "condition_type": "price_below", "threshold": 240})
    assert r.status_code == 201, r.text
    contract(RuleOut, r.json())
    rid = r.json()["rule_id"]
    assert r.json()["symbol"] == "HNB.N0000"

    assert api.post(f"{API}/rules", json={"symbol": "NOPE.N0000", "condition_type": "price_below",
                                          "threshold": 1}).status_code == 404

    p = api.patch(f"{API}/rules/{rid}", json={"threshold": 230, "condition_type": "price_above"})
    assert p.status_code == 200
    contract(RuleOut, p.json())
    assert (p.json()["threshold"], p.json()["condition_type"]) == (230, "price_above")
    assert api.patch(f"{API}/rules/{rid}", json={"condition_type": "bogus"}).status_code == 422

    lst = api.get(f"{API}/rules").json()
    contract(List[RuleOut], lst)
    assert len(lst) == 1
    assert api.delete(f"{API}/rules/{rid}").status_code == 204
    assert api.get(f"{API}/rules").json() == []
    assert api.patch(f"{API}/rules/{rid}", json={"threshold": 1}).status_code == 404


def test_recommendations_contract_and_rules(api):
    db = api.db()
    db.add(Portfolio(portfolio_id=7, user_id=USER_A, name="P"))
    db.add(PortfolioHolding(portfolio_id=7, symbol="HNB.N0000", quantity=1, avg_buy_price=1))
    db.commit()

    r = api.get(f"{API}/recommendations?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"model_version", "weights", "risk_category", "factor_labels", "count", "items"}
    assert abs(sum(body["weights"].values()) - 1.0) < 1e-6
    items = body["items"]
    assert items, body
    for it in items:
        assert {"symbol", "name", "score", "factors"} <= set(it)
        assert isinstance(it["symbol"], str) and isinstance(it["score"], (int, float))
        assert -100 <= it["score"] <= 100
        assert isinstance(it["factors"], dict) and len(it["factors"]) >= 3
        assert it["price"] >= 1.0
    syms = [i["symbol"] for i in items]
    assert "HNB.N0000" not in syms          # already held
    assert "PENNY.N0000" not in syms        # under Rs 1
    assert [i["score"] for i in items] == sorted((i["score"] for i in items), reverse=True)

    # Isolation: B holds nothing, so B does see HNB.
    assert "HNB.N0000" in [i["symbol"] for i in api.as_user(USER_B).get(f"{API}/recommendations").json()["items"]]
    assert len(api.get(f"{API}/recommendations?limit=1").json()["items"]) == 1


def test_learn_lessons_list_and_detail(api):
    r = api.get(f"{API}/learn/lessons")
    assert r.status_code == 200
    lessons = r.json()
    assert len(lessons) == 9
    for l in lessons:
        assert set(l) == {"id", "title", "theme", "minutes", "summary"}
    d = api.get(f"{API}/learn/lessons/{lessons[0]['id']}")
    assert d.status_code == 200
    assert set(d.json()) == {"id", "title", "theme", "minutes", "summary", "key_terms", "sections"}
    assert all(set(s) == {"heading", "body"} for s in d.json()["sections"])
    assert api.db().query(LessonView).filter_by(user_id=USER_A).count() == 1
    assert api.get(f"{API}/learn/lessons/does-not-exist").status_code == 404


def test_stocks_endpoints(api, monkeypatch):
    m = api.get(f"{API}/stocks/market")
    assert m.status_code == 200
    contract(List[MarketData], m.json())
    assert [x["symbol"] for x in m.json()] == sorted(x["symbol"] for x in m.json())
    banks = api.get(f"{API}/stocks/market?sector=%20banks%20").json()
    assert {x["symbol"] for x in banks} == {"HNB.N0000", "COMB.N0000", "PENNY.N0000"}
    assert [x["symbol"] for x in api.get(f"{API}/stocks/market?symbol=jkh.n0000").json()] == ["JKH.N0000"]

    s = api.get(f"{API}/stocks/sectors")
    contract(List[SectorSummary], s.json())
    assert s.json()[0] == {"sector": "Banks", "count": 3}

    c = api.get(f"{API}/stocks/company/jkh.n0000")
    assert c.status_code == 200
    contract(CompanyInfoOut, c.json())
    assert api.get(f"{API}/stocks/company/NOPE").status_code == 404

    i = api.get(f"{API}/stocks/indices")
    contract(List[MarketIndex], i.json())
    assert [x["index_code"] for x in i.json()] == ["ASPI", "SPSL20", "BNK"]

    h = api.get(f"{API}/stocks/history/JKH.N0000?range=1M")
    contract(PriceHistory, h.json())
    assert h.json()["point_count"] == 5
    assert api.get(f"{API}/stocks/history/NOPE?range=1M").json()["point_count"] == 0

    n = api.get(f"{API}/stocks/news/jkh.n0000")
    contract(List[NewsOut], n.json())
    assert len(n.json()) == 1

    se = api.get(f"{API}/stocks/sentiment/COMB.N0000")
    contract(SentimentSummary, se.json())
    assert se.json()["count"] == 1
    none = api.get(f"{API}/stocks/sentiment/NOPE").json()
    assert none["avg_score"] is None and none["label"] == "none"

    import tasks.scrape_tasks as st
    calls = []
    for name in ("scrape_cse_data", "scrape_cse_indices", "scrape_and_analyse_news"):
        monkeypatch.setattr(getattr(st, name), "delay", lambda *a, _n=name: calls.append(_n))
    sc = api.post(f"{API}/stocks/scrape")
    assert sc.status_code == 202
    contract(ScrapeResponse, sc.json())
    assert len(calls) == 3


def test_scrape_is_hidden_in_production(api, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert api.post(f"{API}/stocks/scrape").status_code == 404
    assert api.post(f"{API}/notifications/test").status_code == 404


def test_dashboard_contract_and_personal_data(api):
    db = api.db()
    db.add(Watchlist(user_id=USER_A, symbol="JKH.N0000"))
    db.add(Portfolio(portfolio_id=3, user_id=USER_A, name="P"))
    db.add(PortfolioHolding(portfolio_id=3, symbol="JKH.N0000", quantity=2, avg_buy_price=100))
    db.commit()
    r = api.get(f"{API}/dashboard/")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"aspi", "sectors", "portfolio", "insights", "watchlist_preview"}
    assert body["aspi"]["value"] == 21000.0
    assert body["portfolio"]["current_value"] == 400.0      # 2 x live 200
    assert body["portfolio"]["target_value"] is None
    assert body["portfolio"]["history"] == []
    assert [w["symbol"] for w in body["watchlist_preview"]] == ["JKH.N0000"]
    assert body["insights"] and all({"id", "label", "body", "buttonText"} <= set(i) for i in body["insights"])
    assert not any(i["buttonText"].lower() in ("buy", "sell", "trade") for i in body["insights"])

    b = api.as_user(USER_B).get(f"{API}/dashboard/").json()
    assert b["watchlist_preview"] == [] and b["portfolio"]["current_value"] == 0


def test_notifications_flow(api):
    db = api.db()
    db.add_all([Notification(user_id=USER_A, type="ALERT", message=f"m{i}", is_read=False) for i in range(3)])
    db.commit()
    lst = api.get(f"{API}/notifications/")
    assert lst.status_code == 200
    contract(List[NotificationOut], lst.json())
    nid = lst.json()[0]["notif_id"]
    rd = api.patch(f"{API}/notifications/{nid}/read")
    contract(NotificationOut, rd.json())
    assert rd.json()["is_read"] is True
    assert api.post(f"{API}/notifications/read-all").json() == {"marked_read": 2}
    assert api.delete(f"{API}/notifications/{nid}").status_code == 204
    assert len(api.get(f"{API}/notifications/").json()) == 2
    assert api.patch(f"{API}/notifications/999/read").status_code == 404


def test_notifications_test_endpoint_contract(api):
    r = api.post(f"{API}/notifications/test")
    assert r.status_code == 200, r.text
    assert {"notif_id", "type", "message", "is_read"} <= set(r.json())


def test_device_token_and_language(api):
    r = api.post(f"{API}/me/device-token", json={"device_token": "fcm-token-1234567890"})
    assert r.status_code == 200, r.text
    contract(UserOut, r.json())
    # The same phone signing in as B moves the token to B.
    api.as_user(USER_B).post(f"{API}/me/device-token", json={"device_token": "fcm-token-1234567890"})
    db = api.db()
    assert db.query(UserProfile).filter_by(user_id=USER_A).one().device_token is None
    assert db.query(UserProfile).filter_by(user_id=USER_B).one().device_token == "fcm-token-1234567890"

    lang = api.as_user(USER_A).post(f"{API}/me/language", json={"language": " TA "})
    assert lang.status_code == 200
    assert api.db().query(UserProfile).filter_by(user_id=USER_A).one().language == "ta"
    assert api.as_user(USER_B).delete(f"{API}/me/device-token").status_code == 204
    assert api.db().query(UserProfile).filter_by(user_id=USER_B).one().device_token is None


def test_update_profile_name(api):
    r = api.patch(f"{API}/me", json={"full_name": "  Alice Q  "})
    assert r.status_code == 200
    contract(UserOut, r.json())
    assert r.json()["full_name"] == "Alice Q"


def test_auth_me_and_logout_without_token(api):
    contract(UserOut, api.get(f"{API}/auth/me").json())
    r = api.post(f"{API}/auth/logout")
    assert r.status_code == 200 and r.json() == {"message": "Logged out successfully"}


def test_login_unknown_and_unverified_never_reach_supabase(anon):
    assert anon.post(f"{API}/auth/login", json={"email": "ghost@example.com", "password": "x"}).status_code == 401
    assert anon.post(f"{API}/auth/login", json={"email": "C@EXAMPLE.com", "password": "x"}).status_code == 403


def test_auth_rate_limit_is_429_after_10(anon):
    codes = [anon.post(f"{API}/auth/login", json={"email": "ghost@example.com", "password": "x"}).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_health_uses_db(anon):
    r = anon.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"
    assert "x-response-time-ms" in r.headers


def test_chat_sessions_stream_and_message(api, monkeypatch):
    s = api.post(f"{API}/chat/sessions")
    assert s.status_code == 201
    contract(SessionOut, s.json())
    sid = s.json()["session_id"]

    async def fake_stream(user_message, session_id, db, user):
        db.add(ChatMessage(session_id=session_id, sender_type="user", content=user_message,
                               timestamp=datetime.now(timezone.utc)))
        db.commit()
        yield f"data: {json.dumps({'type': 'token', 'content': 'ok'})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'message_id': 1})}\n\n"

    async def fake_run(user_message, session_id, db, user):
        db.add(ChatMessage(session_id=session_id, sender_type="assistant", content="answer",
                               timestamp=datetime.now(timezone.utc)))
        db.commit()
        return "answer", [{"tool": "get_market_overview"}]

    monkeypatch.setattr(chat_router, "stream_agent", fake_stream)
    monkeypatch.setattr(chat_router, "run_agent", fake_run)

    st = api.post(f"{API}/chat/stream", json={"message": "What is ASPI?", "session_id": sid})
    assert st.status_code == 200
    assert st.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(l[6:]) for l in st.text.splitlines() if l.startswith("data: ")]
    assert [e["type"] for e in events] == ["token", "done"]

    m = api.post(f"{API}/chat/message", json={"message": "hi", "session_id": sid})
    assert m.status_code == 200, m.text
    contract(SendMessageResponse, m.json())
    assert m.json()["tools_used"] == ["get_market_overview"]

    msgs = api.get(f"{API}/chat/sessions/{sid}/messages")
    contract(List[MessageOut], msgs.json())
    assert [x["sender_type"] for x in msgs.json()] == ["user", "assistant"]

    lst = api.get(f"{API}/chat/sessions").json()
    contract(List[SessionOut], lst)
    assert lst[0]["message_count"] == 2
    assert lst[0]["title"] == "What is ASPI?"          # first question names the chat
    assert lst[0]["last_activity"] is not None
    # An empty new chat is still listed (sorted by its start time).
    newer = api.post(f"{API}/chat/sessions").json()["session_id"]
    ids = [x["session_id"] for x in api.get(f"{API}/chat/sessions").json()]
    assert set(ids) == {sid, newer}
    api.delete(f"{API}/chat/sessions/{newer}")
    assert api.delete(f"{API}/chat/sessions/{sid}").status_code == 204
    assert api.get(f"{API}/chat/sessions?active_only=true").json() == []


def test_chat_rate_limit(api, monkeypatch):
    async def fake_stream(**kw):
        yield "data: {}\n\n"
    monkeypatch.setattr(chat_router, "stream_agent", fake_stream)
    sid = api.post(f"{API}/chat/sessions").json()["session_id"]
    codes = [api.post(f"{API}/chat/stream", json={"message": "hi", "session_id": sid}).status_code
             for _ in range(11)]
    assert codes[-1] == 429 and set(codes[:10]) == {200}


# ─── 4. user-data isolation (A owns it, B attacks it) ────────────────────────

@pytest.fixture
def a_data(api):
    db = api.db()
    p = Portfolio(user_id=USER_A, name="A's")
    s = ChatSession(user_id=USER_A, is_active=True)
    db.add_all([p, s])
    db.flush()
    h = PortfolioHolding(portfolio_id=p.portfolio_id, symbol="JKH.N0000", quantity=5, avg_buy_price=150)
    rule = InvestmentRule(user_id=USER_A, symbol="JKH.N0000", condition_type="price_above", threshold=300)
    n = Notification(user_id=USER_A, type="ALERT", message="secret alert", is_read=False)
    db.add_all([h, rule, n, Watchlist(user_id=USER_A, symbol="JKH.N0000"),
                ChatMessage(session_id=s.session_id, sender_type="user", content="my private question")])
    db.commit()
    ids = dict(pid=p.portfolio_id, hid=h.holding_id, rid=rule.rule_id, sid=s.session_id, nid=n.notif_id)
    db.close()
    api.as_user(USER_B)
    return ids


def test_isolation_portfolio(api, a_data):
    assert api.get(f"{API}/portfolio/").json() == []
    assert api.get(f"{API}/portfolio/{a_data['pid']}/history").status_code == 404
    assert api.post(f"{API}/portfolio/{a_data['pid']}/holdings",
                    json={"symbol": "JKH.N0000", "quantity": 1, "avg_buy_price": 1}).status_code == 404
    assert api.delete(f"{API}/portfolio/{a_data['pid']}/holdings/{a_data['hid']}").status_code == 404
    # B's own portfolio + A's holding id: still not deletable.
    bp = api.post(f"{API}/portfolio/", json={"name": "B"}).json()["portfolio_id"]
    assert api.delete(f"{API}/portfolio/{bp}/holdings/{a_data['hid']}").status_code == 404
    assert api.db().get(PortfolioHolding, a_data["hid"]) is not None


def test_isolation_watchlist(api, a_data):
    assert api.get(f"{API}/watchlist").json() == []
    assert api.delete(f"{API}/watchlist/JKH.N0000").status_code == 204
    assert api.db().query(Watchlist).filter_by(user_id=USER_A).count() == 1


def test_isolation_rules(api, a_data):
    assert api.get(f"{API}/rules").json() == []
    assert api.patch(f"{API}/rules/{a_data['rid']}", json={"threshold": 1}).status_code == 404
    assert api.delete(f"{API}/rules/{a_data['rid']}").status_code == 204
    rule = api.db().get(InvestmentRule, a_data["rid"])
    assert rule is not None and rule.threshold == 300


def test_isolation_chat(api, a_data, monkeypatch):
    async def must_not_run(**kw):
        raise AssertionError("agent ran on another user's session")
        yield  # pragma: no cover
    monkeypatch.setattr(chat_router, "stream_agent", must_not_run)
    monkeypatch.setattr(chat_router, "run_agent", must_not_run)

    assert api.get(f"{API}/chat/sessions").json() == []
    r = api.get(f"{API}/chat/sessions/{a_data['sid']}/messages")
    assert r.status_code == 404 and "private" not in r.text
    assert api.delete(f"{API}/chat/sessions/{a_data['sid']}").status_code == 404
    assert api.post(f"{API}/chat/stream", json={"message": "hi", "session_id": a_data["sid"]}).status_code == 404
    assert api.post(f"{API}/chat/message", json={"message": "hi", "session_id": a_data["sid"]}).status_code == 404
    assert api.db().get(ChatSession, a_data["sid"]).is_active is True


def test_isolation_notifications(api, a_data):
    assert api.get(f"{API}/notifications/").json() == []
    assert api.patch(f"{API}/notifications/{a_data['nid']}/read").status_code == 404
    assert api.post(f"{API}/notifications/read-all").json() == {"marked_read": 0}
    assert api.delete(f"{API}/notifications/{a_data['nid']}").status_code == 204
    n = api.db().get(Notification, a_data["nid"])
    assert n is not None and n.is_read is False


def test_isolation_plan_and_dashboard(api, a_data):
    plan = api.get(f"{API}/me/plan").json()
    assert not any(s["done"] for s in plan["steps"])
    assert api.get(f"{API}/dashboard/").json()["watchlist_preview"] == []


def test_market_session_notices(Session_):
    from app.services.notification_service import notify_market_session
    from app.services.portfolio_history import exchange_today

    db = Session_()
    users = db.query(User).count()
    db.add(UserProfile(user_id=USER_B, full_name="Bob QA", language="ta"))
    db.commit()

    # Open: only when cse.lk says the market is open, and only once a day.
    assert notify_market_session(db, "market_open", "Market Close") == 0
    assert notify_market_session(db, "market_open", "Regular Trading - Market Open") == users
    assert notify_market_session(db, "market_open", "Regular Trading - Market Open") == 0

    # Close: nothing on a day with no trading recorded (a holiday)...
    assert notify_market_session(db, "market_close", None) == 0
    db.add(DailyClose(symbol="JKH.N0000", trade_date=exchange_today(), close=20.0,
                      last_traded_at=datetime.now(timezone.utc)))
    db.commit()
    # ...then once, with the ASPI, in each user's language.
    assert notify_market_session(db, "market_close", None) == users
    msgs = {n.user_id: n.message for n in db.query(Notification).filter(Notification.type == "market_close")}
    assert msgs[USER_A] == "The market has closed for today. ASPI 21,000.00 (-0.30%)."
    assert msgs[USER_B].startswith("இன்றைய சந்தை மூடப்பட்டது.")


def test_pending_followup_reads_the_chat(Session_):
    """followup.py step 2: a follow-up is pending only right after the bot asked one."""
    from app.services.agent.followup import FOLLOWUP_TAG, pending_followup
    db = Session_()
    s = ChatSession(user_id=USER_A, is_active=True, start_time=datetime.now(timezone.utc))
    db.add(s)
    db.commit()
    t0 = datetime.now(timezone.utc)

    def say(sender, text, tag=None, secs=0):
        db.add(ChatMessage(session_id=s.session_id, sender_type=sender, content=text,
                           ai_model_used=tag, timestamp=t0 + timedelta(seconds=secs)))
        db.commit()

    assert pending_followup(db, s.session_id) is None                       # empty chat
    say("user", "Which stock?", secs=1)
    say("assistant", "Your goal? OPTIONS: Growth | Income", FOLLOWUP_TAG, secs=2)
    assert pending_followup(db, s.session_id) == ("Which stock?", "Your goal? OPTIONS: Growth | Income")
    say("user", "Income", secs=3)
    say("assistant", "Here is the answer.", "nvidia", secs=4)
    assert pending_followup(db, s.session_id) is None                       # answered: next is a new question
