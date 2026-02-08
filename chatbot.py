# chatbot.py
import os
import json
import sys
import asyncio
from typing import Annotated, TypedDict, List
from dotenv import load_dotenv, find_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
# from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver # Removed
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
# import aiosqlite # Removed
from sqlalchemy.orm import Session
from database import get_db
from models import User, Onboarding, PortfolioRecommendation
from langchain_core.messages import SystemMessage, HumanMessage
from agents.onboarding import onboarding_node, profiler_node
from agents.orchestrator import orchestrator_node
from agents.sentiment import create_sentiment_agent
from agents.red_team import red_team_node
from agents.judge import judge_node

# ... (rest of imports)

# Define the State
class AgentState(TypedDict):
    messages: List[dict]
    user_profile: dict
    thread_id: str
    onboarding_state: dict # keys: current_index, answers, complete
    derived_profile: dict # Result from profiler
    intent: str # trading, investment_options (banking), budgeting, general
    portfolio_recommendation: dict # To pass recommendation to persistence

class InvestmentChatbot:
    def __init__(self, thread_id: str = "investor_demo_001"):
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        self.thread_id = thread_id
        
        # Database Connection String for LangGraph Checkpointer
        self.db_url = os.getenv("DATABASE_URL")
        
        # Resolve absolute paths to ensure servers are found regardless of CWD
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.mcp_config = {
            "social": {
                "command": sys.executable,
                "args": [os.path.join(base_dir, "SocialIntelligence_server.py")],
                "transport": "stdio",
                "env": {"FASTMCP_DISABLE_BANNER": "1", **os.environ} 
            },
            "institutional": {
                "command": sys.executable,
                "args": [os.path.join(base_dir, "finance_server.py")], 
                "transport": "stdio",
                "env": {"FASTMCP_DISABLE_BANNER": "1", **os.environ}
            },
            "tavily": {
                "command": sys.executable,
                "args": [os.path.join(base_dir, "tavily_server.py")],
                "env": {"FASTMCP_DISABLE_BANNER": "1", **os.environ},
                "transport": "stdio"
            }
        }

    def _fetch_user_profile(self, state: AgentState):
        """Node: Fetches or validates user profile from DB."""
        # Use the thread_id (which is the user_id) to fetch the user
        try:
            user_id = int(state["thread_id"])
        except ValueError:
            # Fallback if thread_id is not an int (e.g. uuid)
            return {"user_profile": {"age": 30, "risk_profile": "moderate", "capital_range": "low_to_medium", "financial_literacy": "beginner"}}

        db = next(get_db())
        try:
            # Check for Onboarding Record
            onboarding_rec = db.query(Onboarding).filter(Onboarding.user_id == user_id).first()
            if onboarding_rec and onboarding_rec.derived_profile:
                try:
                    profile_data = json.loads(onboarding_rec.derived_profile)
                    profile_data["needs_onboarding"] = False
                    return {"derived_profile": profile_data, "user_profile": profile_data}
                except:
                    pass 
            
            # If no full profile, fetch basic user info
            user = db.query(User).filter(User.id == user_id).first()
            
            # Default / Needs Onboarding
            default_profile = {
                "age": user.age if user else 30,
                "needs_onboarding": True
            }
            return {"user_profile": default_profile}
        except Exception as e:
            return {"messages": [{"role": "assistant", "content": f"Database Error: {str(e)}"}]}
        finally:
            db.close()

    async def initialize(self):
        """Setup connections and build the graph."""
        # 1. Persistence Layer (Postgres)
        # Ensure we have a valid URL
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is not set.")

        self.pool = AsyncConnectionPool(conninfo=self.db_url, max_size=10, open=False)
        await self.pool.open()
        
        # Run setup to ensure tables exist
        async with self.pool.connection() as conn:
            await conn.set_autocommit(True)
            checkpointer = AsyncPostgresSaver(conn)
            await checkpointer.setup()

        self.checkpointer = AsyncPostgresSaver(self.pool)

        # 2. Connect to MCP Servers
        self.mcp_client = MultiServerMCPClient(self.mcp_config)
        self.mcp_tools = await self.mcp_client.get_tools()

        # 3. Build the Graph
        workflow = StateGraph(AgentState)
        
        # --- NODES ---
        # Onboarding
        workflow.add_node("onboarding", self._onboarding_node_wrapper)
        workflow.add_node("profiler", self._profiler_node_wrapper)
        
        # Core
        workflow.add_node("fetch_profile", self._fetch_user_profile)
        workflow.add_node("orchestrator", self._orchestrator_node_wrapper)
        
        # Branches
        workflow.add_node("general_chat", self._banking_node) # Remapped to Banking
        workflow.add_node("investment_options", self._banking_node) # Remapped to Banking
        workflow.add_node("budgeting", self._budgeting_node)
        
        # Trading Branch (Existing flow)
        workflow.add_node("sentiment_analysis", self._sentiment_node)
        workflow.add_node("analyst_proponent", self._analyst_node)
        workflow.add_node("red_team_skeptic", self._red_team_node)
        workflow.add_node("chief_investment_officer", self._judge_node)
        workflow.add_node("persist_portfolio", self._persist_portfolio_node)

        # --- EDGES ---
        # 1. Entry & Onboarding
        workflow.add_edge(START, "fetch_profile")
        
        workflow.add_conditional_edges(
            "fetch_profile",
            self._route_onboarding,
            {
                "onboarding": "onboarding",
                "ready": "orchestrator"
            }
        )
        
        workflow.add_conditional_edges(
            "onboarding",
            self._check_onboarding_complete,
            {
                "continue": "onboarding", 
                "complete": "profiler",
                "end_onboarding": END
            }
        )
        workflow.add_edge("profiler", "fetch_profile")

        # 2. Orchestration
        workflow.add_conditional_edges(
            "orchestrator",
            self._route_intent,
            {
                "trading": "sentiment_analysis",
                "investment_options": "general_chat", # Banking
                "budgeting": "budgeting",
                "general": "general_chat"
            }
        )

        # 3. Branch Flows
        # Trading Flow
        workflow.add_edge("sentiment_analysis", "analyst_proponent")
        workflow.add_edge("analyst_proponent", "red_team_skeptic")
        workflow.add_edge("red_team_skeptic", "chief_investment_officer")
        workflow.add_edge("chief_investment_officer", "persist_portfolio")
        workflow.add_edge("persist_portfolio", END)
        
        # Other Flows
        workflow.add_edge("general_chat", END)
        workflow.add_edge("investment_options", END)
        workflow.add_edge("budgeting", END)

        self.graph = workflow.compile(checkpointer=self.checkpointer)
        print("Intelligent Investment Analyst Online.")

    # --- WRAPPERS & ROUTING ---
    def _onboarding_node_wrapper(self, state):
        return onboarding_node(state)

    def _profiler_node_wrapper(self, state):
        # 1. Run the profiler logic
        result = profiler_node(state, self.llm)
        
        # 2. Save to Database
        try:
            # Ensure thread_id is int for user_id
            user_id = int(state["thread_id"])
            onboard_data = state.get("onboarding_state", {})
            answers = onboard_data.get("answers", {})
            profile = result.get("derived_profile", {})
            
            db = next(get_db())
            try:
                existing = db.query(Onboarding).filter(Onboarding.user_id == user_id).first()
                if existing:
                    existing.answers = json.dumps(answers)
                    existing.derived_profile = json.dumps(profile)
                else:
                    new_record = Onboarding(
                        user_id=user_id,
                        answers=json.dumps(answers),
                        derived_profile=json.dumps(profile)
                    )
                    db.add(new_record)
                
                db.commit()
            except Exception as e:
                print(f"Error saving onboarding profile: {e}")
            finally:
                db.close()
                
        except ValueError:
            print("Skipping DB save: Invalid User ID")
            
        return result

    def _orchestrator_node_wrapper(self, state):
        return orchestrator_node(state, self.llm)

    async def _banking_node(self, state):
        """Node: Banking & Investment Products (Non-Trading)."""
        profile = state.get("user_profile", {})
        
        system_msg = f"""
        You are a friendly Banking & Savings Consultant.
        Your goal is to explain "safe" investments in simple, everyday language.
        
        User Profile: {json.dumps(profile)}

        SCOPE ENFORCEMENT GRID:
        - [ALLOWED]: Treasury Bills, Fixed Deposits, Savings Accounts, Mutual Funds, Money Market.
        - [ALLOWED]: Banking Apps (GTBank, FirstBank, ALAT, etc.).
        - [PROHIBITED]: Stock trading (Send to Trading Chat).
        - [PROHIBITED]: General Knowledge (e.g. "What is photosynthesis?", "Who is the President?").
        
        If the user asks a PROHIBITED question:
        - Politely decline: "I can only help with banking and safe investments. I cannot answer general questions."
        - Do NOT answer the question.

        Your Advice Must Be:
        1. **Simple**: Explain "Treasury Bills" as "Lending money to the government for a fixed profit". Explain "Fixed Deposits" as "Locking your money in the bank for a higher interest rate".
        2. **Specific**: Suggest actual Nigerian banks/apps where they can buy these (e.g. GTBank App, FirstBank, ALAT, PiggyVest, Cowrywise, Carbon).
        3. **Transparent**: Clearly state: "Your money is locked for X months" or "You can get it back easily".

        Response Template:
        1. **Top Pick**: The best safe option for them (e.g. "90-day T-Bill").
        2. **Why It Works**: One sentence explanation.
        3. **Where to Get It**: "Log in to GTBank Mobile App > Investments".
        4. **Trade-off**: "You can't touch the money for 90 days."
        """
        
        agent_executor = create_react_agent(self.llm, self.mcp_tools, prompt=system_msg)
        result = await agent_executor.ainvoke({"messages": state["messages"]})
        return {"messages": [result["messages"][-1]]}

    async def _budgeting_node(self, state):
        """Node: Budgeting & Cashflow."""
        profile = state.get("user_profile", {})
        
        system_msg = f"""
        You are a Personal Finance Coach (Friendly, Non-Technical, and Practical).
        
        Your Mission: Help the user manage their money better in plain English.
        - Focus on: Simple budgets, tracking spending, cutting waste, and building savings habits.
        - Tone: Encouraging, ultra-simple, no financial jargon. Explain like I'm 5.
        
        User Profile: {json.dumps(profile)}

        SCOPE ENFORCEMENT GRID:
        - [ALLOWED]: Budgeting, Expense Tracking, Debt, Savings Habits, Emergency Funds.
        - [PROHIBITED]: Investing (Stocks, T-Bills) -> Send to Investment Chat.
        - [PROHIBITED]: General Knowledge (e.g. "What is photosynthesis?", "Who won the World Cup?").
        
        If the user asks a PROHIBITED question:
        - Politely decline: "I strictly handle budgeting and savings habits. I do not answer general questions."
        - Do NOT answer the question.

        Your Advice Must Be:
        1. **Simple**: Avoid terms like "asset allocation" or "fixed income". Say "savings" instead.
        2. **Specific**: Recommend actual apps or banks in Nigeria (e.g. PiggyVest, Cowrywise, Opay, Kuda, GTBank, ALAT, etc.). Use search tools to verify current rates or features if needed.
        3. **Actionable**: Give a clear step they can do on their phone right now.

        STRICT RULE:
        - Do NOT give complex investment advice (e.g. stock analysis, bond yields). Send them to the Investment Chat for that.
        - However, you CAN suggest simple savings products on apps (e.g. "Use PiggyVest Safelock" or "Open a Kuda savings plan") as part of building a habit.

        Response Structure:
        - **Friendly Advice**: Your main tip in simple language.
        - **Recommended Tool**: A specific app or bank to use for this (e.g. PiggyVest).
        - **One Small Step**: A tiny action for today (e.g. "Download PiggyVest and save N1000").
        """
        
        agent_executor = create_react_agent(self.llm, self.mcp_tools, prompt=system_msg)
        result = await agent_executor.ainvoke({"messages": state["messages"]})
        return {"messages": [result["messages"][-1]]}
        
    def _route_onboarding(self, state):
        """Decides whether to start onboarding or proceed."""
        if state.get("derived_profile"):
            return "ready"
        ob_state = state.get("onboarding_state", {})
        if ob_state.get("complete"):
             return "ready"
        return "onboarding"

    def _check_onboarding_complete(self, state):
        ob_state = state.get("onboarding_state", {})
        if ob_state.get("complete"):
            return "complete"
        return "end_onboarding" 

    def _route_intent(self, state):
        """Routes based on intent detected by Orchestrator."""
        intent = state.get("intent", "general")
        return intent
        
    # --- NODE IMPLEMENTATIONS ---

    async def _sentiment_node(self, state: AgentState):
        """Node: Gathers market sentiment."""
        news_tools = [t for t in self.mcp_tools if "news" in t.name.lower() or "social" in t.name.lower()]
        if not news_tools:
            news_tools = self.mcp_tools 
        agent_executor = create_sentiment_agent(self.llm, news_tools)
        result = await agent_executor.ainvoke({"messages": state["messages"]})
        last_msg = result["messages"][-1]
        
        # Convert AIMessage to HumanMessage for the next agent to see it as input "context"
        # rather than a previous AI response, to avoid Gemini 400 (two AI msgs in a row or ending in AI for generation)
        sentiment_context = HumanMessage(content=f"MARKET SENTIMENT REPORT:\n{last_msg.content}")
        return {"messages": [sentiment_context]}

    async def _analyst_node(self, state: AgentState):
        """Node: The main investment agent (Proponent)."""
        profile = state.get("user_profile", {})
        system_msg = (
            "You are a Trading Analyst who speaks plain English.\n"
            "Your job is to explain stock/ETF opportunities simply to a beginner/intermediate user.\n"
            "You only provide advice related to:\n"
            "- Public equities (Stocks like MTN, Airtel, Dangote)\n"
            "- ETFs\n"
            f"User Profile: {json.dumps(profile)}\n"
            "SCOPE ENFORCEMENT GRID:\n"
            "- [ALLOWED]: Stocks, ETFs, Trading Apps, Market Analysis.\n"
            "- [PROHIBITED]: General Knowledge (e.g. 'Photosynthesis', 'Sports'), Politics, Religion.\n"
            "- If the user asks a prohibited question, politely decline: 'I only discuss stocks and trading.'\n"
            "Guidelines:\n"
            "1. **Explain Why**: Don't just say 'Buy MTNN'. Say 'Buy MTNN because their profit grew by 20%'.\n"
            "2. **Jargon-Free**: If you use a term like 'P/E Ratio', explain it immediately (e.g. 'Price vs Earnings - how expensive the stock is').\n"
            "3. **Apps to Use**: Recommend specific trading apps operating in Nigeria (e.g. Bamboo, Chaka, Trove, Stanbic IBTC Stockbrokers) for execution.\n"
            "4. **Risks**: Always say 'Prices can go down' in a simple way.\n"
            "Steps:\n"
            "1. Review Sentiment Report.\n"
            "2. Use tools to get data.\n"
            "3. Propose a clear trade ideas with an app recommendation.\n"
            "4. Cite data sources.\n"
        )
        
        agent_executor = create_react_agent(self.llm, self.mcp_tools, prompt=system_msg)
        result = await agent_executor.ainvoke({"messages": state["messages"]})
        # Note: In a real implementation, we would extract structured portfolio data here
        # For now, we will assume the LLM might output JSON if prompted, or we extract it via a tool usage
        return {"messages": [result["messages"][-1]]}

    def _red_team_node(self, state: AgentState):
        """Node: The Skeptic."""
        return red_team_node(state, self.llm)

    def _judge_node(self, state: AgentState):
        """Node: The Final Decision Maker. Generates final recommendation."""
        # We need to enhance the Judge to output a structured portfolio if possible
        # For now, we rely on the existing judge prompt but will add extraction logic in persist_node
        res = judge_node(state, self.llm)
        return res

    def _persist_portfolio_node(self, state: AgentState):
        """Node: Persists the recommended portfolio to the database."""
        # 1. Extract Portfolio from the last message (Naive extraction for now)
        # Ideally, the Judge node calls a 'save_portfolio' tool or outputs strict JSON.
        # We will iterate to improve this. For now, we save the text.
        last_msg = state["messages"][-1].content
        
        # 2. Save to DB
        try:
            user_id = int(state["thread_id"])
            db = next(get_db())
            try:
                # Create a placeholder structure since we don't have strict JSON yet
                # In future: parse JSON from LLM output
                portfolio_data = [{"asset": "Recommended_Action", "details": last_msg[:100]}] 
                
                rec = PortfolioRecommendation(
                    user_id=user_id,
                    portfolio=json.dumps(portfolio_data),
                    risk_level=state.get("user_profile", {}).get("risk_profile", "unknown")
                )
                db.add(rec)
                db.commit()
            except Exception as e:
                print(f"Error persisting portfolio: {e}")
            finally:
                db.close()
        except:
             pass
             
        return state

    async def generate_greeting(self, thread_id: str) -> str:
        """
        Generates a proactive greeting based on the user's profile.
        Uses the Banking Consultant persona.
        """
        # Fetch Profile & Username
        state_snapshot = {"thread_id": thread_id}
        profile_data = self._fetch_user_profile(state_snapshot)
        user_profile = profile_data.get("user_profile", {})
        
        username = "User"
        try:
            db = next(get_db())
            user = db.query(User).filter(User.id == int(thread_id)).first()
            if user:
                username = user.username
        except:
            pass
        finally:
            db.close()
        
        system_prompt = f"""You are a helpful Financial Assistant acting as a Senior Banking Consultant.
        
        User: Name: {username}, Profile: {json.dumps(user_profile)}
        
        Mission: Greet the user and give ONE concrete, actionable banking/investment opportunity (e.g. T-Bills, Savings) available RIGHT NOW.
        Use tools to find rates.
        
        Structure:
        1. Warm Greeting.
        2. The Opportunity (Rate/Product).
        3. The Benefit.
        4. Closing.
        """
        
        try:
            greeting_agent = create_react_agent(self.llm, self.mcp_tools, prompt=system_prompt)
            result = await greeting_agent.ainvoke({"messages": [HumanMessage(content="Find the best opportunity and greet me.")]})
            return result["messages"][-1].content
        except Exception as e:
            return f"Hello {username}! I'm Finance Buddy. How can I help you grow your money today?"

    async def chat(self, user_input: str, thread_id: str = "1", intent: str = None):
        """
        Run the graph for the given user input.
        """
        tid = thread_id if thread_id else self.thread_id
        config = {"configurable": {"thread_id": tid}}
        final_response = "No response generated."
        
        input_state = {"messages": [HumanMessage(content=user_input)], "thread_id": tid}
        if intent:
            input_state["intent"] = intent
        
        async for event in self.graph.astream(input_state, config=config):
            for node, content in event.items():
                 if "messages" in content and content["messages"]:
                     msg = content["messages"][-1]
                     final_response = msg.content
        
        return final_response
