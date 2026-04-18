# tasks/notification_tasks.py
from celery_worker import celery_app


@celery_app.task(bind=True, max_retries=3)
def send_push_notification(self, user_id: str, title: str, body: str, data: dict | None = None):
    """Send a Firebase Cloud Messaging push notification."""
    try:
        from app.services.fcm import FCMService
        fcm = FCMService()
        return fcm.send(user_id=user_id, title=title, body=body, data=data or {})
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
