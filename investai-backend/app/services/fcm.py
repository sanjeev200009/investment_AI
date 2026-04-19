# app/services/fcm.py
import logging
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_fcm_app = None

def _get_fcm_app():
    global _fcm_app
    if _fcm_app is None:
        try:
            import firebase_admin
            from firebase_admin import credentials
            cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
            if not cred_path:
                logger.warning('FIREBASE_CREDENTIALS_PATH not set')
                return None
            cred = credentials.Certificate(cred_path)
            _fcm_app = firebase_admin.initialize_app(cred)
        except Exception as e:
            logger.error('FCM init failed: %s', e)
            return None
    return _fcm_app

def send_push(device_token: str, title: str, body: str, data: dict = None) -> bool:
    """Send a single push notification to a device token."""
    app = _get_fcm_app()
    if not app:
        logger.warning('FCM not available — skipping push')
        return False
    try:
        from firebase_admin import messaging
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=device_token,
        )
        messaging.send(msg)
        return True
    except Exception as e:
        logger.error('FCM send failed: %s', e)
        return False
