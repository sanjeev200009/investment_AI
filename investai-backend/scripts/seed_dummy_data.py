import sys
import os
import random
from datetime import datetime, timedelta

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User, UserProfile, RiskProfile
from app.models.portfolio import Portfolio, PortfolioHolding, InvestmentRule
from app.models.stock import MarketData, NewsSentiment, PricePrediction
from app.models.notification import Notification
from app.models.chat import ChatSession, ChatMessage

def seed_database():
    db = SessionLocal()
    try:
        # 1. Create or get User
        email = "sanjaysanjeev2000@gmail.com"
        clerk_sub = "user_3G4OGmZzJJSqIVRCJcLjlMq3OGf"
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print("Creating mock user...")
            user = User(
                email=email,
                password_hash=clerk_sub,
                full_name="sivasuthakaran Sanjeev",
                is_email_verified=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # Create UserProfile
            profile = UserProfile(
                user_id=user.user_id,
                full_name="sivasuthakaran Sanjeev",
                age=24,
                occupation="Software Engineer",
                income_level="$50,000 - $100,000",
                investment_experience="Intermediate"
            )
            db.add(profile)
            
            # Create RiskProfile
            risk_profile = RiskProfile(
                user_id=user.user_id,
                score=75,
                category="High"
            )
            db.add(risk_profile)
            db.commit()

        # 2. Market Data & News
        symbols = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
        print("Creating Market Data...")
        for sym in symbols:
            # Generate random realistic price
            base_price = random.uniform(100, 500)
            change = random.uniform(-10, 10)
            
            # Insert MarketData
            md = MarketData(
                symbol=sym,
                price=round(base_price, 2),
                change=round(change, 2),
                change_pct=round((change/base_price)*100, 2),
                volume=random.randint(1000000, 50000000),
                market_cap=random.uniform(1e10, 2e12)
            )
            db.add(md)
            
            # Insert NewsSentiment
            news = NewsSentiment(
                symbol=sym,
                headline=f"Important updates regarding {sym} earnings and market strategy",
                url=f"https://finance.yahoo.com/quote/{sym}",
                source="Yahoo Finance",
                summary=f"{sym} announced new strategies to tackle the growing market demand.",
                sentiment_score=random.uniform(-1, 1),
                sentiment_label=random.choice(["Positive", "Neutral", "Negative"]),
                published_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
            )
            db.add(news)
            
            # PricePrediction
            pred = PricePrediction(
                symbol=sym,
                predicted_price=round(base_price * random.uniform(0.9, 1.2), 2),
                model_version="v2.1.0"
            )
            db.add(pred)
            
        db.commit()
        
        # 3. Portfolio & Holdings
        print("Creating Portfolio...")
        portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.user_id).first()
        if not portfolio:
            portfolio = Portfolio(
                user_id=user.user_id,
                name="Main Tech Portfolio"
            )
            db.add(portfolio)
            db.commit()
            db.refresh(portfolio)
            
            # Add holdings
            for sym in ['AAPL', 'TSLA', 'NVDA']:
                holding = PortfolioHolding(
                    portfolio_id=portfolio.portfolio_id,
                    symbol=sym,
                    quantity=round(random.uniform(5, 50), 2),
                    avg_buy_price=round(random.uniform(100, 300), 2)
                )
                db.add(holding)
            db.commit()

        # 4. Investment Rules
        print("Creating Investment Rules...")
        if db.query(InvestmentRule).filter(InvestmentRule.user_id == user.user_id).count() == 0:
            rule1 = InvestmentRule(
                user_id=user.user_id,
                symbol="AAPL",
                condition_type="Price Drops Below",
                threshold=150.0
            )
            rule2 = InvestmentRule(
                user_id=user.user_id,
                symbol="TSLA",
                condition_type="Price Rises Above",
                threshold=300.0
            )
            db.add_all([rule1, rule2])
            db.commit()

        # 5. Notifications
        print("Creating Notifications...")
        if db.query(Notification).filter(Notification.user_id == user.user_id).count() == 0:
            notifs = [
                Notification(user_id=user.user_id, type="Alert", message="AAPL price dropped below $150 threshold!"),
                Notification(user_id=user.user_id, type="News", message="New positive sentiment detected for NVDA."),
                Notification(user_id=user.user_id, type="System", message="Welcome to InvestAI! Your portfolio is set up.")
            ]
            db.add_all(notifs)
            db.commit()

        # 6. Chat Sessions
        print("Creating Chat Sessions...")
        if db.query(ChatSession).filter(ChatSession.user_id == user.user_id).count() == 0:
            session = ChatSession(user_id=user.user_id)
            db.add(session)
            db.commit()
            db.refresh(session)
            
            messages = [
                ChatMessage(session_id=session.session_id, sender_type="user", content="What do you think about TSLA stock?"),
                ChatMessage(session_id=session.session_id, sender_type="ai", content="TSLA has shown strong volatility but our models predict a positive upward trend in the next quarter.", ai_model_used="claude-3-opus")
            ]
            db.add_all(messages)
            db.commit()

        print("Database seeding completed successfully!")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
