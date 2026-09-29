"""News feeds (Google News RSS, LBO RSS, CSE financial reports), offline."""

import asyncio
from datetime import datetime, timezone

import httpx

from app.services import news

GOOGLE = """<?xml version="1.0"?><rss><channel>
<item><title>ASPI gains as banks lead turnover on the Colombo bourse - Daily FT</title>
<link>https://news.google.com/rss/articles/abc</link>
<pubDate>Tue, 29 Sep 2026 06:10:00 GMT</pubDate>
<description>&lt;a href="x"&gt;ASPI gains as banks lead turnover on the Colombo bourse&lt;/a&gt;</description>
<source url="https://www.ft.lk">Daily FT</source></item>
<item><title>Short - X</title><link>https://news.google.com/rss/articles/short</link></item>
</channel></rss>"""

LBO = """<?xml version="1.0"?><rss><channel>
<item><title>Commercial Bank posts higher quarterly profit on interest income</title>
<link>https://www.lankabusinessonline.com/comb-profit/</link>
<pubDate>Tue, 29 Sep 2026 08:00:00 +0530</pubDate>
<description>&lt;p&gt;Commercial Bank of Ceylon reported a rise in profit for the quarter.&lt;/p&gt;</description></item>
</channel></rss>"""

CSE = {"reqFinancialAnnouncemnets": [{
    "path": "cmt/upload_report_file/401_1790245947732.pdf", "uploadedDate": "24 Sep 2026 04:02:27 PM",
    "fileText": "Annual Report as at 31st March 2026", "name": "LANKA REALTY INVESTMENTS PLC", "symbol": "ASCO"}]}


def test_parse_rss_strips_publisher_suffix_and_duplicate_description():
    items = news.parse_rss(GOOGLE)
    assert items[0]["title"] == "ASPI gains as banks lead turnover on the Colombo bourse"
    assert items[0]["source"] == "Daily FT" and items[0]["body"] == ""
    assert items[0]["published_at"] == datetime(2026, 9, 29, 6, 10, tzinfo=timezone.utc)


def test_cse_financial_reports_link_the_real_pdf_in_utc():
    [item] = news.cse_financial_records(CSE)
    assert item["url"] == "https://cdn.cse.lk/cmt/upload_report_file/401_1790245947732.pdf"
    assert item["title"] == "Lanka Realty Investments Plc: Annual Report as at 31st March 2026"
    assert item["published_at"] == datetime(2026, 9, 24, 10, 32, 27, tzinfo=timezone.utc)


def test_fetch_feed_articles_merges_sources_and_skips_known_and_short():
    def handler(request):
        if "news.google.com" in str(request.url):
            return httpx.Response(200, text=GOOGLE)
        if "lankabusinessonline" in str(request.url):
            return httpx.Response(200, text=LBO)
        return httpx.Response(200, json=CSE)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await news.fetch_feed_articles(
                client, known_urls={"https://www.lankabusinessonline.com/comb-profit/"})

    arts = asyncio.run(run())
    assert [a["source"] for a in arts] == ["Daily FT", "CSE"]   # LBO item already known, short one dropped
    assert all(news.validate_news_record(a) for a in arts)


def test_one_feed_down_does_not_stop_the_others():
    def handler(request):
        if "news.google.com" in str(request.url):
            return httpx.Response(503)
        if "lankabusinessonline" in str(request.url):
            return httpx.Response(200, text=LBO)
        return httpx.Response(500)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await news.fetch_feed_articles(client)

    arts = asyncio.run(run())
    assert [a["source"] for a in arts] == ["LBO"]
