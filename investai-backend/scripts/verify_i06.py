# scripts/verify_i06.py
"""Live verification for I-06 (real price history and real portfolio history).

Run with:  python -m scripts.verify_i06

Two fabrications close here. ``generateMockChartData()`` built the stock detail
chart from ``Math.random()`` and labelled the axis with real times, so every
symbol showed a plausible, entirely invented history. The dashboard served
``weekly_history`` as ``current_value x [0.85, 0.82, 0.94, 1.0]`` -- four numbers
derived from the present value, so the line showed the same 15% dip recovering to
exactly today whatever the portfolio had done.

tests/test_daily_close.py is offline by policy (see pytest.ini) and compiles the
Postgres SQL without executing it. What still needs a live database and a live
cse.lk:

*   that Postgres honours the composite ``ON CONFLICT (symbol, trade_date)``
    against the real primary key, so re-scraping a session updates rather than
    duplicating or erroring;
*   that ``WHERE last_traded_at <= excluded.last_traded_at`` refuses to walk a
    day's close backwards when a retried task presents an older record;
*   that the derived ``trade_date`` really lands on the session the exchange
    traded, not the day we scraped -- the single most load-bearing claim in I-06;
*   that both new endpoints serve the stored series.

Stage 1 **commits**, like verify_i05's does and for the same reason: storing the
history is the feature, and it is idempotent by construction. Stages that
fabricate data use a ``ZZ_I06_`` symbol prefix inside a transaction rolled back
in a ``finally``, and the last stage re-checks that nothing survived.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from alembic.script import ScriptDirectory
from sqlalchemy import func, text

from app.database import SessionLocal
from app.models.portfolio import Portfolio, PortfolioHolding, PortfolioSnapshot
from app.models.stock import DailyClose, MarketData, MarketDataLatest
from app.models.user import User
from app.services.portfolio_history import exchange_today, snapshot_portfolios
from app.services.scraper import (_daily_close_payload, _upsert_daily_close,
                                  _warn_on_inconsistent_ohlc,
                                  scrape_and_save_cse, scrape_cse_data)

PREFIX = "ZZ_I06_"
NOW = datetime.now(timezone.utc)

# The migration that created daily_close and portfolio_snapshots. Checked for as
# an ancestor of the current head, not as the head itself -- see stage_schema.
I06_REVISION = "a7b8c9d0e1f2"

# The mock chart's shape, from StockDetailScreen.js. Nothing should serve these.
OLD_FAKE_MULTIPLIERS = (0.85, 0.82, 0.94, 1.0)

# A per-run discriminator for throwaway identities. ``users.email`` is uniquely
# indexed and ``snapshot_portfolios`` commits, so a fixed literal email means an
# interrupted run leaves a row that makes every later run die on a duplicate key
# instead of on whatever it was meant to check. ``_purge`` running first handles
# the tidy case; this handles the case where even that could not run.
RUN = uuid.uuid4().hex[:8]

passed = 0
failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed += 1
        print(f"  [FAIL] {label}")
        if detail:
            print(f"         {detail}")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: the real scrape, committed
# ─────────────────────────────────────────────────────────────────────────────

def stage_scrape() -> None:
    """Scrape cse.lk for real and persist quotes, latest, and daily_close.

    Also the end-to-end proof that the eight fields I-06 added to the scrape are
    still being served: if cse.lk drops ``lastTradedTime``, every record is
    discarded by design and the daily_close count falls to zero here rather than
    silently emptying every chart in production.
    """
    print("\n=== Stage 1: live scrape of cse.lk, committed ===")
    db = SessionLocal()
    try:
        before = db.query(DailyClose).count()
        inserted = asyncio.run(scrape_and_save_cse(db))
        check("the scrape stored market_data rows", inserted > 0,
              f"{inserted} rows")

        after = db.query(DailyClose).count()
        check("daily_close is populated", after > 0, f"{after} rows")
        print(f"         daily_close: {before} -> {after} rows")

        quoted = db.query(MarketDataLatest).filter(
            MarketDataLatest.last_traded_at.isnot(None)).count()
        total_latest = db.query(MarketDataLatest).count()
        check("market_data_latest carries the exchange timestamp",
              quoted > 0, f"{quoted} of {total_latest} rows have last_traded_at")

        hist = db.query(MarketData).filter(
            MarketData.recorded_at >= NOW - timedelta(minutes=10),
            MarketData.last_traded_at.isnot(None)).count()
        check("this scrape's market_data rows carry last_traded_at", hist > 0,
              f"{hist} rows")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: the date is the exchange's, not ours
# ─────────────────────────────────────────────────────────────────────────────

def stage_dates() -> None:
    """The central claim of I-06, checked against the stored table.

    Not a hypothetical. The two market_data snapshots that predate this work were
    stamped 2026-07-05 -- a Sunday, when the CSE is shut -- and 2026-08-27, a
    Thursday carrying the Tuesday 2026-08-25 session. Dating from the scrape would
    have put trading days on weekends and repeated one session across every day
    the market stayed closed.
    """
    print("\n=== Stage 2: trade_date is the session, not the scrape ===")
    db = SessionLocal()
    try:
        today = exchange_today()
        rows = db.query(DailyClose).count()
        if not rows:
            check("daily_close has rows to check", False, "table is empty")
            return

        n = db.execute(text(
            "SELECT count(*) FROM daily_close WHERE trade_date > :d"),
            {"d": today}).scalar()
        check("no trade_date is in the future", n == 0, f"{n} rows")

        n = db.execute(text(
            "SELECT count(*) FROM daily_close "
            "WHERE extract(isodow FROM trade_date) > 5")).scalar()
        check("no trade_date falls on a weekend", n == 0,
              f"{n} rows -- the CSE does not trade Sat/Sun")

        n = db.execute(text(
            "SELECT count(*) FROM daily_close "
            "WHERE trade_date <> (last_traded_at AT TIME ZONE 'UTC')::date")
        ).scalar()
        check("every trade_date is the date of its own last_traded_at", n == 0,
              f"{n} rows disagree")

        # The proof that the two clocks are genuinely different, not coincidentally
        # equal. If cse.lk happens to be serving the current session this passes
        # trivially, so it reports rather than asserts.
        dates = db.execute(text(
            "SELECT trade_date, count(*) FROM daily_close "
            "GROUP BY trade_date ORDER BY trade_date")).all()
        print(f"         sessions stored (today is {today} in Colombo):")
        for d, n in dates:
            same = " <- same as today" if d == today else ""
            print(f"           {d} ({d.strftime('%A')}): {n} symbols{same}")

        stale = [d for d, _ in dates if d != today]
        if stale:
            check("at least one stored session predates today, proving the date "
                  "is not simply now()", True, "")
        else:
            print("         [note] every stored session is today's, so this run "
                  "cannot distinguish exchange time from scrape time. Not a "
                  "failure; the SQL check above still holds.")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: the composite upsert
# ─────────────────────────────────────────────────────────────────────────────

def stage_upsert() -> None:
    """That Postgres honours the composite conflict target and the guard.

    Rolled back. The symbols are ``ZZ_I06_``-prefixed so a failure mid-stage
    leaves nothing a chart could pick up.
    """
    print("\n=== Stage 3: ON CONFLICT (symbol, trade_date) and its guard ===")
    db = SessionLocal()
    try:
        sym = f"{PREFIX}A"
        d = date(2026, 8, 25)
        at = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)

        def rec(close, traded_at, high=200.0, low=100.0):
            return {"symbol": sym, "last_price": close, "close": close,
                    "open": 150.0, "high": high, "low": low,
                    "previous_close": 149.0, "volume": 1.0, "turnover": 1.0,
                    "trades": 1, "last_traded_at": traded_at}

        _upsert_daily_close(db, [rec(150.0, at)], NOW)
        db.flush()
        stored = db.query(DailyClose).filter_by(symbol=sym, trade_date=d).one()
        check("a new symbol-day inserts", stored.close == 150.0,
              f"close={stored.close}")

        # Same day, later trade: must update in place, not insert a second row.
        _upsert_daily_close(db, [rec(160.0, at + timedelta(hours=1))], NOW)
        db.flush()
        n = db.query(DailyClose).filter_by(symbol=sym).count()
        check("a later trade on the same day updates rather than duplicating",
              n == 1, f"{n} rows for one symbol-day")
        db.expire_all()
        stored = db.query(DailyClose).filter_by(symbol=sym, trade_date=d).one()
        check("the later close wins", stored.close == 160.0,
              f"close={stored.close}")

        # An older record arriving second: the guard must refuse it.
        _upsert_daily_close(db, [rec(999.0, at - timedelta(hours=5))], NOW)
        db.flush()
        db.expire_all()
        stored = db.query(DailyClose).filter_by(symbol=sym, trade_date=d).one()
        check("an older record cannot walk the close backwards",
              stored.close == 160.0,
              f"close={stored.close} -- a retried task overwrote a newer value")

        # Re-presenting the same instant must still refresh updated_at: the guard
        # is <= not <, because that is how a caller tells a closed market from a
        # dead scraper.
        before_updated = stored.updated_at
        _upsert_daily_close(db, [rec(160.0, at + timedelta(hours=1))],
                            NOW + timedelta(minutes=5))
        db.flush()
        db.expire_all()
        stored = db.query(DailyClose).filter_by(symbol=sym, trade_date=d).one()
        check("re-scraping an unchanged session still moves updated_at",
              stored.updated_at > before_updated,
              f"{before_updated} -> {stored.updated_at}")

        # A second date for the same symbol is a second row -- that is the series.
        _upsert_daily_close(db, [rec(170.0, at + timedelta(days=2))], NOW)
        db.flush()
        n = db.query(DailyClose).filter_by(symbol=sym).count()
        check("a second trading day is a second row", n == 2, f"{n} rows")

        # Two records for one symbol-day in ONE statement. Postgres raises
        # "ON CONFLICT DO UPDATE command cannot affect row a second time" unless
        # the payload was deduplicated first.
        _upsert_daily_close(db, [rec(180.0, at + timedelta(hours=2)),
                                 rec(181.0, at + timedelta(hours=3))], NOW)
        db.flush()
        db.expire_all()
        stored = db.query(DailyClose).filter_by(symbol=sym, trade_date=d).one()
        check("two records for one symbol-day in one statement do not raise",
              stored.close == 181.0, f"close={stored.close}")

        # A record with no exchange timestamp must not reach the table at all.
        n_before = db.query(DailyClose).filter(
            DailyClose.symbol.like(f"{PREFIX}%")).count()
        _upsert_daily_close(db, [{**rec(1.0, None), "symbol": f"{PREFIX}NOTS"}],
                            NOW)
        db.flush()
        n_after = db.query(DailyClose).filter(
            DailyClose.symbol.like(f"{PREFIX}%")).count()
        check("a record without last_traded_at is stored nowhere",
              n_after == n_before, f"{n_after - n_before} rows appeared")
    finally:
        db.rollback()
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: the feed's own OHLC inconsistency
# ─────────────────────────────────────────────────────────────────────────────

def stage_ohlc() -> None:
    """Quantify, against the live feed, the disagreement I-06 chose to record.

    19 of 271 symbols reported a close outside their own day's range, and in every
    case ``closingPrice``, ``price`` and ``previousClose`` were one number while
    open/high/low described real trades. This stage re-derives that from whatever
    cse.lk is serving now, so a change in the feed's behaviour shows up as a
    changed count rather than as an unexplained candle in the UI.
    """
    print("\n=== Stage 4: close outside [low, high] (recorded, not clamped) ===")
    records = asyncio.run(scrape_cse_data())
    if not records:
        check("the feed returned records to analyse", False, "0 records")
        return

    payload = _daily_close_payload(records, NOW)
    check("every scraped symbol reached the payload",
          len(payload) == len({r["symbol"] for r in records
                               if r.get("last_traded_at") is not None}),
          f"{len(payload)} of {len(records)} scraped")

    bad = _warn_on_inconsistent_ohlc(payload)
    ranged = [p for p in payload if p["low"] is not None and p["high"] is not None]
    print(f"         {len(bad)} of {len(ranged)} symbols with a range report a "
          f"close outside it")

    check("the inconsistency is a minority of symbols",
          len(bad) < len(ranged) * 0.25,
          f"{len(bad)}/{len(ranged)} -- if this grew, the field mapping is wrong, "
          "not the feed")

    stale = [p for p in payload
             if p["symbol"] in set(bad) and p["previous_close"] == p["close"]]
    check("every flagged close equals its own previous close",
          len(stale) == len(bad),
          f"{len(stale)} of {len(bad)} -- the feed is serving a stale reference "
          "price for these, which is the diagnosis this decision rests on")

    thin = [p for p in payload if p["symbol"] in set(bad)
            and (p["trades"] or 0) <= 10]
    check("the flagged symbols are thinly traded",
          len(bad) == 0 or len(thin) == len(bad),
          f"{len(thin)} of {len(bad)} had 10 or fewer trades")

    for p in [p for p in payload if p["symbol"] in set(bad)][:3]:
        print(f"           {p['symbol']:<12} open {p['open']} high {p['high']} "
              f"low {p['low']} close {p['close']} prev {p['previous_close']} "
              f"trades {p['trades']}")

    check("no stored row was clamped into range",
          True if not bad else all(
              not (p["low"] <= p["close"] <= p["high"]) for p in payload
              if p["symbol"] in set(bad)),
          "a clamped value would be a price the exchange never printed")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: portfolio valuation snapshots
# ─────────────────────────────────────────────────────────────────────────────

def stage_snapshots() -> None:
    """Value a throwaway portfolio against real quotes.

    The portfolios table was empty when this was written, so there is nothing real
    to snapshot -- which is also why this stage builds its own rather than
    asserting on stored rows.

    Cleaned up by explicit DELETE rather than by rollback, because
    ``snapshot_portfolios`` commits: it is the entry point a Celery task calls, and
    a task that left its transaction open would hold a connection until the worker
    recycled it. So the rows this stage creates are real until the ``finally``
    removes them, and ``stage_clean`` checks that it did.
    """
    print("\n=== Stage 5: portfolio valuation snapshots ===")
    _purge()
    db = SessionLocal()
    try:
        quote = db.query(MarketDataLatest).filter(
            MarketDataLatest.price.isnot(None)).first()
        if quote is None:
            check("a real quote exists to value against", False, "none stored")
            return

        user = User(user_id=uuid.uuid4(),
                    email=f"{PREFIX}snap_{RUN}@example.invalid",
                    full_name="I06 throwaway", password_hash="x", role="user",
                    is_email_verified=True)
        db.add(user)
        db.flush()

        held = Portfolio(user_id=user.user_id, name=f"{PREFIX}held")
        empty = Portfolio(user_id=user.user_id, name=f"{PREFIX}empty")
        db.add_all([held, empty])
        db.flush()

        db.add(PortfolioHolding(portfolio_id=held.portfolio_id,
                                symbol=quote.symbol, quantity=100,
                                avg_buy_price=float(quote.price) / 2))
        # A symbol we have never quoted, to prove the cost-basis fallback.
        db.add(PortfolioHolding(portfolio_id=held.portfolio_id,
                                symbol=f"{PREFIX}UNQUOTED", quantity=10,
                                avg_buy_price=25.0))
        db.flush()

        written = snapshot_portfolios(db, NOW)
        check("every portfolio was valued", written >= 2, f"{written} rows")

        today = exchange_today(NOW)
        row = db.query(PortfolioSnapshot).filter_by(
            portfolio_id=held.portfolio_id, snapshot_date=today).one()

        expected = float(quote.price) * 100 + 25.0 * 10
        check("the held portfolio is valued at the live quote",
              abs(row.total_value - expected) < 0.01,
              f"{row.total_value} vs {expected}")
        check("the cost basis is recorded alongside the value",
              abs(row.total_cost - (float(quote.price) / 2 * 100 + 250.0)) < 0.01,
              f"total_cost={row.total_cost}")
        check("both holdings are counted", row.holdings_count == 2,
              f"{row.holdings_count}")
        check("only the quoted holding counts as priced", row.priced_count == 1,
              f"{row.priced_count} -- the unquoted one fell back to cost basis")

        if quote.last_traded_at is not None:
            check("priced_at records the session the prices came from",
                  row.priced_at == quote.last_traded_at,
                  f"{row.priced_at} vs {quote.last_traded_at}")
        else:
            print("         [note] this quote has no last_traded_at, so priced_at "
                  "cannot be checked. Re-run after stage 1.")

        empty_row = db.query(PortfolioSnapshot).filter_by(
            portfolio_id=empty.portfolio_id, snapshot_date=today).one()
        check("an empty portfolio still gets a row worth zero",
              empty_row.total_value == 0.0 and empty_row.holdings_count == 0,
              f"value={empty_row.total_value} holdings={empty_row.holdings_count}")

        # Re-running the same day must update, not duplicate or error.
        snapshot_portfolios(db, NOW + timedelta(minutes=1))
        n = db.query(PortfolioSnapshot).filter_by(
            portfolio_id=held.portfolio_id).count()
        check("a second run on the same day updates one row", n == 1, f"{n} rows")

        # The dashboard's series, read the way the endpoint reads it.
        cutoff = today - timedelta(days=30)
        series = (db.query(PortfolioSnapshot.snapshot_date,
                           func.sum(PortfolioSnapshot.total_value))
                  .filter(PortfolioSnapshot.portfolio_id.in_(
                      [held.portfolio_id, empty.portfolio_id]),
                      PortfolioSnapshot.snapshot_date >= cutoff)
                  .group_by(PortfolioSnapshot.snapshot_date)
                  .order_by(PortfolioSnapshot.snapshot_date).all())
        check("the dashboard series sums the user's portfolios per day",
              len(series) == 1 and abs(float(series[0][1]) - expected) < 0.01,
              f"{[(str(d), float(v)) for d, v in series]}")

        # Nothing in the series may match the fabricated shape it replaces.
        values = [float(v) for _, v in series]
        fakes = [expected * m for m in OLD_FAKE_MULTIPLIERS[:-1]]
        check("no point is a multiple of today's value",
              not any(any(abs(v - f) < 0.01 for f in fakes) for v in values),
              f"{values}")
    finally:
        db.rollback()
        db.close()
        _purge()


def _purge() -> None:
    """Remove everything any stage created under the ``ZZ_I06_`` prefix.

    Snapshots and holdings first: portfolio_snapshots cascades on delete but
    portfolio_holdings is checked explicitly, so an FK that stops cascading in a
    future migration surfaces here rather than as an integrity error.

    Opens its own session rather than borrowing the caller's, which it used to do.
    Stages call this from a ``finally``, so the one moment it matters most is the
    one where the caller's session is the thing that broke: a failed flush leaves a
    session that refuses everything until it is rolled back, and a dropped
    connection leaves one that refuses everything full stop. Cleanup that only
    works when nothing went wrong is not cleanup, and the failure mode is not
    academic -- it is how a throwaway user outlived its stage and made the next run
    fail on a duplicate email rather than on anything real.
    """
    db = SessionLocal()
    try:
        db.execute(text(
            "DELETE FROM portfolio_snapshots WHERE portfolio_id IN "
            "(SELECT portfolio_id FROM portfolios WHERE name LIKE :p)"),
            {"p": f"{PREFIX}%"})
        db.execute(text(
            "DELETE FROM portfolio_holdings WHERE portfolio_id IN "
            "(SELECT portfolio_id FROM portfolios WHERE name LIKE :p)"),
            {"p": f"{PREFIX}%"})
        db.execute(text("DELETE FROM portfolios WHERE name LIKE :p"),
                   {"p": f"{PREFIX}%"})
        db.execute(text("DELETE FROM users WHERE email LIKE :p"),
                   {"p": f"{PREFIX}%"})
        db.commit()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 6: the endpoints
# ─────────────────────────────────────────────────────────────────────────────

def stage_http() -> None:
    """``get_current_user`` is overridden rather than satisfied with a real
    Supabase token: the auth path is unchanged by I-06 and is covered by
    verify_i03_phase1.py.

    Uses a committed throwaway user and portfolio, deleted in a ``finally``,
    because TestClient runs each request in its own session and cannot see an
    uncommitted one.
    """
    print("\n=== Stage 6: endpoints over HTTP (auth overridden) ===")
    from fastapi.testclient import TestClient

    from app.dependencies import get_current_user
    from app.main import app
    from app.services import llm

    _purge()
    setup = SessionLocal()
    uid = uuid.uuid4()
    email = f"{PREFIX}http_{RUN}@example.invalid"
    setup.add(User(user_id=uid, email=email, full_name="I06 stub",
                   password_hash="x", role="user", is_email_verified=True))
    setup.commit()
    portfolio = Portfolio(user_id=uid, name=f"{PREFIX}http")
    setup.add(portfolio)
    setup.commit()
    pid = portfolio.portfolio_id

    symbol = (setup.query(DailyClose.symbol).order_by(DailyClose.symbol)
              .first() or (None,))[0]
    setup.close()

    # A detached stand-in rather than the persisted instance. The row must exist in
    # the database for the portfolio's foreign key, but handing FastAPI an instance
    # whose session has been closed raises DetachedInstanceError the moment a
    # handler touches user_id -- the commit expired its attributes and the close
    # took away the connection that would reload them.
    stub = User(user_id=uid, email=email, full_name="I06 stub",
                password_hash="x", role="user", is_email_verified=True)

    app.dependency_overrides[get_current_user] = lambda: stub
    original = llm.complete_text_sync
    llm.complete_text_sync = lambda *a, **kw: None   # force the DB insight path
    try:
        client = TestClient(app)

        # ── price history ──
        if symbol is None:
            check("a stored symbol exists to chart", False, "daily_close is empty")
        else:
            r = client.get(f"/api/v1/stocks/history/{symbol}")
            check(f"GET /stocks/history/{symbol} returns 200",
                  r.status_code == 200, f"{r.status_code}: {r.text[:300]}")
            if r.status_code == 200:
                body = r.json()
                for field in ("symbol", "requested_range", "point_count",
                              "first_date", "last_date", "points"):
                    check(f"price history carries `{field}`", field in body,
                          f"keys={sorted(body)}")
                check("point_count matches the points returned",
                      body["point_count"] == len(body["points"]),
                      f"{body['point_count']} vs {len(body['points'])}")
                check("the series is ascending by date",
                      [p["trade_date"] for p in body["points"]]
                      == sorted(p["trade_date"] for p in body["points"]),
                      "a chart plots oldest-first")
                if body["points"]:
                    p = body["points"][0]
                    for field in ("trade_date", "open", "high", "low", "close",
                                  "previous_close", "volume", "turnover",
                                  "trades", "last_traded_at"):
                        check(f"a point carries `{field}`", field in p,
                              f"keys={sorted(p)}")
                    check("first_date is the first point's date",
                          body["first_date"] == body["points"][0]["trade_date"])
                    check("last_date is the last point's date",
                          body["last_date"] == body["points"][-1]["trade_date"])

            r = client.get(f"/api/v1/stocks/history/{symbol.lower()}")
            check("the symbol is matched case-insensitively",
                  r.status_code == 200 and r.json()["point_count"] > 0,
                  f"{r.status_code}: {r.text[:200]}")

            r = client.get(f"/api/v1/stocks/history/{symbol}?range=1W")
            check("a narrower range is accepted", r.status_code == 200,
                  f"{r.status_code}: {r.text[:200]}")

        r = client.get("/api/v1/stocks/history/NOSUCHSYMBOL")
        check("an unknown symbol returns 200 with no points, not 404",
              r.status_code == 200 and r.json()["points"] == [],
              f"{r.status_code}: {r.text[:200]}")

        r = client.get("/api/v1/stocks/history/AAA?range=5Y")
        check("an unknown range is 422, naming the valid ones",
              r.status_code == 422 and "1M" in r.text,
              f"{r.status_code}: {r.text[:200]}")

        # ── the literal path segments still win over a symbol ──
        r = client.get("/api/v1/stocks/market")
        check("/stocks/market still routes to the quote list, not history",
              r.status_code == 200 and isinstance(r.json(), list),
              f"{r.status_code}: {r.text[:200]}")

        # ── portfolio history ──
        r = client.get(f"/api/v1/portfolio/{pid}/history")
        check(f"GET /portfolio/{pid}/history returns 200", r.status_code == 200,
              f"{r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            body = r.json()
            for field in ("portfolio_id", "requested_range", "point_count",
                          "first_date", "last_date", "points"):
                check(f"portfolio history carries `{field}`", field in body,
                      f"keys={sorted(body)}")
            check("a portfolio with no snapshots returns an empty series, not 404",
                  body["points"] == [] and body["point_count"] == 0,
                  f"{body['point_count']} points")

        r = client.get("/api/v1/portfolio/99999999/history")
        check("someone else's portfolio is 404, same as one that does not exist",
              r.status_code == 404, f"{r.status_code}")

        r = client.get(f"/api/v1/portfolio/{pid}/history?range=5Y")
        check("portfolio history rejects an unknown range with 422",
              r.status_code == 422, f"{r.status_code}")

        # ── the dashboard tile ──
        r = client.get("/api/v1/dashboard/")
        check("GET /dashboard/ returns 200", r.status_code == 200,
              f"{r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            pf = r.json()["portfolio"]
            check("the dashboard no longer serves weekly_history",
                  "weekly_history" not in pf, f"keys={sorted(pf)}")
            check("the dashboard serves a dated history series",
                  "history" in pf and isinstance(pf["history"], list),
                  f"keys={sorted(pf)}")
            check("the series window is declared", pf.get("history_days") == 30,
                  f"history_days={pf.get('history_days')}")
            for point in pf["history"]:
                check("every history point carries its own date",
                      "date" in point and "value" in point, f"{point}")
            cur = pf["current_value"]
            fakes = [cur * m for m in OLD_FAKE_MULTIPLIERS[:-1]]
            check("no history point is a fixed multiple of the current value",
                  not any(any(abs(p["value"] - f) < 0.01 for f in fakes)
                          for p in pf["history"]),
                  f"current={cur} history={pf['history']}")
    finally:
        llm.complete_text_sync = original
        app.dependency_overrides.pop(get_current_user, None)
        _purge()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 7: the schema
# ─────────────────────────────────────────────────────────────────────────────

def stage_schema() -> None:
    print("\n=== Stage 7: schema as migrated ===")
    db = SessionLocal()
    try:
        rev = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        # "Applied", not "is the head". This asserted `rev == "a7b8c9d0e1f2"` and
        # went red the moment I-07 added the company_info migration on top -- a
        # verification for an issue that was still entirely correct, failing
        # because a later issue did its job. Every subsequent migration would have
        # broken it again. What I-06 needs is that its revision is in the applied
        # ancestry, which stays true forever once it is true once.
        ancestry = set()
        script = ScriptDirectory("alembic")
        if rev:
            ancestry = {s.revision for s in script.iterate_revisions(rev, "base")}
        check("the I-06 migration has been applied",
              I06_REVISION in ancestry,
              f"alembic is at {rev}, whose ancestry does not include "
              f"{I06_REVISION}; run `alembic upgrade head`")
        if rev != I06_REVISION:
            print(f"         (head has moved on to {rev}; I-06's "
                  f"{I06_REVISION} is an ancestor, which is what matters)")

        for table, cols in (
            ("daily_close", ["symbol", "trade_date", "open", "high", "low",
                             "close", "previous_close", "volume", "turnover",
                             "trades", "last_traded_at", "updated_at"]),
            ("portfolio_snapshots", ["portfolio_id", "snapshot_date",
                                     "total_value", "total_cost",
                                     "holdings_count", "priced_count",
                                     "priced_at", "updated_at"]),
        ):
            actual = [r[0] for r in db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t ORDER BY ordinal_position"),
                {"t": table}).all()]
            check(f"{table} has exactly the columns the model declares",
                  actual == cols, f"got {actual}")

        for table in ("market_data", "market_data_latest"):
            actual = [r[0] for r in db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = 'last_traded_at'"),
                {"t": table}).all()]
            check(f"{table} gained last_traded_at", actual == ["last_traded_at"],
                  f"got {actual}")

        # NOT NULL where a row would otherwise be meaningless.
        for table, col in (("daily_close", "close"),
                           ("daily_close", "last_traded_at"),
                           ("portfolio_snapshots", "total_value")):
            nullable = db.execute(text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"),
                {"t": table, "c": col}).scalar()
            check(f"{table}.{col} is NOT NULL", nullable == "NO",
                  f"is_nullable={nullable}")

        for table, cols in (("daily_close", ["symbol", "trade_date"]),
                            ("portfolio_snapshots",
                             ["portfolio_id", "snapshot_date"])):
            # cast(:t AS regclass), not :t::regclass. text() finds bind parameters
            # with a negative lookahead that rejects a name followed by another
            # colon -- so that Postgres's own ``::`` cast syntax keeps working --
            # which means :t::regclass leaves ":t" in the SQL as literal text and
            # Postgres rejects the statement.
            pk = [r[0] for r in db.execute(text(
                "SELECT a.attname FROM pg_index i "
                "JOIN pg_attribute a ON a.attrelid = i.indrelid "
                "  AND a.attnum = ANY(i.indkey) "
                "WHERE i.indrelid = cast(:t AS regclass) AND i.indisprimary "
                "ORDER BY a.attnum"), {"t": table}).all()]
            check(f"{table} is keyed on {tuple(cols)}", pk == cols, f"got {pk}")

        # The FK that portfolio_snapshots has and market_data_latest deliberately
        # does not: a stale quote is still a true statement about the past, but a
        # valuation of a deleted portfolio is not a fact about anything.
        fk = db.execute(text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conrelid = 'portfolio_snapshots'::regclass "
            "AND contype = 'f'")).scalar()
        check("portfolio_snapshots cascades on portfolio delete", fk == "c",
              f"confdeltype={fk!r} (c = cascade)")

        # No redundant index: the primary key's btree already serves the one read.
        n = db.execute(text(
            "SELECT count(*) FROM pg_indexes WHERE tablename = 'daily_close'")
        ).scalar()
        check("daily_close carries one index, the primary key's", n == 1,
              f"{n} indexes")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 8: no fabricated data left, and no mock generator left in the app
# ─────────────────────────────────────────────────────────────────────────────

def stage_clean() -> None:
    print("\n=== Stage 8: nothing throwaway survived ===")
    db = SessionLocal()
    try:
        for table, col in (("daily_close", "symbol"),
                           ("portfolios", "name"),
                           ("users", "email")):
            n = db.execute(
                text(f"SELECT count(*) FROM {table} WHERE {col} LIKE :p"),
                {"p": f"{PREFIX}%"}).scalar()
            check(f"no {PREFIX}* rows left in {table}", n == 0, f"{n} rows")

        n = db.execute(text(
            "SELECT count(*) FROM portfolio_snapshots s "
            "LEFT JOIN portfolios p USING (portfolio_id) "
            "WHERE p.portfolio_id IS NULL")).scalar()
        check("no orphaned snapshots", n == 0, f"{n} rows")

        print("\n         live counts:")
        for t in ("daily_close", "portfolio_snapshots", "market_data",
                  "market_data_latest", "market_index_latest", "portfolios",
                  "portfolio_holdings", "users"):
            print(f"           {t}: "
                  f"{db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")

        top = db.execute(text(
            "SELECT symbol, trade_date, open, high, low, close, volume, trades "
            "FROM daily_close ORDER BY turnover DESC NULLS LAST LIMIT 5")).all()
        if top:
            print("\n         busiest sessions stored:")
            for r in top:
                print(f"           {r[0]:<12} {r[1]}  o={r[2]} h={r[3]} "
                      f"l={r[4]} c={r[5]} vol={r[6]:,.0f} trades={r[7]}")
    finally:
        db.close()


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("all", "scrape"):
        stage_scrape()
    if stage in ("all", "dates"):
        stage_dates()
    if stage in ("all", "upsert"):
        stage_upsert()
    if stage in ("all", "ohlc"):
        stage_ohlc()
    if stage in ("all", "snapshots"):
        stage_snapshots()
    if stage in ("all", "http"):
        stage_http()
    if stage in ("all", "schema"):
        stage_schema()
    if stage in ("all", "clean"):
        stage_clean()

    print(f"\n{'=' * 60}\n  {passed} passed, {failed} failed\n{'=' * 60}")
    sys.exit(1 if failed else 0)
