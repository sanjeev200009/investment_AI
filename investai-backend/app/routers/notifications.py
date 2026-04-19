# app/routers/notifications.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db, get_current_user
from app.models.notification import Notification
from app.models.user import User
from pydantic import BaseModel
from datetime import datetime

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
def get_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all notifications for the current user (unread first)."""
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.user_id)
        .order_by(Notification.is_read.asc(), Notification.timestamp.desc())
        .all()
    )

@router.post('/{notif_id}/read', response_model=NotificationOut)
def mark_as_read(
    notif_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.notif_id == notif_id,
        Notification.user_id == user.user_id,
    ).first()
    if not n:
        raise HTTPException(404, 'Notification not found')
    
    n.is_read = True
    db.commit()
    db.refresh(n)
    return n

@router.post('/read-all')
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == user.user_id,
        Notification.is_read == False
    ).update({'is_read': True})
    db.commit()
    return {'message': 'All notifications marked as read'}
