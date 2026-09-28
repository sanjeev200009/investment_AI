# app/routers/notifications.py
"""User notifications: list, mark read, delete — and a test push.

Before I-11 the mobile screen rendered a hardcoded DUMMY_ALERTS array about
TSLA/AAPL/MSFT/NVDA while this working endpoint was never called. The list and
test endpoints predate the batch; mark-read and delete were added with it so
the screen can actually manage what it shows instead of a read-only feed.
"""

from __future__ import annotations

import os

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import add_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/notifications', tags=['Notifications'])


class NotificationOut(BaseModel):
    notif_id: int
    type: str
    message: str
    is_read: bool
    timestamp: datetime

    class Config:
        from_attributes = True


@router.get('/', response_model=List[NotificationOut])
def get_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The signed-in user's notifications, newest first."""
    return (db.query(Notification)
            .filter(Notification.user_id == user.user_id)
            .order_by(Notification.timestamp.desc())
            .limit(100)
            .all())


@router.patch('/{notif_id}/read', response_model=NotificationOut)
def mark_read(
    notif_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark one notification read. Scoped by user — a guessed id cannot flip
    someone else's row."""
    notif = (db.query(Notification)
             .filter(Notification.notif_id == notif_id,
                     Notification.user_id == user.user_id)
             .first())
    if not notif:
        raise HTTPException(404, 'Notification not found')
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.post('/read-all')
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Mark every unread notification read; returns how many changed."""
    count = (db.query(Notification)
             .filter(Notification.user_id == user.user_id,
                     Notification.is_read == False)  # noqa: E712
             .update({Notification.is_read: True}, synchronize_session=False))
    db.commit()
    return {'marked_read': count or 0}


@router.delete('/{notif_id}', status_code=204)
def delete_notification(
    notif_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete one notification. 204 whether or not it existed, so a stale
    screen cannot error on a row already gone."""
    (db.query(Notification)
     .filter(Notification.notif_id == notif_id,
             Notification.user_id == user.user_id)
     .delete(synchronize_session=False))
    db.commit()
    return None


@router.post('/test')
def test_notification(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Create a test notification, and exercise the push path while at it.

    `send_push_alert` was hardcoded False here because the push path referenced
    a `user.fcm_token` column that does not exist — it would have raised
    AttributeError and rolled the notification back (H-2). The service now
    reads user_profiles.device_token like everywhere else, so True is safe.
    """
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise HTTPException(404, "Not found")
    return add_notification(
        db=db,
        user_id=user.user_id,
        message="✅ System Check: Your Notification System is working properly!",
        notif_type="TEST",
        send_push_alert=True,
    )
