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
    push_title: str | None = None,
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
                _dispatch_push(db, user_id, push_title or notif_type, message)
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


# ── Market open / close notices ──────────────────────────────────────────────
# Sent at the start and end of each CSE session (celery beat, Mon-Fri), in the
# user's language, as an in-app notification plus a push where a device token
# exists. Holidays send nothing: "open" needs cse.lk to report the market open,
# "close" needs a trading day recorded today.

MARKET_TITLES = {
    "market_open": {"en": "Market open", "si": "වෙළඳපොළ විවෘතයි", "ta": "சந்தை திறந்துள்ளது"},
    "market_close": {"en": "Market closed", "si": "වෙළඳපොළ වසා ඇත", "ta": "சந்தை மூடப்பட்டது"},
}
MARKET_MESSAGES = {
    "market_open": {
        "en": "The Colombo Stock Exchange is open. Trading runs until 2:30 PM.",
        "si": "කොළඹ කොටස් හුවමාරුව විවෘතයි. ගනුදෙනු ප.ව. 2:30 දක්වා.",
        "ta": "கொழும்பு பங்குச் சந்தை திறந்துள்ளது. வர்த்தகம் பிற்பகல் 2:30 வரை.",
    },
    "market_close": {
        "en": "The market has closed for today. ASPI {value} ({change}).",
        "si": "අද වෙළඳපොළ වසා ඇත. ASPI {value} ({change}).",
        "ta": "இன்றைய சந்தை மூடப்பட்டது. ASPI {value} ({change}).",
    },
}
MARKET_CLOSE_NO_INDEX = {
    "en": "The market has closed for today.",
    "si": "අද වෙළඳපොළ වසා ඇත.",
    "ta": "இன்றைய சந்தை மூடப்பட்டது.",
}


def market_message(event: str, lang: str, aspi=None) -> str:
    """The notice text for one user. `aspi` is a MarketIndexLatest row or None."""
    lang = lang if lang in ("en", "si", "ta") else "en"
    if event == "market_close":
        if aspi is None or aspi.value is None:
            return MARKET_CLOSE_NO_INDEX[lang]
        pct = aspi.change_pct or 0.0
        change = f"{'+' if pct >= 0 else ''}{pct:.2f}%"
        return MARKET_MESSAGES[event][lang].format(value=f"{aspi.value:,.2f}", change=change)
    return MARKET_MESSAGES[event][lang]


def notify_market_session(db: Session, event: str, status: str | None, now=None) -> int:
    """Send today's market-open or market-close notice to every user, once.

    Returns how many users were notified (0 on a holiday, or if already sent).
    """
    from datetime import datetime, time, timezone

    from app.models.stock import DailyClose, MarketIndexLatest
    from app.models.user import User, UserProfile
    from app.services.portfolio_history import EXCHANGE_TZ, exchange_today

    today = exchange_today(now)
    if event == "market_open":
        if "open" not in (status or "").lower():
            return 0
    elif event == "market_close":
        if not db.query(DailyClose).filter(DailyClose.trade_date == today).first():
            return 0
    else:
        raise ValueError(event)

    start = datetime.combine(today, time.min, EXCHANGE_TZ).astimezone(timezone.utc)
    if db.query(Notification).filter(Notification.type == event,
                                     Notification.timestamp >= start).first():
        return 0  # a retried or doubled beat tick must not send twice

    aspi = db.query(MarketIndexLatest).filter(MarketIndexLatest.index_code == "ASPI").first()
    sent = 0
    for user_id, lang in (db.query(User.user_id, UserProfile.language)
                          .outerjoin(UserProfile, UserProfile.user_id == User.user_id).all()):
        lang = lang if lang in ("en", "si", "ta") else "en"
        add_notification(db, user_id, market_message(event, lang, aspi), event,
                         send_push_alert=True, push_title=MARKET_TITLES[event][lang])
        sent += 1
    return sent
