# PCR Data Not Showing - Fix Applied

## Issue
PCR (Put-Call Ratio) data was not being displayed on the dashboard because the OI (Open Interest) field was not being correctly extracted from the `/market-quote/option-greek` API response.

## Root Cause
The Upstox `/market-quote/option-greek` endpoint returns OI data, but the field location in the response structure was not being correctly identified. The code was looking for `oi` at the top level, but it might be nested under `ohlc` or have a different field name.

## Solution Applied

### 1. Enhanced OI Extraction in `get_nifty_pcr()` (Line 265-273)
Updated the OI extraction logic to check multiple possible field locations:

```python
# Extract OI from response - check multiple possible field names
oi = greek_info.get('oi', 0) or greek_info.get('open_interest', 0)
if oi == 0 and 'ohlc' in greek_info:
    oi = greek_info['ohlc'].get('oi', 0) or greek_info['ohlc'].get('open_interest', 0)
```

This checks:
- Top-level `oi` field
- Top-level `open_interest` field  
- Nested `ohlc.oi` field
- Nested `ohlc.open_interest` field

### 2. Added Diagnostic Logging in `get_option_greeks_batch()` (Line 408-415)
Added detailed logging to identify the exact response structure:

```python
if data['data']:
    first_key = list(data['data'].keys())[0]
    first_item = data['data'][first_key]
    self.logger.info(f"🔍 [GREEKS] Response keys: {list(first_item.keys())}")
    if 'oi' in first_item:
        self.logger.info(f"🔍 [GREEKS] OI at top: {first_item.get('oi')}")
    if 'ohlc' in first_item:
        self.logger.info(f"🔍 [GREEKS] OHLC keys: {list(first_item['ohlc'].keys())}")
```

## How to Verify the Fix

### 1. Check Logs for OI Field Location
Run the bot and check logs for the diagnostic messages:

```bash
tail -f logs/niftybot_*.log | grep "\[GREEKS\]"
```

Expected output will show:
- `🔍 [GREEKS] Response keys: [...]` - Shows all fields in response
- `🔍 [GREEKS] OI at top: X` - If OI is at top level
- `🔍 [GREEKS] OHLC keys: [...]` - If OHLC structure exists

### 2. Monitor PCR Calculation
Check if PCR is now being calculated:

```bash
tail -f logs/niftybot_*.log | grep "\[PCR\]"
```

Expected output:
```
📊 [PCR] Starting: spot=26050
✅ [PCR] Found 40 options
✅ [PCR] Got 40 greeks
📊 [PCR] OI: CE=5000000, PE=4500000
✅ [PCR] Result: 0.9000
```

### 3. Check Dashboard
PCR Sentiment Card should now display:
- PCR value (e.g., 0.9000)
- Sentiment (BULLISH, BEARISH, etc.)
- Emoji indicator
- Trend information

## Files Modified

1. **backend/app/data/data_fetcher.py**
   - Line 265-273: Enhanced OI extraction logic in `get_nifty_pcr()`
   - Line 408-415: Added diagnostic logging in `get_option_greeks_batch()`

## API Endpoint Used

- **Endpoint**: `/market-quote/option-greek` (v3 API)
- **URL**: `https://api.upstox.com/v3/market-quote/option-greek`
- **Method**: GET
- **Parameters**: `instrument_key` (comma-separated list)
- **Response**: Contains Greeks data including OI for each option

## Next Steps

1. Restart the bot to apply changes
2. Monitor logs for diagnostic messages
3. Verify PCR appears on dashboard
4. If OI is still 0, check logs to identify exact field name and update extraction logic accordingly

## Troubleshooting

If PCR still shows as `None`:

1. **Check diagnostic logs** for `[GREEKS]` tags to see response structure
2. **Verify API response** contains OI data
3. **Check authentication** - ensure access token is valid
4. **Verify instruments** - ensure NSE.csv is loaded with NIFTY options

## References

- Upstox API Documentation: `/market-quote/option-greek`
- Response includes: Greeks (delta, gamma, theta, vega), IV, and OI
- OI field name may vary based on API version
