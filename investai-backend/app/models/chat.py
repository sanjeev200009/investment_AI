from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ChatSession(Base):
	__tablename__ = "chat_sessions"

	session_id = Column(Integer, primary_key=True, index=True)
	user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
	start_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
	end_time = Column(DateTime(timezone=True))
	is_active = Column(Boolean, default=True, nullable=False)

	user = relationship("User", back_populates="chat_sessions")
	messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
	__tablename__ = "chat_messages"

	message_id = Column(Integer, primary_key=True, index=True)
	session_id = Column(Integer, ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
	sender_type = Column(String(30), nullable=False)
	content = Column(Text, nullable=False)
	context = Column(Text)
	ai_model_used = Column(String(80))
	timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

	session = relationship("ChatSession", back_populates="messages")
