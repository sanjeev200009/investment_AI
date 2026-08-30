# tests/test_daily_close.py
"""Tests for I-06: real price history and real portfolio history.

Two fabrications are closed here. ``generateMockChartData()`` built the stock
detail chart from ``Math.random()`` and labelled the x-axis with real times, so
every symbol showed a plausible, entirely invented six months. The dashboard
served ``weekly_history`` as ``current_value × [0.85, 0.82, 0.94, 1.0]`` — four
numbers derived from the present value, so the "performance" line showed the same
15% dip recovering to exactly today no matter what the portfolio had done.

Offline and holding no database connection, per pytest.ini. As in I-05, the
Postgres-specific SQL is still checked: compiling against the ``postgresql``
dialect needs no connection, so the composite ``ON CONFLICT`` and the per-table
guard column are asserted directly. What needs a live database — that Postgres
honours them against the real primary keys — is ``scripts/verify_i06.py``.

The load-bearing tests are the date ones. ``trade_date`` comes from the
exchange's ``lastTradedTime``, never from our clock, and this is not a
hypothetical preference: the two snapshots already sitting in ``market_data``
were stamped 2026-07-05, a **Sunday** when the CSE is shut, and 2026-08-27, a
Thursday carrying the Tuesday 2026-08-25 session. Dating a chart from the scrape
would put trading days on weekends and repeat one session across every day the
market stayed closed.
"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.models.portfolio import Portfolio, PortfolioHolding, PortfolioSnapshot
from app.models.stock import DailyClose, MarketDataLatest
from app.services import portfolio_history
from app.services.portfolio_history import exchange_today, snapshot_portfolios
from app.services.scraper import (_daily_close_payload, _latest_payload,
                                  _upsert_latest, _warn_on_inconsistent_ohlc)

# The scrape ran on Thursday 2026-08-27 and the feed returned the Tuesday
# 2026-08-25 session. Every date assertion below turns on those being different.
NOW = datetime(2026, 8, 27, 10, 56, 50, tzinfo=timezone.utc)
SCRAPE_DATE = date(2026, 8, 27)

# 2026-08-25T08:59:59.663Z -- a real lastTradedTime from the live feed.
TRADED_AT = datetime(2026, 8, 25, 8, 59, 59, 663000, tzinfo=timezone.utc)
TRADE_DATE = date(2026, 8, 25)


def _rec(symbol='HAYC.N0000', at=TRADED_AT, **kw):
    """One accepted scrape record, shaped as scrape_cse_data returns it.

    Values are a real row from the live feed: HAYC opened 186.5, ranged
    184.0-192.0, closed 190.75 against a previous close of 185.75.
    """
    rec = {
        'symbol': symbol,
        'name': 'HAYLEYS PLC',
        'last_price': 190.75,
        'change': 5.0,
        'change_pct': 2.69,
        'volume': 482438.0,
        'market_cap': 1.43e10,
        'open': 186.5,
        'high': 192.0,
        'low': 184.0,
        'close': 190.75,
        'previous_close': 185.75,
        'turnover': 91_000_000.0,
        'trades': 544,
        'last_traded_at': at,
    }
    rec.update(kw)
    return rec


# ── trade_date comes from the exchange, not from us ──────────────────────────

def test_trade_date_is_the_exchange_session_not_the_scrape_date():
    """The whole reason the table and this function exist. A scrape on Thursday
    the 27th of the Tuesday the 25th session must file under the 25th."""
    [row] = _daily_close_payload([_rec()], NOW)

    assert row['trade_date'] == TRADE_DATE
    assert row['trade_date'] != SCRAPE_DATE


def test_a_record_without_an_exchange_timestamp_is_dropped_not_dated_from_our_clock():
    """There is deliberately no fallback to ``now``. A fallback would reintroduce
    exactly the bug the column was added to fix, silently, for whichever symbols
    the feed happened to omit."""
    payload = _daily_close_payload([_rec(at=None)], NOW)

    assert payload == []


def test_a_naive_exchange_timestamp_is_dropped():
    """trade_date is derived by ``.date()``. On a naive value that silently reads
    the wrong calendar day either side of midnight, and a CSE session sits close
    enough to 00:00 UTC (Colombo is UTC+5:30) for it to matter."""
    payload = _daily_close_payload([_rec(at=TRADED_AT.replace(tzinfo=None))], NOW)

    assert payload == []


def test_a_nonsense_timestamp_type_is_dropped_rather_than_raising():
    """The feed sends epoch milliseconds; a string or an int reaching here means
    the parse changed. One bad symbol must not cost the other 270 their row."""
    payload = _daily_close_payload(
        [_rec(symbol='BAD', at=1787650020362), _rec(symbol='GOOD')], NOW)

    assert [r['symbol'] for r in payload] == ['GOOD']


def test_the_scrape_date_never_appears_anywhere_in_the_row():
    """``updated_at`` is the only field allowed to carry our clock, and it is not
    a date the chart can be keyed on."""
    [row] = _daily_close_payload([_rec()], NOW)

    assert row['updated_at'] == NOW
    dates = {v.date() if isinstance(v, datetime) else v
             for v in row.values() if isinstance(v, (date, datetime))}
    assert SCRAPE_DATE not in dates - {NOW.date()}


# ── one row per symbol-day ───────────────────────────────────────────────────

def test_duplicate_symbol_rows_collapse_to_the_latest_trade():
    """Postgres refuses to touch the same target row twice in one statement --
    "ON CONFLICT DO UPDATE command cannot affect row a second time" -- and the
    trade summary has returned duplicate instrument rows before."""
    early = _rec(at=TRADED_AT - timedelta(hours=3), close=180.0)
    late = _rec(at=TRADED_AT, close=190.75)

    payload = _daily_close_payload([late, early], NOW)

    assert len(payload) == 1
    assert payload[0]['close'] == 190.75
    assert payload[0]['last_traded_at'] == TRADED_AT


def test_the_same_symbol_on_two_dates_is_two_rows():
    """The dedup key is (symbol, trade_date), not symbol. Collapsing on symbol
    alone would make the table one-row-per-stock and there would be no series."""
    payload = _daily_close_payload(
        [_rec(at=TRADED_AT), _rec(at=TRADED_AT - timedelta(days=2))], NOW)

    assert {r['trade_date'] for r in payload} == {
        TRADE_DATE, TRADE_DATE - timedelta(days=2)}


def test_a_later_duplicate_does_not_win_by_arriving_second():
    """Order of appearance must not decide it -- a retried task can present an
    older record after a newer one."""
    for order in ((0, 1), (1, 0)):
        recs = [_rec(at=TRADED_AT, close=190.75),
                _rec(at=TRADED_AT - timedelta(hours=3), close=180.0)]
        [row] = _daily_close_payload([recs[i] for i in order], NOW)

        assert row['close'] == 190.75


# ── the OHLC fields ──────────────────────────────────────────────────────────

def test_the_session_range_is_carried_through_verbatim():
    """These four fields are the chart. The scraper kept six of the endpoint's 23
    fields before I-06 and none of them was an open, high, low or close."""
    [row] = _daily_close_payload([_rec()], NOW)

    assert (row['open'], row['high'], row['low'], row['close']) == (
        186.5, 192.0, 184.0, 190.75)
    assert row['previous_close'] == 185.75
    assert (row['volume'], row['turnover'], row['trades']) == (
        482438.0, 91_000_000.0, 544)


def test_a_missing_high_stays_null_rather_than_becoming_zero():
    """A symbol whose only trade was its open has no meaningful high. Zero would
    drag the chart's y-axis to the origin and flatten every real movement."""
    [row] = _daily_close_payload([_rec(high=None, low=None)], NOW)

    assert row['high'] is None
    assert row['low'] is None


def test_close_falls_back_to_the_last_price_when_the_feed_omits_it():
    """``close`` is NOT NULL -- a row with no close is not a chart point -- and
    ``last_price`` is the field validate_market_record has already proven
    positive."""
    [row] = _daily_close_payload([_rec(close=None)], NOW)

    assert row['close'] == 190.75


def test_a_nonpositive_close_falls_back_too():
    [row] = _daily_close_payload([_rec(close=0.0)], NOW)

    assert row['close'] == 190.75


# ── the feed's own inconsistency ─────────────────────────────────────────────

def test_a_close_outside_the_days_range_is_stored_as_reported():
    """19 of 271 live symbols did this: closingPrice, price and previousClose were
    all one number while open/high/low described real trades. INME traded
    1800-1875 across seven trades and reported a close of 1681.

    Clamping would invent a price the exchange never printed; dropping the row
    would discard an open, high and low that are not in doubt."""
    [row] = _daily_close_payload(
        [_rec(symbol='INME.N0000', open=1873.0, high=1875.0, low=1800.0,
              close=1681.0, previous_close=1681.0, last_price=1681.0)], NOW)

    assert row['close'] == 1681.0
    assert row['close'] < row['low']


def test_the_inconsistency_is_reported_rather_than_passed_over():
    bad = _warn_on_inconsistent_ohlc(_daily_close_payload(
        [_rec(symbol='INME.N0000', high=1875.0, low=1800.0, close=1681.0),
         _rec(symbol='HAYC.N0000')], NOW))

    assert bad == ['INME.N0000']


def test_a_close_on_the_boundary_of_the_range_is_not_flagged():
    """A symbol that traded once has open == high == low == close. That is the
    normal shape of an illiquid instrument, not a contradiction."""
    assert _warn_on_inconsistent_ohlc(_daily_close_payload(
        [_rec(open=12.7, high=12.7, low=12.7, close=12.7)], NOW)) == []


def test_a_row_with_no_range_cannot_contradict_it():
    """None is not a bound. Comparing against it would raise, and a missing high
    is silence rather than disagreement."""
    assert _warn_on_inconsistent_ohlc(_daily_close_payload(
        [_rec(high=None, low=None)], NOW)) == []


# ── the generalised upsert ───────────────────────────────────────────────────

def _sql(statement) -> str:
    """Compile to Postgres SQL. Compiling needs no connection, only executing
    does -- so the dialect-specific clauses can be asserted on offline."""
    return str(statement.compile(dialect=postgresql.dialect()))


class RecordingSession:
    """Captures statements without a database."""

    def __init__(self):
        self.statements: list = []
        self.calls: list[str] = []

    def execute(self, statement, *a, **kw):
        self.calls.append('execute')
        self.statements.append(statement)
        return SimpleNamespace(rowcount=0, all=lambda: [])

    def commit(self):
        self.calls.append('commit')


def test_the_daily_close_upsert_conflicts_on_both_key_columns():
    """A single-column ON CONFLICT (symbol) would make the table
    one-row-per-stock, and every scrape would overwrite yesterday."""
    db = RecordingSession()
    _upsert_latest(db, DailyClose, ('symbol', 'trade_date'),
                   _daily_close_payload([_rec()], NOW), guard='last_traded_at')

    sql = _sql(db.statements[0])
    assert 'INSERT INTO daily_close' in sql
    assert 'ON CONFLICT (symbol, trade_date) DO UPDATE' in sql


def test_daily_close_is_guarded_on_the_exchange_clock_not_ours():
    """updated_at is our clock, so guarding on it would let a stale scrape win by
    being written later. last_traded_at cannot be gamed that way."""
    db = RecordingSession()
    _upsert_latest(db, DailyClose, ('symbol', 'trade_date'),
                   _daily_close_payload([_rec()], NOW), guard='last_traded_at')

    where = _sql(db.statements[0]).split('WHERE')[1]
    assert 'daily_close.last_traded_at <= excluded.last_traded_at' in where
    assert 'updated_at' not in where


def test_the_guard_is_inclusive_so_a_rescrape_still_refreshes_updated_at():
    """``<=`` not ``<``. Re-scraping an unchanged session must still move
    updated_at, because that is how a caller tells a closed market from a dead
    scraper."""
    db = RecordingSession()
    _upsert_latest(db, DailyClose, ('symbol', 'trade_date'),
                   _daily_close_payload([_rec()], NOW), guard='last_traded_at')

    assert '<= excluded.last_traded_at' in _sql(db.statements[0])
    assert '< excluded.last_traded_at' not in _sql(db.statements[0]).replace('<=', '')


def test_the_key_columns_are_never_in_the_set_clause():
    """Assigning a primary key to itself is legal and pointless; assigning it to
    a *different* value from EXCLUDED would be a silent row move."""
    db = RecordingSession()
    _upsert_latest(db, DailyClose, ('symbol', 'trade_date'),
                   _daily_close_payload([_rec()], NOW), guard='last_traded_at')

    assigned = _sql(db.statements[0]).split('DO UPDATE SET')[1].split('WHERE')[0]
    assert 'symbol =' not in assigned
    assert 'trade_date =' not in assigned
    assert 'close =' in assigned


def test_the_portfolio_snapshot_upsert_conflicts_on_portfolio_and_date():
    db = RecordingSession()
    _upsert_latest(db, PortfolioSnapshot, ('portfolio_id', 'snapshot_date'),
                   [{'portfolio_id': 1, 'snapshot_date': TRADE_DATE,
                     'total_value': 100.0, 'total_cost': 90.0,
                     'holdings_count': 1, 'priced_count': 1,
                     'priced_at': TRADED_AT, 'updated_at': NOW}],
                   guard='updated_at')

    sql = _sql(db.statements[0])
    assert 'INSERT INTO portfolio_snapshots' in sql
    assert 'ON CONFLICT (portfolio_id, snapshot_date) DO UPDATE' in sql
    assert 'portfolio_snapshots.updated_at <= excluded.updated_at' in sql


def test_a_payload_missing_its_guard_column_is_rejected_before_the_database():
    """Without the check the guard silently compiles against a column that is not
    in EXCLUDED, and the failure surfaces from inside SQLAlchemy's compiler."""
    db = RecordingSession()
    with pytest.raises(ValueError, match='guard'):
        _upsert_latest(db, DailyClose, ('symbol', 'trade_date'),
                       [{'symbol': 'AAA', 'trade_date': TRADE_DATE,
                         'close': 1.0}], guard='last_traded_at')

    assert db.statements == []


def test_a_payload_missing_a_key_column_is_rejected():
    db = RecordingSession()
    with pytest.raises(ValueError, match='trade_date'):
        _upsert_latest(db, DailyClose, ('symbol', 'trade_date'),
                       [{'symbol': 'AAA', 'close': 1.0,
                         'last_traded_at': TRADED_AT}],
                       guard='last_traded_at')

    assert db.statements == []


def test_an_empty_payload_issues_no_statement():
    """A closed market and a failed fetch both produce no records. Neither should
    send Postgres an INSERT with no VALUES."""
    db = RecordingSession()

    assert _upsert_latest(db, DailyClose, ('symbol', 'trade_date'), [],
                          guard='last_traded_at') == 0
    assert db.statements == []


def test_the_latest_quote_mirror_carries_the_exchange_timestamp():
    """market_data_latest.last_traded_at is what a portfolio snapshot records as
    priced_at. Omitted from the payload, the column exists and is permanently
    NULL, and no snapshot can say which session it priced from."""
    row = SimpleNamespace(symbol='HAYC.N0000', market_id=1, price=190.75,
                          change=5.0, change_pct=2.69, volume=482438.0,
                          market_cap=1.43e10, recorded_at=NOW,
                          last_traded_at=TRADED_AT)

    [payload] = _latest_payload([row], NOW)

    assert payload['last_traded_at'] == TRADED_AT
    assert payload['recorded_at'] == NOW      # both, not one or the other


# ── portfolio valuation snapshots ────────────────────────────────────────────

def test_a_snapshot_is_dated_in_colombo_not_utc():
    """Colombo is UTC+5:30, so anything after 18:30 UTC is already tomorrow at
    the exchange. Dating in UTC would file those snapshots a day early and, worse,
    collide with the previous day's row."""
    assert exchange_today(datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc)) == \
        date(2026, 8, 28)


def test_a_snapshot_taken_just_before_the_boundary_keeps_the_earlier_date():
    assert exchange_today(datetime(2026, 8, 27, 18, 29, tzinfo=timezone.utc)) == \
        date(2026, 8, 27)


def test_the_scheduled_run_time_lands_on_the_day_it_ran():
    """The beat entry is 15:10 Colombo, which is 09:40 UTC the same day."""
    assert exchange_today(datetime(2026, 8, 27, 9, 40, tzinfo=timezone.utc)) == \
        date(2026, 8, 27)


class StubSession:
    """A Session stand-in for snapshot_portfolios.

    Dispatches each query on its first entity rather than on call order, so a test
    does not quietly pass if the two reads are ever swapped. The keys are derived
    from the mapped attributes rather than written as strings, so renaming a column
    breaks the stub instead of silently routing to the wrong result set.
    """

    def __init__(self, portfolios=(), holdings=(), quotes=()):
        self._results = {
            _entity_key(PortfolioHolding.portfolio_id): list(holdings),
            _entity_key(Portfolio.portfolio_id): list(portfolios),
            _entity_key(MarketDataLatest): list(quotes),
        }
        self.statements: list = []
        self.calls: list[str] = []
        self.queries: list[str] = []

    def query(self, *entities):
        key = _entity_key(entities[0])
        self.queries.append(key)
        if key not in self._results:
            raise AssertionError(f'unexpected query on {key!r}')
        return _StubQuery(self._results[key])

    def execute(self, statement, *a, **kw):
        self.calls.append('execute')
        self.statements.append(statement)
        return SimpleNamespace(rowcount=0, all=lambda: [])

    def commit(self):
        self.calls.append('commit')


def _entity_key(entity) -> str:
    """A mapped class by its table name, a column by its qualified name."""
    return getattr(entity, '__tablename__', None) or str(entity)


class _StubQuery:
    def __init__(self, rows):
        self._rows = rows

    def join(self, *a, **kw):
        return self

    def filter(self, *a, **kw):
        return self

    def all(self):
        return self._rows


def _holding(portfolio_id=1, symbol='HAYC.N0000', quantity=100,
             avg_buy_price=150.0):
    return SimpleNamespace(portfolio_id=portfolio_id, symbol=symbol,
                           quantity=quantity, avg_buy_price=avg_buy_price)


def _quote(symbol='HAYC.N0000', price=190.75, last_traded_at=TRADED_AT):
    return SimpleNamespace(symbol=symbol, price=price,
                           last_traded_at=last_traded_at)


def _payload(monkeypatch, **kw):
    """Run snapshot_portfolios and return the rows it handed to the upsert."""
    captured: list[dict] = []

    def _capture(db, model, key, payload, guard='recorded_at'):
        captured.extend(payload)
        assert model is PortfolioSnapshot
        assert key == ('portfolio_id', 'snapshot_date')
        assert guard == 'updated_at'
        return len(payload)

    import app.services.scraper as scraper_mod
    monkeypatch.setattr(scraper_mod, '_upsert_latest', _capture)
    written = snapshot_portfolios(StubSession(**kw), NOW)
    return written, captured


def test_a_portfolio_is_valued_at_the_latest_quote_not_the_purchase_price(
        monkeypatch):
    written, [row] = _payload(
        monkeypatch,
        portfolios=[SimpleNamespace(portfolio_id=1)],
        holdings=[_holding()],
        quotes=[_quote()])

    assert written == 1
    assert row['total_value'] == pytest.approx(19075.0)   # 100 x 190.75
    assert row['total_cost'] == pytest.approx(15000.0)    # 100 x 150.00


def test_the_cost_basis_is_stored_not_derived_later(monkeypatch):
    """Recomputing it from today's holdings would let a purchase made next week
    retroactively change what last week's return looks like."""
    _, [row] = _payload(monkeypatch,
                        portfolios=[SimpleNamespace(portfolio_id=1)],
                        holdings=[_holding()], quotes=[_quote()])

    assert 'total_cost' in row


def test_an_unquoted_holding_is_valued_at_cost_and_counted_as_unpriced(
        monkeypatch):
    """Matching the dashboard, so a holding we have never quoted contributes what
    was paid rather than zero. priced_count is what stops the total reading as
    authoritative when it is not."""
    _, [row] = _payload(monkeypatch,
                        portfolios=[SimpleNamespace(portfolio_id=1)],
                        holdings=[_holding()], quotes=[])

    assert row['total_value'] == pytest.approx(15000.0)
    assert row['holdings_count'] == 1
    assert row['priced_count'] == 0
    assert row['priced_at'] is None


def test_priced_at_is_the_newest_session_any_holding_was_priced_from(monkeypatch):
    """One number for the row, so it has to be the freshest -- claiming the oldest
    would understate how current the valuation is."""
    older = TRADED_AT - timedelta(days=4)
    _, [row] = _payload(
        monkeypatch,
        portfolios=[SimpleNamespace(portfolio_id=1)],
        holdings=[_holding(symbol='AAA'), _holding(symbol='BBB')],
        quotes=[_quote('AAA', last_traded_at=older),
                _quote('BBB', last_traded_at=TRADED_AT)])

    assert row['priced_at'] == TRADED_AT
    assert row['priced_count'] == 2


def test_an_empty_portfolio_still_gets_a_row(monkeypatch):
    """Worth zero is a fact about it. A series that starts at zero and steps up
    when the first holding is bought is the true shape; omitting the row would
    make the chart start mid-story."""
    _, [row] = _payload(monkeypatch,
                        portfolios=[SimpleNamespace(portfolio_id=7)],
                        holdings=[], quotes=[])

    assert row['portfolio_id'] == 7
    assert row['total_value'] == 0.0
    assert row['holdings_count'] == 0


def test_every_portfolio_is_valued_not_only_the_ones_holding_something(
        monkeypatch):
    _, rows = _payload(monkeypatch,
                       portfolios=[SimpleNamespace(portfolio_id=1),
                                   SimpleNamespace(portfolio_id=2)],
                       holdings=[_holding(portfolio_id=1)],
                       quotes=[_quote()])

    assert {r['portfolio_id'] for r in rows} == {1, 2}


def test_a_holding_whose_portfolio_is_gone_is_skipped_not_crashed_on(monkeypatch):
    """The two reads are separate queries, so a portfolio can be deleted between
    them. A KeyError here would cost every other portfolio its snapshot."""
    _, rows = _payload(monkeypatch,
                       portfolios=[SimpleNamespace(portfolio_id=1)],
                       holdings=[_holding(portfolio_id=1),
                                 _holding(portfolio_id=99)],
                       quotes=[_quote()])

    assert [r['portfolio_id'] for r in rows] == [1]
    assert rows[0]['holdings_count'] == 1


def test_no_portfolios_writes_nothing(monkeypatch):
    written, rows = _payload(monkeypatch, portfolios=[], holdings=[], quotes=[])

    assert (written, rows) == (0, [])


def test_the_snapshot_is_dated_from_the_clock_it_is_given(monkeypatch):
    """Passed in rather than read inside, so the whole run shares one date -- the
    same reason recorded_at is read once per scrape."""
    _, [row] = _payload(monkeypatch,
                        portfolios=[SimpleNamespace(portfolio_id=1)],
                        holdings=[], quotes=[])

    assert row['snapshot_date'] == exchange_today(NOW)
    assert row['updated_at'] == NOW


def test_a_quote_with_no_price_does_not_value_a_holding_at_none(monkeypatch):
    """MarketDataLatest.price is nullable. Multiplying None by a quantity raises,
    and the cost basis is the right answer for a symbol with no usable quote."""
    _, [row] = _payload(monkeypatch,
                        portfolios=[SimpleNamespace(portfolio_id=1)],
                        holdings=[_holding()],
                        quotes=[_quote(price=None)])

    assert row['total_value'] == pytest.approx(15000.0)
    assert row['priced_count'] == 0


def test_the_exchange_timezone_is_resolvable_on_this_platform():
    """Windows ships no system tz database, so ZoneInfo('Asia/Colombo') raises
    without the tzdata package. It was only ever present transitively, via celery
    and kombu, and the API process dates snapshots too."""
    assert portfolio_history.EXCHANGE_TZ is not None
    assert exchange_today(NOW).isoformat() == '2026-08-27'
