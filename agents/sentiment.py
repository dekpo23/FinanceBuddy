
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

def create_sentiment_agent(llm, tools):
    """
    Creates an agent dedicated to gathering and analyzing market sentiment.
    It has access to news tools.
    """
    
    system_message = (
        "You are a Market Sentiment Analyst. Your job is to:\n"
        "1. Search for the latest news on the target stock/asset.\n"
        "2. Identify the prevailing market mood (Bullish/Bearish/Neutral).\n"
        "3. Highlight key narratives driving the price.\n"
        "4. Output a brief 'Sentiment Report'.\n"
        "Use the 'get_market_news' tool actively."
    )
    
    # Filter tools to only include relevant ones (news)
    # Assuming tools list is passed, we filter by name if possible, or just give all.
    # For simplicity, we give all, or assume the caller filters.
    # Actually, let's just use all for now as the prompt restricts behavior.
    
    return create_react_agent(llm, tools, state_modifier=system_message)
