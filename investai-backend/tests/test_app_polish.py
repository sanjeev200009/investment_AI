"""Home no longer waits for the LLM; chat context knows the time and the user."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.routers import dashboard
from app.services.agent import memory


def _utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_market_session_uses_colombo_time():
    # Colombo is UTC+05:30. 2026-09-30 is a Wednesday.
    assert memory.market_session(_utc(2026, 9, 30, 3, 59)).startswith("not yet open")   # 09:29
    assert memory.market_session(_utc(2026, 9, 30, 4, 0)).startswith("open")            # 09:30
    assert memory.market_session(_utc(2026, 9, 30, 8, 59)).startswith("open")           # 14:29
    assert memory.market_session(_utc(2026, 9, 30, 9, 0)).startswith("closed for the day")  # 14:30
    assert memory.market_session(_utc(2026, 10, 3, 5, 0)) == "closed (weekend)"        # Saturday


def test_user_snapshot_lists_name_watchlist_and_holdings():
    db = MagicMock()
    db.query.return_value.filter.return_value.limit.return_value = [
        SimpleNamespace(symbol="JKH.N0000")]
    (db.query.return_value.join.return_value.filter.return_value
       .limit.return_value.all.return_value) = [
        SimpleNamespace(symbol="COMB.N0000", quantity=10.0, avg_buy_price=120.5)]
    user = SimpleNamespace(user_id="u1", full_name="Sanjeev Kumar",
                           risk_profile=SimpleNamespace(knowledge_score=3))
    text = memory._user_snapshot(user, db, now=_utc(2026, 9, 30, 5, 0))
    assert "Sanjeev" in text and "10:30" in text and "open" in text
    assert "JKH.N0000" in text and "COMB.N0000 10 @ 120.5" in text
    assert "3/5" in text and "Never recommend buying or selling" in text


def test_dashboard_insights_never_block_on_the_llm(monkeypatch):
    started = []
    monkeypatch.setattr(dashboard.threading, "Thread",
                        lambda target, args, daemon: SimpleNamespace(
                            start=lambda: started.append(args)))
    dashboard._insight_cache.update(key=None, at=0.0, insights=None)
    news = [SimpleNamespace(news_id=1, headline="CSE gains", summary=None)]
    cards = dashboard._cached_insights("1") or (
        list(dashboard._insight_cache["insights"] or [])
        or dashboard._headline_insights(news))
    # Served immediately from real headlines; the model runs in the background.
    assert cards[0]["body"] == "CSE gains"
    assert dashboard._cached_insights("1") is None
