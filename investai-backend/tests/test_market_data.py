# tests/test_market_data.py
"""Tests for I-04: market data integrity.

Two invariants are under test here, both of which were broken:

1.  **One scrape, one timestamp.** ``scrape_and_save_cse`` used to call
    ``datetime.now(timezone.utc)`` inside its per-row loop, so one scrape wrote
    rows under several microsecond-apart timestamps. The live table shows 283
    rows under 6 distinct ``recorded_at`` values from a single run. That makes
    "the latest snapshot" unidentifiable, which matters directly: any daily-close
    aggregation has to be able to group by it.

2.  **One row per symbol in ``market_data_latest``.** Four read paths each
    derived the current price from history at request time, each differently and
    each wrongly. The worst was the dashboard watchlist, which ordered *all*
    history by volume and took six rows -- with two snapshots in the table the
    six-slot preview showed three symbols, twice each.

These tests are offline and hold no database connection, per the policy in
pytest.ini. The Postgres-specific half of the change -- the ``ON CONFLICT``
upsert and its no-backwards guard -- cannot be exercised against SQLite, because
``postgresql.insert()`` does not compile on the SQLite dialect. It is proven
against the real database by ``scripts/verify_i04.py`` instead. What is tested
here is the logic that decides *what* to upsert, which is where the dedup
decision lives, plus the transaction ordering in the caller.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.models.stock import MarketData
from app.services import scraper
from app.services.scraper import _latest_payload, _refresh_latest


NOW = datetime(2026, 8, 27, 9, 30, tzinfo=timezone.utc)

# The exchange's timestamp for a symbol's last trade -- deliberately a different
# instant, and a different date, from NOW. cse.lk keeps serving the previous
# session while the market is shut, so the two are routinely days apart and a test
# that used one value for both would prove nothing about them being distinct.
TRADED_AT = datetime(2026, 8, 25, 8, 59, 59, 663000, tzinfo=timezone.utc)


def _row(symbol, price=10.0, market_id=None, recorded_at=NOW, **kw):
    """A MarketData instance, unattached to any session."""
    return MarketData(
        symbol=symbol,
        price=price,
        market_id=market_id,
        recorded_at=recorded_at,
        change=kw.get('change'),
        change_pct=kw.get('change_pct'),
        volume=kw.get('volume'),
        market_cap=kw.get('market_cap'),
        last_traded_at=kw.get('last_traded_at'),
    )


# ── the upsert payload ───────────────────────────────────────────────────────

def test_payload_has_one_entry_per_row_when_symbols_are_unique():
    rows = [_row('AAA'), _row('BBB'), _row('CCC')]
    payload = _latest_payload(rows, NOW)
    assert [p['symbol'] for p in payload] == ['AAA', 'BBB', 'CCC']


def test_payload_deduplicates_a_symbol_repeated_in_one_batch():
    """Postgres cannot update the same target row twice in one statement.

    Without this dedup the upsert raises "ON CONFLICT DO UPDATE command cannot
    affect row a second time" and the whole scrape is lost, not just the
    duplicate.
    """
    rows = [_row('AAA', price=10.0), _row('BBB'), _row('AAA', price=11.0)]
    payload = _latest_payload(rows, NOW)

    assert len(payload) == 2
    symbols = [p['symbol'] for p in payload]
    assert sorted(symbols) == ['AAA', 'BBB']
    assert len(set(symbols)) == len(symbols)


def test_dedup_keeps_the_last_occurrence():
    """Matches what a sequence of single-row upserts would have left behind."""
    rows = [_row('AAA', price=10.0), _row('AAA', price=11.0), _row('AAA', price=12.0)]
    payload = _latest_payload(rows, NOW)

    assert len(payload) == 1
    assert payload[0]['price'] == 12.0


def test_payload_carries_every_column_the_latest_table_needs():
    """market_data_latest.price is NOT NULL and the response schema requires
    market_id and recorded_at, so a missing key is an insert failure, not a
    cosmetic gap.

    Asserted as an exact dict rather than a subset. ``last_traded_at`` was added
    to the table by I-06 and initially left out of this payload, which no subset
    check would have caught: the column existed, the insert succeeded, and it was
    silently NULL for every symbol — so every portfolio snapshot had no way to say
    which session it priced a holding from."""
    row = _row('AAA', price=9.5, market_id=42, change=0.5, change_pct=5.5,
               volume=1000.0, market_cap=1e9, last_traded_at=TRADED_AT)
    payload = _latest_payload([row], NOW)

    assert payload == [{
        'symbol': 'AAA',
        'market_id': 42,
        'price': 9.5,
        'change': 0.5,
        'change_pct': 5.5,
        'volume': 1000.0,
        'market_cap': 1e9,
        'recorded_at': NOW,
        'last_traded_at': TRADED_AT,
        'updated_at': NOW,
    }]


def test_payload_preserves_recorded_at_from_the_history_row():
    """recorded_at must be the snapshot time, not the time of the upsert --
    it is how callers judge staleness."""
    earlier = NOW - timedelta(hours=3)
    payload = _latest_payload([_row('AAA', recorded_at=earlier)], NOW)

    assert payload[0]['recorded_at'] == earlier
    assert payload[0]['updated_at'] == NOW


def test_payload_keeps_null_optional_fields_as_none():
    """A symbol quoted with no volume must store NULL, not 0 -- the watchlist
    orders by volume with NULLS LAST and 0 would sort as a real value."""
    payload = _latest_payload([_row('AAA')], NOW)

    assert payload[0]['volume'] is None
    assert payload[0]['change'] is None
    assert payload[0]['change_pct'] is None
    assert payload[0]['market_cap'] is None


def test_refresh_latest_is_a_noop_on_an_empty_batch():
    """A scrape that returns nothing (or whose every row fails validation) must
    not execute a VALUES-less INSERT, which is a syntax error."""
    class ExplodingSession:
        def execute(self, *a, **kw):
            raise AssertionError('must not execute anything for an empty batch')

    assert _refresh_latest(ExplodingSession(), []) == 0


# ── the scrape transaction ───────────────────────────────────────────────────

class RecordingSession:
    """Records the order of session calls without touching a database."""

    def __init__(self):
        self.added: list = []
        self.calls: list[str] = []
        self.executed = 0

    def add_all(self, rows):
        self.calls.append('add_all')
        self.added.extend(rows)

    def flush(self):
        self.calls.append('flush')
        # Stand in for the database assigning primary keys.
        for i, row in enumerate(self.added, start=1):
            if row.market_id is None:
                row.market_id = i

    def execute(self, *a, **kw):
        self.calls.append('execute')
        self.executed += 1

    def commit(self):
        self.calls.append('commit')

    def rollback(self):
        self.calls.append('rollback')


@pytest.fixture
def fake_cse(monkeypatch):
    """Replace the network call with a fixed payload."""
    def _install(records):
        async def _fake():
            return records
        monkeypatch.setattr(scraper, 'scrape_cse_data', _fake)
    return _install


def _quote(symbol, price=10.0, volume=100.0):
    return {'symbol': symbol, 'last_price': price, 'change': 0.1,
            'change_pct': 1.0, 'volume': volume, 'market_cap': 1e9}


class TickingClock:
    """A ``datetime`` stand-in whose ``now()`` advances one second per call.

    The point is to make the number of clock reads observable. Asserting on real
    timestamps cannot do this reliably: the old per-row ``now()`` produced only
    two distinct values across 283 rows on this machine, because the loop is
    faster than the clock's effective granularity, so a passing test would prove
    nothing about a faster machine. With a ticking clock, "one timestamp for the
    whole scrape" and "one clock read for the whole scrape" are the same
    assertion, and it holds regardless of speed.
    """

    def __init__(self, start):
        self.start = start
        self.calls = 0

    def now(self, tz=None):
        value = self.start + timedelta(seconds=self.calls)
        self.calls += 1
        return value


def test_every_row_in_one_scrape_shares_one_recorded_at(fake_cse, monkeypatch):
    """The bug this closes: 283 rows landed under 6 distinct timestamps because
    now() was called inside the per-row loop, so no query could group by "the
    snapshot"."""
    fake_cse([_quote(f'SYM{i}') for i in range(50)])
    monkeypatch.setattr(scraper, 'datetime', TickingClock(NOW))
    db = RecordingSession()

    saved = asyncio.run(scraper.scrape_and_save_cse(db))

    assert saved == 50
    stamps = {row.recorded_at for row in db.added}
    assert stamps == {NOW}, f'expected one snapshot timestamp, got {len(stamps)}'


def test_clock_reads_do_not_grow_with_the_number_of_rows(fake_cse, monkeypatch):
    """The timestamp is read outside the loop, so a scrape of 500 symbols reads
    the clock exactly as many times as a scrape of 5."""
    counts = {}
    for n in (5, 500):
        fake_cse([_quote(f'SYM{i}') for i in range(n)])
        clock = TickingClock(NOW)
        monkeypatch.setattr(scraper, 'datetime', clock)
        asyncio.run(scraper.scrape_and_save_cse(RecordingSession()))
        counts[n] = clock.calls

    assert counts[5] == counts[500], (
        f'clock read {counts[5]} times for 5 rows but {counts[500]} for 500 '
        '-- the timestamp is being taken per row'
    )


def test_the_snapshot_timestamp_is_timezone_aware_utc(fake_cse):
    """recorded_at is TIMESTAMPTZ. A naive value would be interpreted in the
    server's timezone, silently shifting every quote."""
    fake_cse([_quote('AAA')])
    db = RecordingSession()

    asyncio.run(scraper.scrape_and_save_cse(db))

    assert db.added[0].recorded_at.tzinfo is not None
    assert db.added[0].recorded_at.utcoffset() == timedelta(0)


def test_history_is_flushed_before_the_latest_table_is_written(fake_cse):
    """market_data_latest.market_id must point at the history row it was copied
    from, and market_id is only assigned by the flush."""
    fake_cse([_quote('AAA'), _quote('BBB')])
    db = RecordingSession()

    asyncio.run(scraper.scrape_and_save_cse(db))

    assert db.calls.index('flush') < db.calls.index('execute')
    assert all(row.market_id is not None for row in db.added)


def test_history_and_latest_commit_together(fake_cse):
    """One commit, after both writes. Two commits would let a crash in between
    leave the price every read path serves permanently behind the history."""
    fake_cse([_quote('AAA')])
    db = RecordingSession()

    asyncio.run(scraper.scrape_and_save_cse(db))

    assert db.calls.count('commit') == 1
    assert db.calls == ['add_all', 'flush', 'execute', 'commit']


def test_invalid_records_reach_neither_table(fake_cse):
    """A zero-price placeholder row must not be stored as a genuine LKR 0.00
    quote in history, and must not become the symbol's current price either."""
    fake_cse([
        _quote('GOOD', price=10.0),
        {'symbol': 'ZERO', 'last_price': 0.0},
        {'symbol': '', 'last_price': 5.0},
        {'symbol': 'X' * 21, 'last_price': 5.0},
        {'symbol': 'NEGVOL', 'last_price': 5.0, 'volume': -1},
    ])
    db = RecordingSession()

    saved = asyncio.run(scraper.scrape_and_save_cse(db))

    assert saved == 1
    assert [row.symbol for row in db.added] == ['GOOD']


def test_a_scrape_returning_nothing_does_not_write_or_raise(fake_cse):
    """The CSE API returns an empty list outside trading hours and on error.
    That must be a no-op, not a crash and not an empty-VALUES INSERT."""
    fake_cse([])
    db = RecordingSession()

    saved = asyncio.run(scraper.scrape_and_save_cse(db))

    assert saved == 0
    assert db.added == []
    assert db.executed == 0


def test_a_duplicate_symbol_from_the_api_is_kept_in_history_but_not_in_latest(fake_cse):
    """History is append-only, so both rows belong there. The latest table has
    symbol as its primary key, so only one can go in."""
    fake_cse([_quote('AAA', price=10.0), _quote('AAA', price=11.0)])
    db = RecordingSession()

    saved = asyncio.run(scraper.scrape_and_save_cse(db))

    assert saved == 2
    assert [row.symbol for row in db.added] == ['AAA', 'AAA']
    assert len(_latest_payload(db.added, NOW)) == 1
