# scripts/verify_i04.py
"""Live verification for I-04 (market data integrity).

Run with:  python -m scripts.verify_i04

The unit tests in tests/test_market_data.py are offline by policy (see
pytest.ini), which leaves two things they cannot prove:

*   the ``ON CONFLICT (symbol) DO UPDATE ... WHERE`` upsert, because
    ``postgresql.insert()`` does not compile on SQLite; and
*   that the rewritten read paths return correct results against the real
    schema and real data.

This script proves both against the live database.

**It writes nothing that survives.** Every stage runs inside a transaction that
is rolled back in a ``finally``, and the throwaway rows use a ``ZZ_I04_`` symbol
prefix and a throwaway user so that even an abrupt failure leaves nothing
recognisable behind. The final stage re-checks the real row counts to confirm
that.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.database import SessionLocal
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.stock import MarketData, MarketDataLatest
from app.models.user import User
from app.services.scraper import _refresh_latest

PREFIX = "ZZ_I04_"
NOW = datetime.now(timezone.utc)

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


def _row(symbol: str, price: float, recorded_at: datetime, market_id: int,
         volume: float | None = None) -> MarketData:
    r = MarketData(symbol=symbol, price=price, recorded_at=recorded_at,
                   volume=volume, change=None, change_pct=None, market_cap=None)
    r.market_id = market_id
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: the ON CONFLICT upsert
# ─────────────────────────────────────────────────────────────────────────────

def stage_upsert() -> None:
    print("\n=== Stage 1: ON CONFLICT upsert semantics (rolled back) ===")
    db = SessionLocal()
    try:
        sym_a, sym_b = f"{PREFIX}A", f"{PREFIX}B"

        # -- insert of a symbol not yet present
        _refresh_latest(db, [
            _row(sym_a, 10.0, NOW, market_id=-101),
            _row(sym_b, 20.0, NOW, market_id=-102),
        ])
        db.flush()
        rows = {r.symbol: r for r in db.query(MarketDataLatest).filter(
            MarketDataLatest.symbol.like(f"{PREFIX}%")).all()}
        check("new symbols are inserted", len(rows) == 2, f"got {sorted(rows)}")
        check("inserted price is correct", rows[sym_a].price == 10.0)
        check("market_id is carried over", rows[sym_a].market_id == -101)

        # -- a newer snapshot moves the quote forward
        later = NOW + timedelta(minutes=15)
        _refresh_latest(db, [_row(sym_a, 11.5, later, market_id=-103)])
        db.flush()
        db.expire_all()
        a = db.query(MarketDataLatest).filter_by(symbol=sym_a).one()
        check("a newer snapshot updates the price", a.price == 11.5,
              f"price={a.price}")
        check("a newer snapshot updates recorded_at", a.recorded_at == later)
        check("a newer snapshot updates market_id", a.market_id == -103)

        # -- an OLDER snapshot must not move the quote backwards
        earlier = NOW - timedelta(hours=6)
        _refresh_latest(db, [_row(sym_a, 99.0, earlier, market_id=-104)])
        db.flush()
        db.expire_all()
        a = db.query(MarketDataLatest).filter_by(symbol=sym_a).one()
        check("an older snapshot does NOT overwrite a newer quote",
              a.price == 11.5, f"price moved backwards to {a.price}")
        check("an older snapshot leaves recorded_at alone", a.recorded_at == later)
        check("an older snapshot leaves market_id alone", a.market_id == -103)

        # -- a re-run of the same snapshot is idempotent, not an error
        _refresh_latest(db, [_row(sym_a, 11.5, later, market_id=-103)])
        db.flush()
        db.expire_all()
        a = db.query(MarketDataLatest).filter_by(symbol=sym_a).one()
        check("replaying the same snapshot is idempotent", a.price == 11.5)

        # -- the same symbol twice in ONE batch: Postgres refuses to touch a
        #    target row twice per statement, so this raises unless deduplicated
        much_later = NOW + timedelta(hours=1)
        try:
            _refresh_latest(db, [
                _row(sym_b, 21.0, much_later, market_id=-105),
                _row(sym_b, 22.0, much_later, market_id=-106),
            ])
            db.flush()
            db.expire_all()
            b = db.query(MarketDataLatest).filter_by(symbol=sym_b).one()
            check("a symbol repeated in one batch does not raise", True)
            check("the last occurrence wins", b.price == 22.0, f"price={b.price}")
        except Exception as exc:  # pragma: no cover - this is the failure mode
            check("a symbol repeated in one batch does not raise", False,
                  f"{type(exc).__name__}: {exc}")
            db.rollback()

        # -- the primary key makes duplicates structurally impossible
        dupes = db.execute(text("""
            SELECT count(*) FROM (
              SELECT symbol FROM market_data_latest GROUP BY symbol HAVING count(*) > 1
            ) d
        """)).scalar()
        check("market_data_latest cannot hold a duplicate symbol", dupes == 0,
              f"{dupes} duplicated symbols")
    finally:
        db.rollback()
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: read paths against real data
# ─────────────────────────────────────────────────────────────────────────────

def stage_reads() -> None:
    print("\n=== Stage 2: read paths against live data (read-only) ===")
    db = SessionLocal()
    try:
        hist_symbols = db.execute(
            text("SELECT count(DISTINCT symbol) FROM market_data")).scalar()
        latest_rows = db.execute(
            text("SELECT count(*) FROM market_data_latest")).scalar()
        check("one latest row per historical symbol",
              hist_symbols == latest_rows,
              f"history has {hist_symbols} symbols, latest has {latest_rows} rows")

        stale = db.execute(text("""
            SELECT count(*) FROM market_data_latest l
            JOIN (SELECT symbol, max(recorded_at) mx FROM market_data GROUP BY symbol) m
              ON m.symbol = l.symbol
            WHERE l.recorded_at <> m.mx
        """)).scalar()
        check("every latest row is the newest for its symbol", stale == 0,
              f"{stale} stale rows")

        # -- /stocks/market, called directly so the response_model is exercised
        from app.routers.stocks import get_market_data
        from app.schemas.stock import MarketData as MarketDataSchema

        result = get_market_data(symbol=None, limit=50, db=db, _=None)
        check("/stocks/market returns rows", len(result) > 0, f"got {len(result)}")
        check("/stocks/market returns at most `limit` rows", len(result) <= 50)
        syms = [r.symbol for r in result]
        check("/stocks/market returns no duplicate symbol",
              len(syms) == len(set(syms)),
              f"{len(syms) - len(set(syms))} duplicates")
        check("/stocks/market is ordered deterministically", syms == sorted(syms))
        try:
            [MarketDataSchema.model_validate(r, from_attributes=True) for r in result]
            check("/stocks/market rows satisfy the unchanged response schema", True)
        except Exception as exc:
            check("/stocks/market rows satisfy the unchanged response schema",
                  False, f"{type(exc).__name__}: {exc}")

        one = get_market_data(symbol=syms[0].lower(), limit=50, db=db, _=None)
        check("/stocks/market?symbol= filters and is case-insensitive",
              len(one) == 1 and one[0].symbol == syms[0],
              f"got {[r.symbol for r in one]}")

        missing = get_market_data(symbol="NOSUCHSYMBOL", limit=50, db=db, _=None)
        check("/stocks/market on an unknown symbol returns empty, not an error",
              missing == [])

        # -- the watchlist preview: the bug was duplicate symbols
        top = (db.query(MarketDataLatest)
               .order_by(MarketDataLatest.volume.desc().nullslast())
               .limit(6).all())
        tsyms = [r.symbol for r in top]
        check("watchlist preview returns 6 rows", len(top) == 6, f"got {len(top)}")
        check("watchlist preview returns 6 DISTINCT symbols",
              len(set(tsyms)) == 6, f"got {tsyms}")

        # -- and the old query, on the same data, for contrast.
        #
        # The pre-fix watchlist ordered *all* history by volume and took six rows,
        # so a symbol with high volume in more than one snapshot occupied more
        # than one slot. Run it as-is against real history. If only one snapshot
        # exists the old query happens to look correct, so fall back to
        # simulating the second one -- the check is meaningful either way, but
        # real history is the stronger evidence.
        snapshots = db.execute(text(
            "SELECT count(DISTINCT recorded_at) FROM market_data")).scalar()
        old_syms = [r[0] for r in db.execute(text(
            "SELECT symbol FROM market_data ORDER BY volume DESC NULLS LAST LIMIT 6"
        )).fetchall()]

        if len(set(old_syms)) < 6:
            print(f"         old query on real history ({snapshots} snapshots): "
                  f"{len(set(old_syms))} distinct of 6 -> {old_syms}")
            check("the old query DOES break on real history (bug confirmed)",
                  True)
        else:
            simulated = [r[0] for r in db.execute(text("""
                SELECT symbol FROM (
                  SELECT symbol, volume FROM market_data
                  UNION ALL
                  SELECT symbol, volume FROM market_data
                ) s ORDER BY volume DESC NULLS LAST LIMIT 6
            """)).fetchall()]
            print(f"         old query, real history ({snapshots} snapshots): "
                  f"{len(set(old_syms))} distinct of 6")
            print(f"         old query, simulated 2nd snapshot: "
                  f"{len(set(simulated))} distinct of 6")
            check("the old query DID break with two snapshots (bug confirmed)",
                  len(set(simulated)) < 6,
                  "expected duplicates from the pre-fix query")

        check("the fixed watchlist is unaffected by how many snapshots exist",
              len(set(tsyms)) == 6, f"got {tsyms}")

        # -- the composite index is actually chosen for a per-symbol time series
        plan = "\n".join(r[0] for r in db.execute(text(
            "EXPLAIN SELECT * FROM market_data WHERE symbol = :s "
            "ORDER BY recorded_at DESC LIMIT 1"), {"s": syms[0]}).fetchall())
        check("per-symbol history lookup uses ix_market_data_symbol_recorded_at",
              "ix_market_data_symbol_recorded_at" in plan,
              plan.replace("\n", " | "))

        # -- the dropped indexes really are gone
        idx = {r[0] for r in db.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'market_data'"))}
        check("redundant ix_market_data_market_id is gone",
              "ix_market_data_market_id" not in idx, f"indexes={sorted(idx)}")
        check("redundant ix_market_data_symbol is gone",
              "ix_market_data_symbol" not in idx, f"indexes={sorted(idx)}")
        check("primary key index is still present", "market_data_pkey" in idx)
    finally:
        db.rollback()
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: the dashboard, with a throwaway portfolio (rolled back)
# ─────────────────────────────────────────────────────────────────────────────

def stage_dashboard() -> None:
    print("\n=== Stage 3: dashboard batched price lookup (rolled back) ===")
    db = SessionLocal()
    try:
        # Two real symbols so prices resolve, one fictitious so the fallback path
        # is exercised.
        real = db.query(MarketDataLatest).order_by(
            MarketDataLatest.symbol).limit(2).all()
        if len(real) < 2:
            check("enough market data to test the dashboard", False,
                  "need at least 2 symbols in market_data_latest")
            return

        user = User(user_id=uuid.uuid4(), email=f"{PREFIX}dash@example.invalid",
                    full_name="I04 throwaway", password_hash="x", role="user",
                    is_email_verified=False)
        db.add(user)
        db.flush()

        port = Portfolio(user_id=user.user_id, name="I04 throwaway")
        db.add(port)
        db.flush()

        holdings = [
            PortfolioHolding(portfolio_id=port.portfolio_id, symbol=real[0].symbol,
                             quantity=10, avg_buy_price=1.0),
            PortfolioHolding(portfolio_id=port.portfolio_id, symbol=real[1].symbol,
                             quantity=5, avg_buy_price=2.0),
            PortfolioHolding(portfolio_id=port.portfolio_id,
                             symbol=f"{PREFIX}GHOST", quantity=7,
                             avg_buy_price=3.0),
        ]
        db.add_all(holdings)
        db.flush()

        expected = (10 * real[0].price) + (5 * real[1].price) + (7 * 3.0)

        # Force the DB-backed insight fallback rather than calling out to an LLM.
        from app.services import llm
        original = llm.complete_text_sync
        llm.complete_text_sync = lambda *a, **kw: None
        try:
            from app.routers.dashboard import get_dashboard_data
            data = get_dashboard_data(db=db, current_user=user)
        finally:
            llm.complete_text_sync = original

        got = data["portfolio"]["current_value"]
        check("portfolio value uses the latest quote per holding",
              abs(got - expected) < 1e-6, f"expected {expected}, got {got}")
        check("an unquoted holding falls back to its cost basis, not zero",
              got > (10 * real[0].price) + (5 * real[1].price),
              f"got {got}")

        wl = data["watchlist_preview"]
        check("dashboard watchlist has no duplicate symbol",
              len({w["symbol"] for w in wl}) == len(wl),
              f"{[w['symbol'] for w in wl]}")
        check("dashboard returns insights", len(data["insights"]) > 0)
    finally:
        db.rollback()
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: over real HTTP, through FastAPI's response_model
# ─────────────────────────────────────────────────────────────────────────────

def stage_http() -> None:
    """Exercise the endpoints through the full request stack.

    Stage 2 calls the endpoint functions directly, which proves the SQL. This
    proves the serialisation: ``/stocks/market`` declares
    ``response_model=List[MarketData]``, a schema written for the history table,
    and it is now fed ``MarketDataLatest`` rows. A missing or mistyped column
    would be a 500 here even though the query itself is fine.

    ``get_current_user`` is overridden rather than satisfied with a real
    Supabase token: the auth path is unchanged by I-04 and is covered by
    verify_i03_phase1.py, and minting a token would mean creating and deleting a
    real account for no added coverage.
    """
    print("\n=== Stage 4: endpoints over HTTP (auth overridden) ===")
    from fastapi.testclient import TestClient

    from app.dependencies import get_current_user
    from app.main import app
    from app.services import llm

    db = SessionLocal()
    stub = User(user_id=uuid.uuid4(), email=f"{PREFIX}http@example.invalid",
                full_name="I04 stub", password_hash="x", role="user",
                is_email_verified=True)

    app.dependency_overrides[get_current_user] = lambda: stub
    original = llm.complete_text_sync
    llm.complete_text_sync = lambda *a, **kw: None
    try:
        client = TestClient(app)

        r = client.get("/api/v1/stocks/market?limit=10")
        check("GET /stocks/market returns 200", r.status_code == 200,
              f"{r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            body = r.json()
            check("GET /stocks/market honours limit", len(body) == 10,
                  f"got {len(body)}")
            check("GET /stocks/market returns distinct symbols",
                  len({q['symbol'] for q in body}) == len(body))
            first = body[0]
            for field in ("symbol", "price", "market_id", "recorded_at"):
                check(f"response carries `{field}`", field in first,
                      f"keys={sorted(first)}")
            check("market_id is an int as the schema declares",
                  isinstance(first.get("market_id"), int),
                  f"got {type(first.get('market_id')).__name__}")

        r = client.get("/api/v1/dashboard/")
        check("GET /dashboard/ returns 200", r.status_code == 200,
              f"{r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            body = r.json()
            wl = body.get("watchlist_preview", [])
            check("dashboard watchlist has 6 entries", len(wl) == 6,
                  f"got {len(wl)}")
            check("dashboard watchlist symbols are distinct",
                  len({w['symbol'] for w in wl}) == len(wl),
                  f"{[w['symbol'] for w in wl]}")
            check("dashboard portfolio value is 0 for a user with no holdings",
                  body["portfolio"]["current_value"] == 0,
                  f"got {body['portfolio']['current_value']}")
    finally:
        llm.complete_text_sync = original
        app.dependency_overrides.pop(get_current_user, None)
        db.rollback()
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: nothing was left behind
# ─────────────────────────────────────────────────────────────────────────────

def stage_clean() -> None:
    print("\n=== Stage 5: no throwaway data survived ===")
    db = SessionLocal()
    try:
        for table, col in (("market_data", "symbol"),
                           ("market_data_latest", "symbol"),
                           ("portfolio_holdings", "symbol"),
                           ("users", "email")):
            n = db.execute(
                text(f"SELECT count(*) FROM {table} WHERE {col} LIKE :p"),
                {"p": f"{PREFIX}%"}).scalar()
            check(f"no {PREFIX}* rows left in {table}", n == 0, f"{n} rows")

        n = db.execute(text(
            "SELECT count(*) FROM portfolios WHERE name = 'I04 throwaway'")).scalar()
        check("no throwaway portfolios left", n == 0, f"{n} rows")

        print("\n         live counts:")
        for t in ("market_data", "market_data_latest", "users",
                  "portfolios", "portfolio_holdings", "news_sentiment"):
            print(f"           {t}: {db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")
    finally:
        db.close()


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("all", "upsert"):
        stage_upsert()
    if stage in ("all", "reads"):
        stage_reads()
    if stage in ("all", "dashboard"):
        stage_dashboard()
    if stage in ("all", "http"):
        stage_http()
    if stage in ("all", "clean"):
        stage_clean()

    print(f"\n{'=' * 60}\n  {passed} passed, {failed} failed\n{'=' * 60}")
    sys.exit(1 if failed else 0)
