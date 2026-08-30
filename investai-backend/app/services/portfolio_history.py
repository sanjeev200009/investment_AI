"""Portfolio valuation history.

The dashboard used to serve ``weekly_history`` as ``current_value × [0.85, 0.82,
0.94, 1.0]``: four numbers derived from the present value, drawn as a performance
chart. Whatever the portfolio had actually done, the line showed a 15% dip
recovering to exactly today — and it implied three past valuations that were
never taken.

They cannot be reconstructed after the fact either, which is why this is a
recorded series rather than a query. A price series can be rebuilt from any
source that kept the prices; a portfolio valuation needs that day's *holdings* as
well, and those change. Once a day passes unrecorded it is gone.
"""
import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio, PortfolioHolding, PortfolioSnapshot
from app.models.stock import MarketDataLatest

logger = logging.getLogger(__name__)

# Snapshots are dated in the exchange's own timezone, not UTC. Colombo is UTC+5:30,
# so a snapshot taken any time after 18:30 local would land on the previous day if
# dated in UTC -- and the task is scheduled after the 14:30 close, well inside that
# window on the following morning's runs.
EXCHANGE_TZ = ZoneInfo("Asia/Colombo")


def exchange_today(now: datetime | None = None) -> date:
    """The current date as the exchange reckons it."""
    return (now or datetime.now(timezone.utc)).astimezone(EXCHANGE_TZ).date()


def snapshot_portfolios(db: Session, now: datetime | None = None) -> int:
    """Record what every portfolio is worth today. Returns snapshots written.

    Two queries regardless of how many portfolios or holdings exist: one join to
    collect the holdings, one ``IN`` clause to price them. The dashboard's
    valuation was an N+1 over holdings before I-04; repeating that here, across
    every user rather than one, would have been worse.
    """
    from app.services.scraper import _upsert_latest  # local: avoids a cycle

    now = now or datetime.now(timezone.utc)
    snapshot_date = exchange_today(now)

    rows = (db.query(PortfolioHolding.portfolio_id, PortfolioHolding.symbol,
                     PortfolioHolding.quantity, PortfolioHolding.avg_buy_price)
            .join(Portfolio, Portfolio.portfolio_id == PortfolioHolding.portfolio_id)
            .all())

    quotes: dict[str, tuple[float, datetime | None]] = {}
    if rows:
        symbols = {r.symbol for r in rows}
        quotes = {
            q.symbol: (float(q.price), q.last_traded_at)
            for q in db.query(MarketDataLatest)
                       .filter(MarketDataLatest.symbol.in_(symbols)).all()
            if q.price is not None
        }

    # Every portfolio gets a row, including ones holding nothing. An empty
    # portfolio is worth zero, which is a fact about it, and a series that starts
    # at zero and steps up when the first holding is bought is the true shape.
    totals: dict[int, dict] = {
        p.portfolio_id: {
            'portfolio_id': p.portfolio_id,
            'snapshot_date': snapshot_date,
            'total_value': 0.0,
            'total_cost': 0.0,
            'holdings_count': 0,
            'priced_count': 0,
            'priced_at': None,
            'updated_at': now,
        }
        for p in db.query(Portfolio.portfolio_id).all()
    }

    for r in rows:
        t = totals.get(r.portfolio_id)
        if t is None:      # holding whose portfolio vanished mid-transaction
            continue

        cost = float(r.avg_buy_price) * float(r.quantity)
        quote = quotes.get(r.symbol)

        if quote is None:
            # Valued at cost basis, matching the dashboard, so an unquoted holding
            # contributes what was paid rather than zero. priced_count records that
            # this happened instead of leaving the total looking authoritative.
            value = cost
        else:
            price, traded_at = quote
            value = price * float(r.quantity)
            t['priced_count'] += 1
            if traded_at is not None and (t['priced_at'] is None
                                          or traded_at > t['priced_at']):
                t['priced_at'] = traded_at

        t['total_value'] += value
        t['total_cost'] += cost
        t['holdings_count'] += 1

    payload = list(totals.values())
    if not payload:
        logger.info('Portfolio snapshot for %s: no portfolios exist', snapshot_date)
        return 0

    # Guarded on updated_at -- our clock -- unlike daily_close, which guards on the
    # exchange's. There is no exchange timestamp for a valuation: the same session's
    # prices are re-valued every day the market stays shut, so ordering by
    # priced_at would make every run after the first a no-op. What must not happen
    # is a retried task overwriting a newer valuation with an older one, and
    # updated_at is exactly that ordering.
    _upsert_latest(db, PortfolioSnapshot, ('portfolio_id', 'snapshot_date'),
                   payload, guard='updated_at')
    db.commit()

    unpriced = sum(t['holdings_count'] - t['priced_count'] for t in payload)
    logger.info('Portfolio snapshot for %s: %d portfolios, %d holdings priced, '
                '%d valued at cost basis', snapshot_date, len(payload),
                sum(t['priced_count'] for t in payload), unpriced)
    return len(payload)
