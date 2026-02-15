import os
import sys
import pandas as pd
import datetime
from app.data.data_fetcher import DataFetcher
from app.core.config import Config
from app.core.logger_config import logger

# Initialize DataFetcher
fetcher = DataFetcher(Config.API_KEY, Config.ACCESS_TOKEN)

# 1. Test Historical Data Inclusivity
print("\\n--- TEST 1: Historical Data Inclusivity ---")
today = datetime.datetime.now().strftime('%Y-%m-%d')
tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

print(f"Fetching History: Yesterday ({yesterday}) to Today ({today})")
df_hist_today = fetcher.get_historical_data('NSE_INDEX|Nifty 50', '5minute', yesterday, today)
if df_hist_today is not None and not df_hist_today.empty:
    print(f"Result (to_date={today}): Last Candle = {df_hist_today.index[-1]}")
else:
    print(f"Result (to_date={today}): Empty")

print(f"Fetching History: Yesterday ({yesterday}) to Tomorrow ({tomorrow})")
df_hist_tomorrow = fetcher.get_historical_data('NSE_INDEX|Nifty 50', '5minute', yesterday, tomorrow)
if df_hist_tomorrow is not None and not df_hist_tomorrow.empty:
    print(f"Result (to_date={tomorrow}): Last Candle = {df_hist_tomorrow.index[-1]}")
else:
    print(f"Result (to_date={tomorrow}): Empty")


# 2. Test Intraday Data Behavior
print("\\n--- TEST 2: Intraday Data Behavior ---")
df_intraday = fetcher.get_intraday_data('NSE_INDEX|Nifty 50', '5minute')

if df_intraday is not None and not df_intraday.empty:
    last_candle_time = df_intraday.index[-1]
    print(f"Intraday Last Candle Time: {last_candle_time}")
    
    # Check Gap from Current Time
    now = datetime.datetime.now()
    # Assuming index is naive and in IST? Or UTC? 
    # Upstox returns offset-aware usually. Let's check tzinfo.
    print(f"Timezone info: {last_candle_time.tzinfo}")
    
    # Calculate difference
    # If naive, assume system time (IST).
    if last_candle_time.tzinfo is None:
         diff = (now - last_candle_time).total_seconds()
    else:
         # Make now aware
         now = now.replace(tzinfo=last_candle_time.tzinfo) # forceful alignment for rough check
         diff = (now - last_candle_time).total_seconds()
         
    print(f"Current System Time: {now}")
    print(f"Gap (Current - Last Candle): {diff:.2f} seconds")
    
    # Check if last candle is 'complete' (e.g. at 10:15:00 for a 5min candle ending at 10:20:00?)
    # Usually timestamps are Open Time.
    # If 5min candle @ 10:15:00 -> It covers 10:15:00 to 10:19:59.
    # Gaps > 300s mean we are missing a completed candle?
    
else:
    print("Intraday Data: Empty/Failed")

# 3. Check Overlap
print("\\n--- TEST 3: Merge Check ---")
if df_hist_tomorrow is not None and df_intraday is not None:
    print(f"Historical Last: {df_hist_tomorrow.index[-1]}")
    print(f"Intraday First: {df_intraday.index[0]}")
    
    # Check for duplicates
    combined = pd.concat([df_hist_tomorrow, df_intraday])
    duplicates = combined.index.duplicated(keep='first')
    num_dupes = duplicates.sum()
    print(f"Duplicates found: {num_dupes}")
    if num_dupes > 0:
        print(f"First 5 duplicates: {combined[duplicates].index[:5]}")

# 4. Test Volume of Data (30 Days)
print("\\n--- TEST 4: 30 Days Data Volume ---")
from_date_30 = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
print(f"Fetching 30 days: {from_date_30} to {today}")
df_30 = fetcher.get_historical_data('NSE_INDEX|Nifty 50', '5minute', from_date_30, today)

if df_30 is not None:
    print(f"Candles Received: {len(df_30)}")
    expected_approx = 30 * 75 # roughly
    print(f"Expected Approx: {expected_approx}")
    
    if len(df_30) < expected_approx * 0.8: # Allow for holidays
        print("⚠️ WARNING: SIGNIFICANTLY LESS DATA THAN EXPECTED. API might be truncating.")
        print(f"First Candle: {df_30.index[0]}")
        print(f"Last Candle: {df_30.index[-1]}")
    else:
        print("✅ Data volume looks reasonable.")
else:
    print("❌ Failed to fetch 30 days data")
