# PCR Data Not Displaying - Root Cause Analysis

## Issue Summary
PCR (Put-Call Ratio) data is not being displayed on the dashboard.

## Root Cause
**The `/market-quote/option-greek` API is returning OI (Open Interest) values of 0 for all options.**

### Evidence from Logs
```
2025-12-03 10:04:23 - 📊 [PCR] Starting: spot=25918.6
2025-12-03 10:04:23 - 📅 [PCR] Expiry: 2025-12-09 00:00:00
2025-12-03 10:04:23 - ✅ [PCR] Found 40 options
2025-12-03 10:04:23 - ✅ [PCR] Got 40 greeks
2025-12-03 10:04:23 - 📊 [PCR] OI: CE=0, PE=0  ← ❌ PROBLEM HERE
2025-12-03 10:04:23 - ❌ [PCR] No CE OI
```

## Why Is OI Zero?

### Investigation Findings:

1. **NSE.csv Instrument File is Stale**
   - Last modified: Dec 3, 10:07 AM (today)
   - Contains only **weekly** NIFTY options expiring on Mondays
   - December 2025 expiries: 2025-12-09, 2025-12-16, 2025-12-23, 2025-12-30
   - **No daily expiries** available

2. **Current Situation**
   - Today: Tuesday, Dec 3, 2025
   - Nearest expiry: Monday, Dec 9, 2025 (6 days away)
   - Options that are 6 days from expiry may have:
     - Zero or very low open interest
     - Inactive trading
     - API returning 0 for OI values

3. **Potential API Issues**
   - The `/market-quote/option-greek` endpoint (v3 API) may:
     - Not return real-time OI data for all options
     - Return 0 for options with low trading activity
     - Require different parameters or endpoint

## Solutions to Try

### Option 1: Use Different API Endpoint ✅ RECOMMENDED
Instead of `/market-quote/option-greek`, use `/market-quote/quotes` which provides:
- Real-time market data
- Actual OI values from exchange
- Better data quality for liquid options

**Implementation:**
```python
def get_nifty_pcr(self, spot_price):
    # Get option instrument keys
    instrument_keys = self._get_option_keys(spot_price)
    
    # Use /market-quote/quotes instead of /market-quote/option-greek
    url = f"{self.base_url}/market-quote/quotes"
    params = {'instrument_key': ','.join(instrument_keys)}
    response = requests.get(url, headers=headers, params=params)
    
    # Extract OI from quotes response
    for key, quote in data['data'].items():
        oi = quote.get('ohlc', {}).get('open_interest', 0)
        # or: oi = quote.get('oi', 0)
```

### Option 2: Verify NSE.csv Update Frequency
The NSE.csv file needs to be fresh and contain all tradable options:
- Daily options for NIFTY (if available)
- Weekly options
- Monthly options

**Check if re-downloading helps:**
```bash
rm backend/NSE.csv
# Restart server - it will auto-download
```

### Option 3: Wait for Market Hours
If current time is outside market hours (9:15 AM - 3:30 PM IST):
- OI data might be stale
- API might return 0 for inactive options
- Try again during active market hours

### Option 4: Increase Strike Range
Current code uses ±500 points from spot price.
Try expanding to ±1000 points to get more liquid options:

```python
strike_range = 1000  # Instead of 500
```

## Immediate Next Steps

1. ✅ **Added logging** to inspect actual API response structure
2. ⏳ **Wait for PCR loop** to run and check sample Greek data
3. 📝 **Document API response format** from logs
4. 🔧 **Implement fix** based on actual API response

## Testing Plan

1. Check logs for "🔍 [GREEKS] Sample data" to see actual API response
2. Verify if OI field exists and what its value is
3. If OI is indeed 0, switch to `/market-quote/quotes` endpoint
4. Test during market hours for better data quality

## Related Files
- `backend/app/data/data_fetcher.py` - PCR calculation logic
- `backend/app/core/market_data.py` - PCR loop (every 120s)
- `backend/app/core/pcr_calculator.py` - PCR math and sentiment

## Status
🔍 **Investigation in progress** - Waiting for API response logging to confirm structure.
