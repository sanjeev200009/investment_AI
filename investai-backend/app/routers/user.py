# app/routers/user.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from app.dependencies import get_db, get_current_user
from app.models.user import User, RiskProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/me', tags=['User'])

class AssessmentRequest(BaseModel):
    goal: str
    risk: str
    experience: str
    savings: str

class RiskProfileResponse(BaseModel):
    score: int
    category: str

@router.post('/risk-profile', response_model=RiskProfileResponse)
def update_risk_profile(
    payload: AssessmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate and save risk profile based on questionnaire answers.
    """
    score = 0
    
    # Calculate Risk Score (0-100)
    # Goal
    if payload.goal == 'Wealth Growth':
        score += 25
    elif payload.goal == 'Income Generation':
        score += 15
    elif payload.goal == 'Major Purchase':
        score += 10
    elif payload.goal == 'Retirement':
        score += 5
        
    # Risk
    if payload.risk == 'Speculative':
        score += 30
    elif payload.risk == 'Growth (Aggressive)':
        score += 25
    elif payload.risk == 'Moderate':
        score += 15
    elif payload.risk == 'Conservative (Low Risk)':
        score += 5
        
    # Experience
    if payload.experience == 'Expert Investor':
        score += 20
    elif payload.experience == 'Intermediate Trader':
        score += 15
    elif payload.experience == 'I know the basics':
        score += 10
    elif payload.experience == 'Complete Beginner':
        score += 5
        
    # Savings
    if payload.savings == '> Rs. 100,000':
        score += 25
    elif payload.savings == 'Rs. 50,000 - 100,000':
        score += 20
    elif payload.savings == 'Rs. 10,000 - 50,000':
        score += 15
    elif payload.savings == '< Rs. 10,000':
        score += 10
        
    score = min(max(score, 0), 100) # Ensure between 0 and 100
    
    if score >= 70:
        category = "High"
    elif score >= 40:
        category = "Medium"
    else:
        category = "Low"
        
    # Save to database
    rp = db.query(RiskProfile).filter(RiskProfile.user_id == current_user.user_id).first()
    if not rp:
        rp = RiskProfile(
            user_id=current_user.user_id,
            score=score,
            category=category
        )
        db.add(rp)
    else:
        rp.score = score
        rp.category = category
        
    db.commit()
    db.refresh(rp)
    
    return RiskProfileResponse(score=rp.score, category=rp.category)
