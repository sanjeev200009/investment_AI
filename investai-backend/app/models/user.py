import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
	__tablename__ = "users"

	user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	email = Column(String(255), unique=True, nullable=False, index=True)
	password_hash = Column(String(255), nullable=False)
	role = Column(String(50), nullable=False, default="user")
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
	risk_profile = relationship("RiskProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
	portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
	investment_rules = relationship("InvestmentRule", back_populates="user", cascade="all, delete-orphan")
	chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
	notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
	__tablename__ = "user_profiles"

	profile_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)
	full_name = Column(String(150), nullable=False)
	age = Column(Integer)
	occupation = Column(String(120))
	income_level = Column(String(80))
	investment_experience = Column(String(80))

	user = relationship("User", back_populates="profile")


class RiskProfile(Base):
	__tablename__ = "risk_profiles"
	__table_args__ = (
		CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_profiles_score_range"),
	)

	risk_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)
	score = Column(Integer, nullable=False)
	category = Column(String(20), nullable=False)
	updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

	user = relationship("User", back_populates="risk_profile")
