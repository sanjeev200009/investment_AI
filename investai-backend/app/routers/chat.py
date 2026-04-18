from fastapi import APIRouter, Depends
from typing import List
from app.schemas.chat import ChatSession, ChatMessage, ChatSessionCreate

router = APIRouter()

@router.get("/sessions", response_model=List[ChatSession])
def get_sessions():
    """
    Get all chat sessions for the user.
    """
    return []

@router.post("/sessions", response_model=ChatSession)
def create_session(session_in: ChatSessionCreate):
    """
    Create a new AI chat session.
    """
    return None

@router.post("/message", response_model=ChatMessage)
def send_message(message_in: str):
    """
    Send a message to the AI agent and get a response.
    """
    return None
