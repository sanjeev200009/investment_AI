# app/routers/user.py
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, Field
import logging

from app.dependencies import get_db, get_current_user
from app.models.user import User, RiskProfile
from app.schemas.auth import UserOut
from app.services.risk_scoring import (
    AssessmentError,
    question_bank,
    score_assessment,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/me', tags=['User'])


class AssessmentRequest(BaseModel):
    """The wizard's answers, keyed by question id as a string.

    Values are an option string, a list of option strings (Q13) or a number
    (Q11's slider). Validation of the contents is
    app/services/risk_scoring.py's job — it can report *which* answer is wrong,
    which a schema-level union cannot.
    """
    answers: dict[str, Any] = Field(min_length=1)


class RiskProfileResponse(BaseModel):
    score: int
    category: str
    answered_weight: int
    total_weight: int
    preferred_language: str | None = None
    sectors: list[str] = []


class QuestionOut(BaseModel):
    id: int
    text: str
    type: str
    options: list[str]
    weight: int


class UpdateProfileRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)



_LANGUAGE_CODES = {
    'en': 'en', 'english': 'en',
    'si': 'si', 'sinhala': 'si', 'සිංහල': 'si',
    'ta': 'ta', 'tamil': 'ta', 'தமிழ்': 'ta',
}

@router.patch('', response_model=UserOut)
def update_own_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the signed-in user's display name.

    Added during the I-02 auth cutover. ProfileScreen's edit button previously
    called Clerk's ``user.update({firstName, lastName})``; with Clerk gone there
    was no endpoint behind it at all. `users.full_name` is a single column, so
    the app sends one combined name rather than two.
    """
    current_user.full_name = payload.full_name.strip()
    try:
        db.commit()
        db.refresh(current_user)
    except SQLAlchemyError:
        db.rollback()
        logger.exception('Failed to update full_name for %s', current_user.user_id)
        raise HTTPException(503, 'Could not save your profile. Please try again.')
    return current_user

@router.get('/assessment/questions', response_model=list[QuestionOut])
def get_assessment_questions():
    """The canonical risk-assessment instrument.

    Served so the client can be driven from the same question bank the server
    scores against, instead of keeping its own copy that silently drifts — the
    drift that made this endpoint reject every submission until the I-02 fix.
    """
    return question_bank()


@router.post('/risk-profile', response_model=RiskProfileResponse)
def update_risk_profile(
    payload: AssessmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Score the risk-assessment wizard and save the result.

    Scoring lives in app/services/risk_scoring.py, which rejects any answer it
    does not recognise rather than contributing zero for it. The previous
    version of this endpoint compared four fields against option strings the
    wizard had stopped using, so it both 422'd on shape and would have scored
    every user 0 / "Low" had the shape matched.
    """
    try:
        result = score_assessment(payload.answers)
    except AssessmentError as exc:
        # 422: the body parsed but does not describe a valid assessment. The
        # message names the offending question so the app can say something
        # useful instead of "could not save".
        raise HTTPException(422, str(exc))

    rp = db.query(RiskProfile).filter(
        RiskProfile.user_id == current_user.user_id).first()
    if rp is None:
        rp = RiskProfile(user_id=current_user.user_id)
        db.add(rp)

    rp.score = result.score
    rp.category = result.category
    rp.answers = result.answers

    # Q14 asks for the preferred language; chat reads user_profiles.language.
    # This was never written, so a Sinhala or Tamil choice never reached chat.
    lang = _LANGUAGE_CODES.get(str(result.preferred_language or '').strip().lower())
    if lang:
        from app.routers.device import _ensure_profile
        _ensure_profile(db, current_user).language = lang

    try:
        db.commit()
        db.refresh(rp)
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            'Failed to save risk profile for %s', current_user.user_id)
        raise HTTPException(
            503, 'Could not save your risk profile. Please try again.')

    return RiskProfileResponse(
        score=rp.score,
        category=rp.category,
        answered_weight=result.answered_weight,
        total_weight=result.total_weight,
        preferred_language=result.preferred_language,
        sectors=result.sectors,
    )
