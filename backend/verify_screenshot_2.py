import pandas as pd
import datetime
from app.data.data_fetcher import DataFetcher
from app.core.config import Config

# Initialize
fetcher = DataFetcher(Config.API_KEY, Config.ACCESS_TOKEN)

# Target Timestamp from Screenshot
target_time_str = "2026-02-10 14:55:00+05:30"
# We need enough history before this date. 
# Let's fetch from 2026-01-01 to 2026-02-11 (covering the target date)
from_date = "2026-01-12" # Approx 30 days before target
to_date = "2026-02-11"

print(f"Fetching History from {from_date} to {to_date}...")
df = fetcher.get_historical_data('NSE_INDEX|Nifty 50', '5minute', from_date, to_date)

if df is not None:
    # Calculate EMA
    df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    # Isolate the target row
    # Ensure index is localized or matching the target string format
    if df.index.tz is None:
        # Assuming Upstox returns offset-aware, but if not we might need to localize
        pass 
        
    try:
        row = df.loc[target_time_str]
        print("\n" + "="*50)
        print(f"🎯 VERIFICATION FOR {target_time_str}")
        print("="*50)
        print(f"Close Price: {row['close']}")
        print(f"EMA 5:       {row['ema_5']:.2f}")
        print(f"EMA 20:      {row['ema_20']:.2f}")
        print("="*50)
        
        expected_ema5 = 25931.43
        expected_ema20 = 25930.30
        
        diff5 = abs(row['ema_5'] - expected_ema5)
        diff20 = abs(row['ema_20'] - expected_ema20)
        
        if diff5 < 0.1 and diff20 < 0.1:
            print("✅ EXACT MATCH (within tolerance)")
        else:
            print(f"❌ MISMATCH. Diff5: {diff5:.2f}, Diff20: {diff20:.2f}")
            
    except KeyError:
        print(f"❌ Timestamp {target_time_str} not found in data.")
        print("Closest timestamps:")
        # Find closest
        # Convert target to datetime
        target_dt = pd.to_datetime(target_time_str)
        # simplistic search
        idx = df.index.get_indexer([target_dt], method='nearest')
        print(df.iloc[idx].index)
else:
    print("Error fetching data")
