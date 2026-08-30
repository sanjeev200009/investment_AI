"""I-03 runtime verification, phase 2: reset tokens survive a process restart.

Run in three stages around a real uvicorn restart, because that restart is the
exact thing the old process-local dict could not survive:

    python -m scripts.verify_i03_phase2 mint      # request a reset, get a token
    <restart uvicorn>
    python -m scripts.verify_i03_phase2 redeem    # spend it on the new process
    python -m scripts.verify_i03_phase2 expiry    # and the expiry path

State is passed between stages through scratch/.i03_reset.json, not through
memory — the point is that nothing in this flow depends on process state.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import text
from supabase import create_client

from app.config import get_settings
from app.database import SessionLocal
from app.utils.security import _hash_token

API = "http://127.0.0.1:8011/api/v1"
SUBJECTS = "scratch/.i03_subjects.json"
STATE = "scratch/.i03_reset.json"

settings = get_settings()
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, extra: str = "") -> bool:
    results.append((ok, label))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {extra}" if extra else ""))
    return ok


def summary(stage: str) -> int:
    failed = [l for ok, l in results if not ok]
    print(f"\n{stage}: {len(results) - len(failed)}/{len(results)} passed")
    for l in failed:
        print(f"  FAILED: {l}")
    return 1 if failed else 0


def subjects() -> dict:
    with open(SUBJECTS) as fh:
        return json.load(fh)


def otp_for(email: str, purpose: str):
    db = SessionLocal()
    try:
        return db.execute(text(
            "SELECT otp_code FROM otp_codes WHERE email=:e AND purpose=:p "
            "AND is_used=false ORDER BY created_at DESC LIMIT 1"),
            {"e": email, "p": purpose}).scalar()
    finally:
        db.close()


def anon_signin(email: str, password: str) -> tuple[bool, str]:
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    try:
        r = client.auth.sign_in_with_password(
            {"email": email, "password": password})
        return bool(r and r.session), "session issued"
    except Exception as e:
        return False, type(e).__name__ + ": " + str(e)[:80]


def mint() -> int:
    s = subjects()
    email = s["gate"]
    print("=" * 74)
    print("H-3  mint a reset token (this process will then be killed)")
    print("=" * 74)
    print(f"subject: {email}")

    r = requests.post(f"{API}/auth/forgot-password", json={"email": email},
                      timeout=45)
    check(r.status_code == 200, "forgot-password -> 200", f"({r.status_code})")

    code = otp_for(email, "reset_password")
    check(code is not None, "a reset OTP was stored", "(value withheld)")

    r = requests.post(f"{API}/auth/verify-reset-otp",
                      json={"email": email, "otp_code": code}, timeout=30)
    if not check(r.status_code == 200, "verify-reset-otp -> 200",
                 f"({r.status_code})"):
        print(r.text[:300])
        return 1

    token = r.json()["reset_token"]
    check(bool(token), "a reset_token was returned")

    db = SessionLocal()
    try:
        row = db.execute(text(
            "SELECT token_hash, email, expires_at FROM password_reset_tokens "
            "WHERE email=:e"), {"e": email}).first()
        check(row is not None, "the token is persisted in Postgres, not in RAM")
        if row:
            check(row[0] == _hash_token(token),
                  "only the SHA-256 hash is stored", f"len={len(row[0])}")
            check(token not in row[0], "the raw token is NOT in the database")
            life = row[2] - datetime.now(timezone.utc)
            check(timedelta(minutes=9) < life <= timedelta(minutes=10),
                  "expires in ~10 minutes", f"{life}")
    finally:
        db.close()

    with open(STATE, "w") as fh:
        json.dump({"email": email, "token": token}, fh)
    print(f"\n  token saved to {STATE}; now restart uvicorn and run 'redeem'")
    return summary("mint")


def redeem() -> int:
    with open(STATE) as fh:
        st = json.load(fh)
    s = subjects()
    email, token = st["email"], st["token"]

    print("=" * 74)
    print("H-3  redeem it on a DIFFERENT process")
    print("=" * 74)
    print("The old implementation kept reset tokens in a module-level dict in")
    print("app/utils/security.py. On a fresh process that dict is empty, so this")
    print("request returned 400 'Invalid or expired reset token' -- and with more")
    print("than one uvicorn worker it failed whenever the request landed on a")
    print("sibling that had not minted the token.\n")

    r = requests.post(f"{API}/auth/reset-password", json={
        "email": email, "reset_token": token,
        "new_password": s["new_password"]}, timeout=45)
    if not check(r.status_code == 200,
                 "reset-password after restart -> 200", f"({r.status_code})"):
        print(r.text[:300])

    ok, why = anon_signin(email, s["new_password"])
    check(ok, "Supabase accepts the NEW password", why)
    ok, why = anon_signin(email, s["password"])
    check(not ok, "Supabase refuses the OLD password", why)

    r = requests.post(f"{API}/auth/login",
                      json={"email": email, "password": s["new_password"]},
                      timeout=30)
    check(r.status_code == 200, "/auth/login with the new password -> 200",
          f"({r.status_code})")

    print("\n-- single use --")
    r = requests.post(f"{API}/auth/reset-password", json={
        "email": email, "reset_token": token,
        "new_password": "Another#Pass789"}, timeout=30)
    check(r.status_code == 400, "replaying the same token -> 400",
          f"({r.status_code})")

    db = SessionLocal()
    try:
        left = db.execute(text(
            "SELECT count(*) FROM password_reset_tokens WHERE email=:e"),
            {"e": email}).scalar()
        check(left == 0, "the spent token was deleted", f"rows={left}")
    finally:
        db.close()
    return summary("redeem")


def expiry() -> int:
    s = subjects()
    email = s["gate"]
    print("=" * 74)
    print("H-3  expiry")
    print("=" * 74)

    r = requests.post(f"{API}/auth/forgot-password", json={"email": email},
                      timeout=45)
    code = otp_for(email, "reset_password")
    r = requests.post(f"{API}/auth/verify-reset-otp",
                      json={"email": email, "otp_code": code}, timeout=30)
    if not check(r.status_code == 200, "minted a second reset token",
                 f"({r.status_code})"):
        return 1
    token = r.json()["reset_token"]

    print("\n-- superseding --")
    r2 = requests.post(f"{API}/auth/forgot-password", json={"email": email},
                       timeout=45)
    code2 = otp_for(email, "reset_password")
    r2 = requests.post(f"{API}/auth/verify-reset-otp",
                       json={"email": email, "otp_code": code2}, timeout=30)
    newer = r2.json()["reset_token"]
    check(newer != token, "a second request issued a different token")

    r = requests.post(f"{API}/auth/reset-password", json={
        "email": email, "reset_token": token,
        "new_password": "Nope#Pass000"}, timeout=30)
    check(r.status_code == 400, "the superseded token is refused",
          f"({r.status_code})")

    print("\n-- age out --")
    # Backdated rather than waiting 10 real minutes. This drives exactly the
    # same predicate -- verify_reset_token filters on `expires_at > now()` in
    # SQL -- so the stored expiry is the only variable being changed.
    db = SessionLocal()
    try:
        n = db.execute(text(
            "UPDATE password_reset_tokens SET expires_at = :past "
            "WHERE token_hash = :h"),
            {"past": datetime.now(timezone.utc) - timedelta(minutes=1),
             "h": _hash_token(newer)}).rowcount
        db.commit()
        check(n == 1, "backdated the live token's expires_at past now()")
    finally:
        db.close()

    r = requests.post(f"{API}/auth/reset-password", json={
        "email": email, "reset_token": newer,
        "new_password": "Nope#Pass111"}, timeout=30)
    check(r.status_code == 400, "an expired token is refused",
          f"({r.status_code})")

    ok, _ = anon_signin(email, s["new_password"])
    check(ok, "the password was NOT changed by either refused attempt")

    print("\n-- a token cannot be used against another account --")
    other = s["brute"]
    requests.post(f"{API}/auth/forgot-password", json={"email": other},
                  timeout=45)
    c = otp_for(other, "reset_password")
    rr = requests.post(f"{API}/auth/verify-reset-otp",
                       json={"email": other, "otp_code": c}, timeout=30)
    others_token = rr.json()["reset_token"]
    r = requests.post(f"{API}/auth/reset-password", json={
        "email": email, "reset_token": others_token,
        "new_password": "Nope#Pass222"}, timeout=30)
    check(r.status_code == 400,
          "a token minted for another address cannot reset this one",
          f"({r.status_code})")

    print("\n-- unknown token --")
    r = requests.post(f"{API}/auth/reset-password", json={
        "email": email, "reset_token": "a-token-nobody-ever-issued",
        "new_password": "Nope#Pass333"}, timeout=30)
    check(r.status_code == 400, "an invented token is refused",
          f"({r.status_code})")

    return summary("expiry")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"mint": mint, "redeem": redeem, "expiry": expiry}.get(stage)
    if not fn:
        print(__doc__)
        sys.exit(2)
    sys.exit(fn())
