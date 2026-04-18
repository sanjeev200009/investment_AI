from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db
from app.schemas.portfolio import Portfolio, PortfolioCreate

router = APIRouter()

@router.get("/", response_model=List[Portfolio])
def get_portfolios(db: Session = Depends(get_db)):
    """
    Get all portfolios for current user.
    """
    return []

@router.post("/", response_model=Portfolio)
def create_portfolio(portfolio_in: PortfolioCreate, db: Session = Depends(get_db)):
    """
    Create a new portfolio.
    """
    return None
