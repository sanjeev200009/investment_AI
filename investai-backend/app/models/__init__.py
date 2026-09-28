# app/models/__init__.py
#
# Re-exports for `from app.models import X`. Note that Alembic does not rely on
# this list — alembic/env.py imports the model *modules* directly, so a table
# missing here is still in Base.metadata and still migrates. MarketIndex and
# MarketIndexLatest were absent from this file between f6a7b8c9d0e1 and
# a7b8c9d0e1f2 for exactly that reason: nothing broke, so nothing surfaced it.
from app.database import Base

from .chat import ChatSession, ChatMessage
from .notification import Notification
from .portfolio import (InvestmentRule, Portfolio, PortfolioHolding,
                        PortfolioSnapshot, Watchlist)
from .stock import (CompanyInfo, DailyClose, MarketData, MarketDataLatest,
                    MarketIndex, MarketIndexLatest, NewsSentiment,
                    PricePrediction)
from .otp import OTPCode, PasswordResetToken
from .user import User, UserProfile, RiskProfile
from .evaluation import LessonView, RecommendationSnapshot
