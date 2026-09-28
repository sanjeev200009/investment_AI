# app/routers/watchlist.py
"""Per-user watchlist CRUD — the endpoint layer for the table that has existed
since migration a1b2c3d4e5f6 without any of this.

Before this router, `WatchlistScreen.js` fetched `/stocks/market?limit=50` and
showed the ten highest-volume symbols — the same ten for every user, on a screen
titled "Watchlist" (I-09). The pattern here follows `routers/portfolio.py`: every
query is scoped by the verified user's id, never by a client-supplied user id.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.portfolio import Watchlist
from app.models.stock import CompanyInfo, MarketDataLatest
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/watchlist', tags=['Watchlist'])

# market_data.symbol is String(20) — reject longer input at the schema rather
# than at the database.
MAX_SYMBOL_LEN = 20


class WatchlistAdd(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)


class WatchlistItem(BaseModel):
    """A watched symbol with the quote it is watched for.

    `added_at` is when the user starred it; `recorded_at` is when the quote was
    scraped. They are different clocks and both matter — a row watched yesterday
    against a quote from the last session is normal, not stale.
    """

    symbol: str
    name: str | None = None
    sector: str | None = None
    # None when the symbol has no quote yet; never a stand-in 0.0.
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    added_at: datetime
    recorded_at: datetime | None = None

    class Config:
        from_attributes = True


@router.get('', response_model=list[WatchlistItem])
def get_watchlist(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The signed-in user's watched symbols with their latest quotes.

    Newest star first — the order a user last curates in is the order they want
    to read. A symbol kept on the list after it stops trading still shows its
    last known quote from market_data_latest, with `recorded_at` saying how old
    that is; delisting it is the user's call, not the API's.
    """
    rows = (
        db.query(Watchlist, MarketDataLatest, CompanyInfo.name,
                 CompanyInfo.sector_group)
        # Outer join: a starred symbol with no quote yet must still be listed,
        # or it vanishes right after the POST that accepted it.
        .outerjoin(MarketDataLatest,
                   MarketDataLatest.symbol == Watchlist.symbol)
        .outerjoin(CompanyInfo, CompanyInfo.symbol == Watchlist.symbol)
        .filter(Watchlist.user_id == user.user_id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )
    return [
        WatchlistItem(
            symbol=wl.symbol,
            name=name,
            sector=sector_group,
            price=quote.price if quote else None,
            change=quote.change if quote else None,
            change_pct=quote.change_pct if quote else None,
            volume=quote.volume if quote else None,
            added_at=wl.added_at,
            recorded_at=quote.recorded_at if quote else None,
        )
        for wl, quote, name, sector_group in rows
    ]


@router.post('', response_model=WatchlistItem, status_code=201)
def add_to_watchlist(
    payload: WatchlistAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Star a symbol. Idempotent: re-adding returns the existing row.

    A symbol that has never traded and has no company profile is rejected with
    404 — a watchlist entry pointing at nothing would render as a dead card
    forever, and every typo deserves its error at add time rather than in the
    list. Either a quote or a profile is enough: a newly listed symbol can have
    a profile before its first scrape, or a quote before the nightly sweep.
    """
    code = payload.symbol.strip().upper()
    if not code or len(code) > MAX_SYMBOL_LEN:
        raise HTTPException(422, f'Symbol must be 1-{MAX_SYMBOL_LEN} characters')

    quote = db.get(MarketDataLatest, code)
    profile = db.get(CompanyInfo, code)
    if quote is None and profile is None:
        raise HTTPException(
            404, f'{code} is not a listed CSE symbol this API holds — '
                 f'check the ticker and try again.')

    row = (db.query(Watchlist)
           .filter(Watchlist.user_id == user.user_id,
                   Watchlist.symbol == code)
           .first())
    if row is None:
        row = Watchlist(user_id=user.user_id, symbol=code)
        db.add(row)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception('Failed to add %s to watchlist for %s',
                             code, user.user_id)
            raise HTTPException(503, 'Could not save your watchlist. '
                                     'Please try again.')
        db.refresh(row)
    # Re-fetch the quote rather than trusting the earlier read: the scrape task
    # may have landed between the two queries.
    current = db.get(MarketDataLatest, code)
    return WatchlistItem(
        symbol=code,
        name=profile.name if profile else None,
        sector=profile.sector_group if profile else None,
        price=current.price if current else None,
        change=current.change if current else None,
        change_pct=current.change_pct if current else None,
        volume=current.volume if current else None,
        added_at=row.added_at,
        recorded_at=current.recorded_at if current else None,
    )


@router.delete('/{symbol}', status_code=204)
def remove_from_watchlist(
    symbol: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unstar a symbol. 204 whether or not it was on the list, so an double-tap
    or a stale screen cannot produce an error the user cannot act on."""
    code = symbol.strip().upper()
    deleted = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user.user_id,
                Watchlist.symbol == code)
        .delete(synchronize_session=False)
    )
    db.commit()
    if not deleted:
        logger.debug('Watchlist remove of absent %s for %s',
                     code, user.user_id)
    return None
