from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Annotated
import os
import sys
import asyncio
import json
import base64

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from database import engine, get_db, Base
from models import User, PortfolioItem, Onboarding
from schemas import UserCreate, UserResponse, Token, ChatRequest, OnboardingSubmission, OnboardingResponse
from chatbot import InvestmentChatbot
from auth import authenticate_user, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password, get_password_hash
from agents.onboarding import get_trading_onboarding_questions, get_conservative_onboarding_questions, profiler_node
import uvicorn

# Initialize DB Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Finance Buddy API", version="2.0")

# Initialize Chatbot Instance
chatbot = InvestmentChatbot()

@app.on_event("startup")
async def startup_event():
    await chatbot.initialize()

from gtts import gTTS
import io

# --- Helper Functions ---

def generate_tts_audio(text: str) -> str:
    """
    Generates audio from text using Google Text-to-Speech (gTTS).
    Returns base64 encoded MP3.
    """
    try:
        # Create a BytesIO buffer to hold the audio data in memory
        mp3_fp = io.BytesIO()
        
        # Initialize gTTS with the text (English)
        tts = gTTS(text=text, lang='en', tld='com.ng') # Use Nigerian accent if available via TLD or just generic 'com'
        
        # Write to buffer
        tts.write_to_fp(mp3_fp)
        
        # Get the bytes
        mp3_bytes = mp3_fp.getvalue()
        
        # Encode to base64
        audio_b64 = base64.b64encode(mp3_bytes).decode('utf-8')
        
        return audio_b64
    except Exception as e:
        print(f"TTS Error: {e}")
        # Fallback to silence if TTS fails
        return "UklGRi4AAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQA=" 

# --- Onboarding Endpoints ---



@app.get("/onboarding/trading")
async def get_trading_questions():
    """Returns onboarding questions tailored for active traders."""
    return {"questions": get_trading_onboarding_questions()}

@app.get("/onboarding/conservative")
async def get_conservative_questions():
    """Returns onboarding questions tailored for conservative investors."""
    return {"questions": get_conservative_onboarding_questions()}

@app.post("/onboarding/submit", response_model=OnboardingResponse)
async def submit_onboarding(
    submission: OnboardingSubmission, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submits answers and generates a profile."""
    # Check existing
    existing = db.query(Onboarding).filter(Onboarding.user_id == current_user.id).first()
    
    answers_json = json.dumps(submission.answers)
    
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
        # Construct a minimal state for the profiler
        # profiler_node expects state["onboarding_state"]["answers"]
        # And also needs to be compatible with AgentState structure somewhat
        profile_state = {
            "onboarding_state": {
                "answers": submission.answers
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

# --- Audio Endpoint ---

@app.post("/audio/chat")
async def audio_chat(
    file: UploadFile = File(...),
    thread_id: str = Form("default"),
    current_user: User = Depends(get_current_user)
):
    """
    Receives an audio file (blob), transcribes it, runs the agent, and returns text + audio response.
    """
    # 1. Save uploaded file temporarily
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        buffer.write(await file.read())
        
    try:
        # 2. Transcribe (Mocking STT)
        user_text = "I want to invest 500k naira in high yield savings." # Mock transcription
        
        # 3. Process with Agent
        response_text = await chatbot.chat(user_text, thread_id=str(current_user.id))
        
        # 4. Text-to-Speech
        # audio_b64 = generate_tts_audio(response_text)
        audio_b64 = None
        
        return {
            "transcription": user_text,
            "text_response": response_text,
            "audio_base64": audio_b64,
            "audio_format": "mp3"
        }
        
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

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

@app.post("/chat/greeting")
async def chat_greeting(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Generates a proactive greeting based on the user's profile.
    """
    thread_id = str(current_user.id)
    
    # Generate Greeting
    greeting_text = await chatbot.generate_greeting(thread_id=thread_id)
    
    # Generate Audio
    # audio_b64 = generate_tts_audio(greeting_text)
    audio_b64 = None
    
    return {
        "text_response": greeting_text,
        "audio_base64": audio_b64,
        "audio_format": "mp3"
    }

@app.post("/chat")
async def chat_with_agent(
    request: ChatRequest, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    **Intelligent Analyst Chat Endpoint**
    
    Initiates or continues a conversation with the Intelligent Trading Analyst.
    Returns both text response and generated audio.
    """
    thread_id = str(current_user.id)
    
    # Pass thread_id securely to the chat method
    response_text = await chatbot.chat(request.message, thread_id=thread_id)
    
    # Generate Audio
    # audio_b64 = generate_tts_audio(response_text)
    audio_b64 = None
    
    return {
        "text_response": response_text,
        "audio_base64": audio_b64,
        "audio_format": "mp3"
    }

@app.post("/chat/budgeting")
async def chat_budgeting(
    request: ChatRequest, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    **Budgeting Assistant Endpoint**
    
    Specific endpoint for budgeting, debt management, and expense tracking advice.
    Forces the chatbot to use the Budgeting Expert persona.
    """
    thread_id = str(current_user.id)
    response_text = await chatbot.chat(request.message, thread_id=thread_id, intent="budgeting")
    # audio_b64 = generate_tts_audio(response_text)
    audio_b64 = None
    
    return {
        "text_response": response_text,
        "audio_base64": audio_b64,
        "audio_format": "mp3"
    }

@app.post("/chat/investment")
async def chat_investment(
    request: ChatRequest, 
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    **Investment Analyst Endpoint**
    
    Specific endpoint for active trading analysis and investment proposals.
    Forces the chatbot to use the Investment Analyst persona.
    """
    thread_id = str(current_user.id)
    # Defaulting to 'trading' for active analysis, or 'investment_options' for passive.
    # Given 'Analyst' persona, 'trading' fits best.
    response_text = await chatbot.chat(request.message, thread_id=thread_id, intent="trading")
    # audio_b64 = generate_tts_audio(response_text)
    audio_b64 = None
    
    return {
        "text_response": response_text,
        "audio_base64": audio_b64,
        "audio_format": "mp3"
    }

@app.get("/portfolio")
def get_user_portfolio(current_user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    """
    **Get User Portfolio**
    
    Retrieves the current stock holdings for the authenticated user from the local database.
    
    *Note*: This returns the *recorded* portfolio state. Real-time broker positions are not currently integrated.
    """
    items = db.query(PortfolioItem).filter(PortfolioItem.user_id == current_user.id).all()
    return {"user": current_user.username, "holdings": items}

@app.get("/")
def home():
    return {"message": "InvestmentBrain API is Online. Go to /docs for Swagger UI."}

