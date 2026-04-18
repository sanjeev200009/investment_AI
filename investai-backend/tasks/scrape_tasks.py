# tasks/scrape_tasks.py
from celery_worker import celery_app


@celery_app.task(bind=True, max_retries=3)
def scrape_stock_news(self, symbol: str):
    """Scrape latest news for a given stock symbol."""
    try:
        from app.services.scraper import NewsScraper
        scraper = NewsScraper()
        results = scraper.fetch_news(symbol)
        return {"symbol": symbol, "articles": len(results)}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
