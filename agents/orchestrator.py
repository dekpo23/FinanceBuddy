from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

def orchestrator_node(state, llm):
    """
    Classifies user intent to route to the correct specialist.
    """
    
    # Check if intent is already forced/set
    existing_intent = state.get("intent")
    if existing_intent in ["trading", "investment_options", "budgeting", "general"]:
        return {"intent": existing_intent}

    messages = state["messages"]
    if not messages:
        return {"intent": "general"}
        
    msg = messages[-1]
    if isinstance(msg, dict):
        last_message = msg.get("content", "")
    else:
        last_message = getattr(msg, "content", "")
    
    system_prompt = """You are the Orchestrator for a Financial Assistant "Finance Buddy".
    Analyze the user's input and classify their intent into one of the following categories:
    
    1. "trading": For active stock analysis, company research, market trends, specific trade ideas, or "analyze [ticker]".
    2. "investment_options": For passive investing, savings, fixed income, bonds, ETFs, low-risk options, or general "where should I put my money" questions.
    3. "budgeting": For expense tracking, debt management, budgeting advice, or cash flow optimization.
    4. "general": For greetings, "what can you do?", or non-financial small talk.
    
    Output JSON: {"intent": "category_name"}
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    
    try:
        result = chain.invoke({"input": last_message})
        intent = result.get("intent", "general")
        # Validate intent
        if intent not in ["trading", "investment_options", "budgeting", "general"]:
            intent = "general"
        return {"intent": intent}
    except Exception as e:
        print(f"Orchestrator parsing error: {e}")
        return {"intent": "general"}
