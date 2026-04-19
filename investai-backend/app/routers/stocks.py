# app/routers/stocks.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.dependencies import get_db, get_current_user
from app.models.stock import MarketData as MarketDataModel, NewsSentiment as NewsSentimentModel
from app.models.user import User
from app.schemas.stock import MarketData, NewsSentiment, PricePrediction

router = APIRouter(prefix='/stocks', tags=['Stocks'])

@router.get('/market', response_model=List[MarketData])
def get_market_data(
    symbol: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get latest market prices. Optionally filter by symbol."""
    # Get the most recent record per symbol
    from sqlalchemy import func
    subq = (
        db.query(
            MarketDataModel.symbol,
            func.max(MarketDataModel.recorded_at).label('max_ts')
        ).group_by(MarketDataModel.symbol).subquery()
    )
    query = db.query(MarketDataModel).join(
        subq,
        (MarketDataModel.symbol == subq.c.symbol) &
        (MarketDataModel.recorded_at == subq.c.max_ts)
    )
    
    if symbol:
        query = query.filter(MarketDataModel.symbol == symbol.upper())
        
    return query.limit(limit).all()

@router.get('/news/{symbol}', response_model=List[NewsSentiment])
def get_stock_news(
    symbol: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get latest news + sentiment for a specific symbol."""
    return (
        db.query(NewsSentimentModel)
        .filter(NewsSentimentModel.symbol == symbol.upper())
        .order_by(NewsSentimentModel.scraped_at.desc())
        .limit(limit)
        .all()
    )

@router.post('/scrape', status_code=202)
def trigger_scrape(
    background_tasks: BackgroundTasks,
    symbol: Optional[str] = None,
    _: User = Depends(get_current_user),
):
    """Manually trigger a background scrape (dev/admin use)."""
    from tasks.scrape_tasks import scrape_stock_news, scrape_cse_market_data
    if symbol:
        scrape_stock_news.delay(symbol)
    else:
        scrape_cse_market_data.delay()
    return {'message': 'Scrape task queued', 'symbol': symbol or 'ALL'}

@router.get('/sentiment/{symbol}')
def get_sentiment_summary(
    symbol: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get aggregated sentiment for a symbol."""
    from app.services.sentiment import get_symbol_sentiment_summary
    return get_symbol_sentiment_summary(db, symbol.upper())
