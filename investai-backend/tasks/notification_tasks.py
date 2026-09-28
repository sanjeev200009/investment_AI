# tasks/notification_tasks.py
import asyncio

from celery_worker import celery_app


@celery_app.task(bind=True, max_retries=3)
def send_push_notification(self, user_id: str, title: str, body: str, data: dict | None = None):
    """Send a push to every device registered for ``user_id``."""
    try:
        from app.database import SessionLocal
        from app.models.user import UserProfile
        from app.services.fcm import send_push

        db = SessionLocal()
        try:
            profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            token = getattr(profile, "device_token", None)
        finally:
            db.close()
        if not token:
            return False
        return asyncio.run(send_push(token, title, body, data or {}))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
