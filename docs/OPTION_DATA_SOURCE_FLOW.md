# Option Data Calculations - Source Flow

## Overview
Your trading bot calculates Greeks and option data through a multi-layer architecture. Here's the complete flow:

---

## 1. **Data Source: Upstox API**

### Entry Point: `main.py` → `TradingBot`
```
TradingBot.initialize()
  ↓
DataFetcher(api_key, access_token)
  ↓
Upstox API Client (upstox_client SDK)
```

### API Endpoints Used:
- **Instrument Master**: `https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz`
  - Downloaded once per 24 hours
  - Contains all option contracts with strike, expiry, instrument_key
  
- **Historical Candles**: `GET /v2/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}`
  - Fetches OHLCV data for Nifty 50 index
  - Used by StrategyEngine for technical analysis
  
- **Market Quotes (LTP)**: `GET /v2/market-quote/ltp`
  - Real-time last traded price for options
  - Used to calculate Implied Volatility
  
- **Market Quotes (Full)**: `GET /v2/market-quote/quotes`
  - Full quote data including OI, volume, bid/ask
  - Used for PCR calculation and Greeks

---

## 2. **Greeks Calculation Pipeline**

### Flow Diagram:
```
Upstox API (Option Price)
  ↓
DataFetcher.get_option_greeks()
  ├─ Spot Price: get_current_price(NIFTY_50)
  ├─ Strike: get_atm_strike(spot_price)
  ├─ Expiry: get_nearest_expiry()
  ├─ Instrument Keys: get_option_instrument_key()
  └─ Option Prices: get_quotes([CE_key, PE_key])
  ↓
GreeksCalculator (Black-Scholes Model)
  ├─ Implied Volatility: implied_volatility(market_price, S, K, T)
  │   └─ Newton-Raphson method (100 iterations max)
  ├─ Greeks: calculate_greeks(S, K, T, sigma, option_type)
  │   ├─ Delta: norm.cdf(d1) or norm.cdf(d1) - 1
  │   ├─ Gamma: norm.pdf(d1) / (S * sigma * sqrt(T))
  │   ├─ Theta: (per day) annual theta / 365
  │   ├─ Vega: S * sqrt(T) * norm.pdf(d1) / 100
  │   ├─ Rho: K * T * exp(-r*T) * norm.cdf(d2) / 100
  │   └─ Quality Score: _calculate_quality_score()
  └─ Return: {delta, gamma, theta, vega, rho, quality_score, iv, price}
```

### Key Inputs:
| Input | Source | Format |
|-------|--------|--------|
| **S (Spot Price)** | Upstox API LTP | Float (e.g., 23500.50) |
| **K (Strike)** | Instrument Master CSV | Float (e.g., 23500.00) |
| **T (Time to Expiry)** | Calculated from expiry date | Years (e.g., 0.0274 = 10 days) |
| **σ (Volatility)** | Calculated from market price | Decimal (e.g., 0.25 = 25%) |
| **r (Risk-free Rate)** | Config (default 0.06) | Decimal (6% annual) |

---

## 3. **Greeks Quality Score Calculation**

### Scoring Breakdown (0-100):

**1. Moneyness (0-30 points)**
- Very ATM (< 1% diff): 30 pts
- ATM (< 5% diff): 25 pts
- Near ATM (< 10% diff): 20 pts
- Slightly OTM/ITM (< 20% diff): 10 pts
- Far OTM/ITM (> 20% diff): 0 pts

**2. Time to Expiry (0-30 points)**
- Optimal (5-30 days): 30 pts
- Good (2-5 or 30-60 days): 20 pts
- Fair (1-2 or 60-90 days): 10 pts
- Poor (< 1 or > 90 days): 0 pts

**3. Volatility (0-20 points)**
- Reasonable (10-100% IV): 20 pts
- Moderate (5-10% or 100-150% IV): 10 pts
- Extreme (< 5% or > 150% IV): 0 pts

**4. Greeks Stability (0-20 points)**
- Good gamma/vega (0.0001-0.01 gamma, 0.01-1.0 vega): 20 pts
- Positive gamma/vega: 10 pts
- Invalid: 0 pts

**Total Score = Sum of all categories (0-100)**

### Quality Thresholds:
- **0-25**: Poor (don't trade)
- **25-50**: Fair (risky)
- **50-75**: Good (acceptable)
- **75-100**: Excellent (ideal)

---

## 4. **Strategy Integration**

### Where Greeks are Used:

**In `strategy.py` → `analyze_signal()`:**
```python
# Line 121-135: Greeks Filter
if not backtest_mode and greeks:
    ce_quality = greeks.get('ce', {}).get('quality_score', 0)
    pe_quality = greeks.get('pe', {}).get('quality_score', 0)
    
    # Require minimum quality score of 50 (Fair or better)
    greeks_bullish = ce_quality >= 50
    greeks_bearish = pe_quality >= 50
    
    filter_checks['greeks'] = greeks_bullish or greeks_bearish
```

**Signal Generation:**
- **BUY_CE**: All filters pass + greeks_bullish (CE quality ≥ 50)
- **BUY_PE**: All filters pass + greeks_bearish (PE quality ≥ 50)
- **HOLD**: Any filter fails

---

## 5. **Data Flow in Real-Time**

### During Live Trading:

```
1. MarketDataManager (async)
   └─ Subscribes to Nifty 50 via WebSocket
   └─ Emits price updates every tick

2. StrategyRunner (sync)
   └─ Receives price update
   └─ Calls StrategyEngine.analyze_signal()
   └─ Fetches Greeks via DataFetcher.get_option_greeks()
   └─ Returns signal (BUY_CE, BUY_PE, or HOLD)

3. TradeExecutor (async)
   └─ Receives signal
   └─ Executes trade via OrderManager
   └─ Manages position and risk

4. Status Broadcast
   └─ Sends complete state to frontend
   └─ Includes Greeks, signal, reasoning
```

---

## 6. **Calculation Accuracy**

### Black-Scholes Model Used:
- **Formula**: Standard European option pricing
- **Assumptions**: 
  - European options (exercise only at expiry)
  - No dividends
  - Constant volatility
  - Log-normal distribution of returns

### Implied Volatility Calculation:
- **Method**: Newton-Raphson iteration
- **Convergence**: < 1e-5 precision or 100 iterations max
- **Initial Guess**: Heuristic based on time value
  ```
  sigma = sqrt(2π/T) * (time_value / S)
  sigma = clipped to [0.01, 2.0]
  ```

### Accuracy Factors:
✅ **Good**:
- Uses actual market prices from Upstox
- Spot price is real-time
- Expiry date is accurate

⚠️ **Potential Issues**:
- IV calculation assumes European options (NSE uses American)
- Risk-free rate is fixed (0.06) - doesn't change with market
- Doesn't account for dividends
- Greeks are point-in-time (change with every tick)

---

## 7. **Configuration**

### In `config.py`:
```python
SYMBOL_NIFTY_50 = "NSE_INDEX|99926009"
TIMEFRAME = "5minute"
RISK_FREE_RATE = 0.06  # Used in Greeks calculation
```

### In `.env`:
```
UPSTOX_API_KEY=<your_api_key>
UPSTOX_ACCESS_TOKEN=<your_access_token>
UPSTOX_REDIRECT_URI=<your_redirect_uri>
```

---

## 8. **Troubleshooting**

### If Greeks Quality is Poor:

1. **Check Spot Price**
   - Verify it's current (not stale)
   - Should match NSE index price

2. **Check Option Prices**
   - Ensure LTP is valid (not 0)
   - Verify bid-ask spread is reasonable

3. **Check Expiry Date**
   - Verify format is YYYY-MM-DD
   - Ensure it's a valid trading expiry

4. **Check IV Convergence**
   - If IV is extreme (< 5% or > 200%), Greeks will be poor
   - Check if market price is realistic

5. **Compare with Broker**
   - Get Greeks from Upstox/NSE directly
   - Compare calculated vs actual
   - Identify systematic bias

---

## 9. **Key Files**

| File | Purpose |
|------|---------|
| `backend/app/core/greeks.py` | Black-Scholes calculations |
| `backend/app/data/data_fetcher.py` | Upstox API integration |
| `backend/app/strategies/strategy.py` | Signal generation with Greeks filter |
| `backend/main.py` | Bot orchestration |
| `backend/app/core/market_data.py` | Real-time price streaming |

---

## Summary

**Option data calculations are sourced from:**
1. **Upstox API** - Real-time prices and instrument data
2. **Black-Scholes Model** - Greeks calculations
3. **Newton-Raphson** - Implied Volatility calculation
4. **Quality Scoring** - Evaluates Greeks reliability

**The flow is:**
```
Upstox API → DataFetcher → GreeksCalculator → StrategyEngine → Signal
```

All calculations are based on **real market data**, not mock data.
