# app/services/email_service.py
import requests
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

def _send(to_email: str, subject: str, html: str) -> bool:
    """Core send function via Brevo HTTP API (Synchronous for stability)."""
    if not settings.BREVO_API_KEY:
        logger.warning('BREVO_API_KEY not set — skipping email')
        return False
        
    # Extract plain text OTP for accessibility
    plain_otp = "Check app"
    if 'radius:10px">' in html:
        try:
            plain_otp = html.split('radius:10px">')[1].split('</span>')[0]
        except Exception:
            pass

    payload = {
        "sender": {"name": settings.BREVO_FROM_NAME, "email": settings.BREVO_FROM_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html,
        "textContent": f"Your InvestAI OTP code is: {plain_otp}"
    }
    
    headers = {
        "api-key": settings.BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=15.0)
        if response.status_code in (200, 201, 202):
            logger.info('Email sent successfully to %s', to_email)
            return True
        else:
            logger.error('Brevo API error (%s): %s', response.status_code, response.text)
            return False
    except Exception as e:
        logger.error('Email error: %s', str(e))
        return False

def send_registration_otp(to_email: str, otp: str, name: str) -> bool:
    """Send 6-digit OTP after registration."""
    html = f'''
    <html><body style="font-family:Arial,sans-serif;max-width:580px;margin:auto">
    <div style="background:#2F80ED;padding:28px;text-align:center">
    <h1 style="color:white;margin:0;font-size:24px">Verify Your Account</h1>
    </div>
    <div style="padding:32px;background:#f9f9f9">
    <p style="font-size:16px">Hi <b>{name}</b>,</p>
    <p>Thank you for registering with InvestAI.</p>
    <p>Enter this OTP code in the app to verify your account:</p>
    <div style="text-align:center;margin:28px 0">
    <span style="font-size:44px;font-weight:bold;letter-spacing:12px;
    color:#2F80ED;background:#EBF5FB;padding:16px 28px;
    border-radius:10px">{otp}</span>
    </div>
    </div>
    </body></html>'''
    return _send(to_email, 'InvestAI — Account Verification', html)

def send_reset_otp(to_email: str, otp: str) -> bool:
    """Send 6-digit OTP for password reset."""
    html = f'''
    <html><body style="font-family:Arial,sans-serif;max-width:580px;margin:auto">
    <div style="background:#EB5757;padding:28px;text-align:center">
    <h1 style="color:white;margin:0;font-size:24px">Reset Your Password</h1>
    </div>
    <div style="padding:32px;background:#f9f9f9">
    <p>Enter this OTP code on the reset screen:</p>
    <div style="text-align:center;margin:28px 0">
    <span style="font-size:44px;font-weight:bold;letter-spacing:12px;
    color:#EB5757;background:#FDEDEC;padding:16px 28px;
    border-radius:10px">{otp}</span>
    </div>
    </div>
    </body></html>'''
    return _send(to_email, 'InvestAI — Password Reset OTP', html)

def send_welcome_email(to_email: str, name: str) -> bool:
    """Send welcome email after OTP verified."""
    html = f'''
    <html><body style="font-family:Arial,sans-serif;max-width:580px;margin:auto">
    <div style="background:#27AE60;padding:28px;text-align:center">
    <h1 style="color:white;margin:0">Account Verified!</h1>
    </div>
    <div style="padding:32px;background:#f9f9f9">
    <p>Hi <b>{name}</b>, your InvestAI account is now active.</p>
    </div>
    </body></html>'''
    return _send(to_email, 'Welcome to InvestAI!', html)
