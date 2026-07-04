# app/routers/notifications.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db, get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import add_notification
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix='/notifications', tags=['Notifications'])

class NotificationOut(BaseModel):
    notif_id: int
    message: str
    is_read: bool
    timestamp: datetime
    
    class Config:
        from_attributes = True

@router.get('/', response_model=List[NotificationOut])
def get_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Show the list of notifications."""
    return db.query(Notification).filter(Notification.user_id == user.user_id).order_by(Notification.timestamp.desc()).all()

@router.post('/test')
def test_notification(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """ONE ENDPOINT: Create a test notification to show it's working."""
    return add_notification(
        db=db,
        user_id=user.user_id,
        message="✅ System Check: Your Notification System is working properly!",
        notif_type="TEST",
        send_push_alert=False # Set to True to test Firebase
    )
