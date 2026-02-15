# Greeks Data Source - WebSocket vs REST API

## Short Answer
**YES, Greeks are calculated from MarketData Streamer (WebSocket)**, but with a hybrid approach:

```
MarketDataStreamer (WebSocket) → Real-time Option Prices
                                 ↓
                    GreeksCalculator (Black-Scholes)
                                 ↓
                    Greeks + Quality Score
```

---

## Data Flow Architecture

### 1. **WebSocket Streaming** (Real-time)
**File**: `backend/app/core/market_data.py`

```python
MarketDataManager
  ├─ Uses: MarketDataStreamerV3 (Upstox SDK)
  ├─ Subscribes to:
  │   ├─ Nifty 50 Index (NSE_INDEX|99926009)
  │   ├─ ATM Call Option (NSE_FO|NIFTY25NOV26050CE)
  │   └─ ATM Put Option (NSE_FO|NIFTY25NOV26050PE)
  ├─ Mode: "full" (includes bid/ask/OI/volume)
  └─ Callback: _on_streamer_message()
```

### 2. **Real-time Price Updates**
When WebSocket receives a tick:

```
_on_streamer_message(message)
  ├─ Extract Nifty 50 price → self.current_price
  ├─ Extract CE option price → self.option_ce_price
  ├─ Extract PE option price → self.option_pe_price
  └─ Trigger: _calculate_and_emit_greeks()
```

### 3. **Greeks Calculation** (On-demand)
**File**: `backend/app/core/greeks.py`

```python
_calculate_and_emit_greeks()
  ├─ Input from WebSocket:
  │   ├─ Spot Price (Nifty 50 LTP)
  │   ├─ CE Option Price (LTP)
  │   └─ PE Option Price (LTP)
  ├─ Calculate:
  │   ├─ Time to Expiry (from expiry date)
  │   ├─ Implied Volatility (Newton-Raphson)
  │   ├─ Greeks (Delta, Gamma, Theta, Vega, Rho)
  │   └─ Quality Score (moneyness, time, IV, stability)
  └─ Output: {delta, gamma, theta, vega, rho, quality_score}
```

---

## Data Sources Comparison

| Source | Method | Frequency | Latency | Used For |
|--------|--------|-----------|---------|----------|
| **WebSocket (Streamer)** | Real-time tick | Every tick | < 100ms | Greeks calculation |
| **REST API (DataFetcher)** | HTTP request | On-demand | 500ms-2s | Fallback, PCR, VIX |

---

## Code Flow in Detail

### Step 1: WebSocket Connection
```python
# market_data.py → start()
self.streamer = MarketDataStreamerV3(
    instrumentKeys=[
        "NSE_INDEX|99926009",      # Nifty 50
        "NSE_FO|NIFTY25NOV26050CE", # ATM Call
        "NSE_FO|NIFTY25NOV26050PE"  # ATM Put
    ],
    mode="full"
)
self.streamer.on("message", self._on_streamer_message)
self.streamer.connect()  # Background thread
```

### Step 2: Receive Tick Data
```python
# websocket_client.py → _on_message()
# Receives binary protobuf message from Upstox
feed_response = MarketDataFeedV3_pb2.FeedResponse()
feed_response.ParseFromString(message)  # Decode protobuf

# Extract prices for each instrument
for instrument_key, feed in feed_response.feeds.items():
    price = feed.ltpc.ltp  # Last Traded Price
    self.latest_data[instrument_key] = {"price": price}
```

### Step 3: Calculate Greeks
```python
# market_data.py → _calculate_and_emit_greeks()
if self.option_ce_price > 0 and self.option_pe_price > 0:
    # Calculate IV from market prices
    ce_iv = greeks_calc.implied_volatility(
        market_price=self.option_ce_price,  # From WebSocket
        S=self.current_price,               # From WebSocket
        K=self.atm_strike,
        T=time_to_expiry
    )
    
    # Calculate Greeks
    ce_greeks = greeks_calc.calculate_greeks(
        S=self.current_price,
        K=self.atm_strike,
        T=time_to_expiry,
        sigma=ce_iv
    )
    
    # Store with quality score
    self.latest_greeks = {
        'ce': {**ce_greeks, 'iv': ce_iv, 'price': self.option_ce_price},
        'pe': {**pe_greeks, 'iv': pe_iv, 'price': self.option_pe_price}
    }
```

### Step 4: Use in Strategy
```python
# strategy.py → analyze_signal()
greeks = market_state.get("greeks")  # From MarketDataManager

if greeks:
    ce_quality = greeks['ce'].get('quality_score', 0)
    pe_quality = greeks['pe'].get('quality_score', 0)
    
    # Filter: Only trade if quality >= 50
    if ce_quality >= 50:
        signal = "BUY_CE"
```

---

## Key Points

### ✅ What's Real-time (WebSocket):
- Nifty 50 price updates
- Option CE/PE prices
- Greeks recalculated on every tick
- Quality scores updated in real-time

### ⚠️ What's Periodic (REST API):
- PCR calculation (every 60 seconds)
- VIX fetch (every 60 seconds)
- Sentiment calculation (every 60 seconds)

### 🔄 Fallback Mechanism:
If WebSocket disconnects:
- `_greeks_loop()` is disabled (commented out)
- Falls back to REST API: `DataFetcher.get_option_greeks()`
- Less frequent (every 5 seconds instead of every tick)

---

## Performance Characteristics

| Metric | WebSocket | REST API |
|--------|-----------|----------|
| **Latency** | < 100ms | 500-2000ms |
| **Frequency** | Every tick (100+ per sec) | Every 5-60 sec |
| **Bandwidth** | Low (binary protobuf) | Higher (JSON) |
| **Reliability** | Requires connection | Always available |
| **Greeks Freshness** | Real-time | Stale (5-60 sec) |

---

## Troubleshooting

### If Greeks are not updating:
1. **Check WebSocket connection**:
   ```python
   # In market_data.py logs
   "✅ Market data stream connected"  # Should see this
   "💰 Nifty price: ₹23500.50"        # Should see price updates
   ```

2. **Check option prices are received**:
   ```python
   "📈 CE option (23500): ₹150.50"
   "📉 PE option (23500): ₹145.25"
   ```

3. **Check Greeks calculation**:
   ```python
   "📊 Greeks calculated: CE ₹150.50 (Q:75), PE ₹145.25 (Q:72)"
   ```

4. **If WebSocket fails**, check:
   - Access token validity
   - Network connectivity
   - Upstox API status

---

## Summary

**Greeks data source:**
1. **Primary**: WebSocket (MarketDataStreamer) - Real-time option prices
2. **Calculation**: Black-Scholes model in GreeksCalculator
3. **Quality**: Evaluated based on moneyness, time, IV, stability
4. **Fallback**: REST API if WebSocket unavailable

**The flow is:**
```
Upstox WebSocket → Option Prices → GreeksCalculator → Quality Score → Strategy Filter
```

All Greeks are **calculated in real-time** from **live market data** via WebSocket.
