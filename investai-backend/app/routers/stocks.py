# app/routers/stocks.py
import os

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta
from app.dependencies import get_db, get_current_user
from app.models.stock import (CompanyInfo as CompanyInfoModel,
                              DailyClose as DailyCloseModel,
                              MarketDataLatest as MarketDataLatestModel,
                              MarketIndexLatest as MarketIndexLatestModel,
                              NewsSentiment as NewsSentimentModel)
from app.models.user import User
from app.schemas.stock import (CompanyInfo, MarketData, MarketIndex,
                               NewsSentiment, PriceHistory, PricePrediction,
                               ScrapeResponse, SectorSummary, SentimentSummary)
from app.services.portfolio_history import exchange_today
from app.services.scraper import HEADLINE_INDEX_CODES

router = APIRouter(prefix='/stocks', tags=['Stocks'])

# Chart windows, in calendar days back from today. Calendar rather than trading
# days so the boundary does not shift as the series grows: "1M" always means the
# last month, and how many trading days that contained is what point_count
# reports. 1W is 7 rather than 5 for the same reason — asking for a week of
# calendar time is unambiguous, asking for five trading days needs a holiday
# calendar this project does not have.
HISTORY_RANGES = {
    '1W': 7,
    '1M': 31,
    '3M': 92,
    '6M': 183,
    '1Y': 366,
    'ALL': 36525,   # a century; effectively unbounded without a null branch
}

@router.get('/market', response_model=List[MarketData])
def get_market_data(
    symbol: Optional[str] = None,
    sector: Optional[str] = None,
    limit: int = Query(300, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get latest market prices, with company name and sector. Filterable.

    Reads market_data_latest, which holds exactly one row per symbol. This used
    to recompute latest-per-symbol on every request with a
    ``GROUP BY symbol HAVING max(recorded_at)`` subquery self-joined back onto the
    full history — work proportional to all history ever scraped, for a result
    that changes only when a scrape runs.

    **The join to company_info is a LEFT join**, so a symbol that has traded but
    not yet been swept keeps appearing here with a null name — the price is the
    thing this endpoint promises, and withholding a quote because we lack a
    company profile would be the wrong failure. It also supplies ``name``, which
    the browse screen has been reading off this payload since it was written even
    though the schema never carried it.

    ``sector`` filters server-side. It has to be the server: the browse screen
    filtered client-side over whatever ``limit`` returned, so a sector's stocks
    outside that page were invisible no matter how the filter was implemented.
    It matches against ``sector_group``, the normalised industry group, not the raw
    feed string — a "Food, Beverage & Tobacco" chip has to find all 46 of that
    sector's companies and not the 2 whose sector cse.lk happened to spell with the
    comma.

    ``limit`` defaults to 300 — above the ~291 symbols the exchange lists, so the
    default is "the whole market" rather than a silent truncation. It was 50, while
    the browse screen asked for 100 and then applied a sector filter to those 100;
    both numbers cut into a 291-symbol market, and a filtered view built on a
    truncated set looks like a sector with three stocks in it rather than an error.
    """
    query = (db.query(MarketDataLatestModel,
                      CompanyInfoModel.name, CompanyInfoModel.sector_group)
             .outerjoin(CompanyInfoModel,
                        CompanyInfoModel.symbol == MarketDataLatestModel.symbol))

    if symbol:
        query = query.filter(MarketDataLatestModel.symbol == symbol.upper())

    if sector:
        # Case- and whitespace-insensitive: these strings reach us from a URL, and
        # "capital goods" should find "Capital Goods" rather than nothing. Exact
        # match on the normalised form, not a LIKE — "Energy" must not also return
        # "Energy Services" if cse.lk ever adds one.
        query = query.filter(
            func.lower(func.trim(CompanyInfoModel.sector_group))
            == sector.strip().lower())

    # Deterministic ordering. Without it Postgres may return rows in any order,
    # so a client paging with `limit` could see the same symbol twice or miss one.
    rows = query.order_by(MarketDataLatestModel.symbol).limit(limit).all()

    # Built by hand rather than left to from_attributes: a joined query yields
    # (model, name, sector) tuples, and Pydantic cannot read a column off a tuple.
    return [MarketData(symbol=quote.symbol,
                       price=quote.price,
                       change=quote.change,
                       change_pct=quote.change_pct,
                       volume=quote.volume,
                       market_id=quote.market_id,
                       recorded_at=quote.recorded_at,
                       name=name,
                       sector=sector_name)
            for quote, name, sector_name in rows]


@router.get('/sectors', response_model=List[SectorSummary])
def get_sectors(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Every CSE industry group present on the exchange, with its symbol count.

    So a client's sector filter chips come from the market rather than from a
    hardcoded array. Both the home and browse screens built theirs from
    ticker-prefix lists — ``['JKH', 'HAYL', 'RICH']`` labelled "Capital Goods" —
    which put companies in the wrong sector and left most of the market in none.

    Grouped on ``sector_group``, the normalised industry group, which is the whole
    reason that column exists: cse.lk's raw sector string takes 39 distinct values
    for 20 sectors, so grouping on it returns 39 chips including three spellings of
    Food, Beverage & Tobacco, and the correctly-spelled chip counts 2 of that
    sector's 46 companies.

    Counted over symbols that currently have a quote, by joining
    market_data_latest, so a chip's count matches how many rows
    ``/market?sector=X`` will actually return. Counting company_info alone would
    promise stocks the price table cannot supply.

    Six symbols are in no chip and the counts therefore do not sum to the market:
    three unit trusts have no sector at all, and three have a sector string that
    resolves to no single group. An "Other" chip would name a sector that does not
    exist on the exchange.

    Ordered by count descending: a filter list is more useful biggest-first, and
    the name breaks ties so the order is stable between requests.

    Returns an empty list before the first company sweep. A client must then show
    no chips rather than falling back to invented ones.
    """
    rows = (db.query(CompanyInfoModel.sector_group,
                     func.count(MarketDataLatestModel.symbol).label('count'))
            .join(MarketDataLatestModel,
                  MarketDataLatestModel.symbol == CompanyInfoModel.symbol)
            .filter(CompanyInfoModel.sector_group.isnot(None))
            .group_by(CompanyInfoModel.sector_group)
            .order_by(func.count(MarketDataLatestModel.symbol).desc(),
                      CompanyInfoModel.sector_group)
            .all())

    return [SectorSummary(sector=sector, count=count) for sector, count in rows]


@router.get('/company/{symbol}', response_model=CompanyInfo)
def get_company_info(
    symbol: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """A symbol's real fundamentals: sector, market cap, 52-week low, beta.

    Replaces the four values the stock detail screen computed from the price
    itself. There is no P/E in the response because cse.lk publishes no EPS to
    compute one from, and no 52-week *high* because the one cse.lk publishes is not
    split-adjusted; the ``CompanyInfo`` schema records what was checked and what was
    measured for both.

    404 when we hold no profile for the symbol, unlike ``/history/{symbol}`` which
    returns an empty series. The difference is that an empty history is a
    meaningful answer — "this symbol has no recorded trading days yet" — whereas a
    company row of all nulls tells a client nothing it can render, and a body of
    nulls is easier to mistake for real data than a 404 is.

    Most fields are nullable even on a 200: a unit trust genuinely has no sector,
    beta or market cap. Render nothing for a null, never a zero or a dash styled
    like a number.
    """
    code = symbol.strip().upper()
    row = db.get(CompanyInfoModel, code)
    if row is None:
        raise HTTPException(
            404, f'No company profile stored for {code}. It is either not a listed '
                 f'CSE symbol or the daily company refresh has not reached it yet.')
    return row

@router.get('/indices', response_model=List[MarketIndex])
def get_market_indices(
    index_code: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get the current reading for every CSE index, or one by code.

    22 rows: ASPI, SPSL20, and the 20 GICS industry groups (BNK, EGY, CG, ...).

    Ordered headline indices first, then industry groups by turnover descending,
    which is the order a list UI wants. ``index_code`` is the final tiebreak so the
    order is fully deterministic and a client paging the result cannot see a row
    twice.

    **The headline indices are identified by code, not by having no turnover.**
    They were identified by the latter, on the reasoning that cse.lk publishes
    turnover per industry group only. It does — but a group in which nothing traded
    gets null rather than zero, so a real sector meets the same test. That is not
    hypothetical: Household & Personal Products had no trades in one session and
    sorted itself between ASPI and S&P SL20 at the top of this list, presented as a
    market-wide index. The two headline codes are fixed and known, so asking which
    they are needs no inference.

    Returns an empty list before the first index scrape has run. Callers must not
    substitute a placeholder value for an absent reading — the whole point of
    this endpoint is that the dashboard used to serve a hardcoded ASPI.
    """
    query = db.query(MarketIndexLatestModel)

    if index_code:
        query = query.filter(MarketIndexLatestModel.index_code == index_code.upper())

    # `case` rather than `in_(...).desc()`: the latter puts True first only because
    # of how the driver renders booleans, and the ASPI-before-SPSL20 order within
    # the headline pair would still be left to the index_code tiebreak by luck
    # (A < S alphabetically). An explicit rank says what the order is.
    headline_rank = case(
        {code: i for i, code in enumerate(HEADLINE_INDEX_CODES)},
        value=MarketIndexLatestModel.index_code,
        else_=len(HEADLINE_INDEX_CODES),
    )

    return query.order_by(
        headline_rank,
        MarketIndexLatestModel.turnover.desc().nullslast(),
        MarketIndexLatestModel.index_code,
    ).all()


@router.get('/history/{symbol}', response_model=PriceHistory)
def get_price_history(
    symbol: str,
    range: str = '1M',
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get a symbol's daily close series.

    ``/history/{symbol}`` rather than ``/{symbol}/history``, following the
    ``/news/{symbol}`` and ``/sentiment/{symbol}`` convention already in this
    router. It also keeps every path segment after ``/stocks/`` a literal, so a
    symbol can never shadow ``/market``, ``/indices`` or ``/scrape``.

    ``range`` is a window measured back from today, not a point count, so a
    request for 1M during a week the market barely traded returns fewer points
    rather than reaching further back to pad. ``point_count`` and the date bounds
    are in the response for that reason — this series starts from the day the
    pipeline began recording it, and the client must be able to say "4 trading
    days" rather than drawing four points across an axis labelled as a month.

    Returns 200 with an empty ``points`` list for a symbol we hold no history for,
    not 404. Absence of history is not absence of the symbol, and the two would be
    indistinguishable to a client that had to treat 404 as "no such stock".
    """
    days = HISTORY_RANGES.get(range.upper())
    if days is None:
        raise HTTPException(
            422, f'Unknown range {range!r}. Valid: {", ".join(HISTORY_RANGES)}')

    code = symbol.strip().upper()
    cutoff = exchange_today() - timedelta(days=days)

    # Ascending: a chart plots oldest-first, and this reads the primary key's btree
    # forward over a contiguous span rather than sorting.
    points = (db.query(DailyCloseModel)
              .filter(DailyCloseModel.symbol == code,
                      DailyCloseModel.trade_date >= cutoff)
              .order_by(DailyCloseModel.trade_date)
              .all())

    return {
        'symbol': code,
        'requested_range': range.upper(),
        'point_count': len(points),
        'first_date': points[0].trade_date if points else None,
        'last_date': points[-1].trade_date if points else None,
        'points': points,
    }


@router.get('/news/{symbol}', response_model=List[NewsSentiment])
def get_stock_news(
    symbol: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get latest news + sentiment for a specific symbol."""
    return (
        db.query(NewsSentimentModel)
        .filter(NewsSentimentModel.symbol == symbol.upper())
        .order_by(NewsSentimentModel.scraped_at.desc())
        .limit(limit)
        .all()
    )

@router.post('/scrape', status_code=202, response_model=ScrapeResponse, tags=['Scraper'])
async def trigger_scrape(
    db: Session = Depends(get_db),
    symbol: Optional[str] = None,
    _: User = Depends(get_current_user),
):
    """Enqueue a scrape and return immediately — 202 Accepted, not the data.

    This used to run the whole pipeline synchronously inside the request: a full
    market + index + news scrape takes on the order of a minute of worker time,
    and any authenticated user could hold that repeatedly by re-sending the
    request, with a 60s client timeout as the only backstop. It is exactly the
    job Celery is already here to do, so the request now enqueues the same task
    the beat schedule runs and returns before any scraping starts.

    202 rather than 200 because the work is *not* done when the response is.
    Clients observe progress in the data itself — a fresh `recorded_at` on
    /market — or in Flower. Nothing in either app called this endpoint, which is
    why the change is safe; the mobile app scrapes nothing manually.
    """
    # Operator tool, not a user feature: any signed-in user could otherwise
    # enqueue unlimited full-market scrapes of cse.lk. Beat runs the schedule
    # in production.
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise HTTPException(404, "Not found")
    if symbol and (len(symbol) > 20 or not symbol.replace('.', '').isalnum()):
        raise HTTPException(422, "Invalid symbol")

    from tasks.scrape_tasks import scrape_cse_data, scrape_cse_indices, \
        scrape_and_analyse_news

    if symbol:
        # On-demand enrichment path: one symbol's news, then scored and embedded
        # by the same chain the scheduled task feeds.
        scrape_and_analyse_news.delay(symbol)
        return {
            'message': f'News scrape for {symbol} enqueued',
            'symbol': symbol,
            'saved_count': None,
        }

    # The three scheduled scrapes, on the same queues beat uses. Indices and news
    # are separate tasks so one failing does not cost the others.
    scrape_cse_data.delay()
    scrape_cse_indices.delay()
    scrape_and_analyse_news.delay()
    return {
        'message': 'Full market, index and news scrape enqueued',
        'symbol': 'ALL',
        'saved_count': None,
    }

@router.get('/sentiment/{symbol}', response_model=SentimentSummary)
def get_sentiment_summary(
    symbol: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get aggregated sentiment for a symbol."""
    from app.services.sentiment import get_symbol_sentiment_summary
    return get_symbol_sentiment_summary(db, symbol.upper())
