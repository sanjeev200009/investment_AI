# app/services/ai_agent.py
"""DEPRECATED — superseded by app.services.agent (the ReAct agent) and
app.services.llm (provider failover). Nothing imports this module.

Do not wire it back up: the models named in app.services.ai_providers are dead
(google/gemini-2.5-flash returns HTTP 402, gemini-1.5-flash returns HTTP 404),
it builds five provider clients at import time, and it has no tool calling. Use
``llm.acreate(..., role=llm.Role.AGENT)`` instead. Removal is tracked as I-21.
"""
import logging
from typing import List, Dict, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.portfolio import Portfolio
from app.models.stock import MarketDataLatest
from app.models.user import User, RiskProfile
from app.services.sentiment import get_symbol_sentiment_summary
from app.services.ai_providers import (
    AnthropicProvider, GoogleProvider, GroqProvider, OpenAIProvider, OpenRouterProvider
)

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize providers in priority order
# Using Groq as primary for testing as requested
PROVIDERS = [
    OpenRouterProvider(),
    GroqProvider(),
    GoogleProvider(),
    OpenAIProvider(),
    AnthropicProvider()
]

SYSTEM_PROMPT = '''
You are InvestAI, a professional investment advisor specialising in the
Colombo Stock Exchange (CSE) in Sri Lanka. You provide personalised,
data-driven investment advice based on each user's portfolio, risk profile,
and current market conditions.

Guidelines:
- Always base recommendations on the context data provided below.
- Be specific — mention stock symbols, prices, and percentages.
- Warn about risks appropriate to the user's risk category.
- Never guarantee returns. Always remind the user this is not
financial advice and they should consult a licensed broker.
- Keep responses concise (under 400 words) unless the user asks for detail.
- Use simple, clear language suitable for retail investors.
'''

def _build_context(db: Session, user: User) -> str:
    """Build a context string from DB data to inject into the prompt."""
    lines = []
    
    # Risk profile
    rp = db.query(RiskProfile).filter(RiskProfile.user_id == user.user_id).first()
    if rp:
        lines.append(f'User risk profile: {rp.category} (score {rp.score}/100)')
    
    # Portfolio holdings
    portfolios = db.query(Portfolio).filter(
        Portfolio.user_id == user.user_id).all()

    # Price every held symbol in one query rather than once per holding.
    held = {h.symbol for p in portfolios for h in p.holdings}
    quotes = {
        r.symbol: r
        for r in db.query(MarketDataLatest).filter(
            MarketDataLatest.symbol.in_(held)).all()
    } if held else {}

    for port in portfolios:
        lines.append(f'Portfolio: {port.name}')
        for h in port.holdings:
            mkt = quotes.get(h.symbol)

            current_price = mkt.price if mkt else h.avg_buy_price
            pnl_pct = ((current_price - h.avg_buy_price) / h.avg_buy_price) * 100

            lines.append(
                f' - {h.symbol}: {h.quantity:.0f} shares @ LKR {h.avg_buy_price:.2f} '
                f'| Current: LKR {current_price:.2f} | P&L: {pnl_pct:+.1f}%'
            )

            # Sentiment
            sent = get_symbol_sentiment_summary(db, h.symbol)
            if sent['count'] > 0:
                lines.append(
                    f'   Sentiment ({h.symbol}): {sent["label"]} '
                    f'(score {sent["avg_score"]:+.3f}, {sent["count"]} articles)'
                )

    # Market overview: the ten largest absolute movers.
    #
    # This was `ORDER BY recorded_at DESC LIMIT 10` over all history, labelled
    # "top 10 movers". Because the scraper stamped each row with its own
    # timestamp, it returned ten arbitrary symbols from the tail of the newest
    # batch — and once a second scrape existed the same symbol could occupy
    # several of the ten slots. Nothing about it was a mover.
    latest_prices = db.query(MarketDataLatest).order_by(
        func.abs(MarketDataLatest.change_pct).desc().nullslast()).limit(10).all()

    if latest_prices:
        lines.append('Biggest movers right now (top 10 by absolute % change):')
        for m in latest_prices:
            lines.append(f'  {m.symbol}: LKR {m.price:.2f} ({m.change_pct:+.1f}%)')
            
    return '\n'.join(lines) if lines else 'No portfolio data available yet.'

def chat_with_agent(
    db: Session,
    user: User,
    conversation_history: list[dict],
    new_message: str,
) -> str:
    """
    Send a message to the AI agent with automatic failover between providers.
    """
    context = _build_context(db, user)
    system_with_context = SYSTEM_PROMPT + f'\n\n=== USER CONTEXT ===\n{context}'
    
    # Normalize message history roles (standard user/assistant)
    messages = conversation_history + [
        {'role': 'user', 'content': new_message}
    ]

    # Attempt providers in order
    last_error = None
    for provider in PROVIDERS:
        try:
            logger.info(f"Attempting response with {provider.name}...")
            return provider.generate_response(system_with_context, messages)
        except Exception as e:
            last_error = str(e)
            logger.warning(f"{provider.name} failed: {last_error}")
            continue

    logger.error(f"All AI providers failed. Last error: {last_error}")
    return "Sorry, I'm having trouble connecting to my brain right now. Please try again in a moment."
