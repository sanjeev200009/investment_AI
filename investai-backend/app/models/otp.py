# app/models/otp.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class OTPCode(Base):
    __tablename__ = 'otp_codes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    purpose = Column(String, nullable=False)  # 'register' or 'reset_password'
    is_used = Column(Boolean, default=False)
    # Wrong-guess counter, capped in app/services/otp.py. A six-digit code is
    # only 10^6 possibilities, so without this the OTP is a speed bump rather
    # than a gate — which matters now that email confirmation depends on it.
    attempts = Column(Integer, nullable=False, server_default='0', default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    """A single-use, short-lived password-reset credential.

    Replaces the process-local ``_reset_tokens: dict`` in app/utils/security.py,
    which lost every pending reset on restart, was invisible to sibling workers
    (so with more than one uvicorn worker or Railway replica a reset failed
    whenever the second request landed on a different process), and grew without
    bound because nothing ever expired.

    Postgres rather than Redis deliberately. Redis is a hard dependency of the
    Celery workers, but *not* of the API process — no request path touches it —
    so putting reset tokens there would add a new runtime dependency to the API
    and make password reset fail whenever Redis is down. The database is already
    required to serve any request at all, and ``otp_codes`` already establishes
    this exact pattern for the same kind of credential.

    Only a SHA-256 hash of the token is stored. The raw token goes to the user
    and is never persisted, so read access to this table does not hand over
    usable reset credentials.
    """

    __tablename__ = 'password_reset_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    # sha256 hex digest: always 64 chars. Unique so a duplicate mint cannot
    # silently shadow an existing token.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
