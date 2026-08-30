"""Remove the throwaway identities created by the I-03 runtime verification.

Deletes from Supabase Auth and Postgres, plus any OTP rows and reset tokens the
walkthrough left behind, then reports what remains so the result is checkable
rather than assumed.

    python -m scripts.verify_i03_cleanup
"""
from __future__ import annotations

import json
import os
import sys

from sqlalchemy import text
from supabase import create_client

from app.config import get_settings
from app.database import SessionLocal

STATE_FILES = ("scratch/.i03_subjects.json", "scratch/.i03_reset.json")
PREFIXES = ("i03-gate-", "i03-brute-", "i03-exploit-")

settings = get_settings()


def main() -> int:
    admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    known: set[str] = set()
    for path in STATE_FILES:
        if os.path.exists(path):
            with open(path) as fh:
                data = json.load(fh)
            known.update(v for k, v in data.items() if "@" in str(v))

    print("=" * 74)
    print("cleanup")
    print("=" * 74)
    print("from the walkthrough's state files:", ", ".join(sorted(known)) or "none")

    # Supabase Auth. Match on prefix rather than only the recorded addresses so a
    # crashed run cannot strand an identity nobody is tracking.
    print("\n-- Supabase Auth --")
    removed_auth = 0
    try:
        page = 1
        targets = []
        while True:
            res = admin.auth.admin.list_users(page=page, per_page=200)
            users = getattr(res, "users", res)
            if not users:
                break
            for u in users:
                if u.email and (u.email in known
                                or u.email.startswith(PREFIXES)):
                    targets.append((u.id, u.email))
            if len(users) < 200:
                break
            page += 1

        for uid, email in targets:
            admin.auth.admin.delete_user(uid)
            removed_auth += 1
            print(f"  deleted {email}")
        if not targets:
            print("  nothing to delete")
    except Exception as e:
        print(f"  ERROR listing/deleting: {e}")
        return 1

    # Postgres. FKs onto users are ON DELETE CASCADE, so removing the user row
    # takes its profile, portfolios, chats and risk profile with it. otp_codes
    # and password_reset_tokens key on email, not user_id, so they need their own
    # delete.
    print("\n-- Postgres --")
    db = SessionLocal()
    try:
        like = " OR ".join(f"email LIKE '{p}%'" for p in PREFIXES)
        params = {"emails": list(known) or [""]}

        for table in ("otp_codes", "password_reset_tokens", "users"):
            n = db.execute(text(
                f"DELETE FROM {table} WHERE email = ANY(:emails) OR {like}"),
                params).rowcount
            print(f"  {table}: {n} row(s) deleted")
        db.commit()

        print("\n-- remaining state --")
        for table in ("users", "user_profiles", "risk_profiles", "portfolios",
                      "otp_codes", "password_reset_tokens", "market_data",
                      "news_sentiment"):
            n = db.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            print(f"  {table:<24} {n}")

        leftover = db.execute(text(
            f"SELECT email FROM users WHERE {like}")).fetchall()
        print(f"\n  throwaway users left in Postgres: {len(leftover)}")
    finally:
        db.close()

    for path in STATE_FILES:
        if os.path.exists(path):
            os.remove(path)
            print(f"  removed {path}")

    print(f"\ndeleted {removed_auth} Supabase identity/identities")
    return 0


if __name__ == "__main__":
    sys.exit(main())
