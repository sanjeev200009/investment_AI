# app/models/__init__.py
from app.database import Base

from .chat import ChatSession, ChatMessage
from .notification import Notification
from .portfolio import Portfolio, PortfolioHolding, InvestmentRule
from .stock import MarketData, PricePrediction, NewsSentiment
from .otp import OTPCode
from .user import User, UserProfile, RiskProfile
