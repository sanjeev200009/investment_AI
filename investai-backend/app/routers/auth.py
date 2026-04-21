# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from supabase import create_client
from datetime import timedelta
import logging

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import (RegisterRequest, LoginRequest,
                               TokenResponse, UserOut, OTPVerifyRequest,
                               ForgotPasswordRequest, ResetPasswordRequest, VerifyResetOTPRequest)
from app.config import get_settings
from app.services.email_service import (send_registration_otp,
                                send_welcome_email, send_reset_otp)
from app.services.otp import create_otp, verify_otp
from app.utils.security import create_reset_token, verify_reset_token

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
    Account created in Supabase but NOT usable locally until OTP verified.
    Sends 6-digit OTP to email.
    """
    admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    # Check if email already registered and verified
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing and existing.is_email_verified:
        raise HTTPException(400, 'Email already registered and verified')

    user_id = None
    try:
        sb_response = admin_client.auth.admin.create_user({
            'email': payload.email,
            'password': payload.password,
            'email_confirm': True,
            'user_metadata': {'full_name': payload.full_name}
        })
        # Extract user_id from various possible response formats
        sb_user = getattr(sb_response, 'user', sb_response)
        user_id = getattr(sb_user, 'id', None)
        if not user_id and isinstance(sb_user, dict):
            user_id = sb_user.get('id')
            
    except Exception as e:
        error_msg = str(e).lower()
        if 'already' in error_msg:
            # User exists in Supabase. We must fetch them to get their ID for the local sync.
            try:
                users_res = admin_client.auth.admin.list_users()
                user_list = getattr(users_res, 'users', users_res)
                target = next((u for u in user_list if u.email == payload.email), None)
                if target:
                    user_id = target.id
            except Exception as inner_e:
                logger.error(f"Failed to fetch existing user from Supabase: {str(inner_e)}")
        
        if not user_id:
            db.rollback()
            raise HTTPException(400, f'Registration error: {str(e)}')

    # Final Local sync
    try:
        if not existing:
            # Check if THIS user_id is already in the DB under a different email (cleanup)
            dup_id = db.query(User).filter(User.user_id == user_id).first()
            if dup_id:
                db.delete(dup_id)
                db.commit()
            
            new_user = User(
                user_id=user_id,
                email=payload.email,
                full_name=payload.full_name,
                password_hash="[MANAGED_BY_SUPABASE]",
                is_email_verified=False
            )
            db.add(new_user)
            db.commit()
    except Exception as db_e:
        db.rollback()
        logger.error(f"Local sync failed: {str(db_e)}")
        # If it's a duplicate ID error, we might be in a race condition. 
        # But we've already done our best to clean it up.

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
    Login. Blocked if email not verified locally.
    Returns Supabase JWT for authenticated access.
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
        full_name=user.full_name,
    )

@router.post('/forgot-password')
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Step 1: User enters their email.
    Sends 6-digit OTP for password reset.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    # Always return success message for security (don't reveal user existence)
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
    Returns a reset_token needed for the final reset action.
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
    return {'message': 'Logged out successfully'}
