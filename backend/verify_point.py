import pandas as pd
import datetime
from app.core.config import Config
from app.data.data_fetcher import DataFetcher
import logging

logging.basicConfig(level=logging.INFO)

def verify_specific_timestamp():
    api_key = Config.API_KEY
    access_token = Config.ACCESS_TOKEN
    fetcher = DataFetcher(api_key, access_token)
    
    # We need data that covers 2026-02-11 10:50:00
    # Fetching 30 days ending today ensures we have it.
    end_date = datetime.datetime.now() + datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=30)
    
    # 1. Fetch Historical
    df_historical = fetcher.get_historical_data(
        Config.SYMBOL_NIFTY_50, 
        '5minute', 
        start_date.strftime('%Y-%m-%d'), 
        end_date.strftime('%Y-%m-%d')
    )
    
    # 2. Fetch Intraday (Today) just in case, though 11th is historical
    df_intraday = fetcher.get_intraday_data(Config.SYMBOL_NIFTY_50, '5minute')
    
    # 3. Merge
    if df_historical is not None and df_intraday is not None:
         df = pd.concat([df_historical, df_intraday])
         df = df[~df.index.duplicated(keep='last')]
         df = df.sort_index()
    else:
        df = df_historical
        
    # 4. Calculate EMA
    df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    # 5. Look for target time
    target_time_str = "2026-02-11 10:50:00"
    
    # Convert index to string to find match
    match = df[df.index.astype(str).str.contains(target_time_str)]
    
    if not match.empty:
        row = match.iloc[0]
        print(f"\n--- Verification for {target_time_str} ---")
        print(f"Time: {row.name}")
        print(f"Close: {row['close']}")
        print(f"EMA 5: {row['ema_5']:.2f}")
        print(f"EMA 20: {row['ema_20']:.2f}")
        
        # Verify Screenshot Values
        screenshot_ema5 = 25966.17
        screenshot_ema20 = 25953.35
        
        diff5 = abs(row['ema_5'] - screenshot_ema5)
        diff20 = abs(row['ema_20'] - screenshot_ema20)
        
        print(f"\nScreenshot Values:")
        print(f"EMA 5: {screenshot_ema5}")
        print(f"EMA 20: {screenshot_ema20}")
        
        print(f"\nDifference:")
        print(f"EMA 5 Diff: {diff5:.2f}")
        print(f"EMA 20 Diff: {diff20:.2f}")
        
    else:
        print(f"❌ Timestamp {target_time_str} not found in data.")
        # Print surrounding values
        surrounding = df[df.index.astype(str).str.contains("2026-02-11 10")]
        if not surrounding.empty:
            print("Available times around 10:xx on 11th:")
            print(surrounding[['close']].head(10))

if __name__ == "__main__":
    verify_specific_timestamp()
