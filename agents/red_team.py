
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

def red_team_node(state, llm):
    """
    The Red Team agent critiques the previous analysis.
    It plays the role of a risk manager/skeptic.
    """
    messages = state["messages"]
    
    # Check if last_message is dict
    if isinstance(last_message, dict):
        last_msg_content = last_message.get("content", "")
    else:
        last_msg_content = getattr(last_message, "content", "")
    
    response = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=last_msg_content)])
    
    # We append the Red Team's critique to the history
    # We prefix it to make it clear who spoke
    return {"messages": [HumanMessage(content=f"**RED TEAM CRITIQUE:**\n{response.content}")]}
