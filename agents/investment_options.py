import os
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def load_knowledge_base():
    """Loads the scraped markdown files into a single context string."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    
    knowledge = ""
    try:
        with open(os.path.join(data_dir, "finance_knowledge.md"), "r", encoding="utf-8") as f:
            knowledge += f.read() + "\n\n"
        with open(os.path.join(data_dir, "platforms.md"), "r", encoding="utf-8") as f:
            knowledge += f.read() + "\n\n"
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        return "Knowledge base unavailable."
        
    return knowledge

def investment_options_node(state, llm):
    """
    Handles queries about Savings, Fixed Income, Bonds, ETFs.
    Uses the local data/ knowledge base.
    """
    messages = state["messages"]
    msg = messages[-1]
    last_msg = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
    
    profile = state.get("user_profile", {})
    profile_str = f"User Profile: Age {profile.get('age')}, Risk {profile.get('risk')}, Capital {profile.get('capital')}, Goal {profile.get('horizon')} years."

    # Load context (for production, use vector search. For now, full context fits in context window)
    context = load_knowledge_base()
    
    system_prompt = f"""You are an Investment Options Specialist for Nigeria.
    Use the provided Knowledge Base to answer the user's question.
    
    {profile_str}
    
    Rules:
    1. PRIORITIZE Nigerian options first (T-Bills, High Yield Savings, local Mutual Funds).
    2. Suggest Global options (ETFs, Dollar Funds) only if relevant or asked.
    3. QUOTE specific rates or platforms from the Knowledge Base (e.g., "Bamboo charges 1.5%").
    4. MENTION user sentiment if found in the text (e.g., "Some users report delays with X").
    5. Be concise and actionable.
    
    Knowledge Base:
    {context[:30000]} # Truncate if too huge, but usually fine for text files
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        response = chain.invoke({"input": last_msg})
        return {"messages": [AIMessage(content=response)]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Error processing investment advice: {e}")]}
