"""Explainable price-prediction baseline — the write side of the
`price_predictions` table that has existed since the initial migration with
nothing ever writing to it (I-16).

The agent's `get_price_prediction` tool reads this table and has returned
{"error": "No prediction available"} for its entire life.

**The model is a least-squares trend line over the stored daily closes —
deliberately.** The dissertation's options here were a real ML model (no
feature data, 6 weeks of history, and a credibility trap if it overfits), no
feature at all (an agent tool that always errors), or something simple enough
to be honest about what it is. This is the third: a transparent extrapolation
whose docstring, model_version and UI copy all say "trend extrapolation, not a
forecast" — the same no-black-box commitment that drove I-13's linear score.

What it is not: a return forecast, a volatility estimate, or a probability.
One number: where the recent trend line lands one trading day out, plus the
residual band the last 20 points actually showed, so the UI can render an
honest range around it.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.stock import DailyClose, PricePrediction

logger = logging.getLogger(__name__)

# Model version recorded per row. Change this whenever the method changes —
# the agent surfaces it, and comparing predictions across methods without it
# would be meaningless.
MODEL_VERSION = "linear-trend-v1"

# Trend is fitted over at most this many most-recent closes. All of history is
# not wanted: a stock that fell for a month and recovered this week would carry
# the whole month's slope.
TREND_POINTS = 20

# Fewer than this and the fit is a straight line through two points — noise.
MIN_POINTS = 5


def fit_next_close(closes: list[float]) -> dict | None:
    """One-day-ahead extrapolation of a least-squares line over `closes`.

    Returns dict(predicted_price, residual, slope) or None if too few points.
    `residual` is the mean absolute deviation of the actual closes from the
    fitted line — the honest width of the band around the prediction.
    """
    n = len(closes)
    if n < MIN_POINTS:
        return None
    # x = 0..n-1, y = closes. Closed-form least squares.
    xs = range(n)
    x_mean = (n - 1) / 2
    y_mean = sum(closes) / n
    sxx = sum((x - x_mean) ** 2 for x in xs)
    sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, closes))
    if sxx == 0:
        return None
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean

    fitted = [intercept + slope * x for x in xs]
    residual = sum(abs(y - f) for y, f in zip(closes, fitted)) / n

    return {
        # x = n is the next trading day.
        "predicted_price": intercept + slope * n,
        "residual": residual,
        "slope": slope,
    }


def update_predictions(db: Session, symbols: list[str] | None = None) -> int:
    """Write a prediction per symbol from its daily_close series. Returns rows
    written.

    Rows are inserted, not upserted — the table carries no unique key and a
    new row per run is the history. The agent's tool reads the latest row per
    symbol, so growth is bounded by one row per symbol per scheduled run.
    """
    cutoff = date.today() - timedelta(days=TREND_POINTS * 3)

    query = (db.query(DailyClose.symbol, DailyClose.trade_date, DailyClose.close)
             .filter(DailyClose.trade_date >= cutoff))
    if symbols:
        query = query.filter(DailyClose.symbol.in_([s.upper() for s in symbols]))
    rows = (query.order_by(DailyClose.symbol, DailyClose.trade_date).all())

    series: dict[str, list[float]] = {}
    for symbol, _trade_date, close in rows:
        series.setdefault(symbol, []).append(float(close))

    written = 0
    for symbol, closes in series.items():
        fit = fit_next_close(closes[-TREND_POINTS:])
        if fit is None:
            continue
        db.add(PricePrediction(
            symbol=symbol,
            predicted_price=round(fit["predicted_price"], 4),
            model_version=MODEL_VERSION,
        ))
        written += 1

    db.commit()
    logger.info("Price predictions: %d rows written (%d symbols with enough "
                "history)", written, len(series))
    return written


def latest_for_symbol(db: Session, symbol: str) -> PricePrediction | None:
    """The newest prediction row for a symbol — what the agent tool serves."""
    return (db.query(PricePrediction)
            .filter(PricePrediction.symbol == symbol.upper())
            .order_by(PricePrediction.generated_at.desc())
            .first())
