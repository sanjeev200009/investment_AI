# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User, UserProfile
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserOut
from app.utils.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix='/auth', tags=['Authentication'])

@router.post('/register', response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, 'Email already registered')
    
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    
    profile = UserProfile(user_id=user.user_id, full_name=payload.full_name)
    db.add(profile)
    db.commit()
    db.refresh(user)
    
    token = create_access_token(str(user.user_id))
    return TokenResponse(
        access_token=token,
        user_id=str(user.user_id),
        email=user.email
    )

@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, 'Invalid email or password')
    
    token = create_access_token(str(user.user_id))
    return TokenResponse(
        access_token=token,
        user_id=str(user.user_id),
        email=user.email
    )

@router.get('/me', response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post('/logout')
def logout():
    return {'message': 'Logged out — clear token on client'}
