from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func

from app.database import Base


class MarketData(Base):
	__tablename__ = "market_data"

	market_id = Column(Integer, primary_key=True, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	price = Column(Float, nullable=False)
	change = Column("change", Float)
	change_pct = Column(Float)
	volume = Column(Float)
	market_cap = Column(Float)
	recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NewsSentiment(Base):
	__tablename__ = "news_sentiment"

	news_id = Column(Integer, primary_key=True, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	headline = Column(String(500), nullable=False)
	url = Column(String(1000), nullable=False)
	source = Column(String(120))
	summary = Column(Text)
	sentiment_score = Column(Float)
	sentiment_label = Column(String(20))
	published_at = Column(DateTime(timezone=True))
	scraped_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PricePrediction(Base):
	__tablename__ = "price_predictions"

	prediction_id = Column(Integer, primary_key=True, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	predicted_price = Column(Float, nullable=False)
	model_version = Column(String(50), nullable=False)
	generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
