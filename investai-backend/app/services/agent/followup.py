# app/services/agent/followup.py
"""The chat's follow-up flow: every new question gets ONE follow-up first.

    1. The user asks a new question.
       -> ask_followup() writes one short follow-up question, with 2-4 answer
          choices on a last line "OPTIONS: a | b | c" (the app shows them as
          buttons). It is saved with ai_model_used = FOLLOWUP_TAG.
    2. The user answers it.
       -> pending_followup() sees that the bot's last message was that
          follow-up and returns (original question, follow-up).
       -> combined_question() joins the original question, the follow-up and
          the user's answer into one request.
    3. The AI agent (core.py) answers the ORIGINAL question with that combined
       request, using its tools and live CSE data as usual.

The next message after an answer counts as a new question, so the cycle repeats.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage
from app.services import llm
from app.services.agent.memory import LANGUAGE_NAMES, clean_script

logger = logging.getLogger(__name__)

# Marks the bot's follow-up message in chat_messages.ai_model_used.
FOLLOWUP_TAG = "followup"

PROMPT = (
    "You help beginner investors on the Colombo Stock Exchange (Sri Lanka).\n"
    "The user asked: \"{question}\"\n\n"
    "Before answering, ask them ONE short follow-up question whose answer will "
    "make your reply more useful and personal. Good things to ask: their goal, "
    "how much they want to invest, their time frame, which company or sector they "
    "mean, or how much they already know about the topic.\n"
    "Write in {language}, in simple, natural everyday words a beginner understands. "
    "Each answer choice must be a short, correct answer to YOUR question (1 to 5 words).\n"
    "Output exactly two lines and nothing else:\n"
    "line 1: the follow-up question\n"
    "line 2: OPTIONS: 2 to 4 short answer choices separated by \" | \""
)

# Used when the LLM is unavailable, so the flow never breaks.
FALLBACK = {
    "en": "To give you a more useful answer: how much do you already know about this?\n"
          "OPTIONS: I'm a complete beginner | I know the basics | Explain in detail",
    "si": "වඩා ප්‍රයෝජනවත් පිළිතුරක් දීමට: ඔබ මේ ගැන කොපමණ දන්නවාද?\n"
          "OPTIONS: මම සම්පූර්ණ ආරම්භකයෙක් | මූලික දේ දන්නවා | විස්තරාත්මකව පැහැදිලි කරන්න",
    "ta": "இன்னும் பயனுள்ள பதில் தர: இதைப் பற்றி உங்களுக்கு எவ்வளவு தெரியும்?\n"
          "OPTIONS: நான் முற்றிலும் புதியவர் | அடிப்படைகள் தெரியும் | விரிவாக விளக்கவும்",
}


async def ask_followup(question: str, lang: str | None) -> str:
    """Step 1: one follow-up question for a new user question, ending with OPTIONS."""
    # The free models write unnatural Sinhala and Tamil choices (tested Oct 2026),
    # so those languages use the hand-written follow-up, which fits any question.
    if lang in ("si", "ta"):
        return FALLBACK[lang]
    language = LANGUAGE_NAMES.get(lang, "English")
    try:
        text = await llm.complete_text(PROMPT.format(question=question[:500], language=language),
                                       role=llm.Role.UTILITY, temperature=0.4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Follow-up generation failed: %s", exc)
        text = None
    text = clean_script((text or "").strip(), lang)
    if "OPTIONS:" not in text.upper() or len(text) > 600:
        text = FALLBACK.get(lang or "en", FALLBACK["en"])
    return text


def pending_followup(db: Session, session_id: int) -> tuple[str, str] | None:
    """Step 2: (original question, follow-up) when the bot's last message in this
    chat was a follow-up still waiting for the user's answer, else None."""
    last_two = (db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.timestamp.desc(), ChatMessage.message_id.desc())
                .limit(2).all())
    if len(last_two) < 2:
        return None
    bot, user = last_two
    if bot.sender_type != "assistant" or bot.ai_model_used != FOLLOWUP_TAG or user.sender_type != "user":
        return None
    return user.content, bot.content


def combined_question(original: str, followup: str, answer: str) -> str:
    """Step 2: the original question, the follow-up and the user's answer, as one
    request for the agent."""
    asked = "\n".join(line for line in followup.splitlines()
                      if not line.strip().upper().startswith("OPTIONS:")).strip()
    return (f"My question: {original}\n"
            f"You asked me: {asked}\n"
            f"My answer: {answer}\n\n"
            "Now answer my question, using my answer to make it fit me. "
            "Do not ask me another question.")
