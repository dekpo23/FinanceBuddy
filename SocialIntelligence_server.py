import os
from fastmcp import FastMCP
from tavily import TavilyClient
import tavily
import requests

mcp = FastMCP("SocialIntelligence")

@mcp.tool()
def get_market_sentiment(ticker: str) -> str:
    """
    Fetches real-time news sentiment for a ticker using Alpha Vantage.
    Returns the average sentiment score and the top relevant headlines.
    """
    api_key = os.getenv("AV_KEY")
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker.upper()}&apikey={api_key}"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        feed = data.get("feed", [])
        if not feed:
            return f"No recent news found for {ticker.upper()}."

        # Extract sentiment labels and scores
        summaries = []
        scores = []
        
        for article in feed[:3]: # Take the top 3 most relevant articles
            title = article.get("title")
            score = article.get("overall_sentiment_score")
            label = article.get("overall_sentiment_label")
            summaries.append(f"- {title} (Sentiment: {label})")
            scores.append(score)

        # Calculate an average sentiment for the demo
        avg_score = sum(scores) / len(scores) if scores else 0
        final_mood = "Bullish" if avg_score > 0.15 else "Bearish 📉" if avg_score < -0.15 else "Neutral ➡️"

        return (
            f"Market Intelligence for {ticker.upper()}:\n"
            f"Overall Mood: {final_mood} (Avg Score: {avg_score:.2f})\n"
            f"Top Headlines:\n" + "\n".join(summaries)
        )

    except Exception as e:
        return f"Error fetching sentiment: {str(e)}"
    
@mcp.tool()
def get_social_volume_score(ticker: str) -> str:
    """
    Simulates fetching social mention volume. 
    In production, you'd use the LunarCrush or StockTwits API here.
    """
    # High volume often precedes high volatility
    import random
    score = random.randint(1, 100)
    trend = "Increasing" if score > 70 else "Stable"
    return f"Social Hype Score for {ticker}: {score}/100. Trend: {trend}"

if __name__ == "__main__":
    mcp.run()