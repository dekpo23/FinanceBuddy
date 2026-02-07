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
    answers: Dict[str, Any] # Request manual parsing if using String in DB
    derived_profile: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
