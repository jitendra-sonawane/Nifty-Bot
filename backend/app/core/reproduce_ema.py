import sys
import os
import logging
import pandas as pd
import datetime as dt_module # Import module to access classes
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Mock logging
logging.basicConfig(level=logging.DEBUG)

from app.core.streaming import CandleManager

def test_candle_manager():
    print("--- Starting CandleManager Test ---")
    
    # Initialize Manager with 1 minute interval
    cm = CandleManager('1minute') 
    
    # Mock historical data
    cm.initialize(pd.DataFrame())
    
    # IST Timezone
    ist = str(timezone(timedelta(hours=5, minutes=30)))
    # We can't use 'ist' object directly in datetime.now() unless it is a tzinfo object.
    # The code in streaming.py creates it: ist = timezone(timedelta(hours=5, minutes=30))
    # Let's trust it works.
    
    print("\n--- Update 1 (Initial) ---")
    # Real time
    is_new, df = cm.update(100.0, 10)
    print(f"Is New: {is_new}, DF Len: {len(df)}")
    if not df.empty:
        print(f"Candle: {df.index[-1]}")

    print("\n--- Update 2 (Same Candle) ---")
    # Should update same candle
    is_new, df = cm.update(101.0, 5)
    print(f"Is New: {is_new}, DF Len: {len(df)}")
    print(f"Close: {df['close'].iloc[-1]}")

    # Now simulate time jump for Next Candle
    # We need to mock app.core.streaming.datetime
    
    import unittest.mock as mock
    
    # Target time: 5 minutes later to be safe
    # If using 1min interval, 2 mins is enough.
    
    # Construct a future time
    # streaming.py uses: now = datetime.now(ist)
    # So we need to return an aware datetime.
    
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    future_time = datetime.now(tz_ist) + timedelta(minutes=2)
    
    # Clean seconds to ensure it lands on a new minute 
    # (though update logic handles it)
    
    print(f"\n--- Simulating Future Time: {future_time} ---")
    
    with mock.patch('app.core.streaming.datetime') as mock_dt:
        mock_dt.now.return_value = future_time
        # We must preserve other attributes of datetime module that streaming.py uses
        mock_dt.strptime = dt_module.datetime.strptime
        mock_dt.timedelta = dt_module.timedelta
        mock_dt.timezone = dt_module.timezone
        
        # NOTE: streaming.py imports: from datetime import datetime, timedelta
        # Patching app.core.streaming.datetime ONLY patches 'datetime' class usage if it was imported as 'import datetime'
        # BUT streaming.py does 'from datetime import datetime'.
        # So we must patch 'app.core.streaming.datetime' which essentially patches the symbol 'datetime' in that module's namespace.
        # This IS correct.
        
        is_new, df = cm.update(102.0, 20)
        print(f"Is New: {is_new}, DF Len: {len(df)}")
        if not df.empty:
            print(f"Last Candle: {df.index[-1]}")
            print(f"Prev Candle: {df.index[-2] if len(df) > 1 else 'None'}")
            
if __name__ == "__main__":
    test_candle_manager()
