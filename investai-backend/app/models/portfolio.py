from sqlalchemy import (Column, Date, DateTime, Float, ForeignKey, Integer,
                        String, UniqueConstraint, func)
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
	snapshots = relationship("PortfolioSnapshot", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioSnapshot(Base):
	"""One row per portfolio per day — what it was actually worth that evening.

	The dashboard's ``weekly_history`` was ``current_value × [0.85, 0.82, 0.94,
	1.0]``: a four-point series derived from the present value, drawn as a
	performance chart. It could only ever show the same shape — a dip then a
	recovery to exactly today — no matter what the portfolio had done, and it
	implied three past valuations that were never taken.

	Valuation has to be recorded when it happens. Unlike a price series there is
	nothing to recover it from later: holdings change, and yesterday's value needs
	yesterday's quantities as well as yesterday's prices. Once a day passes
	unrecorded it is gone.

	``total_cost`` is stored alongside the value rather than derived at read time
	for the same reason — it is the cost basis *as it stood that day*, so a
	later purchase cannot retroactively change what an earlier day's return was.
	"""

	__tablename__ = "portfolio_snapshots"

	# Keyed on portfolio, not user: a user may hold several portfolios and each
	# needs its own line. The primary key's btree serves the only read — WHERE
	# portfolio_id = ? ORDER BY snapshot_date — so there is no second index.
	portfolio_id = Column(Integer, ForeignKey("portfolios.portfolio_id", ondelete="CASCADE"),
	                      primary_key=True)
	snapshot_date = Column(Date, primary_key=True)

	total_value = Column(Float, nullable=False)
	total_cost = Column(Float, nullable=False)
	# How many of the day's holdings had a real quote behind them. A snapshot where
	# this is below holdings_count is partly valued at cost basis, and a caller that
	# cares about accuracy can tell.
	holdings_count = Column(Integer, nullable=False)
	priced_count = Column(Integer, nullable=False)

	# Which trading session those prices came from, as the exchange timestamped it.
	#
	# ``snapshot_date`` is deliberately a *calendar* date, not a trading date — the
	# opposite of ``DailyClose.trade_date``, and for a reason worth stating. "This
	# stock closed at X on Sunday" is meaningless because there was no close. "This
	# portfolio was worth X on Sunday" is a true statement: nothing traded, so it
	# held its Friday value. Keying on the trading date instead would collapse
	# those days into one point and, worse, would let a holding bought on Wednesday
	# retroactively overwrite what the portfolio was worth at Tuesday's close.
	#
	# The cost of the calendar choice is that a closed market yields consecutive
	# identical values. This column is what stops that reading as a stalled
	# scraper: same ``priced_at`` across three days means the market was shut.
	priced_at = Column(DateTime(timezone=True))

	updated_at = Column(DateTime(timezone=True), server_default=func.now(),
	                    onupdate=func.now(), nullable=False)

	portfolio = relationship("Portfolio", back_populates="snapshots")


class PortfolioHolding(Base):
	__tablename__ = "portfolio_holdings"

	holding_id = Column(Integer, primary_key=True, index=True)
	portfolio_id = Column(Integer, ForeignKey("portfolios.portfolio_id", ondelete="CASCADE"), nullable=False, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	quantity = Column(Float, nullable=False)
	avg_buy_price = Column(Float, nullable=False)

	portfolio = relationship("Portfolio", back_populates="holdings")


class Watchlist(Base):
	"""One row per (user, symbol) the user follows.

	The table existed since migration a1b2c3d4e5f6 with a unique constraint on
	(user_id, symbol) and nothing else: no ORM model, no router, no endpoint —
	so every user's "watchlist" was the same top-10-by-volume page, identical
	for everyone (I-09). The model deliberately adds nothing to that shape: the
	migration already promised `user_id` + `symbol` + a timestamp, and every
	read the app wants is a join against market_data_latest for the quote.
	"""

	__tablename__ = "watchlist"

	watchlist_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	__table_args__ = (
		UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
	)

	user = relationship("User", backref="watchlist_items")


class InvestmentRule(Base):
	__tablename__ = "investment_rules"

	rule_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
	symbol = Column(String(20), nullable=False, index=True)
	condition_type = Column(String(80), nullable=False)
	threshold = Column(Float, nullable=False)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	# When this rule last produced an alert. Dedup keys on the rule itself; it
	# used to LIKE-match the symbol inside LLM-written notification text.
	last_triggered_at = Column(DateTime(timezone=True), nullable=True)

	user = relationship("User", back_populates="investment_rules")
