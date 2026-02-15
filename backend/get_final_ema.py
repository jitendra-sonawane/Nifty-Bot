import pandas as pd
import datetime
from app.data.data_fetcher import DataFetcher
from app.core.config import Config

# Initialize
fetcher = DataFetcher(Config.API_KEY, Config.ACCESS_TOKEN)

# 1. Fetch 30 Days History (inclusive of today for simplicity in this script, or merge)
# We'll stick to the proven merge method: History (up to yesterday) + Intraday (Today)
today = datetime.datetime.now().strftime('%Y-%m-%d')
from_date = (datetime.datetime.now() - datetime.timedelta(days=29)).strftime('%Y-%m-%d') # 30 days limit is strict?

print(f"Fetching History from {from_date} to {today}...")
df_hist = fetcher.get_historical_data('NSE_INDEX|Nifty 50', '5minute', from_date, today)

print("Fetching Intraday (Today)...")
df_intra = fetcher.get_intraday_data('NSE_INDEX|Nifty 50', '5minute')

# Merge
if df_hist is not None and df_intra is not None:
    df = pd.concat([df_hist, df_intra])
    df = df[~df.index.duplicated(keep='last')]
    df = df.sort_index()
    
    # Calculate EMA
    df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    # Get last few candles (specifically 15:25 / 15:30)
    print("\n" + "="*50)
    print("📢 FINAL EMA VALUES FOR TRADINGVIEW COMPARISON")
    print("="*50)
    print(df[['close', 'ema_5', 'ema_20']].tail(5))
    
    last_candle = df.iloc[-1]
    print("\nLast Candle timestamp:", last_candle.name)
    print(f"Close Price: {last_candle['close']}")
    print(f"EMA 5:       {last_candle['ema_5']:.2f}")
    print(f"EMA 20:      {last_candle['ema_20']:.2f}")
    print("="*50)
else:
    print("Error fetching data")
