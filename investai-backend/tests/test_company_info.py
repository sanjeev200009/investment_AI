# tests/test_company_info.py
"""Tests for I-07: real company fundamentals in place of fabricated ones.

``StockDetailScreen.js`` displayed four company fundamentals, all four of which
were modulus arithmetic on the live price::

    peRatio   = 8 + (price % 15)
    high52    = price * (1 + (price % 30) / 100)
    low52     = price * (1 - (price % 25) / 100)
    marketCap = 10 + (price % 50) * 2.5      # rendered with a "B" suffix

Labelled "P/E RATIO", "52W HIGH", "52W LOW" and "MARKET CAP". The modulus is the
tell: two stocks at the same price had identical fundamentals, and a price crossing
a multiple of 15 made the "P/E" jump.

Offline and holding no database connection, per pytest.ini. The payloads below are
**verbatim shapes from the live feed**, trimmed to the keys that are read — the
list-wrapping inconsistency between the two endpoints, the ``" "`` business-summary
title, and the null-heavy unit-trust response are all reproduced rather than
idealised, because every one of them is a case that broke something during
development. What needs a live database and live HTTP is
``scripts/verify_i07.py``.

Sector normalisation has its own file, ``test_sectors.py``.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.models.stock import CompanyInfo
from app.services.company_info import (_clean, _first, _positive, _website,
                                       parse_company_payload)
from app.services.scraper import _upsert_latest

REFRESHED = datetime(2026, 8, 27, 10, 40, tzinfo=timezone.utc)

# JKH's real response, trimmed. companyInfoSummery returns bare objects.
JKH_SUMMARY = {
    'reqSymbolInfo': {
        'id': 176, 'name': 'JOHN KEELLS HOLDINGS PLC', 'symbol': 'JKH.N0000',
        'marketCap': 351256216014.0, 'marketCapPercentage': 4.55,
        'quantityIssued': 17740212930, 'parValue': None,
        'isin': 'LK0155N00000',
        'p12HiPrice': 23.9, 'p12LowPrice': 17.8,
        'allHiPrice': 430.25, 'allLowPrice': 2.5,
        'ytdHiPrice': 23.9,
    },
    'reqSymbolBetaInfo': {
        'triASIBetaValue': 1.1489, 'betaValueSPSL': 1.2116,
        'triASIBetaPeriod': '2026',
    },
}

# companyProfile wraps the same kind of record in a one-element list.
JKH_PROFILE = {
    'reqComSumInfo': [{
        'name': 'JOHN KEELLS HOLDINGS PLC', 'sector': 'Capital Goods',
        'boardType': 'Main Board', 'established': '1979',
        'web': 'www.keells.com', 'fax': '0112306160',
    }],
    'infoCompanyBusinessSummary': [{
        # The title is boilerplate and the body is the prose. Reproduced because
        # reading the title instead would have dropped every summary in the market.
        'title': ' ',
        'body': 'John Keells Holdings PLC is a diversified conglomerate.',
    }],
}

# CALC.U0000, a closed-end fund. The nulls are the point: no sector, no beta, no
# market cap. Note the curly quotes in the name -- they are in the live feed.
FUND_SUMMARY = {
    'reqSymbolInfo': {
        'name': 'CAL FIVE YEAR CLOSED END FUND (“Units”)',
        'marketCap': None, 'marketCapPercentage': None,
        'quantityIssued': 20000000, 'parValue': None, 'isin': 'LK0508U00003',
        'p12HiPrice': None, 'p12LowPrice': None,
        'allHiPrice': None, 'allLowPrice': None,
    },
    'reqSymbolBetaInfo': None,
}

FUND_PROFILE = {
    'reqComSumInfo': [{
        'name': 'CAL FIVE YEAR CLOSED END FUND', 'sector': None,
        'boardType': None, 'established': None, 'web': None,
    }],
    'infoCompanyBusinessSummary': [],
}


# ── the two endpoints disagree about wrapping ────────────────────────────────

def test_first_unwraps_a_one_element_list():
    """companyProfile returns ``[{...}]`` where companyInfoSummery returns
    ``{...}``. Without this every companyProfile field would be read off a list and
    come back None -- silently, since ``list.get`` is never reached."""
    assert _first([{'a': 1}]) == {'a': 1}
    assert _first({'a': 1}) == {'a': 1}


def test_first_returns_none_for_the_shapes_that_mean_absence():
    """An empty ``infoCompanyBusinessSummary`` list is normal -- 60 of 291 symbols
    have no description -- so it must not raise."""
    assert _first([]) is None
    assert _first(None) is None
    assert _first('a string') is None
    assert _first(42) is None


def test_first_takes_only_the_first_of_a_longer_list():
    """These containers hold one record. If cse.lk ever returns two, taking the
    first is the documented behaviour rather than an accident."""
    assert _first([{'a': 1}, {'a': 2}]) == {'a': 1}


# ── the feed's several spellings of "no value" ───────────────────────────────

def test_clean_folds_every_spelling_of_absent_into_none():
    """cse.lk uses four: absent, null, "", and a single space. A caller must not
    have to test for each one."""
    assert _clean(None) is None
    assert _clean('') is None
    assert _clean('   ') is None
    assert _clean('  x  ') == 'x'


def test_clean_truncates_to_the_column_width():
    """Every String column here is bounded, and a value over the limit is a write
    error at the database rather than a truncation."""
    assert _clean('x' * 300, 20) == 'x' * 20
    assert len(_clean('LK0155N00000', 20)) == 12


def test_positive_rejects_zero_because_zero_means_no_figure():
    """A zero 52-week low is not a low price, it is the feed declining to answer --
    and it would drag a range chart's axis to the origin, making every stock look
    like it had crashed at some point in the year."""
    assert _positive(0) is None
    assert _positive('0') is None
    assert _positive(-1) is None
    assert _positive(17.8) == 17.8
    assert _positive(None) is None
    assert _positive('not a number') is None


# ── websites, which arrive in three spellings ───────────────────────────────

@pytest.mark.parametrize('raw,expected', [
    # All three of these are in one four-symbol sample from the live feed.
    ('https://www.cal.lk/', 'https://www.cal.lk/'),
    ('www.hnb.lk', 'https://www.hnb.lk'),
    ('www.keells.com', 'https://www.keells.com'),
    ('http://example.lk', 'http://example.lk'),
    ('  www.spaced.lk  ', 'https://www.spaced.lk'),
])
def test_a_website_always_comes_back_with_a_scheme(raw, expected):
    """``Linking.openURL`` on Android fails outright on a scheme-less URL, so two of
    the three spellings above would produce a tappable link that does nothing."""
    assert _website(raw) == expected


@pytest.mark.parametrize('raw', ['mailto:info@x.lk', 'ftp://files.x.lk', '',
                                 '   ', None])
def test_a_non_website_is_dropped_rather_than_prefixed(raw):
    """``https://mailto:info@x.lk`` is a broken link presented as a working one,
    which is worse than no link at all."""
    assert _website(raw) is None


# ── folding both payloads into one row ──────────────────────────────────────

def test_a_full_payload_parses_every_stored_field():
    row = parse_company_payload('JKH.N0000', JKH_SUMMARY, JKH_PROFILE, REFRESHED)

    assert row['symbol'] == 'JKH.N0000'
    assert row['name'] == 'JOHN KEELLS HOLDINGS PLC'
    assert row['sector'] == 'Capital Goods'
    assert row['sector_group'] == 'Capital Goods'
    assert row['market_cap'] == 351256216014.0
    assert row['market_cap_pct'] == 4.55
    assert row['shares_issued'] == 17740212930
    assert row['isin'] == 'LK0155N00000'
    assert row['week52_high'] == 23.9
    assert row['week52_low'] == 17.8
    assert row['all_time_high'] == 430.25
    assert row['beta_asi'] == 1.1489
    assert row['beta_sl20'] == 1.2116
    assert row['beta_period'] == '2026'
    assert row['board'] == 'Main Board'
    assert row['established'] == '1979'
    assert row['website'] == 'https://www.keells.com'
    assert row['business_summary'].startswith('John Keells Holdings PLC')
    assert row['refreshed_at'] == REFRESHED


def test_shares_issued_survives_being_larger_than_an_int32():
    """JKH has 17,740,212,930 shares issued, three orders of magnitude past
    int32 -- which is why the column is BigInteger."""
    row = parse_company_payload('JKH.N0000', JKH_SUMMARY, JKH_PROFILE, REFRESHED)
    assert row['shares_issued'] > 2 ** 31


def test_the_symbols_own_name_wins_over_the_issuing_companys():
    """``reqSymbolInfo`` describes the security; ``reqComSumInfo`` describes the
    company that issued it. For a unit trust those differ, and the security's name
    is what a client asked about."""
    row = parse_company_payload('CALC.U0000', FUND_SUMMARY, FUND_PROFILE, REFRESHED)
    assert row['name'] == 'CAL FIVE YEAR CLOSED END FUND (“Units”)'


def test_a_fund_parses_to_nulls_rather_than_zeros():
    """A closed-end fund has no industry sector and no market capitalisation in the
    ordinary sense. Null is the correct answer and the feed gives it; a zero here
    would render as a measurement."""
    row = parse_company_payload('CALC.U0000', FUND_SUMMARY, FUND_PROFILE, REFRESHED)

    assert row['sector'] is None
    assert row['sector_group'] is None
    assert row['market_cap'] is None
    assert row['week52_high'] is None
    assert row['week52_low'] is None
    assert row['beta_asi'] is None
    assert row['beta_sl20'] is None
    assert row['business_summary'] is None
    # But it does have the fields a fund does have.
    assert row['shares_issued'] == 20000000
    assert row['isin'] == 'LK0508U00003'


def test_a_missing_beta_container_does_not_break_the_row():
    """``reqSymbolBetaInfo`` is null for the three unit trusts. ``_first(None)``
    returning None is what keeps this from being an AttributeError on a sweep."""
    row = parse_company_payload('CALC.U0000', FUND_SUMMARY, FUND_PROFILE, REFRESHED)
    assert row is not None
    assert row['beta_period'] is None


def test_a_zero_beta_is_kept_because_zero_is_a_measurement():
    """Unlike a price, a beta of 0 means something -- the security does not track
    the index -- and a negative beta means it moves against it. Only absence is
    None, which is why beta does not go through ``_positive``."""
    summary = {'reqSymbolInfo': {'name': 'X'},
               'reqSymbolBetaInfo': {'triASIBetaValue': 0.0,
                                     'betaValueSPSL': -0.42}}
    row = parse_company_payload('X.N0000', summary, None, REFRESHED)
    assert row['beta_asi'] == 0.0
    assert row['beta_sl20'] == -0.42


def test_boilerplate_in_the_body_is_dropped_but_a_boilerplate_title_is_not():
    """cse.lk stores "Business Summary" or " " in ``title`` while ``body`` holds the
    prose, so checking the title would have dropped all 231 summaries. The guard is
    against the reverse case, where the placeholder is in the body."""
    profile = {'reqComSumInfo': [{'name': 'X'}],
               'infoCompanyBusinessSummary': [{'title': 'Business Summary',
                                               'body': 'Business Summary'}]}
    row = parse_company_payload('X.N0000', {'reqSymbolInfo': {'name': 'X'}},
                                profile, REFRESHED)
    assert row['business_summary'] is None


def test_the_symbol_is_upper_cased_so_one_company_is_one_row():
    """The symbol is the primary key. Without normalising, "jkh.n0000" and
    "JKH.N0000" would be two rows for one company."""
    row = parse_company_payload('  jkh.n0000  ', JKH_SUMMARY, JKH_PROFILE, REFRESHED)
    assert row['symbol'] == 'JKH.N0000'


@pytest.mark.parametrize('symbol', ['', '   ', None, 'X' * 21])
def test_an_unusable_symbol_is_rejected(symbol):
    """21 characters overflows String(20), and an empty symbol identifies nothing.
    Returning None drops that symbol from the sweep rather than failing the write
    for all 291."""
    assert parse_company_payload(symbol, JKH_SUMMARY, JKH_PROFILE, REFRESHED) is None


def test_a_payload_with_no_name_from_either_source_is_rejected():
    """``name`` is the table's only NOT NULL text column, because a row that cannot
    be labelled is useless to every caller. An unknown symbol answers 404 on the
    summary endpoint and 204 on the profile, and this is what turns that into a
    skipped symbol instead of an IntegrityError."""
    assert parse_company_payload('X.N0000', None, None, REFRESHED) is None
    assert parse_company_payload('X.N0000', {'reqSymbolInfo': {}},
                                 {'reqComSumInfo': [{}]}, REFRESHED) is None


def test_a_name_from_only_the_profile_is_enough():
    """Either source can identify the record; only both failing is fatal."""
    row = parse_company_payload('X.N0000', None,
                                {'reqComSumInfo': [{'name': 'ONLY HERE PLC'}]},
                                REFRESHED)
    assert row['name'] == 'ONLY HERE PLC'


def test_the_raw_sector_is_stored_alongside_the_normalised_group():
    """Both columns, deliberately. The raw string is the evidence a mislabelled
    company is diagnosed from; the group is what a filter uses. Storing only the
    group would make a mapping mistake undiagnosable from the database."""
    profile = {'reqComSumInfo': [{'name': 'X',
                                  'sector': 'FOOD BEVERAGE & TOBACCO'}]}
    row = parse_company_payload('X.N0000', {'reqSymbolInfo': {'name': 'X'}},
                                profile, REFRESHED)
    assert row['sector'] == 'FOOD BEVERAGE & TOBACCO'
    assert row['sector_group'] == 'Food, Beverage & Tobacco'


def test_an_unresolvable_sector_keeps_the_raw_string_and_nulls_the_group():
    """TESS AGRO PLC files "Trading", which no source resolves to one industry
    group. The raw string stays -- it is what a future correction is derived from --
    and the group is null so no chip claims the company."""
    profile = {'reqComSumInfo': [{'name': 'TESS AGRO PLC', 'sector': 'Trading'}]}
    row = parse_company_payload('TESS.N0000',
                                {'reqSymbolInfo': {'name': 'TESS AGRO PLC'}},
                                profile, REFRESHED)
    assert row['sector'] == 'Trading'
    assert row['sector_group'] is None


# ── the upsert ──────────────────────────────────────────────────────────────

class RecordingSession:
    """Captures statements without a database."""

    def __init__(self):
        self.statements: list = []

    def execute(self, statement, *a, **kw):
        self.statements.append(statement)
        return SimpleNamespace(rowcount=0, all=lambda: [])

    def commit(self):
        pass


def _sql(statement) -> str:
    """Compile to Postgres SQL. Compiling needs no connection, only executing
    does -- so the dialect-specific clauses can be asserted on offline."""
    return str(statement.compile(dialect=postgresql.dialect()))


def _row(symbol='JKH.N0000', **over):
    row = parse_company_payload(symbol, JKH_SUMMARY, JKH_PROFILE, REFRESHED)
    row.update(over)
    return row


def test_the_upsert_conflicts_on_the_symbol_alone():
    """One row per symbol. Unlike daily_close, this is current state rather than a
    series, so a composite key would accumulate a company's profile once per
    refresh."""
    db = RecordingSession()
    _upsert_latest(db, CompanyInfo, 'symbol', [_row()], guard='refreshed_at')

    sql = _sql(db.statements[0])
    assert 'INSERT INTO company_info' in sql
    assert 'ON CONFLICT (symbol) DO UPDATE' in sql


def test_the_guard_is_refreshed_at_because_the_exchange_publishes_no_clock():
    """cse.lk stamps company data with nothing, so "the later sweep wins" is the
    only ordering available -- and it is what stops a retried task that started
    first from overwriting a newer one."""
    db = RecordingSession()
    _upsert_latest(db, CompanyInfo, 'symbol', [_row()], guard='refreshed_at')

    where = _sql(db.statements[0]).split('WHERE')[1]
    assert 'company_info.refreshed_at <= excluded.refreshed_at' in where


def test_the_symbol_is_never_in_the_set_clause():
    """It is the conflict target. Assigning it to itself is pointless, and
    assigning it from EXCLUDED is how a key gets changed by accident."""
    db = RecordingSession()
    _upsert_latest(db, CompanyInfo, 'symbol', [_row()], guard='refreshed_at')

    set_clause = _sql(db.statements[0]).split('DO UPDATE SET')[1].split('WHERE')[0]
    assert 'symbol = excluded.symbol' not in set_clause
    assert 'sector_group = excluded.sector_group' in set_clause


def test_the_normalised_group_is_written_not_only_the_raw_sector():
    """The column the index and every filter use. Omitting it from the SET clause
    would leave a re-mapped sector frozen at whatever the first sweep decided."""
    db = RecordingSession()
    _upsert_latest(db, CompanyInfo, 'symbol', [_row()], guard='refreshed_at')

    sql = _sql(db.statements[0])
    assert 'sector_group' in sql.split('ON CONFLICT')[0]
