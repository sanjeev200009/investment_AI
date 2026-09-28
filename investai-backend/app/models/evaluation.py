"""Records kept only so the evaluation plan can be measured (E5, E7).

recommendation_snapshots: the top picks per risk category, saved once per
trading day, so they can later be compared with what prices actually did.
lesson_views: one row each time a user opens a lesson.
"""
from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class RecommendationSnapshot(Base):
	__tablename__ = "recommendation_snapshots"
	__table_args__ = (UniqueConstraint("snapshot_date", "risk_category", "symbol",
	                                   name="uq_rec_snapshot_day_cat_symbol"),)

	id = Column(Integer, primary_key=True)
	snapshot_date = Column(Date, nullable=False, index=True)
	risk_category = Column(String(20), nullable=False)
	rank = Column(Integer, nullable=False)
	symbol = Column(String(20), nullable=False)
	score = Column(Float, nullable=False)
	price = Column(Float, nullable=False)
	model_version = Column(String(30), nullable=False)
	created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LessonView(Base):
	__tablename__ = "lesson_views"

	id = Column(Integer, primary_key=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
	lesson_id = Column(String(60), nullable=False)
	viewed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
