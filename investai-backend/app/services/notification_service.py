import asyncio
import logging
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.services.fcm import send_push_to_user

logger = logging.getLogger(__name__)


def add_notification(
    db: Session,
    user_id: str,
    message: str,
    notif_type: str = "GENERAL",
    send_push_alert: bool = False,
):
    """Persist a notification, then fire the push best-effort.

    Push failures are logged and swallowed: the notification row is the
    durable record, and a transient FCM outage must not roll it back. The push
    is dispatched on the running loop when there is one (router context), or on
    a fresh one in a worker thread otherwise.
    """
    try:
        new_notif = Notification(
            user_id=user_id,
            message=message,
            type=notif_type,
            is_read=False,
        )
        db.add(new_notif)
        db.commit()
        db.refresh(new_notif)

        if send_push_alert:
            # Reads user_profiles.device_token via send_push_to_user. This used
            # to read `user.fcm_token`, a column that has never existed on the
            # User model — any call with send_push_alert=True raised
            # AttributeError and rolled back the notification it was meant to
            # accompany (H-2 / I-12; one of three incompatible device-token
            # conventions in the codebase before I-12 consolidated them).
            try:
                _dispatch_push(db, user_id, notif_type, message)
            except Exception as push_exc:  # noqa: BLE001
                logger.warning("Push for notification %s failed: %s",
                               new_notif.notif_id, push_exc)

        return new_notif

    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        db.rollback()
        raise e


def _dispatch_push(db: Session, user_id: str, title: str, body: str) -> None:
    """Run the async push from sync context without blocking the caller."""
    import threading

    from app.database import SessionLocal

    def _run() -> None:
        # A separate session: the request's session closes when the response
        # returns, which can beat the network round trip to FCM.
        push_db = SessionLocal()
        try:
            asyncio.run(send_push_to_user(
                db=push_db, user_id=user_id, title=title, body=body,
                data={"type": title},
            ))
        finally:
            push_db.close()

    threading.Thread(target=_run, daemon=True).start()
