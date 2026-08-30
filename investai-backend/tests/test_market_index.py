# tests/test_market_index.py
"""Tests for I-05: real index values.

The dashboard served ASPI as a literal ``12450.80 / +1.2%`` with a code comment
admitting it. The real reading was ``21279.65 / -0.31%`` — out by 71% and the
wrong way, on the largest number on the home screen.

Offline and holding no database connection, per pytest.ini. Unlike I-04, the
Postgres-specific SQL *can* be checked here: compiling a statement against the
``postgresql`` dialect needs no connection, only executing it does. So the
``ON CONFLICT DO NOTHING`` and ``DO UPDATE ... WHERE`` clauses are asserted on
directly. What still needs a live database — that Postgres honours those clauses
as intended against the real constraint — is covered by ``scripts/verify_i05.py``.

The timestamp tests are the load-bearing ones. ``recorded_at`` for an index comes
from cse.lk's own ``transactionTime``, not from our clock, because cse.lk keeps
serving the last session's close while the market is shut — scraping on a
Thursday returns Tuesday's figures. Trusting a foreign timestamp brings two
failure modes that a plain "is it a datetime" check would miss, and both are
permanent rather than transient: see ``test_rejects_a_prehistoric_timestamp`` and
``test_rejects_a_far_future_timestamp``.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.models.stock import MarketIndexLatest
from app.services import scraper
from app.services.scraper import (_index_latest_payload, _insert_index_history,
                                  _parse_index_record, _upsert_latest,
                                  validate_index_record)


NOW = datetime(2026, 8, 27, 9, 30, tzinfo=timezone.utc)

# 2026-08-25T09:27:00.362Z — a real transactionTime from the live feed.
REAL_MS = 1787650020362
REAL_AT = datetime(2026, 8, 25, 9, 27, 0, 362000, tzinfo=timezone.utc)


def _raw(symbol='BNK', name='Banks', value=1704.08, ts=REAL_MS, **kw):
    """One allSectors entry, shaped as cse.lk actually returns it."""
    rec = {
        'symbol': symbol,
        'name': name,
        'indexName': f'S&P/CSE {name} Index',
        'indexCode': '4010',
        'indexValue': value,
        'change': -1.29,
        'percentage': -0.0756,
        'sectorPreviousClose': 1705.37,
        'sectorTurnoverToday': 87563669.5,
        'sectorVolumeToday': 4102914.0,
        'sectorTradeToday': 1614.0,
        'transactionTime': ts,
    }
    rec.update(kw)
    return rec


def _rec(index_code='BNK', name='Banks', value=1704.08, recorded_at=REAL_AT, **kw):
    """A parsed index record, as validate/persist see it."""
    rec = {
        'index_code': index_code,
        'name': name,
        'value': value,
        'change': -1.29,
        'change_pct': -0.0756,
        'previous_close': 1705.37,
        'turnover': 87563669.5,
        'volume': 4102914.0,
        'trades': 1614,
        'recorded_at': recorded_at,
    }
    rec.update(kw)
    return rec


# ── parsing what cse.lk actually sends ───────────────────────────────────────

def test_parses_an_industry_group_verbatim():
    """BNK, EGY, CG and the rest are CSE's own identifiers; don't invent codes."""
    parsed = _parse_index_record(_raw())

    assert parsed['index_code'] == 'BNK'
    assert parsed['name'] == 'Banks'
    assert parsed['value'] == 1704.08
    assert parsed['previous_close'] == 1705.37
    assert parsed['recorded_at'] == REAL_AT


def test_the_all_share_index_is_stored_under_the_name_the_project_uses():
    """cse.lk's symbol for it is ASI. Everything else here — the dissertation,
    the home screen label, the dashboard key — says ASPI."""
    parsed = _parse_index_record(_raw(symbol='ASI', name='ALL SHARE PRICE INDEX'))

    assert parsed['index_code'] == scraper.ASPI_CODE == 'ASPI'


def test_the_sl20_code_loses_its_space():
    """cse.lk's symbol is literally 'S&P SL20'. A key with a space in it would
    have to be URL-escaped by every caller."""
    parsed = _parse_index_record(_raw(symbol='S&P SL20', name='S&P SL20'))

    assert parsed['index_code'] == 'SPSL20'


def test_the_key_is_symbol_because_index_code_is_null_for_the_headline_indices():
    """indexCode looks like the obvious key and is not: cse.lk leaves it null for
    ASPI and S&P SL20, so it is neither unique nor complete across the 22 rows."""
    parsed = _parse_index_record(
        _raw(symbol='ASI', name='ALL SHARE PRICE INDEX', indexCode=None))

    assert parsed['index_code'] == 'ASPI'


def test_the_short_name_is_kept_not_the_formal_index_title():
    """'Banks' fits a chart legend; 'S&P/CSE Banks Index' does not."""
    parsed = _parse_index_record(_raw())

    assert parsed['name'] == 'Banks'
    assert 'S&P/CSE' not in parsed['name']


def test_a_long_name_is_truncated_to_the_column_width():
    parsed = _parse_index_record(_raw(name='X' * 400))

    assert len(parsed['name']) == 120


def test_epoch_milliseconds_become_a_timezone_aware_utc_instant():
    """recorded_at is TIMESTAMPTZ. A naive value would be read in the server's
    timezone, shifting every reading by the local offset."""
    parsed = _parse_index_record(_raw())

    assert parsed['recorded_at'] == REAL_AT
    assert parsed['recorded_at'].tzinfo is not None
    assert parsed['recorded_at'].utcoffset() == timedelta(0)


def test_absent_activity_figures_stay_null_rather_than_becoming_zero():
    """cse.lk reports turnover, volume and trades per industry group only, so
    they are null for ASPI and S&P SL20. Coercing them to 0 would assert the
    headline indices saw no trading, which is a claim, not a gap."""
    parsed = _parse_index_record(_raw(
        symbol='ASI', name='ALL SHARE PRICE INDEX',
        sectorTurnoverToday=None, sectorVolumeToday=None, sectorTradeToday=None))

    assert parsed['turnover'] is None
    assert parsed['volume'] is None
    assert parsed['trades'] is None


def test_trade_counts_arrive_as_floats_and_are_stored_as_integers():
    """cse.lk sends sectorTradeToday as 1614.0. The column is INTEGER."""
    parsed = _parse_index_record(_raw(sectorTradeToday=1614.0))

    assert parsed['trades'] == 1614
    assert isinstance(parsed['trades'], int)


# ── validation ───────────────────────────────────────────────────────────────

def test_a_real_reading_is_accepted():
    assert validate_index_record(_rec(), NOW) is True


def test_rejects_a_missing_or_blank_code():
    assert validate_index_record(_rec(index_code=''), NOW) is False
    assert validate_index_record(_rec(index_code='   '), NOW) is False


def test_rejects_a_code_too_long_for_the_column():
    assert validate_index_record(_rec(index_code='X' * 21), NOW) is False


def test_rejects_a_blank_name():
    """market_index_latest.name is NOT NULL, so this would fail on insert and
    take the whole scrape's transaction with it."""
    assert validate_index_record(_rec(name=''), NOW) is False


def test_rejects_a_non_positive_or_non_numeric_value():
    """An index at 0 is a placeholder for one cse.lk has not computed yet."""
    for bad in (0, -1, None, 'x'):
        assert validate_index_record(_rec(value=bad), NOW) is False, bad


def test_rejects_a_missing_timestamp():
    assert validate_index_record(_rec(recorded_at=None), NOW) is False


def test_rejects_a_naive_timestamp():
    assert validate_index_record(
        _rec(recorded_at=datetime(2026, 8, 25, 9, 27)), NOW) is False


def test_rejects_a_prehistoric_timestamp():
    """transactionTime of 0 or null parses to the Unix epoch, which sorts before
    every real reading. The upsert only moves a row forward in time, so a 1970
    row would become that index's permanent 'latest' value."""
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    assert validate_index_record(_rec(recorded_at=epoch), NOW) is False


def test_rejects_a_far_future_timestamp():
    """The more dangerous direction. The upsert refuses to move a row backwards,
    so one reading stamped next year would freeze that index forever — every
    subsequent scrape would be silently discarded as stale."""
    next_year = NOW + timedelta(days=365)

    assert validate_index_record(_rec(recorded_at=next_year), NOW) is False


def test_accepts_a_timestamp_within_the_clock_skew_allowance():
    """cse.lk's clock and this server's need not agree to the second."""
    slightly_ahead = NOW + timedelta(minutes=30)

    assert validate_index_record(_rec(recorded_at=slightly_ahead), NOW) is True


def test_the_live_feed_passes_validation_unchanged():
    """A regression guard on the validator, not on the network: every one of the
    22 shapes cse.lk really returns must survive parsing and validation. A
    stricter rule added later that quietly dropped the headline indices would
    show up here."""
    raws = [
        _raw(symbol='ASI', name='ALL SHARE PRICE INDEX', indexCode=None,
             value=21279.65, sectorTurnoverToday=None, sectorVolumeToday=None,
             sectorTradeToday=None),
        _raw(symbol='S&P SL20', name='S&P SL20', indexCode=None, value=5994.81,
             sectorTurnoverToday=None, sectorVolumeToday=None,
             sectorTradeToday=None),
        _raw(symbol='TRP', name='Transportation', value=94679.11),
        _raw(symbol='A&C', name='Automobiles & Components', value=1245.31),
        _raw(symbol='S&S', name='Software & Services', value=1082.24),
    ]
    parsed = [_parse_index_record(r) for r in raws]

    assert all(validate_index_record(p, NOW) for p in parsed)
    assert [p['index_code'] for p in parsed] == [
        'ASPI', 'SPSL20', 'TRP', 'A&C', 'S&S']


# ── the upsert payload ───────────────────────────────────────────────────────

def test_payload_has_one_entry_per_index():
    payload = _index_latest_payload([_rec(index_code='BNK'),
                                     _rec(index_code='EGY'),
                                     _rec(index_code='ASPI')], NOW)

    assert [p['index_code'] for p in payload] == ['BNK', 'EGY', 'ASPI']


def test_payload_deduplicates_a_code_repeated_in_one_batch():
    """Postgres will not let ON CONFLICT DO UPDATE touch one target row twice in
    a single statement, and the failure loses the whole scrape rather than just
    the duplicate. cse.lk returns each index once, but two raw symbols aliasing
    to the same code would be enough."""
    payload = _index_latest_payload(
        [_rec(index_code='ASPI', value=1.0), _rec(index_code='BNK'),
         _rec(index_code='ASPI', value=2.0)], NOW)

    assert len(payload) == 2
    assert sorted(p['index_code'] for p in payload) == ['ASPI', 'BNK']
    assert next(p for p in payload if p['index_code'] == 'ASPI')['value'] == 2.0


def test_payload_carries_exactly_the_latest_table_columns():
    """A missing key is an insert failure and a surplus key is a SQL error —
    market_index_latest has no column the payload does not name."""
    payload = _index_latest_payload([_rec()], NOW)

    assert payload == [{
        'index_code': 'BNK',
        'name': 'Banks',
        'value': 1704.08,
        'change': -1.29,
        'change_pct': -0.0756,
        'previous_close': 1705.37,
        'turnover': 87563669.5,
        'volume': 4102914.0,
        'trades': 1614,
        'recorded_at': REAL_AT,
        'updated_at': NOW,
    }]
    assert set(payload[0]) == {c.name for c in MarketIndexLatest.__table__.columns}


def test_payload_separates_the_exchange_clock_from_ours():
    """recorded_at is when the exchange recalculated the index; updated_at is
    when we last wrote the row. While the market is shut the first stays frozen
    and the second keeps moving, which is how a reader tells 'market closed' from
    'scraper died'."""
    payload = _index_latest_payload([_rec()], NOW)

    assert payload[0]['recorded_at'] == REAL_AT
    assert payload[0]['updated_at'] == NOW
    assert payload[0]['recorded_at'] != payload[0]['updated_at']


def test_payload_keeps_null_activity_figures_as_none():
    payload = _index_latest_payload(
        [_rec(turnover=None, volume=None, trades=None)], NOW)

    assert payload[0]['turnover'] is None
    assert payload[0]['volume'] is None
    assert payload[0]['trades'] is None


# ── the shared upsert helper ─────────────────────────────────────────────────

class ExplodingSession:
    def execute(self, *a, **kw):
        raise AssertionError('must not execute anything for an empty batch')


def test_upsert_is_a_noop_on_an_empty_payload():
    """A VALUES-less INSERT is a syntax error, so an empty scrape must not reach
    the database at all."""
    assert _upsert_latest(ExplodingSession(), MarketIndexLatest,
                          'index_code', []) == 0


def test_upsert_rejects_a_payload_with_inconsistent_keys():
    """One statement covers the whole batch, so every dict must name the same
    columns. Caught here because the alternative is an opaque error from inside
    SQLAlchemy's compiler."""
    with pytest.raises(ValueError, match='inconsistent keys'):
        _upsert_latest(ExplodingSession(), MarketIndexLatest, 'index_code',
                       [{'index_code': 'BNK', 'value': 1.0},
                        {'index_code': 'EGY'}])


def test_upsert_rejects_a_payload_missing_its_key_column():
    with pytest.raises(ValueError, match='missing its key'):
        _upsert_latest(ExplodingSession(), MarketIndexLatest, 'index_code',
                       [{'value': 1.0, 'recorded_at': REAL_AT}])


# ── the SQL that actually gets generated ─────────────────────────────────────

def _sql(statement) -> str:
    """Compile against the real dialect. Needs no connection — only executing
    does — so the Postgres-specific clauses can be asserted on offline."""
    return str(statement.compile(dialect=postgresql.dialect()))


class RecordingSession:
    """Captures statements without a database.

    ``execute`` has to satisfy two callers: ``_insert_index_history`` reads
    ``.rowcount`` from its INSERT, and ``_warn_on_revised_readings`` calls
    ``.all()`` on its SELECT. ``stored`` seeds that SELECT, so a test can present
    a reading as already-persisted without a database.
    """

    def __init__(self, rowcount=0, stored=()):
        self.calls: list[str] = []
        self.statements: list = []
        self._rowcount = rowcount
        self._stored = list(stored)

    def execute(self, statement, *a, **kw):
        self.calls.append('execute')
        self.statements.append(statement)
        return SimpleNamespace(rowcount=self._rowcount,
                               all=lambda: self._stored)

    def commit(self):
        self.calls.append('commit')

    def rollback(self):
        self.calls.append('rollback')

    @property
    def writes(self) -> list:
        """Statements that are not the revision-detection SELECT."""
        return [s for s in self.statements
                if 'INSERT' in _sql(s).upper()]


def test_history_insert_omits_the_name_column():
    """name lives only on market_index_latest — it is static metadata, and
    repeating it per row would let one index accumulate two spellings. There is
    no such column on market_index, so including it would be a SQL error."""
    db = RecordingSession()
    _insert_index_history(db, [_rec()])

    sql = _sql(db.writes[0])
    assert 'INSERT INTO market_index' in sql
    assert ' name' not in sql.split('VALUES')[0]


def test_history_insert_names_every_column_the_table_has():
    db = RecordingSession()
    _insert_index_history(db, [_rec()])

    columns = _sql(db.writes[0]).split('(')[1].split(')')[0]
    assert [c.strip() for c in columns.split(',')] == [
        'index_code', 'value', 'change', 'change_pct', 'previous_close',
        'turnover', 'volume', 'trades', 'recorded_at']


def test_history_insert_ignores_readings_already_stored():
    """The task runs every 15 minutes; the index only moves during a session.
    Without ON CONFLICT DO NOTHING a closed market would accrue 22 duplicate rows
    per run, and the history would be mostly noise."""
    db = RecordingSession()
    _insert_index_history(db, [_rec()])

    sql = _sql(db.writes[0])
    assert 'ON CONFLICT ON CONSTRAINT uq_market_index_code_recorded_at' in sql
    assert 'DO NOTHING' in sql


def test_history_insert_is_a_noop_on_an_empty_batch():
    db = RecordingSession()

    assert _insert_index_history(db, []) == 0
    assert db.calls == []


def test_history_insert_reports_rows_postgres_actually_accepted():
    """Not len(rows): with DO NOTHING the two differ on every re-scrape, and
    that difference is the signal that the run was a duplicate."""
    db = RecordingSession(rowcount=7)

    assert _insert_index_history(db, [_rec(index_code=f'S{i}') for i in range(22)]) == 7


# ── a reading restated under a timestamp already stored ──────────────────────

def test_a_restated_reading_is_reported():
    """DO NOTHING treats (index_code, recorded_at) as a version key. cse.lk does
    not fully honour that: each index carries its own transactionTime, and in the
    live sample S&P SL20's was stamped five hours before the others while holding
    the close value. An index whose timestamp stalls while its value moves would
    have every later value silently dropped from history, so say so.
    """
    db = RecordingSession(stored=[('BNK', REAL_AT, 1700.00)])

    revised = scraper._warn_on_revised_readings(
        db, [{'index_code': 'BNK', 'recorded_at': REAL_AT, 'value': 1704.08}])

    assert revised == ['BNK']


def test_an_unchanged_reading_is_not_reported():
    """The normal case by far — the task runs every 15 minutes against a market
    that is shut most of the day. This must stay silent or the warning is noise."""
    db = RecordingSession(stored=[('BNK', REAL_AT, 1704.08)])

    assert scraper._warn_on_revised_readings(
        db, [{'index_code': 'BNK', 'recorded_at': REAL_AT, 'value': 1704.08}]) == []


def test_a_reading_at_a_new_timestamp_is_not_reported():
    """A moving index is not a restatement — that is an ordinary new row."""
    db = RecordingSession(stored=[('BNK', REAL_AT, 1700.00)])
    later = REAL_AT + timedelta(minutes=15)

    assert scraper._warn_on_revised_readings(
        db, [{'index_code': 'BNK', 'recorded_at': later, 'value': 1704.08}]) == []


def test_nothing_is_reported_when_no_reading_is_stored_yet():
    db = RecordingSession(stored=[])

    assert scraper._warn_on_revised_readings(
        db, [{'index_code': 'BNK', 'recorded_at': REAL_AT, 'value': 1704.08}]) == []


def test_detection_looks_up_only_the_keys_in_this_batch():
    """A full table scan would grow with every session ever stored, for a check
    that only concerns the 22 rows in hand."""
    db = RecordingSession()
    scraper._warn_on_revised_readings(
        db, [{'index_code': 'BNK', 'recorded_at': REAL_AT, 'value': 1.0},
             {'index_code': 'EGY', 'recorded_at': REAL_AT, 'value': 2.0}])

    sql = _sql(db.statements[0])
    assert 'SELECT' in sql
    assert 'FROM market_index' in sql
    assert '(market_index.index_code, market_index.recorded_at) IN' in sql


def test_detection_runs_before_the_insert():
    """Afterwards it could not tell a value cse.lk restated from one this same
    statement had just written."""
    db = RecordingSession(rowcount=1)
    _insert_index_history(db, [_rec()])

    assert 'SELECT' in _sql(db.statements[0])
    assert 'INSERT' in _sql(db.statements[1])


def test_the_latest_upsert_never_moves_a_reading_backwards():
    """A retried Celery task can present an older reading after a newer one has
    landed. Without the guard the older one wins purely by arriving second."""
    db = RecordingSession()
    scraper._refresh_index_latest(db, [_rec()], NOW)

    sql = _sql(db.writes[0])
    assert 'ON CONFLICT (index_code) DO UPDATE' in sql
    assert 'market_index_latest.recorded_at <= excluded.recorded_at' in sql


def test_the_latest_upsert_updates_every_column_except_the_key():
    db = RecordingSession()
    scraper._refresh_index_latest(db, [_rec()], NOW)

    setclause = _sql(db.writes[0]).split('DO UPDATE SET')[1].split('WHERE')[0]
    assert 'index_code =' not in setclause
    for column in ('name', 'value', 'change', 'change_pct', 'previous_close',
                   'turnover', 'volume', 'trades', 'recorded_at', 'updated_at'):
        assert f'{column} =' in setclause, column


# ── the scrape transaction ───────────────────────────────────────────────────

@pytest.fixture
def fake_indices(monkeypatch):
    """Replace the network call with a fixed list of parsed records."""
    def _install(records):
        async def _fake():
            return records
        monkeypatch.setattr(scraper, 'scrape_index_data', _fake)
    return _install


def test_history_and_latest_commit_together(fake_indices):
    """One commit, after both writes. Two would let a crash in between leave the
    reading every read path serves permanently behind the history."""
    fake_indices([_rec(index_code='BNK'), _rec(index_code='EGY')])
    db = RecordingSession(rowcount=2)

    accepted = asyncio.run(scraper.scrape_and_save_indices(db))

    assert accepted == 2
    assert db.calls == ['execute', 'execute', 'execute', 'commit']


def test_the_history_write_precedes_the_latest_write(fake_indices):
    fake_indices([_rec()])
    db = RecordingSession(rowcount=1)

    asyncio.run(scraper.scrape_and_save_indices(db))

    assert 'INSERT INTO market_index ' in _sql(db.writes[0])
    assert 'INSERT INTO market_index_latest' in _sql(db.writes[1])


def test_a_scrape_returning_nothing_does_not_write_or_raise(fake_indices):
    """cse.lk returns an empty body on error, and the endpoint has been seen to
    404 under a different name. That must be a no-op, not a crash."""
    fake_indices([])
    db = RecordingSession()

    assert asyncio.run(scraper.scrape_and_save_indices(db)) == 0
    assert db.calls == ['commit']


def test_invalid_readings_reach_neither_table(fake_indices):
    """One bad row must not cost the other 21. Each of these would otherwise
    either fail the insert or poison the index's 'latest' value permanently."""
    fake_indices([
        _rec(index_code='BNK'),
        _rec(index_code='', name='no code'),
        _rec(index_code='NONAME', name=''),
        _rec(index_code='ZERO', value=0),
        _rec(index_code='EPOCH', recorded_at=datetime(1970, 1, 1, tzinfo=timezone.utc)),
        _rec(index_code='FUTURE',
             recorded_at=datetime.now(timezone.utc) + timedelta(days=400)),
    ])
    db = RecordingSession(rowcount=1)

    accepted = asyncio.run(scraper.scrape_and_save_indices(db))

    assert accepted == 1
    codes = _sql(db.writes[1])
    assert 'FUTURE' not in codes and 'EPOCH' not in codes


def test_one_clock_read_is_shared_by_validation_and_the_upsert(fake_indices):
    """The skew check and updated_at must use the same instant. If validation
    read the clock separately, a reading could pass the skew check against one
    'now' and be stamped with another — and the whole batch's updated_at would
    stop being a single identifiable moment.

    Spied rather than measured with a patched clock: validate_index_record does
    an isinstance check against datetime, so substituting a fake datetime class
    breaks the function under test rather than observing it.
    """
    seen_by_validate, seen_by_payload = [], []
    real_validate = scraper.validate_index_record
    real_payload = scraper._index_latest_payload

    def spy_validate(rec, now=None):
        seen_by_validate.append(now)
        return real_validate(rec, now)

    def spy_payload(rows, now):
        seen_by_payload.append(now)
        return real_payload(rows, now)

    scraper.validate_index_record = spy_validate
    scraper._index_latest_payload = spy_payload
    try:
        fake_indices([_rec(index_code=f'S{i}') for i in range(22)])
        asyncio.run(scraper.scrape_and_save_indices(RecordingSession(rowcount=22)))
    finally:
        scraper.validate_index_record = real_validate
        scraper._index_latest_payload = real_payload

    assert len(seen_by_validate) == 22
    assert len(set(seen_by_validate)) == 1
    assert seen_by_payload == [seen_by_validate[0]]
