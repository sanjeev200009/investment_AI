# tasks/scrape_tasks.py
import asyncio
import logging
from celery_worker import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3,
                name='tasks.scrape_tasks.scrape_cse_market_data')
def scrape_cse_market_data(self):
    """Periodic task: scrape CSE live prices and save to DB."""
    try:
        from app.services.scraper import scrape_and_save_cse
        db = SessionLocal()
        try:
            count = asyncio.run(scrape_and_save_cse(db))
            logger.info('CSE task: saved %d records', count)
            return {'status': 'ok', 'saved': count}
        finally:
            db.close()
    except Exception as exc:
        logger.error('CSE task failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)

@celery_app.task(bind=True, max_retries=3, name='tasks.scrape_tasks.scrape_all_news')
def scrape_all_news(self):
    """Periodic task: scrape news + run sentiment + save to DB."""
    try:
        from app.services.scraper import scrape_and_save_news
        from app.services.sentiment import score_unseen_news
        db = SessionLocal()
        try:
            saved = asyncio.run(scrape_and_save_news(db))
            scored = score_unseen_news(db)
            return {'status': 'ok', 'saved': saved, 'scored': scored}
        finally:
            db.close()
    except Exception as exc:
        logger.error('News task failed: %s', exc)
        raise self.retry(exc=exc, countdown=120)

@celery_app.task(bind=True, max_retries=3)
def scrape_stock_news(self, symbol: str):
    """On-demand: scrape news for a specific symbol."""
    try:
        from app.services.scraper import scrape_and_save_news
        from app.services.sentiment import score_unseen_news
        db = SessionLocal()
        try:
            saved = asyncio.run(scrape_and_save_news(db, symbol=symbol))
            scored = score_unseen_news(db, symbol=symbol)
            return {'symbol': symbol, 'saved': saved, 'scored': scored}
        finally:
            db.close()
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
