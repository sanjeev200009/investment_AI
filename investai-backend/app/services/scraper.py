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

CSE_TRADE_SUMMARY_URL = (
"https://www.cse.lk/pages/trade-summary/trade-summary.component.html"
)

NEWS_SOURCES = [
"https://www.ft.lk/financial-news",
"https://www.dailymirror.lk/business/",
"https://economynext.com/sri-lanka-stock-market/",
]

HEADERS = {
"User-Agent": (
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
),
"Accept-Language": "en-US,en;q=0.9",
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
    """Returns list of stock dicts from CSE trade summary."""
    results = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30) as c:
            response = await c.get(CSE_TRADE_SUMMARY_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            table = soup.find('table') or soup.find('table', {'class': True})
            if not table:
                logger.warning('CSE: no table found')
                return results

            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) < 6: continue
                try:
                    rec = {
                        'symbol': _clean(cols[0].text),
                        'last_price': _to_float(cols[2].text),
                        'change': _to_float(cols[3].text),
                        'change_pct': _to_float(cols[4].text.replace('%','')),
                        'volume': _to_float(cols[5].text),
                        'market_cap': _to_float(cols[6].text) if len(cols)>6 else None,
                    }
                    if rec['last_price'] and rec['symbol']:
                        results.append(rec)
                except Exception as e:
                    logger.debug('Row parse error: %s', e)
    except Exception as e:
        logger.error('CSE scrape failed: %s', e)
    return results

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
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
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
        items = (soup.find_all('article') or
                 soup.find_all('div', class_=lambda c: c and 'article' in c.lower()))

        for item in items[:20]:
            title_tag = item.find(['h1','h2','h3','h4'])
            link_tag = item.find('a', href=True)
            summary_t = item.find('p')

            title = _clean(title_tag.text) if title_tag else ''
            url = _resolve_url(source_url, link_tag['href']) if link_tag else source_url
            summary = _clean(summary_t.text)[:300] if summary_t else ''

            if not title: continue
            if symbol and symbol.upper() not in (title+summary).upper(): continue

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