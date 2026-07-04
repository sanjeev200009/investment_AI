# tasks/scrape_tasks.py
"""
Background scraping, sentiment analysis, and embedding pipeline.

Task chain on each run:
  scrape_cse_data → store_market_data
  scrape_news      → analyse_sentiment → embed_news_articles
"""

from __future__ import annotations

import asyncio
import logging

from celery_worker import celery_app

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CSE market data
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="tasks.scrape_tasks.scrape_cse_data")
def scrape_cse_data(self):
    """
    Scrape the CSE trade summary and persist new rows to market_data.
    Runs every 15 min during market hours via Celery Beat.
    """
    try:
        asyncio.run(_async_scrape_cse())
    except Exception as exc:
        logger.exception("scrape_cse_data failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


async def _async_scrape_cse():
    from app.database import SessionLocal
    from app.models.stock import MarketData
    from app.services.scraper import scrape_cse_data, validate_market_record

    db = SessionLocal()
    try:
        records = await scrape_cse_data()
        inserted = 0
        for rec in records:
            if not validate_market_record(rec):
                continue
            row = MarketData(
                symbol=rec["symbol"],
                price=rec["last_price"],
                change=rec.get("change"),
                change_pct=rec.get("change_pct"),
                volume=rec.get("volume"),
                market_cap=rec.get("market_cap"),
            )
            db.add(row)
            inserted += 1
        db.commit()
        logger.info("CSE scrape: inserted %d market_data rows", inserted)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# News + sentiment + embeddings
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="tasks.scrape_tasks.scrape_and_analyse_news")
def scrape_and_analyse_news(self, symbol: str | None = None):
    """
    Full pipeline: scrape → sentiment → embed.
    Optionally scoped to a single symbol for on-demand enrichment.
    """
    try:
        new_ids = asyncio.run(_async_scrape_news(symbol))
        if new_ids:
            analyse_sentiment_batch.delay(new_ids)
    except Exception as exc:
        logger.exception("scrape_and_analyse_news failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


async def _async_scrape_news(symbol: str | None) -> list[int]:
    from app.database import SessionLocal
    from app.models.stock import NewsSentiment
    from app.services.scraper import scrape_news, validate_news_record

    db = SessionLocal()
    new_ids = []
    try:
        articles = await scrape_news(symbol)
        for art in articles:
            if not validate_news_record(art):
                continue
            # Dedup by URL
            existing = (
                db.query(NewsSentiment)
                .filter(NewsSentiment.url == art["url"])
                .first()
            )
            if existing:
                continue
            row = NewsSentiment(
                symbol=art.get("symbol") or (symbol or "GENERAL"),
                headline=art["title"],
                url=art["url"],
                source=art.get("source"),
                summary=art.get("summary"),
                published_at=art.get("published_at"),
            )
            db.add(row)
            db.flush()  # get the news_id before commit
            new_ids.append(row.news_id)
        db.commit()
        logger.info("News scrape: inserted %d new articles", len(new_ids))
    finally:
        db.close()
    return new_ids


@celery_app.task(bind=True, max_retries=2, name="tasks.scrape_tasks.analyse_sentiment_batch")
def analyse_sentiment_batch(self, news_ids: list[int]):
    """
    Run VADER sentiment + optional LLM summarisation on a batch of news rows.
    Then kick off embedding generation.
    """
    try:
        asyncio.run(_async_analyse_sentiment(news_ids))
        embed_news_articles.delay(news_ids)
    except Exception as exc:
        logger.exception("analyse_sentiment_batch failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


async def _async_analyse_sentiment(news_ids: list[int]):
    from app.database import SessionLocal
    from app.models.stock import NewsSentiment
    from app.services.sentiment import analyse_text

    db = SessionLocal()
    try:
        rows = (
            db.query(NewsSentiment)
            .filter(NewsSentiment.news_id.in_(news_ids))
            .all()
        )
        for row in rows:
            text = f"{row.headline}. {row.summary or ''}"
            score, label = await analyse_text(text)
            row.sentiment_score = score
            row.sentiment_label = label
        db.commit()
        logger.info("Sentiment analysis complete for %d articles", len(rows))
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, name="tasks.scrape_tasks.embed_news_articles")
def embed_news_articles(self, news_ids: list[int]):
    """
    Generate NVIDIA NIM embeddings for news rows and store them in pgvector.
    """
    try:
        count = asyncio.run(_async_embed(news_ids))
        logger.info("Embedded %d news articles", count)
    except Exception as exc:
        logger.exception("embed_news_articles failed: %s", exc)
        raise self.retry(exc=exc, countdown=90)


async def _async_embed(news_ids: list[int]) -> int:
    from app.database import SessionLocal
    from app.services.agent.embeddings import embed_and_store_news

    db = SessionLocal()
    try:
        return await embed_and_store_news(news_ids, db)
    finally:
        db.close()
