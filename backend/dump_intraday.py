import pandas as pd
from app.core.config import Config
from app.data.data_fetcher import DataFetcher
import logging

logging.basicConfig(level=logging.INFO)

def dump_intraday_data():
    api_key = Config.API_KEY
    access_token = Config.ACCESS_TOKEN
    fetcher = DataFetcher(api_key, access_token)
    
    print("Fetching Intraday Data (minutes/5)...")
    df_intraday = fetcher.get_intraday_data(Config.SYMBOL_NIFTY_50, '5minute')
    
    if df_intraday is not None and not df_intraday.empty:
        print(f"✅ Success! Found {len(df_intraday)} candles.")
        print("\nFirst 5 Candles:")
        print(df_intraday.head())
        print("\nLast 5 Candles:")
        print(df_intraday.tail())
        
        filename = "intraday_dump.csv"
        df_intraday.to_csv(filename)
        print(f"\nDumped to {filename}")
    else:
        print("❌ Failed: Intraday data is None or empty.")

if __name__ == "__main__":
    dump_intraday_data()
