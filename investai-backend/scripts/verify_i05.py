# scripts/verify_i05.py
"""Live verification for I-05 (real index values).

Run with:  python -m scripts.verify_i05

The dashboard served ASPI as a literal ``12450.80 / +1.2%``. The real reading is
``21279.65 / -0.31%`` — out by 71% and pointing the wrong way, on the largest
number on the home screen.

tests/test_market_index.py is offline by policy (see pytest.ini) and compiles the
Postgres SQL without executing it, which proves the statements are *generated*
correctly. Three things still need a live database and a live cse.lk:

*   that Postgres honours ``ON CONFLICT DO NOTHING`` against the real named
    constraint, so a 15-minute task against a closed market stores nothing;
*   that the ``WHERE recorded_at <= excluded.recorded_at`` guard really refuses
    to move a reading backwards; and
*   that the read paths return the real index, not the old literal.

Stage 1 is the exception to this project's "verification writes nothing" rule and
does so deliberately: it runs the real scrape and **commits** it. Storing index
readings is the feature, the tables start empty, and the operation is idempotent
by construction — re-running this script inserts no duplicate history. Every
other stage uses a ``ZZ_I05_`` code prefix inside a transaction rolled back in a
``finally``, and the last stage re-checks that nothing recognisable survived.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, text

from app.database import SessionLocal
from app.models.stock import MarketIndex, MarketIndexLatest
from app.models.user import User
from app.services.portfolio_history import EXCHANGE_TZ
from app.services.scraper import (ASPI_CODE, HEADLINE_INDEX_CODES,
                                  _insert_index_history,
                                  _refresh_index_latest,
                                  _warn_on_revised_readings,
                                  scrape_and_save_indices, scrape_index_data,
                                  validate_index_record)

PREFIX = "ZZ_I05_"

# A fixed reference instant for the synthetic fixtures, so a stage that writes a
# row "6 hours ago" and then reads it back is comparing against the same anchor
# either side. Deliberately NOT used for checks against live scraped data: those
# run minutes after module load, and a clock captured up here would call a
# perfectly fresh reading "stamped in the future". Those read the clock
# themselves.
NOW = datetime.now(timezone.utc)

# The figures the dashboard used to hardcode. Nothing should ever serve these.
OLD_FAKE_ASPI = 12450.80
OLD_FAKE_CHANGE_PCT = 1.2

# CSE continuous trading, local time. Used only to decide whether a check may
# assume the session is settled -- see market_is_open().
_OPEN_HOUR, _OPEN_MIN = 9, 30
_CLOSE_HOUR, _CLOSE_MIN = 14, 30


def market_is_open() -> bool:
    """True if the CSE is mid-session right now, in Asia/Colombo.

    Three checks below were written assuming a settled session and failed on a
    live one: an intraday re-scrape legitimately advances index values, so
    "inserts no new history rows" and "restates nothing" are false during
    trading. Rather than delete them -- they are the checks that prove the
    idempotency the whole append-only history design rests on -- they degrade to
    observations while the market is open and assert while it is closed.

    Weekends only; the CSE's public holiday calendar is not in this codebase, so
    a holiday reads as closed-and-settled, which is the correct assumption
    anyway. There is no market-is-open helper in app/ to borrow -- the
    application never needs to know, only this verification does.
    """
    local = datetime.now(EXCHANGE_TZ)
    if local.weekday() >= 5:
        return False
    minutes = local.hour * 60 + local.minute
    return (_OPEN_HOUR * 60 + _OPEN_MIN) <= minutes <= (_CLOSE_HOUR * 60 + _CLOSE_MIN)

# The figures the dashboard used to hardcode. Nothing should ever serve these.
OLD_FAKE_ASPI = 12450.80
OLD_FAKE_CHANGE_PCT = 1.2

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


def _rec(index_code: str, value: float, recorded_at: datetime,
         name: str = "I05 throwaway", turnover: float | None = None) -> dict:
    return {"index_code": index_code, "name": name, "value": value,
            "change": None, "change_pct": None, "previous_close": None,
            "turnover": turnover, "volume": None, "trades": None,
            "recorded_at": recorded_at}


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: the real scrape, committed
# ─────────────────────────────────────────────────────────────────────────────

def stage_scrape() -> None:
    """Scrape cse.lk for real and persist it.

    Also the end-to-end proof: if the endpoint moved, the payload shape changed,
    or a validation rule is too strict, the accepted count drops below 22 here
    rather than silently emptying the dashboard in production.
    """
    print("\n=== Stage 1: live scrape of cse.lk, committed ===")
    db = SessionLocal()
    try:
        before_hist = db.query(MarketIndex).count()
        before_latest = db.query(MarketIndexLatest).count()

        accepted = asyncio.run(scrape_and_save_indices(db))
        check("the live scrape accepted readings", accepted > 0,
              "cse.lk returned nothing usable — endpoint or payload may have moved")
        check("all 22 CSE indices were accepted", accepted == 22,
              f"accepted {accepted}; CSE publishes ASPI + S&P SL20 + 20 groups")

        after_hist = db.query(MarketIndex).count()
        after_latest = db.query(MarketIndexLatest).count()
        print(f"         history {before_hist} -> {after_hist}, "
              f"latest {before_latest} -> {after_latest}")

        check("market_index_latest holds one row per accepted index",
              after_latest == accepted, f"{after_latest} rows for {accepted} indices")

        aspi = db.query(MarketIndexLatest).filter_by(index_code=ASPI_CODE).one_or_none()
        check("ASPI is present", aspi is not None)
        if aspi is None:
            return

        print(f"         ASPI = {aspi.value} ({aspi.change_pct:+.2f}%) "
              f"at {aspi.recorded_at.isoformat()}")
        check("the stored ASPI is not the old hardcoded figure",
              abs(aspi.value - OLD_FAKE_ASPI) > 1.0, f"value={aspi.value}")
        check("ASPI is in a plausible range for the CSE All Share",
              5_000 < aspi.value < 100_000, f"value={aspi.value}")

        sl20 = db.query(MarketIndexLatest).filter_by(index_code="SPSL20").one_or_none()
        check("S&P SL20 is present", sl20 is not None)
        check("S&P SL20 is below ASPI, as the two indices stand",
              sl20 is not None and sl20.value < aspi.value,
              f"sl20={sl20.value if sl20 else None}, aspi={aspi.value}")

        # recorded_at is the exchange's transactionTime, not our clock. While the
        # market is shut cse.lk keeps serving the last session's close, so this is
        # expected to lag — the point is that it lags *honestly* instead of being
        # restamped with now() and filing Tuesday's close under Thursday.
        lag = NOW - aspi.recorded_at
        print(f"         reading is {lag.total_seconds() / 3600:.1f}h old "
              f"(market closed => expected)")
        check("recorded_at is the exchange clock, not the scrape clock",
              aspi.recorded_at < NOW - timedelta(seconds=30),
              f"recorded_at={aspi.recorded_at} is within 30s of now, which would "
              f"mean it was stamped locally")
        check("updated_at is our clock and is current",
              (NOW - aspi.updated_at).total_seconds() < 300,
              f"updated_at={aspi.updated_at}")
        check("the two clocks are stored separately",
              aspi.recorded_at != aspi.updated_at)

        # cse.lk reports turnover per industry group only.
        headline = db.query(MarketIndexLatest).filter(
            MarketIndexLatest.index_code.in_(HEADLINE_INDEX_CODES)).all()
        check("the headline indices carry no turnover, rather than zero",
              all(h.turnover is None for h in headline),
              f"{[(h.index_code, h.turnover) for h in headline]}")

        # This asserted `count(turnover IS NOT NULL) == 20`, and it was wrong: an
        # industry group in which nothing traded gets null turnover, not zero.
        # Household & Personal Products traded nothing on 2026-08-28 and the check
        # failed on a market condition rather than a defect -- while the real defect
        # it should have caught, /stocks/indices treating "no turnover" as "is a
        # headline index" and hoisting HPP to the top of the list, went unnoticed
        # because both symptoms have the same cause.
        #
        # What must hold is narrower and actually a property of the pipeline: only
        # industry groups ever carry turnover, and a group carrying none carries no
        # volume or trade count either -- an untraded sector, not a half-parsed row.
        with_turnover = {r.index_code for r in db.query(MarketIndexLatest)
                         .filter(MarketIndexLatest.turnover.isnot(None)).all()}
        check("only industry groups carry turnover",
              not (with_turnover & set(HEADLINE_INDEX_CODES)),
              f"headline codes with turnover: "
              f"{sorted(with_turnover & set(HEADLINE_INDEX_CODES))}")

        quiet = db.query(MarketIndexLatest).filter(
            MarketIndexLatest.turnover.is_(None),
            MarketIndexLatest.index_code.notin_(HEADLINE_INDEX_CODES)).all()
        check("a group with no turnover has no volume or trades either",
              all(q.volume is None and q.trades is None for q in quiet),
              f"{[(q.index_code, q.turnover, q.volume, q.trades) for q in quiet]}")
        check("every group with turnover also has a value",
              all(r.value and r.value > 0 for r in db.query(MarketIndexLatest)
                  .filter(MarketIndexLatest.turnover.isnot(None)).all()))
        print(f"         {len(with_turnover)}/20 industry groups traded this "
              f"session; quiet: {sorted(q.index_code for q in quiet) or 'none'}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: re-scraping a stored session stores nothing
# ─────────────────────────────────────────────────────────────────────────────

def stage_idempotent() -> None:
    """The task runs every 15 minutes; the index only moves during a session.

    Without ``ON CONFLICT DO NOTHING`` on ``(index_code, recorded_at)`` a closed
    market would accrue 22 duplicate rows per tick — 22 × 4 × 24 a day — and the
    history would be mostly noise. This is committed too, and must be a no-op.

    **Two of these checks assert only while the market is closed.** A settled
    session is the condition under which "nothing new was stored" is the correct
    outcome; mid-session, cse.lk recalculates indices between the two scrapes and
    new readings at new timestamps are precisely what append-only history is for.
    Asserting no-growth during trading would fail on correct behaviour, so those
    two degrade to bounded observations — see ``market_is_open()``.
    """
    print("\n=== Stage 2: re-scraping the same session is a no-op (committed) ===")
    live = market_is_open()
    if live:
        print("         NOTE: the CSE is mid-session, so cse.lk may legitimately "
              "advance readings between the two scrapes below. The two "
              "idempotency checks relax to bounds; re-run after 14:30 "
              "Asia/Colombo for the strict form.")
    db = SessionLocal()
    try:
        before = db.query(MarketIndex).count()
        accepted = asyncio.run(scrape_and_save_indices(db))
        after = db.query(MarketIndex).count()

        check("the second scrape still accepts every reading", accepted == 22,
              f"accepted {accepted}")
        if live:
            # At most one new row per index: anything above 22 would mean the same
            # (index_code, recorded_at) got in twice, which is the actual defect
            # this stage exists to catch, and it stays caught mid-session.
            check("and inserts at most one new history row per index",
                  0 <= after - before <= 22,
                  f"history grew {before} -> {after}, i.e. {after - before} rows "
                  f"for 22 indices")
            print(f"         intraday: {after - before} of 22 indices had "
                  f"recalculated since the previous scrape")
        else:
            check("but inserts no new history rows", after == before,
                  f"history grew {before} -> {after}")

        dupes = db.execute(text("""
            SELECT count(*) FROM (
              SELECT index_code, recorded_at FROM market_index
              GROUP BY index_code, recorded_at HAVING count(*) > 1
            ) d
        """)).scalar()
        check("market_index holds no duplicate (index_code, recorded_at)",
              dupes == 0, f"{dupes} duplicated readings")

        # The constraint, not just the ON CONFLICT clause, is what makes this
        # structural — a future insert written without the clause still cannot
        # duplicate a reading.
        con = db.execute(text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'market_index'::regclass AND contype = 'u'
        """)).fetchall()
        check("the uniqueness is enforced by a real constraint",
              ("uq_market_index_code_recorded_at",) in [tuple(c) for c in con],
              f"unique constraints={[c[0] for c in con]}")

        rejected = False
        try:
            row = db.query(MarketIndex).first()
            db.add(MarketIndex(index_code=row.index_code, value=1.0,
                               recorded_at=row.recorded_at))
            db.flush()
        except Exception:
            rejected = True
        finally:
            db.rollback()
        check("the database itself rejects a duplicate reading", rejected,
              "a plain INSERT of an existing (index_code, recorded_at) succeeded")

        # DO NOTHING treats (index_code, recorded_at) as a version key, and
        # _warn_on_revised_readings reports when cse.lk does not honour that. It
        # must be silent when the feed is consistent, or it is noise on every tick.
        records = asyncio.run(scrape_index_data())
        revised = _warn_on_revised_readings(db, [
            {"index_code": r["index_code"], "recorded_at": r["recorded_at"],
             "value": r["value"]} for r in records])
        if live:
            # Mid-session cse.lk does restate: it publishes a new value against an
            # unchanged transactionTime for an index it has recalculated but not
            # re-stamped. That is the exact case this warning was written for, so
            # observing it is the helper working, not a failure. What must still
            # hold is that it names real indices and does not claim the whole
            # market was restated -- a blanket 22 would mean the comparison itself
            # is broken (wrong key, or reading the wrong column).
            check("any intraday restatement is partial, not the whole feed",
                  len(revised) < 22,
                  f"all 22 indices reported as restated: {revised}")
            print(f"         intraday: cse.lk restated "
                  f"{len(revised)} of 22 at an unchanged timestamp"
                  f"{': ' + str(revised) if revised else ''}")
        else:
            check("re-scraping the stored session restates nothing", not revised,
                  f"cse.lk restated: {revised}")
    finally:
        db.rollback()
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: the latest-row upsert, with throwaway codes (rolled back)
# ─────────────────────────────────────────────────────────────────────────────

def stage_upsert() -> None:
    print("\n=== Stage 3: market_index_latest upsert semantics (rolled back) ===")
    db = SessionLocal()
    try:
        code_a, code_b = f"{PREFIX}A", f"{PREFIX}B"

        _refresh_index_latest(db, [_rec(code_a, 10.0, NOW),
                                   _rec(code_b, 20.0, NOW)], NOW)
        db.flush()
        rows = {r.index_code: r for r in db.query(MarketIndexLatest).filter(
            MarketIndexLatest.index_code.like(f"{PREFIX}%")).all()}
        check("new index codes are inserted", len(rows) == 2, f"got {sorted(rows)}")
        check("the inserted value is correct", rows[code_a].value == 10.0)

        later = NOW + timedelta(minutes=15)
        _refresh_index_latest(db, [_rec(code_a, 11.5, later)], later)
        db.flush()
        db.expire_all()
        a = db.query(MarketIndexLatest).filter_by(index_code=code_a).one()
        check("a newer reading moves the value forward", a.value == 11.5,
              f"value={a.value}")
        check("a newer reading moves recorded_at forward", a.recorded_at == later)

        # The failure mode: a retried Celery task presenting an older reading
        # after a newer one has already landed. Without the guard the stale one
        # wins purely by arriving second.
        earlier = NOW - timedelta(hours=6)
        _refresh_index_latest(db, [_rec(code_a, 99.0, earlier)], NOW)
        db.flush()
        db.expire_all()
        a = db.query(MarketIndexLatest).filter_by(index_code=code_a).one()
        check("an older reading does NOT overwrite a newer one", a.value == 11.5,
              f"value moved backwards to {a.value}")
        check("an older reading leaves recorded_at alone", a.recorded_at == later)

        _refresh_index_latest(db, [_rec(code_a, 11.5, later)], later)
        db.flush()
        db.expire_all()
        check("replaying the same reading is idempotent, not an error",
              db.query(MarketIndexLatest).filter_by(index_code=code_a).one().value
              == 11.5)

        # Postgres refuses to touch one target row twice in a single statement, and
        # the error loses the whole scrape rather than just the duplicate. Two raw
        # cse.lk symbols aliasing to one code would be enough to trigger it.
        much_later = NOW + timedelta(hours=1)
        try:
            _refresh_index_latest(db, [_rec(code_b, 21.0, much_later),
                                       _rec(code_b, 22.0, much_later)], much_later)
            db.flush()
            db.expire_all()
            b = db.query(MarketIndexLatest).filter_by(index_code=code_b).one()
            check("a code repeated in one batch does not raise", True)
            check("the last occurrence wins", b.value == 22.0, f"value={b.value}")
        except Exception as exc:
            check("a code repeated in one batch does not raise", False,
                  f"{type(exc).__name__}: {exc}")
            db.rollback()

        # And the history insert, which uses DO NOTHING rather than DO UPDATE, so
        # a reading already stored is left exactly as it was — but says so, since
        # the newer value is being discarded.
        db.query(MarketIndex).filter(
            MarketIndex.index_code.like(f"{PREFIX}%")).delete()
        n1 = _insert_index_history(db, [_rec(code_a, 10.0, NOW)])
        db.flush()
        n2 = _insert_index_history(db, [_rec(code_a, 999.0, NOW)])
        db.flush()
        db.expire_all()
        stored = db.query(MarketIndex).filter_by(index_code=code_a).all()
        check("the first history insert reports one row", n1 == 1, f"got {n1}")
        check("a repeat history insert reports zero rows", n2 == 0, f"got {n2}")
        check("only one history row exists for that reading", len(stored) == 1,
              f"{len(stored)} rows")
        check("DO NOTHING left the original value untouched",
              stored and stored[0].value == 10.0,
              f"value={stored[0].value if stored else None}")
        # The warning above this line in the output is that discard being reported.
        check("a discarded restatement is detected, not silent",
              _warn_on_revised_readings(
                  db, [{"index_code": code_a, "recorded_at": NOW, "value": 999.0}])
              == [code_a],
              "the newer value would vanish from history unremarked")

        dupes = db.execute(text("""
            SELECT count(*) FROM (
              SELECT index_code FROM market_index_latest
              GROUP BY index_code HAVING count(*) > 1
            ) d
        """)).scalar()
        check("market_index_latest cannot hold a duplicate code", dupes == 0,
              f"{dupes} duplicated codes")
    finally:
        db.rollback()
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: the schema serves the reads it was designed for
# ─────────────────────────────────────────────────────────────────────────────

def stage_schema() -> None:
    print("\n=== Stage 4: indexes and stored-data consistency (read-only) ===")
    db = SessionLocal()
    try:
        idx = {r[0] for r in db.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'market_index'"))}
        check("market_index carries exactly two indexes", len(idx) == 2,
              f"indexes={sorted(idx)}")
        check("the unique constraint's index exists",
              "uq_market_index_code_recorded_at" in idx, f"indexes={sorted(idx)}")

        # A btree on (index_code, recorded_at) ASC is scanned *backwards* to serve
        # ORDER BY recorded_at DESC, so this table needs no companion DESC index —
        # unlike market_data, which has no such constraint and needed an explicit
        # ix_market_data_symbol_recorded_at.
        #
        # seqscan is disabled only for the EXPLAIN: at 22 rows the planner is right
        # to prefer a sequential scan, and the claim under test is that the index
        # *can* serve the query, not that it is chosen at this table size.
        db.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(r[0] for r in db.execute(text(
            "EXPLAIN SELECT * FROM market_index WHERE index_code = :c "
            "ORDER BY recorded_at DESC LIMIT 1"), {"c": ASPI_CODE}).fetchall())
        check("a per-index time series is served by the constraint's btree",
              "uq_market_index_code_recorded_at" in plan, plan.replace("\n", " | "))
        check("and it is scanned backwards, so no DESC index is needed",
              "Backward" in plan, plan.replace("\n", " | "))
        db.rollback()

        # The same invariant I-04 checks on market_data_latest.
        codes = db.execute(text(
            "SELECT count(DISTINCT index_code) FROM market_index")).scalar()
        latest = db.execute(text("SELECT count(*) FROM market_index_latest")).scalar()
        check("one latest row per historical index code", codes == latest,
              f"history has {codes} codes, latest has {latest} rows")

        stale = db.execute(text("""
            SELECT count(*) FROM market_index_latest l
            JOIN (SELECT index_code, max(recorded_at) mx FROM market_index
                  GROUP BY index_code) m ON m.index_code = l.index_code
            WHERE l.recorded_at <> m.mx
        """)).scalar()
        check("every latest row is the newest reading for its index", stale == 0,
              f"{stale} stale rows")

        prehistoric = db.execute(text(
            "SELECT count(*) FROM market_index WHERE recorded_at < '2000-01-01'"
        )).scalar()
        check("no reading was stored at the Unix epoch", prehistoric == 0,
              f"{prehistoric} rows, which would each be a permanent 'latest'")

        future = db.execute(text(
            "SELECT count(*) FROM market_index WHERE recorded_at > now() + interval '1 day'"
        )).scalar()
        check("no reading was stored in the future", future == 0,
              f"{future} rows, which would freeze that index forever")

        nonpositive = db.execute(text(
            "SELECT count(*) FROM market_index WHERE value <= 0")).scalar()
        check("no index was stored at or below zero", nonpositive == 0,
              f"{nonpositive} rows")
    finally:
        db.rollback()
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: the endpoints, over HTTP
# ─────────────────────────────────────────────────────────────────────────────

def stage_http() -> None:
    """``get_current_user`` is overridden rather than satisfied with a real
    Supabase token: the auth path is unchanged by I-05 and is covered by
    verify_i03_phase1.py, and minting a token would mean creating and deleting a
    real account for no added coverage.
    """
    print("\n=== Stage 5: endpoints over HTTP (auth overridden) ===")
    from fastapi.testclient import TestClient

    from app.dependencies import get_current_user
    from app.main import app
    from app.services import llm

    stub = User(user_id=uuid.uuid4(), email=f"{PREFIX}http@example.invalid",
                full_name="I05 stub", password_hash="x", role="user",
                is_email_verified=True)
    app.dependency_overrides[get_current_user] = lambda: stub
    original = llm.complete_text_sync
    llm.complete_text_sync = lambda *a, **kw: None  # force the DB insight fallback
    try:
        client = TestClient(app)

        r = client.get("/api/v1/stocks/indices")
        check("GET /stocks/indices returns 200", r.status_code == 200,
              f"{r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            body = r.json()
            check("GET /stocks/indices returns all 22 indices", len(body) == 22,
                  f"got {len(body)}")
            codes = [i["index_code"] for i in body]
            check("no index appears twice", len(codes) == len(set(codes)),
                  f"{len(codes) - len(set(codes))} duplicates")
            check("the headline indices sort first", codes[:2] == [ASPI_CODE, "SPSL20"]
                  or set(codes[:2]) == {ASPI_CODE, "SPSL20"}, f"first two: {codes[:2]}")
            groups = [i for i in body if i["turnover"] is not None]
            turnovers = [g["turnover"] for g in groups]
            check("industry groups are ordered by turnover descending",
                  turnovers == sorted(turnovers, reverse=True),
                  f"{turnovers[:5]}")
            first = body[0]
            for field in ("index_code", "name", "value", "change", "change_pct",
                          "previous_close", "turnover", "volume", "trades",
                          "recorded_at"):
                check(f"response carries `{field}`", field in first,
                      f"keys={sorted(first)}")

        r = client.get(f"/api/v1/stocks/indices?index_code={ASPI_CODE.lower()}")
        check("GET /stocks/indices?index_code= filters, case-insensitively",
              r.status_code == 200 and len(r.json()) == 1
              and r.json()[0]["index_code"] == ASPI_CODE,
              f"{r.status_code}: {r.text[:200]}")

        r = client.get("/api/v1/stocks/indices?index_code=NOSUCHINDEX")
        check("an unknown code returns empty, not an error",
              r.status_code == 200 and r.json() == [], f"{r.status_code}")

        r = client.get("/api/v1/dashboard/")
        check("GET /dashboard/ returns 200", r.status_code == 200,
              f"{r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            body = r.json()
            aspi = body.get("aspi")
            check("dashboard serves an aspi object", isinstance(aspi, dict),
                  f"got {aspi!r}")
            if isinstance(aspi, dict):
                check("dashboard ASPI is no longer the hardcoded 12450.80",
                      abs(aspi["value"] - OLD_FAKE_ASPI) > 1.0,
                      f"value={aspi['value']}")
                check("dashboard change_pct is no longer the hardcoded +1.2",
                      abs(aspi["change_pct"] - OLD_FAKE_CHANGE_PCT) > 0.01,
                      f"change_pct={aspi['change_pct']}")
                check("dashboard ASPI matches the stored reading",
                      _stored_aspi_matches(aspi), f"payload={aspi}")
                check("dashboard reports the exchange's timestamp",
                      "recorded_at" in aspi and aspi["recorded_at"],
                      f"keys={sorted(aspi)}")

            sectors = body.get("sectors")
            check("dashboard serves a sector breakdown", bool(sectors),
                  f"got {sectors!r}")
            if sectors:
                total = sum(s["share_pct"] for s in sectors)
                check("sector shares sum to 100 within rounding",
                      abs(total - 100) < 1.0, f"sum={total}")
                check("the breakdown is not three slices summing to exactly 100",
                      not (len(sectors) == 3 and total == 100.0),
                      "that was the tell in the hardcoded version")
                check("every named slice is a real CSE industry group",
                      all(s["code"] == "OTHER" or _is_real_code(s["code"])
                          for s in sectors),
                      f"{[s['code'] for s in sectors]}")
                check("the remainder slice accounts for the unnamed groups",
                      any(s["code"] == "OTHER" for s in sectors),
                      f"{[s['code'] for s in sectors]}")
                check("no slice claims a change it cannot know",
                      all(s["change_pct"] is None for s in sectors
                          if s["code"] == "OTHER"))
                print(f"         sectors: "
                      f"{[(s['code'], s['share_pct']) for s in sectors]}")
    finally:
        llm.complete_text_sync = original
        app.dependency_overrides.pop(get_current_user, None)


def _stored_aspi_matches(payload: dict) -> bool:
    db = SessionLocal()
    try:
        row = db.query(MarketIndexLatest).filter_by(index_code=ASPI_CODE).one_or_none()
        return row is not None and abs(row.value - payload["value"]) < 1e-6
    finally:
        db.close()


def _is_real_code(code: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(MarketIndexLatest).filter_by(index_code=code).count() == 1
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 6: validation against the live payload, and nothing left behind
# ─────────────────────────────────────────────────────────────────────────────

def stage_live_payload() -> None:
    """Parse cse.lk's current response and check every record on its own.

    Stage 1 only sees an aggregate count. If one index started failing validation
    this names it, rather than leaving a silent 21-of-22.
    """
    print("\n=== Stage 6: every live record passes validation (read-only) ===")
    records = asyncio.run(scrape_index_data())
    check("cse.lk returned records", bool(records), "empty response")
    if not records:
        return

    check("cse.lk returned 22 indices", len(records) == 22, f"got {len(records)}")

    rejected = [r for r in records
                if not validate_index_record(r, datetime.now(timezone.utc))]
    check("no live record is rejected", not rejected,
          f"rejected: {[r.get('index_code') for r in rejected]}")

    codes = [r["index_code"] for r in records]
    check("live codes are unique", len(codes) == len(set(codes)),
          f"{len(codes) - len(set(codes))} duplicates")
    check("ASPI is in the live payload", ASPI_CODE in codes, f"codes={codes}")
    check("SPSL20 is in the live payload", "SPSL20" in codes, f"codes={codes}")
    check("no raw cse.lk symbol leaked through unaliased",
          "ASI" not in codes and "S&P SL20" not in codes, f"codes={codes}")
    check("every record has a name for the latest table's NOT NULL column",
          all(r["name"] for r in records))
    check("every timestamp is timezone-aware",
          all(r["recorded_at"].tzinfo is not None for r in records))

    # transactionTime is per index, not market-wide: it is the last time that
    # index was recalculated, so 22 records carry 22 timestamps. What must hold is
    # that they all describe one trading session and none is in the future.
    stamps = sorted(r["recorded_at"] for r in records)
    dates = {s.date() for s in stamps}
    check("every reading belongs to the same trading date", len(dates) == 1,
          f"dates={sorted(d.isoformat() for d in dates)}")

    # Against the clock read here, not one captured at module load, and with a
    # tolerance. Both mattered: this check failed by 1.8 seconds on a reading that
    # was fresh, because NOW was six stages older than the scrape, and cse.lk's
    # own clock runs a second or two ahead of this machine's. A minute of
    # tolerance still catches what the check is for -- a timestamp parsed with the
    # wrong unit or the wrong epoch, which lands years out, not seconds. The write
    # path already takes this position: validate_index_record allows a full day
    # (MAX_INDEX_CLOCK_SKEW) for the same reason.
    skew = timedelta(minutes=1)
    now = datetime.now(timezone.utc)
    check("no live reading is stamped meaningfully in the future",
          stamps[-1] <= now + skew,
          f"newest={stamps[-1].isoformat()} is "
          f"{(stamps[-1] - now).total_seconds():.0f}s ahead of now")
    print(f"         per-index timestamps span "
          f"{(stamps[-1] - stamps[0]).total_seconds() / 3600:.1f}h "
          f"({stamps[0].time()} .. {stamps[-1].time()} UTC)")

    # The freshest and stalest, named. S&P SL20 was stamped five hours before the
    # rest in the sample this was written against, while carrying the close value
    # the dedicated snpData endpoint reported — which is why the history insert
    # reports restatements rather than trusting the timestamp blindly.
    by_time = sorted(records, key=lambda r: r["recorded_at"])
    print(f"         stalest: {by_time[0]['index_code']} at "
          f"{by_time[0]['recorded_at'].time()} UTC; freshest: "
          f"{by_time[-1]['index_code']} at {by_time[-1]['recorded_at'].time()} UTC")


def stage_clean() -> None:
    print("\n=== Stage 7: no throwaway data survived ===")
    db = SessionLocal()
    try:
        for table in ("market_index", "market_index_latest"):
            n = db.execute(
                text(f"SELECT count(*) FROM {table} WHERE index_code LIKE :p"),
                {"p": f"{PREFIX}%"}).scalar()
            check(f"no {PREFIX}* rows left in {table}", n == 0, f"{n} rows")

        n = db.execute(text("SELECT count(*) FROM users WHERE email LIKE :p"),
                       {"p": f"{PREFIX}%"}).scalar()
        check(f"no {PREFIX}* users left", n == 0, f"{n} rows")

        print("\n         live counts:")
        for t in ("market_index", "market_index_latest", "market_data",
                  "market_data_latest", "news_sentiment", "users"):
            print(f"           {t}: "
                  f"{db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")

        print("\n         stored indices:")
        # Ordered the way /stocks/indices orders them, so this listing is a
        # readable check on that route rather than a second, differently-wrong
        # opinion. `turnover IS NULL DESC` was the ordering here too, and it put a
        # quiet industry group above S&P SL20 for the same reason the route did.
        headline_first = case(
            {code: i for i, code in enumerate(HEADLINE_INDEX_CODES)},
            value=MarketIndexLatest.index_code,
            else_=len(HEADLINE_INDEX_CODES))
        for r in db.query(MarketIndexLatest).order_by(
                headline_first,
                MarketIndexLatest.turnover.desc().nullslast(),
                MarketIndexLatest.index_code).all():
            pct = f"{r.change_pct:+.2f}%" if r.change_pct is not None else "     -"
            to = f"{r.turnover:,.0f}" if r.turnover is not None else "-"
            print(f"           {r.index_code:<8} {r.value:>12,.2f}  {pct:>8}  "
                  f"turnover={to:>16}  {r.name}")
    finally:
        db.close()


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("all", "scrape"):
        stage_scrape()
    if stage in ("all", "idempotent"):
        stage_idempotent()
    if stage in ("all", "upsert"):
        stage_upsert()
    if stage in ("all", "schema"):
        stage_schema()
    if stage in ("all", "http"):
        stage_http()
    if stage in ("all", "payload"):
        stage_live_payload()
    if stage in ("all", "clean"):
        stage_clean()

    print(f"\n{'=' * 60}\n  {passed} passed, {failed} failed\n{'=' * 60}")
    sys.exit(1 if failed else 0)
