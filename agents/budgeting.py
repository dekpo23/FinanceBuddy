from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def budgeting_node(state, llm):
    """
    Handles queries about Budgeting, Debt, and Expense Management.
    """
    messages = state["messages"]
    msg = messages[-1]
    last_msg = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
    
    # Simple advice logic without external tools for now
    system_prompt = """You are a Budgeting & Debt Expert.
    Propvide practical, empathy-driven advice on managing personal finances in Nigeria.
    
    Focus on:
    1. The 50/30/20 Rule.
    2. Debt Snowball vs Avalanche methods.
    3. Practical tips for cutting costs in the current economy (e.g., bulk buying, energy saving).
    4. Keep answers short and encouraging.
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
        return {"messages": [AIMessage(content=f"Error in budgeting advice: {e}")]}
