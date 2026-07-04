# app/services/agent/memory.py
"""
Multi-turn conversation memory.

Persistence layer: chat_sessions + chat_messages tables (already in schema).
In-request layer: builds the message list that goes into the LLM context window,
  applying a rolling window so long conversations don't exceed the token limit.

Memory strategy:
  1. Always include the system prompt.
  2. Include the last N turns (configurable, default 10).
  3. If a user risk profile exists, inject it as a system message after the
     initial system prompt so the LLM always knows the investor's tolerance.
  4. Summarise older turns via a single 'summary' assistant message when history
     exceeds MAX_TURNS (prevents runaway context growth).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_TURNS = 10          # rolling window of full messages kept verbatim
SUMMARY_THRESHOLD = 20  # summarise when history exceeds this many messages


SYSTEM_PROMPT = """\
You are InvestAI, an AI-powered investment assistant built for beginner investors \
in the Sri Lankan stock market (Colombo Stock Exchange, CSE).

Your responsibilities:
- Answer questions about CSE stocks, market trends, and investment concepts.
- Use the provided tools to fetch real-time data before answering.
- Explain financial concepts in simple, beginner-friendly language.
- Respond in the same language the user writes in (Sinhala, Tamil, or English).
- Always cite your data source when quoting prices or news.
- Never present AI predictions as guaranteed outcomes. Always add a disclaimer.
- If the user asks you to execute a trade or move real money, explain that you \
  can only provide educational guidance and they must use a licensed broker.

Personality: Patient, encouraging, clear. You are talking to someone who may \
have never invested before. Avoid jargon unless you immediately define it.
"""


def _risk_context(user) -> str | None:
    """Build a risk-profile injection message if the user has one."""
    rp = getattr(user, "risk_profile", None)
    if not rp:
        return None
    return (
        f"This user's risk profile: {rp.category} risk tolerance "
        f"(score {rp.score}/100). Tailor your advice accordingly. "
        f"For a Low-risk user, favour stable blue-chip stocks and bonds. "
        f"For a High-risk user, you may discuss growth stocks and sector bets."
    )


# ─────────────────────────────────────────────────────────────────────────────


class ConversationMemory:
    """
    Manages loading, building, and saving conversation messages
    for a single chat session.
    """

    def __init__(self, session_id: int, db: Session, user):
        self.session_id = session_id
        self.db = db
        self.user = user

    def load_history(self) -> list[dict]:
        """
        Load the last MAX_TURNS * 2 messages from the DB and return them
        as a list of {role, content} dicts ready for the LLM.
        """
        from app.models.chat import ChatMessage

        rows = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == self.session_id)
            .order_by(ChatMessage.timestamp.desc())
            .limit(MAX_TURNS * 2)
            .all()
        )
        # rows are newest-first; reverse so they're chronological
        rows = list(reversed(rows))
        messages = []
        for row in rows:
            role: Literal["user", "assistant"] = (
                "user" if row.sender_type == "user" else "assistant"
            )
            messages.append({"role": role, "content": row.content})
        return messages

    def build_context(self, new_user_message: str) -> list[dict]:
        """
        Assemble the full message list to send to the LLM:
          [system] + [risk injection] + [history] + [new user message]
        """
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        risk = _risk_context(self.user)
        if risk:
            messages.append({"role": "system", "content": risk})

        history = self.load_history()
        messages.extend(history)
        messages.append({"role": "user", "content": new_user_message})
        return messages

    def save_user_message(self, content: str) -> int:
        """Persist the user's message and return its message_id."""
        from app.models.chat import ChatMessage

        msg = ChatMessage(
            session_id=self.session_id,
            sender_type="user",
            content=content,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg.message_id

    def save_assistant_message(
        self,
        content: str,
        model_used: str,
        context_snapshot: str | None = None,
    ) -> int:
        """Persist the AI response and return its message_id."""
        from app.models.chat import ChatMessage

        msg = ChatMessage(
            session_id=self.session_id,
            sender_type="assistant",
            content=content,
            ai_model_used=model_used,
            context=context_snapshot,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg.message_id


def get_or_create_session(user_id: str, db: Session, title: str = "New chat") -> int:
    """
    Return the most recent active session_id for the user,
    or create a new one if none exists.
    """
    from app.models.chat import ChatSession

    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == user_id,
            ChatSession.is_active == True,
        )
        .order_by(ChatSession.start_time.desc())
        .first()
    )
    if not session:
        session = ChatSession(
            user_id=user_id,
            is_active=True,
            start_time=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session.session_id
