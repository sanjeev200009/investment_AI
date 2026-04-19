# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from supabase import create_client

from app.dependencies import get_db, get_current_user
from app.models import User
from app.schemas.auth import (RegisterRequest, LoginRequest,
                              TokenResponse, UserOut, OTPVerifyRequest,
                              ForgotPasswordRequest, ResetPasswordRequest, VerifyResetOTPRequest)
from app.config import get_settings
from app.services.email import (send_registration_otp,
                                send_welcome_email, send_reset_otp)
from app.services.otp import create_otp, verify_otp
from app.utils.security import create_reset_token, verify_reset_token
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix='/auth', tags=['Authentication'])

def get_supabase():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

@router.post('/register', status_code=201)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Step 1 of 2: Register the user.
    Account created but NOT usable until OTP verified.
    Sends 6-digit OTP to email.
    """
    # Check if email already registered and verified
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing and existing.is_email_verified:
        raise HTTPException(400, 'Email already registered and verified')

    # Use admin client to bypass Supabase's default confirmation email
    # because we handle OTP verification internally via Brevo
    admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    try:
        admin_client.auth.admin.create_user({
            'email': payload.email,
            'password': payload.password,
            'email_confirm': True,
            'user_metadata': {'full_name': payload.full_name}
        })
    except Exception as e:
        if 'already' not in str(e).lower():
            raise HTTPException(400, f'Registration error: {str(e)}')

    # Update full_name (trigger already created public.users row)
    user = db.query(User).filter(User.email == payload.email).first()
    if user and payload.full_name:
        user.full_name = payload.full_name
        db.commit()

    # Generate and send OTP
    otp = create_otp(db, payload.email, purpose='register')
    background_tasks.add_task(
        send_registration_otp, payload.email, otp, payload.full_name)

    return {
        'message': 'Registration successful. Check your email for the OTP code.',
        'email': payload.email,
        'next_step': 'POST /auth/verify-otp with your 6-digit code',
    }

@router.post('/verify-otp')
async def verify_registration_otp(
    payload: OTPVerifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Step 2 of 2: Verify the OTP sent after registration.
    Marks user as verified — they can now log in.
    """
    ok = verify_otp(db, payload.email, payload.otp_code, purpose='register')
    if not ok:
        raise HTTPException(400, 'Invalid or expired OTP. Request a new one.')

    # Mark user as verified
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(404, 'User not found')

    user.is_email_verified = True
    db.commit()

    # Send welcome email
    background_tasks.add_task(
        send_welcome_email, payload.email, user.full_name or 'Investor')

    return {'message': 'Email verified! You can now log in.'}

@router.post('/resend-otp')
async def resend_otp(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Resend registration OTP if user did not receive it."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(404, 'Email not registered')
    if user.is_email_verified:
        raise HTTPException(400, 'Email already verified')

    otp = create_otp(db, payload.email, purpose='register')
    background_tasks.add_task(
        send_registration_otp, payload.email, otp, user.full_name or '')

    return {'message': 'New OTP sent to your email'}

@router.post('/login', response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Login. Blocked if email not verified.
    Returns Supabase JWT for local verification by other endpoints.
    """
    # Check verification BEFORE calling Supabase
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(401, 'Invalid email or password')
    if not user.is_email_verified:
        raise HTTPException(403, 'Email not verified. Check your email for the OTP code.')

    supabase = get_supabase()
    try:
        auth_response = supabase.auth.sign_in_with_password({
            'email': payload.email,
            'password': payload.password,
        })
    except Exception:
        raise HTTPException(401, 'Invalid email or password')

    if not auth_response.session:
        raise HTTPException(401, 'Authentication failed')

    return TokenResponse(
        access_token=auth_response.session.access_token,
        token_type='bearer',
        user_id=str(auth_response.user.id),
        email=auth_response.user.email,
    )

@router.post('/forgot-password')
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Step 1: User enters their email.
    Sends 6-digit OTP to that email for password reset.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    # Always return success — never reveal if email exists
    if user:
        otp = create_otp(db, payload.email, purpose='reset_password')
        background_tasks.add_task(send_reset_otp, payload.email, otp)
    
    return {
        'message': 'If that email exists, an OTP has been sent.',
        'next_step': 'POST /auth/verify-reset-otp with your 6-digit code',
    }

@router.post('/verify-reset-otp')
async def verify_reset_otp_endpoint(
    payload: VerifyResetOTPRequest,
    db: Session = Depends(get_db),
):
    """
    Step 2: User enters the OTP from their email.
    Returns a reset_token needed for the final step.
    """
    ok = verify_otp(db, payload.email, payload.otp_code, purpose='reset_password')
    if not ok:
        raise HTTPException(400, 'Invalid or expired OTP. Request a new one.')

    reset_token = create_reset_token(payload.email)
    
    return {
        'message': 'OTP verified.',
        'reset_token': reset_token,
        'next_step': 'POST /auth/reset-password with new_password + reset_token',
    }

@router.post('/reset-password')
async def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Step 3: User submits new password + reset_token.
    Updates password in Supabase Auth.
    """
    # Verify the reset token
    email = verify_reset_token(payload.reset_token)
    if not email or email != payload.email:
        raise HTTPException(400, 'Invalid or expired reset token')

    # Use Supabase Admin to update the password
    admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, 'User not found')

    try:
        admin.auth.admin.update_user_by_id(
            str(user.user_id),
            {'password': payload.new_password}
        )
    except Exception as e:
        raise HTTPException(500, f'Password update failed: {str(e)}')

    return {'message': 'Password reset successfully. You can now log in.'}

@router.get('/me', response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post('/logout')
def logout():
    return {'message': 'Logged out — delete token from AsyncStorage'}
