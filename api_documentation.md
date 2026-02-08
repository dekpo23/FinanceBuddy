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

### 1. Get Questions
**GET** `/onboarding`
- **Response:** JSON object containing the unified set of onboarding questions.

### 2. Submit Answers
**POST** `/onboarding/submit`

**Body:**
A simple JSON object where keys are question IDs and values are the user's answers.

**Example:**
```json
{
  "q1": "Aggressive Wealth Growth",
  "q2": "Hold and wait for recovery",
  "q3": "Over 10,000,000",
  "q4": "Long Term (5+ years)",
  "q5": "Balanced",
  "q6": "Intermediate",
  "q7": "Naira Only"
}
```

**Response:**
Returns the generated `derived_profile`.
```json
{
    "id": 1,
    "user_id": 1,
    "answers": { "q1": "..." },
    "derived_profile": {
        "risk_score": 7,
        "investor_type": "Growth",
        "recommended_allocation": { ... }
    }
}
```

---

## Chat


### 1. Budgeting Chat (NEW)
**POST** `/chat/budgeting`
- Use this for "Budget Helper" mode. It forces the AI to focus on savings/debt.
**Body:**
```json
{
  "message": "How can I save more money each month?"
}
```

### 2. Investment Analyst Chat (NEW)
**POST** `/chat/investment`
- Use this for "Investment Analyst" mode (Stocks, T-Bills, Market Analysis).
**Body:**
```json
{
  "message": "What are the best T-Bill rates right now?"
}
```

### 3. General Chat (Router)
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
