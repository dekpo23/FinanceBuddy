import os
import sys
from tavily import TavilyClient
from dotenv import load_dotenv, find_dotenv

# Load env variables
load_dotenv(find_dotenv(), override=True)

api_key = os.getenv("TAVILY_API_KEY")
if not api_key:
    print("Error: TAVILY_API_KEY not found in .env")
    sys.exit(1)

client = TavilyClient(api_key=api_key)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def scrape_and_save(filename, queries, title):
    print(f"Scraping data for: {title}...")
    content = [f"# {title}\n\nGenerated via Tavily Search\n"]
    
    for query in queries:
        print(f"  - Searching: {query}")
        try:
            # simple search
            response = client.search(query, search_depth="advanced", max_results=5)
            content.append(f"## Query: {query}\n")
            
            for result in response.get("results", []):
                content.append(f"### {result['title']}")
                content.append(f"**Source**: {result['url']}")
                content.append(f"{result['content']}\n")
                
        except Exception as e:
            print(f"    Failed: {e}")
            content.append(f"Error fetching {query}: {e}\n")
            
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(content))
    print(f"Saved to {filepath}\n")

def main():
    # 1. General Investment Options (Nigeria + Global)
    investment_queries = [
        "Current high yield savings rates in Nigeria 2024 2025",
        "Nigerian Treasury Bills rates current yield 2025",
        "Best dollar mutual funds in Nigeria 2025",
        "Performance of S&P 500 ETFs vs Nigerian Stocks 2024",
        "Eurobond yields for Nigerian banks 2025"
    ]
    scrape_and_save("finance_knowledge.md", investment_queries, "Investment Options & Rates")

    # 2. Trading Platforms (Fees, Sentiment, Features)
    platform_queries = [
        "Bamboo vs Chaka vs Trove vs Risevest fees comparison 2025",
        "Bamboo app user reviews trustpilot reddit 2024",
        "Risevest withdrawal issues reddit",
        "Trove finance customer support reviews",
        "How to buy US stocks from Nigeria using Chaka"
    ]
    scrape_and_save("platforms.md", platform_queries, "Trading Platforms Knowledge Base")

if __name__ == "__main__":
    main()
