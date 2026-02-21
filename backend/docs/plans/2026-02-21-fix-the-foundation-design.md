# Fix the Foundation: Indicator Accuracy, Data Pipeline & Strategy Logic

**Date:** 2026-02-21
**Status:** Approved
**Approach:** Fix existing calculations and data flow before adding new features

---

## Problem Statement

A comprehensive audit of the Nifty-50 Options Trading Bot revealed 14 issues across three categories: indicator calculation accuracy, data pipeline integrity, and strategy decision logic. The bot currently uses non-standard formulas for RSI, ATR, and Supertrend; has broken volume data and an IV Rank bug; and contains several strategy logic inconsistencies. These issues cause the bot's signals to diverge from what standard charting platforms would show for the same market data.

---

## Audit Summary

### Critical / High Priority

| # | Issue | Category | Impact |
|---|-------|----------|--------|
| 1 | RSI uses SMA instead of Wilder's smoothing | Indicator | RSI values differ from standard by 5-10 points; threshold checks (>55, <45) produce wrong results |
| 6 | Volume always 0 in live streaming | Data Pipeline | No volume confirmation for any trades; volume ratio always NaN or 1.0 |
| 7 | IV Rank includes current IV in its own range | Data Pipeline | IV Rank readings are incorrect; docstring contradicts implementation |

### Medium Priority

| # | Issue | Category | Impact |
|---|-------|----------|--------|
| 2 | ATR uses SMA instead of Wilder's | Indicator | Inconsistent with market_regime.py which uses correct Wilder's ATR |
| 3 | Supertrend ATR uses SMA | Indicator | Supertrend bands differ from standard charting tools |
| 8 | Thread safety between WebSocket and strategy | Data Pipeline | Race conditions on shared dicts (pcr_oi_data, greeks, instrument_prices) |
| 9 | Timezone handling assumes naive = IST | Data Pipeline | Could cause 5.5hr offset if Upstox returns UTC-naive timestamps |
| 11 | PCR docstring inverted vs code | Strategy | Confusing for maintenance; raw vs contrarian interpretation mismatch |
| 12 | EMA filter is trend confirmation, not crossover | Strategy | Filter passes anytime short EMA > long EMA, not just on fresh crossovers |

### Low Priority

| # | Issue | Category | Impact |
|---|-------|----------|--------|
| 4 | ADX +DM/-DM first-row NaN propagation | Indicator | Minor impact on early ADX values |
| 5 | IV Newton-Raphson can oscillate | Indicator | Edge case for deep OTM options |
| 10 | PCR OI data freshness | Data Pipeline | Mix of fresh and stale OI values across strikes |
| 13 | Breakout requires two consecutive breaks | Strategy | Overly conservative; misses valid breakouts |
| 14 | Support/Resistance too noisy | Strategy | Many micro-swing levels; frontend clutter |

---

## Design: Three-Phase Fix

### Phase 1: Fix Indicator Calculations

**Goal:** Align RSI, ATR, and Supertrend with industry-standard (Wilder's) implementations.

#### 1.1 RSI Fix

**File:** `app/strategies/strategy.py` method `calculate_rsi`

**Current (SMA-based):**
```python
gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
```

**Corrected (Wilder's smoothing):**
```python
gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
```

**Why:** Wilder's smoothing gives more weight to recent data and produces smoother RSI that doesn't "jump" when old candles drop out of the window. This is the standard used by TradingView, Zerodha Kite, and all major platforms.

#### 1.2 ATR Fix

**File:** `app/strategies/strategy.py` method `calculate_atr`

Replace `.rolling(window=period).mean()` with `.ewm(alpha=1/period, adjust=False).mean()` on line 181.

This also ensures consistency with `market_regime.py` which already uses the correct Wilder's ATR.

#### 1.3 Supertrend ATR Fix

**File:** `app/strategies/strategy.py` method `calculate_supertrend`

Replace line 66 `atr = tr.rolling(window=period).mean()` with `atr = tr.ewm(alpha=1/period, adjust=False).mean()`.

#### 1.4 IV Newton-Raphson Dampening

**File:** `app/core/greeks.py` method `implied_volatility`

Add dampening factor to prevent oscillation:
```python
sigma = sigma + 0.7 * (diff / vega)  # 0.7 dampening factor
```

Add bisection fallback after 50 N-R iterations:
- If N-R hasn't converged after 50 iterations, switch to bisection method with bounds [0.001, 5.0]
- Bisection is slower but guaranteed to converge

#### Phase 1 Verification

After applying these fixes:
1. Run the bot during market hours
2. Compare RSI values with TradingView for the same 5-minute Nifty candles
3. Verify Supertrend direction matches TradingView
4. Values should be within 1-2 points of TradingView (minor differences expected due to historical data depth)

---

### Phase 2: Fix Data Pipeline

#### 2.1 IV Rank Bug Fix

**File:** `app/intelligence/iv_rank.py` method `update`

**Current (buggy):**
```python
self._history.append(self._current_iv)       # Adds current to history first
self._last_history_update_time = now
self.save_state()
self._compute()                               # Then computes rank INCLUDING current
```

**Corrected:**
```python
self._compute()                               # Compute rank against EXISTING history
if now - self._last_history_update_time >= interval:
    self._history.append(self._current_iv)    # Then add to history for future
    self._last_history_update_time = now
    self.save_state()
```

This ensures current IV is compared against the historical range WITHOUT including itself, matching the documented behavior.

#### 2.2 Hybrid Volume Proxy

**Decision:** Use ATM option combined volume (CE+PE) for activity measurement, plus enhance market breadth module with volume weighting.

**Rationale:** Nifty 50 is a calculated index with no trading volume. ATM option volume is the best readily available proxy.

**Changes:**

**market_data.py:**
- Add `self.synthetic_volume: float = 0.0` to state
- After processing ATM option prices, calculate: `self.synthetic_volume = pcr_volume_data.get(ce_key, 0) + pcr_volume_data.get(pe_key, 0)`
- Include `synthetic_volume` in `get_market_state()` return dict

**strategy_runner.py:**
- Change `candle_manager.update(current_price, volume=0)` to `candle_manager.update(current_price, volume=market_state.get('synthetic_volume', 0))`

**market_breadth.py (enhancement):**
- Track per-stock volume from `nifty50_quotes` (volume field is already captured from WebSocket)
- Maintain a 20-period rolling average volume per stock
- Add `volume_weighted_advancing` count: stocks where price > open AND volume > 1.2x average
- Include `volume_breadth_quality` in breadth context output

#### 2.3 Thread Safety

**File:** `app/core/market_data.py`

Add a `threading.Lock()` for shared state:
```python
self._data_lock = threading.Lock()
```

Wrap compound writes in `_on_streamer_message()`:
- When updating `pcr_oi_data` (dict iteration in PCR calculation)
- When updating `_api_greeks_ce/pe` (dict replacement)

Wrap compound reads in `get_market_state()`:
- Use `with self._data_lock:` when building the return dict from multiple shared dicts

Simple dict reads/writes (`instrument_prices[key] = value`) are GIL-protected and don't need locking.

#### 2.4 Timezone Verification

**File:** `app/core/streaming.py` class `CandleManager`

Add a one-time validation in `initialize()`:
```python
# Verify timezone alignment
first_ts = self.df.index[0]
last_ts = self.df.index[-1]
logger.info(f"Timezone check: First candle={first_ts}, Last candle={last_ts}, TZ={self.df.index.tz}")
# If last candle is during market hours (9:15-15:30 IST), timestamps are correct
# If last candle is at 3:45-10:00 (offset by 5.5hr), apply UTC->IST correction
```

#### 2.5 PCR OI Freshness

**File:** `app/core/market_data.py`

Change `pcr_oi_data` from `Dict[str, float]` to `Dict[str, Tuple[float, float]]` storing `(oi_value, timestamp)`.

When calculating PCR, skip entries older than 30 seconds to ensure consistent snapshots.

---

### Phase 3: Fix Strategy Logic

#### 3.1 PCR Documentation Fix

**File:** `app/core/pcr_calculator.py`

Rewrite the module docstring to match the contrarian interpretation used in the code:
```
PCR > 1.5: Heavy put writing = strong support = BULLISH (contrarian: extreme fear = reversal opportunity)
PCR 1.0-1.5: More puts than calls = moderate support = BULLISH
PCR ~ 1.0: Balanced = NEUTRAL
PCR 0.5-1.0: More calls than puts = resistance building = BEARISH
PCR < 0.5: Heavy call writing = strong resistance = BEARISH (contrarian: extreme greed = reversal risk)
```

Fix `_get_interpretation()` to use consistent language (remove contradictory "bullish but overbought" phrasing).

#### 3.2 EMA Filter Configuration

**File:** `app/core/config.py` and `app/strategies/strategy.py`

Add config:
```python
EMA_FILTER_MODE = "trend"  # "trend" or "crossover"
```

In `check_signal()`:
- `"trend"` mode (default): Current behavior — passes when EMA_5 > EMA_20
- `"crossover"` mode: Only passes when a crossover happened within the last 2 candles

This preserves backward compatibility while allowing tighter filtering.

#### 3.3 Breakout Sensitivity Adjustment

**File:** `app/strategies/strategy.py` method `detect_breakout`

Change from requiring both current and previous close:
```python
# Current: requires two confirmations
if current_price > threshold_up and prev_close > highest_high:
```

To single close with volume:
```python
# New: single close above threshold
if current_price > threshold_up:
    # Volume confirmation will be added by the caller using synthetic_volume
```

The breakout detection becomes simpler; volume confirmation is handled at the strategy level using the new synthetic volume data from Phase 2.

#### 3.4 Support/Resistance Clustering

**File:** `app/strategies/strategy.py` method `calculate_support_resistance`

After finding all local extrema, cluster levels within 0.3% of each other:
```python
def _cluster_levels(levels, threshold_pct=0.3):
    """Group nearby levels and return cluster averages."""
    if not levels:
        return []
    sorted_levels = sorted(levels)
    clusters = [[sorted_levels[0]]]
    for level in sorted_levels[1:]:
        if (level - clusters[-1][-1]) / clusters[-1][-1] * 100 < threshold_pct:
            clusters[-1].append(level)
        else:
            clusters.append([level])
    return [round(sum(c) / len(c), 2) for c in clusters]
```

This reduces 20+ noisy levels to 3-5 meaningful zones.

---

## Files Changed

| File | Phase | Changes |
|------|-------|---------|
| `app/strategies/strategy.py` | 1, 3 | RSI, ATR, Supertrend formulas; EMA filter mode; breakout; S/R clustering |
| `app/core/greeks.py` | 1 | IV solver dampening + bisection fallback |
| `app/intelligence/iv_rank.py` | 2 | Fix compute-before-append ordering |
| `app/core/market_data.py` | 2 | Synthetic volume; thread lock; PCR OI freshness |
| `app/core/strategy_runner.py` | 2 | Pass synthetic volume to candle manager |
| `app/core/streaming.py` | 2 | Timezone verification in CandleManager |
| `app/intelligence/market_breadth.py` | 2 | Volume-weighted breadth enhancement |
| `app/core/pcr_calculator.py` | 3 | Docstring fix |
| `app/core/config.py` | 3 | EMA_FILTER_MODE config |

---

## Risk Assessment

- **Phase 1 (Indicator fixes):** Low risk. Changing formulas will shift indicator values, causing different signals than before. This is the intended outcome — the new signals will be correct. Run paper trading for 2-3 sessions to verify.
- **Phase 2 (Data pipeline):** Medium risk. Thread locking could introduce deadlocks if not careful. IV Rank fix changes rank values. Volume proxy adds new data flow.
- **Phase 3 (Strategy logic):** Low risk. Most changes are documentation or configurable. S/R clustering reduces levels but nearest_support/resistance logic is unchanged.

---

## Success Criteria

1. RSI values within 2 points of TradingView for the same Nifty 5-minute candles
2. Supertrend direction matches TradingView at all times
3. IV Rank correctly shows values that can exceed 100 or go below 0 at extremes
4. Volume ratio shows meaningful non-zero values during market hours
5. No race condition errors in logs during sustained WebSocket streaming
6. All 225 existing tests continue to pass (may need threshold adjustments in tests)
