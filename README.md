# Finance Buddy - Intelligent Financial Assistant

## Overview
**Finance Buddy** is an advanced, geography-aware financial assistant designed for the Nigerian market (and global investors). It goes beyond simple chatbot responses by employing a **Multi-Agent Orchestration Architecture** to guide users through their financial journey—from onboarding and profiling to active trading analysis and passive investment recommendations.

## Core Features

### 1. **Smart Onboarding & Profiling**
-   **Structured Onboarding**: New users are guided through a 7-step questionnaire to determine their financial personality.
-   **User Profiling**: Automatically infers **Risk Tolerance**, **Investment Horizon**, and **Capital Allocation** based on answers.
-   **Database Integration**: Stores profiles in PostgreSQL for persistent, personalized advice.

### 2. **Intelligent Orchestration**
-   The **Orchestrator Agent** analyzes user intent and routes queries to the most relevant specialist:
    -   **Trading Agent**: For active stock analysis, technicals, and market sentiment (Uses the Proponent-Skeptic-Judge workflow).
    -   **Investment Options Agent**: For passive savings, Fixed Income (T-Bills), and Mutual Funds. Prioritizes **Nigerian** options first.
    -   **Budgeting Agent**: For expense tracking and debt management advice.

### 3. **Real-Time Knowledge Base (Web Scraping)**
-   **Scraper**: `scripts/scrape_finance_data.py` fetches real-time rates (Savings, T-Bills) and platform details (Bamboo, Chaka, etc.) from the web.
-   **Context-Aware**: The Investment Agent uses this local knowledge base (`data/*.md`) to provide accurate, up-to-date answers with citations.

### 4. **Multi-Modal Interface (Audio)**
-   **Voice Support**: The API accepts audio files, transcribes them (mocked), processes the query, and returns both text and audio responses.

## System Architecture

```mermaid
graph TD
    User[User] -->|Text/Audio| API[FastAPI]
    API -->|Thread ID| Orchestrator[Orchestrator Agent]
    
    subgraph "Routing Layer"
        Orchestrator -->|Active Trading| Trading[Trading & Analyst Agent]
        Orchestrator -->|Savings/Rates| Invest[Investment Options Agent]
        Orchestrator -->|Expenses| Budget[Budgeting Agent]
        Orchestrator -->|New User| Onboard[Onboarding Agent]
    end
    
    subgraph "Data Sources"
        Trading -->|Sentiment| Tavily[Tavily API]
        Trading -->|Technicals| AlphaV[Alpha Vantage]
        Invest -->|Rates/Fees| KB[Local Knowledge Base (Scraped)]
        Onboard -->|Profile| DB[(PostgreSQL)]
    end
```

## Prerequisites
-   **Python 3.10+**
-   **PostgreSQL** (Active instance required)
-   **API Keys**: Google Gemini (or OpenAI), Tavily.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd Investment_Analysis_Hackathon
    ```

2.  **Install Dependencies**:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    pip install -r requirements.txt
    ```

3.  **Environment Setup**:
    Create a `.env` file:
    ```ini
    # Database
    db_user=postgres
    db_password=your_password
    db_host=localhost
    db_port=5432
    db_name=investment_db

    # Keys
    GOOGLE_API_KEY=your_gemini_key
    TAVILY_API_KEY=your_tavily_key
    SECRET_KEY=your_jwt_secret
    ```

## Usage Guide

### 1. Populate Knowledge Base
Before starting, fetch the latest financial data:
```bash
python scripts/scrape_finance_data.py
# Generates data/finance_knowledge.md and data/platforms.md
```

### 2. Start the API
Run the FastAPI server:
```bash
python api.py
# Server starts at http://127.0.0.1:8000
```
*Note: The server automatically initializes the database tables and the chatbot graph on startup.*

### 3. API Endpoints
-   **Auth**:
    -   `POST /auth/register`: Create account.
    -   `POST /auth/token`: Login (Get JWT).
-   **Onboarding**:
    -   `GET /onboarding/questions`: Fetch the 7 onboarding questions.
    -   `POST /onboarding/submit`: Submit answers to generate profile.
-   **Chat**:
    -   `POST /chat`: Text-based interaction.
    -   `POST /audio/chat`: Upload audio file (`.wav`/`.mp3`), get text + audio response.

## Testing
Run the integration tests to verify the workflow:
```bash
python tests/test_workflow.py
```
