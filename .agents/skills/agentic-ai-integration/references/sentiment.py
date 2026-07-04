# app/services/sentiment.py
"""
Sentiment analysis service.
Two-tier approach:
  1. VADER (fast, local, free) — scores -1.0 to +1.0
  2. LLM summary (optional, higher quality) — only for articles without a summary
"""

from __future__ import annotations

import logging

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
    try:
        import httpx
        from app.config import get_settings

        api_key = getattr(get_settings(), "OPENROUTER_API_KEY", "")
        if not api_key:
            return None

        prompt = (
            f"Summarise this financial news article in 1-2 plain sentences "
            f"suitable for a beginner investor in Sri Lanka. "
            f"Focus on the practical impact.\n\n"
            f"Headline: {headline}\n\n"
            f"Article: {body[:1000]}"
        )
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-flash-1.5",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.2,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("LLM summarisation failed: %s", e)
        return None
