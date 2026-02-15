# Rate Limiting Error Analysis

## Error Details
```
ERROR - ❌ Error fetching quotes: 429 - {"status":"error","errors":[{"errorCode":"UDAPI10005","message":"Too Many Request Sent",...}]}
```

## Root Cause

The **429 Too Many Requests** error is being caused by **excessive calls to the Upstox `/market-quote/quotes` API endpoint**.

### Which API is Causing This?

**API Endpoint:** `/v2/market-quote/quotes`  
**Method:** `DataFetcher.get_quotes()`  
**Location:** `/backend/app/data/data_fetcher.py` (lines 405-441)

### Where is it Being Called From?

Based on log analysis and code inspection, the `get_quotes()` method is being called from **multiple locations**:

1. **`DataFetcher.get_option_greeks()`** (line 572)
   - Called to fetch option prices for Greeks calculation
   - This is being called by the deprecated `_greeks_loop()` in `market_data.py`

2. **`TradingBot._on_price_update()`** in `main.py` (lines 136, 187)
   - Called to check exits for open positions
   - Called to calculate unrealized PnL

3. **Strategy Runner** (indirectly)
   - Fetches historical data every time price updates
   - This triggers the strategy check which may need option data

### Frequency Analysis

Looking at the logs, the pattern shows:
- **Every 1-2 seconds**: Quotes API is being called
- This is happening because:
  1. WebSocket is streaming Nifty prices continuously
  2. Each price update triggers Greeks calculation
  3. Greeks calculation calls `get_quotes()` for option prices
  4. Position monitoring also calls `get_quotes()` for exit checks

### Log Evidence

```
2025-12-04 10:16:52 - INFO - 🔍 Fetching quotes for 1 keys: NSE_FO|46807: Unknown
2025-12-04 10:16:52 - ERROR - ❌ Error fetching quotes: 429
2025-12-04 10:16:53 - INFO - 🔍 Fetching quotes for 1 keys: NSE_FO|46807: Unknown
2025-12-04 10:16:53 - ERROR - ❌ Error fetching quotes: 429
2025-12-04 10:16:54 - INFO - 🔍 Fetching quotes for 2 keys: NSE_FO|46807: Unknown | NSE_FO|46807: Unknown
2025-12-04 10:16:54 - ERROR - ❌ Error fetching quotes: 429
```

The quotes are being fetched **every second**, which far exceeds Upstox's rate limits.

## Why This is Happening

### Current Architecture Issue

The application is using a **hybrid approach** that's causing redundancy:

1. **WebSocket Streaming** (✅ Good)
   - Streaming Nifty 50 prices via WebSocket
   - Streaming CE/PE option prices via WebSocket
   - This is efficient and real-time

2. **HTTP Polling** (❌ Redundant)
   - Still calling `get_quotes()` via HTTP for the same data
   - This is happening because:
     - The deprecated `_greeks_loop()` is still active (though commented out)
     - Position monitoring is calling quotes API
     - Strategy runner might be triggering additional calls

### The Specific Culprit

Looking at line 572 in `data_fetcher.py`:
```python
def get_option_greeks(self, spot_price, expiry_date=None):
    # ... code ...
    quotes = self.get_quotes([ce_key, pe_key])  # ← THIS IS BEING CALLED TOO FREQUENTLY
```

This method is being called even though the application is already receiving option prices via WebSocket.

## Upstox API Rate Limits

Upstox has the following rate limits:
- **Market Quote APIs**: Limited to a certain number of requests per second/minute
- **Error Code UDAPI10005**: "Too Many Request Sent"

The exact limits aren't publicly documented, but based on the errors, it appears to be:
- Approximately **1-2 requests per second** maximum
- Or **~60-120 requests per minute**

## Solutions

### Immediate Fix (Quick)

**Add rate limiting/caching to `get_quotes()`:**

```python
import time
from functools import lru_cache

class DataFetcher:
    def __init__(self, api_key, access_token):
        # ... existing code ...
        self._quotes_cache = {}
        self._quotes_cache_ttl = 1.0  # 1 second cache
    
    def get_quotes(self, instrument_keys):
        # Check cache first
        cache_key = ','.join(sorted(instrument_keys))
        now = time.time()
        
        if cache_key in self._quotes_cache:
            cached_data, cached_time = self._quotes_cache[cache_key]
            if now - cached_time < self._quotes_cache_ttl:
                self.logger.debug(f"📦 Using cached quotes (age: {now - cached_time:.2f}s)")
                return cached_data
        
        # Fetch from API
        # ... existing get_quotes code ...
        
        # Cache the result
        self._quotes_cache[cache_key] = (result, now)
        return result
```

### Better Fix (Recommended)

**Remove redundant HTTP polling and rely solely on WebSocket data:**

1. **Stop calling `get_quotes()` for option prices** when WebSocket is active
2. **Use cached WebSocket prices** from `MarketDataManager`:
   - `self.option_ce_price`
   - `self.option_pe_price`

3. **Modify Greeks calculation** to use WebSocket data:
```python
# In market_data.py, _calculate_and_emit_greeks() already does this!
# Just ensure get_option_greeks() is not being called elsewhere
```

4. **Position monitoring** should also use WebSocket data or add throttling

### Long-term Fix (Best)

**Implement a centralized quote cache/manager:**

1. Create a `QuoteManager` class that:
   - Maintains a cache of all instrument prices
   - Updates from WebSocket (primary source)
   - Falls back to HTTP API only when needed
   - Implements proper rate limiting

2. All components request quotes from `QuoteManager` instead of directly calling API

## Recommended Actions

### Priority 1: Add Caching (Immediate)
Add 1-second caching to `get_quotes()` to prevent rapid-fire API calls

### Priority 2: Audit Callers (Short-term)
Review all places calling `get_quotes()` and:
- Remove calls that can use WebSocket data
- Add throttling to position monitoring
- Ensure `_greeks_loop()` is truly disabled

### Priority 3: Refactor Architecture (Long-term)
Implement centralized quote management to prevent this issue from recurring

## Files to Modify

1. `/backend/app/data/data_fetcher.py` - Add caching to `get_quotes()`
2. `/backend/app/core/market_data.py` - Ensure WebSocket data is being used
3. `/backend/main.py` - Throttle position monitoring quote fetches
4. `/backend/app/core/strategy_runner.py` - Review if it needs quote data

## Current Status

✅ **WebSocket streaming is working** - Option prices are being received  
❌ **HTTP polling is redundant** - Still calling quotes API unnecessarily  
⚠️ **Rate limit exceeded** - Too many API calls per second  

The good news is that the core functionality (WebSocket streaming) is working correctly. We just need to remove or throttle the redundant HTTP calls.
