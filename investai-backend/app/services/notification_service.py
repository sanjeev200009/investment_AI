import logging
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.user import User
from app.services.fcm import send_push

logger = logging.getLogger(__name__)

def add_notification(
    db: Session, 
    user_id: str, 
    message: str, 
    notif_type: str = "GENERAL", 
    send_push_alert: bool = False
):
    try:
        new_notif = Notification(
            user_id=user_id,
            message=message,
            type=notif_type,
            is_read=False
        )
        db.add(new_notif)
        db.commit()
        db.refresh(new_notif)
        
    
        if send_push_alert:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user and user.fcm_token:
                logger.info(f"Sending push alert to user: {user_id}")
                send_push(
                    device_token=user.fcm_token,
                    title=notif_type,
                    body=message
                )
            else:
                logger.debug(f"Skipping push alert for user {user_id}: No FCM token registered.")
                
        return new_notif
        
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        db.rollback()
        raise e
