# app/services/otp.py
import random
import string
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.otp import OTPCode

OTP_EXPIRY_MINUTES = 10

def generate_otp() -> str:
    """Generate a secure 6-digit OTP."""
    return ''.join(random.choices(string.digits, k=6))

def create_otp(db: Session, email: str, purpose: str) -> str:
    """
    Create a new OTP for email+purpose.
    Deletes any existing unused OTPs for same email+purpose first.
    purpose: 'register' or 'reset_password'
    """
    # Delete old OTPs for this email+purpose
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

def verify_otp(db: Session, email: str, otp_code: str, purpose: str) -> bool:
    """
    Verify OTP. Returns True if valid.
    Marks as used on success so it cannot be reused.
    """
    record = db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.otp_code == otp_code,
        OTPCode.purpose == purpose,
        OTPCode.is_used == False,
    ).first()

    if not record:
        return False  # OTP not found or already used

    # Check expiry
    now = datetime.now(timezone.utc)
    if record.expires_at < now:
        db.delete(record)
        db.commit()
        return False  # OTP expired

    # Mark as used
    record.is_used = True
    db.commit()
    
    return True
