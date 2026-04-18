from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class PortfolioHoldingBase(BaseModel):
    symbol: str
    shares: float
    average_price: float

class PortfolioHoldingCreate(PortfolioHoldingBase):
    portfolio_id: int

class PortfolioHolding(PortfolioHoldingBase):
    holding_id: int
    current_price: Optional[float] = None
    market_value: Optional[float] = None

    class Config:
        from_attributes = True

class PortfolioBase(BaseModel):
    name: str
    description: Optional[str] = None

class PortfolioCreate(PortfolioBase):
    pass

class Portfolio(PortfolioBase):
    portfolio_id: int
    user_id: UUID
    created_at: datetime
    holdings: List[PortfolioHolding] = []

    class Config:
        from_attributes = True
