# app/routers/rules.py
"""Investment-rule CRUD — the missing half of the rules engine.

`tasks/rules_tasks.py` is a complete evaluator: five condition types, a 1-hour
dedup window, AI-generated explanations with a template fallback. It has been
logging "no investment rules found" since it was written, because nothing
anywhere could create a rule — no model exposure, no router, no screen (I-10).
This router is the write side; the evaluator needs no change.

The condition vocabulary is validated here against the evaluator's own table:
importing CONDITION_EVALUATORS rather than restating the five names means a
sixth condition type added to the evaluator is automatically creatable, and a
typo here can never drift from what the evaluator actually understands.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.portfolio import InvestmentRule
from app.models.user import User
from tasks.rules_tasks import CONDITION_EVALUATORS

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/rules', tags=['Rules'])


class RuleCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    condition_type: str = Field(min_length=1, max_length=80)
    threshold: float


class RuleUpdate(BaseModel):
    """Partial update. Any field left None is left unchanged."""
    condition_type: str | None = None
    threshold: float | None = None


class RuleOut(BaseModel):
    rule_id: int
    symbol: str
    condition_type: str
    threshold: float
    created_at: datetime

    class Config:
        from_attributes = True


def _validate_condition(condition_type: str) -> None:
    if condition_type not in CONDITION_EVALUATORS:
        raise HTTPException(
            422, f'Unknown condition_type {condition_type!r}. '
                 f'Valid: {", ".join(sorted(CONDITION_EVALUATORS))}')


@router.get('', response_model=list[RuleOut])
def list_rules(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The signed-in user's rules, oldest first."""
    return (db.query(InvestmentRule)
            .filter(InvestmentRule.user_id == user.user_id)
            .order_by(InvestmentRule.created_at)
            .all())


@router.post('', response_model=RuleOut, status_code=201)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a rule the background evaluator will check every 15 minutes
    during market hours."""
    code = payload.symbol.strip().upper()
    _validate_condition(payload.condition_type)

    # The evaluator skips a rule whose symbol has never quoted, silently and
    # forever — reject the typo here where the user can fix it. Volume-spike
    # thresholds read the same quote table, so this check serves all five types.
    from app.models.stock import MarketDataLatest
    if db.get(MarketDataLatest, code) is None:
        raise HTTPException(
            404, f'{code} has no market data yet — is it a listed CSE symbol?')

    rule = InvestmentRule(
        user_id=user.user_id,
        symbol=code,
        condition_type=payload.condition_type,
        threshold=payload.threshold,
    )
    db.add(rule)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception('Failed to create rule for %s (%s %s)',
                         user.user_id, code, payload.condition_type)
        raise HTTPException(503, 'Could not save your rule. Please try again.')
    db.refresh(rule)
    return rule


@router.patch('/{rule_id}', response_model=RuleOut)
def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Change a rule's condition or threshold. Symbol is immutable — delete and
    recreate instead, so a mis-typed ticker is a deliberate act."""
    rule = (db.query(InvestmentRule)
            .filter(InvestmentRule.rule_id == rule_id,
                    InvestmentRule.user_id == user.user_id)
            .first())
    if rule is None:
        raise HTTPException(404, 'Rule not found')

    if payload.condition_type is not None:
        _validate_condition(payload.condition_type)
        rule.condition_type = payload.condition_type
    if payload.threshold is not None:
        rule.threshold = payload.threshold

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception('Failed to update rule %s for %s',
                         rule_id, user.user_id)
        raise HTTPException(503, 'Could not save your rule. Please try again.')
    db.refresh(rule)
    return rule


@router.delete('/{rule_id}', status_code=204)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a rule. 204 whether or not it existed — deleting an already-deleted
    rule is the outcome the caller wanted, not an error."""
    deleted = (db.query(InvestmentRule)
               .filter(InvestmentRule.rule_id == rule_id,
                       InvestmentRule.user_id == user.user_id)
               .delete(synchronize_session=False))
    db.commit()
    if not deleted:
        logger.debug('Delete of absent rule %s for %s', rule_id, user.user_id)
    return None
