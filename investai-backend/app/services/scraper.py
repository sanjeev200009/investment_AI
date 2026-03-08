"""
Web Scraping Pipeline for InvestAI
Handles CSE stock data and financial news scraping.
"""

import httpx
import logging
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  CSE Scraper
# ─────────────────────────────────────────────

CSE_TRADE_SUMMARY_URL = "https://www.cse.lk/pages/trade-summary/trade-summary.component.html"

NEWS_SOURCES = [
    "https://www.marketwatch.com/investing",
    "https://www.investing.com/news/stock-market-news",
    "https://www.ft.lk/financial-news",          # Lanka Financial Times
    "https://www.dailymirror.lk/business/",       # Daily Mirror Business
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


async def scrape_cse_data() -> list[dict]:
    """
    Scrapes the CSE trade summary page.
    Returns a list of dicts with keys:
        symbol, company_name, last_price, change, change_pct, volume, market_cap, scraped_at
    """
    results = []

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
            response = await client.get(CSE_TRADE_SUMMARY_URL)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # CSE trade summary table rows
        table = soup.find("table", {"id": "trade-summary-table"})
        if not table:
            # Fallback: find any table with stock-like headers
            table = soup.find("table")

        if not table:
            logger.warning("CSE: Could not find trade summary table.")
            return results

        rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 6:
                continue

            try:
                record = {
                    "symbol":       _clean(cols[0].text),
                    "company_name": _clean(cols[1].text),
                    "last_price":   _to_float(cols[2].text),
                    "change":       _to_float(cols[3].text),
                    "change_pct":   _to_float(cols[4].text.replace("%", "")),
                    "volume":       _to_int(cols[5].text),
                    "market_cap":   _to_float(cols[6].text) if len(cols) > 6 else None,
                    "scraped_at":   datetime.utcnow().isoformat(),
                }

                # Basic validation: skip rows with no price
                if record["last_price"] is None or record["symbol"] == "":
                    continue

                results.append(record)

            except Exception as row_err:
                logger.debug("CSE row parse error: %s", row_err)
                continue

        logger.info("CSE scraper: fetched %d stock records.", len(results))

    except httpx.HTTPStatusError as e:
        logger.error("CSE HTTP error %s: %s", e.response.status_code, e)
    except httpx.RequestError as e:
        logger.error("CSE request error: %s", e)
    except Exception as e:
        logger.error("CSE unexpected error: %s", e)

    return results


# ─────────────────────────────────────────────
#  News Scraper
# ─────────────────────────────────────────────

async def scrape_news(symbol: Optional[str] = None) -> list[dict]:
    """
    Scrapes financial news headlines from configured sources.
    Optionally filter articles that mention a specific stock symbol.
    Returns a list of dicts with keys:
        title, url, source, summary, published_at, symbol (if matched), scraped_at
    """
    all_articles = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        for source_url in NEWS_SOURCES:
            articles = await _scrape_single_news_source(client, source_url, symbol)
            all_articles.extend(articles)

    # Deduplicate by URL
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)

    logger.info("News scraper: fetched %d unique articles.", len(unique_articles))
    return unique_articles


async def _scrape_single_news_source(
    client: httpx.AsyncClient,
    source_url: str,
    symbol: Optional[str]
) -> list[dict]:
    """Scrapes a single news source and returns parsed articles."""
    articles = []

    try:
        response = await client.get(source_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Generic extraction: look for <article> tags or <h2>/<h3> inside common wrappers
        raw_items = (
            soup.find_all("article")
            or soup.find_all("div", class_=lambda c: c and "article" in c.lower())
            or soup.find_all("li", class_=lambda c: c and "article" in c.lower())
        )

        for item in raw_items[:20]:  # Cap at 20 per source
            title_tag = item.find(["h1", "h2", "h3", "h4"])
            link_tag  = item.find("a", href=True)
            summary_tag = item.find("p")

            title   = _clean(title_tag.text) if title_tag else ""
            url     = _resolve_url(source_url, link_tag["href"]) if link_tag else source_url
            summary = _clean(summary_tag.text) if summary_tag else ""

            if not title:
                continue

            # If filtering by symbol, skip unrelated articles
            if symbol and symbol.upper() not in (title + summary).upper():
                continue

            articles.append({
                "title":        title,
                "url":          url,
                "source":       source_url,
                "summary":      summary[:300],   # Truncate for DB
                "published_at": _extract_date(item),
                "symbol":       symbol or None,
                "scraped_at":   datetime.utcnow().isoformat(),
            })

    except httpx.HTTPStatusError as e:
        logger.warning("News source %s returned HTTP %s", source_url, e.response.status_code)
    except httpx.RequestError as e:
        logger.warning("News source %s request error: %s", source_url, e)
    except Exception as e:
        logger.warning("News source %s parse error: %s", source_url, e)

    return articles


# ─────────────────────────────────────────────
#  Data Validation
# ─────────────────────────────────────────────

def validate_market_record(record: dict) -> bool:
    """
    Validates a CSE market data record before DB insert.
    Returns True if valid, False otherwise.
    """
    if not record.get("symbol"):
        return False
    if record.get("last_price") is None or record["last_price"] <= 0:
        return False
    if not isinstance(record.get("volume"), int):
        return False
    return True


def validate_news_record(record: dict) -> bool:
    """
    Validates a news article record before DB insert.
    Returns True if valid, False otherwise.
    """
    if not record.get("title") or len(record["title"]) < 5:
        return False
    if not record.get("url"):
        return False
    return True


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _clean(text: str) -> str:
    return " ".join(text.split()).strip()


def _to_float(text: str) -> Optional[float]:
    try:
        return float(text.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _to_int(text: str) -> Optional[int]:
    try:
        return int(text.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _resolve_url(base: str, href: str) -> str:
    if href.startswith("http"):
        return href
    from urllib.parse import urljoin
    return urljoin(base, href)


def _extract_date(tag) -> Optional[str]:
    """Try to extract a published date from time/meta tags."""
    time_tag = tag.find("time")
    if time_tag and time_tag.get("datetime"):
        return time_tag["datetime"]
    return None