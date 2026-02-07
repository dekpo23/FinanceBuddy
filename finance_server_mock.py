from fastmcp import FastMCP
import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, risk_models, expected_returns
import yfinance as yf
import os
import json
import datetime
from typing import Dict, Any

# 1. Initialize MCP Server
mcp = FastMCP("InstitutionalBrain")

# Constants
PORTFOLIO_FILE = "portfolio.json"

def _load_portfolio() -> Dict[str, Any]:
    if not os.path.exists(PORTFOLIO_FILE):
        return {"cash": 100000.0, "positions": {}}
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"cash": 100000.0, "positions": {}}

def _save_portfolio(portfolio: Dict[str, Any]):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=4)

def _get_current_price(ticker: str) -> float:
    try:
        # Use fast fetch
        ticker_obj = yf.Ticker(ticker)
        # Try to get fast info first, fallback to history
        price = None
        if hasattr(ticker_obj, 'fast_info'):
             price = ticker_obj.fast_info.last_price
        
        if not price:
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]
                
        return price if price else 0.0
    except:
        return 0.0

# --- RESOURCES ---
@mcp.resource("market://status")
def market_status() -> str:
    """Returns the current market status (Open/Closed) and next open/close times."""
    now = datetime.datetime.now()
    # Simple Mock: Open 9:30-16:00 Mon-Fri
    is_weekday = now.weekday() < 5
    start_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    end_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    is_open = is_weekday and (start_time <= now <= end_time)
    status = "OPEN" if is_open else "CLOSED"
    return f"Market Status: {status} (Simulated based on local time)"

# --- TOOLS ---

@mcp.tool()
def optimize_portfolio(tickers: list[str], risk_appetite: float = 1.0, asset_class: str = "equity") -> str:
    """
    Calculates optimal portfolio weights.
    risk_appetite: 0.1 (Conservative) to 2.0 (Aggressive).
    asset_class: "equity", "crypto", or "mixed".
    """
    try:
        # 1. Download Adjusted Close prices for the last 3 years
        data = yf.download(tickers, period="3y", interval="1d", auto_adjust=True)
        # Handle multi-column dataframe vs series
        if 'Close' in data.columns:
            data = data['Close']
        
        if data.empty:
            return "Error: No data found for the provided tickers."

        # 2. Calculate Mean Historical Return and Covariance Matrix
        mu = expected_returns.mean_historical_return(data)
        S = risk_models.CovarianceShrinkage(data).ledoit_wolf()
        
        # 3. Optimize for Maximum Sharpe Ratio
        ef = EfficientFrontier(mu, S)
        
        # Adjust risk-free rate based on appetite
        risk_free_rate = 0.05 / (risk_appetite if risk_appetite > 0 else 0.1) 
        weights = ef.max_sharpe(risk_free_rate=risk_free_rate)
        
        cleaned_weights = ef.clean_weights()
        
        return f"Optimization Results ({asset_class}): {dict(cleaned_weights)}"

    except Exception as e:
        return f"An error occurred during optimization: {str(e)}"

@mcp.tool()
def execute_trade(symbol: str, qty: float, side: str, asset_type: str = "stock") -> str:
    """
    Executes a market order (Mock).
    side: "buy" or "sell"
    """
    try:
        portfolio = _load_portfolio()
        cash = portfolio.get("cash", 100000.0)
        positions = portfolio.get("positions", {})
        
        price = _get_current_price(symbol)
        if price <= 0:
            return f"Error: Could not fetch price for {symbol}"
            
        value = price * qty
        
        if side.lower() == "buy":
            if cash < value:
                return f"Insufficient funds. Req: ${value:.2f}, Avail: ${cash:.2f}"
            
            cash -= value
            current_qty = positions.get(symbol, 0)
            positions[symbol] = current_qty + qty
            
        elif side.lower() == "sell":
            current_qty = positions.get(symbol, 0)
            if current_qty < qty:
                return f"Insufficient shares. Req: {qty}, Avail: {current_qty}"
                
            cash += value
            positions[symbol] = current_qty - qty
            if positions[symbol] <= 0:
                del positions[symbol]
                
        portfolio["cash"] = cash
        portfolio["positions"] = positions
        _save_portfolio(portfolio)
        
        return f"Trade Executed (MOCK): {side.upper()} {qty} {symbol} @ ${price:.2f}. Remaining Cash: ${cash:.2f}"

    except Exception as e:
        return f"Trade Execution Failed: {str(e)}"

@mcp.tool()
def get_portfolio() -> str:
    """
    Retrieves current positions from local mock portfolio.
    """
    try:
        portfolio = _load_portfolio()
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0.0)
        
        if not positions:
            return f"Portfolio is currently empty. Cash: ${cash:.2f}"
            
        summary = [f"Cash: ${cash:.2f}"]
        
        for symbol, qty in positions.items():
            price = _get_current_price(symbol)
            value = price * qty
            summary.append(f"{symbol}: {qty} shares @ ${price:.2f} (Value: ${value:.2f})")
            
        return "Current Portfolio:\n" + "\n".join(summary)

    except Exception as e:
        return f"Failed to fetch portfolio: {str(e)}"

@mcp.tool()
def get_market_status() -> str:
    """Checks if the market is open."""
    return market_status()

if __name__ == "__main__":
    mcp.run()
