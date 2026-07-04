# app/routers/chat.py
"""
Chat router — fully implemented with:
  - Session management (create, list, close)
  - SSE streaming endpoint for real-time AI responses
  - Non-streaming fallback for simpler clients
  - Message history retrieval
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.services.agent import get_or_create_session, stream_agent, run_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class SessionOut(BaseModel):
    session_id: int
    is_active: bool
    start_time: datetime
    message_count: int

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    message_id: int
    sender_type: str
    content: str
    ai_model_used: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    message: str
    session_id: Optional[int] = None   # if None, uses or creates the active session
    language: str = "en"               # en | si | ta


class SendMessageResponse(BaseModel):
    message_id: int
    session_id: int
    response: str
    tools_used: List[str] = []


# ─────────────────────────────────────────────────────────────────────────────
# Session endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    active_only: bool = Query(False),
):
    """List all chat sessions for the authenticated user."""
    q = db.query(ChatSession).filter(ChatSession.user_id == user.user_id)
    if active_only:
        q = q.filter(ChatSession.is_active == True)
    sessions = q.order_by(ChatSession.start_time.desc()).all()

    result = []
    for s in sessions:
        msg_count = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == s.session_id)
            .count()
        )
        result.append(
            SessionOut(
                session_id=s.session_id,
                is_active=s.is_active,
                start_time=s.start_time,
                message_count=msg_count,
            )
        )
    return result


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new chat session. Previous active sessions remain open."""
    session = ChatSession(
        user_id=user.user_id,
        is_active=True,
        start_time=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionOut(
        session_id=session.session_id,
        is_active=session.is_active,
        start_time=session.start_time,
        message_count=0,
    )


@router.delete("/sessions/{session_id}", status_code=204)
def close_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a session as inactive (soft close)."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user.user_id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")
    session.is_active = False
    session.end_time = datetime.now(timezone.utc)
    db.commit()


@router.get("/sessions/{session_id}/messages", response_model=List[MessageOut])
def get_messages(
    session_id: int,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve message history for a session."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user.user_id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp.asc())
        .limit(limit)
        .all()
    )
    return messages


# ─────────────────────────────────────────────────────────────────────────────
# Streaming message endpoint (primary)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/stream")
async def stream_message(
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Send a message to the AI agent and stream the response via SSE.

    The mobile client should consume this as an EventSource / SSE stream.

    Each event is a JSON object:
      {"type": "tool_start",  "tool": "get_stock_data",  "args": {...}}
      {"type": "tool_result", "tool": "get_stock_data",  "summary": "HNB: LKR 192..."}
      {"type": "token",       "content": "Based on the..."}
      {"type": "done",        "message_id": 123}
      {"type": "error",       "detail": "..."}

    React Native usage:
      import EventSource from 'react-native-sse';
      const es = new EventSource(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id }),
      });
      es.addEventListener('message', e => { const d = JSON.parse(e.data); ... });
    """
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    session_id = body.session_id or get_or_create_session(
        str(user.user_id), db
    )

    # Verify session belongs to this user
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user.user_id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for chunk in stream_agent(
                user_message=body.message,
                session_id=session_id,
                db=db,
                user=user,
            ):
                yield chunk
        except Exception as e:
            logger.exception("Stream error: %s", e)
            import json
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Non-streaming fallback (for simple HTTP clients / testing)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/message", response_model=SendMessageResponse)
async def send_message(
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Send a message and wait for the full response (non-streaming).
    Use /stream for the mobile app; use this for testing or simple clients.
    """
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    session_id = body.session_id or get_or_create_session(
        str(user.user_id), db
    )

    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user.user_id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    try:
        response_text, tool_calls_log = await run_agent(
            user_message=body.message,
            session_id=session_id,
            db=db,
            user=user,
        )
    except Exception as e:
        logger.exception("Agent error: %s", e)
        raise HTTPException(500, f"Agent error: {str(e)}")

    # Get the saved message_id
    last_msg = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.sender_type == "assistant",
        )
        .order_by(ChatMessage.timestamp.desc())
        .first()
    )

    return SendMessageResponse(
        message_id=last_msg.message_id if last_msg else -1,
        session_id=session_id,
        response=response_text,
        tools_used=[tc["tool"] for tc in tool_calls_log],
    )
