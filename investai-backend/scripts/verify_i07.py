# scripts/verify_i07.py
"""Live verification for I-07 (real company fundamentals, real sector filters).

Run with:  python -m scripts.verify_i07

``StockDetailScreen.js`` displayed four company fundamentals, all four of which
were modulus arithmetic on the live price::

    peRatio   = 8 + (price % 15)
    high52    = price * (1 + (price % 30) / 100)
    low52     = price * (1 - (price % 25) / 100)
    marketCap = 10 + (price % 50) * 2.5      # rendered with a "B" suffix

and the home and browse screens filtered by sector using hardcoded ticker-prefix
arrays -- ``['JKH', 'HAYL', 'RICH']`` was "Capital Goods" -- because nothing stored
a sector.

tests/test_company_info.py and tests/test_sectors.py are offline by policy (see
pytest.ini): they parse fixed payloads and compile the Postgres SQL without
executing it. What still needs a live database and a live cse.lk:

*   that the two undocumented endpoints still answer for the whole market, and
    that the fill rates have not silently collapsed -- the fabricated tiles were
    never null, so a client that starts receiving nulls everywhere is a regression
    an offline test cannot see;
*   that Postgres honours ``ON CONFLICT (symbol)`` against the real primary key,
    and that ``WHERE refreshed_at <= excluded.refreshed_at`` refuses to walk a
    profile backwards when a retried task presents an older sweep;
*   that the 20 sector chips the API produces are the exchange's own index names,
    joinable to ``market_index_latest`` with no mapping table -- the claim the
    whole of ``app/services/sectors.py`` exists to make true;
*   that exactly six symbols have no industry group and they are the six
    documented ones, so a new unresolved sector string shows up here rather than
    as a company quietly missing from every chip;
*   that ``week52_high`` is absent from the API response, since the stored column
    is not split-adjusted and 26 of 287 symbols publish a 12-month high from
    before a forward split;
*   that all three endpoints serve what they promise.

Stage 1 **commits**, like verify_i05's and verify_i06's do and for the same
reason: storing the fundamentals is the feature, and the upsert is idempotent by
construction. Stages that fabricate data use a ``ZZ_I07_`` symbol prefix inside a
transaction rolled back in a ``finally``, and the last stage re-checks that
nothing survived.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.database import SessionLocal
from app.models.stock import CompanyInfo, MarketDataLatest
from app.models.user import User
from app.services.company_info import (fetch_company_info, known_symbols,
                                       parse_company_payload,
                                       refresh_company_info)
from app.services.scraper import _upsert_latest
from app.services.sectors import CANONICAL_SECTORS, canonical_sector

PREFIX = "ZZ_I07_"
NOW = datetime.now(timezone.utc)

# The six symbols that must have no industry group, and why. Asserted by symbol
# rather than by count: a count alone would stay at six while one company fell out
# of a chip and another fell in.
EXPECTED_UNGROUPED = {
    # No sector in the feed at all -- closed-end funds and unit trusts have no
    # industry sector, and cse.lk correctly returns null rather than a substitute.
    "CALC.U0000", "CALI.U0000", "CALU.U0000",
    # A sector string that resolves to no single industry group. "Industrials" is a
    # GICS *sector* spanning three groups; "Trading" belongs to a seafood processor,
    # so the plausible reading of the string and of the business disagree.
    "CWL.N0000", "TESS.N0000", "TESS.X0000",
}

# The fabricated tiles' formulae, so a value that still matches one is caught.
# Nothing should serve these.
OLD_FAKE_PE = lambda price: 8 + (price % 15)                          # noqa: E731
OLD_FAKE_MARKET_CAP = lambda price: 10 + (price % 50) * 2.5           # noqa: E731

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


def _purge() -> None:
    """Remove everything any stage created under the ``ZZ_I07_`` prefix.

    Opens its own session rather than borrowing the caller's, for the reason
    verify_i06's does: stages call this from a ``finally``, so the moment it matters
    most is the moment the caller's session is the thing that broke. A failed flush
    leaves a session that refuses everything until it is rolled back.
    """
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM company_info WHERE symbol LIKE :p"),
                   {"p": f"{PREFIX}%"})
        db.execute(text("DELETE FROM market_data_latest WHERE symbol LIKE :p"),
                   {"p": f"{PREFIX}%"})
        db.execute(text("DELETE FROM users WHERE email LIKE :p"),
                   {"p": f"{PREFIX}%"})
        db.commit()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: the real sweep, committed
# ─────────────────────────────────────────────────────────────────────────────

def stage_sweep() -> None:
    """Fetch the whole market from cse.lk and store it.

    Commits, because storing the fundamentals is the feature. Safe to re-run: the
    upsert is keyed on symbol and guarded on refreshed_at, so a second run updates
    291 rows rather than adding any.
    """
    print("\n=== Stage 1: the live sweep, committed ===")
    db = SessionLocal()
    try:
        targets = known_symbols(db)
        check("market_data_latest has symbols to sweep", len(targets) > 100,
              f"{len(targets)} symbols -- run verify_i04 first if this is low")
        if not targets:
            return

        before = db.query(CompanyInfo).count()
        started = datetime.now(timezone.utc)
        written = asyncio.run(refresh_company_info(db))
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()

        check("the sweep wrote a row for every symbol", written == len(targets),
              f"{written} of {len(targets)}")
        check("the sweep finished in under 60s", elapsed < 60,
              f"{elapsed:.1f}s -- the measured figure is ~8s at concurrency 6")
        print(f"         {written} rows in {elapsed:.1f}s "
              f"({before} rows before)")

        # One refreshed_at for the whole sweep, so "this refresh" is one
        # identifiable thing a query can filter on.
        stamps = db.execute(text(
            "SELECT count(DISTINCT refreshed_at) FROM company_info")).scalar()
        check("the whole sweep shares one refreshed_at", stamps == 1,
              f"{stamps} distinct timestamps")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: fill rates -- the numbers a client will actually render
# ─────────────────────────────────────────────────────────────────────────────

def stage_fill() -> None:
    """A fabricated tile was never null. A real one is, sometimes, and the whole
    point of I-07 is that the nulls are honest -- so the fill rates are the thing
    that says the feed is still answering rather than quietly returning empties.
    """
    print("\n=== Stage 2: fill rates ===")
    db = SessionLocal()
    try:
        total = db.query(CompanyInfo).count()
        check("company_info is populated", total > 100, f"{total} rows")
        if not total:
            return

        # Floors, not exact counts: cse.lk adds and delists companies, so an exact
        # figure would fail for a reason that is not a defect. Each floor is well
        # below the measured fill and well above "the endpoint stopped answering".
        for column, floor, note in (
            ("name", 1.0, "NOT NULL -- a row that cannot be labelled is useless"),
            ("sector", 0.95, "null for the three unit trusts"),
            ("sector_group", 0.95, "null for those three plus three unresolved"),
            ("market_cap", 0.95, "null for three unit trusts and one fund"),
            ("week52_low", 0.95, "the one price range that is served"),
            ("shares_issued", 0.95, ""),
            ("isin", 0.95, ""),
            ("beta_asi", 0.95, "null for the three unit trusts"),
            ("website", 0.60, "215 of 291 measured -- many companies file none"),
            ("business_summary", 0.60, "231 of 291 measured"),
        ):
            n = db.execute(text(
                f"SELECT count({column}) FROM company_info")).scalar()
            ratio = n / total
            check(f"{column} filled for >= {floor:.0%} of rows",
                  ratio >= floor, f"{n}/{total} = {ratio:.1%}. {note}")

        # A website with no scheme does nothing in Linking.openURL on Android.
        n = db.execute(text(
            "SELECT count(*) FROM company_info WHERE website IS NOT NULL "
            "AND website NOT LIKE 'http://%' AND website NOT LIKE 'https://%'"
        )).scalar()
        check("every stored website has a scheme", n == 0, f"{n} without one")

        # Zero is the feed's way of saying "no figure", and _positive drops it.
        for column in ("market_cap", "week52_low", "week52_high", "par_value"):
            n = db.execute(text(
                f"SELECT count(*) FROM company_info WHERE {column} = 0")).scalar()
            check(f"no zero stored in {column}", n == 0,
                  f"{n} rows -- zero would render as a measurement")

        # Beta is not filtered by _positive, because zero and negative are real.
        n = db.execute(text(
            "SELECT count(*) FROM company_info WHERE beta_asi <= 0")).scalar()
        print(f"         beta_asi <= 0 for {n} symbols "
              f"(kept deliberately: a negative beta is a measurement)")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: the sector vocabulary
# ─────────────────────────────────────────────────────────────────────────────

def stage_sectors() -> None:
    """The claim ``app/services/sectors.py`` exists to make true.

    An earlier probe compared two symbols, found JKH -> "Capital Goods" matching the
    index name exactly, and concluded the two vocabularies were identical. Over 291
    symbols they are not: 39 distinct strings for 20 industry groups, three of them
    spellings of Food, Beverage & Tobacco. This stage is what would have caught
    that.
    """
    print("\n=== Stage 3: sector strings, groups, and index names ===")
    db = SessionLocal()
    try:
        raw_count = db.execute(text(
            "SELECT count(DISTINCT sector) FROM company_info "
            "WHERE sector IS NOT NULL")).scalar()
        group_count = db.execute(text(
            "SELECT count(DISTINCT sector_group) FROM company_info "
            "WHERE sector_group IS NOT NULL")).scalar()
        print(f"         {raw_count} distinct raw strings -> "
              f"{group_count} industry groups")
        check("the raw feed really does need normalising", raw_count > 20,
              f"{raw_count} distinct strings for at most 20 sectors. If this "
              f"drops to 20, cse.lk cleaned its data and the table can shrink")
        check("every group is one of the 20 canonical sectors",
              group_count <= 20, f"{group_count} groups")

        # The load-bearing join: a chip's label and its index reading must be the
        # same string, with no mapping table between two vocabularies.
        orphans = db.execute(text(
            "SELECT DISTINCT c.sector_group FROM company_info c "
            "LEFT JOIN market_index_latest i ON i.name = c.sector_group "
            "WHERE c.sector_group IS NOT NULL AND i.name IS NULL")).all()
        check("every sector_group matches a market_index_latest name",
              not orphans, f"unmatched: {[r[0] for r in orphans]}")

        for name in CANONICAL_SECTORS:
            hit = db.execute(text(
                "SELECT count(*) FROM market_index_latest WHERE name = :n"),
                {"n": name}).scalar()
            check(f"index reading exists for '{name}'", hit == 1,
                  f"{hit} rows -- CANONICAL_SECTORS is spelled from the feed, so "
                  f"a miss means cse.lk renamed a sector")

        # Exactly the six documented symbols, by symbol rather than by count.
        ungrouped = {r[0] for r in db.execute(text(
            "SELECT c.symbol FROM company_info c "
            "JOIN market_data_latest m ON m.symbol = c.symbol "
            "WHERE c.sector_group IS NULL")).all()}
        check("exactly the six documented symbols have no industry group",
              ungrouped == EXPECTED_UNGROUPED,
              f"unexpected: {sorted(ungrouped - EXPECTED_UNGROUPED)}, "
              f"missing: {sorted(EXPECTED_UNGROUPED - ungrouped)}")

        # Anything unresolved that is not one of the two known strings is a sector
        # cse.lk started spelling a new way, and a company silently out of a chip.
        unresolved = db.execute(text(
            "SELECT DISTINCT sector FROM company_info "
            "WHERE sector IS NOT NULL AND sector_group IS NULL")).all()
        check("no unresolved sector string beyond the two documented",
              {r[0] for r in unresolved} <= {"Industrials", "Trading"},
              f"unresolved: {sorted(r[0] for r in unresolved)}")

        # The stored group must be what the current table computes. They diverge
        # when the table changes without a re-sweep, which is exactly when a chip
        # starts disagreeing with itself.
        drift = [(s, stored) for s, stored in db.execute(text(
            "SELECT DISTINCT sector, sector_group FROM company_info "
            "WHERE sector IS NOT NULL")).all()
            if canonical_sector(s) != stored]
        check("no stored group disagrees with the current mapping", not drift,
              f"{len(drift)} drifted: {drift[:4]} -- re-run the sweep")

        # The measured headline: the correctly-spelled chip found 2 of 46 before.
        n = db.execute(text(
            "SELECT count(*) FROM company_info c "
            "JOIN market_data_latest m ON m.symbol = c.symbol "
            "WHERE lower(trim(c.sector_group)) = 'food, beverage & tobacco'"
        )).scalar()
        raw_n = db.execute(text(
            "SELECT count(*) FROM company_info c "
            "JOIN market_data_latest m ON m.symbol = c.symbol "
            "WHERE c.sector = 'Food, Beverage & Tobacco'")).scalar()
        check("the Food, Beverage & Tobacco chip finds the whole sector",
              n > raw_n * 2,
              f"{n} via sector_group vs {raw_n} via the raw string")
        print(f"         Food, Beverage & Tobacco: {n} symbols grouped, "
              f"{raw_n} spelled that way in the feed")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: the upsert, against the real primary key
# ─────────────────────────────────────────────────────────────────────────────

def stage_upsert() -> None:
    """Rolled back in a ``finally``. Uses ``ZZ_I07_`` symbols so nothing here can
    touch a real company's row even if the rollback fails."""
    print("\n=== Stage 4: ON CONFLICT and the no-backwards guard ===")
    db = SessionLocal()
    symbol = f"{PREFIX}A"
    try:
        def row(name, refreshed, **over):
            payload = {
                "symbol": symbol, "name": name, "sector": "Capital Goods",
                "sector_group": "Capital Goods", "market_cap": 1000.0,
                "market_cap_pct": None, "shares_issued": 100,
                "par_value": None, "isin": None, "week52_high": 2.0,
                "week52_low": 1.0, "all_time_high": None, "all_time_low": None,
                "beta_asi": 1.0, "beta_sl20": None, "beta_period": None,
                "board": None, "established": None, "website": None,
                "business_summary": None, "refreshed_at": refreshed,
            }
            payload.update(over)
            return payload

        _upsert_latest(db, CompanyInfo, "symbol", [row("FIRST", NOW)],
                       guard="refreshed_at")
        db.flush()
        got = db.execute(text(
            "SELECT name FROM company_info WHERE symbol = :s"),
            {"s": symbol}).scalar()
        check("a new symbol inserts", got == "FIRST", f"got {got!r}")

        # Same key, later sweep: must update in place, not duplicate.
        _upsert_latest(db, CompanyInfo, "symbol",
                       [row("SECOND", NOW + timedelta(minutes=1))],
                       guard="refreshed_at")
        db.flush()
        rows = db.execute(text(
            "SELECT name FROM company_info WHERE symbol = :s"),
            {"s": symbol}).all()
        check("a later sweep updates in place, one row per symbol",
              len(rows) == 1 and rows[0][0] == "SECOND", f"{rows}")

        # Same key, earlier sweep: the guard must refuse it. This is the retried
        # task case -- a task that started first can finish last.
        _upsert_latest(db, CompanyInfo, "symbol",
                       [row("STALE", NOW - timedelta(hours=1))],
                       guard="refreshed_at")
        db.flush()
        got = db.execute(text(
            "SELECT name FROM company_info WHERE symbol = :s"),
            {"s": symbol}).scalar()
        check("an older sweep cannot overwrite a newer one", got == "SECOND",
              f"got {got!r} -- refreshed_at guard did not hold")

        # Two records for one symbol in one statement, against a row that does
        # **not exist yet**. `ON CONFLICT DO UPDATE` cannot affect the same target
        # row twice in one command, which is why `refresh_company_info` dedupes by
        # symbol before it upserts.
        #
        # The fresh symbol is the point. Running this against the row above passes
        # for the wrong reason: the guard's WHERE filters both updates out, nothing
        # is actually modified, and Postgres never notices the collision. That was
        # this check's first form and it reported a green tick for a statement
        # Postgres rejects outright once the row is writable -- so the necessity of
        # the dedup depends on the row being newer than what is stored, which is the
        # ordinary case on every sweep after the first.
        #
        # In a SAVEPOINT because a failed statement poisons its transaction: without
        # one, the rollback would also undo the three checks above.
        fresh = f"{PREFIX}B"
        savepoint = db.begin_nested()
        try:
            _upsert_latest(db, CompanyInfo, "symbol",
                           [row("DUP1", NOW, symbol=fresh),
                            row("DUP2", NOW, symbol=fresh)],
                           guard="refreshed_at")
            db.flush()
            savepoint.rollback()
            check("Postgres rejects two records for one row in one statement",
                  False, "it did not -- so something other than the service's "
                         "dedup is keeping a duplicated symbol list from failing "
                         "a sweep, and that assumption needs re-checking")
        except Exception as exc:                                    # noqa: BLE001
            savepoint.rollback()
            check("Postgres rejects two records for one row in one statement",
                  "cannot affect row a second time" in str(exc).lower(),
                  f"raised something else: {str(exc)[:160]}")

        # And that the service's dedup makes that same input writable.
        deduped = {r["symbol"]: r for r in [row("D1", NOW, symbol=fresh),
                                            row("D2", NOW, symbol=fresh)]}
        _upsert_latest(db, CompanyInfo, "symbol", list(deduped.values()),
                       guard="refreshed_at")
        db.flush()
        rows = db.execute(text(
            "SELECT name FROM company_info WHERE symbol = :s"),
            {"s": fresh}).all()
        check("dedup by symbol makes the duplicate input writable",
              len(rows) == 1 and rows[0][0] == "D2",
              f"got {rows} -- one row, and the last record for a key wins")
    finally:
        db.rollback()
        db.close()
        _purge()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: the feed itself, live
# ─────────────────────────────────────────────────────────────────────────────

def stage_feed() -> None:
    """Both endpoints are undocumented, so their behaviour is checked rather than
    assumed -- including the unknown-symbol case, which answers 404 on the summary
    and **204 No Content** on the profile. A 204 has no body, so calling .json() on
    it raises; the status guard is what keeps one bad symbol from failing a sweep.
    """
    print("\n=== Stage 5: cse.lk, live ===")

    rows = asyncio.run(fetch_company_info(["JKH.N0000", "HNB.N0000",
                                           "CALC.U0000", "ZZZZ.N0000"]))
    by_symbol = {r["symbol"]: r for r in rows}

    check("an unknown symbol is skipped, not crashed on",
          "ZZZZ.N0000" not in by_symbol, f"got {sorted(by_symbol)}")
    check("three known symbols came back", len(by_symbol) == 3,
          f"{sorted(by_symbol)}")

    jkh = by_symbol.get("JKH.N0000")
    if jkh is None:
        check("JKH parsed", False, "no row")
    else:
        check("JKH has a real name", "KEELLS" in (jkh["name"] or "").upper(),
              f"{jkh['name']!r}")
        check("JKH has a market cap in the hundreds of billions",
              (jkh["market_cap"] or 0) > 1e11, f"{jkh['market_cap']}")
        check("JKH's sector resolves to an index name",
              jkh["sector_group"] in CANONICAL_SECTORS,
              f"raw={jkh['sector']!r} group={jkh['sector_group']!r}")
        check("JKH's website has a scheme",
              (jkh["website"] or "").startswith("http"), f"{jkh['website']!r}")
        check("JKH's shares issued exceeds an int32",
              (jkh["shares_issued"] or 0) > 2 ** 31, f"{jkh['shares_issued']}")
        # The measured caveat behind not serving all_time_high.
        if jkh["all_time_high"] and jkh["week52_high"]:
            check("JKH's all-time high still dwarfs its 12-month high",
                  jkh["all_time_high"] > jkh["week52_high"] * 5,
                  f"all={jkh['all_time_high']} p12={jkh['week52_high']} -- if "
                  f"this stops holding, cse.lk started split-adjusting and the "
                  f"suppressed fields could be revisited")

    fund = by_symbol.get("CALC.U0000")
    if fund is None:
        check("the closed-end fund parsed", False, "no row")
    else:
        check("a fund has no sector rather than a substitute",
              fund["sector"] is None and fund["sector_group"] is None,
              f"{fund['sector']!r} / {fund['sector_group']!r}")
        check("a fund has no market cap rather than a zero",
              fund["market_cap"] is None, f"{fund['market_cap']}")
        check("a fund still has its identifiers",
              bool(fund["name"]) and bool(fund["isin"]),
              f"{fund['name']!r} {fund['isin']!r}")

    # An all-null payload must be dropped, not written as a row of nulls -- that
    # would overwrite a good earlier refresh with nothing.
    check("a payload with no name anywhere is dropped",
          parse_company_payload("X.N0000", None, None, NOW) is None)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 6: the endpoints
# ─────────────────────────────────────────────────────────────────────────────

def stage_http() -> None:
    """``get_current_user`` is overridden rather than satisfied with a real
    Supabase token: the auth path is unchanged by I-07 and is covered by
    verify_i03_phase1.py.
    """
    print("\n=== Stage 6: endpoints over HTTP (auth overridden) ===")
    from fastapi.testclient import TestClient

    from app.dependencies import get_current_user
    from app.main import app

    _purge()
    setup = SessionLocal()
    uid = uuid.uuid4()
    email = f"{PREFIX}http_{RUN}@example.invalid"
    setup.add(User(user_id=uid, email=email, full_name="I07 stub",
                   password_hash="x", role="user", is_email_verified=True))
    setup.commit()
    symbol = (setup.query(CompanyInfo.symbol)
              .order_by(CompanyInfo.symbol).first() or (None,))[0]
    setup.close()

    # A detached stand-in rather than the persisted instance: handing FastAPI an
    # instance whose session has been closed raises DetachedInstanceError the
    # moment a handler touches user_id.
    stub = User(user_id=uid, email=email, full_name="I07 stub",
                password_hash="x", role="user", is_email_verified=True)
    app.dependency_overrides[get_current_user] = lambda: stub
    try:
        client = TestClient(app)

        # ── GET /stocks/sectors ──
        r = client.get("/api/v1/stocks/sectors")
        check("GET /stocks/sectors returns 200", r.status_code == 200,
              f"{r.status_code}: {r.text[:300]}")
        chips = r.json() if r.status_code == 200 else []
        if chips:
            check("every chip carries a sector and a count",
                  all({"sector", "count"} <= set(c) for c in chips),
                  f"{chips[:2]}")
            stray = [c["sector"] for c in chips
                     if c["sector"] not in CANONICAL_SECTORS]
            check("every chip label is a canonical sector", not stray,
                  f"stray: {stray}")
            check("at most 20 chips, not 39 raw strings", len(chips) <= 20,
                  f"{len(chips)} chips")
            check("chips are ordered by count descending",
                  [c["count"] for c in chips]
                  == sorted((c["count"] for c in chips), reverse=True),
                  "a filter list is more useful biggest-first")
            check("no chip is empty", all(c["count"] > 0 for c in chips))
            print(f"         {len(chips)} chips, "
                  f"{sum(c['count'] for c in chips)} symbols covered")

        # ── GET /stocks/market, with and without a sector ──
        r = client.get("/api/v1/stocks/market?limit=400")
        check("GET /stocks/market returns 200", r.status_code == 200,
              f"{r.status_code}: {r.text[:300]}")
        quotes = r.json() if r.status_code == 200 else []
        if quotes:
            check("the default limit covers the whole market", len(quotes) > 200,
                  f"{len(quotes)} rows -- it was 50, against 291 symbols")
            named = [q for q in quotes if q.get("name")]
            check("market rows carry a company name", len(named) > 200,
                  f"{len(named)}/{len(quotes)} -- the browse screen reads "
                  f"`s.name` and the schema never had it")
            check("market rows carry a sector",
                  sum(1 for q in quotes if q.get("sector")) > 200,
                  f"{sum(1 for q in quotes if q.get('sector'))}/{len(quotes)}")
            sectors_seen = {q["sector"] for q in quotes if q.get("sector")}
            check("the sector on a row is a canonical group, not a raw string",
                  sectors_seen <= set(CANONICAL_SECTORS),
                  f"stray: {sorted(sectors_seen - set(CANONICAL_SECTORS))}")

        if chips:
            biggest = chips[0]
            r = client.get("/api/v1/stocks/market",
                           params={"sector": biggest["sector"], "limit": 400})
            check(f"GET /stocks/market?sector={biggest['sector']} returns 200",
                  r.status_code == 200, f"{r.status_code}: {r.text[:200]}")
            if r.status_code == 200:
                filtered = r.json()
                check("the filtered count matches the chip's count",
                      len(filtered) == biggest["count"],
                      f"{len(filtered)} rows vs chip count {biggest['count']}")
                check("every filtered row is in that sector",
                      all(q["sector"] == biggest["sector"] for q in filtered),
                      "server-side filtering, so a sector's stocks outside the "
                      "first page are not invisible")

            # Case-insensitive, because these strings arrive from a URL.
            r = client.get("/api/v1/stocks/market",
                           params={"sector": biggest["sector"].lower(),
                                   "limit": 400})
            check("the sector filter is case-insensitive",
                  r.status_code == 200 and len(r.json()) == biggest["count"],
                  f"{r.status_code}, {len(r.json()) if r.status_code == 200 else '-'} rows")

            r = client.get("/api/v1/stocks/market",
                           params={"sector": "No Such Sector"})
            check("an unknown sector returns an empty list, not everything",
                  r.status_code == 200 and r.json() == [],
                  f"{r.status_code}, {len(r.json()) if r.status_code == 200 else '-'} rows")

        # ── GET /stocks/company/{symbol} ──
        if symbol is None:
            check("a stored company exists to fetch", False,
                  "company_info is empty -- run stage 1")
        else:
            r = client.get(f"/api/v1/stocks/company/{symbol}")
            check(f"GET /stocks/company/{symbol} returns 200",
                  r.status_code == 200, f"{r.status_code}: {r.text[:300]}")
            if r.status_code == 200:
                body = r.json()
                for field in ("symbol", "name", "sector", "sector_group",
                              "market_cap", "shares_issued", "week52_low",
                              "beta_asi", "beta_sl20", "refreshed_at"):
                    check(f"company payload carries `{field}`", field in body,
                          f"keys={sorted(body)}")

                # The absences, each deliberate and each measured.
                check("no pe_ratio in the response", "pe_ratio" not in body,
                      "cse.lk publishes no EPS; 94 keys were walked")
                for field in ("week52_high", "all_time_high", "all_time_low"):
                    check(f"no {field} in the response", field not in body,
                          "stored but not split-adjusted: 26 of 287 symbols "
                          "publish a pre-split high, and no field cse.lk serves "
                          "distinguishes them")

            r = client.get("/api/v1/stocks/company/zzzz.n0000")
            check("an unknown symbol is a 404, not a body of nulls",
                  r.status_code == 404, f"{r.status_code}: {r.text[:200]}")

            r = client.get(f"/api/v1/stocks/company/{symbol.lower()}")
            check("a lower-case symbol resolves", r.status_code == 200,
                  f"{r.status_code}")

        # Auth is still required -- the override is on this app instance only, so
        # this checks the dependency is wired, using a second client without it.
        del app.dependency_overrides[get_current_user]
        r = TestClient(app).get("/api/v1/stocks/sectors")
        check("the new endpoints require auth", r.status_code in (401, 403),
              f"{r.status_code}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        _purge()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 7: the schema in the database
# ─────────────────────────────────────────────────────────────────────────────

def stage_schema() -> None:
    print("\n=== Stage 7: the migrated schema ===")
    db = SessionLocal()
    try:
        cols = {r[0]: (r[1], r[2]) for r in db.execute(text(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = 'company_info'")).all()}
        check("company_info exists with its columns", len(cols) > 15,
              f"{len(cols)} columns")
        check("symbol is NOT NULL", cols.get("symbol", (None, "YES"))[1] == "NO")
        check("name is NOT NULL, so no row is unlabellable",
              cols.get("name", (None, "YES"))[1] == "NO")
        check("refreshed_at is NOT NULL",
              cols.get("refreshed_at", (None, "YES"))[1] == "NO")
        check("both sector columns exist",
              "sector" in cols and "sector_group" in cols, f"{sorted(cols)}")
        check("shares_issued is a bigint, not an integer",
              cols.get("shares_issued", ("",))[0] == "bigint",
              f"{cols.get('shares_issued')} -- JKH has 1.77e10 shares")
        check("business_summary is text, not a bounded string",
              cols.get("business_summary", ("",))[0] == "text",
              f"{cols.get('business_summary')}")

        # Everything but the three identity columns must be nullable: the gaps are
        # real and a NOT NULL would force a substitute value.
        forced = [c for c, (_, nullable) in cols.items()
                  if nullable == "NO" and c not in ("symbol", "name",
                                                    "refreshed_at")]
        check("every other column is nullable", not forced, f"{forced}")

        idx = {r[0]: r[1] for r in db.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'company_info'")).all()}
        check("the sector index is on sector_group",
              "ix_company_info_sector_group" in idx, f"{sorted(idx)}")
        check("no index left on the raw sector string",
              "ix_company_info_sector" not in idx,
              "the raw string is never filtered on")
        definition = idx.get("ix_company_info_sector_group", "")
        check("the sector index is partial on NOT NULL",
              "sector_group IS NOT NULL" in definition, definition)

        version = db.execute(text(
            "SELECT version_num FROM alembic_version")).scalar()
        check("alembic is at the company_info revision",
              version == "b8c9d0e1f2a3", f"{version}")

        check("the symbol is the primary key", db.execute(text(
            "SELECT count(*) FROM information_schema.table_constraints "
            "WHERE table_name = 'company_info' "
            "AND constraint_type = 'PRIMARY KEY'")).scalar() == 1)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 8: nothing throwaway survived
# ─────────────────────────────────────────────────────────────────────────────

def stage_clean() -> None:
    print("\n=== Stage 8: nothing throwaway survived ===")
    db = SessionLocal()
    try:
        for table, col in (("company_info", "symbol"),
                           ("market_data_latest", "symbol"),
                           ("users", "email")):
            n = db.execute(
                text(f"SELECT count(*) FROM {table} WHERE {col} LIKE :p"),
                {"p": f"{PREFIX}%"}).scalar()
            check(f"no {PREFIX}* rows left in {table}", n == 0, f"{n} rows")

        # A profile for a symbol that no longer trades is harmless but pointless.
        n = db.execute(text(
            "SELECT count(*) FROM company_info c "
            "LEFT JOIN market_data_latest m ON m.symbol = c.symbol "
            "WHERE m.symbol IS NULL")).scalar()
        print(f"         {n} profiles for symbols with no current quote")

        print("\n         live counts:")
        for t in ("company_info", "market_data_latest", "market_index_latest",
                  "daily_close"):
            print(f"           {t}: "
                  f"{db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")

        print("\n         biggest companies stored:")
        for r in db.execute(text(
            "SELECT symbol, name, sector_group, market_cap, week52_low, beta_asi "
            "FROM company_info ORDER BY market_cap DESC NULLS LAST LIMIT 5")).all():
            print(f"           {r[0]:<12} {(r[1] or '')[:26]:<28} "
                  f"{(r[2] or '-'):<26} cap={r[3]:,.0f} "
                  f"52wLow={r[4]} beta={r[5]}")
    finally:
        db.close()


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("all", "sweep"):
        stage_sweep()
    if stage in ("all", "fill"):
        stage_fill()
    if stage in ("all", "sectors"):
        stage_sectors()
    if stage in ("all", "upsert"):
        stage_upsert()
    if stage in ("all", "feed"):
        stage_feed()
    if stage in ("all", "http"):
        stage_http()
    if stage in ("all", "schema"):
        stage_schema()
    if stage in ("all", "clean"):
        stage_clean()

    print(f"\n{'=' * 60}\n  {passed} passed, {failed} failed\n{'=' * 60}")
    sys.exit(1 if failed else 0)
