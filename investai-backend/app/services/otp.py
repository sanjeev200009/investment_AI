# app/services/otp.py
"""One-time codes for registration and password reset.

Three properties this module is responsible for, none of which held before:

*   **Unpredictable codes.** Generation used ``random.choices``, i.e. the Mersenne
    Twister, which is not a cryptographic PRNG — its internal state is
    recoverable from observed output, so codes were guessable in principle.
    ``secrets`` is the correct source for anything used as a credential.
*   **A bounded number of guesses.** A six-digit code is 10^6 possibilities.
    Unlimited attempts made it a speed bump, not a gate. That was tolerable
    while email confirmation was enforced by Supabase independently; it is not
    now that ``/auth/verify-otp`` is the only thing standing between
    registration and a confirmed account.
*   **Constant-time comparison.** ``==`` on the code leaks a prefix-match timing
    signal. ``secrets.compare_digest`` does not.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.otp import OTPCode

OTP_EXPIRY_MINUTES = 10

# Wrong guesses allowed before the code is destroyed and a new one must be
# requested. Five is enough to absorb typos and far short of useful for a
# brute-force search.
MAX_OTP_ATTEMPTS = 5


def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def _as_utc(value: datetime) -> datetime:
    """Treat a naive datetime as UTC.

    ``otp_codes.expires_at`` is ``TIMESTAMPTZ``, so Postgres hands back an aware
    value and this is a no-op in production. It matters because comparing a naive
    datetime to an aware one raises ``TypeError`` rather than returning False —
    so if a driver or a drifted column ever yielded a naive value, expiry
    checking would become a 500 on every verification attempt instead of
    degrading. UTC is the right assumption: every value written here comes from
    ``datetime.now(timezone.utc)``.
    """
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def create_otp(db: Session, email: str, purpose: str) -> str:
    """
    Create a new OTP for email+purpose.
    Deletes any existing unused OTPs for same email+purpose first.
    purpose: 'register' or 'reset_password'
    """
    # Delete old OTPs for this email+purpose. This is also what guarantees at
    # most one live code per (email, purpose), which `verify_otp` relies on when
    # it looks the record up without knowing the code.
    db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.purpose == purpose,
        OTPCode.is_used == False
    ).delete()
    db.commit()

    otp = generate_otp()
    expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    record = OTPCode(
        email=email,
        otp_code=otp,
        purpose=purpose,
        expires_at=expires,
    )
    db.add(record)
    db.commit()

    return otp


def verify_otp(db: Session, email: str, otp_code: str, purpose: str,
               consume: bool = True) -> bool:
    """Verify an OTP. Returns True if it is valid.

    The record is located by ``email`` + ``purpose`` rather than by the submitted
    code, which is what makes per-code attempt counting possible: a wrong guess
    matches no record, so a lookup keyed on the code has nothing to increment.

    ``consume=False`` checks validity without spending the code. It exists so a
    caller can confirm an external side effect *before* the code is burnt — see
    ``/auth/verify-otp``, which must confirm the Supabase identity first so that
    a failure there leaves the user able to retry with the same code rather than
    stranded with a spent one.
    """
    record = db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.purpose == purpose,
        OTPCode.is_used == False,
    ).order_by(OTPCode.created_at.desc()).first()

    if not record:
        return False  # no live code for this email+purpose

    now = datetime.now(timezone.utc)
    if _as_utc(record.expires_at) < now:
        db.delete(record)
        db.commit()
        return False  # expired

    if (record.attempts or 0) >= MAX_OTP_ATTEMPTS:
        # Out of guesses. Destroy it so the only way forward is a fresh code.
        db.delete(record)
        db.commit()
        return False

    if not secrets.compare_digest(str(record.otp_code), str(otp_code)):
        record.attempts = (record.attempts or 0) + 1
        db.commit()
        return False

    if consume:
        record.is_used = True
        db.commit()

    return True
