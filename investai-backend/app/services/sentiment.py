# app/services/sentiment.py
"""
Sentiment analysis service.
Two-tier approach:
  1. VADER (fast, local, free) — scores -1.0 to +1.0
  2. LLM summary (optional, higher quality) — only for articles without a summary
"""

from __future__ import annotations

import logging

from app.services import llm

logger = logging.getLogger(__name__)

_vader_analyser = None


def _get_vader():
    global _vader_analyser
    if _vader_analyser is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _vader_analyser = SentimentIntensityAnalyzer()
        _vader_analyser.lexicon.update(MARKET_LEXICON)
    return _vader_analyser


# VADER is tuned on social media and has no sense of market direction: "CSE
# continues slide, falls 0.6% to new six-month low" scored +0.38 because the
# body's "active" and "winners" outweighed it. Valences on VADER's -4..+4 scale.
MARKET_LEXICON = {
    "slide": -1.8, "slides": -1.8, "falls": -1.8, "fell": -1.8, "fall": -1.5,
    "drop": -1.5, "drops": -1.5, "dropped": -1.5, "decline": -1.6, "declines": -1.6,
    "declined": -1.6, "plunge": -2.5, "plunges": -2.5, "plunged": -2.5, "slump": -2.2,
    "slumps": -2.2, "tumble": -2.2, "tumbles": -2.2, "losers": -1.5, "selloff": -2.0,
    "sell-off": -2.0, "bearish": -2.0, "down": -1.0,
    "gain": 1.5, "gains": 1.5, "gained": 1.5, "rise": 1.5, "rises": 1.5, "rose": 1.5,
    "rally": 2.0, "rallies": 2.0, "rebound": 1.6, "rebounds": 1.6, "surge": 2.2,
    "surges": 2.2, "bullish": 2.0, "up": 0.8,
}


async def analyse_text(text: str) -> tuple[float, str]:
    """
    Returns (score, label).
    score: float -1.0 (very negative) to +1.0 (very positive)
    label: 'positive' | 'neutral' | 'negative'
    """
    try:
        analyser = _get_vader()
        scores = analyser.polarity_scores(text)
        compound = scores["compound"]

        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        return round(compound, 4), label
    except Exception as e:
        logger.warning("VADER analysis failed: %s", e)
        return 0.0, "neutral"


async def summarise_article(headline: str, body: str) -> str | None:
    """
    Use the LLM to produce a 1-2 sentence plain-English summary of a news article.
    Returns None if the LLM call fails (caller should keep original text).
    """
    prompt = (
        f"Summarise this financial news article in 1-2 plain sentences "
        f"suitable for a beginner investor in Sri Lanka. "
        f"Focus on the practical impact. Reply with the summary only.\n\n"
        f"Headline: {headline}\n\n"
        f"Article: {body[:1000]}"
    )
    # Brevity is requested in the prompt rather than enforced with a small
    # max_tokens: the previous cap of 100 tokens was being consumed by hidden
    # reasoning on current models, which returned an empty summary.
    return await llm.complete_text(prompt, role=llm.Role.UTILITY,
                                   temperature=0.2)

async def score_unseen_news(db, symbol: str = None) -> int:
    """Backfill sentiment for rows the Celery chain never reached.

    Scores the article body, matching ``_async_analyse_sentiment`` in
    ``tasks/scrape_tasks.py``. The two must agree: this is the on-demand path and
    that is the scheduled one, and a score whose meaning depended on which task
    happened to produce it would make every cross-article comparison — the
    per-symbol average below, and any sentiment ranking — incoherent.

    Unlike the scheduled task this does *not* summarise. It exists to be cheap and
    synchronous behind a request, and summarising N articles is N LLM round trips.
    """
    from app.models.stock import NewsSentiment
    query = db.query(NewsSentiment).filter(NewsSentiment.sentiment_score == None)
    if symbol:
        query = query.filter(NewsSentiment.symbol == symbol)
    unscored = query.all()
    count = 0
    for row in unscored:
        body = row.body or row.summary or ""
        text = f"{row.headline}. {body[:1500]}" if body else row.headline
        score, label = await analyse_text(text)
        row.sentiment_score = score
        row.sentiment_label = label
        count += 1
    db.commit()
    return count

SENTIMENT_WINDOW_DAYS = 30


def sentiment_label_for(avg: float | None) -> str:
    """VADER's conventional +/-0.05 cut-offs; "none" when nothing was scored."""
    if avg is None:
        return "none"
    if avg >= 0.05:
        return "positive"
    if avg <= -0.05:
        return "negative"
    return "neutral"


def get_symbol_sentiment_summary(db, symbol: str) -> dict:
    """Average news sentiment for one company over the last 30 days.

    Keys match schemas.stock.SentimentSummary. They used not to (average_score /
    overall_label / article_count), so GET /stocks/sentiment/{symbol} failed
    response validation with a 500 on every call. A symbol with no scored
    article gets avg_score None and label "none", never a neutral 0.0: "no news"
    and "neutral news" are different facts.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func
    from app.models.stock import NewsSentiment

    since = datetime.now(timezone.utc) - timedelta(days=SENTIMENT_WINDOW_DAYS)
    rows = (
        db.query(NewsSentiment)
        .filter(
            NewsSentiment.symbol == symbol,
            func.coalesce(NewsSentiment.published_at, NewsSentiment.scraped_at) >= since,
        )
        .order_by(NewsSentiment.published_at.desc().nullslast(), NewsSentiment.scraped_at.desc())
        .all()
    )
    scores = [r.sentiment_score for r in rows if r.sentiment_score is not None]
    avg = round(sum(scores) / len(scores), 4) if scores else None
    return {
        "symbol": symbol,
        "count": len(scores),
        "avg_score": avg,
        "label": sentiment_label_for(avg),
        "recent_headlines": [r.headline for r in rows[:5]],
    }

