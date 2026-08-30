"""Request-scoped dependencies: database session and authenticated user.

The auth story here is the fix for the project's most severe defect. The previous
implementation called ``jwt.get_unverified_claims(token)`` — no signature check,
no expiry check, no issuer check — then looked the user up by a *synthesised*
email ``f"{sub}@clerk.local"`` and **created an account** if none existed. Any
self-signed token therefore granted access to a freshly provisioned user, and the
rows it created were disjoint from the real ones written by ``/auth/register``
(which keys by Supabase UUID + real email), so one person could exist twice.

What replaces it:

* **Signature is verified.** Supabase issues either legacy **HS256** tokens signed
  with the project's shared JWT secret, or current **asymmetric** (ES256/RS256)
  tokens verifiable via JWKS. Both are supported: the token header's ``alg``
  selects the path, so this works on either project configuration and survives a
  project migrating from one to the other.
* **Claims are validated** — ``exp``, ``iss``, and ``aud``.
* **Users are looked up by ``user_id`` = the token's ``sub``**, which is exactly
  what ``routers/auth.py`` writes. No synthesised emails.
* **Users are never auto-created.** A correctly signed token whose ``sub`` is
  absent from ``users`` means the local sync in ``/auth/register`` failed. That is
  a bug to surface, not a reason to invent an account.
* **Infrastructure failure is distinguished from token rejection.** A JWKS outage
  or a database error returns 503, not 401 — the previous blanket
  ``except Exception`` reported a dead database as "invalid authentication token",
  which is the kind of thing that costs hours to diagnose.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)

# auto_error=False so a *missing* header produces our own 401 with a useful
# message rather than HTTPBearer's bare "Not authenticated".
bearer_scheme = HTTPBearer(auto_error=False)

HS_ALGS = ("HS256", "HS384", "HS512")
ASYM_ALGS = ("ES256", "RS256", "ES384", "RS384", "ES512", "RS512")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------
# Fetched lazily and cached with a TTL. A lock prevents a burst of concurrent
# requests from all fetching at once after expiry — FastAPI runs sync
# dependencies in a threadpool, so this genuinely can be hit in parallel.
_jwks: dict | None = None
_jwks_fetched_at: float = 0.0
_jwks_lock = threading.Lock()


def _jwks_url() -> str:
    s = get_settings()
    return f"{s.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _fetch_jwks(force: bool = False) -> dict:
    """Return the project's JWKS, cached for ``SUPABASE_JWKS_TTL_SECONDS``.

    ``force`` bypasses the cache, used once when a token presents an unknown
    ``kid`` — that is the signal a key was rotated.
    """
    global _jwks, _jwks_fetched_at
    ttl = get_settings().SUPABASE_JWKS_TTL_SECONDS

    with _jwks_lock:
        fresh = _jwks is not None and (time.monotonic() - _jwks_fetched_at) < ttl
        if fresh and not force:
            return _jwks  # type: ignore[return-value]

        url = _jwks_url()
        try:
            resp = httpx.get(url, timeout=10.0,
                             headers={"apikey": get_settings().SUPABASE_ANON_KEY})
            resp.raise_for_status()
            _jwks = resp.json()
            _jwks_fetched_at = time.monotonic()
            logger.info("Fetched Supabase JWKS: %d key(s)",
                        len(_jwks.get("keys", [])))
            return _jwks
        except Exception as exc:  # noqa: BLE001 - network/parse, both retryable
            if _jwks is not None:
                # Serve the stale copy rather than locking every user out over a
                # transient blip. Keys are long-lived; staleness is the lesser
                # risk, and an unknown kid still triggers a forced refetch.
                logger.warning("JWKS refresh failed (%s); using cached keys",
                               type(exc).__name__)
                return _jwks
            raise HTTPException(
                503, "Authentication service unavailable") from exc


def _key_for(kid: str | None) -> dict:
    """Find the signing key for a ``kid``, refetching once on a miss."""
    for forced in (False, True):
        keys = _fetch_jwks(force=forced).get("keys", [])
        if not kid and len(keys) == 1:
            return keys[0]
        for key in keys:
            if key.get("kid") == kid:
                return key
        if forced:
            break
    raise JWTError(f"no signing key matches kid={kid!r}")


def _project_publishes_asymmetric_keys() -> bool:
    """True if the project's JWKS lists at least one signing key.

    Used only to tell a forged HS256 token apart from a server that is genuinely
    missing its shared secret. Returns False when the answer cannot be
    established (JWKS unreachable and nothing cached), because "I don't know"
    must not be reported as "that token is fake".
    """
    try:
        return bool(_fetch_jwks().get("keys"))
    except HTTPException:
        return False


# ---------------------------------------------------------------------------
# token verification
# ---------------------------------------------------------------------------
def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase access token and return its validated claims.

    Raises :class:`jose.JWTError` (or a subclass) if the token is not
    trustworthy, and :class:`fastapi.HTTPException` 503 if verification could not
    be *attempted* — the caller maps those to 401 and 503 respectively. Keeping
    the two apart is the point: an unverifiable token and an unreachable key
    server are different failures.
    """
    settings = get_settings()

    # The header is unauthenticated input; it selects which key to try and
    # nothing more. The signature check below is what establishes trust.
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")

    if alg in HS_ALGS:
        secret = settings.SUPABASE_JWT_SECRET
        if not secret:
            # No shared secret. Before calling this a misconfiguration, work out
            # whether this project even uses HS256: if it publishes asymmetric
            # signing keys, then it signs asymmetrically, and an HS256 token did
            # not come from it. That is a forged token (401), not a broken
            # server (503) — and the distinction matters, because 503 is
            # retryable. The mobile client keeps its token on a non-401 and
            # would hold a dead one indefinitely instead of signing out.
            if _project_publishes_asymmetric_keys():
                raise JWTError(
                    f"token uses {alg} but this project signs asymmetrically")
            logger.error(
                "Token is %s-signed but SUPABASE_JWT_SECRET is not set, and the "
                "project publishes no JWKS keys. Copy the secret from Supabase "
                "Dashboard -> Project Settings -> API -> JWT Keys into .env.",
                alg)
            raise HTTPException(503, "Authentication is not configured")
        key: object = secret
    elif alg in ASYM_ALGS:
        key = _key_for(header.get("kid"))
    else:
        # 'none' lands here, which is the important case: an attacker stripping
        # the signature and setting alg=none must not be able to reach a verify
        # path that trusts the payload.
        raise JWTError(f"unsupported token algorithm {alg!r}")

    issuer = settings.SUPABASE_JWT_ISSUER or \
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"
    audience = settings.SUPABASE_JWT_AUDIENCE

    return jwt.decode(
        token,
        key,
        algorithms=[alg],
        issuer=issuer,
        # Supabase user tokens carry aud='authenticated'. Allow the check to be
        # switched off by blanking the setting, but verify by default.
        audience=audience or None,
        options={
            "verify_signature": True,
            "verify_exp": True,
            "verify_iss": True,
            "verify_aud": bool(audience),
            "require_exp": True,
            "require_sub": True,
        },
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not (credentials.credentials or "").strip():
        raise HTTPException(401, "Missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})

    try:
        claims = verify_supabase_token(credentials.credentials)
    except HTTPException:
        raise  # 503 from the paths above — already correct, don't mask as 401
    except ExpiredSignatureError:
        raise HTTPException(401, "Token has expired",
                            headers={"WWW-Authenticate": "Bearer"})
    except (JWTClaimsError, JWTError) as exc:
        # Deliberately terse to the client, specific in the log.
        logger.warning("Rejected token: %s: %s", type(exc).__name__, exc)
        raise HTTPException(401, "Invalid authentication token",
                            headers={"WWW-Authenticate": "Bearer"})

    sub = claims.get("sub")
    try:
        user_id = uuid.UUID(str(sub))
    except (ValueError, AttributeError, TypeError):
        logger.warning("Verified token has a non-UUID sub %r", sub)
        raise HTTPException(401, "Invalid authentication token",
                            headers={"WWW-Authenticate": "Bearer"})

    try:
        user = db.query(User).filter(User.user_id == user_id).first()
    except SQLAlchemyError:
        # A database outage is not an authentication failure. Reporting it as one
        # is what made the previous implementation so hard to debug.
        logger.exception("Database error while loading user %s", user_id)
        raise HTTPException(503, "Service temporarily unavailable")

    if user is None:
        # The signature was valid, so this identity is real in Supabase Auth but
        # absent locally: the sync in /auth/register did not complete. Creating a
        # row here would paper over that and fragment the user's data.
        logger.error(
            "Verified Supabase user %s has no local users row — the local sync "
            "in /auth/register failed for this account.", user_id)
        raise HTTPException(401, "Account not provisioned. Please register again.",
                            headers={"WWW-Authenticate": "Bearer"})

    return user
