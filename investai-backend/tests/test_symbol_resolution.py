"""The agent's tools accept bare tickers and company names (offline, SQLite)."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.stock import CompanyInfo, MarketDataLatest, MarketIndexLatest
from app.services.agent.tools import ToolExecutor, resolve_symbols


def _db():
    engine = create_engine("sqlite://")
    for m in (MarketDataLatest, CompanyInfo, MarketIndexLatest):
        m.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    now = datetime(2026, 9, 29, 9, 15, tzinfo=timezone.utc)
    for sym, price in [("JKH.N0000", 18.9), ("JKH.X0000", 17.0), ("COMB.N0000", 132.0), ("COMB.X0000", 120.0)]:
        db.add(MarketDataLatest(symbol=sym, price=price, change_pct=0.5, volume=1000, recorded_at=now, updated_at=now))
    db.add(CompanyInfo(symbol="JKH.N0000", name="JOHN KEELLS HOLDINGS PLC", refreshed_at=now))
    db.add(MarketIndexLatest(index_code="ASPI", name="All Share Price Index", value=20847.26, change_pct=-0.46, recorded_at=now, updated_at=now))
    db.commit()
    return db


def test_bare_ticker_full_symbol_and_name_resolve_to_voting_share():
    db = _db()
    got = resolve_symbols(db, ["JKH", "comb.n0000", "John Keells", "ZZZZ"])
    assert got == {"JKH": "JKH.N0000", "comb.n0000": "COMB.N0000", "John Keells": "JKH.N0000", "ZZZZ": None}


def test_stock_data_tool_answers_for_a_bare_ticker_and_names_unknowns():
    db = _db()
    out = asyncio.run(ToolExecutor(db, "u")._get_stock_data(["JKH", "ZZZZ"]))
    assert out["stocks"]["JKH.N0000"]["price"] == 18.9
    assert "No listed CSE company" in out["stocks"]["ZZZZ"]["error"]


def test_market_overview_includes_the_aspi():
    db = _db()
    out = asyncio.run(ToolExecutor(db, "u")._get_market_overview())
    assert out["indices"]["ASPI"]["value"] == 20847.26
