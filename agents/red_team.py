
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

def red_team_node(state, llm):
    """
    The Red Team agent critiques the previous analysis.
    It plays the role of a risk manager/skeptic.
    """
    messages = state["messages"]
    
    last_message = messages[-1]
    
    # Check if last_message is dict
    if isinstance(last_message, dict):
        last_msg_content = last_message.get("content", "")
    else:
        last_msg_content = getattr(last_message, "content", "")
    
    prompt = """
    You are the "Red Team" Skeptic. Your job is to find flaws in the previous investment analysis.
    - Highlight risks (market, regulatory, company-specific).
    - Question assumptions made by the proponent.
    - Be critical but constructive.
    - If the analysis is sound, acknowledge it but still point out potential downsides.
    """
    
    response = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=last_msg_content)])
    
    # We append the Red Team's critique to the history
    # We prefix it to make it clear who spoke
    return {"messages": [HumanMessage(content=f"**RED TEAM CRITIQUE:**\n{response.content}")]}
