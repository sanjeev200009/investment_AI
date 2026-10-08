"""Fix the data problems the 5 Oct 2026 database audit found.

    python scripts/db_cleanup.py            # dry run: shows what would change
    python scripts/db_cleanup.py --apply    # change it

1.  Stale quotes: market_data_latest rows with no exchange trade time that were
    last scraped over 30 days ago (AMF.N0000 and BRR.N0000, from the 5 Jul seed;
    neither is in cse.lk's trade summary). Removing the row hides them from the
    market list, search, the AI and recommendations. If they trade again the
    next scrape puts them straight back.
2.  Users with no user_profiles row get one, the same way device.py's
    _ensure_profile would on first use.
3.  Expired OTP codes and reset tokens are purged (the daily task does this from now on).
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models.stock import MarketDataLatest  # noqa: E402
from app.models.user import User, UserProfile  # noqa: E402
from app.services.otp import purge_expired_otps  # noqa: E402
from app.utils.security import purge_expired_reset_tokens  # noqa: E402
import app.models.chat, app.models.notification, app.models.portfolio  # noqa: E402,F401  (mappers)


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        stale = (db.query(MarketDataLatest)
                 .filter(MarketDataLatest.last_traded_at.is_(None),
                         MarketDataLatest.recorded_at < datetime.now(timezone.utc) - timedelta(days=30))
                 .all())
        print('Stale quotes:', [(q.symbol, q.price, q.recorded_at.date().isoformat()) for q in stale])
        no_profile = db.query(User).filter(~User.profile.has()).all()
        print('Users without a profile:', [str(u.user_id)[:8] for u in no_profile])
        if not apply:
            print('Dry run: nothing changed. Re-run with --apply.')
            return
        for q in stale:
            db.delete(q)
        for u in no_profile:
            db.add(UserProfile(user_id=u.user_id, full_name=u.full_name or u.email.split('@')[0]))
        db.commit()
        print('Purged', purge_expired_otps(db), 'OTP codes and', purge_expired_reset_tokens(db), 'reset tokens')
        print('Done.')
    finally:
        db.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--apply', action='store_true', help='make the changes (default: dry run)')
    main(ap.parse_args().apply)
