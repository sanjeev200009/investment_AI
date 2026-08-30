"""Normalising cse.lk's sector strings onto the exchange's own 20 index names.

**The problem, measured over all 291 symbols.** ``companyProfile`` →
``reqComSumInfo.sector`` returns **39 distinct strings** for a market the same site
publishes **20 industry-group indices** for. The strings disagree with the index
names and with each other::

    Food Beverage & Tobacco              34   index name: "Food, Beverage & Tobacco"
    FOOD BEVERAGE & TOBACCO              10   ... the same sector, shouted
    Food, Beverage & Tobacco              2   ... the same sector, correct
    Real Estate Management & Development 18   index: "Real Estate Management&Development"
    Diversified Financial                 4   index: "Diversified Financials"
    Capital Goods.                        1   trailing period
    Materials (1510)                      1   GICS code appended
    45103010 - Application Software       1   GICS code, sub-industry level
    - Property & Casualty Insurance       1   leading dash, sub-industry level
    Banks Finance & Insurance             2   the pre-2019 CSE sector name
    Trading / Services / Industrials / Power and Energy   1-2 each, also legacy

A filter built on the raw string produces 39 chips, three of which are
Food Beverage & Tobacco, and the correctly-spelled one finds 2 of that sector's 46
companies. **This module exists because I asserted the opposite.** An earlier probe
compared two symbols, found ``JKH`` → "Capital Goods" matching the index name
exactly, and I wrote into three docstrings that the two vocabularies were identical
and no mapping table was needed. Over two symbols that was true. Over 291 it is not.

**The count of distinct strings is not stable, which is the argument in miniature.**
The first full sweep counted 38; the next counted 39, without the market changing
size. cse.lk edits these strings in place, so any number written down here is a
measurement with a date on it rather than a property of the exchange. What is stable
is the 20 published index names, which is why those are what this module maps onto
and why the tests assert the count of *those* rather than the count of raw strings.

**Why a table in code rather than a join.** Three sources of truth were checked
first and none serves membership: ``allSectors`` returns index *readings* with a
numeric ``sectorId`` but no constituents; ``companiesBySector``,
``sectorWiseSummery``, ``indexComposition`` and ``gicsSectors`` are all 404; and the
company payload carries ``securityId`` but no ``sectorId``, so there is nothing to
join the numeric ids against. The mapping is therefore a judgement, which is why it
is written out entry by entry with its basis recorded rather than done with a
regex.

**Two kinds of entry, kept apart on purpose.**

``_GICS_DERIVED`` — the raw string is a GICS code or a sub-industry/industry name,
and the published GICS hierarchy determines its industry group. "Consumer Finance"
is industry 402020, which sits in Diversified Financials; that is a fact about GICS,
not an opinion about the company.

``_COMPANY_DERIVED`` — the raw string is a legacy pre-2019 CSE sector spanning
several GICS groups, and the group was resolved from what the company actually does.
Weaker evidence, so it is labelled as such and covers four symbols.

Anything resolvable by neither is left **unmapped**, and callers get None. Three
symbols land there and that is the right answer for them: "Industrials" is a GICS
*sector* containing Capital Goods, Commercial & Professional Services and
Transportation, so CHRISSWORLD PLC could be in any of the three; and "Trading" reads
like GICS "Trading Companies & Distributors" (Capital Goods) but the company behind
it is TESS AGRO PLC, a seafood processor, which would make that mapping actively
wrong. Guessing to avoid a null would put two companies in sectors they are not in.
"""

# The 20 industry-group index names exactly as market_index_latest stores them,
# which is exactly as cse.lk's allSectors returns them. ASPI and S&P SL20 are
# excluded -- they are market-wide indices, not sectors.
#
# Spelled here rather than read from the database so that normalising does not
# require a populated market_index_latest, and so a rename upstream shows up as a
# failing test rather than as sectors silently ceasing to match.
CANONICAL_SECTORS = (
    "Automobiles & Components",
    "Banks",
    "Capital Goods",
    "Commercial & Professional Services",
    "Consumer Durables & Apparel",
    "Consumer Services",
    "Diversified Financials",
    "Energy",
    "Food & Staples Retailing",
    # Note the comma. cse.lk's index name has it; the sector string usually does
    # not, which is the single biggest source of mismatch (46 symbols).
    "Food, Beverage & Tobacco",
    "Health Care Equipment & Services",
    "Household & Personal Products",
    "Insurance",
    "Materials",
    # Note the absent spaces around the ampersand. This is the index name as
    # published; the sector string spells it with spaces (18 symbols).
    "Real Estate Management&Development",
    "Retailing",
    "Software & Services",
    "Telecommunication Services",
    "Transportation",
    "Utilities",
)

# Raw string -> canonical, where the GICS hierarchy settles it. Keys are matched
# case-insensitively after whitespace and trailing-punctuation normalisation, so
# "FOOD BEVERAGE & TOBACCO" and "Food Beverage & Tobacco" both hit one entry.
_GICS_DERIVED = {
    # --- a spelling difference the loose comparison cannot absorb ---
    # Every other spelling variant in the feed -- "Food Beverage & Tobacco" for
    # "Food, Beverage & Tobacco", "FOOD & STAPLES RETAILING", "HealthCare Equipment
    # & Services", "Real Estate Management & Development" -- differs from the index
    # name only in punctuation, spacing or case, so _loose resolves it and an entry
    # here would be dead weight. A missing plural is a different letter, not
    # punctuation, so this one needs stating.
    "diversified financial": "Diversified Financials",

    # --- GICS code appended or substituted for the name ---
    # 1510 is the Materials industry group; 6010 is Real Estate, whose CSE index is
    # "Real Estate Management&Development".
    "materials (1510)": "Materials",
    "real estate (6010)": "Real Estate Management&Development",
    "45103010 - application software": "Software & Services",
    "application software": "Software & Services",

    # --- a GICS industry or sub-industry, mapped to its own industry group ---
    # Each of these is a level below the index's granularity, so the parent is
    # determined by the GICS hierarchy itself.
    "property & casualty insurance": "Insurance",          # 40301020 -> Insurance
    "multi-line insurance": "Insurance",                   # 40301030 -> Insurance
    "life & health insurance": "Insurance",                # 40301010 -> Insurance
    "insurance brokers": "Insurance",                      # 40301040 -> Insurance
    "consumer finance": "Diversified Financials",          # 402020  -> Div Fin
    "diversified financial services": "Diversified Financials",   # 402010
    "investment banking & brokerage": "Diversified Financials",   # 40203020
    "capital markets": "Diversified Financials",                  # 402030
    "asset management & custody banks": "Diversified Financials",  # 40203010
    "independent power producers & energy traders": "Utilities",   # 551050
    "electric utilities": "Utilities",                            # 551010
    "real estate development": "Real Estate Management&Development",
    "real estate operating companies": "Real Estate Management&Development",
    "trading companies & distributors": "Capital Goods",          # 201070
    "hotels restaurants & leisure": "Consumer Services",          # 253010
    "hotels, restaurants & leisure": "Consumer Services",
}

# Raw string -> canonical, resolved from the company rather than from GICS. These
# are legacy pre-2019 CSE sector names, each of which spanned several of today's
# industry groups, so the string alone cannot settle it. Four symbols. Listed
# separately from the GICS mappings because the evidence is weaker and a reader
# auditing this file should be able to see which entries are which.
_COMPANY_DERIVED = {
    # HNB FINANCE PLC (HNBF.N0000, HNBF.X0000). A licensed finance company, not a
    # licensed commercial bank, so the Banks index is the wrong home; GICS puts
    # deposit-taking finance companies in Diversified Financials, alongside the
    # other LFCs on the exchange.
    "banks finance & insurance": "Diversified Financials",
    # VALLIBEL POWER ERATHNA PLC (VPEL.N0000). A run-of-river hydropower generator,
    # which is the same business as WINDFORCE PLC -- and cse.lk labels that one
    # "Independent Power Producers & Energy Traders", i.e. Utilities. The two
    # strings describe one business.
    "power and energy": "Utilities",
    # MERCANTILE SHIPPING COMPANY PLC (MSL.N0000). A shipping line: GICS Marine
    # Transportation, in the Transportation industry group.
    "services": "Transportation",
}

# Deliberately absent, with the reason, so a future reader does not "fix" it:
#
#   "industrials"  -- CHRISSWORLD PLC (CWL.N0000). Industrials is a GICS *sector*
#                     containing Capital Goods, Commercial & Professional Services
#                     and Transportation. Three candidate groups, no way to choose
#                     from the string, and the company's filings are not in this
#                     feed.
#   "trading"      -- TESS AGRO PLC (TESS.N0000, TESS.X0000). Reads like GICS
#                     "Trading Companies & Distributors" (Capital Goods), but the
#                     company is a seafood processor and exporter, which would be
#                     Food, Beverage & Tobacco. The plausible reading of the string
#                     and the plausible reading of the business disagree, so
#                     neither is used.
_KNOWN_UNMAPPABLE = ("industrials", "trading")

_CANONICAL_BY_KEY = {s.lower(): s for s in CANONICAL_SECTORS}


def _loose(text: str) -> str:
    """The punctuation-blind comparison form of a sector name.

    Drops everything that is not a letter or digit, and drops the standalone word
    "and", so "Food Beverage and Tobacco", "Food, Beverage & Tobacco" and "FOOD
    BEVERAGE & TOBACCO" all reduce to one string.

    Equating "and" with "&" is safe here specifically because no two of the 20
    canonical names differ only by that conjunction -- collapsing it cannot merge
    two real sectors, only two spellings of one. That is checked by a test, so if
    the exchange ever adds a sector where it matters, the collapse fails loudly
    rather than silently misfiling companies.
    """
    words = [w for w in text.lower().split() if w != "and"]
    return "".join(ch for ch in "".join(words) if ch.isalnum())


# The canonical names in comparison form, so a respelling upstream still resolves
# without needing its own table entry.
_CANONICAL_BY_LOOSE = {_loose(s): s for s in CANONICAL_SECTORS}


def _key(raw: str) -> str:
    """The lookup form of a raw sector string.

    Lowercased, collapsed whitespace, and stripped of the leading dashes and
    trailing periods cse.lk sometimes leaves behind ("- Property & Casualty
    Insurance", "Capital Goods."). Not stripped of the ``&``/comma differences --
    those are handled by explicit table entries and by the loose fallback, because
    silently equating "&" and "and" everywhere would be a wider rule than the data
    justifies.
    """
    text = " ".join(str(raw).split()).strip().lower()
    return text.strip(" .-–—")


def canonical_sector(raw: str | None) -> str | None:
    """Map a cse.lk sector string onto one of the 20 CSE industry-group names.

    Returns None for absent input, and for the two legacy strings no source can
    resolve. None means "we do not know which group this is", which is what a
    sector filter must show as absent rather than lumping into an "Other" bucket
    that would look like a real sector.

    Resolution order, most authoritative first:

    1.  Exact match against a canonical name. The 17 sectors cse.lk already spells
        correctly take this path and never touch the table.
    2.  The explicit GICS-derived table.
    3.  The explicit company-derived table.
    4.  A punctuation-insensitive match against the canonical names, which catches
        an upstream respelling ("Food Beverage and Tobacco") without a new entry.
    """
    if raw is None:
        return None
    key = _key(raw)
    if not key:
        return None

    exact = _CANONICAL_BY_KEY.get(key)
    if exact:
        return exact

    mapped = _GICS_DERIVED.get(key) or _COMPANY_DERIVED.get(key)
    if mapped:
        return mapped

    return _CANONICAL_BY_LOOSE.get(_loose(key))
