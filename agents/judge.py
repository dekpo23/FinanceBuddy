
from langchain_core.messages import HumanMessage, SystemMessage

def judge_node(state, llm):
    """
    The Judge Agent weighs the Proponent (Analyst) and Skeptic (Red Team).
    Output: Final Recommendation + Confidence Score (0-100%).
    """
    state_messages = state["messages"]
    
    # We provide the entire conversation history to the Judge
    # It sees the Analyst's proposal and the Red Team's critique.
    
    prompt = (
        "You are the 'Chief Investment Officer' (The Judge). "
        "You represent the final decision maker.\n"
        "Your Role:\n"
        "1. Review the initial proposal (Analyst).\n"
        "2. Review the critique (Red Team/Skeptic).\n"
        "3. Decide whether to proceed with the trade or not.\n"
        "4. Assign a Confidence Score (0-100%).\n"
        "5. Summarize the key reasons for your decision.\n"
        "Be decisive. If the risks are too high, reject the trade."
    )
    
    response = llm.invoke([SystemMessage(content=prompt)] + state_messages)
    
    return {"messages": [HumanMessage(content=f"**CIO DECISION:**\n{response.content}")]}
