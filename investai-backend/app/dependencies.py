# app/dependencies.py
import uuid
import logging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from supabase import create_client

from app.database import SessionLocal
from app.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()
bearer_scheme = HTTPBearer()

# Initialize Supabase client once for performance
admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    
    # 1. Verify token with Supabase (source of truth for auth)
    try:
        user_response = admin_client.auth.get_user(token)
        if not user_response or not user_response.user:
            logger.error("Supabase verification failed: No user in response")
            raise HTTPException(status_code=401, detail='Invalid token')
        supabase_user_id = user_response.user.id
        logger.info(f"Supabase token verified for user: {supabase_user_id}")
    except Exception as e:
        logger.error(f"Supabase verification exception: {str(e)}")
        raise HTTPException(status_code=401, detail='Invalid or expired token')

    # 2. Find user in local database
    uid = uuid.UUID(str(supabase_user_id))
    user = db.query(User).filter(User.user_id == uid).first()
    
    if not user:
        logger.warning(f"User {uid} verified by Supabase but not found in local DB")
        raise HTTPException(status_code=404, detail='User not found')
    
    return user
