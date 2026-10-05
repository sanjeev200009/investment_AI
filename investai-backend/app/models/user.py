import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
	__tablename__ = "users"

	user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	email = Column(String(255), unique=True, nullable=False, index=True)
	full_name = Column(String(255), nullable=True)
	password_hash = Column(String(255), nullable=False)
	role = Column(String(50), nullable=False, default="user")
	is_email_verified = Column(Boolean, default=False)
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
	# FCM registration token for this user's current device. Existed in the
	# database since migration a1b2c3d4e5f6 but not on this model, so every
	# push lookup returned None forever (I-12). String(512): FCM v1 tokens run
	# ~140-250 chars and Google reserves the right to grow them.
	device_token = Column(String(512))
	# UI + LLM output language (en | si | ta). Same migration; same story —
	# the column was there, the model never mapped it, so the preference the
	# risk quiz collected was unreadable server-side (I-15).
	language = Column(String(5), nullable=False, default="en", server_default="en")

	user = relationship("User", back_populates="profile")


class RiskProfile(Base):
	__tablename__ = "risk_profiles"
	__table_args__ = (
		CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_profiles_score_range"),
		CheckConstraint("category IN ('Low', 'Medium', 'High')", name="ck_risk_profiles_category_values"),
	)

	risk_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)
	score = Column(Integer, nullable=False)
	category = Column(String(20), nullable=False)
	# The raw wizard responses that produced `score`, keyed by question id.
	# Kept so the score is auditable after the fact, and because two answers
	# are not risk indicators but are still needed elsewhere: Q13 sector
	# interest and Q14 preferred language. Nullable — profiles created before
	# this column existed have none.
	answers = Column(JSONB, nullable=True)
	# Correct answers to the five knowledge checks (0-5). Null when the user
	# took an older version of the quiz that had none.
	knowledge_score = Column(Integer, nullable=True)
	updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

	user = relationship("User", back_populates="risk_profile")
