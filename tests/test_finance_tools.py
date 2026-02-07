
import sys
import os
# import pytest (removed)
from unittest.mock import MagicMock, patch

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from finance_server import _get_technical_indicators, _get_market_news, _get_insider_activity

def test_get_technical_indicators():
    # We can mock yf.download to return a sample DF
    with patch('finance_server.yf.download') as mock_download:
        import pandas as pd
        import numpy as np
        
        # Create a dummy dataframe with enough data for technicals
        dates = pd.date_range(start='2023-01-01', periods=300)
        data = {'Close': np.random.rand(300) * 100}
        df = pd.DataFrame(data, index=dates)
        mock_download.return_value = df
        
        result = _get_technical_indicators("AAPL")
        print("Technical Indicators Result:\n", result)
        assert "Technical Analysis for AAPL" in result
        assert "RSI" in result
        assert "MACD" in result

def test_get_market_news():
    with patch('finance_server.TavilyClient') as mock_tavily:
        mock_client = MagicMock()
        mock_tavily.return_value = mock_client
        mock_client.search.return_value = {
            'results': [
                {'title': 'Test News', 'url': 'http://test.com', 'content': 'This is a test news content.'}
            ]
        }
        
        result = _get_market_news("AAPL")
        print("Market News Result:\n", result)
        assert "Recent News for AAPL" in result
        assert "Test News" in result

def test_get_insider_activity():
    with patch('finance_server.yf.Ticker') as mock_ticker:
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        
        # Mock insider transactions
        import pandas as pd
        data = {
            'Start Date': ['2023-01-01'], 
            'Insider': ['Cook Tim'], 
            'Shares': [1000],
            'Text': ['Sale at $150'],
            'URL': ['']
        }
        mock_instance.insider_transactions = pd.DataFrame(data)
        
        # Mock major holders
        mock_instance.major_holders = pd.DataFrame({'0': ['50%'], '1': ['Insiders']})
        
        result = _get_insider_activity("AAPL")
        print("Insider Activity Result:\n", result)
        assert "Insider Activity for AAPL" in result
        assert "Cook Tim" in result

if __name__ == "__main__":
    # Manually running functions for quick check if pytest not available
    try:
        test_get_technical_indicators()
        test_get_market_news()
        test_get_insider_activity()
        print("All tests passed!")
    except Exception as e:
        print(f"Tests failed: {e}")
