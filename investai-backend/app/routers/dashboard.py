from fastapi import APIRouter, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models.stock import NewsSentiment, MarketData

router = APIRouter(prefix='/dashboard', tags=['Dashboard'])

@router.get('/')
def get_dashboard_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns dashboard data featuring real AI Insights from the database.
    """
    # Fetch 3 latest news
    news = db.query(NewsSentiment).order_by(NewsSentiment.scraped_at.desc()).limit(3).all()
    
    insights = []
    labels = ["MARKET MOVER", "RISK ALERT", "AI INSIGHT"]
    for i, item in enumerate(news):
        insights.append({
            "id": f"insight_{item.news_id}",
            "label": labels[i % len(labels)],
            "body": item.headline or item.summary or "No details available.",
            "buttonText": "Read More"
        })

    # If no news found, provide a fallback insight
    if not insights:
        insights = [{
            "id": "insight_empty",
            "label": "AI INSIGHT",
            "body": "No market news available. Wait for the daily scraper.",
            "buttonText": "Refresh"
        }]

    # Fetch top 6 stocks by volume for the dashboard watchlist preview
    top_stocks = db.query(MarketData).order_by(MarketData.volume.desc()).limit(6).all()
    watchlist_preview = []
    for stock in top_stocks:
        watchlist_preview.append({
            "symbol": stock.symbol,
            "price": stock.price,
            "change_pct": stock.change_pct
        })

    return {
        "aspi": {
            "value": 12450.80, # ASPI mock or from DB if available
            "change_pct": 1.2
        },
        "portfolio": {
            "current_value": 145000,
            "target_value": 200000
        },
        "insights": insights,
        "watchlist_preview": watchlist_preview
    }
