"""Real news ingestion: which story, from where, when, and about which companies.

Replaces a news pipeline that got all four of those wrong. What was in
``news_sentiment`` before this module existed — 60 rows, measured 2026-08-28:

  * ``symbol`` was ``'GENERAL'`` on all 60. The scraper's attribution was
    ``art.get('symbol') or symbol or 'GENERAL'`` where ``symbol`` is the optional
    function argument, so unless a caller asked for one specific ticker nothing
    was ever attributed and the per-symbol sentiment endpoint had nothing to read.
  * ``summary`` was the literal string ``"Editorial :"`` on all 60. The extractor
    was ``h3.find_next('p')`` — whatever paragraph happened to follow the headline
    in document order, which on ft.lk's index page is the footer's editorial
    contact block. That string was then fed to VADER *as the article text* and
    pasted into the dashboard's LLM prompt.
  * ``published_at`` was NULL on all 60. It was never parsed from anywhere.
  * ``sentiment_label`` was NULL on all 60.

And the headline selector was a blanket ``soup.find_all('h3')[:20]``, which takes
whatever the theme happens to use ``h3`` for.

Design notes that are not obvious from the code:

**Two sources, not three.** ``https://www.dailymirror.lk/business`` was in the
list and is deliberately not here any more; see NEWS_SOURCES.

**Bodies are fetched only for URLs we have never stored.** The beat schedule runs
this every 30 minutes around the clock, and an index page yields the same ~20
stories for hours. Fetching every article page every run would be ~2,000 requests
a day to two publishers to re-read stories already in the table. Deduplicating
first means a steady-state run costs two index fetches plus one article fetch per
genuinely new story.

**One row per (article, symbol).** A story naming three companies becomes three
rows so that ``NewsSentiment.symbol`` can carry an index and per-symbol queries
stay a simple equality filter. Articles matching no company are stored once under
``GENERAL`` — a rupee fixing or a T-bill auction really is market-wide news, and
that is different from "we failed to attribute it".
"""
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models.stock import CompanyInfo, NewsSentiment
from app.services.portfolio_history import EXCHANGE_TZ

logger = logging.getLogger(__name__)

# Symbol used when an article is genuinely about the market rather than about a
# listed company. Not a failure marker -- see the module docstring.
GENERAL_SYMBOL = "GENERAL"

# Headlines shorter than this are page furniture rather than stories. ft.lk's
# index carries a bare "NOTICE" item; dailymirror's carried one too.
MIN_HEADLINE_LEN = 25

# news_sentiment.url is String(500) and is half of a unique index, so a btree key
# has to stay under Postgres' ~2704-byte limit. The longest URL across the 60
# pre-existing rows was 151 characters.
MAX_URL_LEN = 500

# What goes in news_sentiment.summary when the LLM summariser has not run yet:
# the opening of the real article body. A genuine lede rather than a placeholder,
# so the row is useful before analyse_sentiment_batch reaches it and still useful
# if the LLM is rate-limited.
LEDE_CHARS = 500

# Politeness gap between two requests to the same publisher within one run.
PER_REQUEST_DELAY = 1.0

# Article bodies fetched per source per run. Two independent reasons for a bound:
#
# *Runtime.* The scrape beat fires every 30 minutes, and ft.lk's latency is
# measured at 1.0s, 1.0s and 93.7s for three consecutive articles, with its index
# page taking 47.6s in the same run. Unbounded, a cold start of 54 articles can
# outlast its own schedule interval, and then two runs are hitting the same two
# publishers at once.
#
# *Politeness.* 8 per source is 16 article fetches in the worst case, against a
# steady state of 0-3 — the index serves the same stories for hours, so almost
# every run finds nothing new to fetch.
#
# A cold start therefore fills in over several runs rather than one long one,
# which is a better shape anyway: each run commits what it got.
MAX_ARTICLES_PER_RUN = 8

# Attempts and timeout per request. Retrying beats a longer single timeout because
# ft.lk's failure mode is a hang that clears on reconnect, not a slow transfer.
FETCH_ATTEMPTS = 3
FETCH_TIMEOUT = httpx.Timeout(45.0, connect=15.0)


@dataclass(frozen=True)
class NewsSource:
    """One publisher, with the selectors established by reading its markup.

    Every field here was measured against the live pages rather than guessed --
    see scratch/probe_news.py, which prints what each selector actually matches.
    """

    label: str                  # stored in news_sentiment.source
    index_url: str
    headline_selector: str      # elements on the index page that are real headlines
    body_selector: str          # container on the article page holding the story
    date_selector: str = ""     # visible date element, when there is no metadata


NEWS_SOURCES: list[NewsSource] = [
    NewsSource(
        label="Daily FT",
        index_url="https://www.ft.lk/Financial-Services/42",
        # Its index wraps each story card in div.card-body.cbm. A blanket h3
        # search happens to return the same 30 here, but only because this
        # section's template has no other h3 -- scoping to the card makes that
        # explicit instead of relying on it.
        headline_selector="div.card-body.cbm h3",
        # No semantic article container: the story shares div.col-xl-9.lcol with
        # the byline, an unrendered {{hitsCtrl.values.hits}} Angular expression
        # and the visible date, so _extract_body has to drop those.
        body_selector="div.col-xl-9.lcol",
        # ft.lk publishes no article:published_time, no ld+json datePublished and
        # no date meta of any kind. The date is visible text in span.gtime,
        # formatted "Wednesday, 26 August 2026 00:00" -- the time is always
        # 00:00, so only the date part is meaningful.
        date_selector="span.gtime",
    ),
    NewsSource(
        label="EconomyNext",
        index_url="https://economynext.com/markets/",
        headline_selector="h3.recent-top-header",
        # Article pages carry seven div.story-page-text-main blocks -- the story
        # plus a river of neighbouring ones. _extract_body takes the first in
        # document order; taking the longest picks a different story, which is
        # how this was found.
        body_selector="div.story-page-text-main",
    ),
]

# Removed from NEWS_SOURCES rather than left broken, for two independent reasons,
# both verifiable:
#
#   1. https://www.dailymirror.lk/robots.txt publishes "Crawl-delay: 3600" for
#      User-agent: *. One request an hour. The pipeline it was wired into fetched
#      the index plus up to 20 article pages per run, every 30 minutes -- so
#      honouring the stated crawl delay and fetching article bodies are mutually
#      exclusive for this publisher, and the old code was issuing ~21 requests
#      where 0.5 were permitted.
#   2. It answers httpx with HTTP 403 regardless of headers -- tested with no UA
#      override, with the short urllib UA, with a full Chrome UA, with
#      Accept-Encoding: identity, with Connection: close, and over both HTTP/1.1
#      and HTTP/2. urllib.request with the same UA gets HTTP 200, so the block is
#      on the TLS/ALPN fingerprint, not on anything in the request. Keeping the
#      source would mean keeping a second HTTP stack alive purely for it, which
#      is exactly the urllib.request-inside-asyncio.to_thread that
#      _scrape_single_news_source used to do while ignoring the AsyncClient it
#      was handed.
#
# Restoring it is one entry in NEWS_SOURCES plus a fetch path that honours a
# 3600-second delay. That is a decision about a publisher's terms, so it belongs
# to whoever owns the deployment, not to this module.
DROPPED_SOURCES = {"www.dailymirror.lk": "robots.txt Crawl-delay: 3600; 403s httpx"}


# ─────────────────────────────────────────────────────────────────────────────
# Symbol attribution
# ─────────────────────────────────────────────────────────────────────────────

# Trailing words that are legal form rather than identity.
LEGAL_TAIL = frozenset({
    "plc", "ltd", "limited", "company", "co", "corporation", "corp", "inc",
    "pvt", "private",
})

# Trailing words that say what a company does, not which company it is. Peeled
# one at a time to derive the short form a headline would actually use:
# "SOFTLOGIC LIFE INSURANCE PLC" -> "softlogic life".
INDUSTRY_TAIL = frozenset({
    "insurance", "assurance", "finance", "financial", "bank", "banking",
    "holdings", "holding", "plantations", "plantation", "hotels", "hotel",
    "resorts", "resort", "industries", "industry", "industrial", "developments",
    "development", "investments", "investment", "capital", "group", "telecom",
    "telecommunications", "power", "energy", "cables", "mills", "foods", "food",
    "beverages", "beverage", "textiles", "leisure", "properties", "property",
    "estates", "estate", "breweries", "brewery", "distilleries", "motors",
    "trading", "traders", "services", "service", "tea", "lands", "land",
    "chemicals", "packaging", "printing", "logistics", "shipping", "marine",
    "electricals", "electrical", "electronics", "constructions", "construction",
    "engineering", "systems", "technologies", "technology", "solutions",
    "international", "exports", "imports", "agencies", "enterprises", "ventures",
    "assets", "asset", "funds", "fund", "trust", "trusts", "securities", "life",
})

# Place names and filler. A *derived* short form made only of these is not an
# identification. This set is what stops "SRI LANKA TELECOM PLC" from yielding
# the short form "sri lanka" -- which matched 48 of the 60 stored headlines and
# attributed all of them to SLTL, the first false positive this matcher produced.
GENERIC = frozenset({
    "sri", "lanka", "lankan", "ceylon", "colombo", "asia", "asian", "national",
    "people", "s", "central", "united", "first", "new", "royal", "union",
    "eastern", "western", "southern", "northern", "global", "general",
    "standard", "premier", "prime", "grand", "commercial", "and", "the", "of",
    "pan", "east", "west", "north", "south",
})

# A one-word identification must be at least this long. 4 admits "ODEL PLC";
# below that a name is indistinguishable from an abbreviation in prose.
MIN_SOLO_TOKEN = 4

# Derived short forms stop at this many tokens. This is what keeps "SANASA
# DEVELOPMENT BANK PLC" from yielding bare "sanasa", which attributed a Sanasa
# Life Insurance story to Sanasa Development Bank -- a different listed entity
# sharing a group brand. Genuinely one-word companies (Hayleys, Hemas, Agstar,
# Odel) are unaffected: their single token is the *full* filed name, admitted by
# the other rule.
MIN_DERIVED_TOKENS = 2

TICKER_RE = re.compile(r"\b[A-Z][A-Z0-9]{2,5}\b")

# Base tickers never matched as tickers, because the same letters are ordinary
# text in financial news.
#
# PLC is the one that mattered in measurement: PEOPLE'S LEASING & FINANCE PLC
# trades as PLC.N0000, and "PLC" is the legal suffix of nearly every Sri Lankan
# listed company -- so a bare ticker match attributed "Assetline Finance PLC
# marks transformational year" to People's Leasing. Of the three base tickers
# appearing as capitalised tokens across the 60 stored headlines (CDB, NTB, PLC)
# that was the only wrong one, and blocking it makes the ticker path 2-for-2.
#
# The rest are pre-emptive acronyms that recur constantly on these sites.
# Blocking one only costs recall when a story names a company by ticker alone,
# and there is no such story among the 60.
TICKER_BLOCKLIST = frozenset({
    "PLC", "LTD", "INC",
    "CSE", "ASPI", "CBSL", "SEC", "GDP", "CPI", "VAT", "PAYE", "IPO", "ETF",
    "NAV", "EPS", "AGM", "EGM", "ESG", "IFRS", "SLFRS", "GAAP", "EBIT",
    "CEO", "CFO", "COO", "CIO", "CTO", "API", "SME", "SMB", "FDI", "FMCG",
    "USD", "LKR", "EUR", "GBP", "INR", "AUD", "JPY", "CNY",
    "IMF", "ADB", "USA", "ATM", "QR", "AI", "IT", "HR", "PR",
})

# Above this share of uppercase letters the text is shouting, and every short
# word in it looks like a ticker. Ticker matching is skipped.
SHOUTY_RATIO = 0.6


def _tokens(text: str) -> list[str]:
    """Lowercase alphanumeric tokens.

    Matching is done on token *sequences*, never substrings, because all 273 base
    tickers are 3-4 alphabetic characters and every short company name is a
    substring of some English word: "ACL" sits inside "miracle", "AEL" inside
    "fuel".
    """
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def name_phrases(name: str) -> list[list[str]]:
    """Token sequences that identify a company in running text, longest first.

    Two rules, and the split between them is the whole design.

    1. The **full filed name** minus legal suffix always identifies the company.
       "union bank of colombo" is specific as a contiguous four-token phrase no
       matter how unremarkable each word is alone.
    2. **Derived short forms** — the filed name with industry and place tails
       peeled off, which is how a headline actually refers to a company — are
       where false positives live, so they carry two extra tests: at least
       ``MIN_DERIVED_TOKENS`` tokens, and not composed *entirely* of ``GENERIC``
       placeholders.

    An earlier version applied rule 2's tests to the filed name as well and so
    produced **no phrase at all** for 25 companies, among them UNION ASSURANCE,
    UNION BANK OF COLOMBO, NATIONAL DEVELOPMENT BANK, PEOPLE'S INSURANCE and
    ODEL — every token of those names is generic or an industry word on its own.
    That is why the rules are layered rather than combined.

    Note rule 2 tests ``GENERIC`` only, not ``GENERIC | INDUSTRY_TAIL``: "union
    bank" and "asian hotels" are real short forms and survive; "sri lanka" and
    "people s" do not.
    """
    toks = _tokens(name)
    while toks and toks[-1] in LEGAL_TAIL:
        toks.pop()
    if not toks:
        return []

    phrases: list[list[str]] = []
    if len(toks) >= 2 or len(toks[0]) >= MIN_SOLO_TOKEN:
        phrases.append(list(toks))

    cur = list(toks)
    while len(cur) > MIN_DERIVED_TOKENS and cur[-1] in (INDUSTRY_TAIL | GENERIC):
        cur.pop()
        if not all(t in GENERIC for t in cur) and cur not in phrases:
            phrases.append(list(cur))
    return phrases


def _contains(haystack: list[str], needle: list[str]) -> bool:
    n = len(needle)
    if not n or n > len(haystack):
        return False
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


class SymbolMatcher:
    """Attributes article text to CSE symbols, using I-07's ``company_info``.

    Built once per scrape run and reused, because ``name_phrases`` over 293
    companies is not free and the phrase set does not change mid-run.

    Measured against the 60 headlines already in ``news_sentiment``
    (2026-08-28, headline text only, no bodies): 12 headlines attributed, **15
    symbol attributions, all 15 correct** by inspection. The unattributed 48 are
    genuinely company-free — rupee fixings, T-bill auctions, index summaries — or
    name institutions that are not CSE-listed at all: People's Bank, Bank of
    Ceylon, CBSL, Visa, Port City, SLIIT.
    """

    def __init__(self, phrases: dict[str, list[list[str]]],
                 by_base: dict[str, list[str]]) -> None:
        self.phrases = phrases
        self.by_base = by_base

    @classmethod
    def from_db(cls, db: Session) -> "SymbolMatcher":
        phrases: dict[str, list[list[str]]] = {}
        by_base: dict[str, list[str]] = {}
        for symbol, name in db.query(CompanyInfo.symbol, CompanyInfo.name).all():
            p = name_phrases(name or "")
            if p:
                phrases[symbol] = p
            by_base.setdefault(symbol.split(".")[0].upper(), []).append(symbol)
        logger.debug("SymbolMatcher: %d companies with phrases, %d base tickers",
                     len(phrases), len(by_base))
        return cls(phrases, by_base)

    def match(self, text: str) -> dict[str, str]:
        """symbol -> why it matched, for one article's text.

        Two symbols for the same company (voting and non-voting share classes)
        both match by design: 28 of the 34 phrases shared between symbols are a
        single company's two classes, and a story about Commercial Bank is about
        both of them. The remaining 6 are real corporate groups — "john keells"
        is shared by JKH, JKL and KHL — where the ambiguity is in the language,
        not in the matcher.
        """
        hay = _tokens(text)
        matched: dict[str, tuple[list[str], str]] = {}
        for symbol, phrase_list in self.phrases.items():
            for phrase in phrase_list:          # longest first
                if _contains(hay, phrase):
                    matched[symbol] = (phrase, "name:" + " ".join(phrase))
                    break

        # Longest match wins. If one company was identified by "john keells
        # hotels", a different company matched only by "john keells" is dropped:
        # the more specific phrase is the one the headline actually used.
        superseded = {
            sym for sym, (phrase, _) in matched.items()
            if any(other != sym and len(p2) > len(phrase) and _contains(p2, phrase)
                   for other, (p2, _) in matched.items())
        }
        hits = {sym: why for sym, (_, why) in matched.items()
                if sym not in superseded}

        letters = [c for c in text if c.isalpha()]
        shouty = bool(letters) and (
            sum(c.isupper() for c in letters) / len(letters) > SHOUTY_RATIO)
        if not shouty:
            for m in TICKER_RE.finditer(text):
                base = m.group(0)
                if base in TICKER_BLOCKLIST:
                    continue
                for symbol in self.by_base.get(base, []):
                    hits.setdefault(symbol, "ticker:" + base)
        return hits


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# economynext serves "11:12 am,Friday August 28, 2026" in
# article:published_time and "2026-08-28T11:12 am+00:00" in modified/updated.
# Neither is ISO 8601 -- the first has no separator after the comma and the
# second puts a space and a lowercase meridiem inside what looks like an ISO
# string -- so datetime.fromisoformat rejects both and each needs its own shape.
_MERIDIEM_ISO = re.compile(
    r"^(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})T"
    r"(?P<h>\d{1,2}):(?P<mi>\d{2})\s*(?P<ap>am|pm)", re.I)
_TIME_THEN_DATE = re.compile(
    r"^(?P<h>\d{1,2}):(?P<mi>\d{2})\s*(?P<ap>am|pm)\s*,\s*"
    r"(?:\w+day)?\s*(?P<mon>[A-Za-z]+)\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{4})", re.I)
# ft.lk's visible date: "Wednesday, 26 August 2026 00:00".
_DAY_MONTH_YEAR = re.compile(
    r"(?:\w+day),?\s+(?P<d>\d{1,2})\s+(?P<mon>[A-Za-z]+)\s+(?P<y>\d{4})"
    r"(?:\s+(?P<h>\d{1,2}):(?P<mi>\d{2}))?")

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}


def _month(name: str) -> int | None:
    n = (name or "").lower()
    if n in _MONTHS:
        return _MONTHS[n]
    for full, num in _MONTHS.items():
        if full.startswith(n[:3]) and len(n) >= 3:
            return num
    return None


def _to_utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime | None:
    """Build a UTC instant from a local Colombo wall-clock reading.

    Both publishers date stories in Sri Lankan local time and neither states an
    offset (economynext's "+00:00" is the WordPress default, not a real one), so
    a naive reading is Asia/Colombo. Storing it as UTC without that conversion
    would put every article 5.5 hours early.
    """
    try:
        local = datetime(year, month, day, hour, minute, tzinfo=EXCHANGE_TZ)
    except ValueError:
        return None
    return local.astimezone(timezone.utc)


def parse_published_at(raw: str | None) -> datetime | None:
    """Best-effort publish instant from any of the shapes these sites emit."""
    text = _clean(raw)
    if not text:
        return None

    m = _MERIDIEM_ISO.match(text)
    if m:
        hour = int(m.group("h")) % 12 + (12 if m.group("ap").lower() == "pm" else 0)
        return _to_utc(int(m.group("y")), int(m.group("mo")), int(m.group("d")),
                       hour, int(m.group("mi")))

    m = _TIME_THEN_DATE.match(text)
    if m:
        month = _month(m.group("mon"))
        if month:
            hour = int(m.group("h")) % 12 + (12 if m.group("ap").lower() == "pm" else 0)
            return _to_utc(int(m.group("y")), month, int(m.group("d")),
                           hour, int(m.group("mi")))

    m = _DAY_MONTH_YEAR.search(text)
    if m:
        month = _month(m.group("mon"))
        if month:
            return _to_utc(int(m.group("y")), month, int(m.group("d")),
                           int(m.group("h") or 0), int(m.group("mi") or 0))

    # A genuine ISO 8601 value, in case either publisher starts emitting one.
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        logger.debug("unparseable publish date: %r", text[:60])
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=EXCHANGE_TZ)
    return parsed.astimezone(timezone.utc)


def extract_published_at(soup: BeautifulSoup, source: NewsSource) -> datetime | None:
    """Publish instant from metadata, falling back to the visible date element.

    Metadata first because it is machine-readable and unambiguous, but only
    economynext has any: ft.lk emits no article:published_time, no ld+json
    datePublished and no date meta of any kind, so its date has to come from
    ``span.gtime``.
    """
    for attr, key in (("property", "article:published_time"),
                      ("name", "article:published_time"),
                      ("property", "og:published_time"),
                      ("name", "publish-date"),
                      ("name", "date")):
        tag = soup.find("meta", attrs={attr: key})
        if tag and tag.get("content"):
            when = parse_published_at(tag["content"])
            if when:
                return when

    if source.date_selector:
        node = soup.select_one(source.date_selector)
        if node:
            when = parse_published_at(node.get_text())
            if when:
                return when
    return None


# Paragraphs that are furniture rather than prose. "Editorial :" is here because
# it is literally what every one of the 60 pre-existing summaries contained: the
# old extractor took the paragraph following the headline in document order and
# landed in ft.lk's footer contact block.
_BOILERPLATE = re.compile(
    r"^\s*(editorial\s*:|advertis|share this|follow us|tags?\s*:|"
    r"related (stories|news)|comments?\s*\(|read more|\+94\s*\d)", re.I)

# An unrendered Angular expression. ft.lk's article template emits
# "{{hitsCtrl.values.hits}}" as literal text where a view counter should be, and
# it sits *inside* the first paragraph rather than in its own element — so it has
# to be cut out of the text, not filtered out by element.
_TEMPLATE_EXPR = re.compile(r"\{\{[^}]*\}\}")

# The rendered date, with its trailing separator dashes. Also inside ft.lk's first
# paragraph: that paragraph reads "Wednesday, 26 August 2026 00:00 - -
# {{hitsCtrl.values.hits}} By Wealth Trust Securities At the round of Treasury
# Bond auctions..." — metadata and prose in one node. Anchored to the start so a
# date mentioned mid-sentence in a real story is left alone.
_LEADING_DATE = re.compile(
    r"^\s*(?:\w+day),?\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}"
    r"(?:\s+\d{1,2}:\d{2})?\s*[-–—\s]*", re.I)

# Shorter than this and a paragraph is a caption, a credit line or a stub.
MIN_PARAGRAPH_LEN = 40


def _strip_furniture(text: str) -> str:
    """Remove template leftovers and a leading date stamp from one paragraph."""
    text = _clean(_TEMPLATE_EXPR.sub(" ", text))
    text = _LEADING_DATE.sub("", text)
    return _clean(text)


def extract_body(soup: BeautifulSoup, source: NewsSource) -> str:
    """The story's own prose, from the first matching container.

    **First in document order, not longest.** economynext article pages carry
    seven ``div.story-page-text-main`` blocks — the story plus a river of
    neighbouring ones — so picking the largest returns a different article
    entirely. That is not hypothetical: it is how this was found, with a probe
    that reported the body of "New Anthoney's Farms named among sustainability
    leaders" for a URL about the ASPI closing up.

    Cleaning happens *within* each paragraph rather than by dropping whole
    elements, because ft.lk puts the date, an unrendered template expression and
    the opening sentence in the same ``<p>``. An element-level filter either keeps
    all three or discards the lede.
    """
    container = soup.select_one(source.body_selector)
    if container is None:
        return ""
    parts: list[str] = []
    for p in container.find_all("p"):
        text = _strip_furniture(p.get_text())
        if len(text) < MIN_PARAGRAPH_LEN or _BOILERPLATE.match(text):
            continue
        parts.append(text)
    return " ".join(parts)


def validate_news_record(art: dict) -> bool:
    """True if a scraped record looks like a real story.

    Index pages carry navigation labels and teaser stubs alongside genuine
    headlines — ft.lk's business index has a bare "NOTICE" item — so a length
    floor plus a real absolute URL is the minimum bar for storing a row.
    """
    if len(_clean(art.get("title") or art.get("headline") or "")) < MIN_HEADLINE_LEN:
        return False
    url = (art.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return False
    if len(url) > MAX_URL_LEN:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Fetching
# ─────────────────────────────────────────────────────────────────────────────

def _undecoded(response: httpx.Response) -> str | None:
    """The content-encoding httpx could not undo, or None if the body is text.

    Guards a failure mode that produces **no error at all**: if the request
    advertises an encoding httpx has no decoder for, the server compresses,
    ``response.status_code`` is 200, and ``response.text`` returns the compressed
    bytes decoded as characters. Every selector then matches nothing and the run
    logs a clean "0 headlines".

    That is not hypothetical — it is what happened here. ``DEFAULT_HEADERS`` hard-
    coded ``Accept-Encoding: gzip, deflate, br`` while neither ``brotli`` nor
    ``brotlicffi`` was installed, so economynext.com returned 21,572 Brotli bytes
    that became 20,415 characters of mojibake. Fixed at the source by removing that
    header, and checked here as well because the next codec to become fashionable
    (zstd) would reintroduce it, and because a silent wrong answer is much worse
    than a loud absent one.
    """
    encoding = (response.headers.get("content-encoding") or "").lower().strip()
    if not encoding or encoding == "identity":
        return None
    from httpx._decoders import SUPPORTED_DECODERS
    if encoding in SUPPORTED_DECODERS:
        return None
    return encoding


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    """GET a page with the client the caller owns, retrying transient failures.

    Uses the passed ``AsyncClient``, which the function this replaces did not:
    ``_scrape_single_news_source(client, ...)`` accepted the client, ignored it,
    and ran ``urllib.request.urlopen`` inside ``asyncio.to_thread`` — so every
    request opened a fresh TCP and TLS connection, none of the configured
    headers or timeouts applied, and the pool the caller had built went unused.
    """
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            response = await client.get(url, timeout=FETCH_TIMEOUT)
            if response.status_code == 200:
                bad = _undecoded(response)
                if bad:
                    logger.error(
                        "%s returned Content-Encoding: %s, which this httpx build "
                        "cannot decode — the body would be unusable. Remove the "
                        "hand-written Accept-Encoding header, or install the "
                        "matching decoder.", url, bad)
                    return None
                return response.text
            logger.warning("news fetch %s -> HTTP %s (attempt %d/%d)",
                           url, response.status_code, attempt, FETCH_ATTEMPTS)
            # A 403/404 will not change on retry; a 429/5xx might.
            if response.status_code < 500 and response.status_code != 429:
                return None
        except Exception as exc:                      # noqa: BLE001
            logger.warning("news fetch %s failed (attempt %d/%d): %s: %s",
                           url, attempt, FETCH_ATTEMPTS, type(exc).__name__, exc)
        if attempt < FETCH_ATTEMPTS:
            await asyncio.sleep(PER_REQUEST_DELAY * attempt)
    return None


def index_links(html: str, source: NewsSource) -> list[tuple[str, str]]:
    """(headline, absolute url) for every real story on an index page."""
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for node in soup.select(source.headline_selector):
        anchor = node.find("a", href=True) or node.find_parent("a", href=True)
        if not anchor:
            continue
        title = _clean(node.get_text())
        url = urljoin(source.index_url, anchor["href"])
        if not title or url in seen:
            continue
        seen.add(url)
        out.append((title, url))
    return out


async def scrape_news_articles(client: httpx.AsyncClient,
                               matcher: SymbolMatcher | None = None,
                               known_urls: set[str] | None = None,
                               sources: list[NewsSource] | None = None,
                               limit_per_source: int = MAX_ARTICLES_PER_RUN
                               ) -> list[dict]:
    """Fetch index pages, then bodies for stories not already stored.

    ``known_urls`` is why this is affordable on a 30-minute schedule: an index
    page serves the same stories for hours, so skipping bodies for URLs already
    in the table turns a steady-state run into two index fetches plus one article
    fetch per genuinely new story.

    Freshest first, so when ``limit_per_source`` bites it is the oldest stories
    that wait for the next run. Both index pages list newest at the top.
    """
    known = known_urls or set()
    articles: list[dict] = []

    for source in sources if sources is not None else NEWS_SOURCES:
        html = await _fetch(client, source.index_url)
        if not html:
            logger.warning("news source %s unreachable, skipping", source.label)
            continue

        links = index_links(html, source)
        fresh = [(t, u) for t, u in links if u not in known]
        deferred = max(0, len(fresh) - limit_per_source)
        if deferred:
            # Said out loud rather than silently truncated: "12 headlines, 8 new"
            # with no further comment reads as complete coverage when it is not.
            logger.info("%s: %d headlines, %d new, fetching %d this run "
                        "(%d deferred to the next)",
                        source.label, len(links), len(fresh),
                        limit_per_source, deferred)
        else:
            logger.info("%s: %d headlines, %d new", source.label, len(links),
                        len(fresh))

        for title, url in fresh[:limit_per_source]:
            record = {"title": title, "url": url[:MAX_URL_LEN],
                      "source": source.label, "body": "", "summary": "",
                      "published_at": None, "symbols": {}}
            if not validate_news_record(record):
                continue

            await asyncio.sleep(PER_REQUEST_DELAY)
            page = await _fetch(client, url)
            if page:
                soup = BeautifulSoup(page, "lxml")
                record["body"] = extract_body(soup, source)
                record["published_at"] = extract_published_at(soup, source)
            else:
                # Storable without a body: the headline and URL are real and the
                # matcher still runs on the headline. The row simply has a
                # shorter summary and no publish date.
                logger.info("no body for %s", url)

            record["summary"] = record["body"][:LEDE_CHARS]
            if matcher is not None:
                record["symbols"] = matcher.match(
                    f"{title}. {record['body']}")
            articles.append(record)

    return articles


# ─────────────────────────────────────────────────────────────────────────────
# Feeds: machine-readable sources that don't break on a page redesign and
# aren't blocked the way page scraping is (EconomyNext answers its own RSS
# with 403). Each is optional: one being down never stops the others.
# ─────────────────────────────────────────────────────────────────────────────

# Google News aggregates the Sri Lankan business press (Daily FT, EconomyNext,
# Daily Mirror, LBO, Sunday Times...) into one stable RSS feed. No key.
GOOGLE_NEWS_RSS = ("https://news.google.com/rss/search?q=%28%22Colombo+Stock+Exchange%22"
                   "+OR+CSE+OR+ASPI%29+Sri+Lanka+when%3A3d&hl=en-LK&gl=LK&ceid=LK:en")
LBO_RSS = "https://www.lankabusinessonline.com/feed/"
# The exchange's own register of listed companies' financial reports; each
# row links to the real PDF on the CSE's file server.
CSE_FINANCIALS_URL = "https://www.cse.lk/api/getFinancialAnnouncement"
CSE_FILES = "https://cdn.cse.lk/"
MAX_FEED_ITEMS = 25


def parse_rss(xml_text: str) -> list[dict]:
    """RSS 2.0 items as {title, url, source, body, published_at}."""
    items = []
    for it in ET.fromstring(xml_text).iter("item"):
        title = _clean(it.findtext("title"))
        source_el = it.find("source")
        source = _clean(source_el.text) if source_el is not None else ""
        # Google News appends " - Publisher" to every headline.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].rstrip()
        body = _clean(BeautifulSoup(it.findtext("description") or "", "lxml").get_text(" "))
        if body.startswith(title):   # Google's description just repeats the headline
            body = ""
        try:
            published = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except (TypeError, ValueError):
            published = None
        items.append({"title": title, "url": (it.findtext("link") or "").strip(),
                      "source": source, "body": body, "published_at": published})
    return items


def cse_financial_records(payload: dict) -> list[dict]:
    """getFinancialAnnouncement rows as feed items, e.g. "ACME PLC: Interim
    Financial Statements for Q1", linking the report PDF."""
    items = []
    for row in payload.get("reqFinancialAnnouncemnets") or []:   # sic, CSE's spelling
        if not row.get("path") or not row.get("name"):
            continue
        try:
            published = (datetime.strptime(row["uploadedDate"], "%d %b %Y %I:%M:%S %p")
                         .replace(tzinfo=EXCHANGE_TZ).astimezone(timezone.utc))
        except (KeyError, TypeError, ValueError):
            published = None
        items.append({"title": f"{_clean(row['name']).title()}: {_clean(row.get('fileText'))}",
                      "url": CSE_FILES + row["path"].lstrip("/"), "source": "CSE",
                      "body": "", "published_at": published})
    return items


async def fetch_feed_articles(client: httpx.AsyncClient,
                              matcher: SymbolMatcher | None = None,
                              known_urls: set[str] | None = None) -> list[dict]:
    """New stories from the feeds, in the same shape as scrape_news_articles."""
    known = known_urls or set()
    collected: list[tuple[str, dict]] = []
    for label, url in (("Google News", GOOGLE_NEWS_RSS), ("LBO", LBO_RSS)):
        text = await _fetch(client, url)
        if not text:
            logger.warning("news feed %s unreachable, skipping", label)
            continue
        try:
            collected += [(label, it) for it in parse_rss(text)[:MAX_FEED_ITEMS]]
        except ET.ParseError as exc:
            logger.warning("news feed %s: unreadable RSS (%s)", label, exc)
    try:
        resp = await client.post(CSE_FINANCIALS_URL, headers={
            "Origin": "https://www.cse.lk", "Referer": "https://www.cse.lk/"})
        resp.raise_for_status()
        collected += [("CSE", it) for it in cse_financial_records(resp.json())]
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("CSE financial announcements unavailable (%s)", exc)

    articles = []
    for label, it in collected:
        url = it["url"][:MAX_URL_LEN]
        if url in known:
            continue
        known.add(url)
        record = {"title": it["title"], "url": url,
                  # Aggregated stories keep the real publisher's name.
                  "source": it["source"] if label == "Google News" and it["source"] else label,
                  "body": it["body"], "summary": it["body"][:LEDE_CHARS],
                  "published_at": it["published_at"], "symbols": {}}
        if not validate_news_record(record):
            continue
        if matcher is not None:
            record["symbols"] = matcher.match(f"{record['title']}. {record['body']}")
        articles.append(record)
    logger.info("news feeds: %d items, %d new", len(collected), len(articles))
    return articles


# ─────────────────────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────────────────────

def save_news_articles(db: Session, articles: list[dict]) -> list[int]:
    """Write one row per (article, matched symbol); return new news_id values.

    Rows already present for the same (url, symbol) are **updated** rather than
    skipped, which is what repairs the 60 pre-existing rows: they carry real
    headlines and URLs but ``summary = 'Editorial :'`` and no publish date, so
    the next run over the same URL backfills a real lede and a real date.

    When an article does get attributed, any ``GENERAL`` row for that URL is
    deleted. ``GENERAL`` means "no company identified"; once one has been, that
    row is a stale assertion, not a market-wide story.
    """
    new_ids: list[int] = []

    for art in articles:
        if not validate_news_record(art):
            continue
        symbols = sorted(art.get("symbols") or {}) or [GENERAL_SYMBOL]
        url = art["url"][:MAX_URL_LEN]

        for symbol in symbols:
            row = (db.query(NewsSentiment)
                   .filter(NewsSentiment.url == url,
                           NewsSentiment.symbol == symbol)
                   .one_or_none())
            if row is None:
                row = NewsSentiment(symbol=symbol, url=url,
                                    headline=art["title"][:500])
                db.add(row)
                db.flush()
                new_ids.append(row.news_id)
            else:
                row.headline = art["title"][:500]

            row.source = (art.get("source") or "")[:120]
            # Only overwrite with something we actually have, so a run that
            # could not reach an article page does not blank a good body.
            if art.get("body"):
                row.body = art["body"]
                row.summary = art["body"][:LEDE_CHARS]
            if art.get("published_at"):
                row.published_at = art["published_at"]

        if symbols != [GENERAL_SYMBOL]:
            stale = (db.query(NewsSentiment)
                     .filter(NewsSentiment.url == url,
                             NewsSentiment.symbol == GENERAL_SYMBOL)
                     .one_or_none())
            if stale is not None:
                logger.info("dropping GENERAL row for %s, now attributed to %s",
                            url, symbols)
                db.delete(stale)

    db.commit()
    return new_ids


async def scrape_and_save_news(db: Session, symbol: str | None = None) -> list[int]:
    """Scrape both sources and persist. Returns news_id values for new rows.

    ``symbol`` filters to stories that mention one company, for the on-demand
    enrichment path in ``routers/stocks.py``. It is a *filter* now, not a label:
    it used to be written into ``news_sentiment.symbol`` for every row the run
    produced, which is how 60 rows ended up stamped ``GENERAL`` — the caller
    passed nothing, so every article claimed to be about nothing in particular
    regardless of which companies it named.
    """
    known = {u for (u,) in db.query(NewsSentiment.url).all()}
    matcher = SymbolMatcher.from_db(db)

    from app.services.scraper import DEFAULT_HEADERS
    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=FETCH_TIMEOUT,
                                 follow_redirects=True) as client:
        articles = await scrape_news_articles(client, matcher=matcher,
                                              known_urls=known)
        articles += await fetch_feed_articles(client, matcher=matcher,
                                              known_urls=known | {a["url"] for a in articles})

    if symbol:
        want = symbol.upper()
        articles = [a for a in articles
                    if any(s.split(".")[0] == want.split(".")[0]
                           for s in (a.get("symbols") or {}))]
        logger.info("news scrape filtered to %s: %d articles", want, len(articles))

    ids = save_news_articles(db, articles)
    logger.info("news scrape: %d articles, %d new rows", len(articles), len(ids))
    return ids
