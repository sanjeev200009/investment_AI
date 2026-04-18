# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.database import SessionLocal
from supabase import create_client, Client

settings = get_settings()

# Initialize Supabase client
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

bearer_scheme = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        # Call Supabase to instantly verify the token and get the user identity
        response = supabase.auth.get_user(token)
        if not response or not response.user:
             raise HTTPException(status_code=401, detail='Invalid or expired token')
        
        user_id = response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f'Invalid token: {str(e)}')
    
    # Check if the user exists in our local PostgreSQL replica
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found in local database. Please ensure the trigger ran.')
    
    return user
