# app/schemas/chat.py — replace entirely
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class MessageIn(BaseModel):
    session_id: int
    content: str

class ChatMessageOut(BaseModel):
    message_id: int
    session_id: int
    sender_type: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime

    class Config:
        from_attributes = True

class ChatSessionCreate(BaseModel):
    title: Optional[str] = 'New Chat'

class ChatSessionOut(BaseModel):
    session_id: int
    user_id: UUID
    start_time: datetime
    is_active: bool
    messages: List[ChatMessageOut] = []

    class Config:
        from_attributes = True
