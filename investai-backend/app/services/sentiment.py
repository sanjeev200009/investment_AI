# app/services/sentiment.py
import logging
from typing import Optional
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sqlalchemy.orm import Session
from app.models.stock import NewsSentiment

logger = logging.getLogger(__name__)

_analyzer = SentimentIntensityAnalyzer()

def analyse_text(text: str) -> tuple[float, str]:
    """
    Score a piece of text using VADER.
    Returns (compound_score, label) where label is 'Positive'/'Negative'/'Neutral'.
    """
    scores = _analyzer.polarity_scores(text)
    compound = scores['compound']
    if compound >= 0.05:
        label = 'Positive'
    elif compound <= -0.05:
        label = 'Negative'
    else:
        label = 'Neutral'
    return compound, label

def score_unseen_news(db: Session, symbol: Optional[str] = None) -> int:
    """
    Find all NewsSentiment rows with no sentiment score yet,
    run VADER, and write results back. Returns count of rows scored.
    """
    query = db.query(NewsSentiment).filter(
        NewsSentiment.sentiment_score == None  # noqa: E711
    )
    if symbol:
        query = query.filter(NewsSentiment.symbol == symbol)
    
    rows = query.all()
    for row in rows:
        text = row.headline + ' ' + (row.summary or '')
        score, label = analyse_text(text)
        row.sentiment_score = score
        row.sentiment_label = label
    
    db.commit()
    logger.info('Scored %d news articles', len(rows))
    return len(rows)

def get_symbol_sentiment_summary(db: Session, symbol: str) -> dict:
    """
    Return aggregated sentiment stats for a symbol.
    Used by the AI agent context builder.
    """
    rows = db.query(NewsSentiment).filter(
        NewsSentiment.symbol == symbol,
        NewsSentiment.sentiment_score != None  # noqa
    ).order_by(NewsSentiment.scraped_at.desc()).limit(20).all()

    if not rows:
        return {'symbol': symbol, 'count': 0, 'avg_score': 0.0, 'label': 'No data'}
    
    scores = [r.sentiment_score for r in rows]
    avg = sum(scores) / len(scores)
    label = 'Positive' if avg >= 0.05 else ('Negative' if avg <= -0.05 else 'Neutral')
    
    return {
        'symbol': symbol,
        'count': len(rows),
        'avg_score': round(avg, 4),
        'label': label,
        'recent_headlines': [r.headline for r in rows[:5]]
    }
