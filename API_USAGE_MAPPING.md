# API Usage Mapping - Complete Breakdown

## Overview
Your application uses a combination of **Upstox v2 APIs**, **Upstox v3 APIs**, and **WebSocket streaming** for different purposes.

---

## 1. Historical Data (EMA Calculation)

### Purpose
Fetch historical candle data to calculate technical indicators (EMA, MACD, RSI, etc.)

### API Used
**Upstox v3 Historical Candle API**
- **Endpoint:** `GET /v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}`
- **Method:** `DataFetcher.get_historical_data()`
- **Location:** `/backend/app/data/data_fetcher.py` (lines 192-265)

### Usage Pattern
```python
# Called by: StrategyRunner._run_strategy()
df = self.data_fetcher.get_historical_data(
    'NSE_INDEX|Nifty 50', 
    '5minute',  # interval (parsed to: unit='minutes', interval='5')
    '2025-11-29',  # from_date
    '2025-12-04'   # to_date
)
```

### Frequency
- Called **every time price updates** (via StrategyRunner)
- Approximately **every 1-2 seconds** when market is active
- Returns: OHLCV data + Open Interest

### Data Returned
```json
{
  "data": {
    "candles": [
      ["2025-12-04T09:15:00", 26000, 26050, 25990, 26040, 1000000, 5000000],
      // [timestamp, open, high, low, close, volume, oi]
    ]
  }
}
```

---

## 2. Real-time Prices (Nifty 50 + Options)

### Purpose
Get real-time price updates for Nifty 50 index and ATM option contracts (CE/PE)

### API Used
**Upstox WebSocket v3 (MarketDataStreamerV3)**
- **Protocol:** WebSocket with Protobuf encoding
- **SDK:** `upstox_client.feeder.market_data_streamer_v3.MarketDataStreamerV3`
- **Location:** `/backend/app/core/market_data.py` (lines 115-158)

### Usage Pattern
```python
# Initialization in MarketDataManager.start()
self.streamer = MarketDataStreamerV3(
    api_client=api_client,
    instrumentKeys=[
        'NSE_INDEX|Nifty 50',      # Nifty 50 index
        'NSE_FO|46807',             # CE option (ATM)
        'NSE_FO|46808'              # PE option (ATM)
    ],
    mode="full"  # Full mode includes bid/ask/OI
)

# Callbacks
self.streamer.on("message", self._on_streamer_message)
```

### Frequency
- **Continuous streaming** (real-time)
- Updates received as market data changes
- Typically **multiple updates per second** during active trading

### Data Received
```python
{
  "feeds": {
    "NSE_INDEX|Nifty 50": {
      "fullFeed": {
        "indexFF": {
          "ltpc": {"ltp": 26040.50}  # Last Traded Price
        }
      }
    },
    "NSE_FO|46807": {
      "fullFeed": {
        "marketFF": {
          "ltpc": {"ltp": 122.00, "ltt": "...", "cp": 120.50},
          "marketOHLC": {...},
          "eFeedDetails": {"oi": 50000}  # Open Interest
        }
      }
    }
  }
}
```

### What It's Used For
1. **Nifty 50 current price** → Triggers strategy checks
2. **CE option price** → Used for Greeks calculation
3. **PE option price** → Used for Greeks calculation
4. **Open Interest** → Available but not currently used for Greeks

---

## 3. Greeks Calculation (Current Implementation)

### Purpose
Calculate option Greeks (Delta, Gamma, Theta, Vega) for ATM options

### Current Method
**Calculated locally using Black-Scholes model**
- **Location:** `/backend/app/core/greeks.py`
- **Triggered by:** WebSocket price updates
- **Method:** `MarketDataManager._calculate_and_emit_greeks()`

### Data Sources
1. **Option Prices** → From WebSocket (see #2 above)
2. **Spot Price** → From WebSocket (Nifty 50)
3. **Strike Price** → Calculated ATM strike
4. **Time to Expiry** → Calculated from expiry date
5. **Implied Volatility** → Calculated using Newton-Raphson method

### Process Flow
```
WebSocket Update (CE/PE prices)
    ↓
_on_streamer_message() receives prices
    ↓
_calculate_and_emit_greeks()
    ↓
Calculate IV using option price + Black-Scholes
    ↓
Calculate Greeks using IV + Black-Scholes
    ↓
Emit to frontend
```

### Frequency
- Calculated **every time option prices update** via WebSocket
- Approximately **every 1-2 seconds** during active trading

---

## 4. PCR (Put-Call Ratio) Calculation

### Purpose
Calculate market sentiment using Put-Call Ratio from Open Interest data

### API Used
**Upstox v3 Option Greek API** (Note: This is for OI data, not Greeks calculation)
- **Endpoint:** `GET /v3/market-quote/option-greek`
- **Method:** `DataFetcher.get_option_greeks_batch()`
- **Location:** `/backend/app/data/data_fetcher.py` (lines 502-532)

### Usage Pattern
```python
# Called by: DataFetcher.get_nifty_pcr()
instrument_keys = [
    'NSE_FO|NIFTY25D0926050CE',
    'NSE_FO|NIFTY25D0926050PE',
    # ... all options in strike range (±500 from spot)
]

greeks_data = self.get_option_greeks_batch(instrument_keys)
```

### Frequency
- Called **every 30 seconds** (via `_pcr_loop()` in market_data.py)
- Fetches data for **~20-40 option contracts** (all strikes in range)

### Data Returned
```json
{
  "data": {
    "NSE_FO:NIFTY25D0926050CE": {
      "oi": 50000,           // Open Interest ← THIS IS WHAT WE USE
      "ohlc": {
        "open": 120,
        "high": 125,
        "low": 118,
        "close": 122,
        "oi": 50000
      },
      "greeks": {            // These are provided but NOT used
        "delta": 0.52,
        "gamma": 0.003,
        "theta": -15.2,
        "vega": 25.1,
        "iv": 18.5
      }
    }
  }
}
```

### What It's Used For
```python
# Extract OI for all CE and PE options
total_ce_oi = sum(all CE open interest)
total_pe_oi = sum(all PE open interest)

# Calculate PCR
pcr = total_pe_oi / total_ce_oi
```

### Why This API?
The Option Greek API is used **NOT for Greeks** but because it's the **only API that provides Open Interest (OI) data** for multiple option contracts in a single call.

---

## 5. Market Quotes (Redundant - Causing Rate Limit)

### Purpose
Fetch current market quotes (LTP, bid, ask, etc.)

### API Used
**Upstox v2 Market Quote API** ⚠️ **REDUNDANT**
- **Endpoint:** `GET /v2/market-quote/quotes`
- **Method:** `DataFetcher.get_quotes()`
- **Location:** `/backend/app/data/data_fetcher.py` (lines 405-441)

### Current Usage (Problematic)
```python
# Called from multiple places:

# 1. get_option_greeks() - Line 572
quotes = self.get_quotes([ce_key, pe_key])
ce_price = quotes.get(ce_key, {}).get('last_price', 0)
pe_price = quotes.get(pe_key, {}).get('last_price', 0)

# 2. TradingBot._on_price_update() - main.py line 136
quotes = self.data_fetcher.get_quotes(keys)
current_prices = {k: v.get('last_price', 0) for k, v in quotes.items()}

# 3. TradingBot.get_status() - main.py line 187
quotes = self.data_fetcher.get_quotes(keys)
```

### Frequency
- Called **every 1-2 seconds** ⚠️ **TOO FREQUENT**
- This is causing the **429 Rate Limit errors**

### Why It's Redundant
You're already getting the same price data from WebSocket (#2 above), so these HTTP calls are unnecessary.

---

## 6. VIX (Volatility Index)

### Purpose
Get current India VIX value for sentiment analysis

### API Used
**Upstox v2 Market Quote LTP API**
- **Endpoint:** `GET /v2/market-quote/ltp`
- **Method:** `DataFetcher.get_india_vix()` → calls `get_current_price()`
- **Location:** `/backend/app/data/data_fetcher.py` (lines 380-384)

### Usage Pattern
```python
# Called by: MarketDataManager._pcr_loop()
vix = await loop.run_in_executor(None, self.data_fetcher.get_india_vix)
```

### Frequency
- Called **every 30 seconds** (same loop as PCR)

### Data Returned
```json
{
  "data": {
    "NSE_INDEX|India VIX": {
      "last_price": 14.25
    }
  }
}
```

---

## Complete API Usage Summary Table

| Purpose | API | Endpoint | Method | Frequency | Status |
|---------|-----|----------|--------|-----------|--------|
| **Historical Data (EMA)** | Upstox v3 Historical | `/v3/historical-candle/...` | `get_historical_data()` | Every 1-2s | ✅ Working (Fixed) |
| **Real-time Prices** | WebSocket v3 | WebSocket Stream | `MarketDataStreamerV3` | Continuous | ✅ Working |
| **Greeks Calculation** | Local (Black-Scholes) | N/A | `GreeksCalculator` | Every 1-2s | ✅ Working |
| **PCR (OI Data)** | Upstox v3 Option Greek | `/v3/market-quote/option-greek` | `get_option_greeks_batch()` | Every 30s | ✅ Working |
| **VIX** | Upstox v2 LTP | `/v2/market-quote/ltp` | `get_india_vix()` | Every 30s | ✅ Working |
| **Market Quotes** | Upstox v2 Quotes | `/v2/market-quote/quotes` | `get_quotes()` | Every 1-2s | ⚠️ **REDUNDANT** |

---

## Key Insights

### ✅ What's Working Well

1. **WebSocket for real-time prices** - Efficient, no rate limits
2. **v3 Historical API for EMA** - Now fixed with correct interval format
3. **Local Greeks calculation** - Fast, no API calls needed
4. **PCR calculation** - Smart use of Option Greek API for OI data

### ⚠️ What Needs Fixing

1. **`get_quotes()` is redundant** - You're already getting prices from WebSocket
2. **Rate limiting on quotes API** - Calling it too frequently (every 1-2s)
3. **Historical data called too often** - Could be cached for 1-5 minutes

### 💡 Optimization Opportunities

1. **Remove `get_quotes()` calls** - Use WebSocket prices instead
2. **Cache historical data** - Don't fetch every second, cache for 1-5 minutes
3. **Use WebSocket OI** - The WebSocket already provides OI data in "full" mode

---

## Clarification on "Option Greek API"

**Important:** The `/v3/market-quote/option-greek` API is named "Option Greek" but you're using it **primarily for Open Interest (OI) data**, NOT for the Greeks themselves.

- **API provides:** OI, OHLC, and Greeks
- **You use:** Only the OI values
- **You calculate:** Greeks locally using Black-Scholes

This is actually a good approach because:
1. Upstox's Greeks might not match your strategy's assumptions
2. Local calculation gives you full control
3. You can validate and adjust the Greeks as needed

---

## Recommended Next Steps

1. **Immediate:** Add caching to `get_quotes()` to stop rate limiting
2. **Short-term:** Remove redundant `get_quotes()` calls, use WebSocket data
3. **Medium-term:** Cache historical data for 1-5 minutes
4. **Long-term:** Consider using WebSocket OI data instead of Option Greek API

Would you like me to implement any of these optimizations?
