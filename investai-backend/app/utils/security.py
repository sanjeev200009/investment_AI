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

import secrets

# Simple in-memory store for reset tokens (use Redis in production)
_reset_tokens: dict = {}

def create_reset_token(email: str) -> str:
    """Create a short-lived reset token after OTP verified."""
    token = secrets.token_urlsafe(32)
    _reset_tokens[token] = email
    return token

def verify_reset_token(token: str) -> str | None:
    """Verify reset token and return email. Returns None if invalid."""
    email = _reset_tokens.pop(token, None)
    return email

