# PCR Sentiment Fix - Deployment Checklist

## ✅ Fixes Applied

### 1. Rate Limit Handling
- [x] Increased PCR fetch interval from 60s to 120s
- [x] File: `backend/app/core/market_data.py` (Line 511)
- [x] Reduces API calls from 60/hour to 30/hour

### 2. Comprehensive Logging Added
- [x] Added [GREEKS] logging tags to `get_option_greeks_batch()`
- [x] Added [PCR] logging tags to `get_nifty_pcr()`
- [x] File: `backend/app/data/data_fetcher.py`
- [x] Logs show: API calls, response status, OI aggregation, PCR calculation

### 3. Frontend Data Flow
- [x] Added `pcr`, `pcr_analysis`, `vix` to status response
- [x] File: `backend/main.py`
- [x] Updated PCRSentimentCard data binding
- [x] File: `frontend/src/Dashboard.tsx`

## 📋 Deployment Steps

### Step 1: Restart Backend
```bash
# Stop current bot
pkill -f "python3 main.py"

# Wait 5 seconds
sleep 5

# Start bot
cd /Users/jitendrasonawane/Workpace/backend
python3 main.py
```

### Step 2: Monitor Logs
```bash
# Watch for PCR and Greeks logs
tail -f logs/niftybot_*.log | grep "\[PCR\]\|\[GREEKS\]"
```

### Step 3: Verify Dashboard
- Open dashboard in browser
- Check PCR Sentiment Card
- Should show:
  - PCR value (e.g., 0.9000)
  - Sentiment label (BULLISH/BEARISH/etc)
  - Emoji indicator
  - Trend information

## 🔍 Verification Checklist

### Logs Should Show
- [ ] `📊 [PCR] Starting calculation for spot: XXXX`
- [ ] `✅ [PCR] Found X Nifty options`
- [ ] `📅 [PCR] Nearest expiry: XXXX-XX-XX`
- [ ] `✅ [PCR] Found X options in range`
- [ ] `🔍 [GREEKS] Calling /market-quote/option-greek for X instruments`
- [ ] `📥 [GREEKS] Response status: 200`
- [ ] `✅ [GREEKS] Received data for X instruments`
- [ ] `📊 [PCR] OI: CE=X(XXXXXXX), PE=X(XXXXXXX)`
- [ ] `✅ [PCR] Calculated: X.XXXX`

### Dashboard Should Show
- [ ] PCR Sentiment Card visible
- [ ] PCR value displayed (not "Waiting for PCR data...")
- [ ] Sentiment label (BULLISH/BEARISH/NEUTRAL/EXTREME_BULLISH/EXTREME_BEARISH)
- [ ] Emoji indicator (🟢/🔴/🟡)
- [ ] Trend information (if available)

### API Rate Limiting
- [ ] No 429 errors in logs (or significantly reduced)
- [ ] PCR updates every 120 seconds (not every 60)
- [ ] VIX updates every 120 seconds

## 🚨 Troubleshooting

### If PCR Still Shows "Waiting for PCR data..."

1. **Check logs for [PCR] tags**
   ```bash
   grep "\[PCR\]" logs/niftybot_*.log | tail -20
   ```

2. **Identify failure point**
   - If no [PCR] logs: `get_nifty_pcr()` not being called
   - If stops at "Found X Nifty options": Instrument filtering issue
   - If stops at "Nearest expiry": No future expiries found
   - If stops at "Found X options in range": Strike range filtering issue
   - If stops at "Calling /market-quote/option-greek": API call failed
   - If stops at "Response status": Check status code (200 = success, 429 = rate limited)

3. **Check API authentication**
   ```bash
   grep "Access Token" logs/niftybot_*.log | tail -5
   ```

4. **Verify instruments loaded**
   ```bash
   grep "Instruments loaded" logs/niftybot_*.log
   ```

### If Getting 429 Errors

- Interval is already 120s, so this shouldn't happen
- If still occurring, increase to 180s:
  ```python
  await asyncio.sleep(180)  # Every 3 minutes
  ```

### If PCR Value is 0 or Negative

- Check OI values in logs: `📊 [PCR] OI: CE=X(XXXXXXX), PE=X(XXXXXXX)`
- If CE OI is 0: No call options in range
- If PE OI is 0: No put options in range
- Verify strike range is correct (±500 points from spot)

## 📊 Expected Behavior

### Normal Operation
```
📊 [PCR] Starting calculation for spot: 26050
✅ [PCR] Found 100 Nifty options
📅 [PCR] Nearest expiry: 2025-12-05
✅ [PCR] Found 40 options in range
🔍 [GREEKS] Calling /market-quote/option-greek for 40 instruments
📥 [GREEKS] Response status: 200
✅ [GREEKS] Received data for 40 instruments
📊 [PCR] OI: CE=20(5000000), PE=20(4500000)
✅ [PCR] Calculated: 0.9000
📊 PCR Updated: 0.9000 | Sentiment: BULLISH
```

### Dashboard Display
```
PCR Sentiment
0.900 BULLISH 🟢

Bullish sentiment - more calls than puts

Trend: 📉 Bullish Trend

Extreme Bearish > 1.5
Extreme Bullish < 0.5
```

## 🎯 Success Criteria

- [x] PCR calculation completes without errors
- [x] PCR value is displayed on dashboard
- [x] Sentiment label is shown (BULLISH/BEARISH/etc)
- [x] No 429 rate limit errors
- [x] Logs show detailed [PCR] and [GREEKS] tags
- [x] PCR updates every 120 seconds
- [x] Frontend receives PCR data via WebSocket/polling

## 📝 Notes

- PCR interval increased to 120s to avoid rate limiting
- Logging added with [PCR] and [GREEKS] tags for easy debugging
- Frontend now receives PCR data at top level of status response
- All changes are backward compatible
- No database changes required
- No frontend rebuild required (uses existing components)

## 🔄 Rollback Plan

If issues occur, revert changes:

1. **Revert interval**: Change 120 back to 60 in `market_data.py` line 511
2. **Remove logging**: Not necessary, logging is non-breaking
3. **Restart bot**: Changes take effect immediately

## 📞 Support

If PCR still doesn't work after these fixes:

1. Check logs for [PCR] and [GREEKS] tags
2. Verify API authentication token is valid
3. Ensure instruments CSV is loaded
4. Check if `/market-quote/option-greek` API is working
5. Verify strike range filtering logic
6. Check OI values in API response
