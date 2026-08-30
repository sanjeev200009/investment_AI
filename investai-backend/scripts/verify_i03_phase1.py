"""I-03 runtime verification, phase 1: the OTP is a real gate.

Not a test file — a scripted walk through the live API and live Supabase project,
because the defect this closes is about what *Supabase* will accept, which no
mocked test can demonstrate.

    python -m scripts.verify_i03_phase1

Uses throwaway addresses and prints the state needed by phase 2. Cleanup is
scripts/verify_i03_cleanup.py.
"""
from __future__ import annotations

import json
import sys
import uuid

import requests
from sqlalchemy import text
from supabase import create_client

from app.config import get_settings
from app.database import SessionLocal

API = "http://127.0.0.1:8011/api/v1"
PASSWORD = "Throwaway#Pass123"
NEW_PASSWORD = "Rotated#Pass456"

settings = get_settings()
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, extra: str = "") -> bool:
    results.append((ok, label))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {extra}" if extra else ""))
    return ok


def otp_for(email: str, purpose: str) -> str | None:
    db = SessionLocal()
    try:
        return db.execute(text(
            "SELECT otp_code FROM otp_codes WHERE email=:e AND purpose=:p "
            "AND is_used=false ORDER BY created_at DESC LIMIT 1"),
            {"e": email, "p": purpose}).scalar()
    finally:
        db.close()


def attempts_for(email: str, purpose: str):
    db = SessionLocal()
    try:
        return db.execute(text(
            "SELECT attempts FROM otp_codes WHERE email=:e AND purpose=:p "
            "ORDER BY created_at DESC LIMIT 1"),
            {"e": email, "p": purpose}).scalar()
    finally:
        db.close()


def anon_signin(email: str, password: str) -> tuple[bool, str]:
    """Sign in against Supabase directly with the public anon key.

    This is the attack H-4 allowed: the anon key ships inside the mobile app, so
    anyone can make this call and skip our /auth/login entirely.
    """
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    try:
        r = client.auth.sign_in_with_password(
            {"email": email, "password": password})
        return bool(r and r.session), "session issued"
    except Exception as e:
        return False, type(e).__name__ + ": " + str(e)[:90]


def main() -> int:
    gate = f"i03-gate-{uuid.uuid4().hex[:8]}@example.com"
    brute = f"i03-brute-{uuid.uuid4().hex[:8]}@example.com"

    print("=" * 74)
    print("H-4  the OTP must gate Supabase itself, not just our own login")
    print("=" * 74)
    print(f"subject: {gate}")

    r = requests.post(f"{API}/auth/register", json={
        "email": gate, "password": PASSWORD, "full_name": "I03 Gate"},
        timeout=45)
    if not check(r.status_code == 201, "register -> 201", f"({r.status_code})"):
        print(r.text[:400])
        return 1

    print("\n-- before the OTP is entered --")
    ok, why = anon_signin(gate, PASSWORD)
    check(not ok, "direct Supabase sign-in with the ANON key is REFUSED", why)

    r = requests.post(f"{API}/auth/login",
                      json={"email": gate, "password": PASSWORD}, timeout=30)
    check(r.status_code == 403, "our /auth/login is refused too",
          f"({r.status_code})")

    code = otp_for(gate, "register")
    check(code is not None and len(code) == 6,
          "a 6-digit OTP was stored", "(value withheld)")
    check(attempts_for(gate, "register") == 0, "attempts starts at 0")

    print("\n-- enter the OTP --")
    r = requests.post(f"{API}/auth/verify-otp",
                      json={"email": gate, "otp_code": code}, timeout=45)
    if not check(r.status_code == 200, "verify-otp -> 200", f"({r.status_code})"):
        print(r.text[:400])

    print("\n-- after the OTP is entered --")
    ok, why = anon_signin(gate, PASSWORD)
    check(ok, "the SAME direct Supabase sign-in now SUCCEEDS", why)

    r = requests.post(f"{API}/auth/login",
                      json={"email": gate, "password": PASSWORD}, timeout=30)
    check(r.status_code == 200, "our /auth/login -> 200", f"({r.status_code})")
    token = r.json().get("access_token") if r.status_code == 200 else None

    if token:
        me = requests.get(f"{API}/auth/me",
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=30)
        check(me.status_code == 200 and me.json().get("is_email_verified") is True,
              "/auth/me reports is_email_verified=true")

    print("\n" + "=" * 74)
    print("H-4  a six-digit code must not accept unlimited guesses")
    print("=" * 74)
    print(f"subject: {brute}")

    r = requests.post(f"{API}/auth/register", json={
        "email": brute, "password": PASSWORD, "full_name": "I03 Brute"},
        timeout=45)
    check(r.status_code == 201, "register -> 201", f"({r.status_code})")

    real = otp_for(brute, "register")
    wrong = "000000" if real != "000000" else "111111"

    for i in range(1, 6):
        r = requests.post(f"{API}/auth/verify-otp",
                          json={"email": brute, "otp_code": wrong}, timeout=30)
        check(r.status_code == 400, f"wrong guess {i} -> 400",
              f"attempts={attempts_for(brute, 'register')}")

    r = requests.post(f"{API}/auth/verify-otp",
                      json={"email": brute, "otp_code": real}, timeout=30)
    check(r.status_code == 400,
          "the CORRECT code is refused after 5 wrong guesses",
          f"({r.status_code})")
    check(attempts_for(brute, "register") is None,
          "the code was destroyed, not just counted")

    ok, why = anon_signin(brute, PASSWORD)
    check(not ok, "the brute-forced account is still unusable in Supabase", why)

    print("\n-- a fresh code recovers the account --")
    r = requests.post(f"{API}/auth/resend-otp", json={"email": brute}, timeout=45)
    check(r.status_code == 200, "resend-otp -> 200", f"({r.status_code})")
    fresh = otp_for(brute, "register")
    check(fresh is not None and fresh != real, "a different code was issued")
    check(attempts_for(brute, "register") == 0, "attempt count reset to 0")
    r = requests.post(f"{API}/auth/verify-otp",
                      json={"email": brute, "otp_code": fresh}, timeout=45)
    check(r.status_code == 200, "verify-otp with the fresh code -> 200",
          f"({r.status_code})")

    with open("scratch/.i03_subjects.json", "w") as fh:
        json.dump({"gate": gate, "brute": brute, "password": PASSWORD,
                   "new_password": NEW_PASSWORD}, fh)

    failed = [l for ok_, l in results if not ok_]
    print("\n" + "=" * 74)
    print(f"phase 1: {len(results) - len(failed)}/{len(results)} passed")
    for l in failed:
        print(f"  FAILED: {l}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
