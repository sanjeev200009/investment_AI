# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user_id: str
    email: str

class UserOut(BaseModel):
    user_id: UUID
    email: str
    role: str

    class Config:
        from_attributes = True
