import sys
import os
import pandas as pd
import numpy as np
import datetime
from app.core.config import Config
from app.data.data_fetcher import DataFetcher

# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ema_convergence():
    api_key = Config.API_KEY
    access_token = Config.ACCESS_TOKEN
    
    if not access_token:
        print("Error: No access token found in .env")
        return

    fetcher = DataFetcher(api_key, access_token)
    
    # 1. Fetch LONG history (e.g., 30 days) to get a "converged" true EMA
    end_date = datetime.datetime.now() + datetime.timedelta(days=1)
    start_date_long = end_date - datetime.timedelta(days=30)
    
    print(f"Fetching LONG history (30 days): {start_date_long.date()} to {end_date.date()}")
    df_long = fetcher.get_historical_data(
        Config.SYMBOL_NIFTY_50, 
        '5minute', 
        start_date_long.strftime('%Y-%m-%d'), 
        end_date.strftime('%Y-%m-%d')
    )
    
    # Fetch Intraday (Today)
    df_intraday = fetcher.get_intraday_data(Config.SYMBOL_NIFTY_50, '5minute')
    if df_long is not None and df_intraday is not None:
         print(f"Merging Long History ({len(df_long)}) + Intraday ({len(df_intraday)})")
         df_long = pd.concat([df_long, df_intraday])
         df_long = df_long[~df_long.index.duplicated(keep='last')]
         df_long = df_long.sort_index()
    
    if df_long is None or df_long.empty:
        print("Failed to fetch long history data")
        return

    # Calculate EMA on long history
    df_long['ema_5'] = df_long['close'].ewm(span=5, adjust=False).mean()
    df_long['ema_20'] = df_long['close'].ewm(span=20, adjust=False).mean()
    
    true_ema_20 = df_long['ema_20'].iloc[-1]
    true_ema_5 = df_long['ema_5'].iloc[-1]
    
    print(f"Last Candle Time (Long): {df_long.index[-1]}")
    print(f"TRUE EMA-5 (30 days): {true_ema_5:.2f}")
    print(f"TRUE EMA-20 (30 days): {true_ema_20:.2f}")
    
    # 2. Fetch SHORT history (5 days) - mimicking current production
    start_date_short = end_date - datetime.timedelta(days=5)
    print(f"\nFetching SHORT history (5 days): {start_date_short.date()} to {end_date.date()}")
    
    # We can just slice the long dataframe to simulate fetching short history
    # This ensures we use EXACTLY the same data points for comparison
    df_short = df_long[df_long.index >= pd.Timestamp(start_date_short.date(), tz=df_long.index.tz)]
    
    if df_short.empty:
        print("Short slice is empty!")
        return
        
    # Calculate EMA on short history
    df_short_calc = df_short.copy()
    df_short_calc['ema_5'] = df_short_calc['close'].ewm(span=5, adjust=False).mean()
    df_short_calc['ema_20'] = df_short_calc['close'].ewm(span=20, adjust=False).mean()
    
    short_ema_20 = df_short_calc['ema_20'].iloc[-1]
    short_ema_5 = df_short_calc['ema_5'].iloc[-1]
    
    print(f"Last Candle Time (Short): {df_short_calc.index[-1]}")
    print(f"PROD EMA-5 (5 days): {short_ema_5:.2f}")
    print(f"PROD EMA-20 (5 days): {short_ema_20:.2f}")
    
    # 3. Compare
    diff_5 = abs(true_ema_5 - short_ema_5)
    diff_20 = abs(true_ema_20 - short_ema_20)
    
    print(f"\nDifferences:")
    print(f"EMA-5 Diff: {diff_5:.4f}")
    print(f"EMA-20 Diff: {diff_20:.4f}")
    
    if diff_20 > 0.1: # Threshold depends on asset price, for Nifty (24000) 0.1 is small but let's see
        print("\n❌ SIGNIFICANT DISCREPANCY in EMA-20!")
        print("Possible Fix: Increase historical data fetch to 15-30 days.")
    else:
        print("\n✅ Discrepancy is negligible. Initialization length is likely NOT the issue.")

    # 4. Check "Incomplete Candle" simulation
    # Let's see if the very last value matches what we expect from StreamingEMA
    # StreamingEMA uses the exact same recursive formula as Pandas adjust=False
    # So if Pandas result on 5 days matches, StreamingEMA should match,
    # UNLESS the StreamingEMA state is carried over incorrectly across restarts or gaps.
    
if __name__ == "__main__":
    try:
        test_ema_convergence()
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
