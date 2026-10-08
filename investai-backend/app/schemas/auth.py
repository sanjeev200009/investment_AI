from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field
from uuid import UUID

# EmailStr lowercases only the domain. Supabase stores the whole address
# lowercased, and our lookups are exact matches, so "John@x.com" at register
# and "john@x.com" at login used to be two different accounts to us.
Email = Annotated[EmailStr, AfterValidator(str.lower)]

def _strong(password: str) -> str:
    """New passwords need a letter and a number; login does not re-check old ones."""
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("Password must contain both letters and numbers")
    return password


NewPassword = Annotated[str, Field(min_length=8), AfterValidator(_strong)]


class RegisterRequest(BaseModel):
    email: Email
    password: NewPassword
    full_name: str = Field(min_length=2)

class LoginRequest(BaseModel):
    email: Email
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user_id: str
    email: str
    full_name: str | None = None
    # Supabase access tokens expire in about an hour. Returning the refresh
    # token lets the client renew silently via POST /auth/refresh; before the
    # I-02 cutover Clerk's SDK did this invisibly, so dropping it here would
    # have signed every user out mid-session.
    refresh_token: str | None = None
    expires_in: int | None = None

class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)

class OTPVerifyRequest(BaseModel):
    email: Email
    otp_code: str = Field(min_length=6, max_length=6)
    # Set on the Supabase account at verification, not at registration; see
    # routers/auth.py verify_registration_otp.
    password: NewPassword

class ForgotPasswordRequest(BaseModel):
    email: Email

class VerifyResetOTPRequest(BaseModel):
    email: Email
    otp_code: str = Field(min_length=6, max_length=6)

class ResetPasswordRequest(BaseModel):
    email: Email
    reset_token: str
    new_password: NewPassword

class UserOut(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None
    role: str
    is_email_verified: bool

    class Config:
        from_attributes = True
