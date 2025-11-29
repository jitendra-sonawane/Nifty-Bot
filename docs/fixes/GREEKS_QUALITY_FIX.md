# Greeks Quality Issues - Analysis & Fixes

## Problems Found

### 1. **Parameter Mismatch in Function Calls** ❌ FIXED
**Problem**: The `option_data_handler.py` was calling Greeks functions with incorrect parameter names:
- Called `implied_volatility(option_price=..., spot_price=..., strike=..., time_to_expiry=...)`
- But function signature expects: `implied_volatility(market_price, S, K, T, ...)`
- Called `calculate_greeks(spot_price=..., strike=..., time_to_expiry=..., volatility=...)`
- But function signature expects: `calculate_greeks(S, K, T, sigma, ...)`

**Impact**: These mismatches could cause silent failures or incorrect calculations.

**Fix**: Updated parameter names in option_data_handler.py to match function signatures:
```python
# Before
iv = self.greeks_calc.implied_volatility(
    option_price=last_price,
    spot_price=spot_price,
    strike=option_info['strike'],
    time_to_expiry=time_to_expiry,
    ...
)

# After
iv = self.greeks_calc.implied_volatility(
    market_price=last_price,
    S=spot_price,
    K=option_info['strike'],
    T=time_to_expiry,
    ...
)
```

---

### 2. **Poor IV Initial Guess** ❌ FIXED
**Problem**: IV calculation started with fixed guess of `sigma = 0.5` (50%)
- For OTM options, this is way too high and causes slow/failed convergence
- For ITM options, might be too low

**Impact**: IV Newton-Raphson iterations fail to converge properly for many options.

**Fix**: Implemented intelligent initial guess:
```python
# Better heuristic using time value
intrinsic = max(S - K, 0) if option_type == 'CE' else max(K - S, 0)
time_value = market_price - intrinsic

if time_value <= 0:
    return 0.01  # At/below intrinsic value

# Use heuristic for initial guess
sigma = np.sqrt(2 * np.pi / T) * (time_value / S) if T > 0 else 0.3
sigma = np.clip(sigma, 0.01, 2.0)  # Keep in bounds (1-200%)
```

This adapts based on option's moneyness and time value.

---

### 3. **Insufficient Risk-Free Rate Flexibility** ❌ FIXED
**Problem**: 
- `calculate_greeks()` didn't accept `risk_free_rate` parameter
- Hard-coded `self.r` (default 0.07) with no override capability

**Impact**: Can't use accurate rates for different scenarios; Greeks calculations locked to default rate.

**Fix**: Added optional `risk_free_rate` parameter to:
- `calculate_greeks()`
- `black_scholes_price()`
- `implied_volatility()`

Now you can override per call or use instance default.

---

### 4. **Vega Normalization** ⚠️ PARTIALLY FIXED
**Problem**: Vega divided by 100 but raw calculation already contains large multipliers
- Formula: `S * sqrt(T) * N'(d1) / 100`
- This may still produce counter-intuitive values

**Current behavior**: Vega normalized as "per 1% IV change" which is correct for reporting, but verify if output matches your trading platform's convention.

**Recommendation**: Compare against NSE/broker Greeks to verify scale is correct.

---

### 5. **Theta Normalization** ✓ CORRECT
**Problem**: Theta divided by 365 for per-day value
- This is correct for most platforms (theta decays annually, report as daily)

**Status**: No change needed - this is right.

---

### 6. **Division by Zero Risks** ⚠️ PARTIALLY FIXED
**Problem**: Multiple places where `gamma = norm.pdf(d1) / (S * sigma * sqrt(T))` could fail:
- S = 0 (spot price is zero)
- sigma = 0 (zero volatility)
- T = 0 (expiry reached)

**Fixes Applied**:
```python
# Gamma calculation with guards
if sigma > 0 and S > 0:
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
else:
    gamma = 0

# IV with bounds
sigma = np.clip(sigma, 0.001, 5.0)  # Stay between 0.1% and 500%

# IV fallback
if vega < 1e-10:
    return max(round(sigma, 4), 0.0001)
```

---

## Summary of Changes

| Component | Issue | Fix |
|-----------|-------|-----|
| `greeks.py` | Poor IV convergence | Better initial guess, bounds checking |
| `greeks.py` | Missing risk_free_rate param | Added optional override parameter |
| `greeks.py` | Division by zero risks | Added safety guards |
| `option_data_handler.py` | Wrong parameter names | Corrected to match signatures |
| Greeks calculation | Low precision in some cases | Improved numerical stability |

---

## Testing Recommendations

1. **Compare with market Greeks**:
   ```bash
   python3 backend/tests/test_greeks.py
   ```
   Compare output against NSE/Upstox live Greeks

2. **Check IV convergence**:
   - Log IV calculation iterations
   - Verify convergence happens in < 20 iterations for most options
   - Watch for OTM options converging properly

3. **Verify Greek signs**:
   - Delta: CE should be 0-1, PE should be -1-0
   - Gamma: Always positive
   - Theta: CE usually negative, PE usually positive
   - Vega: Usually positive (both CE & PE gain value with higher IV)
   - Rho: CE positive, PE negative

4. **Test edge cases**:
   - Deep ITM options
   - Deep OTM options
   - Options near expiry (T < 0.01)
   - Very high/low spot vs strike

---

## What's NOT Changed

- Black-Scholes formula itself (mathematically correct)
- d1/d2 calculations (these are standard)
- Core Greeks formulas (these match literature)

---

## Next Steps if Greeks Still Poor

If Greeks quality is still poor after these fixes:

1. **Check IV source**:
   - Verify market price being used is actual LTP (not bid/ask)
   - Check if using correct bid-ask spread

2. **Check spot price**:
   - Ensure spot price is current (not stale)
   - Verify it's the exact NSE index price

3. **Check expiry date**:
   - Verify expiry date format is correct (YYYY-MM-DD)
   - Ensure time calculation includes market holidays

4. **Compare methodologies**:
   - Get Greeks from NSE/broker for same option
   - Compare calculated IV vs broker's IV
   - Identify systematic bias

5. **Use market IV**:
   - If available, use broker's IV instead of calculating from price
   - Use that directly in Greeks calculation (skip IV calculation step)
