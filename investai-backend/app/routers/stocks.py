# app/routers/stocks.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.dependencies import get_db, get_current_user
from app.models.stock import MarketData as MarketDataModel, NewsSentiment as NewsSentimentModel
from app.models.user import User
from app.schemas.stock import MarketData, NewsSentiment, PricePrediction, ScrapeResponse, SentimentSummary
from app.services.scraper import scrape_and_save_cse, scrape_and_save_news
from app.services.sentiment import score_unseen_news

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

@router.post('/scrape', status_code=200, response_model=ScrapeResponse, tags=['Scraper'])
async def trigger_scrape(
    db: Session = Depends(get_db),
    symbol: Optional[str] = None,
    _: User = Depends(get_current_user),
):
    """Manually trigger a synchronous scrape and wait for results."""
    try:
        if symbol:
            saved = await scrape_and_save_news(db, symbol=symbol)
            scored = score_unseen_news(db, symbol=symbol)
            return {
                'message': f'News scrape completed for {symbol}',
                'symbol': symbol,
                'saved_count': saved
            }
        else:
            # Scrape market data
            saved_stocks = await scrape_and_save_cse(db)
            # Also scrape general news
            saved_news = await scrape_and_save_news(db)
            return {
                'message': 'Full market and news scrape completed',
                'symbol': 'ALL',
                'saved_count': saved_stocks + saved_news
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")

@router.get('/sentiment/{symbol}', response_model=SentimentSummary)
def get_sentiment_summary(
    symbol: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get aggregated sentiment for a symbol."""
    from app.services.sentiment import get_symbol_sentiment_summary
    return get_symbol_sentiment_summary(db, symbol.upper())
