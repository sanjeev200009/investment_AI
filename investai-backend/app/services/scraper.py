"""
Web Scraping Pipeline for InvestAI
Handles CSE stock data and financial news scraping with DB persistence.
"""
import httpx
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from app.models.stock import (DailyClose, MarketData, MarketDataLatest,
                              MarketIndex, MarketIndexLatest, NewsSentiment)
from app.database import SessionLocal
from app.services.news import MIN_HEADLINE_LEN, NEWS_SOURCES as _news_sources

logger = logging.getLogger(__name__)

CSE_TRADE_SUMMARY_URL = "https://www.cse.lk/api/tradeSummary"
CSE_MARKET_STATUS_URL = "https://www.cse.lk/api/marketStatus"
# One call returns all 22 indices: ASPI, S&P SL20, and the 20 GICS industry
# groups. Its values were confirmed to agree exactly with the dedicated aspiData
# and snpData endpoints and with dailyMarketSummery, so this is the single source
# rather than three that would have to be reconciled.
CSE_ALL_SECTORS_URL = "https://www.cse.lk/api/allSectors"


# The news sources and their per-page selectors live in app/services/news.py,
# where each selector sits next to a note on what it was measured to match. This
# name is derived rather than restated so the two can never drift; it stays
# importable from here because tests and scripts reach for it at this path.
#
# It is now two sources, not three: https://www.dailymirror.lk/business was
# dropped in I-08 because its robots.txt publishes "Crawl-delay: 3600" — one
# request an hour, against a pipeline that was issuing ~21 every 30 minutes — and
# because it answers httpx with HTTP 403 on every header and protocol combination
# tried, which is what the removed ``urllib.request``-in-a-thread fetch was
# working around. See DROPPED_SOURCES in app/services/news.py.
NEWS_SOURCES = [s.index_url for s in _news_sources]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    # No Accept-Encoding. httpx sets it from the decoders it actually has —
    # `httpx._decoders.SUPPORTED_DECODERS`, which here is gzip/deflate/identity —
    # so letting it write the header is the only way the claim stays true.
    #
    # This header used to read "gzip, deflate, br", and neither `brotli` nor
    # `brotlicffi` is installed. economynext.com honours Brotli when offered, so
    # every request to it returned **HTTP 200 with an undecodable body**: 21,572
    # bytes of compressed data that `response.text` handed to BeautifulSoup as
    # 20,415 characters of mojibake. No exception, no warning, no non-2xx status —
    # just zero elements matching any selector. The same request with a header
    # httpx had written returned gzip, 174,600 characters, and 24 headlines.
    #
    # cse.lk currently answers gzip, so the price pipeline is unaffected — but it
    # is unaffected only because the server chose not to take an option we were
    # advertising, and the failure mode there would be an empty trade summary
    # rather than a visible error.
    "Connection": "keep-alive",
}

CSE_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/equity/trade-summary",
}

# Headlines shorter than this are almost always page furniture (nav labels,
# "Related stories" stubs) rather than real articles. Imported above rather than
# restated: the bar is enforced in app/services/news.py at parse time and again
# before insert, and two copies of the number would drift.

# market_data.symbol is String(20); anything longer would raise on insert.
MAX_SYMBOL_LEN = 20

# market_index_latest.name is String(120).
MAX_INDEX_NAME_LEN = 120

# cse.lk's own symbols for the two headline indices, mapped to the names used
# everywhere else in this project -- the dissertation, the UI label and every
# other reference say "ASPI", and CSE's "S&P SL20" contains a space, which makes
# a poor key. The 20 industry-group symbols (BNK, EGY, CG, ...) are CSE's own
# identifiers and are stored verbatim.
INDEX_CODE_ALIASES = {
    "ASI": "ASPI",
    "S&P SL20": "SPSL20",
}

# The All Share Price Index, under the code this project stores it as.
ASPI_CODE = "ASPI"

# The two market-wide indices, in the order a list UI wants them, as distinct from
# the 20 industry groups. Named explicitly rather than inferred from "has no
# turnover": cse.lk reports turnover per industry group, but a group in which
# nothing traded gets null rather than zero, so on a quiet session a real sector
# is indistinguishable from a headline index by that test. It happened -- Household
# & Personal Products had no trades and sorted itself between ASPI and S&P SL20 at
# the top of /stocks/indices.
HEADLINE_INDEX_CODES = ("ASPI", "SPSL20")

# A reading timestamped further ahead than this is rejected. The upsert into
# market_index_latest refuses to move a row backwards in time, so one bad
# far-future timestamp would freeze that index permanently -- no later reading
# could ever replace it. A day of slack absorbs any real clock skew between
# cse.lk and this server.
MAX_INDEX_CLOCK_SKEW = timedelta(days=1)


# ■■ Validation ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
def validate_market_record(rec: dict) -> bool:
    """True if a scraped CSE record is worth persisting.

    The trade summary API returns placeholder rows with a zero price for
    instruments that have not traded yet in the session; those would otherwise
    be stored as a genuine LKR 0.00 quote.
    """
    symbol = (rec.get('symbol') or '').strip()
    if not symbol or len(symbol) > MAX_SYMBOL_LEN:
        return False

    price = rec.get('last_price')
    if not isinstance(price, (int, float)) or price <= 0:
        return False

    volume = rec.get('volume')
    if volume is not None and (not isinstance(volume, (int, float)) or volume < 0):
        return False

    return True


def validate_index_record(rec: dict, now: datetime | None = None) -> bool:
    """True if a scraped index reading is worth persisting.

    The timestamp checks are the substantive ones. ``recorded_at`` comes from
    cse.lk's own ``transactionTime`` field, and both of its failure modes are
    damaging rather than merely untidy:

    *   **Missing or zero** would land at the Unix epoch, which sorts before
        every real reading — so "the latest value" would be a 1970 row forever.
    *   **Far in the future** would freeze the index. The upsert into
        ``market_index_latest`` will not move a row backwards in time, so no
        subsequent reading could ever replace it.
    """
    code = (rec.get('index_code') or '').strip()
    if not code or len(code) > MAX_SYMBOL_LEN:
        return False

    if not (rec.get('name') or '').strip():
        return False

    value = rec.get('value')
    if not isinstance(value, (int, float)) or value <= 0:
        return False

    recorded_at = rec.get('recorded_at')
    if not isinstance(recorded_at, datetime):
        return False
    if recorded_at.tzinfo is None:
        return False
    if recorded_at.year < 2000:
        return False
    if recorded_at > (now or datetime.now(timezone.utc)) + MAX_INDEX_CLOCK_SKEW:
        return False

    return True


def validate_news_record(art: dict) -> bool:
    """True if a scraped article looks like a real story.

    Delegates to ``app.services.news`` so there is one bar, applied both at parse
    time and again before the insert. Kept importable from here because
    ``tests/`` and ``routers/stocks.py`` reach for it at this path.
    """
    from app.services.news import validate_news_record as _impl
    return _impl(art)


# ■■ CSE Scraper ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
async def scrape_and_save_cse(db: Session) -> int:
    """Scrape CSE data into market_data, market_data_latest and daily_close.

    Returns rows inserted into the history table.

    Three things here are load-bearing beyond the insert itself:

    *   **One timestamp for the whole scrape.** ``recorded_at`` is computed once,
        before the loop. It used to be ``datetime.now()`` per row, which stamped a
        single scrape with several microsecond-apart values — the live table shows
        283 rows under 6 distinct timestamps from one run. That makes "the latest
        snapshot" unidentifiable, which anything aggregating a daily close has to
        be able to group by.
    *   **market_data_latest is updated in the same transaction.** If it were a
        separate commit, a crash between the two would leave the price every read
        path serves permanently behind the history.
    *   **daily_close is upserted here, not by an end-of-day task.** The
        remediation plan called for a separate nightly job reading back the last
        snapshot of each trading day. That loses any day the job misses, and there
        is nothing to recover it from — cse.lk publishes no history endpoint.
        Folding it into the 15-minute scrape makes every run a checkpoint, so the
        worst a missed run costs is resolution within a day rather than the day
        itself. It also keeps all three writes in one transaction.
    """
    records = await scrape_cse_data()
    recorded_at = datetime.now(timezone.utc)

    rows: list[MarketData] = []
    accepted: list[dict] = []
    skipped = 0
    for rec in records:
        if not validate_market_record(rec):
            skipped += 1
            continue
        accepted.append(rec)
        rows.append(MarketData(
            symbol=rec['symbol'],
            price=rec['last_price'],
            change=rec.get('change'),
            change_pct=rec.get('change_pct'),
            volume=rec.get('volume'),
            market_cap=rec.get('market_cap'),
            recorded_at=recorded_at,
            last_traded_at=rec.get('last_traded_at'),
        ))

    db.add_all(rows)
    # Assign market_id before building the upsert, so market_data_latest points at
    # the history row it was copied from.
    db.flush()
    _refresh_latest(db, rows)
    days = _upsert_daily_close(db, accepted, recorded_at)
    db.commit()

    logger.info('Saved %d CSE records (%d scraped, %d rejected) at %s; '
                '%d daily_close rows touched',
                len(rows), len(records), skipped, recorded_at.isoformat(), days)
    return len(rows)


def _upsert_daily_close(db: Session, records: list[dict], now: datetime) -> int:
    """Fold accepted scrape records into one ``daily_close`` row per symbol-day.

    Returns rows in the upsert payload — not rows changed, which is usually fewer
    and legitimately zero once a session has been fully captured.
    """
    payload = _daily_close_payload(records, now)
    _warn_on_inconsistent_ohlc(payload)
    return _upsert_latest(db, DailyClose, ('symbol', 'trade_date'), payload,
                          guard='last_traded_at')


def _warn_on_inconsistent_ohlc(payload: list[dict]) -> list[str]:
    """Log symbols whose close falls outside their own high/low. Returns them.

    cse.lk's own fields disagree for a minority of symbols, and the disagreement
    is systematic rather than random. In the sample this was written against, 19
    of 271 had a ``closingPrice`` outside their ``[low, high]``, and in **every**
    one of those cases ``closingPrice``, ``price`` and ``previousClose`` were all
    the same number — the previous session's close — while ``open``, ``high`` and
    ``low`` reflected the current session. INME traded between 1800 and 1875 with
    seven trades, and reported a close of 1681.

    All 19 were thinly traded (1–7 trades), so the likeliest reading is that the
    feed's price field lags for illiquid instruments while the range updates
    normally.

    Not clamped and not dropped. Clamping would invent a price the exchange never
    printed; dropping would discard the only record of those symbols' sessions,
    including the open/high/low that are not in question. Stored as reported, and
    logged so the inconsistency is a known property of the data rather than a
    surprise in a chart.

    Nothing is stored to mark the affected rows because the condition is a
    one-line predicate over columns already present —
    ``WHERE close < low OR close > high`` — so a stored flag would be a second
    copy of a fact that can go stale.
    """
    bad = [p['symbol'] for p in payload
           if p['low'] is not None and p['high'] is not None
           and not (p['low'] <= p['close'] <= p['high'])]
    if bad:
        logger.warning(
            "%d of %d symbols report a close outside their own high/low: %s%s. "
            "Stored as reported — cse.lk's price field lags for thinly traded "
            "instruments while the range updates. Query them with "
            "'close < low OR close > high'.",
            len(bad), len(payload), ', '.join(sorted(bad)[:8]),
            '' if len(bad) <= 8 else f' and {len(bad) - 8} more')
    return bad


def _aware_trade_date(value) -> date | None:
    """The calendar date of a timezone-aware timestamp, or None if it is not one.

    Duck-typed rather than ``isinstance(value, datetime)``, which would be the
    obvious spelling and is the wrong one here. Tests fake the clock by replacing
    this module's ``datetime`` name with a stub object, so an ``isinstance`` check
    against that name raises ``TypeError`` instead of answering the question. The
    two attributes actually used downstream are the two checked.

    ``tzinfo`` is not a formality. ``trade_date`` is taken with ``.date()``, and on
    a naive value that silently reads whichever calendar day the server's own
    offset implies — Colombo is UTC+5:30, so a late CSE session is exactly the
    case where it would land on the wrong day.
    """
    tzinfo = getattr(value, 'tzinfo', None)
    to_date = getattr(value, 'date', None)
    if tzinfo is None or not callable(to_date):
        return None
    return to_date()


def _daily_close_payload(records: list[dict], now: datetime) -> list[dict]:
    """Build the ``daily_close`` upsert payload: one entry per symbol-day.

    ``trade_date`` is the date of the exchange's ``lastTradedTime``, never of
    ``now``. That is the entire point of the table and the reason this function
    exists separately from the insert — see ``DailyClose``.

    A record without ``last_traded_at`` is dropped rather than dated from our
    clock. In practice the live feed supplies it for all 271 symbols, but the
    fallback would silently reintroduce exactly the bug the column was added to
    fix, so there is no fallback.

    Deduplicated by ``(symbol, trade_date)`` keeping the **latest**
    ``last_traded_at``, because Postgres refuses to touch the same target row
    twice in one statement. The trade summary has returned duplicate instrument
    rows before, and one scrape could in principle carry two dates for one symbol
    if it straddled midnight UTC — Colombo is UTC+5:30, so a CSE session never
    does, but the dedup does not depend on that holding.

    ``close`` prefers the feed's ``closingPrice`` and falls back to ``last_price``.
    Those two agreed on all 271 symbols in the live sample, so the fallback is
    effectively dead code kept because ``close`` is NOT NULL and ``last_price`` is
    the field validation has already proven positive.

    What they did **not** agree with, for 19 of those 271, was the day's own
    ``[low, high]``. That is a property of the feed rather than of this function —
    see ``_warn_on_inconsistent_ohlc``, which logs it — and the value is stored as
    reported rather than clamped into range.
    """
    best: dict[tuple, dict] = {}
    for rec in records:
        at = rec.get('last_traded_at')
        trade_date = _aware_trade_date(at)
        if trade_date is None:
            continue

        key = (rec['symbol'], trade_date)
        if key in best and best[key]['last_traded_at'] >= at:
            continue

        close = rec.get('close')
        if not isinstance(close, (int, float)) or close <= 0:
            close = rec['last_price']

        best[key] = {
            'symbol': rec['symbol'],
            'trade_date': trade_date,
            'open': rec.get('open'),
            'high': rec.get('high'),
            'low': rec.get('low'),
            'close': close,
            'previous_close': rec.get('previous_close'),
            'volume': rec.get('volume'),
            'turnover': rec.get('turnover'),
            'trades': rec.get('trades'),
            'last_traded_at': at,
            'updated_at': now,
        }
    return list(best.values())


def _latest_payload(rows: list[MarketData], now: datetime) -> list[dict]:
    """Build the ``market_data_latest`` upsert payload: one entry per symbol.

    Split out from ``_refresh_latest`` because this is the part with a decision in
    it, and it can be tested without a database.

    A single scrape can report the same symbol more than once (the trade summary
    has returned duplicate instrument rows), and Postgres refuses to touch the
    same target row twice in one statement -- "ON CONFLICT DO UPDATE command
    cannot affect row a second time". Deduplicating here keeps the *last*
    occurrence, matching what an unguarded sequence of single-row upserts would
    have left behind.
    """
    by_symbol = {r.symbol: r for r in rows}
    return [{
        'symbol': r.symbol,
        'market_id': r.market_id,
        'price': r.price,
        'change': r.change,
        'change_pct': r.change_pct,
        'volume': r.volume,
        'market_cap': r.market_cap,
        'recorded_at': r.recorded_at,
        # Carried through even though the guard reads ``recorded_at``. Without it
        # the column exists and is permanently NULL, and a portfolio snapshot has
        # no way to say which session it priced a holding from.
        'last_traded_at': r.last_traded_at,
        'updated_at': now,
    } for r in by_symbol.values()]


def _upsert_latest(db: Session, model, key, payload: list[dict],
                   guard: str = 'recorded_at') -> int:
    """Upsert ``payload`` into a keyed table, never moving a row backwards.

    Shared by ``market_data_latest``, ``market_index_latest``, ``daily_close`` and
    ``portfolio_snapshots``. They differ in shape — two are one-row-per-key
    mirrors of an append-only history, one is a per-day series, one is a
    valuation log — but all four need the same two guarantees, so the guarantees
    live here once.

    The ``WHERE`` clause is the one with teeth. A retried Celery task, or two
    scrapes overlapping, can present an older reading after a newer one has
    already landed; without the guard the older one would win purely by arriving
    second. ``<=`` rather than ``<`` so that re-scraping an unchanged reading
    still refreshes ``updated_at`` — which is how a caller tells "the market is
    closed" from "the scraper has died".

    ``key`` is a column name or a sequence of them, so a composite primary key
    like ``daily_close``'s ``(symbol, trade_date)`` works without a second
    function. ``guard`` names the column the no-backwards comparison reads:
    ``daily_close`` orders by ``last_traded_at``, since its ``updated_at`` is our
    clock and would let a stale scrape win by being written later.

    Every dict must have identical keys; ``pg_insert().values(list)`` builds one
    statement for the whole batch. Checked explicitly because the alternative is
    an opaque error from deep inside SQLAlchemy's compiler.

    Does not commit — the caller owns the transaction, so history and latest move
    together or not at all.
    """
    if not payload:
        return 0

    keys = [key] if isinstance(key, str) else list(key)

    expected = payload[0].keys()
    if any(row.keys() != expected for row in payload[1:]):
        raise ValueError(
            f'{model.__tablename__} upsert payload has inconsistent keys')
    missing = [k for k in keys if k not in expected]
    if missing:
        raise ValueError(
            f'{model.__tablename__} upsert payload is missing its key '
            f'{missing[0]!r}')
    if guard not in expected:
        raise ValueError(
            f'{model.__tablename__} upsert payload is missing its guard column '
            f'{guard!r}')

    updatable = [c for c in expected if c not in keys]

    stmt = pg_insert(model).values(payload)
    db.execute(stmt.on_conflict_do_update(
        index_elements=[getattr(model, k) for k in keys],
        set_={c: stmt.excluded[c] for c in updatable},
        where=getattr(model, guard) <= stmt.excluded[guard],
    ))
    return len(payload)


def _refresh_latest(db: Session, rows: list[MarketData]) -> int:
    """Upsert one row per symbol into market_data_latest."""
    return _upsert_latest(db, MarketDataLatest, 'symbol',
                          _latest_payload(rows, datetime.now(timezone.utc)))


async def scrape_cse_data() -> list[dict]:
    """Returns list of stock dicts from CSE trade summary API.

    The endpoint returns 23 fields per symbol and this used to keep six of them.
    The rest are what a price chart is made of: ``open``, ``high``, ``low``,
    ``closingPrice``, ``previousClose``, ``turnover``, ``tradevolume``, and above
    all ``lastTradedTime``.

    ``lastTradedTime`` is the important one. It is the exchange's own timestamp
    for this symbol's last trade, and without it there is no way to tell which
    *session* a quote belongs to — cse.lk keeps serving the last session's numbers
    while the market is shut, so a Thursday scrape of Tuesday's close looks like
    Thursday data. ``daily_close.trade_date`` is derived from it.

    Note it is **per symbol**, not market-wide: a live scrape returns 271 symbols
    with 271 distinct values, spanning about five hours within one trading date.
    So it cannot double as the snapshot timestamp that ``recorded_at`` provides,
    and both are stored.
    """
    results = []
    try:
        async with httpx.AsyncClient(headers=CSE_HEADERS, timeout=60) as c:
            response = await c.post(CSE_TRADE_SUMMARY_URL)
            response.raise_for_status()
            data = response.json()

            raw_records = data.get('reqTradeSummery', [])
            for rec in raw_records:
                try:
                    results.append({
                        'symbol': rec.get('symbol', '').strip(),
                        'name': (rec.get('name') or '').strip() or None,
                        'last_price': float(rec.get('price', 0)),
                        'change': float(rec.get('change', 0)),
                        'change_pct': float(rec.get('percentageChange', 0)),
                        'volume': float(rec.get('sharevolume', 0)),
                        'market_cap': float(rec.get('marketCap', 0)) if rec.get('marketCap') else None,
                        # The session's range. Kept as None rather than 0.0 when
                        # absent: a symbol whose only trade was its open has no
                        # meaningful high, and storing zero would drag every chart
                        # axis to the origin.
                        'open': _opt_float(rec.get('open')),
                        'high': _opt_float(rec.get('high')),
                        'low': _opt_float(rec.get('low')),
                        'close': _opt_float(rec.get('closingPrice')),
                        'previous_close': _opt_float(rec.get('previousClose')),
                        'turnover': _opt_float(rec.get('turnover')),
                        # Arrives as a float (7.0) but counts discrete trades.
                        'trades': _opt_int(rec.get('tradevolume')),
                        'last_traded_at': _epoch_ms_to_utc(rec.get('lastTradedTime')),
                    })
                except (ValueError, TypeError) as e:
                    logger.debug('Record parse error: %s', e)
    except Exception as e:
        logger.error('CSE scrape failed: %s', e)
        raise

    if not results:
        status = await get_market_status()
        if status:
            logger.info('Market is currently in "%s" status - No trade records available yet.', status)
        else:
            logger.warning('No CSE trade records found and market status could not be determined.')
            
    return results

async def get_market_status() -> Optional[str]:
    """Checks the current status of the CSE market."""
    try:
        async with httpx.AsyncClient(headers=CSE_HEADERS, timeout=10) as c:
            r = await c.post(CSE_MARKET_STATUS_URL)
            if r.status_code == 200:
                return r.json().get('status')
    except Exception as e:
        logger.debug('Failed to fetch market status: %s', e)
    return None

# ■■ CSE Index Scraper ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
async def scrape_and_save_indices(db: Session) -> int:
    """Scrape all CSE indices into market_index and refresh market_index_latest.

    Returns the number of readings **accepted**, not the number of history rows
    inserted. Those differ constantly and deliberately: ``(index_code,
    recorded_at)`` is unique, so re-scraping a session that has already been
    stored inserts nothing. Since the task runs every 15 minutes and the market
    is open for five hours a day, "0 rows inserted" is the normal, correct
    outcome most of the time, and returning it would read like a failure. Both
    numbers are logged.

    Replaces the hardcoded ``12450.80 / +1.2%`` the dashboard served as ASPI. The
    real reading at the time this was written was ``21279.65 / -0.31%`` — out by
    71% and the wrong way.
    """
    records = await scrape_index_data()

    # One clock read for the whole scrape, threaded through explicitly, so that
    # every row of one run shares an updated_at and nothing has to be patched to
    # test it. Note this is *our* clock; recorded_at comes from the exchange.
    now = datetime.now(timezone.utc)

    rows: list[dict] = []
    skipped = 0
    for rec in records:
        if not validate_index_record(rec, now):
            skipped += 1
            continue
        rows.append(rec)

    inserted = _insert_index_history(db, rows)
    _refresh_index_latest(db, rows, now)
    db.commit()

    logger.info('Indices: %d accepted (%d scraped, %d rejected), '
                '%d new history rows', len(rows), len(records), skipped, inserted)
    return len(rows)


def _insert_index_history(db: Session, rows: list[dict]) -> int:
    """Append new index readings, ignoring ones already stored.

    ``ON CONFLICT DO NOTHING`` on ``(index_code, recorded_at)`` makes the whole
    scrape idempotent. Without it, every 15-minute run against a closed market
    would add 22 more copies of the same closing values — cse.lk keeps serving
    the last session until the next one opens.

    That treats ``(index_code, recorded_at)`` as a version key: same key, same
    reading. cse.lk does not entirely honour that — see
    ``_warn_on_revised_readings``, which reports it when it happens instead of
    letting the newer value vanish unremarked.

    Returns rows actually inserted.
    """
    if not rows:
        return 0

    columns = ('index_code', 'value', 'change', 'change_pct', 'previous_close',
               'turnover', 'volume', 'trades', 'recorded_at')
    payload = [{c: r[c] for c in columns} for r in rows]

    _warn_on_revised_readings(db, payload)

    stmt = pg_insert(MarketIndex).values(payload)
    result = db.execute(stmt.on_conflict_do_nothing(
        constraint='uq_market_index_code_recorded_at'))
    return result.rowcount or 0


def _warn_on_revised_readings(db: Session, payload: list[dict]) -> list[str]:
    """Log any reading cse.lk has restated under a timestamp already stored.

    ``recorded_at`` is cse.lk's own ``transactionTime``, and the insert above
    trusts it as a version key. Each index carries its **own** timestamp — the
    last time that index was recalculated — not one market-wide one, and those
    are not uniformly fresh. In the sample this was written against, the 20
    industry groups were all stamped within a couple of minutes of the close, but
    S&P SL20's was stamped 09:30 local, five hours earlier, while carrying the
    same value the dedicated ``snpData`` endpoint reported for the close.

    So an index whose timestamp stalls while its value moves is a real
    possibility, and for that index ``DO NOTHING`` would keep the first value and
    discard every later one. The user-facing number is unaffected —
    ``market_index_latest``'s guard admits an equal timestamp, so it still tracks
    the newest value — but the history row for that timestamp stays at whatever
    was seen first.

    Log it rather than resolve it: overwriting history would make an append-only
    table mutable, and storing both would need a version key cse.lk does not
    provide. Returns the affected codes so callers can assert on them.
    """
    keys = [(p['index_code'], p['recorded_at']) for p in payload]
    stored = db.execute(
        select(MarketIndex.index_code, MarketIndex.recorded_at, MarketIndex.value)
        .where(tuple_(MarketIndex.index_code, MarketIndex.recorded_at).in_(keys))
    ).all()
    if not stored:
        return []

    incoming = {(p['index_code'], p['recorded_at']): p['value'] for p in payload}
    revised = [
        (code, old, incoming[(code, at)])
        for code, at, old in stored
        if incoming.get((code, at)) is not None and incoming[(code, at)] != old
    ]
    for code, old, new in revised:
        logger.warning(
            'Index %s restated at an unchanged timestamp: stored %s, cse.lk now '
            'reports %s. Keeping the stored history row; the latest reading still '
            'tracks the new value.', code, old, new)
    return [code for code, _, _ in revised]


def _index_latest_payload(rows: list[dict], now: datetime) -> list[dict]:
    """Build the ``market_index_latest`` upsert payload: one entry per index.

    Deduplicated by ``index_code`` for the same reason as the quote payload —
    Postgres will not let ``ON CONFLICT DO UPDATE`` touch one target row twice in
    a single statement. cse.lk returns each index once today, but two raw symbols
    aliasing to one code (see ``INDEX_CODE_ALIASES``) would be enough to break
    the whole scrape rather than just the duplicate.
    """
    by_code = {r['index_code']: r for r in rows}
    return [{
        'index_code': r['index_code'],
        'name': r['name'],
        'value': r['value'],
        'change': r['change'],
        'change_pct': r['change_pct'],
        'previous_close': r['previous_close'],
        'turnover': r['turnover'],
        'volume': r['volume'],
        'trades': r['trades'],
        'recorded_at': r['recorded_at'],
        'updated_at': now,
    } for r in by_code.values()]


def _refresh_index_latest(db: Session, rows: list[dict], now: datetime) -> int:
    """Upsert one row per index into market_index_latest."""
    return _upsert_latest(db, MarketIndexLatest, 'index_code',
                          _index_latest_payload(rows, now))


async def scrape_index_data() -> list[dict]:
    """Fetch every CSE index from the allSectors endpoint.

    Returns parsed dicts ready for ``validate_index_record``. A network failure
    returns an empty list rather than raising, matching ``scrape_cse_data``, so a
    scrape that cannot reach cse.lk is a no-op instead of a lost transaction.
    """
    try:
        async with httpx.AsyncClient(headers=CSE_HEADERS, timeout=60) as c:
            response = await c.post(CSE_ALL_SECTORS_URL)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error('CSE index scrape failed: %s', e)
        return []

    if not isinstance(data, list):
        logger.error('allSectors returned %s, expected a list of indices',
                     type(data).__name__)
        return []

    results = []
    for rec in data:
        try:
            results.append(_parse_index_record(rec))
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.debug('Index record parse error: %s', e)

    if not results:
        status = await get_market_status()
        logger.warning('No CSE index readings parsed (market status: %s)',
                       status or 'unknown')

    return results


def _parse_index_record(rec: dict) -> dict:
    """Map one allSectors entry onto the market_index columns.

    ``symbol`` is the key rather than ``indexCode``, which looks like the
    obvious choice and is not: cse.lk leaves ``indexCode`` **null** for both
    headline indices, so it is neither unique nor complete. ``symbol`` was
    confirmed distinct across all 22 rows.

    ``name`` is CSE's short label ("Banks", "Energy") rather than the formal
    ``indexName`` ("S&P/CSE Banks Index"), because the short form is what a UI
    legend can actually fit. It is stored verbatim, uppercase and all.

    ``transactionTime`` is **per index**, not market-wide: it is the last time
    that index was recalculated, so the 22 records carry 22 different timestamps.
    They are not uniformly fresh — see ``_warn_on_revised_readings`` — and any
    daily-close series must therefore key off the trading date rather than
    treating this timestamp as the moment of the close.
    """
    raw_code = (rec.get('symbol') or '').strip()
    return {
        'index_code': INDEX_CODE_ALIASES.get(raw_code, raw_code),
        'name': (rec.get('name') or '').strip()[:MAX_INDEX_NAME_LEN],
        'value': _opt_float(rec.get('indexValue')),
        'change': _opt_float(rec.get('change')),
        'change_pct': _opt_float(rec.get('percentage')),
        'previous_close': _opt_float(rec.get('sectorPreviousClose')),
        # Null for ASPI and S&P SL20 -- CSE reports activity per industry group.
        'turnover': _opt_float(rec.get('sectorTurnoverToday')),
        'volume': _opt_float(rec.get('sectorVolumeToday')),
        'trades': _opt_int(rec.get('sectorTradeToday')),
        'recorded_at': _epoch_ms_to_utc(rec.get('transactionTime')),
    }


# ■■ News Scraper ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
#
# The implementation moved to app/services/news.py in I-08. What was here was
# ~50 lines that got every field wrong: a blanket ``soup.find_all('h3')[:20]``
# for headlines, ``h3.find_next('p')`` for the summary — which returned ft.lk's
# footer contact block, so all 60 stored rows had ``summary = 'Editorial :'`` —
# no publish date parsing at all, ``symbol`` hardcoded to ``'GENERAL'`` unless a
# caller named one ticker, and an ``httpx.AsyncClient`` that was accepted as an
# argument and then ignored in favour of ``urllib.request`` in a thread.
#
# These two names stay because five call sites import them from here
# (``routers/stocks.py``, ``tasks/scrape_tasks.py``, ``scrape_now.py``). They are
# thin delegations, not wrappers with behaviour of their own.

async def scrape_and_save_news(db: Session, symbol: str = None) -> list[int]:
    """Scrape both news sources and persist. See app.services.news.

    ``symbol`` is a *filter* on which stories are kept, not a label written to
    every row. That inversion is the core of I-08: it used to be assigned to
    ``news_sentiment.symbol`` for every article the run produced, so a caller
    passing nothing — which is every caller except the on-demand enrichment path
    — stamped the whole batch ``GENERAL`` regardless of which companies the
    stories actually named.
    """
    from app.services.news import scrape_and_save_news as _impl
    return await _impl(db, symbol)


async def scrape_news(symbol: str = None) -> list[dict]:
    """Fetch and parse articles without persisting. See app.services.news."""
    from app.services import news as news_service

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS,
                                 timeout=news_service.FETCH_TIMEOUT,
                                 follow_redirects=True) as client:
        articles = await news_service.scrape_news_articles(client)

    if symbol:
        want = symbol.upper()
        articles = [a for a in articles
                    if want in f"{a['title']} {a.get('body', '')}".upper()]
    return articles


# ■■ Helpers ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
def _clean(t): return ' '.join(t.split()).strip()

def _opt_float(v):
    """float(v), or None if v is absent or not a number.

    Distinct from ``_to_float`` below, which parses formatted strings out of
    HTML. This one guards JSON fields that are legitimately null: cse.lk omits
    turnover, volume and trades for ASPI and S&P SL20, and coercing those to 0.0
    would claim the headline indices had no activity rather than that the figure
    is not published per index.
    """
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(',', '').strip())
    except (TypeError, ValueError):
        return None


def _opt_int(v):
    """int(v), or None. cse.lk sends trade counts as floats (116.0)."""
    f = _opt_float(v)
    return None if f is None else int(f)


def _epoch_ms_to_utc(ms):
    """Epoch milliseconds to a tz-aware UTC datetime, or None.

    Zero is rejected rather than treated as a valid instant: it would become
    1970-01-01, which sorts before every real reading, so the "latest" value for
    that index would be the bad row forever.
    """
    value = _opt_float(ms)
    if not value or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _to_float(t):
    try: return float(t.replace(',','').strip())
    except: return None
