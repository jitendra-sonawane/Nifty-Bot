import yfinance as yf
import pandas as pd
import datetime

def verify_with_yahoo():
    print("Fetching data from Yahoo Finance (^NSEI)...")
    
    # 30 days data, 5m interval to match our backend
    # end_date is exclusive in yfinance usually, but let's check recent data
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=30)
    
    # Valid intervals: 1m,2m,5m,15m,30m,60m...
    # Yahoo Finance allows 60d max for 5m interval
    ticker = yf.Ticker("^NSEI")
    df = ticker.history(start=start_date, end=end_date, interval="5m")
    
    if df.empty:
        print("❌ No data received from Yahoo Finance.")
        return

    # Calculate EMA
    # Adjust=False is what we use in backend (standard for technical indicators)
    df['ema_5'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['ema_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    print(f"\nLast 5 Candles from Yahoo Finance:")
    print(df[['Close', 'ema_5', 'ema_20']].tail())
    
    last_row = df.iloc[-1]
    print(f"\nLatest Yahoo Finance Values ({last_row.name}):")
    print(f"Close: {last_row['Close']:.2f}")
    print(f"EMA 5: {last_row['ema_5']:.2f}")
    print(f"EMA 20: {last_row['ema_20']:.2f}")

    # Specific check for 2026-02-11 15:25 (Market Close yesterday) if available
    # Check if 11th Feb data exists
    target_date_str = "2026-02-11"
    # Filter for that day
    day_data = df[df.index.astype(str).str.contains(target_date_str)]
    
    if not day_data.empty:
        last_candle_of_day = day_data.iloc[-1]
        print(f"\n--- Benchmark: {target_date_str} Market Close ---")
        print(f"Time: {last_candle_of_day.name}")
        print(f"Close: {last_candle_of_day['Close']:.2f}")
        print(f"EMA 5: {last_candle_of_day['ema_5']:.2f}")
        print(f"EMA 20: {last_candle_of_day['ema_20']:.2f}")
        print(f"-------------------------------------------")

if __name__ == "__main__":
    try:
        verify_with_yahoo()
    except ImportError:
        print("yfinance not installed. Installing...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
        print("Installed yfinance. Retrying...")
        verify_with_yahoo()
    except Exception as e:
        print(f"Error: {e}")
