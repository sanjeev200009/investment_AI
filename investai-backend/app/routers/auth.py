# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session
from supabase import create_client
from gotrue.errors import AuthRetryableError
from datetime import timedelta
import logging

from app.dependencies import bearer_scheme, get_db, get_current_user
from app.rate_limit import limit
from app.models.user import User
from app.schemas.auth import (RegisterRequest, LoginRequest,
                               TokenResponse, UserOut, OTPVerifyRequest,
                               ForgotPasswordRequest, ResetPasswordRequest,
                               VerifyResetOTPRequest, RefreshRequest)
from app.config import get_settings
from app.services.email_service import (send_registration_otp,
                                send_welcome_email, send_reset_otp)
from app.services.otp import OTPRateLimited, create_otp, verify_otp
from app.utils.security import create_reset_token, verify_reset_token

logger = logging.getLogger(__name__)
settings = get_settings()

# Every auth endpoint is rate limited per client IP: 10 calls a minute is far
# above what a person typing needs and far below what guessing needs.
router = APIRouter(prefix='/auth', tags=['Authentication'],
                   dependencies=[Depends(limit('auth', 10, 60))])

OTP_TOO_SOON = 'Please wait a minute before requesting another code.'


def _find_supabase_user_id(admin_client, email: str):
    # list_users() returns one page (50 by default); walk the pages so a
    # re-registration still finds the account once there are more users.
    page = 1
    while True:
        batch = admin_client.auth.admin.list_users(page=page, per_page=200)
        users = getattr(batch, 'users', batch) or []
        for u in users:
            if (u.email or '').lower() == email.lower():
                return u.id
        if len(users) < 200:
            return None
        page += 1

def _user_by_email(db: Session, email: str):
    # Request emails arrive lowercased (schemas/auth.py); lower() the column too
    # so rows stored mixed-case before that normalisation are still found.
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()

def get_supabase():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

@router.post('/register', status_code=201)
def register(
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
    existing = _user_by_email(db, payload.email)
    if existing and existing.is_email_verified:
        raise HTTPException(400, 'Email already registered and verified')

    user_id = None
    try:
        sb_response = admin_client.auth.admin.create_user({
            'email': payload.email,
            'password': payload.password,
            # Deliberately NOT confirmed here. Creating the user pre-confirmed
            # made the OTP decorative: Supabase would accept
            # sign_in_with_password for this account immediately, and the anon
            # key needed to do that is public by design and ships inside the
            # mobile app. The only gate was our own `is_email_verified` column,
            # which anyone talking to Supabase directly simply bypassed.
            # Confirmation now happens in /auth/verify-otp, so possession of the
            # emailed code is what actually unlocks the account.
            'email_confirm': False,
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
                user_id = (str(existing.user_id) if existing
                           else _find_supabase_user_id(admin_client, payload.email))
            except Exception as inner_e:
                logger.error(f"Failed to fetch existing user from Supabase: {str(inner_e)}")
        
        if not user_id:
            db.rollback()
            logger.error('Registration failed for %s: %s', payload.email, e)
            raise HTTPException(400, 'Registration failed. Please check your details and try again.')

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
        # Returning 201 here sent an OTP for an account /verify-otp could never
        # find. Fail visibly instead so the user can simply retry.
        raise HTTPException(503, 'Registration is temporarily unavailable. Please try again.')

    # Generate and send OTP. The password given here is NOT authoritative: if
    # this email already had an unconfirmed Supabase account (someone else may
    # have registered it first), that account keeps its old password until
    # /verify-otp sets the one supplied by whoever holds the emailed code.
    try:
        otp = create_otp(db, payload.email, purpose='register')
    except OTPRateLimited:
        raise HTTPException(429, OTP_TOO_SOON)
    background_tasks.add_task(
        send_registration_otp, payload.email, otp, payload.full_name)

    return {
        'message': 'Registration successful. Check your email for the OTP code.',
        'email': payload.email,
        'next_step': 'POST /auth/verify-otp with your 6-digit code',
    }

@router.post('/verify-otp')
def verify_registration_otp(
    payload: OTPVerifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Step 2 of 2: Verify the OTP sent after registration.

    This is where the account actually becomes usable. Registration creates the
    Supabase identity *unconfirmed*, so until this succeeds Supabase itself
    refuses sign_in_with_password — the OTP is a real gate rather than a local
    flag that only our own /auth/login consults.
    """
    # Check the code without spending it. The Supabase confirmation below is the
    # step that can fail for reasons outside the user's control, and burning
    # their code before attempting it would leave them unable to retry.
    if not verify_otp(db, payload.email, payload.otp_code, purpose='register',
                      consume=False):
        raise HTTPException(400, 'Invalid or expired OTP. Request a new one.')

    user = _user_by_email(db, payload.email)
    if not user:
        raise HTTPException(404, 'User not found')

    # Confirm the email in Supabase Auth. Idempotent, so a retry after a partial
    # failure is safe.
    admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    try:
        # The password is set here, by whoever proved they own the inbox. Setting
        # it at /register let anyone pre-register a victim's email with their own
        # password and inherit the account once the victim verified.
        admin.auth.admin.update_user_by_id(
            str(user.user_id),
            {'email_confirm': True, 'password': payload.password})
    except Exception as exc:
        logger.exception(
            'Could not confirm Supabase email for %s; OTP left unspent so the '
            'user can retry', payload.email)
        raise HTTPException(
            503,
            'Could not complete verification. Please try that code again.',
        ) from exc

    # Supabase is confirmed; now spend the code and record the local flag.
    verify_otp(db, payload.email, payload.otp_code, purpose='register')
    user.is_email_verified = True
    db.commit()

    # Send welcome email
    background_tasks.add_task(
        send_welcome_email, payload.email, user.full_name or 'Investor')

    return {'message': 'Email verified! You can now log in.'}

@router.post('/resend-otp')
def resend_otp(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Resend registration OTP if user did not receive it."""
    # Same answer whether or not the email exists or is verified, so this
    # endpoint cannot be used to discover who has an account.
    user = _user_by_email(db, payload.email)
    if user and not user.is_email_verified:
        try:
            otp = create_otp(db, payload.email, purpose='register')
        except OTPRateLimited:
            raise HTTPException(429, OTP_TOO_SOON)
        background_tasks.add_task(
            send_registration_otp, payload.email, otp, user.full_name or '')
    return {'message': 'If that email is awaiting verification, a new code has been sent.'}

@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Login. Blocked if email not verified locally.
    Returns Supabase JWT for authenticated access.
    """
    # Check verification BEFORE calling Supabase
    user = _user_by_email(db, payload.email)
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
    except AuthRetryableError:
        # Network failure or Supabase 5xx: not the user's password.
        raise HTTPException(503, 'Sign-in is temporarily unavailable. Please try again.')
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
        refresh_token=auth_response.session.refresh_token,
        expires_in=auth_response.session.expires_in,
    )


@router.post('/refresh', response_model=TokenResponse)
def refresh_session(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a refresh token for a fresh Supabase access token.

    Needed because access tokens live about an hour and app/dependencies.py now
    enforces `exp`. Without this the app would 401 and sign the user out
    mid-session — Clerk's SDK used to refresh transparently, so removing Clerk
    without adding this would have been a regression.

    Deliberately unauthenticated: the caller's access token is expired by
    definition, so the refresh token is the credential being presented. Supabase
    rotates it on use, so a token can only be redeemed once.
    """
    supabase = get_supabase()
    try:
        auth_response = supabase.auth.refresh_session(payload.refresh_token)
    except AuthRetryableError:
        # Supabase unreachable. 503, not 401: a 401 makes the app sign the user
        # out, which an outage is no reason to do.
        raise HTTPException(503, 'Sign-in is temporarily unavailable. Please try again.')
    except Exception:
        # Wrong, revoked, or already-redeemed token. 401 so the client's
        # interceptor treats it as "session over" and signs out.
        raise HTTPException(401, 'Session expired. Please sign in again.')

    if not auth_response or not auth_response.session:
        raise HTTPException(401, 'Session expired. Please sign in again.')

    # Keep full_name authoritative from our own users table rather than from
    # Supabase metadata, which registration does not keep in step.
    user = _user_by_email(db, auth_response.user.email or '')

    return TokenResponse(
        access_token=auth_response.session.access_token,
        token_type='bearer',
        user_id=str(auth_response.user.id),
        email=auth_response.user.email,
        full_name=user.full_name if user else None,
        refresh_token=auth_response.session.refresh_token,
        expires_in=auth_response.session.expires_in,
    )

@router.post('/forgot-password')
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Step 1: User enters their email.
    Sends 6-digit OTP for password reset.
    """
    user = _user_by_email(db, payload.email)
    # Always return success message for security (don't reveal user existence)
    if user:
        try:
            otp = create_otp(db, payload.email, purpose='reset_password')
            background_tasks.add_task(send_reset_otp, payload.email, otp)
        except OTPRateLimited:
            # Silently skip: a 429 here would reveal that the email exists.
            logger.info('Reset OTP rate-limited for %s', payload.email)
    
    return {
        'message': 'If that email exists, an OTP has been sent.',
        'next_step': 'POST /auth/verify-reset-otp with your 6-digit code',
    }

@router.post('/verify-reset-otp')
def verify_reset_otp_endpoint(
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
    
    reset_token = create_reset_token(db, payload.email)
    return {
        'message': 'OTP verified.',
        'reset_token': reset_token,
        'next_step': 'POST /auth/reset-password with new_password + reset_token',
    }

@router.post('/reset-password')
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Step 3: User submits new password + reset_token.
    Updates password in Supabase Auth.
    """
    # Check the token without spending it; it is spent only once Supabase has
    # accepted the new password, so a failure below can be retried.
    email = verify_reset_token(db, payload.reset_token, consume=False)
    if not email or email != payload.email:
        raise HTTPException(400, 'Invalid or expired reset token')

    # Use Supabase Admin to update the password
    admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    user = _user_by_email(db, email)
    if not user:
        raise HTTPException(404, 'User not found')

    try:
        admin.auth.admin.update_user_by_id(
            str(user.user_id),
            {'password': payload.new_password}
        )
    except Exception as e:
        logger.error('Password update failed for %s: %s', email, e)
        raise HTTPException(503, 'Could not update the password. Please try again.')

    verify_reset_token(db, payload.reset_token)
    return {'message': 'Password reset successfully. You can now log in.'}

@router.get('/me', response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post('/logout')
def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    """Revoke the caller's Supabase refresh tokens (all devices).

    Best effort: the client clears its own tokens regardless, and an expired or
    missing access token just means there is nothing left to revoke.
    """
    if credentials:
        try:
            admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            admin.auth.admin.sign_out(credentials.credentials)
        except Exception as exc:
            logger.info('Logout revoke skipped: %s', exc)
    return {'message': 'Logged out successfully'}
