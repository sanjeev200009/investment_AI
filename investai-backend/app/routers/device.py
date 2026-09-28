# app/routers/device.py
"""Device-token registration and language preference — the write side of
user_profiles columns that existed since migration a1b2c3d4e5f6 without any
endpoint to set them (I-12, I-15).

Three device-token conventions predate this router: `fcm.py` read a non-existent
`user.fcm_token`, the `UserProfile.device_token` column was unmapped and
unreadable, and the app never sent a token anywhere. This is the one convention
that survives: POST /me/device-token from the app after FCM registration.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User, UserProfile
from app.schemas.auth import UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/me', tags=['User'])

LANGUAGES = ('en', 'si', 'ta')


class DeviceTokenRequest(BaseModel):
    device_token: str = Field(min_length=10, max_length=512)


class LanguageRequest(BaseModel):
    language: str = Field(min_length=2, max_length=5)


def _ensure_profile(db: Session, user: User) -> UserProfile:
    """The user's profile row, created on first use.

    Registration creates users but not profiles; a user who skipped onboarding
    still needs somewhere to put a device token.
    """
    profile = getattr(user, 'profile', None)
    if profile is None:
        profile = UserProfile(
            user_id=user.user_id,
            full_name=user.full_name or user.email.split('@')[0],
        )
        db.add(profile)
        db.flush()
    return profile


@router.post('/device-token', response_model=UserOut)
def register_device_token(
    payload: DeviceTokenRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Store the FCM token for the calling device.

    Called by the app each time it obtains a token — FCM rotates them, so the
    latest value is the live one, not a first-registration-only value.
    """
    token = payload.device_token.strip()
    try:
        # A phone belongs to whoever is signed in on it now. Without this, after
        # user B signs in on A's old phone, A's rule alerts kept arriving there.
        db.query(UserProfile).filter(
            UserProfile.device_token == token,
            UserProfile.user_id != user.user_id,
        ).update({UserProfile.device_token: None}, synchronize_session=False)
        profile = _ensure_profile(db, user)
        profile.device_token = token
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError:
        db.rollback()
        logger.exception('Failed to store device token for %s', user.user_id)
        raise HTTPException(503, 'Could not save your device token. '
                                 'Please try again.')


@router.delete('/device-token', status_code=204)
def clear_device_token(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stop pushes to this user's device. Called by the app on logout."""
    profile = getattr(user, 'profile', None)
    if profile is not None and profile.device_token:
        profile.device_token = None
        db.commit()


@router.post('/language', response_model=UserOut)
def set_language(
    payload: LanguageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Persist the UI/LLM output language (en | si | ta).

    The risk quiz already collects a preferred language; this endpoint is the
    settings toggle, and both write the same column. The chat endpoint reads it
    to steer which language the agent replies in (FR-6).
    """
    lang = payload.language.strip().lower()
    if lang not in LANGUAGES:
        raise HTTPException(
            422, f'Unsupported language {payload.language!r}. '
                 f'Valid: {", ".join(LANGUAGES)}')
    try:
        profile = _ensure_profile(db, user)
        profile.language = lang
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError:
        db.rollback()
        logger.exception('Failed to set language for %s', user.user_id)
        raise HTTPException(503, 'Could not save your language preference. '
                                 'Please try again.')
