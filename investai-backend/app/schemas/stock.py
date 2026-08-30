from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class MarketDataBase(BaseModel):
    symbol: str
    price: float
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None

class MarketData(MarketDataBase):
    market_id: int
    recorded_at: datetime
    # Joined from company_info, both nullable, both added in I-07.
    #
    # ``name`` closes a bug rather than adding a feature: StockBrowseScreen read
    # ``s.name`` off this payload for its list rows and its search filter, and this
    # schema never had the field — so every row rendered nameless and searching for
    # "John Keells" matched nothing, silently, because an undefined property in JS
    # is not an error. The scraper had been parsing the name from the trade summary
    # all along with nowhere to put it.
    #
    # Null when a symbol has traded but the daily company sweep has not reached it
    # yet, which is the window between a new listing's first quote and that
    # evening's refresh. Clients must render the symbol in that case, not "null".
    name: Optional[str] = None
    # The normalised industry group (``CompanyInfo.sector_group``), not the raw feed
    # string, so a chip's label and the value on a row are the same vocabulary.
    sector: Optional[str] = None

    class Config:
        from_attributes = True

class MarketIndex(BaseModel):
    """A CSE index reading: ASPI, S&P SL20, or one of 20 industry groups.

    ``turnover``, ``volume`` and ``trades`` are null for ASPI and S&P SL20 —
    cse.lk publishes those per industry group only, and reporting 0 would claim
    the headline indices saw no trading.

    ``recorded_at`` is the exchange's own timestamp for the reading, so a client
    can tell a live figure from the previous session's close. It is not the time
    the value was scraped.
    """
    index_code: str
    name: str
    value: float
    change: Optional[float] = None
    change_pct: Optional[float] = None
    previous_close: Optional[float] = None
    turnover: Optional[float] = None
    volume: Optional[float] = None
    trades: Optional[int] = None
    recorded_at: datetime

    class Config:
        from_attributes = True


class DailyClose(BaseModel):
    """One trading day's OHLC for one symbol.

    ``trade_date`` is the date the exchange recorded the trades on, taken from its
    own ``lastTradedTime``, not the date we scraped. The distinction is why this
    table exists: cse.lk keeps serving the last session's numbers while the market
    is shut, so a scrape date would put Tuesday's close on Thursday — and the two
    snapshots in the pre-existing history were stamped a Sunday and a Thursday
    carrying Tuesday.

    ``open``, ``high`` and ``low`` are nullable because they are the exchange's to
    report; a symbol whose only print was its open has no range. ``close`` always
    has a value.
    """
    symbol: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    previous_close: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    trades: Optional[int] = None
    last_traded_at: datetime

    class Config:
        from_attributes = True


class PriceHistory(BaseModel):
    """A symbol's close series, with the honesty fields wrapped around it.

    The count and date bounds are part of the response rather than left for the
    client to infer, because this series is short and will stay short for a while:
    it accumulates one point per trading day from the date the pipeline started
    recording, and there is no CSE endpoint to backfill from. A client that knows
    it has four points can say "4 trading days" instead of drawing four points
    across an axis labelled as a month.

    ``requested_range`` echoes what was asked for so the gap between requested and
    delivered is visible in the payload itself.
    """
    symbol: str
    requested_range: str
    point_count: int
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    points: list[DailyClose]


class CompanyInfo(BaseModel):
    """What a listed company *is*, as opposed to what it traded at today.

    Replaces four fabricated tiles on the stock detail screen, all four of which
    were modulus arithmetic on the live price (``peRatio = 8 + (price % 15)``).

    **There is no ``pe_ratio`` field**, and its absence is deliberate rather than
    pending. cse.lk publishes no EPS, dividend, yield or net-asset figure anywhere
    in either company endpoint — 94 distinct keys were walked to establish that —
    so a P/E cannot be computed from this source at all. The tile is gone from the
    app instead of being backed by a field that would be null for every symbol.

    **There is no ``week52_high``, ``all_time_high`` or ``all_time_low`` either,
    and that one is a data-quality decision rather than a missing source.** All
    three are stored — they are what the exchange publishes and the columns are
    auditable — but none is split-adjusted, and cse.lk restates nothing. Measured
    over every symbol carrying a range: **26** report a 12-month span of 5x or
    more, 13 of 10x or more. Re-measured 2026-08-28 as 26 of 289, having been 26 of
    287 when first taken — the same symbols, against a market that gained two
    listings. MERC publishes 22.0–10,999.0 while trading at 23.0; CPRT
    29.7–4,700.0 at 30.0; COLO 36.3–584.0 at 34.9. On a "52W HIGH" tile beside the
    live price those read as a 99.8% collapse. The only discriminator cse.lk's own
    fields offer (``p12HiPrice == allHiPrice``) catches 16 of 24 known-bad symbols
    and false-positives on 2 of 15 controls — MELS and AEL, both legitimately at
    all-time highs — so there is no rule that suppresses MERC without also
    suppressing a stock at a real high. Serving the field with a caveat in the docs
    does not help: the client renders the number, not the docstring.

    ``week52_low`` **is** served, and the asymmetry is structural rather than luck:
    a forward split inflates old nominal *highs* and cannot inflate a low. No low
    is split-contaminated; the great majority sit within 1–2x of the price and the
    handful above 3x are plausible rallies.

    It does lag the session, though, and by more than an earlier measurement here
    claimed. cse.lk recomputes the bound between sessions, not intraday, so a stock
    printing a new low today is quoted *below* its own published 52-week low until
    the next recalculation. Re-measured 2026-08-28: **9 of 289** symbols are priced
    under their reported low — 8 of them by less than 4%, but CDB by **6.4%**
    (37.40 against a price of 35.00). An earlier draft of this docstring said "all
    under 2.2% out"; that was true when written and is the kind of claim that
    quietly stops being true, so what is stated now is the mechanism and a dated
    measurement rather than a bound.

    This is a lag, not a contradiction, and it is left as the exchange reports it.
    Clamping the low down to the live price would fabricate a bound the exchange
    never published, and suppressing the field would cost every symbol a real
    indicator to spare nine a small inconsistency. A client showing both should not
    assert that the price is inside the range.

    The 52-week high the app does show is derived from I-06's ``daily_close``,
    which is split-consistent by construction because it only ever records prices
    it observed, and which reports its own ``point_count`` so a short series says
    so. Same principle as the P/E decision: nothing invented, nothing rendered
    wrong, nothing dropped from storage.

    What replaces the four fabricated tiles is five real indicators: market cap, a
    52-week low the exchange computes, shares issued, sector, and beta against two
    indices.

    **Almost everything is nullable, and the gaps are a class rather than noise.**
    Three unit trusts (``CALI``/``CALU``/``CALC.U0000``) have no sector, no beta and
    no market cap; ``AMF.N0000`` has no market cap or 52-week range. A closed-end
    fund has no industry sector, so null is the correct answer and cse.lk returns it
    rather than a substitute. Clients must omit a tile whose value is null, not
    render "0" or "—" as though it were a measurement.

    ``refreshed_at`` is our clock, not the exchange's: it publishes no timestamp for
    company data. It is here so a client can say how old a figure is.
    """
    symbol: str
    name: str
    # Both sector columns are returned. ``sector`` is what cse.lk filed, kept in the
    # payload so a mislabelled company is diagnosable from the API alone rather than
    # needing database access; ``sector_group`` is that string normalised onto one of
    # the exchange's 20 industry-group index names and is the one a client should
    # display and filter on. They differ for 86 of the 288 symbols that have a
    # sector, and are null-vs-set for 3 more.
    #
    # ``sector_group`` is null both when there is no sector at all and when the
    # string resolves to no single group; a client cannot distinguish those and does
    # not need to — both mean the sector is unknown, so the tile is omitted.
    sector: Optional[str] = None
    sector_group: Optional[str] = None

    market_cap: Optional[float] = None
    market_cap_pct: Optional[float] = None

    shares_issued: Optional[int] = None
    par_value: Optional[float] = None
    isin: Optional[str] = None

    # The exchange's own 12-month low (``p12LowPrice``), not derived from I-06's
    # daily_close — that series starts at its first scrape, so a real 52-week window
    # from it is 52 weeks away. There is no matching high here; see above.
    week52_low: Optional[float] = None

    # Beta can legitimately be negative or zero, so a client must not treat
    # falsiness as absence here. Only null means "not published".
    beta_asi: Optional[float] = None
    beta_sl20: Optional[float] = None
    beta_period: Optional[str] = None

    board: Optional[str] = None
    established: Optional[str] = None
    website: Optional[str] = None
    business_summary: Optional[str] = None

    refreshed_at: datetime

    class Config:
        from_attributes = True


class SectorSummary(BaseModel):
    """One CSE industry group, with how many listed symbols sit in it.

    Exists so the home and browse screens can build their filter chips from what
    the market actually contains. Both screens hardcoded sectors as ticker-prefix
    arrays — ``['JKH', 'HAYL', 'RICH']`` was "Capital Goods" — which mislabelled
    every company whose ticker did not happen to be listed and silently returned an
    empty list for the rest.

    ``sector`` is ``CompanyInfo.sector_group``, so it matches
    ``MarketIndexLatest.name`` exactly and a client can show "Capital Goods" stocks
    beside the Capital Goods index reading without a second vocabulary. It is
    **not** the raw feed string: grouping on that yields 39 chips for 20 sectors,
    three of them spellings of Food, Beverage & Tobacco, with the correct one
    matching 2 of that sector's 46 companies.

    Six symbols appear in no chip — three unit trusts with no sector and three
    whose sector string resolves to no single group. A "Other (6)" chip would
    imply a sector that does not exist, so the list is 20 real groups and the
    counts deliberately do not sum to the market.
    """
    sector: str
    count: int


class NewsSentimentBase(BaseModel):
    symbol: str
    headline: str
    url: str
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None

class NewsSentiment(NewsSentimentBase):
    """A scraped article, scoped to one company it mentions.

    ``summary`` and ``source`` were stored by the scraper and absent from this
    schema, so no client could ever read them — a news list could show a headline
    and nothing else, and had no way to attribute the story to a publication. The
    reason it was never missed is that ``summary`` was the literal string
    "Editorial :" on all 60 stored rows before I-08, so serving it would only have
    exposed the defect sooner.

    ``body`` is deliberately not exposed. It is the full article text, held so the
    LLM summariser and VADER read what was published; republishing a copyrighted
    story in full through our own API is a different act from linking to it, and
    the client has ``url``.
    """

    news_id: int
    # The LLM's plain-English summary once analyse_sentiment_batch has run, the
    # article's opening 500 characters until then. Null only for a row whose
    # article page could not be fetched — the headline and link are still real.
    summary: Optional[str] = None
    # Publication name ("Daily FT", "EconomyNext"), for provenance on the row.
    source: Optional[str] = None
    # Parsed per source and stored as UTC. Null when the article page was
    # unreachable; a client should fall back to `scraped_at` ordering, not to
    # showing today's date.
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PricePredictionBase(BaseModel):
    symbol: str
    predicted_price: float
    model_version: str

class PricePrediction(PricePredictionBase):
    prediction_id: int
    generated_at: datetime

    class Config:
        from_attributes = True

class ScrapeResponse(BaseModel):
    message: str
    symbol: Optional[str] = None
    saved_count: Optional[int] = None

class SentimentSummary(BaseModel):
    symbol: str
    count: int
    avg_score: float
    label: str
    recent_headlines: list[str]
