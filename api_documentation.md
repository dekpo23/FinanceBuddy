# Finance Buddy API Documentation

Base URL: `http://localhost:8000` (or deployed URL)

## Authentication

### 1. Register User
**POST** `/auth/register`
**Body:**
```json
{
  "username": "david",
  "email": "david@example.com",
  "password": "securepassword123",
  "age": 30
}
```

### 2. Login (Get Token)
**POST** `/auth/token`
- Content-Type: `application/x-www-form-urlencoded`
- Body: `username=david&password=securepassword123`

**Response:**
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer"
}
```
> **Note:** Include this token in the header of ALL subsequent requests: `Authorization: Bearer <token>`

### 3. Get Current User Info
**GET** `/auth/me`
**Response:**
```json
{
  "id": 1,
  "username": "david",
  "email": "david@example.com",
  "age": 30
}
```

---

## Onboarding (First Time User)

### 1. Get Questions (Conservative Track)
**GET** `/onboarding/conservative`

### 2. Get Questions (Trading Track)
**GET** `/onboarding/trading`

### 3. Submit Answers
**POST** `/onboarding/submit`

This endpoint accepts the user's answers to the onboarding questions. 
- You do NOT need to answer all questions if skipped, but providing more data improves the profile.
- The `answers` keys must match the question IDs found in the GET response (e.g. `c1`, `t1`).

**Body Example (Conservative Track):**
```json
{
  "answers": {
    "c1": "Beating Inflation (Preserving purchasing power)",
    "c2": "Medium Term (1 - 3 years)",
    "c3": "I can lock funds for 3-6 months",
    "c4": ["Treasury Bills (Government Backed)", "Fixed Deposits (Bank)"],
    "c5": "15-20% (Medium Risk / T-Bills)",
    "c6": "₦200,000 - ₦1,000,000",
    "c7": "Naira Only"
  }
}
```

**Body Example (Trading Track):**
```json
{
  "answers": {
    "t1": "Daily Income Generation (Day Trading)",
    "t2": "Novice (< 1 year)",
    "t3": "High (Willing to risk 20%+ for high returns)",
    "t4": ["Crypto (Bitcoin, Altcoins)", "Forex/Currencies"],
    "t5": "1-2 hours",
    "t6": "$2,000 - $10,000",
    "t7": "Never (Cash only)"
  }
}
```

**Response:**
Returns the generated `derived_profile`.
```json
{
    "id": 1,
    "user_id": 1,
    "answers": { ... },
    "derived_profile": {
        "risk_score": 7,
        "investor_type": "Growth",
        "recommended_allocation": { ... }
    }
}
```

---

## Chat & Greeting

### 1. Get Personalized Greeting
**POST** `/chat/greeting`
- **Body:** Empty JSON `{}` (or no body).
- **Response:**
```json
{
  "text_response": "Hi David! Given your conservative profile...",
  "audio_base64": "SUQzBAAAAA...",
  "audio_format": "mp3"
}
```

### 2. Budgeting Chat (NEW)
**POST** `/chat/budgeting`
- Use this for "Budget Helper" mode. It forces the AI to focus on savings/debt.
**Body:**
```json
{
  "message": "How can I save more money each month?"
}
```

### 3. Investment Analyst Chat (NEW)
**POST** `/chat/investment`
- Use this for "Investment Analyst" mode (Stocks, T-Bills, Market Analysis).
**Body:**
```json
{
  "message": "What are the best T-Bill rates right now?"
}
```

### 4. General Chat (Router)
**POST** `/chat`
- Automatically routes to budget or investment based on context.
**Body:**
```json
{
  "message": "Hello"
}
```

---

## Portfolio

### 1. Get User Portfolio
**GET** `/portfolio`
**Response:**
```json
{
  "user": "david",
  "holdings": [
    {"symbol": "TSLA", "quantity": 10, ...}
  ]
}
```
