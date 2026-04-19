# app/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db, get_current_user
from app.models.chat import ChatSession, ChatMessage
from app.models.user import User
from app.schemas.chat import ChatSessionCreate, ChatSessionOut, MessageIn, ChatMessageOut

router = APIRouter(prefix='/chat', tags=['Chat'])

@router.get('/sessions', response_model=List[ChatSessionOut])
def get_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all chat sessions for the current user."""
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.user_id)
        .order_by(ChatSession.start_time.desc())
        .all()
    )

@router.post('/sessions', response_model=ChatSessionOut, status_code=201)
def create_session(
    payload: ChatSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new chat session."""
    session = ChatSession(user_id=user.user_id, is_active=True)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.post('/message', response_model=ChatMessageOut)
def send_message(
    payload: MessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a message to the AI agent and receive a response."""
    # Validate session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.session_id == payload.session_id,
        ChatSession.user_id == user.user_id,
    ).first()
    
    if not session:
        raise HTTPException(404, 'Chat session not found')

    # Save user message
    user_msg = ChatMessage(
        session_id=payload.session_id,
        sender_type='user',
        content=payload.content,
    )
    db.add(user_msg)
    db.commit()

    # Build conversation history for AI context (last 20 messages)
    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == payload.session_id)
        .order_by(ChatMessage.timestamp.asc())
        .limit(20)
        .all()
    )
    
    history = [
        {'role': 'user' if r.sender_type == 'user' else 'assistant',
         'content': r.content}
        for r in history_rows[:-1]  # exclude the message we just saved
    ]

    # Call AI agent
    from app.services.ai_agent import chat_with_agent
    reply_text = chat_with_agent(db, user, history, payload.content)

    # Save assistant reply
    ai_msg = ChatMessage(
        session_id=payload.session_id,
        sender_type='assistant',
        content=reply_text,
        ai_model_used='claude-sonnet-4-20250514',
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)
    
    return ai_msg

@router.delete('/sessions/{session_id}', status_code=204)
def close_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Close / deactivate a chat session."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user.user_id
    ).first()
    
    if not session:
        raise HTTPException(404, 'Session not found')
    
    session.is_active = False
    db.commit()
