from config import Config
from data_fetcher import DataFetcher
import sys

def test_connection():
    print("Testing Upstox Connection...")
    
    token = Config.ACCESS_TOKEN
    if not token:
        print("❌ No ACCESS_TOKEN found in .env")
        return

    print(f"Token found (first 10 chars): {token[:10]}...")
    
    fetcher = DataFetcher(token)
    
    # Test 1: Get Current Price
    print("\nAttempting to fetch Nifty 50 price...")
    try:
        # Try the key we used in main.py
        key = 'NSE_INDEX|Nifty 50' 
        price = fetcher.get_current_price(key)
        
        if price:
            print(f"✅ Success! Current Nifty 50 Price: {price}")
        else:
            print(f"❌ Failed to fetch price for {key}. Result was None.")
            print("Possible reasons: Invalid Instrument Key, Market Closed (should still show LTP), or Token Expired.")
            
    except Exception as e:
        print(f"❌ Exception during fetch: {e}")

if __name__ == "__main__":
    test_connection()
