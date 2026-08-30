"""Company fundamentals from cse.lk, for I-07.

The stock detail screen showed four "fundamentals" that were modulus arithmetic on
the live price::

    peRatio   = 8 + (price % 15)
    high52    = price * (1 + (price % 30) / 100)
    low52     = price * (1 - (price % 25) / 100)
    marketCap = 10 + (price % 50) * 2.5      # displayed with a "B" suffix

This module replaces them with what the exchange publishes.

**Two endpoints, both POST with a ``symbol`` form field.** Neither is documented;
both were found in cse.lk's own network traffic and then probed across all 291
symbols in ``market_data_latest`` before this was written.

``companyInfoSummery`` returns four keys, two of which matter:

* ``reqSymbolInfo`` — ``marketCap``, ``marketCapPercentage``, ``quantityIssued``,
  ``isin``, ``parValue``, ``name``, and the price ranges: ``p12HiPrice`` /
  ``p12LowPrice`` (12 months), ``allHiPrice`` / ``allLowPrice`` (all time), plus
  YTD, MTD and WTD ranges that are not stored — a 52-week range is a recognised
  investor reference point and four overlapping windows on one tile is noise.
* ``reqSymbolBetaInfo`` — ``triASIBetaValue``, ``betaValueSPSL`` and the period.

``companyProfile`` returns nine, two of which matter:

* ``reqComSumInfo`` — ``sector``, ``boardType``, ``established``, ``web``, and
  contact details that are not stored: an investment adviser has no use for a
  company's fax number.
* ``infoCompanyBusinessSummary`` — prose describing the business.

Both wrap their records inconsistently: ``companyInfoSummery`` returns bare
objects, ``companyProfile`` returns one-element lists. ``_first`` normalises that
rather than the call sites each remembering which is which.

**No P/E and no EPS.** 94 distinct keys were walked across both payloads at every
nesting depth; not one is an earnings, dividend, yield or net-asset figure. So
there is no ``pe_ratio`` here and the tile is gone from the app. Computing one
from an assumed EPS would be the original bug with extra steps.

**The sector string needs normalising, and ``app.services.sectors`` does it.** The
288 populated values are 39 distinct strings for 20 industry groups. That module's
docstring carries the measurement and the reasoning; this one stores both the raw
string and the normalised group.

**``week52_high`` is parsed and stored but not served.** 26 of 287 symbols publish
a 12-month high from before a forward split, which the exchange never restated —
MERC's range is 22.0–10,999.0 against a price of 22.7 — and no field cse.lk serves
distinguishes those from a symbol genuinely at a 12-month high. ``week52_low`` is
clean, structurally so: a split inflates old nominal highs and cannot inflate a
low. See ``app/schemas/stock.py`` for what that means for the response.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models.stock import CompanyInfo, MarketDataLatest
from app.services.scraper import (CSE_HEADERS, _opt_float, _opt_int,
                                  _upsert_latest)
from app.services.sectors import canonical_sector

logger = logging.getLogger(__name__)

CSE_COMPANY_SUMMARY_URL = "https://www.cse.lk/api/companyInfoSummery"
CSE_COMPANY_PROFILE_URL = "https://www.cse.lk/api/companyProfile"

# How many symbols to have in flight. Capped low deliberately: this hits an
# undocumented endpoint on a public exchange site, and 6 in flight is polite where
# 50 would look like a scraper worth blocking. It is not set for speed -- at 6 the
# whole 291-symbol market sweeps in 7.8s, or 0.027s per symbol against 0.12s
# serially, and nothing waits on this task.
CONCURRENCY = 6

# Longer than the 25s the probe used. A company sweep is not on any request path,
# so a slow response is better waited out than retried.
TIMEOUT = 30

# cse.lk returns the description with the boilerplate title "Business Summary", or
# sometimes a single space, or the company's own name. None of those is a summary.
_JUNK_SUMMARY_TITLES = {"", " ", "business summary"}


def _first(value):
    """Unwrap ``companyProfile``'s one-element list wrappers.

    ``companyInfoSummery`` returns ``{...}`` where ``companyProfile`` returns
    ``[{...}]`` for the same kind of record. Returns None for an empty list rather
    than raising, since an empty ``infoCompanyKeyExecutive`` is normal.
    """
    if isinstance(value, list):
        return value[0] if value else None
    return value if isinstance(value, dict) else None


def _clean(value, limit=None):
    """A stripped non-empty string, or None.

    cse.lk uses several spellings of "no value": absent, null, "", and a single
    space (``infoCompanyBusinessSummary.title`` is " " for JKH). All become None,
    so a caller never has to test for three of them.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit] if limit else text


def _positive(value):
    """A float that is greater than zero, or None.

    Prices and market caps are the fields this guards. Zero is not a low price
    here, it is the feed's way of saying it has no figure -- and a zero 52-week
    low would drag a range chart's axis to the origin and make every stock look
    like it had crashed at some point in the last year.
    """
    number = _opt_float(value)
    return number if number is not None and number > 0 else None


def _website(value):
    """A tappable URL, or None.

    cse.lk stores whatever the company filed, and the three spellings are all
    present in one four-symbol sample: ``https://www.cal.lk/``, ``www.hnb.lk``,
    ``www.keells.com``. Two of those three fail outright in
    ``Linking.openURL`` on Android, which requires a scheme, so the scheme is
    added here rather than in each of the places that might render a link.

    ``https`` rather than ``http``: a listed company's site supports TLS, and if
    one does not the redirect is the site's problem rather than ours to guess at.
    """
    url = _clean(value, 300)
    if url is None:
        return None
    lowered = url.lower()
    if lowered.startswith(("http://", "https://")):
        return url
    # A bare "mailto:" or "ftp:" is not a website. Anything with a scheme we do not
    # recognise is dropped rather than turned into https://mailto:x, which would be
    # a broken link presented as a working one.
    if "://" in url or url.startswith("mailto:"):
        return None
    return f"https://{url}"[:300]


def parse_company_payload(symbol: str, summary: dict | None,
                          profile: dict | None,
                          refreshed_at: datetime) -> dict | None:
    """Fold both endpoints' payloads into one ``company_info`` row.

    Returns None when the record cannot be identified -- no symbol, or no name
    from either source. ``name`` is the table's only NOT NULL text column because
    a row that cannot be labelled is useless to every caller; everything else is
    nullable and genuinely null for some symbols.

    Every numeric field is coerced defensively rather than trusted. The feed is
    not typed: ``quantityIssued`` arrives as an int, ``tdyTradeVolume`` as a float
    that counts discrete trades, and any of them can be null.
    """
    code = (symbol or "").strip().upper()
    if not code or len(code) > 20:
        return None

    info = _first((summary or {}).get("reqSymbolInfo")) or {}
    beta = _first((summary or {}).get("reqSymbolBetaInfo")) or {}
    company = _first((profile or {}).get("reqComSumInfo")) or {}
    about = _first((profile or {}).get("infoCompanyBusinessSummary")) or {}

    # reqSymbolInfo is the better source -- it is the security's own record, where
    # reqComSumInfo names the issuing company and for a unit trust those differ.
    name = _clean(info.get("name"), 200) or _clean(company.get("name"), 200)
    if not name:
        return None

    summary_text = _clean(about.get("body"))
    # The title is checked, not the body: cse.lk stores the placeholder in `title`
    # ("Business Summary" or " ") while `body` holds real prose, so a summary is
    # dropped only when the body itself is empty. Kept as a guard against the
    # reverse case, where the boilerplate has been pasted into the body.
    if summary_text and summary_text.strip().lower() in _JUNK_SUMMARY_TITLES:
        summary_text = None

    raw_sector = _clean(company.get("sector"), 80)

    return {
        "symbol": code,
        "name": name,
        "sector": raw_sector,
        # Normalised at write time, not read time. Two reasons: a sector filter
        # becomes an indexed equality instead of 291 function calls per request,
        # and storing both makes a mapping change visible as a diff on this column
        # rather than as a silent shift in what a chip returns.
        "sector_group": canonical_sector(raw_sector),

        "market_cap": _positive(info.get("marketCap")),
        "market_cap_pct": _opt_float(info.get("marketCapPercentage")),

        "shares_issued": _opt_int(info.get("quantityIssued")),
        "par_value": _positive(info.get("parValue")),
        "isin": _clean(info.get("isin"), 20),

        # p12* is the exchange's 12-month range. Named week52 for the UI.
        "week52_high": _positive(info.get("p12HiPrice")),
        "week52_low": _positive(info.get("p12LowPrice")),
        # Stored, but **not split-adjusted**, and nothing should build a tile on it
        # without saying so. JKH's allHiPrice is 430.25 against a close of 19.80 and
        # a 12-month range of 17.80-23.90 -- a pre-split price the exchange has
        # never restated. Shown next to today's price it reads as a 95% crash.
        "all_time_high": _positive(info.get("allHiPrice")),
        "all_time_low": _positive(info.get("allLowPrice")),

        # Not _positive: a beta below zero is meaningful -- it says the security
        # moves against the index -- and a beta of exactly 0 says it does not
        # track the index at all. Only absence is None.
        "beta_asi": _opt_float(beta.get("triASIBetaValue")),
        "beta_sl20": _opt_float(beta.get("betaValueSPSL")),
        "beta_period": _clean(beta.get("triASIBetaPeriod"), 20),

        "board": _clean(company.get("boardType"), 40),
        "established": _clean(company.get("established"), 20),
        "website": _website(company.get("web")),
        "business_summary": summary_text,

        "refreshed_at": refreshed_at,
    }


async def _fetch_one(client: httpx.AsyncClient, url: str, symbol: str) -> dict | None:
    """One POST, returning the parsed body or None. Never raises.

    A sweep of 291 symbols will meet a timeout or a 500 eventually, and one
    symbol's failure must cost only that symbol. The caller distinguishes "no data
    for this symbol" from "the whole sweep failed" by counting.
    """
    try:
        response = await client.post(url, data={"symbol": symbol},
                                     headers=CSE_HEADERS, timeout=TIMEOUT)
    except Exception as exc:                                     # noqa: BLE001
        logger.debug("company fetch %s %s failed: %s", url, symbol, exc)
        return None
    if response.status_code != 200:
        logger.debug("company fetch %s %s -> HTTP %s", url, symbol,
                     response.status_code)
        return None
    try:
        body = response.json()
    except ValueError:
        logger.debug("company fetch %s %s returned non-JSON", url, symbol)
        return None
    return body if isinstance(body, dict) else None


async def fetch_company_info(symbols: list[str],
                             now: datetime | None = None) -> list[dict]:
    """Fetch and parse both payloads for every symbol.

    Returns one dict per symbol that answered with an identifiable record. A
    symbol whose endpoints both fail is omitted rather than represented by a row
    of nulls -- ``company_info`` is a cache of what the exchange says, and an
    all-null row would overwrite a good earlier refresh with nothing.

    ``refreshed_at`` is taken **once** for the whole sweep, not per symbol. Same
    reasoning as I-04's ``recorded_at``: it makes "this refresh" a single
    identifiable thing, so a query can tell which symbols a given sweep touched.
    A sweep takes about 8 seconds, so per-symbol timestamps would spread across it
    for no gain.
    """
    refreshed_at = now or datetime.now(timezone.utc)
    gate = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def one(symbol: str):
            async with gate:
                summary, profile = await asyncio.gather(
                    _fetch_one(client, CSE_COMPANY_SUMMARY_URL, symbol),
                    _fetch_one(client, CSE_COMPANY_PROFILE_URL, symbol))
            if summary is None and profile is None:
                return None
            return parse_company_payload(symbol, summary, profile, refreshed_at)

        results = await asyncio.gather(*(one(s) for s in symbols))

    return [r for r in results if r is not None]


def known_symbols(db: Session) -> list[str]:
    """The symbols worth refreshing: whatever the last scrape saw.

    Driven off ``market_data_latest`` rather than a hardcoded list or
    ``company_info`` itself. A new listing appears in the trade summary first, so
    reading the price table is what lets fundamentals follow the market instead of
    needing a second place to register a symbol. Ordered so a partial sweep is
    reproducible.
    """
    return [r[0] for r in
            db.query(MarketDataLatest.symbol)
              .order_by(MarketDataLatest.symbol).all()]


async def refresh_company_info(db: Session, symbols: list[str] | None = None,
                               now: datetime | None = None) -> int:
    """Refresh ``company_info`` for ``symbols``, or for the whole market.

    Returns rows upserted. Commits -- unlike the scrape path, there is no second
    table that has to move in the same transaction, and a sweep that fetched 291
    symbols should not lose all of them because the 292nd request timed out.

    The upsert reuses the scrape path's helper, with ``refreshed_at`` as the
    no-backwards guard. That column is our clock rather than the exchange's, which
    is the right guard here for the opposite reason to ``daily_close``'s: cse.lk
    publishes no timestamp for company data, so "later sweep wins" is the only
    ordering available, and a retried task that started before a newer one must
    not overwrite it.
    """
    targets = symbols if symbols is not None else known_symbols(db)
    if not targets:
        logger.info("company_info refresh: no symbols to refresh")
        return 0

    rows = await fetch_company_info(targets, now=now)
    if not rows:
        logger.warning("company_info refresh: %d symbols requested, none "
                       "answered -- leaving the table untouched", len(targets))
        return 0

    # Dedupe by symbol before the upsert, for the same reason `_latest_payload`
    # does: `ON CONFLICT DO UPDATE` cannot touch the same target row twice in one
    # statement. `known_symbols` cannot produce duplicates -- it reads a primary
    # key -- but a caller passing an explicit list can, and casing is normalised
    # during parsing so "jkh.n0000" and "JKH.N0000" collapse to one key here even
    # though they were two distinct requests.
    deduped = {r["symbol"]: r for r in rows}

    written = _upsert_latest(db, CompanyInfo, "symbol", list(deduped.values()),
                             guard="refreshed_at")
    db.commit()

    missing = len(targets) - len(deduped)
    with_sector = sum(1 for r in deduped.values() if r["sector"])
    # Logged separately from with_sector so the gap between them is visible: a
    # symbol with a sector string but no group is one cse.lk started spelling a new
    # way, and that shows up here as the two counts diverging rather than as a chip
    # quietly losing a company.
    with_group = sum(1 for r in deduped.values() if r["sector_group"])
    unmapped = sorted(r["sector"] for r in deduped.values()
                      if r["sector"] and not r["sector_group"])
    logger.info("company_info refresh: %d/%d symbols stored (%d no answer), "
                "%d with a sector, %d resolved to a group", written, len(targets),
                missing, with_sector, with_group)
    if unmapped:
        logger.warning("company_info refresh: %d sector strings did not resolve "
                       "to an industry group: %s", len(unmapped),
                       sorted(set(unmapped)))
    return written
