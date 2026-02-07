# app/agents/finance_server.py
from fastmcp import FastMCP
import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, risk_models, expected_returns
import yfinance as yf
import requests
import os
from tavily import TavilyClient
# Alpaca imports removed

import pandas_ta as ta

# 1. Initialize MCP Server
mcp = FastMCP("InstitutionalBrain")

# --- PROMPTS ---
@mcp.prompt()
def analyze_stock(ticker: str) -> str:
    """Create a prompt to analyze a specific stock ticker."""
    return f"Please analyze {ticker} based on the following criteria:\n1. Latest Price and Trend\n2. Relevant News from the last week\n3. Financial Health (if available)\n4. Buy/Sell/Hold Recommendation based on Risk Profile."

@mcp.tool()
def optimize_portfolio(tickers: list[str], risk_appetite: float = 1.0, asset_class: str = "equity") -> str:
    """
    Calculates optimal portfolio weights.
    risk_appetite: 0.1 (Conservative) to 2.0 (Aggressive).
    asset_class: "equity", "crypto", or "mixed".
    """
    try:
        # Basic validation or asset class expansion could happen here
        # For now, we trust the ticker list provided by the reasoning agent
        
        # 1. Download Adjusted Close prices for the last 3 years
        # Note: For crypto, yfinance tickers usually look like "BTC-USD"
        data = yf.download(tickers, period="3y", interval="1d", auto_adjust=True)['Close']
        
        if data.empty:
            return "Error: No data found for the provided tickers."

        # 2. Calculate Mean Historical Return and Covariance Matrix
        mu = expected_returns.mean_historical_return(data)
        S = risk_models.CovarianceShrinkage(data).ledoit_wolf()
        
        # 3. Optimize for Maximum Sharpe Ratio
        ef = EfficientFrontier(mu, S)
        
        # Adjust risk-free rate based on appetite
        risk_free_rate = 0.05 / risk_appetite 
        weights = ef.max_sharpe(risk_free_rate=risk_free_rate)
        
        cleaned_weights = ef.clean_weights()
        
        return f"Optimization Results ({asset_class}): {dict(cleaned_weights)}"

    except Exception as e:
        return f"An error occurred during optimization: {str(e)}"


# --- LOGIC IMPLEMENTATIONS (Separated for Testing) ---

def _get_technical_indicators(ticker: str, period: str = "1y") -> str:
    try:
        # Download data
        df = yf.download(ticker, period=period, interval="1d", auto_adjust=True)
        if df.empty:
            return f"No data found for {ticker}."
        
        # Ensure single level column index if MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
             df.columns = df.columns.get_level_values(0)

        # Calculate Indicators
        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # MACD
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1) # Append MACD columns
        
        # Bollinger Bands
        bb = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bb], axis=1)

        # SMAs
        df['SMA_50'] = ta.sma(df['Close'], length=50)
        df['SMA_200'] = ta.sma(df['Close'], length=200)

        # Get latest values
        latest = df.iloc[-1]
        
        # Dynamic column lookup
        rsi_col = [c for c in df.columns if c.startswith('RSI')][0]
        macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
        macd_signal_col = [c for c in df.columns if c.startswith('MACDs_')][0]
        macd_hist_col = [c for c in df.columns if c.startswith('MACDh_')][0]
        bbu_col = [c for c in df.columns if c.startswith('BBU_')][0]
        bbl_col = [c for c in df.columns if c.startswith('BBL_')][0]
        
        # Check for Golden/Death Cross in the last 10 days
        recent_sma = df.tail(10)
        crossovers = ""
        if (recent_sma['SMA_50'] > recent_sma['SMA_200']).all():
            crossovers = "Trend: Bullish (SMA 50 > SMA 200)"
        elif (recent_sma['SMA_50'] < recent_sma['SMA_200']).all():
            crossovers = "Trend: Bearish (SMA 50 < SMA 200)"
        else:
             crossovers = "Trend: Recent Crossover Detected (Potential Reversal)"

        summary = f"""
Technical Analysis for {ticker} (Latest):
Price: {latest['Close']:.2f}
RSI (14): {latest[rsi_col]:.2f} (Over 70=Overbought, Under 30=Oversold)
MACD: {latest[macd_col]:.2f} | Signal: {latest[macd_signal_col]:.2f} | Hist: {latest[macd_hist_col]:.2f}
Bollinger Bands: Upper={latest[bbu_col]:.2f}, Lower={latest[bbl_col]:.2f}
SMA 50: {latest['SMA_50']:.2f}
SMA 200: {latest['SMA_200']:.2f}
{crossovers}
"""
        return summary

    except Exception as e:
        cols = df.columns.tolist() if 'df' in locals() else "N/A"
        return f"Error calculating technicals: {str(e)} | Available columns: {cols}"

def _get_market_news(ticker: str, limit: int = 5) -> str:
    try:
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = tavily.search(query=f"latest news about {ticker} stock", topic="news", max_results=limit)
        
        news_items = []
        for result in response['results']:
            news_items.append(f"- [{result['title']}]({result['url']}): {result['content'][:200]}...")
            
        return f"Recent News for {ticker}:\n" + "\n".join(news_items)
    except Exception as e:
        return f"Error fetching news: {str(e)}"

def _get_insider_activity(ticker: str) -> str:
    try:
        stock = yf.Ticker(ticker)
        
        # Insider Transactions
        transactions = stock.insider_transactions
        trans_summary = "No recent insider transactions found."
        if transactions is not None and not transactions.empty:
            # Get last 5 transactions
            recent = transactions.head(5)
            trans_list = []
            for index, row in recent.iterrows():
                # Clean up date if possible, yfinance returns it as index or column depending on version
                # Assuming index is not date, usually 'Start Date' col
                date = row.get('Start Date', 'N/A')
                person = row.get('Insider', 'Unknown')
                shares = row.get('Shares', 0)
                url = row.get('URL', '')
                trans_text = row.get('Text', '')
                trans_list.append(f"- {date}: {person} | {trans_text} | {shares} shares")
            trans_summary = "Recent Insider Transactions:\n" + "\n".join(trans_list)

        # Major Holders
        holders = stock.major_holders
        holders_summary = "No holder data found."
        if holders is not None and not holders.empty:
            # yfinance major_holders formatting varies. 
            # Often it's a dataframe with 0: Value, 1: Breakdown
             holders_summary = "Major Holders:\n" + holders.to_string(index=False, header=False)

        return f"Insider Activity for {ticker}:\n\n{trans_summary}\n\n{holders_summary}"

    except Exception as e:
        return f"Error fetching insider activity: {str(e)}"

# --- MCP TOOLS ---

@mcp.tool()
def get_technical_indicators(ticker: str, period: str = "1y") -> str:
    """Calculates key technical indicators for a given ticker."""
    return _get_technical_indicators(ticker, period)

@mcp.tool()
def get_market_news(ticker: str, limit: int = 5) -> str:
    """Fetches recent news for a ticker using Tavily."""
    return _get_market_news(ticker, limit)

@mcp.tool()
def get_insider_activity(ticker: str) -> str:
    """Fetches insider trading activity and major holders using yfinance."""
    return _get_insider_activity(ticker)

if __name__ == "__main__":
    mcp.run()
