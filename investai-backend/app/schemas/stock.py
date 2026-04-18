from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MarketDataBase(BaseModel):
    symbol: str
    price: float
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None

class MarketData(MarketDataBase):
    market_id: int
    recorded_at: datetime

    class Config:
        from_attributes = True

class NewsSentimentBase(BaseModel):
    symbol: str
    headline: str
    url: str
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None

class NewsSentiment(NewsSentimentBase):
    news_id: int
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PricePredictionBase(BaseModel):
    symbol: str
    predicted_price: float
    model_version: str

class PricePrediction(PricePredictionBase):
    prediction_id: int
    generated_at: datetime

    class Config:
        from_attributes = True
