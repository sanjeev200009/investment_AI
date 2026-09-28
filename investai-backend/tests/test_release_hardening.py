"""Offline checks for the release-hardening changes: request limits, model
output validation on the dashboard, and holding input validation."""

import pytest
from pydantic import ValidationError

from app import rate_limit
from app.routers.dashboard import _clean_insights
from app.schemas.portfolio import HoldingCreate, HoldingOut


def test_rate_limit_blocks_after_max_and_recovers_after_window():
    key = "test|client-a"
    assert all(rate_limit.check(key, 3, 60, now=100.0 + i) for i in range(3))
    assert rate_limit.check(key, 3, 60, now=103.0) is False
    # Once the first hit is older than the window, a slot frees up.
    assert rate_limit.check(key, 3, 60, now=160.5) is True


def test_rate_limit_is_per_key():
    assert rate_limit.check("test|b", 1, 60, now=0.0)
    assert rate_limit.check("test|c", 1, 60, now=0.0)
    assert rate_limit.check("test|b", 1, 60, now=1.0) is False


def test_dashboard_insights_drop_malformed_items_and_trading_verbs():
    raw = [
        {"label": "market mover", "body": " ASPI fell 1%. ", "buttonText": "Trade"},
        "not a dict",
        {"label": "AI INSIGHT", "body": ""},
        {"label": "made up", "body": "Banks led turnover."},
    ]
    out = _clean_insights(raw)
    assert [i["body"] for i in out] == ["ASPI fell 1%.", "Banks led turnover."]
    assert {i["buttonText"] for i in out} == {"View"}
    assert out[1]["label"] == "AI INSIGHT"   # unknown label is coerced
    assert _clean_insights({"body": "object, not list"}) == []


def test_holding_input_is_validated_and_normalised():
    h = HoldingCreate(symbol=" jkh.n0000 ", quantity=10, avg_buy_price=190.5)
    assert h.symbol == "JKH.N0000"
    for bad in ({"quantity": 0}, {"quantity": -5}, {"avg_buy_price": -1},
                {"symbol": "X" * 21}):
        with pytest.raises(ValidationError):
            HoldingCreate(**{"symbol": "JKH.N0000", "quantity": 1,
                             "avg_buy_price": 1, **bad})


def test_existing_invalid_rows_remain_readable():
    # Rows stored before validation existed must not break GET /portfolio.
    HoldingOut(symbol="jkh", quantity=-1, avg_buy_price=0,
               holding_id=1, portfolio_id=1)


def test_sentiment_summary_matches_its_response_schema():
    # The service used to return average_score/overall_label/article_count,
    # which SentimentSummary rejected, so the endpoint 500'd on every call.
    from app.schemas.stock import SentimentSummary
    from app.services.sentiment import sentiment_label_for

    no_news = SentimentSummary(symbol="X.N0000", count=0, avg_score=None,
                               label=sentiment_label_for(None), recent_headlines=[])
    assert no_news.label == "none"          # "no news" is not "neutral news"
    assert sentiment_label_for(0.2) == "positive"
    assert sentiment_label_for(-0.2) == "negative"
    assert sentiment_label_for(0.01) == "neutral"


def test_risk_weights_are_complete_and_change_the_ranking():
    from app.services.recommendations import (FACTOR_WEIGHTS, RISK_WEIGHTS,
                                              score_factors, weights_for)
    for cat, w in RISK_WEIGHTS.items():
        assert set(w) == set(FACTOR_WEIGHTS), cat
        assert abs(sum(w.values()) - 1.0) < 1e-9, cat
    assert weights_for(None) is FACTOR_WEIGHTS
    assert weights_for("Unknown") is FACTOR_WEIGHTS

    # A volatile, thinly traded riser vs a liquid, steady stock with good news.
    jumpy = {"daily_change": 1.0, "momentum_4w": 0.8, "liquidity": -0.6, "news_sentiment": 0.0}
    steady = {"daily_change": 0.0, "momentum_4w": 0.1, "liquidity": 0.9, "news_sentiment": 0.5}
    low = {k: score_factors(v, weights_for("Low"))[0] for k, v in (("jumpy", jumpy), ("steady", steady))}
    high = {k: score_factors(v, weights_for("High"))[0] for k, v in (("jumpy", jumpy), ("steady", steady))}
    assert low["steady"] > low["jumpy"]      # cautious users see the steady stock first
    assert high["jumpy"] > high["steady"]    # risk-tolerant users see the mover first


def test_score_redistributes_over_measured_factors_only():
    from app.services.recommendations import score_factors, FACTOR_WEIGHTS
    score, breakdown = score_factors({"liquidity": 1.0, "news_sentiment": 1.0}, FACTOR_WEIGHTS)
    assert round(score, 6) == 100.0
    assert abs(sum(b["weight"] for b in breakdown.values()) - 1.0) < 1e-3
