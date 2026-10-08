# tasks/scrape_tasks.py
"""
Background scraping, sentiment analysis, and embedding pipeline.

Task chain on each run:
  scrape_cse_data    → store_market_data
  scrape_cse_indices → store index readings
  scrape_news        → analyse_sentiment → embed_news_articles
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
    from app.services.scraper import scrape_and_save_cse

    db = SessionLocal()
    try:
        inserted = await scrape_and_save_cse(db)
        logger.info("CSE scrape: inserted %d market_data rows", inserted)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# CSE index readings
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="tasks.scrape_tasks.scrape_cse_indices")
def scrape_cse_indices(self):
    """
    Scrape ASPI, S&P SL20 and the 20 industry-group indices into market_index.

    A separate task from scrape_cse_data rather than a second step inside it,
    even though both run on the same schedule against the same host. They read
    different endpoints, so one being down or slow should not cost the other its
    run — and retrying a combined task would re-scrape the half that already
    succeeded.
    """
    try:
        asyncio.run(_async_scrape_indices())
    except Exception as exc:
        logger.exception("scrape_cse_indices failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


async def _async_scrape_indices():
    from app.database import SessionLocal
    from app.services.scraper import scrape_and_save_indices

    db = SessionLocal()
    try:
        accepted = await scrape_and_save_indices(db)
        logger.info("CSE index scrape: %d index readings accepted", accepted)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio valuation snapshots
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3,
                 name="tasks.scrape_tasks.snapshot_portfolio_values")
def snapshot_portfolio_values(self):
    """
    Record what every portfolio is worth today, into portfolio_snapshots.

    Not folded into scrape_cse_data the way daily_close was, and the asymmetry is
    deliberate. daily_close belongs in the scrape because it is a projection of
    exactly what the scrape just fetched, and running it more often only sharpens
    the result. A valuation is a statement about a calendar day and needs to be
    taken once, after the close — running it every 15 minutes would rewrite the
    day's row all afternoon with intraday values, so the number a user saw at
    lunchtime would not be the one recorded.

    Scheduled after the 14:30 Colombo close. It writes a row every day it runs,
    including weekends: a portfolio really is worth something on a Saturday, and
    the snapshot's priced_at says which session's prices that value came from.

    Not a retry-on-any-failure loop over portfolios — one query values all of
    them, so a failure is a database failure and retrying the whole task is right.
    """
    try:
        _snapshot_portfolios()
    except Exception as exc:
        logger.exception("snapshot_portfolio_values failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


def _snapshot_portfolios():
    from app.database import SessionLocal
    from app.services.portfolio_history import snapshot_portfolios

    db = SessionLocal()
    try:
        written = snapshot_portfolios(db)
        logger.info("Portfolio snapshots: %d portfolios valued", written)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3,
                 name="tasks.scrape_tasks.snapshot_recommendations")
def snapshot_recommendations(self):
    """Evaluation plan E5: store today's top recommendations per risk category."""
    from app.database import SessionLocal
    from app.services.recommendations import snapshot_recommendations as snap

    db = SessionLocal()
    try:
        logger.info("Recommendation snapshots: %d rows", snap(db))
    except Exception as exc:
        db.rollback()
        logger.exception("snapshot_recommendations failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Company fundamentals
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=2,
                 name="tasks.scrape_tasks.refresh_company_info")
def refresh_company_info(self, symbols: list[str] | None = None):
    """
    Refresh company_info: sector, market cap, 52-week range, shares issued, beta.

    Daily, not every 15 minutes like the quote scrape. These fields change on
    corporate-action timescales — a share issue, a sector reclassification — so
    re-fetching them intraday would cost 582 HTTP requests to rewrite the same
    values. Daily is already more often than the data changes; it is that often
    only so a newly listed symbol picks up a name and sector within a day.

    ``symbols`` is optional and exists for the on-demand case: a symbol that
    appears in the trade summary for the first time can be filled immediately
    rather than waiting for the nightly sweep.

    Retries twice rather than three times, with a long backoff. A failure here
    degrades gracefully — the previous sweep's rows are still in the table and the
    UI shows slightly stale fundamentals — so this is not worth hammering cse.lk
    over. Contrast the quote scrape, where a missed run is a permanent hole in the
    price history.
    """
    try:
        asyncio.run(_async_refresh_company_info(symbols))
    except Exception as exc:
        logger.exception("refresh_company_info failed: %s", exc)
        raise self.retry(exc=exc, countdown=600)


async def _async_refresh_company_info(symbols: list[str] | None):
    from app.database import SessionLocal
    from app.services.company_info import refresh_company_info as refresh

    db = SessionLocal()
    try:
        written = await refresh(db, symbols)
        logger.info("Company info refresh: %d rows written", written)
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Price predictions
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=2,
                 name="tasks.scrape_tasks.update_price_predictions")
def update_price_predictions(self):
    """
    Write one price_predictions row per symbol with enough daily_close history.

    Runs after the daily portfolio snapshot (15:10) so it reads the day's final
    close. The model is a least-squares trend extrapolation — see
    app/services/predictor.py for why that is the honest choice for a series
    this young — and the agent's get_price_prediction tool reads the latest row
    per symbol. Until this task existed the table was written by nothing and
    the tool errored on every call (I-16).
    """
    try:
        from app.database import SessionLocal
        from app.services.predictor import update_predictions

        db = SessionLocal()
        try:
            written = update_predictions(db)
            logger.info("Price predictions: %d rows written", written)
        finally:
            db.close()
    except Exception as exc:
        logger.exception("update_price_predictions failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


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
    from app.services.scraper import scrape_and_save_news

    db = SessionLocal()
    try:
        new_ids = await scrape_and_save_news(db, symbol)
        logger.info("News scrape: inserted %d new articles", len(new_ids))
        return new_ids
    finally:
        db.close()


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
    """Summarise each article, then score the sentiment of the real text.

    Two changes from what this did before I-08, and the order between them
    matters.

    **``summarise_article`` is now called.** It existed in
    ``app/services/sentiment.py`` and was invoked from nowhere — the LLM summary
    the plan called for was written, tested by
    ``scripts/verify_llm_providers.py``, and never reached the database.

    **Sentiment is scored on the article body, not on ``summary``.** The old line
    was ``f"{row.headline}. {row.summary or ''}"``, and ``summary`` was the
    literal string "Editorial :" on every stored row, so VADER was scoring a
    footer contact block. Scoring the body rather than the LLM's summary is
    deliberate even now that the summary is real: VADER is a lexicon counter, so
    it wants the author's own words and their volume, not a paraphrase that has
    had the affect compressed out of it.

    A failed summary is not a failed row. ``summarise_article`` returns None when
    every LLM provider is unavailable — routine on a free tier — and the lede that
    ``news.py`` already stored stays in place, so the row keeps a real summary and
    still gets scored.
    """
    from app.database import SessionLocal
    from app.models.stock import NewsSentiment
    from app.services.sentiment import analyse_text, summarise_article

    db = SessionLocal()
    try:
        rows = (
            db.query(NewsSentiment)
            .filter(NewsSentiment.news_id.in_(news_ids))
            .all()
        )
        summarised = 0
        for row in rows:
            body = row.body or ""
            if body:
                summary = await summarise_article(row.headline, body)
                if summary:
                    row.summary = summary.strip()
                    summarised += 1

            # Headline first, then the body: a headline is written to carry the
            # sentiment of the story, so it should not be diluted by 2,000
            # characters of neutral reporting. The body is capped for the same
            # reason — VADER's compound score is length-normalised, and a long
            # article of factual prose drags any signal toward zero.
            text = f"{row.headline}. {body[:1500]}" if body else row.headline
            score, label = await analyse_text(text)
            row.sentiment_score = score
            row.sentiment_label = label
        db.commit()
        logger.info("Sentiment analysis complete for %d articles (%d summarised)",
                    len(rows), summarised)
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


# ─────────────────────────────────────────────────────────────────────────────
# Housekeeping
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.scrape_tasks.purge_expired_credentials")
def purge_expired_credentials():
    """Delete login codes and reset tokens that expired over a day ago.

    Nothing else ever removed them, so otp_codes kept every code since April.
    """
    from app.database import SessionLocal
    from app.services.otp import purge_expired_otps
    from app.utils.security import purge_expired_reset_tokens

    db = SessionLocal()
    try:
        otps, tokens = purge_expired_otps(db), purge_expired_reset_tokens(db)
        logger.info("Purged %d expired OTP codes and %d reset tokens", otps, tokens)
    finally:
        db.close()


@celery_app.task(name="tasks.scrape_tasks.market_session_notice")
def market_session_notice(event: str):
    """Tell every user the CSE has opened ("market_open") or closed ("market_close")."""
    from app.database import SessionLocal
    from app.services.notification_service import notify_market_session
    from app.services.scraper import get_market_status

    status = asyncio.run(get_market_status()) if event == "market_open" else None
    db = SessionLocal()
    try:
        sent = notify_market_session(db, event, status)
        logger.info("%s notice: %d users (cse status %r)", event, sent, status)
    finally:
        db.close()
