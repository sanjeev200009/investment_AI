# tests/test_sectors.py
"""Tests for I-07's sector normalisation.

``app/services/sectors.py`` exists because cse.lk's ``reqComSumInfo.sector``
returns **39 distinct strings** for a market the same site publishes 20
industry-group indices for: "Food Beverage & Tobacco" (34 symbols), "FOOD BEVERAGE
& TOBACCO" (10) and "Food, Beverage & Tobacco" (2) are one sector typed three
ways. Filtering on the raw string gives 39 chips and the correctly-spelled Food
chip finds 2 of that sector's 46 companies.

The load-bearing test here is not any individual mapping — it is
``test_every_mapping_lands_on_a_canonical_name``. A table of hand-written string
pairs rots by typo: one entry reading "Diversified Financial**s** Services" ->
"Diversified Financial" silently creates a 21st sector that no index matches and
no chip in the UI corresponds to, and nothing at runtime would notice. That test
makes a typo in either column a failure at collection time.

Offline, no database, no HTTP — the whole module is pure string mapping, which is
deliberate: the judgement calls are auditable in a diff rather than buried in a
query. ``scripts/verify_i07.py`` is where the live half is checked, that the 291
real strings actually resolve and that the six unresolved ones are the six
documented symbols.
"""

import pytest

from app.services.sectors import (CANONICAL_SECTORS, _COMPANY_DERIVED,
                                  _GICS_DERIVED, _KNOWN_UNMAPPABLE, _key,
                                  _loose, canonical_sector)


# ── the table's own integrity ────────────────────────────────────────────────

def test_every_mapping_lands_on_a_canonical_name():
    """The right-hand side of every entry must be one of the 20 index names.

    A typo here would invent a sector: "Diversified Financial" instead of
    "Diversified Financials" produces a chip that matches no index reading and no
    other company, and it would look like a real sector with one member in it.
    """
    for table, label in ((_GICS_DERIVED, '_GICS_DERIVED'),
                         (_COMPANY_DERIVED, '_COMPANY_DERIVED')):
        for raw, mapped in table.items():
            assert mapped in CANONICAL_SECTORS, (
                f'{label}[{raw!r}] -> {mapped!r} is not a CSE index name')


def test_every_table_key_is_already_in_lookup_form():
    """Keys are matched after ``_key`` normalisation, so a key that ``_key`` would
    change is dead — it can never be hit. An entry added as "Consumer Finance"
    rather than "consumer finance" would silently do nothing."""
    for table, label in ((_GICS_DERIVED, '_GICS_DERIVED'),
                         (_COMPANY_DERIVED, '_COMPANY_DERIVED')):
        for raw in table:
            assert _key(raw) == raw, f'{label} key {raw!r} is unreachable'


def test_the_two_tables_do_not_overlap():
    """The split exists so a reader can tell GICS-derived mappings from
    judgement-derived ones. A key in both makes the weaker table's entry dead code
    and the distinction meaningless."""
    assert not set(_GICS_DERIVED) & set(_COMPANY_DERIVED)


def test_the_unmappable_strings_are_not_in_either_table():
    """These two are documented as deliberately unresolved. An entry for one would
    contradict the documentation while looking like a fix."""
    for raw in _KNOWN_UNMAPPABLE:
        assert raw not in _GICS_DERIVED
        assert raw not in _COMPANY_DERIVED


def test_there_are_exactly_twenty_canonical_sectors():
    """The CSE publishes 20 industry-group indices plus ASPI and S&P SL20. If this
    count changes, the market changed and the table needs revisiting — better a
    failing test than a chip list quietly missing a sector."""
    assert len(CANONICAL_SECTORS) == 20
    assert len(set(CANONICAL_SECTORS)) == 20


def test_no_two_canonical_names_collide_under_loose_comparison():
    """The property the punctuation-blind fallback rests on.

    ``_loose`` drops punctuation and the word "and", so two sectors whose names
    differed only by those would become indistinguishable and one would silently
    absorb the other's companies. That is not true of today's 20 names, and this
    test is what makes it fail loudly rather than quietly if the exchange adds a
    sector where it stops being true.
    """
    reduced = [_loose(name) for name in CANONICAL_SECTORS]
    assert len(set(reduced)) == len(CANONICAL_SECTORS)


# ── resolution ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('name', CANONICAL_SECTORS)
def test_every_canonical_name_round_trips(name):
    """The 17 sectors cse.lk already spells correctly must pass through untouched
    and never need a table entry."""
    assert canonical_sector(name) == name


@pytest.mark.parametrize('raw,expected', [
    # The three spellings of one sector, which is 46 of 291 symbols.
    ('Food Beverage & Tobacco', 'Food, Beverage & Tobacco'),
    ('FOOD BEVERAGE & TOBACCO', 'Food, Beverage & Tobacco'),
    ('Food, Beverage & Tobacco', 'Food, Beverage & Tobacco'),
    # The ampersand-spacing difference, 18 symbols.
    ('Real Estate Management & Development', 'Real Estate Management&Development'),
    # A missing plural, 4 symbols.
    ('Diversified Financial', 'Diversified Financials'),
    # A GICS code appended, and one substituted for the name entirely.
    ('Materials (1510)', 'Materials'),
    ('Real Estate (6010)', 'Real Estate Management&Development'),
    ('45103010 - Application Software', 'Software & Services'),
    # Sub-industry names, one level below the index's granularity.
    ('- Property & Casualty Insurance', 'Insurance'),
    ('Multi-line Insurance', 'Insurance'),
    ('Consumer Finance', 'Diversified Financials'),
    ('Investment Banking & Brokerage', 'Diversified Financials'),
    ('Independent Power Producers & Energy Traders', 'Utilities'),
    # Legacy pre-2019 CSE sector names.
    ('Banks Finance & Insurance', 'Diversified Financials'),
    ('Power and Energy', 'Utilities'),
    ('Services', 'Transportation'),
    # Trailing punctuation and a case difference.
    ('Capital Goods.', 'Capital Goods'),
    ('FOOD & STAPLES RETAILING', 'Food & Staples Retailing'),
    ('HealthCare Equipment & Services', 'Health Care Equipment & Services'),
])
def test_the_real_strings_from_the_feed_resolve(raw, expected):
    """Every case in this list was observed in the live 291-symbol sweep. They are
    parametrised rather than asserted in a loop so a regression names the string
    that broke."""
    assert canonical_sector(raw) == expected


@pytest.mark.parametrize('raw', ['Industrials', 'INDUSTRIALS', 'industrials',
                                 'Trading', 'trading', ' Trading '])
def test_the_unresolvable_strings_stay_unresolved(raw):
    """None, not a guess.

    "Industrials" is a GICS *sector* spanning Capital Goods, Commercial &
    Professional Services and Transportation, so CHRISSWORLD PLC could be in any of
    three groups. "Trading" reads like GICS "Trading Companies & Distributors"
    (Capital Goods) but belongs to TESS AGRO PLC, a seafood processor — the string
    and the business disagree. Mapping either to avoid a null would put a company
    in a sector it is not in, which is the class of defect I-07 exists to remove.
    """
    assert canonical_sector(raw) is None


def test_absence_and_emptiness_are_none_not_a_crash():
    """The feed spells "no sector" four ways, and three unit trusts use them."""
    assert canonical_sector(None) is None
    assert canonical_sector('') is None
    assert canonical_sector('   ') is None
    assert canonical_sector('-') is None


@pytest.mark.parametrize('raw', ['  capital   goods  ', 'CAPITAL GOODS',
                                 'Capital Goods...', '- Capital Goods'])
def test_case_whitespace_and_stray_punctuation_do_not_defeat_a_match(raw):
    """cse.lk's strings arrive with collapsed-whitespace, casing and leading-dash
    variation across symbols. All of it is noise around the same sector."""
    assert canonical_sector(raw) == 'Capital Goods'


def test_the_loose_fallback_handles_a_respelling_without_a_new_entry():
    """A punctuation-only change upstream must not silently drop a sector.

    "Food Beverage and Tobacco" is not in either table; it resolves because the
    alphanumeric-only comparison against the canonical names catches it. This is
    the safety net that keeps a cse.lk edit from emptying a chip.
    """
    assert canonical_sector('Food Beverage and Tobacco') == 'Food, Beverage & Tobacco'
    assert canonical_sector('Real-Estate/Management&Development') == \
        'Real Estate Management&Development'


def test_the_fallback_does_not_match_a_substring():
    """Loose matching compares whole normalised strings, not prefixes. "Bank" must
    not become "Banks" and "Energy Services" must not become "Energy" — a filter
    that over-matches puts companies in the wrong sector as surely as one that
    under-matches."""
    assert canonical_sector('Bank') is None
    assert canonical_sector('Energy Services') is None
    assert canonical_sector('Retail') is None
