# app/routers/portfolio.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import timedelta

from app.dependencies import get_db, get_current_user
from app.models.portfolio import Portfolio, PortfolioHolding, PortfolioSnapshot
from app.models.user import User
from app.schemas.portfolio import (HoldingCreate, HoldingOut, PortfolioCreate,
                                   PortfolioHistory, PortfolioOut)
from app.services.portfolio_history import exchange_today
# Shared with /stocks/history/{symbol} rather than redefined, so "1M" cannot come
# to mean two different windows in two charts on the same screen.
from app.routers.stocks import HISTORY_RANGES

router = APIRouter(prefix='/portfolio', tags=['Portfolio'])

@router.get('/', response_model=List[PortfolioOut])
def get_portfolios(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Portfolio).filter(Portfolio.user_id == user.user_id).all()

@router.post('/', response_model=PortfolioOut, status_code=201)
def create_portfolio(payload: PortfolioCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = Portfolio(user_id=user.user_id, name=payload.name)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.get('/{portfolio_id}/history', response_model=PortfolioHistory)
def get_portfolio_history(
    portfolio_id: int,
    range: str = '1M',
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a portfolio's recorded valuation series.

    Replaces the dashboard's ``current_value × [0.85, 0.82, 0.94, 1.0]`` — four
    points derived from the present value, so the chart showed the same dip and
    recovery no matter what the portfolio had done.

    404 when the portfolio is not this user's, matching the other handlers here,
    and deliberately the same response as a portfolio that does not exist: telling
    an unauthorised caller which portfolio ids are real is a disclosure the reply
    does not need to make.

    An existing portfolio with no snapshots yet returns 200 and an empty series.
    Unlike price history this can never be backfilled — valuing a past day needs
    that day's holdings as well as its prices — so a new portfolio genuinely has
    no history until the daily task has run at least once.
    """
    days = HISTORY_RANGES.get(range.upper())
    if days is None:
        raise HTTPException(
            422, f'Unknown range {range!r}. Valid: {", ".join(HISTORY_RANGES)}')

    owned = db.query(Portfolio.portfolio_id).filter(
        Portfolio.portfolio_id == portfolio_id,
        Portfolio.user_id == user.user_id,
    ).first()
    if not owned:
        raise HTTPException(404, 'Portfolio not found')

    cutoff = exchange_today() - timedelta(days=days)
    points = (db.query(PortfolioSnapshot)
              .filter(PortfolioSnapshot.portfolio_id == portfolio_id,
                      PortfolioSnapshot.snapshot_date >= cutoff)
              .order_by(PortfolioSnapshot.snapshot_date)
              .all())

    return {
        'portfolio_id': portfolio_id,
        'requested_range': range.upper(),
        'point_count': len(points),
        'first_date': points[0].snapshot_date if points else None,
        'last_date': points[-1].snapshot_date if points else None,
        'points': points,
    }


@router.post('/{portfolio_id}/holdings', response_model=HoldingOut, status_code=201)
def add_holding(portfolio_id: int, payload: HoldingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    portfolio = db.query(Portfolio).filter(
        Portfolio.portfolio_id == portfolio_id,
        Portfolio.user_id == user.user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(404, 'Portfolio not found')
    
    h = PortfolioHolding(portfolio_id=portfolio_id, **payload.model_dump())
    db.add(h)
    db.commit()
    db.refresh(h)
    return h

@router.delete('/{portfolio_id}/holdings/{holding_id}', status_code=204)
def delete_holding(portfolio_id: int, holding_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    portfolio = db.query(Portfolio).filter(
        Portfolio.portfolio_id == portfolio_id,
        Portfolio.user_id == user.user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(404, 'Portfolio not found')
    
    h = db.query(PortfolioHolding).filter(
        PortfolioHolding.holding_id == holding_id,
        PortfolioHolding.portfolio_id == portfolio_id
    ).first()
    
    if not h:
        raise HTTPException(404, 'Holding not found')
    
    db.delete(h)
    db.commit()
