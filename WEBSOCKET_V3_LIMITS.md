# Upstox WebSocket v3 - Instrument Limits & Capabilities

## Quick Answer

**You can subscribe to up to 5,000 instruments** on a single WebSocket v3 connection (if using only one mode).

---

## Detailed Breakdown

### Subscription Limits (Per User)

| Scenario | Limit | Notes |
|----------|-------|-------|
| **Single Mode** (e.g., only 'LTPC') | **5,000 instruments** | Maximum for one subscription category |
| **Multiple Modes** (e.g., 'LTPC' + 'Option Greeks') | **2,000 instruments per mode** | When subscribing to multiple categories |
| **Full D30 Mode** (Upstox Plus) | **50 instruments per connection** | Premium mode with 30 market depth levels |

### Your Current Usage

Looking at your code in `/backend/app/core/market_data.py`:

```python
self.streamer = MarketDataStreamerV3(
    api_client=api_client,
    instrumentKeys=[
        'NSE_INDEX|Nifty 50',      # 1 instrument
        self.option_ce_key,         # 1 instrument (CE option)
        self.option_pe_key          # 1 instrument (PE option)
    ],
    mode="full"  # Full mode
)
```

**Current subscription:** Only **3 instruments** (Nifty 50 + 2 options)  
**Available capacity:** You can add **4,997 more instruments** in "full" mode!

---

## Subscription Modes

### 1. LTPC Mode (Default)
**Data provided:**
- Last Traded Price (LTP)
- Close Price (CP)

**Limit:** 5,000 instruments (single mode)

### 2. Full Mode (What you're using)
**Data provided:**
- LTP, LTT (Last Traded Time), LTQ (Last Traded Quantity), CP
- 5 market depth levels (bid/ask prices and quantities)
- Extended feed metadata
- **Option Greeks** (Delta, Gamma, Theta, Vega, IV)
- **Open Interest (OI)**

**Limit:** 5,000 instruments (single mode) or 2,000 (if using multiple modes)

### 3. Full D30 Mode (Upstox Plus - Premium)
**Data provided:**
- LTPC data
- **30 market depth levels** (vs 5 in regular Full mode)
- Extended feed metadata
- Option Greeks

**Limit:** 50 instruments per WebSocket connection

### 4. Option Greeks Mode
**Data provided:**
- Only Option Greeks data (Delta, Gamma, Theta, Vega, IV)

**Limit:** 5,000 instruments (single mode) or 2,000 (if using multiple modes)

---

## Connection Limits

| Account Type | Max WebSocket Connections |
|--------------|---------------------------|
| **Regular** | 2 connections per user |
| **Upstox Plus** | 5 connections per user |

**Note:** These limits are **per user**, not per app or access token.

---

## Implications for Your PCR Calculation

### Current Approach (Using HTTP API)
```python
# In get_nifty_pcr() - you fetch ~20-40 option contracts via HTTP
instrument_keys = relevant_opts['instrument_key'].tolist()  # ~20-40 instruments
greeks_data = self.get_option_greeks_batch(instrument_keys)  # HTTP API call
```

**Frequency:** Every 30 seconds  
**API:** `/v3/market-quote/option-greek` (HTTP)

### Potential WebSocket Approach ✨

Since you can subscribe to **5,000 instruments** in full mode, you could:

1. **Subscribe to ALL relevant option contracts** via WebSocket
2. **Get real-time OI updates** instead of polling every 30 seconds
3. **Eliminate the HTTP API calls** for PCR calculation

#### Example Implementation

```python
# Get all Nifty options in strike range
strike_range = 500
relevant_opts = future_opts[
    (future_opts['expiry'] == nearest_expiry) & 
    (future_opts['strike'] >= spot_price - strike_range) & 
    (future_opts['strike'] <= spot_price + strike_range)
]

# Get all instrument keys (~20-40 options)
option_keys = relevant_opts['instrument_key'].tolist()

# Subscribe to WebSocket (in addition to Nifty + ATM options)
all_instruments = [
    'NSE_INDEX|Nifty 50',
    *option_keys  # All options in strike range
]

self.streamer = MarketDataStreamerV3(
    api_client=api_client,
    instrumentKeys=all_instruments,  # ~23-43 instruments total
    mode="full"  # Includes OI data!
)
```

**Benefits:**
- ✅ Real-time OI updates (instead of 30-second polling)
- ✅ No HTTP API calls for PCR
- ✅ More accurate PCR calculation
- ✅ No rate limiting issues
- ✅ Still well within the 5,000 instrument limit

---

## What "Full" Mode Provides

When you use `mode="full"`, the WebSocket provides:

```python
{
  "feeds": {
    "NSE_FO|NIFTY25D0926050CE": {
      "fullFeed": {
        "marketFF": {
          "ltpc": {
            "ltp": 122.00,      # Last Traded Price
            "ltt": "...",        # Last Traded Time
            "ltq": 75,           # Last Traded Quantity
            "cp": 120.50         # Close Price
          },
          "marketOHLC": {
            "open": 121.00,
            "high": 123.50,
            "low": 119.00,
            "close": 122.00
          },
          "eFeedDetails": {
            "oi": 50000,         # ← Open Interest (for PCR!)
            "atp": 121.50,       # Average Traded Price
            "volume": 1250000,
            "totalBuyQty": 625000,
            "totalSellQty": 625000,
            "lowerCircuit": 100.00,
            "upperCircuit": 150.00
          },
          "optionGreeks": {      # ← Option Greeks (if you want them)
            "delta": 0.52,
            "gamma": 0.003,
            "theta": -15.2,
            "vega": 25.1,
            "iv": 18.5
          },
          "marketLevel": {       # 5 levels of market depth
            "bidAskQuote": [
              {"bq": 100, "bp": 121.95, "aq": 150, "ap": 122.05},
              // ... 4 more levels
            ]
          }
        }
      }
    }
  }
}
```

**You're already getting all this data!** You just need to extract the OI values.

---

## Comparison: V2 vs V3

| Feature | WebSocket V2 | WebSocket V3 |
|---------|--------------|--------------|
| Max Instruments | 100 | 5,000 |
| Encoding | JSON | Protobuf (more efficient) |
| Market Depth | 5 levels | 5 levels (Full) / 30 levels (Full D30) |
| Option Greeks | ❌ No | ✅ Yes |
| Open Interest | ❌ No | ✅ Yes |
| Performance | Good | Excellent |

---

## Recommendations for Your Application

### Current State
- ✅ Using WebSocket v3 for 3 instruments (Nifty + 2 ATM options)
- ⚠️ Using HTTP API for PCR (20-40 option contracts, every 30s)
- ⚠️ Using HTTP API for redundant quote fetches (causing rate limits)

### Optimization Strategy

#### Phase 1: Expand WebSocket Subscriptions
```python
# Subscribe to all options needed for PCR calculation
# Instead of: 3 instruments
# Use: ~23-43 instruments (Nifty + all options in strike range)
```

**Impact:**
- Real-time PCR updates (vs 30-second polling)
- Eliminate `/v3/market-quote/option-greek` HTTP calls
- More accurate and timely PCR data

#### Phase 2: Remove Redundant HTTP Calls
```python
# Remove get_quotes() calls for option prices
# Use WebSocket data instead (already available)
```

**Impact:**
- Eliminate rate limiting errors
- Reduce API usage
- Faster response times

#### Phase 3: Dynamic Subscription Management
```python
# When ATM changes, update option subscriptions
# Unsubscribe from old strike options
# Subscribe to new strike options
```

**Impact:**
- Always have relevant options subscribed
- Optimal use of WebSocket capacity

---

## Code Example: Enhanced WebSocket Setup

```python
async def start(self):
    # ... existing code ...
    
    # Get all option contracts for PCR calculation
    pcr_option_keys = self._get_pcr_option_keys(self.current_price)
    
    # Build comprehensive instrument list
    instrument_keys = [
        self.nifty_key,           # Nifty 50
        self.option_ce_key,       # ATM CE
        self.option_pe_key,       # ATM PE
        *pcr_option_keys          # All options for PCR (~20-40)
    ]
    
    logger.info(f"📊 Subscribing to {len(instrument_keys)} instruments via WebSocket")
    logger.info(f"   - Nifty 50: 1")
    logger.info(f"   - ATM Options: 2")
    logger.info(f"   - PCR Options: {len(pcr_option_keys)}")
    logger.info(f"   - Remaining capacity: {5000 - len(instrument_keys)}")
    
    # Initialize streamer with all instruments
    self.streamer = MarketDataStreamerV3(
        api_client=api_client,
        instrumentKeys=instrument_keys,
        mode="full"  # Includes OI + Greeks
    )
    
    # ... rest of setup ...

def _get_pcr_option_keys(self, spot_price):
    """Get all option instrument keys needed for PCR calculation."""
    if self.data_fetcher.instruments_df is None:
        return []
    
    # Get nearest expiry
    expiry = self.data_fetcher.get_nearest_expiry()
    if not expiry:
        return []
    
    # Get options in strike range
    strike_range = 500
    nifty_opts = self.data_fetcher.instruments_df[
        (self.data_fetcher.instruments_df['name'] == 'NIFTY') & 
        (self.data_fetcher.instruments_df['instrument_type'] == 'OPTIDX') &
        (self.data_fetcher.instruments_df['expiry'] == pd.to_datetime(expiry)) &
        (self.data_fetcher.instruments_df['strike'] >= spot_price - strike_range) &
        (self.data_fetcher.instruments_df['strike'] <= spot_price + strike_range)
    ]
    
    return nifty_opts['instrument_key'].tolist()
```

---

## Summary

| Question | Answer |
|----------|--------|
| **Max instruments in WebSocket v3?** | **5,000** (single mode) or **2,000** (multiple modes) |
| **Your current usage?** | **3 instruments** (0.06% of capacity) |
| **Can you add PCR options to WebSocket?** | **Yes!** You have room for 4,997 more |
| **Should you do this?** | **Absolutely!** It will eliminate rate limiting and improve PCR accuracy |

---

## Next Steps

Would you like me to:

1. ✅ **Implement WebSocket subscriptions for PCR options** (eliminate HTTP polling)
2. ✅ **Remove redundant `get_quotes()` calls** (fix rate limiting)
3. ✅ **Add dynamic subscription management** (update when ATM changes)

This will make your application:
- Faster (real-time vs 30-second polling)
- More reliable (no rate limits)
- More efficient (fewer API calls)
- More accurate (real-time OI data)
