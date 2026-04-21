"""
Web Scraping Pipeline for InvestAI
Handles CSE stock data and financial news scraping with DB persistence.
"""
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.models.stock import MarketData, NewsSentiment
from app.database import SessionLocal

logger = logging.getLogger(__name__)

CSE_TRADE_SUMMARY_URL = "https://www.cse.lk/api/tradeSummary"
CSE_MARKET_STATUS_URL = "https://www.cse.lk/api/marketStatus"


NEWS_SOURCES = [
    "https://www.ft.lk/Financial-Services/42",
    "https://www.dailymirror.lk/business",
    "https://economynext.com/markets/",
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

CSE_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.cse.lk",
    "Referer": "https://www.cse.lk/equity/trade-summary",
}

# ■■ CSE Scraper ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
async def scrape_and_save_cse(db: Session) -> int:
    """Scrape CSE data and upsert into market_data table."""
    records = await scrape_cse_data()
    saved = 0
    for rec in records:
        row = MarketData(
            symbol=rec['symbol'],
            price=rec['last_price'],
            change=rec.get('change'),
            change_pct=rec.get('change_pct'),
            volume=rec.get('volume'),
            market_cap=rec.get('market_cap'),
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(row)
        saved += 1
    db.commit()
    logger.info('Saved %d CSE records', saved)
    return saved

async def scrape_cse_data() -> list[dict]:
    """Returns list of stock dicts from CSE trade summary API."""
    results = []
    try:
        async with httpx.AsyncClient(headers=CSE_HEADERS, timeout=60) as c:
            response = await c.post(CSE_TRADE_SUMMARY_URL)
            response.raise_for_status()
            data = response.json()
            
            raw_records = data.get('reqTradeSummery', [])
            for rec in raw_records:
                try:
                    results.append({
                        'symbol': rec.get('symbol', '').strip(),
                        'last_price': float(rec.get('price', 0)),
                        'change': float(rec.get('change', 0)),
                        'change_pct': float(rec.get('percentageChange', 0)),
                        'volume': float(rec.get('sharevolume', 0)),
                        'market_cap': float(rec.get('marketCap', 0)) if rec.get('marketCap') else None,
                    })
                except (ValueError, TypeError) as e:
                    logger.debug('Record parse error: %s', e)
    except Exception as e:
        logger.error('CSE scrape failed: %s', e)

    if not results:
        status = await get_market_status()
        if status:
            logger.info('Market is currently in "%s" status - No trade records available yet.', status)
        else:
            logger.warning('No CSE trade records found and market status could not be determined.')
            
    return results

async def get_market_status() -> Optional[str]:
    """Checks the current status of the CSE market."""
    try:
        async with httpx.AsyncClient(headers=CSE_HEADERS, timeout=10) as c:
            r = await c.post(CSE_MARKET_STATUS_URL)
            if r.status_code == 200:
                return r.json().get('status')
    except Exception as e:
        logger.debug('Failed to fetch market status: %s', e)
    return None

# ■■ News Scraper ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
async def scrape_and_save_news(db: Session, symbol: str = None) -> int:
    """Scrape news and save to news_sentiment table, deduplicating by URL."""
    articles = await scrape_news(symbol)
    saved = 0
    for art in articles:
        existing = db.query(NewsSentiment).filter(
            NewsSentiment.url == art['url']
        ).first()
        if existing: continue

        row = NewsSentiment(
            symbol=art.get('symbol') or symbol or 'GENERAL',
            headline=art['title'][:500],
            url=art['url'][:1000],
            source=art.get('source', '')[:120],
            summary=art.get('summary', '')[:500],
            published_at=None,
        )
        db.add(row)
        saved += 1
    db.commit()
    logger.info('Saved %d news articles', saved)
    return saved

async def scrape_news(symbol: str = None) -> list[dict]:
    all_articles = []
    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=30) as client:
        for src in NEWS_SOURCES:
            arts = await _scrape_single_news_source(client, src, symbol)
            all_articles.extend(arts)

    seen, unique = set(), []
    for a in all_articles:
        if a['url'] not in seen:
            seen.add(a['url'])
            unique.append(a)
    return unique

async def _scrape_single_news_source(client, source_url, symbol):
    articles = []
    try:
        r = await client.get(source_url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'lxml')
        # Daily Mirror and FT often use <h3> for headlines within an <a> tag
        # EconomyNext uses <h3><a>
        headlines = soup.find_all('h3')
        for h3 in headlines[:20]:
            title = _clean(h3.text)
            if not title: continue
            
            # Find the link: usually it's the parent or a child <a>
            link_tag = h3.find('a', href=True) or h3.find_parent('a', href=True)
            if not link_tag: continue
            
            url = _resolve_url(source_url, link_tag['href'])
            
            # Try to find a summary nearby (p tag)
            summary_tag = h3.find_next('p') or h3.find_parent().find_next('p')
            summary = _clean(summary_tag.text)[:300] if summary_tag else ''

            if symbol and symbol.upper() not in (title + summary).upper():
                continue

            articles.append({
                'title': title,
                'url': url,
                'source': source_url,
                'summary': summary,
                'symbol': symbol or None
            })
    except Exception as e:
        logger.warning('Source %s failed: %s', source_url, e)
    return articles

# ■■ Helpers ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
def _clean(t): return ' '.join(t.split()).strip()

def _to_float(t):
    try: return float(t.replace(',','').strip())
    except: return None

def _resolve_url(base, href):
    if href.startswith('http'): return href
    from urllib.parse import urljoin
    return urljoin(base, href)