from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class ChatMessageBase(BaseModel):
    content: str
    role: str # 'user' or 'assistant'

class ChatMessageCreate(ChatMessageBase):
    session_id: int

class ChatMessage(ChatMessageBase):
    message_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionBase(BaseModel):
    title: Optional[str] = None

class ChatSessionCreate(ChatSessionBase):
    pass

class ChatSession(ChatSessionBase):
    session_id: int
    user_id: UUID
    created_at: datetime
    messages: List[ChatMessage] = []

    class Config:
        from_attributes = True
