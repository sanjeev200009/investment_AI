import httpx
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def _send(to_email: str, subject: str, html: str) -> bool:
    """Core send function via Brevo HTTP API."""
    if not settings.BREVO_API_KEY:
        logger.warning('BREVO_API_KEY not set — skipping email')
        return False
    
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {
            "name": settings.BREVO_FROM_NAME,
            "email": settings.BREVO_FROM_EMAIL
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html
    }

    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
        logger.info('Email sent successfully to %s: %s', to_email, subject)
        return True
    except httpx.HTTPStatusError as e:
        logger.error('Brevo API error (%s): %s', e.response.status_code, e.response.text)
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
            <p style="color:#666;font-size:13px">
                This code expires in <b>10 minutes</b>.<br>
                If you did not register, ignore this email.
            </p>
        </div>
    </body></html>'''
    return _send(to_email, 'InvestAI — Verify your account', html)

def send_reset_otp(to_email: str, otp: str) -> bool:
    """Send 6-digit OTP for password reset."""
    html = f'''
    <html><body style="font-family:Arial,sans-serif;max-width:580px;margin:auto">
        <div style="background:#EB5757;padding:28px;text-align:center">
            <h1 style="color:white;margin:0;font-size:24px">Reset Your Password</h1>
        </div>
        <div style="padding:32px;background:#f9f9f9">
            <p>You requested a password reset for your InvestAI account.</p>
            <p>Enter this OTP code on the reset screen:</p>
            <div style="text-align:center;margin:28px 0">
                <span style="font-size:44px;font-weight:bold;letter-spacing:12px;
                color:#EB5757;background:#FDEDEC;padding:16px 28px;
                border-radius:10px">{otp}</span>
            </div>
            <p style="color:#666;font-size:13px">
                Expires in <b>10 minutes</b>.<br>
                If you did not request this, ignore this email.
            </p>
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
            <p>You can now log in and start exploring CSE stocks.</p>
        </div>
    </body></html>'''
    return _send(to_email, 'Welcome to InvestAI!', html)
