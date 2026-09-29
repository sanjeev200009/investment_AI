"""Offline regression tests for the auth/push audit fixes. No DB, no network."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from gotrue.errors import AuthRetryableError

from app.routers import auth
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import email_service, fcm


def test_request_emails_are_lowercased_and_trimmed():
    assert LoginRequest(email=" John@Example.COM ", password="x").email == "john@example.com"
    assert RegisterRequest(email="A.B@X.com", password="12345678",
                           full_name="Al").email == "a.b@x.com"


class _Outage:
    def sign_in_with_password(self, _):
        raise AuthRetryableError("connection refused", 0)

    def refresh_session(self, _):
        raise AuthRetryableError("connection refused", 0)


@pytest.fixture
def supabase_down(monkeypatch):
    monkeypatch.setattr(auth, "get_supabase", lambda: SimpleNamespace(auth=_Outage()))
    monkeypatch.setattr(auth, "_user_by_email", lambda db, email: SimpleNamespace(
        is_email_verified=True, full_name="X"))


def test_login_reports_supabase_outage_as_503_not_bad_password(supabase_down):
    with pytest.raises(HTTPException) as e:
        auth.login(LoginRequest(email="a@b.com", password="x"), db=None)
    assert e.value.status_code == 503


def test_refresh_reports_supabase_outage_as_503_not_signed_out(supabase_down):
    with pytest.raises(HTTPException) as e:
        auth.refresh_session(auth.RefreshRequest(refresh_token="t"), db=None)
    assert e.value.status_code == 503


def test_email_templates_escape_the_callers_name(monkeypatch):
    sent = []
    monkeypatch.setattr(email_service, "_send", lambda to, subj, html: sent.append(html))
    email_service.send_registration_otp("a@b.com", "123456", '<a href="http://evil">x</a>')
    email_service.send_welcome_email("a@b.com", "<script>")
    assert all("<a href" not in h and "<script>" not in h for h in sent)
    assert "&lt;a href" in sent[0]


class _Unregistered(Exception):
    pass


class _FakeMessaging:
    UnregisteredError = _Unregistered
    SenderIdMismatchError = type("SenderIdMismatch", (Exception,), {})

    def Message(self, **kw):
        return kw

    def Notification(self, **kw):
        return kw

    def AndroidConfig(self, **kw):
        return kw

    def send(self, message):
        raise _Unregistered()


class _FakeDB:
    def __init__(self, user):
        self.user, self.commits = user, 0

    def query(self, *_):
        return self

    def filter(self, *_):
        return self

    def first(self):
        return self.user

    def commit(self):
        self.commits += 1


def test_unregistered_token_is_cleared(monkeypatch):
    monkeypatch.setattr(fcm, "_get_messaging", lambda: _FakeMessaging())
    user = SimpleNamespace(profile=SimpleNamespace(device_token="dead-token-123"))
    db = _FakeDB(user)
    ok = asyncio.run(fcm.send_push_to_user(db, "u1", "t", "b"))
    assert ok is False
    assert user.profile.device_token is None and db.commits == 1


def test_rule_push_tolerates_missing_change_pct(monkeypatch):
    import app.database
    import app.services.fcm as fcm_mod
    from tasks import rules_tasks

    sent = {}

    async def fake_push(db, user_id, title, body, data):
        sent["body"] = body
        return True

    monkeypatch.setattr(fcm_mod, "send_push_to_user", fake_push)
    monkeypatch.setattr(app.database, "SessionLocal",
                        lambda: SimpleNamespace(close=lambda: None))
    asyncio.run(rules_tasks._async_send_push(
        "u1", "JKH.N0000", "price_above", 100.0, 101.5, None, 7))
    assert "+0.00%" in sent["body"]


def test_reset_token_survives_a_failed_supabase_update(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.otp import PasswordResetToken
    from app.schemas.auth import ResetPasswordRequest
    from app.utils.security import create_reset_token

    engine = create_engine("sqlite://")
    PasswordResetToken.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    token = create_reset_token(db, "a@b.com")

    calls = []

    def update_user_by_id(uid, attrs):
        calls.append(uid)
        if len(calls) == 1:
            raise RuntimeError("supabase down")

    admin = SimpleNamespace(auth=SimpleNamespace(admin=SimpleNamespace(
        update_user_by_id=update_user_by_id)))
    monkeypatch.setattr(auth, "create_client", lambda *a: admin)
    monkeypatch.setattr(auth, "_user_by_email",
                        lambda db, email: SimpleNamespace(user_id="u1"))
    req = ResetPasswordRequest(email="a@b.com", reset_token=token,
                               new_password="newpass123")

    with pytest.raises(HTTPException) as e:
        auth.reset_password(req, db=db)
    assert e.value.status_code == 503
    assert auth.reset_password(req, db=db)["message"].startswith("Password reset")
    with pytest.raises(HTTPException) as e:  # now spent
        auth.reset_password(req, db=db)
    assert e.value.status_code == 400
    db.close()


class _RecDB:
    """Records bulk deletes and commits; .get() answers from a dict."""

    def __init__(self, found=None, first=None):
        self.deleted, self.commits, self.found, self._first = [], 0, found or {}, first

    def query(self, model):
        self._model = model
        return self

    def filter(self, *_):
        return self

    def first(self):
        return self._first

    def delete(self, synchronize_session=None):
        self.deleted.append(self._model.__tablename__)

    def get(self, model, key):
        return self.found.get(key)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def _admin(delete_user):
    return SimpleNamespace(auth=SimpleNamespace(admin=SimpleNamespace(
        delete_user=delete_user)))


def test_delete_account_supabase_failure_is_503_and_keeps_local_data(monkeypatch):
    import supabase
    from app.routers import user as user_router

    def boom(uid):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(supabase, "create_client", lambda *a: _admin(boom))
    db = _RecDB()
    with pytest.raises(HTTPException) as e:
        user_router.delete_account(db=db, user=SimpleNamespace(user_id="u1", email="A@b.com"))
    assert e.value.status_code == 503
    assert db.deleted == [] and db.commits == 0


def test_delete_account_removes_user_and_email_keyed_rows(monkeypatch):
    import supabase
    from gotrue.errors import AuthApiError
    from app.routers import user as user_router

    def already_gone(uid):
        raise AuthApiError("User not found", 404, "user_not_found")

    for delete_user in (lambda uid: None, already_gone):
        monkeypatch.setattr(supabase, "create_client", lambda *a: _admin(delete_user))
        db = _RecDB()
        assert user_router.delete_account(
            db=db, user=SimpleNamespace(user_id="u1", email="a@b.com")) is None
        assert db.deleted == ["otp_codes", "password_reset_tokens", "users"]
        assert db.commits == 1


def test_delete_account_route_is_delete_me():
    from app.routers.user import router
    assert any(r.path == "/me" and "DELETE" in r.methods for r in router.routes)


def test_add_holding_rejects_unknown_symbol_with_422():
    from app.routers.portfolio import add_holding
    from app.schemas.portfolio import HoldingCreate

    db = _RecDB(found={}, first=SimpleNamespace(portfolio_id=1))
    with pytest.raises(HTTPException) as e:
        add_holding(1, HoldingCreate(symbol="nope.n0000", quantity=1, avg_buy_price=10),
                    db=db, user=SimpleNamespace(user_id="u1"))
    assert e.value.status_code == 422 and "NOPE.N0000" in e.value.detail
