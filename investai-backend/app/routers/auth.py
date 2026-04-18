from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.schemas.auth import UserCreate, UserLogin, Token

router = APIRouter()

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user in Supabase and sync to local DB.
    """
    # Placeholder for actual Supabase logic
    return {"access_token": "placeholder_token", "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user via Supabase and return access token.
    """
    # Placeholder for actual Supabase logic
    return {"access_token": "placeholder_token", "token_type": "bearer"}
