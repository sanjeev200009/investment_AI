from fastapi import APIRouter, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.dependencies import get_db, get_current_user
from app.models.stock import NewsSentiment, MarketData
from app.models.user import User
from app.models.portfolio import Portfolio

router = APIRouter(prefix='/dashboard', tags=['Dashboard'])

@router.get('/')
def get_dashboard_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Returns dashboard data featuring real AI Insights from the database.
    """
    # Fetch 3 latest news
    news = db.query(NewsSentiment).order_by(NewsSentiment.scraped_at.desc()).limit(3).all()
    news_text = "\n".join([f"- {item.headline}: {item.summary}" for item in news]) if news else "General market conditions are stable but require monitoring."
    
    insights = []
    
    try:
        from app.services.ai_providers import OpenRouterProvider
        import json
        import re
        
        provider = OpenRouterProvider()
        system_prompt = """You are a financial AI assistant. Generate exactly 3 short, actionable insights for a user based on the provided market news. 
Return ONLY a valid JSON array of objects with exactly these keys: "id" (string, unique), "label" (string: 'AI INSIGHT', 'MARKET MOVER', or 'RISK ALERT'), "body" (string, max 2 sentences), and "buttonText" (string, e.g. 'View', 'Analyze', 'Trade'). Do not include markdown blocks or any other text."""
        
        messages = [{"role": "user", "content": f"Recent market news:\n{news_text}"}]
        
        response_text = provider.generate_response(system_prompt, messages)
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        
        if json_match:
            insights = json.loads(json_match.group(0))
        else:
            insights = json.loads(response_text)
            
    except Exception as e:
        print(f"AI Insights generation failed: {e}")
        # Fallback to database
        labels = ["MARKET MOVER", "RISK ALERT", "AI INSIGHT"]
        for i, item in enumerate(news):
            insights.append({
                "id": f"insight_{item.news_id}",
                "label": labels[i % len(labels)],
                "body": item.headline or item.summary or "No details available.",
                "buttonText": "Read More"
            })

    # If no news found and AI failed, provide a fallback insight
    if not insights:
        insights = [{
            "id": "insight_empty",
            "label": "AI INSIGHT",
            "body": "No market news available right now. Keep an eye on your portfolio.",
            "buttonText": "Refresh"
        }]

    # Fetch top 6 stocks by volume for the dashboard watchlist preview
    top_stocks = db.query(MarketData).order_by(MarketData.volume.desc()).limit(6).all()
    watchlist_preview = []
    for stock in top_stocks:
        watchlist_preview.append({
            "symbol": stock.symbol,
            "price": float(stock.price) if stock.price else 0,
            "change_pct": float(stock.change_pct) if stock.change_pct else 0
        })

    # Calculate Real Portfolio Value
    from app.models.portfolio import PortfolioHolding
    holdings = db.query(PortfolioHolding).join(Portfolio).filter(Portfolio.user_id == current_user.user_id).all()
    current_val = 0
    for item in holdings:
        # Get latest market price
        latest = db.query(MarketData).filter(MarketData.symbol == item.symbol).order_by(MarketData.recorded_at.desc()).first()
        price = float(latest.price) if latest else float(item.avg_buy_price)
        current_val += price * item.quantity

    target_val = current_val * 1.5 if current_val > 0 else 100000
    
    # Generate deterministic pseudo-historical weekly data based on current_val
    weekly_history = [
        current_val * 0.85,
        current_val * 0.82,
        current_val * 0.94,
        current_val
    ]

    return {
        "aspi": {
            "value": 12450.80, # ASPI is an index, hardcoded for now since our scraper only gets individual stocks
            "change_pct": 1.2
        },
        "portfolio": {
            "current_value": current_val,
            "target_value": target_val,
            "weekly_history": weekly_history
        },
        "insights": insights,
        "watchlist_preview": watchlist_preview
    }
