# app/utils/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(
        {'sub': subject, 'exp': expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

import hashlib
import secrets
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.otp import PasswordResetToken
from app.services.otp import OTP_EXPIRY_MINUTES

# Reset tokens live in Postgres (app/models/otp.py::PasswordResetToken), not in a
# process-local dict as they used to. The old `_reset_tokens: dict = {}` lost
# every pending reset on restart, was invisible to sibling workers, and never
# expired. See the model's docstring for why Postgres rather than Redis.
#
# The window matches the OTP's, because a reset token is only ever issued
# immediately after an OTP was verified: giving the second step a longer life
# than the first would widen the exposure for no usability gain.
RESET_TOKEN_EXPIRY_MINUTES = OTP_EXPIRY_MINUTES


def _hash_token(token: str) -> str:
    """SHA-256 hex of a reset token.

    Plain SHA-256 rather than a password hash is right here: the token is 32
    bytes from `secrets`, so there is no low-entropy input for an attacker to
    grind through, and reset verification sits on the request path where bcrypt's
    deliberate slowness would buy nothing.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(db: Session, email: str) -> str:
    """Mint a short-lived reset token after the OTP has been verified.

    Only the hash is stored; the returned value is the sole copy of the raw
    token. Any previous token for the address is dropped, so requesting a new
    reset invalidates an older link rather than leaving both live.
    """
    db.execute(delete(PasswordResetToken).where(
        PasswordResetToken.email == email))

    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        token_hash=_hash_token(token),
        email=email,
        expires_at=datetime.now(timezone.utc) + timedelta(
            minutes=RESET_TOKEN_EXPIRY_MINUTES),
    ))
    db.commit()
    return token


def verify_reset_token(db: Session, token: str,
                       consume: bool = True) -> str | None:
    """Consume a reset token and return the email it was issued for.

    Returns None if the token is unknown, already used, or expired.

    ``consume=False`` only checks it, so /auth/reset-password can update the
    Supabase password first and spend the token after — a Supabase failure then
    leaves the user able to retry instead of restarting the reset (the same
    pattern as ``verify_otp``).

    The delete and the expiry check are one statement with RETURNING, so the
    token is spent atomically: two concurrent requests carrying the same token
    cannot both succeed, which a read-then-delete would allow.
    """
    if not token:
        return None

    if not consume:
        row = db.execute(
            select(PasswordResetToken.email).where(
                PasswordResetToken.token_hash == _hash_token(token),
                PasswordResetToken.expires_at > datetime.now(timezone.utc),
            )
        ).first()
        return row[0] if row else None

    row = db.execute(
        delete(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == _hash_token(token),
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
        .returning(PasswordResetToken.email)
    ).first()
    db.commit()
    return row[0] if row else None


def purge_expired_reset_tokens(db: Session) -> int:
    """Delete reset tokens that are past their expiry.

    `verify_reset_token` already refuses expired tokens, so this is hygiene
    rather than enforcement — it stops the table accumulating rows for resets
    that were requested and never completed.
    """
    result = db.execute(delete(PasswordResetToken).where(
        PasswordResetToken.expires_at <= datetime.now(timezone.utc)))
    db.commit()
    return result.rowcount or 0

