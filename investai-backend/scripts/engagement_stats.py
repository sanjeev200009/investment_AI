"""Engagement-rate stats from chat_messages — §13 target: > 5 AI messages per
active session (I-17).

Read-only over the live database (like verify_i04's read stages, this is a
reporting script, not a probe). Run from investai-backend:

    python -m scripts.engagement_stats
"""

from __future__ import annotations

from sqlalchemy import func

from app.database import SessionLocal
from app.models.chat import ChatMessage, ChatSession


def main() -> None:
    db = SessionLocal()
    try:
        sessions = db.query(ChatSession).count()
        if not sessions:
            print("No chat sessions yet — engage the agent first, then re-run.")
            return

        messages = db.query(ChatMessage).count()
        per_session = (
            db.query(ChatMessage.session_id, func.count(ChatMessage.message_id))
            .group_by(ChatMessage.session_id)
            .all()
        )
        counts = [c for _sid, c in per_session]
        ai_messages = (db.query(ChatMessage)
                       .filter(ChatMessage.sender_type == "assistant").count())

        print(f"sessions                : {sessions}")
        print(f"messages total          : {messages} ({ai_messages} AI)")
        print(f"messages per session    : mean {messages / sessions:.2f}, "
              f"median {sorted(counts)[len(counts) // 2]}")
        # §13 defines engagement as messages per session; the AI-message count
        # is the stricter form, since a user echo does not demonstrate use.
        if ai_messages:
            print(f"AI messages per session : {ai_messages / sessions:.2f} "
                  f"(§13 target > 5)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
