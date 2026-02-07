from fastmcp import FastMCP
from tavily import TavilyClient
import os

# Initialize FastMCP
mcp = FastMCP("TavilySearch")

# Initialize Tavily Client
# Logic: use env var, default to empty to prevent crash (runtime error is better than startup crash)
tavily_api_key = os.getenv("TAVILY_API_KEY") 
tavily_client = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None

@mcp.tool()
def web_search(query: str) -> str:
    """
    Performs a web search using Tavily.
    Returns a summary of search results.
    """
    if not tavily_client:
        return "Error: TAVILY_API_KEY is missing."

    try:
        response = tavily_client.search(query=query, search_depth="basic")
        results = response.get("results", [])
        
        if not results:
            return "No results found."
            
        formatted = []
        for i, res in enumerate(results[:5]):
            formatted.append(f"{i+1}. {res.get('title', 'No Title')}\n   {res.get('content', '')[:200]}...\n   Source: {res.get('url', '')}")
            
        return "\n\n".join(formatted)
        
    except Exception as e:
        return f"Search failed: {str(e)}"

if __name__ == "__main__":
    mcp.run()
