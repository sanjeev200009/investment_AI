# app/schemas/portfolio.py
from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import List, Optional

class HoldingCreate(BaseModel):
    # Validated here because nothing downstream did: a negative quantity or
    # price corrupted P&L and snapshots, a lowercase symbol never matched a
    # quote, and a symbol over 20 characters was a DataError (500).
    symbol: str = Field(min_length=1, max_length=20)
    quantity: float = Field(gt=0)
    avg_buy_price: float = Field(gt=0)

    @field_validator('symbol')
    @classmethod
    def _normalise_symbol(cls, v: str) -> str:
        return v.strip().upper()

class HoldingOut(BaseModel):
    # Not a subclass of HoldingCreate: rows stored before validation existed
    # must still be readable.
    symbol: str
    quantity: float
    avg_buy_price: float
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


class PortfolioSnapshotOut(BaseModel):
    """One day's valuation of one portfolio.

    ``priced_count`` below ``holdings_count`` means the rest were valued at their
    cost basis because no quote existed, so ``total_value`` is partly what was
    paid rather than what it is worth. Exposed rather than hidden: a client showing
    a return figure should be able to tell the user how much of it is real.

    ``priced_at`` is the trading session the prices came from. ``snapshot_date`` is
    a calendar date, so while the market is shut consecutive days carry the same
    value — correctly, since the portfolio was worth that on each of them. Equal
    ``priced_at`` across those days is what distinguishes a closed market from a
    scraper that has stopped.
    """
    snapshot_date: date
    total_value: float
    total_cost: float
    holdings_count: int
    priced_count: int
    priced_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PortfolioHistory(BaseModel):
    """A portfolio's valuation series.

    Carries the same honesty fields as ``PriceHistory`` and for the same reason:
    the series begins when recording began, not when the portfolio was created,
    and nothing can backfill the days in between. A client that knows it has two
    points should not draw a month.
    """
    portfolio_id: int
    requested_range: str
    point_count: int
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    points: List[PortfolioSnapshotOut]
