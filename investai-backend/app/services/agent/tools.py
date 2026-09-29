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

# ponytail: lesson embeddings cached in process memory. Nine short lessons do
# not justify a table; move them into pgvector if the corpus grows past ~100.
_lesson_vectors: list[tuple[dict, list[float]]] | None = None


async def _relevant_lessons(query: str, limit: int = 2) -> list[dict]:
    """The lessons closest to the question, by embedding similarity; keyword
    ranking if the embedding service is unavailable. Never raises."""
    global _lesson_vectors
    from app.content.lessons import LESSONS, keyword_rank, lesson_text

    ranked: list[dict] = []
    try:
        from app.services.agent.embeddings import get_embedding, get_embeddings_batch
        if _lesson_vectors is None:
            vectors = await get_embeddings_batch([lesson_text(l) for l in LESSONS], input_type="passage")
            _lesson_vectors = list(zip(LESSONS, vectors))
        q = await get_embedding(query, input_type="query")

        def cosine(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            return dot / (na * nb) if na and nb else 0.0

        scored = sorted(((cosine(q, v), l) for l, v in _lesson_vectors), key=lambda s: s[0], reverse=True)
        ranked = [l for sim, l in scored[:limit] if sim > 0.2]
    except Exception as exc:  # embedding outage: still answer from the lessons
        logger.warning("Lesson embedding search failed (%s); using keyword ranking", exc)
        ranked = keyword_rank(query, limit)

    return [
        {"lesson_id": l["id"], "title": l["title"], "text": lesson_text(l)}
        for l in ranked
    ]

PREDICTION_MAX_AGE_DAYS = 3

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
                        "description": "CSE tickers or company names, e.g. ['HNB', 'COMB.N0000', 'John Keells']",
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
                "Semantic search (RAG) across InvestAI's beginner lessons and indexed CSE "
                "news. Use it for concept questions ('what is a P/E ratio', 'how does the "
                "CSE work', 'what is diversification') and for broad news questions like "
                "'what is happening in the banking sector'. Prefer the lesson text when "
                "explaining a concept."
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
                "Get today's CSE snapshot: the ASPI and S&P SL20 index levels with their "
                "change, plus top gainers, top losers and most active stocks. Use this "
                "whenever the user asks about the overall market or an index."
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

def resolve_symbols(db, terms: list[str]) -> dict[str, str | None]:
    """Map what a user or model wrote to listed symbols: 'JKH', 'jkh.n0000'
    and 'John Keells' all resolve to 'JKH.N0000'. The tool schema invites bare
    tickers but every table keys on the full CSE symbol, so without this every
    lookup by ticker missed. Voting shares (.N0000) win over other classes."""
    from app.models.stock import CompanyInfo, MarketDataLatest

    listed = sorted(s for (s,) in db.query(MarketDataLatest.symbol).all())
    listed_set = set(listed)
    names = db.query(CompanyInfo.symbol, CompanyInfo.name).all()
    out: dict[str, str | None] = {}
    for term in terms:
        t = (term or "").strip()
        up = t.upper()
        if up in listed_set:
            out[term] = up
            continue
        base = up.split(".")[0]
        same = [s for s in listed if s.split(".")[0] == base]
        if same:
            out[term] = next((s for s in same if s.endswith(".N0000")), same[0])
            continue
        low = t.lower()
        hits = [sym for sym, name in names if name and len(low) >= 3 and low in name.lower()]
        out[term] = (next((h for h in hits if h.endswith(".N0000")), hits[0]) if hits else None)
    return out


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
            # A failed statement leaves the Postgres transaction aborted; without
            # this every later tool and the final save_assistant_message fail too.
            self.db.rollback()
            return json.dumps({"error": f"{tool_name} failed; the data is unavailable right now."})

    # ── individual tool implementations ──────────────────────────────────────

    async def _get_stock_data(self, symbols: list[str]) -> dict:
        from app.models.stock import MarketDataLatest

        # One query for the whole request rather than one per symbol.
        resolved = resolve_symbols(self.db, symbols)
        wanted = [v for v in resolved.values() if v]
        rows = {
            r.symbol: r
            for r in self.db.query(MarketDataLatest).filter(
                MarketDataLatest.symbol.in_(wanted)).all()
        }

        results = {term: {"error": f"No listed CSE company matches '{term}'"}
                   for term, sym in resolved.items() if not sym}
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
        symbol = resolve_symbols(self.db, [symbol])[symbol] or symbol.upper().strip()
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

        symbol = resolve_symbols(self.db, [symbol])[symbol] or symbol.upper().strip()
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

        # A trend line from last week says nothing about tomorrow; refuse stale
        # rows rather than let the model quote them as current.
        from datetime import datetime, timedelta, timezone
        generated = pred.generated_at
        if generated is not None and generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        if generated is None or generated < datetime.now(timezone.utc) - timedelta(days=PREDICTION_MAX_AGE_DAYS):
            return {"error": f"No recent prediction available for {symbol}"}

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
            # Without these the model read upside_pct as a price target.
            "horizon": "next trading day",
            "current_price_recorded_at": str(current.recorded_at) if current else None,
            # Names the method, not just the liability: the model is a linear
            # trend extrapolation over recent daily closes (I-16), not a
            # learned forecast, and the wording says so.
            "disclaimer": (
                "This is a statistical trend extrapolation from recent closing "
                "prices, not a forecast of what the price will do. For "
                "educational purposes only — not financial advice."
            ),
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
            self.db.rollback()   # the failed statement aborted the transaction
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

        lessons = await _relevant_lessons(query)
        return {
            "query": query,
            "lessons": lessons,
            "results": results,
            "total": len(results),
        }

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

        from app.models.stock import MarketIndexLatest
        result: dict = {"as_of": str(as_of), "indices": {
            i.index_code: {"name": i.name, "value": i.value, "change_pct": i.change_pct,
                           "as_of": str(i.updated_at)}
            for i in self.db.query(MarketIndexLatest).filter(
                MarketIndexLatest.index_code.in_(["ASPI", "SPSL20"])).all()}}
        if category in ("gainers", "all"):
            result["top_gainers"] = sorted_by_change[:5]
        if category in ("losers", "all"):
            result["top_losers"] = sorted_by_change[-5:][::-1]
        if category in ("active", "all"):
            result["most_active"] = sorted_by_volume[:5]

        return result
