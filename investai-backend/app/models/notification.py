from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Notification(Base):
	__tablename__ = "notifications"

	notif_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
	type = Column(String(50), nullable=False)
	message = Column(Text, nullable=False)
	is_read = Column(Boolean, default=False, nullable=False)
	timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	user = relationship("User", back_populates="notifications")
