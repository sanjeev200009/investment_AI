"""Transparent ranked recommendations — the real thing behind the label "AI
Picks".

The previous implementation of that label was `sort(() => 0.5 - Math.random())`,
deleted in I-07. What replaces it is deliberately *not* a model: a simple linear
score with stated weights, because the dissertation commits to no black-box
outputs (§12.1) and a defensible viva answer is "here is the formula, here is
each stock's contribution" rather than "trust the network".

Design constraints, in order:

* **Every factor is measured, never derived from the price alone.** A factor
  that cannot be measured for a symbol is reported as `null` and its weight is
  redistributed across the factors that *were* measured — a symbol with no news
  coverage is not penalised for it, it is scored on what exists.
* **The score is explainable at the row level.** Each response carries the
  factor values, the weight each carried, and the points each contributed, so
  "why is this stock ranked here" has a concrete answer.
* **Weights live in one dict at the top of the file.** They are a stated
  research decision, not tuned parameters; changing one is a documented act,
  not a code accident.

Score is -100 to +100. Every factor is normalised to [-1, 1] before weighting
(liquidity's market percentile is centred on zero, the rest are bounded raw
values), so no single factor's units dominate the sum and a median stock on a
factor contributes nothing for it. A symbol needs at least MIN_FACTORS measured
factors to be ranked: with weight redistribution, one lucky reading (a single
+5% day, or liquidity alone) would otherwise carry 100% of the score.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.portfolio import PortfolioHolding
from app.models.stock import CompanyInfo, DailyClose, MarketDataLatest, NewsSentiment

logger = logging.getLogger(__name__)

# The stated weights. They sum to 1.0 and each factor's contribution to a
# symbol's score is weight × factor_value × 100.
MIN_FACTORS = 2

FACTOR_WEIGHTS: dict[str, float] = {
    # Daily price momentum — a small tailwind, not a thesis.
    "daily_change": 0.15,
    # Medium-term momentum: close now vs ~4 trading weeks ago.
    "momentum_4w": 0.30,
    # Liquidity: how tradeable the position is, percentile-ranked across the
    # market by turnover (volume × price where the feed gives no turnover).
    "liquidity": 0.25,
    # Average news sentiment for the symbol, from the news pipeline.
    "news_sentiment": 0.30,
}

# Weights per risk category (proposal 6.10: recommendations are tailored to the
# user's risk profile). Same four factors, same transparent sum; only the
# emphasis moves, and the weights actually used are returned with every
# response, so the tailoring is visible rather than hidden.
#
#   Low     favours tradeable stocks with steady news, and all but ignores one
#           day's swing: a cautious beginner should not be steered by noise.
#   Medium  the balanced default above.
#   High    leans on trend (momentum) and today's move, accepts thinner trading.
#
# A stated research decision, not tuned values. Each row sums to 1.0.
RISK_WEIGHTS: dict[str, dict[str, float]] = {
    "Low": {"daily_change": 0.05, "momentum_4w": 0.20, "liquidity": 0.40, "news_sentiment": 0.35},
    "Medium": FACTOR_WEIGHTS,
    "High": {"daily_change": 0.20, "momentum_4w": 0.40, "liquidity": 0.15, "news_sentiment": 0.25},
}


def weights_for(risk_category: str | None) -> dict[str, float]:
    """The weights for a risk category; the balanced default when unknown."""
    return RISK_WEIGHTS.get(risk_category or "", FACTOR_WEIGHTS)


def score_factors(factors: dict[str, float], weights: dict[str, float]) -> tuple[float, dict]:
    """Weighted sum over the measured factors, weights redistributed over them.

    Each factor value is in [-1, 1]; the score is in [-100, 100]. Returns the
    score and a per-factor breakdown (value, effective weight, contribution).
    """
    weight_total = sum(weights[f] for f in factors)
    breakdown: dict[str, dict] = {}
    score = 0.0
    for f, value in sorted(factors.items()):
        weight = weights[f] / weight_total
        contribution = weight * value * 100
        score += contribution
        breakdown[f] = {
            "value": round(value, 4),
            "weight": round(weight, 4),
            "contribution": round(contribution, 2),
            "label": FACTOR_LABELS[f],
        }
    return score, breakdown


# Human-readable statements of what each factor measures, served with the
# response so the UI never has to invent a description.
FACTOR_LABELS: dict[str, str] = {
    "daily_change": "Today's price movement",
    "momentum_4w": "Price trend over the last ~4 trading weeks",
    "liquidity": "Trading activity vs the rest of the market",
    "news_sentiment": "Average sentiment of recent news coverage",
}

MODEL_VERSION = "linear-v3"  # v3: weights chosen by the user's risk category

# How many symbols to return. The whole ranked market is available; the app
# shows a page.
DEFAULT_LIMIT = 10

# A symbol needs at least this many daily closes for the momentum factor;
# fewer and the trend is noise over whatever window happens to exist.
MIN_MOMENTUM_POINTS = 5

# Momentum is measured over this many trading days when the series has them.
MOMENTUM_WINDOW_DAYS = 20

# News sentiment is averaged over articles scraped in the last month.
SENTIMENT_WINDOW_DAYS = 30


def _percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    """symbol -> rank in [0, 1] across the given values.

    Percentile rather than min-max normalisation: a single giant turnover
    (DIAL Rs. 428.7B market cap class) would flatten every other symbol to ~0
    under min-max, while percentile rank says "more liquid than N% of the
    market" — the statement a beginner actually cares about.
    """
    if not values:
        return {}
    sorted_vals = sorted(values.values())
    n = len(sorted_vals)
    ranks: dict[str, float] = {}
    for symbol, v in values.items():
        below = sum(1 for x in sorted_vals if x < v)
        # Midpoint rank so ties share a value and the lowest is 0.5/n, not 0.
        ranks[symbol] = (below + 0.5) / n
    return ranks


def _close_series(db: Session, cutoff: date) -> dict[str, list[float]]:
    """symbol -> ascending closes since cutoff, one query for the market."""
    rows = (db.query(DailyClose.symbol, DailyClose.trade_date, DailyClose.close)
            .filter(DailyClose.trade_date >= cutoff)
            .order_by(DailyClose.symbol, DailyClose.trade_date)
            .all())
    series: dict[str, list[float]] = {}
    for symbol, _trade_date, close in rows:
        series.setdefault(symbol, []).append(float(close))
    return series


def _sentiment_averages(db: Session, cutoff: date) -> dict[str, float]:
    """symbol -> mean sentiment score over recent scored articles."""
    rows = (db.query(NewsSentiment.symbol,
                     func.avg(NewsSentiment.sentiment_score).label("avg"))
            .filter(NewsSentiment.sentiment_score.isnot(None),
                    NewsSentiment.scraped_at >= cutoff)
            .group_by(NewsSentiment.symbol)
            .all())
    return {symbol: float(avg) for symbol, avg in rows}


def build_recommendations(
    db: Session,
    user_id: Any = None,
    limit: int = DEFAULT_LIMIT,
    risk_category: str | None = None,
) -> dict[str, Any]:
    """Rank the quoted market and return the top `limit` with full factor
    breakdowns. Excludes symbols the user already holds, so the list is
    somewhere to look rather than a mirror of the portfolio. `risk_category`
    (Low / Medium / High, from the user's risk profile) selects the weights."""
    weights = weights_for(risk_category)
    applied_category = risk_category if risk_category in RISK_WEIGHTS else None
    quotes = db.query(MarketDataLatest).all()
    if not quotes:
        return {"model_version": MODEL_VERSION, "weights": weights,
                "risk_category": applied_category,
                "factor_labels": FACTOR_LABELS, "count": 0, "items": []}

    held: set[str] = set()
    if user_id is not None:
        held = {h.symbol for h in
                db.query(PortfolioHolding.symbol)
                .join(PortfolioHolding.portfolio)
                .filter_by(user_id=user_id).all()}

    today = date.today()
    momentum_cutoff = today - timedelta(days=MOMENTUM_WINDOW_DAYS * 2)
    sentiment_cutoff = today - timedelta(days=SENTIMENT_WINDOW_DAYS)

    closes = _close_series(db, momentum_cutoff)
    sentiments = _sentiment_averages(db, sentiment_cutoff)

    # Liquidity is ranked across every quoted symbol, so a held symbol's
    # exclusion does not shift the percentile scale.
    turnover: dict[str, float] = {}
    for q in quotes:
        t = q.volume * q.price if (q.volume is not None and q.price) else None
        if t:
            turnover[q.symbol] = t
    liquidity_rank = _percentile_ranks(turnover)

    profiles = {p.symbol: p for p in db.query(CompanyInfo).all()}

    items: list[dict[str, Any]] = []
    for q in quotes:
        if q.symbol in held or not q.price:
            continue

        factors: dict[str, float] = {}
        # --- daily change: bounded, no normalisation needed ---
        if q.change_pct is not None:
            factors["daily_change"] = max(-1.0, min(1.0, float(q.change_pct) / 5.0))

        # --- 4-week momentum ---
        series = closes.get(q.symbol, [])
        if len(series) >= MIN_MOMENTUM_POINTS:
            base = series[0]
            if base > 0:
                ret = (series[-1] - base) / base
                factors["momentum_4w"] = max(-1.0, min(1.0, ret / 0.20))

        # --- liquidity percentile ---
        if q.symbol in liquidity_rank:
            factors["liquidity"] = 2.0 * liquidity_rank[q.symbol] - 1.0

        # --- news sentiment: average in [-1, 1] ---
        if q.symbol in sentiments:
            factors["news_sentiment"] = max(-1.0, min(1.0, sentiments[q.symbol]))

        if len(factors) < MIN_FACTORS:
            continue

        score, breakdown = score_factors(factors, weights)

        profile = profiles.get(q.symbol)
        items.append({
            "symbol": q.symbol,
            "name": profile.name if profile else None,
            "sector": profile.sector_group if profile else None,
            "price": float(q.price),
            "change_pct": float(q.change_pct) if q.change_pct is not None else None,
            "score": round(score, 2),
            "factors": breakdown,
        })

    items.sort(key=lambda r: r["score"], reverse=True)
    return {
        "model_version": MODEL_VERSION,
        "weights": weights,
        "risk_category": applied_category,
        "factor_labels": FACTOR_LABELS,
        "count": len(items),
        "items": items[:limit],
    }


SNAPSHOT_SIZE = 10


def snapshot_recommendations(db: Session, day: date | None = None) -> int:
    """Evaluation plan E5: save the top picks for each risk category on `day`
    (default: today in Colombo). Re-running the same day replaces its rows."""
    from app.models.evaluation import RecommendationSnapshot
    from app.services.portfolio_history import exchange_today

    day = day or exchange_today()
    db.query(RecommendationSnapshot).filter(
        RecommendationSnapshot.snapshot_date == day).delete()
    rows = [
        RecommendationSnapshot(
            snapshot_date=day, risk_category=category, rank=rank,
            symbol=item["symbol"], score=item["score"], price=item["price"],
            model_version=MODEL_VERSION)
        for category in RISK_WEIGHTS
        for rank, item in enumerate(
            build_recommendations(db, limit=SNAPSHOT_SIZE, risk_category=category)["items"], 1)
    ]
    db.add_all(rows)
    db.commit()
    return len(rows)
