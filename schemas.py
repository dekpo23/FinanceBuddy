from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    age: Optional[int] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    age: Optional[int]

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None



from typing import Dict, Any, List

class OnboardingSubmission(BaseModel):
    answers: Dict[str, Any]

class OnboardingResponse(BaseModel):
    id: int
    user_id: int
    answers: dict # Request manual parsing if using String in DB
    derived_profile: Optional[dict] = None
    
    class Config:
        from_attributes = True

class PortfolioRecommendationResponse(BaseModel):
    id: int
    portfolio: list[dict] # List of assets with weights
    risk_level: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
