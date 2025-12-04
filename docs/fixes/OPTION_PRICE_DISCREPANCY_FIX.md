# Option Price Data Discrepancy - Investigation & Fix

**Date**: 2025-12-01  
**Issue**: Option prices showing 150-250 instead of real 69-70  
**Status**: 🔴 CRITICAL - Using mock data instead of real prices

## Problem

Dashboard is displaying **random option prices (100-300)** instead of real market prices (~69-70 for NIFTY 26300 CE).

### Root Cause

From `backend/server.log`:
```
ERROR - ❌ Error fetching quotes: 400 - UDAPI1087: One of either symbol or instrument_key is invalid
INFO - 📊 Using mock option prices (quotes unavailable)
```

**Issue Chain**:
1. `get_option_greeks()` tries to fetch option prices via API
2. API call fails with invalid instrument_key format
3. Fallback to **mock data**: `random.uniform(100, 300)` (lines 499-513 in data_fetcher.py)
4. Mock prices displayed on dashboard instead of real prices

### Invalid Instrument Keys Found

Logs show these **incorrect** formats:
- ❌ `'NIFTY 2025-11-25 26100 PE'` - Human readable format
- ❌ `'NSE_FO:NIFTY25NOV26050CE'` - Uses colon instead of pipe

**Expected format**: `NSE_FO|NIFTY05DEC24300CE`

## Investigation

### File: `data_fetcher.py` (Lines 495-513)
```python
# If quotes fail (API error/2025 date), generate mock quotes
if not quotes:
    import random
    quotes = {
        ce_key: {'last_price': round(random.uniform(100, 300), 2)},  # ❌ MOCK
        pe_key: {'last_price': round(random.uniform(100, 300), 2)}   # ❌ MOCK
    }
    self.logger.info(f"📊 Using mock option prices (quotes unavailable)")
```

This fallback was meant for testing but is being triggered in production due to API failures.

## Solutions

### Option 1: Fix Instrument Key Format (Recommended)
- Ensure `get_option_instrument_key()` returns proper `NSE_FO|xxxxx` format
- Validate keys before sending to API
- Fixed in lines 118-174 of data_fetcher.py

### Option 2: Use WebSocket for Option Prices
- Subscribe to CE/PE options via WebSocket instead of HTTP polling
- More efficient and real-time
- Already implemented in `option_data_handler.py` for real-time option data

### Option 3: Remove Mock Fallback (Temporary)
- Remove random fallback so errors are visible
- Force fix of root cause instead of hiding with fake data

## Immediate Actions

1. ✅ **Check instrument keys** - Verify format in `get_option_instrument_key()`
2. ⏳ **Use WebSocket option data** - Switch from HTTP to WS for option prices  
3. ⏳ **Remove/Disable mock fallback** - Don't hide errors with fake data

## Verification

To verify the fix:
```bash
# Check backend logs for API errors
tail -f backend/server.log | grep -E "(quotes|UDAPI|mock)"

# ✅ Success: No "Using mock option prices" messages
# ✅ Success: No UDAPI1087 errors
# ✅ Success: Real prices displayed (check against broker app)
```

## Next Steps

1. Fix instrument key format validation
2. Ensure WebSocket option subscription is working
3. Add error alerts when mock data is used
4. Remove mock fallback or make it more obvious (add WARNING badge on UI)

---

**Priority**: 🔴 HIGH - Affects trading decisions with incorrect option prices
