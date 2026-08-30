from fastapi import APIRouter, Depends
from typing import Any, Dict, List, Optional
from datetime import timedelta
import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.models.stock import NewsSentiment, MarketDataLatest, MarketIndexLatest
from app.models.user import User
from app.models.portfolio import Portfolio, PortfolioSnapshot
from app.services.portfolio_history import exchange_today
from app.services.scraper import ASPI_CODE

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/dashboard', tags=['Dashboard'])

# How many industry groups the sector breakdown names individually before
# rolling the rest into one "Other sectors" slice.
TOP_SECTOR_COUNT = 3

# Window for the portfolio value tile's sparkline. 30 days rather than the 4
# points the fabricated series had: the shape should be governed by how much has
# been recorded, not by a number chosen to fill the tile.
HISTORY_DAYS = 30

# Articles fed to the insight prompt, and the number of insight cards the model is
# asked for. One card per story, so the two are the same number.
NEWS_FOR_INSIGHTS = 3


def _index_payload(row: MarketIndexLatest) -> Dict[str, Any]:
    return {
        "code": row.index_code,
        "name": row.name,
        "value": float(row.value),
        "change": float(row.change) if row.change is not None else None,
        "change_pct": float(row.change_pct) if row.change_pct is not None else None,
        # The exchange's own timestamp for the reading, not the time we scraped
        # it. cse.lk serves the last session's close while the market is shut, so
        # this is how a client knows whether it is showing a live figure.
        "recorded_at": row.recorded_at.isoformat(),
    }


def _sector_breakdown(indices: List[MarketIndexLatest]) -> List[Dict[str, Any]]:
    """Real turnover shares for the home screen's sector donut.

    Replaces a hardcoded "Banking 40% / Cap Goods 35% / Food 25%" legend whose
    arcs were fixed ``strokeDasharray`` values in the JSX.

    The named slices are the largest industry groups by today's turnover, with
    everything else combined into one remainder slice so the shares still sum to
    100 without any of them being invented. Three slices summing to exactly 100
    was the tell in the old version: the CSE has 20 industry groups, and the top
    three are nowhere near the whole market.

    ASPI and S&P SL20 are excluded — they are not sectors, and cse.lk reports no
    turnover for them, so they would contribute nothing but a null.
    """
    sectors = [i for i in indices if i.turnover is not None and i.turnover > 0]
    total = sum(i.turnover for i in sectors)
    if not total:
        return []

    ranked = sorted(sectors, key=lambda i: i.turnover, reverse=True)
    top = ranked[:TOP_SECTOR_COUNT]

    breakdown = [{
        "code": s.index_code,
        "name": s.name,
        "turnover": float(s.turnover),
        "share_pct": round(s.turnover / total * 100, 1),
        "change_pct": float(s.change_pct) if s.change_pct is not None else None,
    } for s in top]

    rest = ranked[TOP_SECTOR_COUNT:]
    if rest:
        rest_turnover = sum(s.turnover for s in rest)
        breakdown.append({
            "code": "OTHER",
            "name": f"Other sectors ({len(rest)})",
            "turnover": float(rest_turnover),
            "share_pct": round(rest_turnover / total * 100, 1),
            # Averaging 17 index movements would produce a number that means
            # nothing, so this slice reports no change rather than a fake one.
            "change_pct": None,
        })

    return breakdown


@router.get('/')
def get_dashboard_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Returns dashboard data featuring real AI Insights from the database.
    """
    # The three most recently *published* stories, not the three most recently
    # scraped.
    #
    # `scraped_at` was the only ordering available before I-08, because
    # `published_at` was NULL on every row — nothing parsed it. It is a poor proxy:
    # a re-scrape touches rows in whatever order the index page lists them, so
    # "latest news" was really "whichever three the parser reached last".
    # `nullslast` keeps a row whose article page was unreachable from jumping the
    # queue, and `scraped_at` remains the tiebreak within the same publish minute.
    news = (db.query(NewsSentiment)
            .order_by(NewsSentiment.published_at.desc().nullslast(),
                      NewsSentiment.scraped_at.desc())
            .limit(NEWS_FOR_INSIGHTS)
            .all())
    # Headline plus the article's own summary. This is the prompt the insights are
    # generated from, and until I-08 every `summary` here was the literal string
    # "Editorial :" — ft.lk's footer contact block, picked up by an extractor that
    # took whatever paragraph followed the headline in the document. So the model
    # was being handed three headlines and three copies of a phone number and asked
    # for actionable market insight.
    news_text = "\n".join(
        f"- {item.headline}: {item.summary}" if item.summary else f"- {item.headline}"
        for item in news
    ) if news else "General market conditions are stable but require monitoring."
    
    insights = []
    
    try:
        from app.services import llm
        import json
        import re

        system_prompt = """You are a financial AI assistant. Generate exactly 3 short, actionable insights for a user based on the provided market news.
Return ONLY a valid JSON array of objects with exactly these keys: "id" (string, unique), "label" (string: 'AI INSIGHT', 'MARKET MOVER', or 'RISK ALERT'), "body" (string, max 2 sentences), and "buttonText" (string, e.g. 'View', 'Analyze', 'Trade'). Do not include markdown blocks or any other text."""

        # Sync call: this endpoint is a plain `def`, so FastAPI already runs it in
        # a threadpool and blocking here does not stall the event loop.
        response_text = llm.complete_text_sync(
            f"Recent market news:\n{news_text}",
            system=system_prompt,
            role=llm.Role.UTILITY,
        )
        if response_text is None:
            # Deliberately not "no LLM provider available", which is what this said
            # and what it is not. complete_text_sync returns None when *every*
            # provider in the chain failed for this call, and on a free tier the
            # overwhelming cause is a transient 429 or 403, not missing keys. The
            # old wording sent me looking for unconfigured credentials while
            # scripts/verify_llm_providers.py was passing 27/27 against the same
            # keys. llm.py has already logged which provider failed and how.
            raise RuntimeError(
                "every LLM provider failed for this request (see the llm logger "
                "for the per-provider reason); falling back to real headlines")

        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)

        if json_match:
            insights = json.loads(json_match.group(0))
        else:
            insights = json.loads(response_text)

    except Exception as e:
        # logger, not print: this is the one place the dashboard degrades, and a
        # bare print does not reach the app's log handlers, carries no level and no
        # timestamp, and is invisible under a process manager. It is a warning
        # rather than an error because the degradation is designed -- real
        # headlines are served below, and the screen stays truthful either way.
        logger.warning("AI insight generation failed, serving real headlines "
                       "instead: %s", e)
        # Fallback to database
        labels = ["MARKET MOVER", "RISK ALERT", "AI INSIGHT"]
        for i, item in enumerate(news):
            insights.append({
                "id": f"insight_{item.news_id}",
                "label": labels[i % len(labels)],
                "body": item.headline or item.summary or "No details available.",
                "buttonText": "Read More"
            })

    # If no news found and AI failed, provide a fallback insight
    if not insights:
        insights = [{
            "id": "insight_empty",
            "label": "AI INSIGHT",
            "body": "No market news available right now. Keep an eye on your portfolio.",
            "buttonText": "Refresh"
        }]

    # Top 6 stocks by volume for the dashboard watchlist preview.
    #
    # Reads market_data_latest, which is one row per symbol. This used to order
    # *all* market_data history by volume and take six rows, so as soon as a
    # second scrape existed the same symbol filled several slots — with two
    # snapshots the six-slot preview showed three distinct symbols, each twice.
    top_stocks = (
        db.query(MarketDataLatest)
        .order_by(MarketDataLatest.volume.desc().nullslast())
        .limit(6)
        .all()
    )
    watchlist_preview = []
    for stock in top_stocks:
        watchlist_preview.append({
            "symbol": stock.symbol,
            "price": float(stock.price) if stock.price else 0,
            "change_pct": float(stock.change_pct) if stock.change_pct else 0
        })

    # Calculate Real Portfolio Value
    from app.models.portfolio import PortfolioHolding
    holdings = db.query(PortfolioHolding).join(Portfolio).filter(Portfolio.user_id == current_user.user_id).all()

    # One query for every held symbol, not one per holding. The previous loop
    # issued a separate ORDER BY recorded_at DESC LIMIT 1 per holding, so a
    # 20-stock portfolio meant 20 round trips plus 20 sorts over that symbol's
    # full history.
    prices: dict[str, float] = {}
    if holdings:
        symbols = {h.symbol for h in holdings}
        prices = {
            row.symbol: float(row.price)
            for row in db.query(MarketDataLatest).filter(
                MarketDataLatest.symbol.in_(symbols)).all()
            if row.price is not None
        }

    current_val = 0
    for item in holdings:
        # Fall back to the purchase price for a symbol we have never quoted, so
        # an unscraped holding contributes its cost basis rather than zero.
        price = prices.get(item.symbol, float(item.avg_buy_price))
        current_val += price * item.quantity

    target_val = current_val * 1.5 if current_val > 0 else 100000

    # The recorded valuation series, replacing a fabricated one.
    #
    # This was `[current_val * 0.85, current_val * 0.82, current_val * 0.94,
    # current_val]` — four numbers derived from the present value and drawn as a
    # performance chart, so it showed the same 15% dip and recovery to exactly
    # today whatever the portfolio had actually done, and implied three past
    # valuations that were never taken.
    #
    # Deliberately not padded to a fixed length. An empty list means the daily
    # snapshot task has not run yet, and the client shows nothing rather than a
    # flat line at today's value, which would be the old bug in a quieter form.
    portfolio_ids = {h.portfolio_id for h in holdings}
    history: List[Dict[str, Any]] = []
    if portfolio_ids:
        cutoff = exchange_today() - timedelta(days=HISTORY_DAYS)
        # Summed across the user's portfolios per day, since this tile shows one
        # combined figure. Done in SQL rather than in Python so a user with several
        # portfolios still costs one query.
        rows = (db.query(PortfolioSnapshot.snapshot_date,
                         func.sum(PortfolioSnapshot.total_value).label('value'))
                .filter(PortfolioSnapshot.portfolio_id.in_(portfolio_ids),
                        PortfolioSnapshot.snapshot_date >= cutoff)
                .group_by(PortfolioSnapshot.snapshot_date)
                .order_by(PortfolioSnapshot.snapshot_date)
                .all())
        history = [{'date': r.snapshot_date.isoformat(), 'value': float(r.value)}
                   for r in rows]

    # Every index in one query -- 22 rows, one round trip. ASPI is pulled out for
    # the headline tile and the industry groups feed the sector donut.
    indices = db.query(MarketIndexLatest).all()
    aspi_row = next((i for i in indices if i.index_code == ASPI_CODE), None)

    return {
        # None, not a placeholder, when no index reading has been scraped yet.
        # This field was a literal 12450.80 / +1.2% with a comment admitting it;
        # the real value was 21279.65 / -0.31%, so the hardcoded figure was out by
        # 71% and pointing the wrong way. A client that cannot show a real number
        # must show that it has none.
        "aspi": _index_payload(aspi_row) if aspi_row else None,
        "sectors": _sector_breakdown(indices),
        "portfolio": {
            "current_value": current_val,
            "target_value": target_val,
            # Renamed from `weekly_history`, which described a shape rather than a
            # source and promised a week the data cannot yet supply. Each entry
            # carries its own date, so the client labels the axis from the payload
            # instead of assuming four evenly spaced weeks.
            "history": history,
            "history_days": HISTORY_DAYS,
        },
        "insights": insights,
        "watchlist_preview": watchlist_preview
    }
