# app/routers/recommendations.py
"""Ranked recommendations endpoint — I-13.

The scoring itself lives in `app/services/recommendations.py`, whose module
docstring records why it is a transparent linear score rather than a model.
This router is a thin authenticated wrapper: the same data costs the same
regardless of caller, but the user exclusion ("what you already hold") needs
an identity.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.recommendations import build_recommendations

router = APIRouter(prefix='/recommendations', tags=['Recommendations'])


@router.get('')
def get_recommendations(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Top-ranked CSE symbols with per-factor explanations.

    `weights` and `factor_labels` are served in every response rather than
    documented once, so the client can always render "why" without a second
    endpoint and the weights in the UI cannot drift from the weights in force.
    """
    # The user's risk category picks the weights (proposal 6.10). No profile
    # yet (onboarding skipped): the balanced default, and `risk_category` in
    # the response is null so the app can say the list is not personalised.
    risk = getattr(user, "risk_profile", None)
    return build_recommendations(db, user_id=user.user_id, limit=limit,
                                 risk_category=getattr(risk, "category", None))
