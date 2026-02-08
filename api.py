from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Annotated

import sys
import asyncio
import json


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from database import engine, get_db, Base
from models import User, PortfolioItem, Onboarding
from schemas import UserCreate, UserResponse, Token, ChatRequest, OnboardingSubmission, OnboardingResponse
from chatbot import InvestmentChatbot
from auth import authenticate_user, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password, get_password_hash
from agents.onboarding import profiler_node, get_onboarding_schema
import uvicorn

# Initialize DB Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Finance Buddy API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Chatbot Instance
chatbot = InvestmentChatbot()

@app.on_event("startup")
async def startup_event():
    await chatbot.initialize()



# --- Onboarding Endpoints ---

@app.get("/onboarding")
def get_onboarding_questions_schema():
    """
    Returns the unified onboarding questions (JSON schema).
    """
    schema = get_onboarding_schema()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema unavailable")
    return schema

@app.post("/onboarding/submit", response_model=OnboardingResponse)
async def submit_onboarding(
    answers: dict = Body(..., example={
        "q1": "Answer",
        "q2": "Answer",
        "q3": "Answer",
        "q4": "Answer",
        "q5": "Answer",
        "q6": "Answer",
        "q7": "Answer"
    }), 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits answers and generates a unified financial profile.
    Body should be a JSON object where keys are question IDs and values are answers.
    """
    # Check existing
    existing = db.query(Onboarding).filter(Onboarding.user_id == current_user.id).first()
    
    answers_json = json.dumps(answers)
    
    if existing:
        existing.answers = answers_json
    else:
        new_record = Onboarding(user_id=current_user.id, answers=answers_json)
        db.add(new_record)
        existing = new_record
    
    db.commit()
    db.refresh(existing)
    
    # --- Trigger Profiling ---
    try:
        profile_state = {
            "onboarding_state": {
                "answers": answers
            }
        }
        
        # Use the chatbot's LLM instance
        result = profiler_node(profile_state, chatbot.llm)
        derived_profile = result.get("derived_profile", {})
        
        # Save to DB
        existing.derived_profile = json.dumps(derived_profile)
        db.commit()
        db.refresh(existing)
        
    except Exception as e:
        print(f"Profiling failed: {e}")
        derived_profile = None

    return OnboardingResponse(
        id=existing.id, 
        user_id=existing.user_id, 
        answers=json.loads(existing.answers),
        derived_profile=json.loads(existing.derived_profile) if existing.derived_profile else None
    )


# --- Chat Endpoints ---

@app.post("/auth/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter((User.username == user.username) | (User.email == user.email)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        age=user.age
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/auth/token", response_model=Token)
def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    # Check if username matches either 'username' or 'email' field
    user = db.query(User).filter((User.username == form_data.username) | (User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserResponse)
def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Returns the current authenticated user's details (ID, Username, Email).
    Use the 'id' field as the thread_id for chat interactions.
    """
    return current_user



@app.post("/chat")
async def chat_with_agent(
    request: ChatRequest, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    **Banking & Investment Products Endpoint**
    
    Handles low-to-moderate risk financial products:
    - Treasury Bills
    - Fixed Deposits / Money Market Funds
    - Savings Instruments
    
    Does NOT handle active trading or stock picking (use `/chat/trading`).
    """
    thread_id = str(current_user.id)
    # Default intent for main chat is now Banking/Investment
    response_text = await chatbot.chat(request.message, thread_id=thread_id, intent="general") 
    
    return {
        "text_response": response_text,
        "audio_base64": None,
        "audio_format": "mp3"
    }

@app.post("/chat/budgeting")
async def chat_budgeting(
    request: ChatRequest, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    **Budgeting & Cashflow Endpoint**
    
    Focuses on income, expenses, debt management, and actionable savings steps.
    """
    thread_id = str(current_user.id)
    response_text = await chatbot.chat(request.message, thread_id=thread_id, intent="budgeting")
    
    return {
        "text_response": response_text,
        "audio_base64": None,
        "audio_format": "mp3"
    }

@app.post("/chat/trading")
async def chat_trading(
    request: ChatRequest, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    **Active Trading Endpoint**
    
    Handles:
    - Stocks & ETFs (NGX, US)
    - Portfolio Construction
    - Active Investment Strategies
    """
    thread_id = str(current_user.id)
    response_text = await chatbot.chat(request.message, thread_id=thread_id, intent="trading")
    
    return {
        "text_response": response_text,
        "audio_base64": None,
        "audio_format": "mp3"
    }

@app.get("/portfolio", response_model=list[dict]) 
def get_portfolio_recommendations(
    current_user: Annotated[User, Depends(get_current_user)], 
    db: Session = Depends(get_db)
):
    """
    **Get Portfolio Recommendations**
    
    Retrieves the history of portfolio recommendations generated by the Trading Agent.
    Returns: List of portfolio objects with versioning/timestamps.
    """
    # Import locally to avoid circular import issues if placed at top before models is fully loaded
    from models import PortfolioRecommendation
    
    recs = db.query(PortfolioRecommendation).filter(PortfolioRecommendation.user_id == current_user.id).order_by(PortfolioRecommendation.created_at.desc()).all()
    
    results = []
    for r in recs:
        results.append({
            "id": r.id,
            "portfolio": json.loads(r.portfolio),
            "risk_level": r.risk_level,
            "created_at": r.created_at
        })
        
    return results

@app.get("/")
def home():
    return {"message": "Finance Buddy API is Online. Go to /docs for Swagger UI."}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
