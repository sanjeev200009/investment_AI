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
    return _vader_analyser


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

def get_symbol_sentiment_summary(db, symbol: str):
    from app.models.stock import NewsSentiment
    rows = db.query(NewsSentiment).filter(NewsSentiment.symbol == symbol).all()
    if not rows:
        return {"symbol": symbol, "average_score": 0.0, "overall_label": "neutral", "article_count": 0}
    scores = [r.sentiment_score for r in rows if r.sentiment_score is not None]
    avg = sum(scores) / len(scores) if scores else 0.0
    label = "neutral"
    if avg >= 0.05: label = "positive"
    elif avg <= -0.05: label = "negative"
    return {"symbol": symbol, "average_score": avg, "overall_label": label, "article_count": len(rows)}

