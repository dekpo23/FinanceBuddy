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
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.orm import Session
from database import get_db
from models import User, Onboarding
from langchain_core.messages import SystemMessage, HumanMessage

# Import New Agent Logic
from agents.red_team import red_team_node
from agents.judge import judge_node
from agents.sentiment import create_sentiment_agent
from agents.onboarding import onboarding_node, profiler_node
from agents.orchestrator import orchestrator_node
from agents.investment_options import investment_options_node
from agents.budgeting import budgeting_node

# Force reload environment variables to ensure they are picked up
load_dotenv(find_dotenv(), override=True)

# Debug: Check if key is loaded
if not os.getenv("TAVILY_API_KEY"):
    print("WARNING: TAVILY_API_KEY not found in environment variables. Web search tools may fail.")

# Define the State
class AgentState(TypedDict):
    messages: List[dict]
    user_profile: dict
    thread_id: str
    onboarding_state: dict # keys: current_index, answers, complete
    derived_profile: dict # Result from profiler
    intent: str # trading, investment_options, budgeting, general

class InvestmentChatbot:
    def __init__(self, thread_id: str = "investor_demo_001"):
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        self.thread_id = thread_id
        
        # Database Connection String for LangGraph Checkpointer
        self.db_url = f"postgresql://{os.getenv('db_user')}:{os.getenv('db_password')}@{os.getenv('db_host')}:{os.getenv('db_port')}/{os.getenv('db_name')}"
        
        # Resolve absolute paths to ensure servers are found regardless of CWD
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.mcp_config = {
            "social": {
                "command": sys.executable,
                "args": [os.path.join(base_dir, "SocialIntelligence_server.py")],
                "transport": "stdio",
                "env": {"FASTMCP_DISABLE_BANNER": "1", **os.environ} 
            },
            # "institutional" server removed temporarily or updated if needed, 
            # assuming finance_server.py is still the target but we might need to be careful with tools
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
            return {"user_profile": {"age": 30, "risk": "Medium", "capital": 10000, "horizon": 5}}

        db = next(get_db())
        try:
            # Check for Onboarding Record
            # We prefer the derived profile if available (this comment line is fine)
            onboarding_rec = db.query(Onboarding).filter(Onboarding.user_id == user_id).first()
            if onboarding_rec and onboarding_rec.derived_profile:
                # If we have a full profile, parse and return it
                try:
                    profile_data = json.loads(onboarding_rec.derived_profile)
                    # Add flag to indicate we are ready
                    profile_data["needs_onboarding"] = False
                    return {"derived_profile": profile_data, "user_profile": profile_data}
                except:
                   pass # Fallback if JSON parse fails
            
            # If no full profile, fetch basic user info (age)
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
        # 1. Persistence Layer
        self.pool = AsyncConnectionPool(conninfo=self.db_url, max_size=10, open=False)
        await self.pool.open()
        
        # Run setup with autocommit to allow CREATE INDEX CONCURRENTLY
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
        workflow.add_node("general_chat", self._general_node)
        workflow.add_node("investment_options", self._investment_node_wrapper)
        workflow.add_node("budgeting", self._budgeting_node_wrapper)
        
        # Trading Branch (Existing flow)
        workflow.add_node("sentiment_analysis", self._sentiment_node)
        workflow.add_node("analyst_proponent", self._analyst_node)
        workflow.add_node("red_team_skeptic", self._red_team_node)
        workflow.add_node("chief_investment_officer", self._judge_node)

        # --- EDGES ---
        # 1. Entry & Onboarding
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
        # workflow.add_edge("fetch_profile", "orchestrator") # Removed direct edge, now conditional
        
        workflow.add_conditional_edges(
            "orchestrator",
            self._route_intent,
            {
                "trading": "sentiment_analysis",
                "investment_options": "investment_options",
                "budgeting": "budgeting",
                "general": "general_chat"
            }
        )

        # 3. Branch Flows
        # Trading Flow
        workflow.add_edge("sentiment_analysis", "analyst_proponent")
        workflow.add_edge("analyst_proponent", "red_team_skeptic")
        workflow.add_edge("red_team_skeptic", "chief_investment_officer")
        workflow.add_edge("chief_investment_officer", END)
        
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
                # Check for existing record
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

    def _investment_node_wrapper(self, state):
        return investment_options_node(state, self.llm)

    def _budgeting_node_wrapper(self, state):
        return budgeting_node(state, self.llm)
        
    def _general_node(self, state):
        """Simple general chatbot for non-financial queries."""
        msg = state["messages"][-1]
        response = self.llm.invoke([
            SystemMessage(content="You are a helpful Financial Assistant. Structure your answers clearly."),
            msg
        ])
        return {"messages": [response]}

    def _route_onboarding(self, state):
        """Decides whether to start onboarding or proceed."""
        # If 'derived_profile' exists in state, we are done.
        if state.get("derived_profile"):
            return "ready"
            
        # Check internal flag
        ob_state = state.get("onboarding_state", {})
        if ob_state.get("complete"):
             return "ready"
             
        # Else start/continue onboarding
        return "onboarding"

    def _check_onboarding_complete(self, state):
        ob_state = state.get("onboarding_state", {})
        if ob_state.get("complete"):
            return "complete"
        return "end_onboarding" # Signal to end the run (wait for user)

    def _route_intent(self, state):
        """Routes based on intent detected by Orchestrator."""
        intent = state.get("intent", "general")
        return intent
        
    # --- NODE IMPLEMENTATIONS ---

    def _sentiment_node(self, state: AgentState):
        """Node: Gathers market sentiment."""
        # We use a dedicated sentiment agent
        # Filter tools to only include 'get_market_news' ideally, but letting it pick is fine for now
        # Or better yet, we specifically give it only news tools if we can filter self.mcp_tools
        
        # Simple string matching for tools
        news_tools = [t for t in self.mcp_tools if "news" in t.name.lower() or "social" in t.name.lower()]
        if not news_tools:
            news_tools = self.mcp_tools # Fallback
            
        agent_executor = create_sentiment_agent(self.llm, news_tools)
        
        # We invoke it with the latest user query
        # But we need to ensure it knows WHAT to search for.
        # The user's query is in messages[-1]
        
        result = agent_executor.invoke({"messages": state["messages"]})
        
        # We format the result to clearly indicate it's a sentiment report
        last_msg = result["messages"][-1]
        return {"messages": [last_msg]}

    def _analyst_node(self, state: AgentState):
        """Node: The main investment agent (Proponent)."""
        # Dynamic System Message based on Profile
        profile = state.get("user_profile", {})
        system_msg = (
            "You are an expert Investment Analyst (The Proponent). "
            "Your goal is to propose a high-conviction trade idea based on data.\n"
            f"User Profile: Age {profile.get('age')}, Risk {profile.get('risk')}, "
            f"Capital ${profile.get('capital')}, Horizon {profile.get('horizon')} years.\n"
            "Steps:\n"
            "1. Review the Sentiment Report provided previously.\n"
            "2. Use 'get_technical_indicators' to validate price action.\n"
            "3. Use 'get_insider_activity' to check for conviction.\n"
            "4. Propose a specific trade with Entry, Stop Loss, and Take Profit targets.\n"
            "5. Cite your sources (Technicals + Sentiment + Insider).\n"
            "DO NOT attempt to execute the trade. Just propose it for the user."
        )
        
        # Include all tools for the analyst
        agent_executor = create_react_agent(self.llm, self.mcp_tools, state_modifier=system_msg)
        result = agent_executor.invoke({"messages": state["messages"]})
        return {"messages": [result["messages"][-1]]}

    def _red_team_node(self, state: AgentState):
        """Node: The Skeptic."""
        # Use the imported function, passing our LLM
        return red_team_node(state, self.llm)

    def _judge_node(self, state: AgentState):
        """Node: The Final Decision Maker."""
        # Use the imported function, passing our LLM
        return judge_node(state, self.llm)

    async def generate_greeting(self, thread_id: str) -> str:
        """
        Generates a proactive greeting based on the user's profile.
        """
        
        # 1. Fetch Profile & Username
        state_snapshot = {"thread_id": thread_id}
        profile_data = self._fetch_user_profile(state_snapshot)
        user_profile = profile_data.get("user_profile", {})
        
        # Fetch Username directly for personalization
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
        
        # 2. Construct Prompt (Agentic & Simple)
        system_prompt = f"""You are 'Finance Buddy', a practical and helpful financial assistant.
        
        User:
        Name: {username}
        Profile: {json.dumps(user_profile, indent=2)}
        
        Your Mission:
        Greet the user by name and give them ONE concrete, actionable financial tip or opportunity available RIGHT NOW that fits their profile.
        
        The user has little financial knowledge. Explain things simply (like you're talking to a friend).
        Focus on: "What do I stand to gain?" vs "What are the risks?".
        
        CRITICAL INSTRUCTION:
        You MUST use your tools (like search/news) to find REAL-TIME data before answering.
        - If Conservative: Search for the latest "Treasury Bill rates in Nigeria". Tell them the current % return and which banks/platforms offer it (e.g. GTBank, PiggyVest, Cowrywise).
        - If Aggressive: Search for "top performing stocks NGX this week" or "crypto trends". Mention the potential gain but warn about the risk simply.
        - If Balanced: Search for "Money Market Fund rates Nigeria".
        
        Structure your answer:
        1.  **Warm Greeting**: "Hi {username}!"
        2.  **The Opportunity**: "Did you know you can currently earn around X% interest risk-free with Treasury Bills?" (Use real rate found from tool).
        3.  **The Benefit**: "This means if you save N100k, you could get back N1xxk without doing anything."
        4.  **How to get it**: "Most banks like [Bank Names found] offer this via their app."
        5.  **Closing**: "Want me to show you how to start?"
        
        Keep it practical. No jargon like "yield curve" or "asset allocation". Just "Interest", "Profit", "Safety".
        """
        
        # 3. Invoke Agent (with Tools)
        try:
            # Create a localized agent for this greeting task
            greeting_agent = create_react_agent(self.llm, self.mcp_tools, state_modifier=system_prompt)
            
            # Run the agent
            result = await greeting_agent.ainvoke({"messages": [HumanMessage(content="Find the best opportunity for me right now and greet me.")]})
            return result["messages"][-1].content
            
        except Exception as e:
            print(f"Greeting generation failed: {e}")
            return f"Hello {username}! I'm Finance Buddy. How can I help you grow your money today?"

    async def chat(self, user_input: str, thread_id: str = "1", intent: str = None):
        """
        Run the graph for the given user input.
        thread_id: Optional override for the session ID.
        intent: Optional forced intent (e.g. 'budgeting').
        """
        # Use provided thread_id or fall back to instance default
        tid = thread_id if thread_id else self.thread_id
        config = {"configurable": {"thread_id": tid}}
        
        # Run the graph
        final_response = "No response generated."
        
        # Prepare input state
        input_state = {"messages": [HumanMessage(content=user_input)]}
        if intent:
            input_state["intent"] = intent
        
        async for event in self.graph.astream(
            input_state,
            config=config
        ):
            # We can log events here if needed
            # Or capture intermediate outputs
            for node, content in event.items():
                 if "messages" in content and content["messages"]:
                     msg = content["messages"][-1]
                     # We might want to stream this back to the user, but for now we just return the final one
                     final_response = msg.content
        
        return final_response
