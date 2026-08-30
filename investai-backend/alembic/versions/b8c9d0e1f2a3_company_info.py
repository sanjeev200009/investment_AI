"""company_info (I-07: real fundamentals)

``StockDetailScreen.js`` displayed four company fundamentals, all four of which
were arithmetic on the current price:

    peRatio  = 8 + (price % 15)
    high52   = price * (1 + (price % 30) / 100)
    low52    = price * (1 - (price % 25) / 100)
    marketCap = 10 + (price % 50) * 2.5   -- rendered with a "B" suffix

Labelled "P/E RATIO", "52W HIGH", "52W LOW" and "MARKET CAP". The modulus is the
tell: the numbers move with the price and are otherwise unrelated to the company,
so two stocks trading at the same price had identical fundamentals and a stock
whose price rose past a multiple of 15 saw its P/E jump discontinuously. Sector
filters on two screens were hardcoded ticker-prefix arrays for the same reason --
nothing stored a sector.

**What cse.lk actually serves.** Two POST endpoints, probed across all 291
symbols in ``market_data_latest``:

* ``companyInfoSummery`` -> ``reqSymbolInfo`` carries ``marketCap`` (287/291),
  ``p12HiPrice``/``p12LowPrice`` -- the real 12-month range (287/291) --
  ``allHiPrice``/``allLowPrice``, ``quantityIssued`` (290/291), ``isin``,
  ``parValue`` and ``name`` (291/291); ``reqSymbolBetaInfo`` carries beta against
  both the ASI and S&P SL20 (288/291).
* ``companyProfile`` -> ``reqComSumInfo`` carries ``sector`` (288/291),
  ``boardType``, ``established`` and ``web``; ``infoCompanyBusinessSummary``
  carries a prose description (231/291).

**Two sector columns, because the feed's sector string is not a category.** Those
288 sectors are **39 distinct strings** for a market cse.lk itself publishes 20
industry-group indices for: "Food Beverage & Tobacco" (34), "FOOD BEVERAGE &
TOBACCO" (10) and "Food, Beverage & Tobacco" (2) are one sector typed three ways,
and "Materials (1510)", "- Property & Casualty Insurance" and "Banks Finance &
Insurance" are a GICS code, a sub-industry and a pre-2019 CSE sector name. A chip
list built on the raw string shows 39 chips and the correctly-spelled Food
chip finds 2 of that sector's 46 companies. So ``sector`` stores the feed
verbatim -- auditable, and the place a future correction gets diffed against --
and ``sector_group`` stores it normalised onto the exchange's own 20 index names
by ``app.services.sectors``. The index is on ``sector_group``, because that is
the column anything filters by. 288 raw strings collapse to 20 groups; 3 symbols
(CWL, TESS x2) are left with a null group on purpose, documented there.

The four symbols missing market cap and the 12-month range are ``CALI.U0000``,
``CALU.U0000``, ``CALC.U0000`` and ``AMF.N0000`` -- three unit trusts and a fund.
The three ``.U0000`` units are also the ones missing sector and beta. That is a
coherent class rather than random gaps: a closed-end fund has no industry sector
and no market capitalisation in the ordinary sense. So every numeric column here
is nullable, and the API returns null rather than a substitute.

**No P/E ratio column, and no EPS.** 94 distinct keys were walked across both
endpoints at every nesting depth; none is an earnings, dividend, yield or net
asset value figure. P/E cannot be computed without EPS, EPS is not published
here, and the only remaining source would be parsing annual-report PDFs. The tile
is therefore removed from the app rather than given a column to be null in. This
is the deliberate answer to the remediation plan's question, and it follows its
own recommendation: three real numbers beat six invented ones. It is worth being
precise about what is lost -- a genuine valuation multiple -- and what is gained:
market cap, a real 52-week range, shares issued, sector and beta against two
indices, which is five real indicators where there were four fake ones.

**Refreshed wholesale, not per request.** A full sweep is two POSTs per symbol
and all 291 measured 7.8 seconds at concurrency 6. It is a daily Celery task
rather than a read-through cache: company fundamentals change on corporate-action
timescales, and a per-request fetch would put a third-party round trip on the
critical path of a screen that already loads a price and a chart.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_info",
        # The full CSE symbol including the class suffix (JKH.N0000), so this
        # joins market_data_latest directly. reqComSumInfo also returns a bare
        # "JKH", which is deliberately not used as the key -- it is not unique
        # across a company's share classes.
        sa.Column("symbol", sa.String(20), primary_key=True),

        # 291/291. NOT NULL because a record with no company name identifies
        # nothing, and a row that cannot be labelled is worse than an absent one.
        sa.Column("name", sa.String(200), nullable=False),

        # The sector string exactly as cse.lk filed it, unnormalised: "Food
        # Beverage & Tobacco", "FOOD BEVERAGE & TOBACCO", "Materials (1510)",
        # "- Property & Casualty Insurance". Kept verbatim because it is the raw
        # evidence -- when the normalisation below is wrong, this is what proves
        # it, and re-deriving groups from a corrected table needs the input.
        # Nothing filters on this column. Null for the three unit trusts.
        sa.Column("sector", sa.String(80), nullable=True),

        # `sector` folded onto one of the exchange's 20 industry-group index names
        # by app.services.sectors.canonical_sector, so a sector filter and its
        # index reading are the same string -- which is what makes "show me
        # Capital Goods stocks and the Capital Goods index" one coherent view
        # rather than two vocabularies.
        #
        # Null in two distinct cases the API must not conflate: the feed gave no
        # sector at all (3 unit trusts), or it gave one that no source can resolve
        # to a single group (3 symbols -- "Industrials" is a GICS *sector*
        # spanning three groups; "Trading" names a company that is a seafood
        # processor). Both mean "unknown group", so both are excluded from the
        # chip list rather than bucketed into an "Other" that would read as real.
        sa.Column("sector_group", sa.String(80), nullable=True),

        # Rs., absolute. JKH's is 351,256,216,014 -- ~3.5e11, well inside a
        # double's exact-integer range (2^53), so Float is safe here and matches
        # market_data.market_cap's type rather than introducing a second one.
        sa.Column("market_cap", sa.Float(), nullable=True),
        # Fraction of total market capitalisation, as cse.lk reports it (4.55 for
        # JKH, i.e. percent not ratio).
        sa.Column("market_cap_pct", sa.Float(), nullable=True),

        # quantityIssued. BigInteger, not Integer: JKH has 17,740,212,930 shares
        # issued, which overflows int32 by three orders of magnitude.
        sa.Column("shares_issued", sa.BigInteger(), nullable=True),
        sa.Column("par_value", sa.Float(), nullable=True),
        sa.Column("isin", sa.String(20), nullable=True),

        # p12HiPrice / p12LowPrice -- the exchange's own 12-month range. Named
        # week52 because that is what the UI calls it and what an investor
        # recognises; the docstring is where the provenance lives.
        #
        # These are why I-06's daily_close is not the source. daily_close starts
        # accumulating from its first scrape, so a real 52-week range from it is
        # 52 weeks away. cse.lk has one today.
        sa.Column("week52_high", sa.Float(), nullable=True),
        sa.Column("week52_low", sa.Float(), nullable=True),
        sa.Column("all_time_high", sa.Float(), nullable=True),
        sa.Column("all_time_low", sa.Float(), nullable=True),

        # Beta against the Total Return ASI and against S&P SL20. Kept because
        # this is an app that assigns users a risk profile: beta is the one
        # published number that speaks to how much a holding amplifies market
        # movement, which is exactly what a risk-matched recommendation needs.
        sa.Column("beta_asi", sa.Float(), nullable=True),
        sa.Column("beta_sl20", sa.Float(), nullable=True),
        # The period the beta was computed over ("2026", quarter 1). Stored so a
        # displayed beta can say how old it is instead of implying it is live.
        sa.Column("beta_period", sa.String(20), nullable=True),

        sa.Column("board", sa.String(40), nullable=True),
        sa.Column("established", sa.String(20), nullable=True),
        sa.Column("website", sa.String(300), nullable=True),
        # Text, not a bounded String: these run to several hundred words and
        # truncating a business description mid-sentence to fit a column is the
        # kind of silent corruption that only shows up in the UI.
        sa.Column("business_summary", sa.Text(), nullable=True),

        # Our clock, not the exchange's -- cse.lk publishes no timestamp for
        # company data. This is the no-backwards guard column for the upsert and
        # the basis of any staleness claim the UI makes.
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Sector is a filter, not a lookup key: "every stock in Banking" scans this.
    # On sector_group rather than sector, because the raw string is never filtered
    # on -- indexing it would cost writes to serve no query.
    #
    # Partial on NOT NULL: the six symbols with no resolvable group are never a
    # filter target, so an index entry for them would only ever be scanned past.
    op.create_index("ix_company_info_sector_group", "company_info",
                    ["sector_group"],
                    postgresql_where=sa.text("sector_group IS NOT NULL"))


def downgrade() -> None:
    # Safely reversible, unlike a7b8c9d0e1f2's. Every column here is re-fetchable
    # from cse.lk in about 8 seconds, because company fundamentals are current
    # state rather than a series -- there is no accumulated history to lose.
    op.drop_index("ix_company_info_sector_group", table_name="company_info")
    op.drop_table("company_info")
