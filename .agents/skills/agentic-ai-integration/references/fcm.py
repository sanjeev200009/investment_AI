# app/services/fcm.py
"""
Firebase Cloud Messaging push notification service.
Looks up the user's stored device token and sends a push.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

FCM_URL = "https://fcm.googleapis.com/fcm/send"


def _get_fcm_key() -> str:
    from app.config import get_settings
    return get_settings().FCM_SERVER_KEY


async def send_push(device_token: str, title: str, body: str, data: dict = {}) -> bool:
    """Send a push notification to a specific device token."""
    key = _get_fcm_key()
    if not key:
        logger.warning("FCM_SERVER_KEY not set — skipping push")
        return False

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                FCM_URL,
                headers={
                    "Authorization": f"key={key}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": device_token,
                    "notification": {
                        "title": title,
                        "body": body,
                        "sound": "default",
                    },
                    "data": {**data, "click_action": "FLUTTER_NOTIFICATION_CLICK"},
                    "priority": "high",
                },
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("failure", 0) > 0:
                    logger.warning("FCM partial failure: %s", result)
                    return False
                return True
            logger.error("FCM HTTP %s: %s", resp.status_code, resp.text[:200])
            return False
        except Exception as e:
            logger.error("FCM send failed: %s", e)
            return False


async def send_push_to_user(
    db: Session,
    user_id: str,
    title: str,
    body: str,
    data: dict = {},
) -> bool:
    """
    Look up the user's device token from the DB and send a push.
    Returns True if at least one token received the notification.
    """
    from app.models.user import User

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        logger.warning("FCM: user %s not found", user_id)
        return False

    # device_token stored on user_profiles (added in migration)
    profile = getattr(user, "profile", None)
    device_token = getattr(profile, "device_token", None) if profile else None

    if not device_token:
        logger.info("FCM: no device token for user %s", user_id)
        return False

    return await send_push(device_token, title, body, data)
