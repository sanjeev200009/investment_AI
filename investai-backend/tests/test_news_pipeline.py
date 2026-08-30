# tests/test_news_pipeline.py
"""Tests for I-08: real article bodies, dates and per-company attribution.

``news_sentiment`` held 60 rows before this work. Every one of them was wrong in
the same four ways, measured 2026-08-28:

* ``symbol = 'GENERAL'`` on all 60 — the writer was
  ``art.get('symbol') or symbol or 'GENERAL'`` where ``symbol`` was the scrape
  function's own optional argument, so nothing was ever attributed to a company;
* ``summary`` was the literal string ``'Editorial :'`` on all 60 — the extractor
  was ``h3.find_next('p')``, which on ft.lk's index page is the footer contact
  block, and that string was then scored by VADER *as the article text* and
  pasted into the dashboard's LLM prompt;
* ``published_at`` NULL on all 60 — never parsed;
* ``sentiment_label`` NULL on all 60.

Offline and holding no database connection, per ``pytest.ini``. The HTML fixtures
below are **reduced from the live pages**, preserving the specific structures that
broke something during development rather than idealising them: economynext's
seven-way story river, ft.lk's date and unrendered Angular expression sharing a
``<p>`` with the lede, and ft.lk's total absence of date metadata. What needs a
live database and live HTTP is ``scripts/verify_i08.py``.
"""

from datetime import datetime, timezone

import pytest
from bs4 import BeautifulSoup

from app.services.news import (GENERAL_SYMBOL, MAX_URL_LEN, MIN_HEADLINE_LEN,
                               NEWS_SOURCES, SymbolMatcher, _tokens,
                               extract_body, extract_published_at, index_links,
                               name_phrases, parse_published_at,
                               validate_news_record)

FT = next(s for s in NEWS_SOURCES if s.label == "Daily FT")
EN = next(s for s in NEWS_SOURCES if s.label == "EconomyNext")


# ─────────────────────────────────────────────────────────────────────────────
# Source configuration
# ─────────────────────────────────────────────────────────────────────────────

def test_dailymirror_is_not_a_source():
    """Dropped in I-08, and the test states why so a re-add is a deliberate act.

    Two independent reasons: dailymirror.lk's robots.txt publishes
    ``Crawl-delay: 3600`` — one request an hour, against a pipeline issuing ~21
    every 30 minutes — and it answers httpx with HTTP 403 on every header and
    protocol combination tried, which is what the removed
    ``urllib.request``-in-a-thread fetch existed to work around.
    """
    hosts = [s.index_url for s in NEWS_SOURCES]
    assert not any("dailymirror" in h for h in hosts), hosts
    assert len(NEWS_SOURCES) == 2


def test_scraper_reexports_derive_from_news_module():
    """scraper.NEWS_SOURCES is computed from this module, not restated.

    Five call sites import the news entry points from ``app.services.scraper``.
    Two copies of the source list would drift, and the drift would be invisible.
    """
    from app.services import scraper
    assert scraper.NEWS_SOURCES == [s.index_url for s in NEWS_SOURCES]
    assert scraper.MIN_HEADLINE_LEN == MIN_HEADLINE_LEN


def test_default_headers_do_not_advertise_undecodable_encoding():
    """The bug that made the whole rewrite look like it had found no news.

    ``DEFAULT_HEADERS`` hard-coded ``Accept-Encoding: gzip, deflate, br`` while
    neither ``brotli`` nor ``brotlicffi`` was installed. economynext.com honours
    Brotli when offered, so every request to it returned **HTTP 200 with an
    undecodable body**: 21,572 compressed bytes that ``response.text`` handed to
    BeautifulSoup as 20,415 characters of mojibake. No exception, no warning, no
    non-2xx status — just zero matches for every selector.

    httpx writes this header itself from the decoders it actually has, so the fix
    is to not write it. Asserting the *absence* of the key rather than a specific
    value is deliberate: any hand-written value can go stale against the installed
    decoder set, which is exactly how this happened.
    """
    from httpx._decoders import SUPPORTED_DECODERS
    from app.services.scraper import CSE_HEADERS, DEFAULT_HEADERS

    for name, headers in (("DEFAULT_HEADERS", DEFAULT_HEADERS),
                          ("CSE_HEADERS", CSE_HEADERS)):
        keys = {k.lower() for k in headers}
        assert "accept-encoding" not in keys, (
            f"{name} writes Accept-Encoding by hand; httpx knows which of "
            f"{sorted(SUPPORTED_DECODERS)} it can decode and this does not")


def test_undecoded_detects_unsupported_encoding():
    """A body httpx could not decompress is reported, not parsed as text."""
    import httpx
    from app.services.news import _undecoded

    brotli = httpx.Response(200, headers={"content-encoding": "br"},
                            content=b"\x1b\x0e\x00\x00")
    assert _undecoded(brotli) == "br"

    plain = httpx.Response(200, text="<html></html>")
    assert _undecoded(plain) is None
    assert _undecoded(httpx.Response(
        200, headers={"content-encoding": "identity"}, text="x")) is None


# ─────────────────────────────────────────────────────────────────────────────
# Index parsing
# ─────────────────────────────────────────────────────────────────────────────

# ft.lk's index, reduced: two story cards plus the "NOTICE" stub its business
# section carries, and a heading with no anchor.
FT_INDEX = """
<html><body>
<div class="card-body cbm">
  <h3><a href="/financial-services/Bullish-outcome-at-Rs-50-b-T-Bond/42-796500">
      Bullish outcome at Rs. 50 b T-Bond auction</a></h3>
</div>
<div class="card-body cbm">
  <h3><a href="https://www.ft.lk/financial-services/Sampath-Bank-honoured/42-796490">
      Sampath Bank honoured with three prestigious accolades</a></h3>
</div>
<div class="card-body cbm"><h3><a href="/notice/42-1">NOTICE</a></h3></div>
<div class="card-body cbm"><h3>Heading with no link at all</h3></div>
<div class="sidebar"><h3><a href="/other/1">Sidebar item outside the card</a></h3></div>
</body></html>
"""


def test_index_links_scoped_to_story_cards():
    links = index_links(FT_INDEX, FT)
    titles = [t for t, _ in links]

    assert "Bullish outcome at Rs. 50 b T-Bond auction" in titles
    # Scoped to div.card-body.cbm, so a sidebar heading is not a story. The old
    # scraper used a blanket soup.find_all('h3').
    assert "Sidebar item outside the card" not in titles
    # A heading with no anchor yields no link rather than a row with no URL.
    assert "Heading with no link at all" not in titles


def test_index_links_resolve_relative_and_absolute_hrefs():
    by_title = dict(index_links(FT_INDEX, FT))
    assert by_title["Bullish outcome at Rs. 50 b T-Bond auction"] == (
        "https://www.ft.lk/financial-services/"
        "Bullish-outcome-at-Rs-50-b-T-Bond/42-796500")
    # An already-absolute href is left alone rather than urljoin'd onto itself.
    assert by_title[
        "Sampath Bank honoured with three prestigious accolades"].startswith(
            "https://www.ft.lk/financial-services/Sampath-Bank")


def test_index_links_deduplicate_by_url():
    """The same story often appears twice, as a hero card and in the river."""
    html = FT_INDEX.replace("</body>", """
      <div class="card-body cbm"><h3>
        <a href="/financial-services/Bullish-outcome-at-Rs-50-b-T-Bond/42-796500">
        Bullish outcome at Rs. 50 b T-Bond auction</a></h3></div>
    </body>""")
    urls = [u for _, u in index_links(html, FT)]
    assert len(urls) == len(set(urls))


def test_notice_stub_is_rejected_by_validation():
    """"NOTICE" is a real item on ft.lk's business index and not a story."""
    notice = next((r for t, u in index_links(FT_INDEX, FT)
                   if t == "NOTICE" for r in [{"title": t, "url": u}]), None)
    assert notice is not None, "the fixture should still contain the stub"
    assert validate_news_record(notice) is False


@pytest.mark.parametrize("record, ok", [
    ({"title": "Sampath Bank honoured with three accolades",
      "url": "https://www.ft.lk/a/1"}, True),
    # Below MIN_HEADLINE_LEN.
    ({"title": "NOTICE", "url": "https://www.ft.lk/a/1"}, False),
    ({"title": "x" * (MIN_HEADLINE_LEN - 1),
      "url": "https://www.ft.lk/a/1"}, False),
    # Exactly at the bar is accepted; the constant is a floor, not a threshold.
    ({"title": "x" * MIN_HEADLINE_LEN, "url": "https://www.ft.lk/a/1"}, True),
    # A relative or scheme-less URL is not storable: the client renders a link.
    ({"title": "A perfectly reasonable financial headline",
      "url": "/relative/path"}, False),
    ({"title": "A perfectly reasonable financial headline",
      "url": "javascript:void(0)"}, False),
    ({"title": "A perfectly reasonable financial headline", "url": ""}, False),
    # Longer than the column and half of a unique index — rejected rather than
    # truncated to a link that 404s.
    ({"title": "A perfectly reasonable financial headline",
      "url": "https://www.ft.lk/" + "a" * MAX_URL_LEN}, False),
    ({"title": None, "url": "https://www.ft.lk/a/1"}, False),
])
def test_validate_news_record(record, ok):
    assert validate_news_record(record) is ok


def test_validate_accepts_headline_key_as_well_as_title():
    """save_news_articles re-validates rows keyed the way the model names them."""
    assert validate_news_record({"headline": "Sampath Bank honoured with awards",
                                 "url": "https://www.ft.lk/a/1"}) is True


# ─────────────────────────────────────────────────────────────────────────────
# Body extraction
# ─────────────────────────────────────────────────────────────────────────────

# ft.lk's article page, reduced to the structure that matters: the date, an
# unrendered Angular expression and the opening sentence share one <p>, and the
# page carries the footer editorial block that produced 'Editorial :' in all 60
# stored summaries.
FT_ARTICLE = """
<html><head><title>Bullish outcome</title></head><body>
<div class="col-xl-9 lcol">
  <span class="gtime">Wednesday, 26 August 2026 00:00</span>
  <p>Wednesday, 26 August 2026 00:00 - - {{hitsCtrl.values.hits}} By Wealth Trust
     Securities At the round of Treasury Bond auctions conducted yesterday, the
     Rs. 50 billion on offer was oversubscribed by 3.4 times.</p>
  <p>Short caption</p>
  <p>The weighted average yield on the 2029 maturity declined to 8.92% from 9.14%
     at the preceding auction, extending a downward trajectory that has held for
     six consecutive weeks.</p>
  <p>Share this article on social media</p>
</div>
<div class="col-sm-4 col-md col-12 col">
  <p>Editorial : +94 0112 479 356, 479 377, 479 391</p>
</div>
</body></html>
"""

# economynext's article page: seven div.story-page-text-main blocks, of which the
# first is this story and the rest are a river of neighbouring ones. Picking the
# longest returns a different article entirely.
EN_ARTICLE = """
<html><head>
<meta property="article:published_time" content="11:12 am,Friday August 28, 2026">
<meta property="article:modified_time" content="2026-08-28T11:12 am+00:00">
</head><body>
<div class="story-page-text-main">
  <p>ECONOMYNEXT - Sri Lanka's Colombo Stock Exchange was trading higher at Friday
     midday with the ASPI up 43.29 points at 21,322.94.</p>
  <p>Capital goods counters led turnover, with John Keells Holdings and Hayleys
     accounting for a combined 1.2 billion rupees of the day's activity.</p>
</div>
<div class="story-page-text-main">
  <p>ECONOMYNEXT - New Anthoney's Farms has been named among the island's
     sustainability leaders in an award scheme run by a chamber body, and this
     block is deliberately far longer than the real story above it so that any
     longest-match heuristic picks the wrong article, which is how this was
     found in the first place during probing of the live pages.</p>
  <p>The company said the recognition followed a multi-year programme of effluent
     treatment upgrades across its processing sites, and that further investment
     was planned for the coming financial year at three additional locations.</p>
</div>
</body></html>
"""


def test_ft_body_strips_date_and_template_sharing_the_lede_paragraph():
    """The junk is *inside* the first <p>, so element filtering cannot remove it.

    The paragraph reads "Wednesday, 26 August 2026 00:00 - -
    {{hitsCtrl.values.hits}} By Wealth Trust Securities At the round of..." — a
    date, an unrendered Angular expression and the lede in one node. Dropping the
    element loses the lede; keeping it puts template source into the text the LLM
    summarises and VADER scores.
    """
    body = extract_body(BeautifulSoup(FT_ARTICLE, "lxml"), FT)

    assert "{{" not in body and "hitsCtrl" not in body
    assert not body.startswith("Wednesday")
    assert body.startswith("By Wealth Trust Securities")
    assert "oversubscribed by 3.4 times" in body
    assert "8.92%" in body


def test_ft_body_excludes_footer_and_furniture():
    """'Editorial :' was the entire stored summary of all 60 rows."""
    body = extract_body(BeautifulSoup(FT_ARTICLE, "lxml"), FT)

    assert "Editorial" not in body
    assert "+94" not in body
    assert "Share this article" not in body
    # Below MIN_PARAGRAPH_LEN: a caption, not prose.
    assert "Short caption" not in body


def test_economynext_body_takes_first_block_not_longest():
    """Seven story blocks per page; document order identifies the right one."""
    soup = BeautifulSoup(EN_ARTICLE, "lxml")
    body = extract_body(soup, EN)

    assert "ASPI was up" in body or "ASPI up 43.29" in body
    assert "21,322.94" in body
    # The decoy block is longer. If it appears, the extractor is picking by size.
    assert "Anthoney" not in body, "picked a neighbouring story from the river"


def test_extract_body_returns_empty_when_container_absent():
    """A layout change degrades to no body, not to an exception or wrong text."""
    assert extract_body(BeautifulSoup(
        "<html><body><p>" + "x" * 200 + "</p></body></html>", "lxml"), EN) == ""


# ─────────────────────────────────────────────────────────────────────────────
# Publish dates
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    # economynext's article:published_time. Not ISO 8601 — no separator after the
    # comma — so datetime.fromisoformat rejects it.
    ("11:12 am,Friday August 28, 2026", datetime(2026, 8, 28, 5, 42, tzinfo=timezone.utc)),
    # economynext's modified/updated. Looks ISO until the space and the lowercase
    # meridiem inside it. The "+00:00" is WordPress's default, not a real offset —
    # the reading is Colombo local, which is why this is not 11:12Z.
    ("2026-08-28T11:12 am+00:00", datetime(2026, 8, 28, 5, 42, tzinfo=timezone.utc)),
    # ft.lk's span.gtime, its only date anywhere on the page.
    ("Wednesday, 26 August 2026 00:00", datetime(2026, 8, 25, 18, 30, tzinfo=timezone.utc)),
    ("Tuesday, 25 August 2026 08:07", datetime(2026, 8, 25, 2, 37, tzinfo=timezone.utc)),
    # 12 am is hour 0 and rolls the UTC date back; 12 pm is hour 12.
    ("12:01 am,Tuesday March 3, 2026", datetime(2026, 3, 2, 18, 31, tzinfo=timezone.utc)),
    ("12:30 pm,Tuesday March 3, 2026", datetime(2026, 3, 3, 7, 0, tzinfo=timezone.utc)),
    ("3:45 pm,Monday January 5, 2026", datetime(2026, 1, 5, 10, 15, tzinfo=timezone.utc)),
    # A genuine ISO value with an explicit offset is respected as given.
    ("2026-08-28T11:12:00+05:30", datetime(2026, 8, 28, 5, 42, tzinfo=timezone.utc)),
    ("", None),
    (None, None),
    ("nonsense", None),
    ("Someday, 99 Nonemonth 2026 00:00", None),
])
def test_parse_published_at(raw, expected):
    assert parse_published_at(raw) == expected


def test_dates_are_read_as_colombo_local_not_utc():
    """Both publishers date in Asia/Colombo and neither states an offset.

    Reading them naively as UTC would place every article 5.5 hours early, which
    on a midday story puts it before the market opened.
    """
    when = parse_published_at("11:12 am,Friday August 28, 2026")
    assert when.hour == 5 and when.minute == 42
    assert when.tzinfo is not None, "must be tz-aware for a timestamptz column"


def test_economynext_date_from_metadata():
    soup = BeautifulSoup(EN_ARTICLE, "lxml")
    assert extract_published_at(soup, EN) == datetime(
        2026, 8, 28, 5, 42, tzinfo=timezone.utc)


def test_ft_date_from_visible_element_because_there_is_no_metadata():
    """ft.lk publishes no article:published_time, no ld+json, no date meta."""
    soup = BeautifulSoup(FT_ARTICLE, "lxml")
    assert not soup.find_all("meta"), "the fixture must keep ft.lk's bare <head>"
    assert extract_published_at(soup, FT) == datetime(
        2026, 8, 25, 18, 30, tzinfo=timezone.utc)


def test_missing_date_is_none_not_now():
    """No date beats today's date: 'published_at' drives the dashboard ordering."""
    soup = BeautifulSoup("<html><body><p>no date here</p></body></html>", "lxml")
    assert extract_published_at(soup, FT) is None
    assert extract_published_at(soup, EN) is None


# ─────────────────────────────────────────────────────────────────────────────
# Symbol attribution
# ─────────────────────────────────────────────────────────────────────────────

def test_tokens_are_sequences_not_substrings():
    """All 273 base tickers are 3-4 letters and sit inside ordinary words.

    A substring search — ``if base in text`` — attributes ACL to any story
    containing "miracle" and AEL to any containing "fuel".
    """
    assert "acl" not in _tokens("a miracle recovery")
    assert _tokens("A MIRACLE recovery") == ["a", "miracle", "recovery"]
    assert _tokens("People's Leasing & Finance PLC") == [
        "people", "s", "leasing", "finance", "plc"]


@pytest.mark.parametrize("filed, must_include, must_exclude", [
    # Industry tails peel off, because that is how a headline names a company.
    ("SOFTLOGIC LIFE INSURANCE PLC",
     [["softlogic", "life", "insurance"], ["softlogic", "life"]], []),
    # The full filed name is always an identification, however generic its words
    # are one at a time. An earlier version tested the whole-name phrase the same
    # way it tests derived ones and produced NO phrase for 25 companies, among
    # them these four.
    ("UNION BANK OF COLOMBO PLC", [["union", "bank", "of", "colombo"]], []),
    ("UNION ASSURANCE PLC", [["union", "assurance"]], []),
    ("NATIONAL DEVELOPMENT BANK PLC", [["national", "development", "bank"]], []),
    ("PEOPLE'S INSURANCE PLC", [["people", "s", "insurance"]], []),
    # The catastrophic false positive: "sri lanka" appeared in 48 of the 60
    # stored headlines, so a derived phrase made only of place words attributed
    # nearly the whole news feed to SLTL.
    ("SRI LANKA TELECOM PLC",
     [["sri", "lanka", "telecom"]], [["sri", "lanka"]]),
    # Same rule, different placeholder set.
    ("PEOPLE'S LEASING & FINANCE PLC",
     [["people", "s", "leasing"]], [["people", "s"]]),
    # A group brand must not become a bare token: "sanasa" alone attributed a
    # Sanasa Life Insurance story to Sanasa Development Bank, a different listed
    # entity. MIN_DERIVED_TOKENS stops the peel at two.
    ("SANASA DEVELOPMENT BANK PLC",
     [["sanasa", "development", "bank"]], [["sanasa"]]),
    # Genuinely one-word companies are unaffected: the single token is the *full*
    # filed name, admitted by the other rule. MIN_SOLO_TOKEN is 4 to allow this.
    ("ODEL PLC", [["odel"]], []),
    ("HAYLEYS PLC", [["hayleys"]], []),
    # Real short forms survive: the derived test rejects all-GENERIC phrases, not
    # phrases containing an industry word.
    ("ASIAN HOTELS AND PROPERTIES PLC",
     [["asian", "hotels"]], []),
    # Nothing but a legal suffix identifies nothing.
    ("PLC", [], [["plc"]]),
])
def test_name_phrases(filed, must_include, must_exclude):
    phrases = name_phrases(filed)
    for want in must_include:
        assert want in phrases, f"{filed}: missing {want} from {phrases}"
    for unwanted in must_exclude:
        assert unwanted not in phrases, f"{filed}: {unwanted} must not be a phrase"


def test_name_phrases_are_longest_first():
    """match() takes the first hit per company, so order is the specificity rule."""
    phrases = name_phrases("SOFTLOGIC LIFE INSURANCE PLC")
    assert [len(p) for p in phrases] == sorted(
        (len(p) for p in phrases), reverse=True)


def test_every_real_company_name_yields_a_phrase():
    """293 of 293 companies in company_info have a usable phrase.

    This was 268 of 293 until the two rules were separated. A company with no
    phrase can never be attributed a story, silently.
    """
    filed = [
        "JOHN KEELLS HOLDINGS PLC", "UNION ASSURANCE PLC", "ODEL PLC",
        "UNION BANK OF COLOMBO PLC", "NATIONAL DEVELOPMENT BANK PLC",
        "PEOPLE'S INSURANCE PLC", "COMMERCIAL BANK OF CEYLON PLC",
        "ASIAN HOTELS AND PROPERTIES PLC", "CEYLON COLD STORES PLC",
        "CENTRAL FINANCE COMPANY PLC", "UNION CHEMICALS LANKA PLC",
        "CEYLON INVESTMENT PLC", "COLOMBO LAND & DEVELOPMENT COMPANY PLC",
        "LION BREWERY (CEYLON) PLC", "HAYLEYS PLC", "HEMAS HOLDINGS PLC",
        "AGSTAR PLC", "SRI LANKA TELECOM PLC", "EXPOLANKA HOLDINGS PLC",
    ]
    missing = [n for n in filed if not name_phrases(n)]
    assert missing == [], f"no usable phrase for {missing}"


# A matcher over a reduced company list, built the way SymbolMatcher.from_db
# builds one. Every name here is a real filed name from company_info.
COMPANIES = {
    "JKH.N0000": "JOHN KEELLS HOLDINGS PLC",
    "KHL.N0000": "JOHN KEELLS HOTELS PLC",
    "SAMP.N0000": "SAMPATH BANK PLC",
    "PLC.N0000": "PEOPLE'S LEASING & FINANCE PLC",
    "SLTL.N0000": "SRI LANKA TELECOM PLC",
    "NTB.N0000": "NATIONS TRUST BANK PLC",
    "NTB.X0000": "NATIONS TRUST BANK PLC",
    "SHL.N0000": "SOFTLOGIC HOLDINGS PLC",
    "AAIC.N0000": "SOFTLOGIC LIFE INSURANCE PLC",
    "ODEL.N0000": "ODEL PLC",
    "SDB.N0000": "SANASA DEVELOPMENT BANK PLC",
    "ACL.N0000": "ACL CABLES PLC",
}


@pytest.fixture
def matcher():
    phrases, by_base = {}, {}
    for symbol, filed in COMPANIES.items():
        p = name_phrases(filed)
        if p:
            phrases[symbol] = p
        by_base.setdefault(symbol.split(".")[0].upper(), []).append(symbol)
    return SymbolMatcher(phrases, by_base)


def test_match_by_company_name(matcher):
    hits = matcher.match("Sampath Bank honoured with three prestigious accolades")
    assert set(hits) == {"SAMP.N0000"}
    assert hits["SAMP.N0000"] == "name:sampath bank"


def test_match_by_ticker(matcher):
    hits = matcher.match("NTB opens latest conversion window for non-voting shares")
    # Both share classes: a story about Nations Trust Bank is about both listings,
    # and the ticker names the company, not one class of it.
    assert set(hits) == {"NTB.N0000", "NTB.X0000"}
    assert all(v == "ticker:NTB" for v in hits.values())


def test_generic_place_phrase_does_not_attribute_the_whole_feed(matcher):
    """The false positive that forced the design.

    "sri lanka" appears in 48 of the 60 stored headlines. Blind two-token prefixes
    of "SRI LANKA TELECOM PLC" therefore attributed nearly every article to SLTL,
    including "Sri Lanka's digital commerce landscape is growing: Visa".
    """
    assert matcher.match("Sri Lanka's digital commerce landscape is growing: Visa") == {}
    assert matcher.match("Sri Lanka rupee at 328.00/05 to US dollar") == {}
    # The full name still matches when a story really is about the company.
    assert "SLTL.N0000" in matcher.match("Sri Lanka Telecom posts higher profit")


def test_legal_suffix_is_not_a_ticker(matcher):
    """PEOPLE'S LEASING & FINANCE trades as PLC.N0000, and "PLC" is the legal
    suffix of nearly every listed company here — so an unguarded ticker match
    attributed "Assetline Finance PLC marks transformational year" to People's
    Leasing. Of the three base tickers appearing as capitalised tokens across the
    60 stored headlines (CDB, NTB, PLC), that was the only wrong one.
    """
    assert matcher.match("Assetline Finance PLC marks transformational year") == {}
    # The company itself is still reachable by name.
    assert "PLC.N0000" in matcher.match(
        "People's Leasing sets new benchmark in Corporate Reporting")


def test_ticker_matching_skipped_in_shouty_text(matcher):
    """In an all-caps headline every short word looks like a ticker."""
    assert matcher.match("ACL CABLES ANNOUNCES RESULTS").keys() <= {"ACL.N0000"}
    assert matcher.match("BREAKING NEWS FROM THE CSE TODAY") == {}


def test_substring_ticker_is_not_a_match(matcher):
    """ACL is inside "miracle"; token-sequence matching is what prevents this."""
    assert matcher.match("A miracle recovery for the tourism sector") == {}


def test_longest_match_wins_between_related_companies(matcher):
    """"john keells hotels" identifies KHL, so JKH is not also attributed.

    Six phrases in company_info are genuinely shared between different corporate
    entities ("aitken spence", "amana takaful", "c t", "capital alliance",
    "john keells", "richard pieris"); the other 28 shared phrases are one
    company's two share classes, where attributing both is correct.
    """
    hits = matcher.match("John Keells Hotels reports higher occupancy")
    assert set(hits) == {"KHL.N0000"}

    # With only the group name, the group holding company is the match.
    assert set(matcher.match("John Keells to invest in new venture")) == {"JKH.N0000"}


def test_longest_match_distinguishes_softlogic_entities(matcher):
    """Softlogic Life Insurance and Softlogic Holdings are separate listings."""
    assert set(matcher.match("Softlogic Life targets investment-grade rating")) == {
        "AAIC.N0000"}
    assert set(matcher.match("Softlogic Holdings, Odel continue restructure")) == {
        "SHL.N0000", "ODEL.N0000"}


def test_group_brand_does_not_leak_to_a_sibling_listing(matcher):
    """A bare "sanasa" attributed a Sanasa Life story to Sanasa Development Bank.

    Different listed entities sharing a group brand. MIN_DERIVED_TOKENS = 2 is
    what prevents it, and Sanasa Life is not a CSE listing at all — so the correct
    answer here is no attribution, not a plausible one.
    """
    assert matcher.match("Sanasa Life targets investment-grade rating") == {}
    assert set(matcher.match("Sanasa Development Bank posts higher profit")) == {
        "SDB.N0000"}


def test_market_wide_stories_match_nothing(matcher):
    """A rupee fixing or a T-bill auction genuinely names no listed company.

    These become one GENERAL row, which is a claim about the article rather than
    an admission of failure — the distinction the old pipeline could not make,
    because it labelled all 60 rows GENERAL without reading any of them.
    """
    for headline in [
        "Sri Lanka rupee at 328.00/05 to US dollar, bond yields steady",
        "T-Bill yields continue downward trajectory for sixth week",
        "CBSL seeks liquidators for failed banks, finance companies",
        "Bullish outcome at Rs. 50 b T-Bond auction",
    ]:
        assert matcher.match(headline) == {}, headline


def test_general_symbol_is_a_claim_not_a_fallback():
    """Before I-08 every row was GENERAL, so the label carried no information."""
    assert GENERAL_SYMBOL == "GENERAL"
