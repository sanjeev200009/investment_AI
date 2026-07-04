import uuid
import logging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt

from app.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)
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
        # Decode the Clerk token to get the user ID
        payload = jwt.get_unverified_claims(token)
        clerk_sub = payload.get("sub", "unknown")
        
        # 1. Fetch existing user from the database by mapping clerk_sub to email for now
        mapped_email = f"{clerk_sub}@clerk.local"
        user = db.query(User).filter(User.email == mapped_email).first()
        
        # 2. If no user exists, create a dummy one mapped to this Clerk sub
        if not user:
            logger.info(f"No user found for Clerk sub {clerk_sub}. Creating record in DB.")
            user = User(
                email=mapped_email,
                password_hash="clerk_mock_hash",
                full_name="Clerk User"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
        return user
    except Exception as e:
        logger.error(f"Error parsing Clerk token: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
