"""
Firebase Cloud Messaging push notification service.

Sends over **FCM HTTP v1** through `firebase-admin`, whose service-account
credentials are swapped for a short-lived OAuth token per send. The previous
implementation POSTed to `https://fcm.googleapis.com/fcm/send` with
`Authorization: key=<server key>` — the legacy API Google decommissioned in
June 2024, which now returns 404 on every call. `firebase-admin` was already a
dependency; it was simply never used (I-12).

Credential file: FIREBASE_CREDENTIALS_PATH (default `firebase-key.json`),
gitignored. Without it, pushes are skipped with a warning rather than raising —
the same degrade-not-break posture as the email service.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#firebase-admin is lazy-imported so the API process still boots if it is
# missing from an environment that never pushes.
_cred = None
_messaging = None
_init_lock = threading.Lock()
_init_attempted = False


def _get_messaging():
    """Initialise firebase_admin once, lazily. None when unavailable."""
    global _cred, _messaging, _init_attempted
    with _init_lock:
        if _messaging is not None or _init_attempted:
            return _messaging
        _init_attempted = True
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
        except ImportError:
            logger.warning("firebase-admin not installed — push disabled")
            return None

        import json
        from app.config import get_settings
        path = get_settings().FIREBASE_CREDENTIALS_PATH
        # FIREBASE_CREDENTIALS_JSON holds the service-account JSON itself, for
        # hosts where the key cannot live on disk. It wins over the file path.
        inline = get_settings().FIREBASE_CREDENTIALS_JSON.strip()
        try:
            _cred = credentials.Certificate(json.loads(inline) if inline else path)
            path = "FIREBASE_CREDENTIALS_JSON" if inline else path
            firebase_admin.initialize_app(_cred)
            _messaging = messaging
            logger.info("FCM initialised from %s", path)
        except Exception as exc:  # noqa: BLE001 - missing/invalid key file
            logger.warning(
                "FCM unavailable (could not load %s: %s) — push disabled. "
                "Place the service-account JSON there to enable.",
                path, type(exc).__name__)
        return _messaging


async def send_push(device_token: str, title: str, body: str,
                    data: dict = {}) -> bool:
    """Send one push via FCM HTTP v1. Returns delivery success."""
    return await _send_push_status(device_token, title, body, data) == "ok"


async def _send_push_status(device_token: str, title: str, body: str,
                            data: dict = {}) -> str:
    """Send one push; returns "ok", "unregistered" or "failed".

    firebase_admin's send is blocking; offloaded to a thread so callers in the
    event loop (rules evaluator, notification service) do not stall it.
    """
    messaging = _get_messaging()
    if messaging is None:
        return "failed"

    # FCM data payloads must be string→string; anything else is rejected with
    # an error that surfaces two layers away from the bug.
    str_data = {k: str(v) for k, v in (data or {}).items()}
    str_data.setdefault("type", "general")

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=str_data,
        token=device_token,
        android=messaging.AndroidConfig(priority="high"),
    )

    def _send():
        try:
            messaging.send(message)
            return "ok"
        except messaging.UnregisteredError:
            # Token rotated or the app was uninstalled — permanent, so the
            # caller should stop using it. Logged at warning, not error.
            logger.warning("FCM token is unregistered (stale device token)")
            return "unregistered"
        except messaging.SenderIdMismatchError:
            logger.error("FCM token belongs to a different sender/project — "
                         "check FIREBASE_CREDENTIALS_PATH matches the app's "
                         "Firebase project")
            return "failed"
        except Exception as exc:  # noqa: BLE001 - transient FCM failures
            logger.error("FCM send failed: %s: %s", type(exc).__name__, exc)
            return "failed"

    import asyncio
    return await asyncio.to_thread(_send)


async def send_push_to_user(
    db: Session,
    user_id: str,
    title: str,
    body: str,
    data: dict = {},
) -> bool:
    """
    Look up the user's device token from the DB and send a push.
    Returns True if the push was delivered.
    """
    from app.models.user import User

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        logger.warning("FCM: user %s not found", user_id)
        return False

    profile = getattr(user, "profile", None)
    device_token = getattr(profile, "device_token", None) if profile else None

    if not device_token:
        logger.info("FCM: no device token registered for user %s", user_id)
        return False

    status = await _send_push_status(device_token, title, body, data)
    if status == "unregistered":
        # Dead for good; clear it so every later alert stops paying for a
        # doomed FCM round trip. The app re-registers on its next sign-in.
        profile.device_token = None
        db.commit()
    return status == "ok"
