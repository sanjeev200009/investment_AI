# app/services/agent/tools.py
"""
Agentic tool definitions for InvestAI.
Each tool is a callable the LLM can invoke during a reasoning loop.
Tools return structured dicts that are serialised into the context window.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Tool schemas (OpenAI-compatible function-calling format)
# ─────────────────────────────────────────────────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_data",
            "description": (
                "Retrieve the latest market data for one or more CSE stock symbols. "
                "Returns price, change, change_pct, volume, and market_cap. "
                "Use this whenever the user asks about a specific stock's price or performance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of CSE ticker symbols e.g. ['HNB', 'COMB', 'DIAL']",
                    }
                },
                "required": ["symbols"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_news",
            "description": (
                "Fetch recent news headlines and AI sentiment scores for a CSE stock symbol. "
                "Use this when the user asks about news, events, or what is happening with a stock."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "CSE ticker symbol e.g. 'HNB'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of news articles to return (default 5, max 10)",
                        "default": 5,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_portfolio",
            "description": (
                "Read the authenticated user's portfolio holdings, including "
                "symbol, quantity, average buy price, and current P&L. "
                "Use this when the user asks about their own investments."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_prediction",
            "description": (
                "Get the AI model's price prediction for a CSE stock symbol. "
                "Use this when the user asks whether a stock will go up/down or for a forecast."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "CSE ticker symbol",
                    }
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_financial_knowledge",
            "description": (
                "Semantic search across indexed CSE news and market reports using RAG. "
                "Use this for broad questions like 'what sectors are performing well' or "
                "'what are analysts saying about the banking sector'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_overview",
            "description": (
                "Get a snapshot of the top gainers, top losers, and most active stocks "
                "on the CSE today. Use this when the user asks about the overall market."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["gainers", "losers", "active", "all"],
                        "description": "Which category to return",
                        "default": "all",
                    }
                },
                "required": [],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool executor
# ─────────────────────────────────────────────────────────────────────────────

class ToolExecutor:
    """
    Executes tool calls requested by the LLM.
    Receives a live DB session and the authenticated user_id so tools can
    query user-specific data without breaking isolation.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Route a tool call to its implementation. Always returns a JSON string."""
        dispatch = {
            "get_stock_data": self._get_stock_data,
            "get_stock_news": self._get_stock_news,
            "get_user_portfolio": self._get_user_portfolio,
            "get_price_prediction": self._get_price_prediction,
            "search_financial_knowledge": self._search_financial_knowledge,
            "get_market_overview": self._get_market_overview,
        }
        handler = dispatch.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            result = await handler(**arguments)
            return json.dumps(result, default=str)
        except Exception as exc:
            logger.exception("Tool %s failed: %s", tool_name, exc)
            return json.dumps({"error": str(exc)})

    # ── individual tool implementations ──────────────────────────────────────

    async def _get_stock_data(self, symbols: list[str]) -> dict:
        from app.models.stock import MarketDataLatest

        # One query for the whole request rather than one per symbol.
        wanted = [s.upper().strip() for s in symbols]
        rows = {
            r.symbol: r
            for r in self.db.query(MarketDataLatest).filter(
                MarketDataLatest.symbol.in_(wanted)).all()
        }

        results = {}
        for sym in wanted:
            row = rows.get(sym)
            if row:
                results[sym] = {
                    "symbol": row.symbol,
                    "price": row.price,
                    "change": row.change,
                    "change_pct": row.change_pct,
                    "volume": row.volume,
                    "market_cap": row.market_cap,
                    "recorded_at": str(row.recorded_at),
                }
            else:
                results[sym] = {"error": f"No data found for {sym}"}
        return {"stocks": results, "retrieved_at": datetime.now(timezone.utc).isoformat()}

    async def _get_stock_news(self, symbol: str, limit: int = 5) -> dict:
        from app.models.stock import NewsSentiment

        limit = min(limit, 10)
        symbol = symbol.upper().strip()
        rows = (
            self.db.query(NewsSentiment)
            .filter(NewsSentiment.symbol == symbol)
            .order_by(NewsSentiment.scraped_at.desc())
            .limit(limit)
            .all()
        )
        articles = [
            {
                "headline": r.headline,
                "summary": r.summary,
                "sentiment_label": r.sentiment_label,
                "sentiment_score": r.sentiment_score,
                "source": r.source,
                "url": r.url,
                "published_at": str(r.published_at),
            }
            for r in rows
        ]
        return {
            "symbol": symbol,
            "article_count": len(articles),
            "articles": articles,
        }

    async def _get_user_portfolio(self) -> dict:
        from app.models.portfolio import Portfolio, PortfolioHolding
        from app.models.stock import MarketDataLatest

        portfolios = (
            self.db.query(Portfolio)
            .filter(Portfolio.user_id == self.user_id)
            .all()
        )

        # Price every held symbol across every portfolio in one query. This was a
        # per-holding query inside a nested loop, so the cost grew with the number
        # of holdings on a path the chat agent hits on most turns.
        held = {h.symbol for p in portfolios for h in p.holdings}
        prices: dict[str, float] = {}
        if held:
            prices = {
                r.symbol: r.price
                for r in self.db.query(MarketDataLatest).filter(
                    MarketDataLatest.symbol.in_(held)).all()
            }

        output = []
        for p in portfolios:
            holdings = []
            total_cost = 0.0
            total_value = 0.0
            for h in p.holdings:
                current_price = prices.get(h.symbol)
                cost = h.quantity * h.avg_buy_price
                value = h.quantity * current_price if current_price else None
                pnl = (value - cost) if value is not None else None
                pnl_pct = (pnl / cost * 100) if (pnl is not None and cost > 0) else None

                total_cost += cost
                if value:
                    total_value += value

                holdings.append({
                    "symbol": h.symbol,
                    "quantity": h.quantity,
                    "avg_buy_price": h.avg_buy_price,
                    "current_price": current_price,
                    "cost_basis": round(cost, 2),
                    "current_value": round(value, 2) if value else None,
                    "pnl": round(pnl, 2) if pnl is not None else None,
                    "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
                })

            output.append({
                "portfolio_name": p.name,
                "portfolio_id": p.portfolio_id,
                "holdings": holdings,
                "total_cost_basis": round(total_cost, 2),
                "total_current_value": round(total_value, 2),
                "total_pnl": round(total_value - total_cost, 2),
            })
        return {"portfolios": output}

    async def _get_price_prediction(self, symbol: str) -> dict:
        from app.models.stock import PricePrediction, MarketDataLatest

        symbol = symbol.upper().strip()
        pred = (
            self.db.query(PricePrediction)
            .filter(PricePrediction.symbol == symbol)
            .order_by(PricePrediction.generated_at.desc())
            .first()
        )
        current = (
            self.db.query(MarketDataLatest)
            .filter(MarketDataLatest.symbol == symbol)
            .first()
        )
        if not pred:
            return {"error": f"No prediction available for {symbol}"}

        upside = None
        if current and current.price:
            upside = round(
                (pred.predicted_price - current.price) / current.price * 100, 2
            )
        return {
            "symbol": symbol,
            "current_price": current.price if current else None,
            "predicted_price": pred.predicted_price,
            "upside_pct": upside,
            "model_version": pred.model_version,
            "generated_at": str(pred.generated_at),
            "disclaimer": "This is an AI-generated forecast for educational purposes only. Not financial advice.",
        }

    async def _search_financial_knowledge(self, query: str, limit: int = 5) -> dict:
        """
        RAG: embed the query via NVIDIA NIM, then run a pgvector similarity
        search over indexed news_sentiment embeddings.
        Falls back to keyword search if pgvector is unavailable.
        """
        from app.services.agent.embeddings import get_embedding
        from app.models.stock import NewsSentiment

        limit = min(limit, 10)

        try:
            # "query" side of the asymmetric embedding model; the indexed rows
            # were embedded as "passage".
            query_embedding = await get_embedding(query, input_type="query")
            # pgvector cosine similarity search using raw SQL
            from sqlalchemy import text as sql_text
            rows = self.db.execute(
                sql_text(
                    """
                    SELECT news_id, symbol, headline, summary,
                           sentiment_label, sentiment_score, source, published_at,
                           1 - (embedding <=> cast(:vec AS vector)) AS similarity
                    FROM   news_sentiment
                    WHERE  embedding IS NOT NULL
                    ORDER  BY embedding <=> cast(:vec AS vector)
                    LIMIT  :lim
                    """
                ),
                {"vec": str(query_embedding), "lim": limit},
            ).fetchall()

            results = [
                {
                    "headline": r.headline,
                    "summary": r.summary,
                    "symbol": r.symbol,
                    "sentiment_label": r.sentiment_label,
                    "source": r.source,
                    "similarity": round(r.similarity, 3),
                    "published_at": str(r.published_at),
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("pgvector search failed (%s), falling back to keyword", e)
            # Keyword fallback
            rows = (
                self.db.query(NewsSentiment)
                .filter(
                    NewsSentiment.headline.ilike(f"%{query}%")
                    | NewsSentiment.summary.ilike(f"%{query}%")
                )
                .order_by(NewsSentiment.scraped_at.desc())
                .limit(limit)
                .all()
            )
            results = [
                {
                    "headline": r.headline,
                    "summary": r.summary,
                    "symbol": r.symbol,
                    "sentiment_label": r.sentiment_label,
                    "source": r.source,
                    "similarity": None,
                    "published_at": str(r.published_at),
                }
                for r in rows
            ]

        return {"query": query, "results": results, "total": len(results)}

    async def _get_market_overview(self, category: str = "all") -> dict:
        from app.models.stock import MarketDataLatest

        # One row per symbol by construction, so no timestamp window is needed.
        # This used to take max(recorded_at) and then select everything within an
        # hour of it — a workaround for the scraper stamping each row with its own
        # microsecond timestamp, which also meant a symbol could appear more than
        # once and skew the gainer/loser rankings below.
        rows = self.db.query(MarketDataLatest).all()

        if not rows:
            return {"error": "No market data available"}

        all_stocks = [
            {
                "symbol": r.symbol,
                "price": r.price,
                "change_pct": r.change_pct,
                "volume": r.volume,
            }
            for r in rows
            if r.change_pct is not None
        ]

        sorted_by_change = sorted(
            all_stocks, key=lambda x: x["change_pct"] or 0, reverse=True
        )
        sorted_by_volume = sorted(
            all_stocks, key=lambda x: x["volume"] or 0, reverse=True
        )

        # Every row carries the recorded_at of the snapshot it came from. They are
        # normally all equal, but a symbol the last scrape did not return keeps its
        # older timestamp, so report the newest rather than assuming uniformity.
        as_of = max(r.recorded_at for r in rows)

        result: dict = {"as_of": str(as_of)}
        if category in ("gainers", "all"):
            result["top_gainers"] = sorted_by_change[:5]
        if category in ("losers", "all"):
            result["top_losers"] = sorted_by_change[-5:][::-1]
        if category in ("active", "all"):
            result["most_active"] = sorted_by_volume[:5]

        return result
