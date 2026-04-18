# app/services/email.py
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def _send(to_email: str, subject: str, html: str) -> bool:
    """Core send function via Brevo SMTP."""
    if not settings.BREVO_SMTP_PASSWORD:
        logger.warning('BREVO_SMTP_PASSWORD not set — skipping email')
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'{settings.BREVO_FROM_NAME} <{settings.BREVO_FROM_EMAIL}>'
        msg['To'] = to_email
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        with smtplib.SMTP(settings.BREVO_SMTP_HOST, settings.BREVO_SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(settings.BREVO_SMTP_USER, settings.BREVO_SMTP_PASSWORD)
            s.sendmail(settings.BREVO_FROM_EMAIL, [to_email], msg.as_string())
            
        logger.info('Email sent to %s: %s', to_email, subject)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error('Brevo auth failed — check BREVO_SMTP_USER + PASSWORD')
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
