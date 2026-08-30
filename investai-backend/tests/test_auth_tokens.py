"""Negative tests for Supabase access-token verification.

The point of I-02 is not that a valid login works — it is that an *invalid* token
is refused. Before this, ``get_current_user`` called
``jwt.get_unverified_claims`` and auto-created an account for any ``sub`` it had
not seen, so a self-signed token granted access to a brand-new user. Each test
below corresponds to an attack that previously succeeded.

Tokens are minted here rather than captured from a real login: that lets the
suite assert on tampering and expiry, which a captured token cannot demonstrate,
and it runs with no network and no database.

    python -m pytest tests/test_auth_tokens.py -v
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app import dependencies as deps
from app.config import get_settings

SECRET = "test-jwt-secret-not-a-real-one"
WRONG_SECRET = "attacker-does-not-know-the-secret"
SUPABASE_URL = "https://testproject.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
USER_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def settings_for_hs256():
    """Point the verifier at a legacy HS256 project, then restore."""
    s = get_settings()
    fields = ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_JWT_AUDIENCE",
              "SUPABASE_JWT_ISSUER", "SUPABASE_ANON_KEY")
    saved = {f: getattr(s, f) for f in fields}
    s.SUPABASE_URL = SUPABASE_URL
    s.SUPABASE_JWT_SECRET = SECRET
    s.SUPABASE_JWT_AUDIENCE = "authenticated"
    s.SUPABASE_JWT_ISSUER = ""
    s.SUPABASE_ANON_KEY = "test-anon-key"
    # never let a test hit a real JWKS endpoint
    deps._jwks, deps._jwks_fetched_at = None, 0.0
    yield s
    for f, v in saved.items():
        setattr(s, f, v)
    deps._jwks, deps._jwks_fetched_at = None, 0.0


class FakeQuery:
    def __init__(self, result, raises=None):
        self._result, self._raises = result, raises

    def filter(self, *_a, **_kw):
        return self

    def first(self):
        if self._raises:
            raise self._raises
        return self._result


class FakeDB:
    """Minimal stand-in for a Session — these tests are about auth, not SQL."""

    def __init__(self, user=None, raises=None):
        self._user, self._raises = user, raises

    def query(self, _model):
        return FakeQuery(self._user, self._raises)


class FakeUser:
    def __init__(self, user_id=USER_ID):
        self.user_id = user_id
        self.email = "real.person@example.com"


def make_token(secret=SECRET, alg="HS256", **overrides) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(USER_ID),
        "iss": ISSUER,
        "aud": "authenticated",
        "role": "authenticated",
        "email": "real.person@example.com",
        "exp": now + timedelta(hours=1),
        "iat": now,
    }
    claims.update(overrides)
    for k in [k for k, v in claims.items() if v is None]:
        del claims[k]
    return jwt.encode(claims, secret, algorithm=alg)


def creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(obj).encode()).rstrip(b"=").decode()


# ---------------------------------------------------------------------------
# the happy path must still work
# ---------------------------------------------------------------------------
def test_valid_token_is_accepted():
    claims = deps.verify_supabase_token(make_token())
    assert claims["sub"] == str(USER_ID)


def test_valid_token_resolves_to_the_matching_user():
    user = deps.get_current_user(creds(make_token()), FakeDB(FakeUser()))
    assert user.user_id == USER_ID


# ---------------------------------------------------------------------------
# C-1: forged and tampered tokens
# ---------------------------------------------------------------------------
def test_token_signed_with_wrong_secret_is_rejected():
    """The core of C-1. An attacker self-signs a token for any account."""
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token(secret=WRONG_SECRET)),
                              FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_tampered_sub_is_rejected():
    """Take a legitimately signed token and swap the sub for a victim's."""
    victim = "99999999-8888-7777-6666-555555555555"
    header_b64, payload_b64, sig = make_token().split(".")
    payload = json.loads(base64.urlsafe_b64decode(
        payload_b64 + "=" * (-len(payload_b64) % 4)))
    payload["sub"] = victim
    forged = f"{header_b64}.{_b64(payload)}.{sig}"

    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(forged), FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_alg_none_is_rejected():
    """Strip the signature and declare alg=none — the classic JWT bypass."""
    now = datetime.now(timezone.utc)
    unsigned = "{}.{}.".format(
        _b64({"alg": "none", "typ": "JWT"}),
        _b64({"sub": str(USER_ID), "iss": ISSUER, "aud": "authenticated",
              "exp": int((now + timedelta(hours=1)).timestamp())}),
    )
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(unsigned), FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_unsigned_claims_are_never_trusted():
    """Guard against a regression to jwt.get_unverified_claims: a token whose
    payload is perfectly well-formed but whose signature is garbage must fail."""
    header_b64, payload_b64, _ = make_token().split(".")
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(f"{header_b64}.{payload_b64}.deadbeef"),
                              FakeDB(FakeUser()))
    assert e.value.status_code == 401


# ---------------------------------------------------------------------------
# claim validation
# ---------------------------------------------------------------------------
def test_expired_token_is_rejected():
    now = datetime.now(timezone.utc)
    stale = make_token(exp=now - timedelta(minutes=1), iat=now - timedelta(hours=2))
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(stale), FakeDB(FakeUser()))
    assert e.value.status_code == 401
    assert "expired" in e.value.detail.lower()


def test_token_from_another_supabase_project_is_rejected():
    """A valid token from a different project must not authenticate here."""
    other = make_token(iss="https://someoneelse.supabase.co/auth/v1")
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(other), FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_wrong_audience_is_rejected():
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token(aud="anon")), FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_missing_sub_is_rejected():
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token(sub=None)), FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_non_uuid_sub_is_rejected():
    """The old code used sub to build an email, so any string worked."""
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token(sub="not-a-uuid")),
                              FakeDB(FakeUser()))
    assert e.value.status_code == 401


# ---------------------------------------------------------------------------
# header handling
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [None, "", "   "])
def test_missing_or_blank_token_is_rejected(bad):
    c = None if bad is None else creds(bad)
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(c, FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_garbage_token_is_rejected():
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds("not.a.jwt"), FakeDB(FakeUser()))
    assert e.value.status_code == 401


# ---------------------------------------------------------------------------
# no silent account creation, and infra errors are not auth errors
# ---------------------------------------------------------------------------
def test_verified_token_for_unknown_user_does_not_create_an_account():
    """Previously this auto-provisioned a user. It must now 401 instead."""
    db = FakeDB(user=None)
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token()), db)
    assert e.value.status_code == 401
    assert "provision" in e.value.detail.lower()


def test_database_error_is_503_not_401():
    """A dead database previously reported 'Invalid authentication token'."""
    from sqlalchemy.exc import OperationalError
    db = FakeDB(raises=OperationalError("select 1", {}, Exception("down")))
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token()), db)
    assert e.value.status_code == 503


def test_hs256_without_secret_on_an_hs256_project_is_503_not_401(monkeypatch):
    """Misconfiguration must be loud, not look like a bad password to the user.

    "No shared secret AND no published keys" is the genuinely ambiguous case:
    the server cannot verify anything, which is its own fault, not the client's.
    """
    _serve_jwks(monkeypatch)                    # project publishes no keys
    get_settings().SUPABASE_JWT_SECRET = ""
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token()), FakeDB(FakeUser()))
    assert e.value.status_code == 503


def test_hs256_token_on_an_asymmetric_project_is_401_not_503(monkeypatch,
                                                             rsa_keypair):
    """An HS256 token aimed at a JWKS-signing project is forged, not a misconfig.

    The status code carries weight beyond tidiness: 503 is retryable, and the
    mobile client deliberately keeps its stored token on any non-401 so a
    backend outage cannot sign people out. Reporting a permanently unusable
    token as 503 would make the app hold it forever instead of clearing it.
    """
    _, pub_jwk = rsa_keypair
    _serve_jwks(monkeypatch, pub_jwk)           # project signs asymmetrically
    get_settings().SUPABASE_JWT_SECRET = ""
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token()), FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_unreachable_jwks_does_not_call_a_token_forged(monkeypatch):
    """"I can't check" must not be reported as "that token is fake"."""
    def _boom(force=False):
        raise HTTPException(503, "Authentication service unavailable")
    monkeypatch.setattr(deps, "_fetch_jwks", _boom)
    get_settings().SUPABASE_JWT_SECRET = ""
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(make_token()), FakeDB(FakeUser()))
    assert e.value.status_code == 503


# ---------------------------------------------------------------------------
# asymmetric (current Supabase projects) — verified via JWKS
# ---------------------------------------------------------------------------
@pytest.fixture
def rsa_keypair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jose import jwk

    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_jwk = jwk.construct(pem, algorithm="RS256").public_key().to_dict()
    pub_jwk = {k: (v.decode() if isinstance(v, bytes) else v)
               for k, v in pub_jwk.items()}
    pub_jwk.update(kid="test-key-1", alg="RS256", use="sig")
    return pem, pub_jwk


def _serve_jwks(monkeypatch, *keys):
    monkeypatch.setattr(deps, "_fetch_jwks",
                        lambda force=False: {"keys": list(keys)})


def test_asymmetric_token_is_accepted_via_jwks(monkeypatch, rsa_keypair):
    pem, pub_jwk = rsa_keypair
    _serve_jwks(monkeypatch, pub_jwk)
    get_settings().SUPABASE_JWT_SECRET = ""  # asymmetric projects have no secret

    token = jwt.encode(
        {"sub": str(USER_ID), "iss": ISSUER, "aud": "authenticated",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        pem, algorithm="RS256", headers={"kid": "test-key-1"})

    user = deps.get_current_user(creds(token), FakeDB(FakeUser()))
    assert user.user_id == USER_ID


def test_asymmetric_token_signed_by_an_unknown_key_is_rejected(monkeypatch,
                                                               rsa_keypair):
    """Attacker generates their own keypair and signs a token with it."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    _, pub_jwk = rsa_keypair
    _serve_jwks(monkeypatch, pub_jwk)          # server trusts only this key
    get_settings().SUPABASE_JWT_SECRET = ""

    rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue_pem = rogue.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    token = jwt.encode(
        {"sub": str(USER_ID), "iss": ISSUER, "aud": "authenticated",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        rogue_pem, algorithm="RS256", headers={"kid": "test-key-1"})

    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(token), FakeDB(FakeUser()))
    assert e.value.status_code == 401


def test_unknown_kid_is_rejected(monkeypatch, rsa_keypair):
    pem, pub_jwk = rsa_keypair
    _serve_jwks(monkeypatch, pub_jwk)
    get_settings().SUPABASE_JWT_SECRET = ""

    token = jwt.encode(
        {"sub": str(USER_ID), "iss": ISSUER, "aud": "authenticated",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        pem, algorithm="RS256", headers={"kid": "rotated-away"})

    with pytest.raises(HTTPException) as e:
        deps.get_current_user(creds(token), FakeDB(FakeUser()))
    assert e.value.status_code == 401
