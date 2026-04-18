# app/routers/portfolio.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db, get_current_user
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.user import User
from app.schemas.portfolio import PortfolioCreate, PortfolioOut, HoldingCreate, HoldingOut

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
