
import yfinance as yf

def check_insider():
    try:
        ticker = yf.Ticker("AAPL")
        print("--- Insider Transactions ---")
        print(ticker.insider_transactions.head() if ticker.insider_transactions is not None else "No data")
        print("\n--- Insider Purchases ---")
        print(ticker.insider_purchases.head() if ticker.insider_purchases is not None else "No data")
        print("\n--- Insider Roster Holders ---")
        print(ticker.major_holders.head() if ticker.major_holders is not None else "No major holders")
        print(ticker.institutional_holders.head() if ticker.institutional_holders is not None else "No institutional holders")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_insider()
