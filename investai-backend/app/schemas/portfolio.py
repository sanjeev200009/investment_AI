# app/schemas/portfolio.py
from pydantic import BaseModel
from datetime import datetime
from typing import List

class HoldingCreate(BaseModel):
    symbol: str
    quantity: float
    avg_buy_price: float

class HoldingOut(HoldingCreate):
    holding_id: int
    portfolio_id: int

    class Config:
        from_attributes = True

class PortfolioCreate(BaseModel):
    name: str

class PortfolioOut(BaseModel):
    portfolio_id: int
    name: str
    created_at: datetime
    holdings: List[HoldingOut] = []

    class Config:
        from_attributes = True
