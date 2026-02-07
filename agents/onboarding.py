import json
import os
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Load Questions Resource
def load_questions(filename):
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to root, then into resources
        resources_dir = os.path.join(os.path.dirname(base_dir), "resources") 
        filepath = os.path.join(resources_dir, filename)
        
        with open(filepath, "r") as f:
            data = json.load(f)
            return data.get("questions", [])
    except Exception as e:
        print(f"Error loading questions from {filename}: {e}")
        return []

def get_trading_onboarding_questions():
    """Returns onboarding questions customized for active traders."""
    return load_questions("trading_onboarding_questions.json")

def get_conservative_onboarding_questions():
    """Returns onboarding questions customized for conservative investors."""
    return load_questions("conservative_onboarding_questions.json")

def get_onboarding_questions():
    """Returns the default/general onboarding questions."""
    return load_questions("financial_onboarding_questions.json")

def onboarding_node(state):
    """
    Manages the onboarding flow.
    - Checks current question index.
    - If answer provided in last message, saves it.
    - Selects next question.
    - If all done, sets 'onboarding_complete' flag.
    """
    questions = get_onboarding_questions()
    total_questions = len(questions)
    
    # State initialization (if not present)
    # in LangGraph, we'd usually rely on the reducer, but here we read from 'onboarding_state' key
    onboarding_state = state.get("onboarding_state", {"current_index": 0, "answers": {}, "complete": False})
    
    current_index = onboarding_state.get("current_index", 0)
    answers = onboarding_state.get("answers", {})
    
    # Check if we are receiving an answer to a previous question
    # If the last message was from the user AND we are active (not start)
    last_msg = state["messages"][-1] if state["messages"] else None
    
    
    if last_msg:
        # Handle case where message is a dict (serialized) or an object
        msg_type = getattr(last_msg, "type", None) or last_msg.get("type")
        msg_content = getattr(last_msg, "content", None) or last_msg.get("content")
        
        if msg_type == "human" and current_index < total_questions:
            # Save answer for the *current* question (before incrementing)
            q_id = questions[current_index]["id"]
            answers[q_id] = msg_content
        
        # Advance index
        current_index += 1
        onboarding_state["current_index"] = current_index
        onboarding_state["answers"] = answers

    # Check if we are done
    if current_index >= total_questions:
        onboarding_state["complete"] = True
        return {
            "onboarding_state": onboarding_state,
            "messages": [AIMessage(content="Thank you! I'm analyzing your profile now...")]
        }

    # Ask the Next Question
    next_q = questions[current_index]
    
    # Format options if available
    options_text = ""
    if "options" in next_q:
        options_text = "\nOptions:\n" + "\n".join([f"- {opt}" for opt in next_q["options"]])
    
    question_text = f"{next_q['text']}{options_text}"
    
    return {
        "onboarding_state": onboarding_state,
        "messages": [AIMessage(content=question_text)]
    }

def profiler_node(state, llm):
    """
    Analyzes the user's onboarding answers and generates a financial profile.
    """
    # 1. Extract answers from state
    # Ensure we look in 'onboarding_state' where we stored them
    onboard_data = state.get("onboarding_state", {})
    answers = onboard_data.get("answers", {})
    
    if not answers:
        return {"derived_profile": {"error": "No answers provided"}}

    # 2. Construct Prompt
    # Note: We use double curly braces {{ }} to escape them in f-strings or LangChain templates
    system_prompt = """You are an expert Financial Profiler. 
    Analyze the user's answers to the onboarding questionnaire and derive a structured financial profile.
    
    Output Format (JSON):
    {{
        "risk_score": 1-10 (1=Safe, 10=Aggressive),
        "investment_style": "Passive" | "Active" | "Balanced",
        "time_horizon": "Short" | "Medium" | "Long",
        "primary_goal": "Growth" | "Income" | "Preservation",
        "recommended_asset_allocation": {{
            "stocks": "X%",
            "bonds": "Y%",
            "crypto": "Z%",
            "cash": "W%",
            "real_estate": "V%"
        }},
        "notes": "Brief observation about the user."
    }}
    """
    
    user_msg = f"User Answers: {json.dumps(answers, indent=2)}"
    
    # 3. Invoke LLM
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    
    try:
        profile = chain.invoke({"input": user_msg})
        return {"derived_profile": profile}
    except Exception as e:
        return {"derived_profile": {"error": str(e)}}
