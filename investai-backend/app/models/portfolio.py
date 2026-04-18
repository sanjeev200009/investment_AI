from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Portfolio(Base):
	__tablename__ = "portfolios"

	portfolio_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
	name = Column(String(120), nullable=False)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	user = relationship("User", back_populates="portfolios")
	holdings = relationship("PortfolioHolding", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioHolding(Base):
	__tablename__ = "portfolio_holdings"

	holding_id = Column(Integer, primary_key=True, index=True)
	portfolio_id = Column(Integer, ForeignKey("portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	quantity = Column(Float, nullable=False)
	avg_buy_price = Column(Float, nullable=False)

	portfolio = relationship("Portfolio", back_populates="holdings")


class InvestmentRule(Base):
	__tablename__ = "investment_rules"

	rule_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	condition_type = Column(String(80), nullable=False)
	threshold = Column(Float, nullable=False)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	user = relationship("User", back_populates="investment_rules")
