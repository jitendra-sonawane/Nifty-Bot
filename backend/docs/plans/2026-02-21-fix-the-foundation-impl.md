# Fix the Foundation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 14 identified issues across indicator calculations, data pipeline, and strategy logic so the bot's math matches industry standards and data flows correctly from Upstox WebSocket to strategy decisions.

**Architecture:** Three-phase fix — (1) correct indicator math (RSI, ATR, Supertrend, IV solver), (2) fix data pipeline bugs (IV Rank, volume proxy, thread safety, timezone, PCR freshness), (3) clean up strategy logic (PCR docs, EMA filter, breakout, S/R clustering). Each phase has its own tests and commit.

**Tech Stack:** Python 3, pandas, numpy, scipy, pytest

---

## Phase 1: Fix Indicator Calculations

### Task 1: Fix RSI to use Wilder's Smoothing

**Files:**
- Modify: `app/strategies/strategy.py:32-37`
- Test: `tests/test_strategy.py`

**Step 1: Write the failing test**

Add to `tests/test_strategy.py` inside class `TestCalculateRSI`:

```python
def test_rsi_wilders_smoothing(self):
    """RSI should use Wilder's EWM smoothing, not SMA.

    With Wilder's smoothing (alpha=1/14), RSI is smoother and does not
    jump abruptly when old values leave the window.  We verify by
    comparing against a known-correct Wilder's RSI for a specific
    price series.
    """
    # 30 prices: first 15 rise, then 15 fall
    prices = pd.Series(
        list(range(100, 115)) + list(range(115, 100, -1))
    , dtype=float)
    rsi = self.engine.calculate_rsi(prices, period=14)

    # With Wilder's smoothing, the final RSI after equal rise-then-fall
    # should be close to 50 (balanced).  SMA-based RSI would differ
    # significantly because old gains "fall off" the window.
    last_rsi = rsi.iloc[-1]
    assert 35 < last_rsi < 65, f"RSI {last_rsi:.1f} not near 50 — likely still using SMA"

def test_rsi_smooth_not_jumpy(self):
    """Wilder's RSI should not jump more than ~5 points on a single candle
    unless the candle itself is extreme."""
    np.random.seed(99)
    prices = pd.Series(24000 + np.cumsum(np.random.normal(0, 10, 100)))
    rsi = self.engine.calculate_rsi(prices, period=14)
    valid = rsi.dropna()
    diffs = valid.diff().dropna().abs()
    # No single-candle jump > 15 points in a normal random walk
    assert diffs.max() < 15, f"RSI jumped {diffs.max():.1f} pts — SMA artifact"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestCalculateRSI::test_rsi_wilders_smoothing tests/test_strategy.py::TestCalculateRSI::test_rsi_smooth_not_jumpy -v`

Expected: At least one FAIL (SMA-based RSI will differ from Wilder's expectations)

**Step 3: Write minimal implementation**

In `app/strategies/strategy.py`, replace lines 32-37:

```python
def calculate_rsi(self, series, period=14):
    delta = series.diff()
    gain  = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestCalculateRSI -v`

Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/strategies/strategy.py tests/test_strategy.py
git commit -m "fix: use Wilder's smoothing for RSI calculation

Replace .rolling().mean() with .ewm(alpha=1/period) to match
the standard RSI formula used by TradingView and Zerodha Kite."
```

---

### Task 2: Fix ATR to use Wilder's Smoothing

**Files:**
- Modify: `app/strategies/strategy.py:174-181`
- Test: `tests/test_strategy.py`

**Step 1: Write the failing test**

Add a new class to `tests/test_strategy.py`:

```python
class TestCalculateATR:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_atr_uses_ewm(self, sample_ohlcv_df):
        """ATR should use Wilder's EWM, not SMA rolling mean."""
        atr = self.engine.calculate_atr(sample_ohlcv_df)
        valid = atr.dropna()
        assert len(valid) > 0
        # EWM starts producing values from row 0 (not row period-1 like SMA)
        # After fix, first non-NaN should appear much earlier than row 14
        first_valid_idx = atr.first_valid_index()
        first_pos = sample_ohlcv_df.index.get_loc(first_valid_idx)
        # EWM produces values from index 1 (after first diff); SMA waits until index 14
        assert first_pos < 5, f"ATR first valid at position {first_pos} — likely still SMA"

    def test_atr_consistency_with_regime_module(self, sample_ohlcv_df):
        """ATR from strategy.py should match ATR from market_regime.py (both Wilder's)."""
        from app.intelligence.market_regime import MarketRegimeModule
        strategy_atr = self.engine.calculate_atr(sample_ohlcv_df).iloc[-1]
        regime_atr_pct = MarketRegimeModule._calculate_atr_pct(sample_ohlcv_df, 14)
        regime_atr = regime_atr_pct / 100 * sample_ohlcv_df['close'].iloc[-1]
        # Both should be within 5% of each other since they use the same formula
        # (regime uses rolling, our fix makes strategy use ewm — after fix both are ewm)
        assert abs(strategy_atr - regime_atr) / regime_atr < 0.05, \
            f"Strategy ATR={strategy_atr:.2f} vs Regime ATR={regime_atr:.2f} — mismatch"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestCalculateATR -v`

Expected: FAIL (SMA produces first valid at row 14, not row 1)

**Step 3: Write minimal implementation**

In `app/strategies/strategy.py`, replace line 181:

```python
def calculate_atr(self, df, period=14):
    high  = df['high']
    low   = df['low']
    close = df['close']
    tr    = pd.concat([high - low,
                       (high - close.shift(1)).abs(),
                       (low  - close.shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestCalculateATR -v`

Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/strategies/strategy.py tests/test_strategy.py
git commit -m "fix: use Wilder's smoothing for ATR calculation

Consistent with market_regime.py which already used ewm."
```

---

### Task 3: Fix Supertrend ATR to use Wilder's Smoothing

**Files:**
- Modify: `app/strategies/strategy.py:56-65`
- Test: `tests/test_strategy.py`

**Step 1: Write the failing test**

Add a new class to `tests/test_strategy.py`:

```python
class TestCalculateSupertrend:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_supertrend_returns_correct_shape(self, sample_ohlcv_df):
        st, upper, lower = self.engine.calculate_supertrend(sample_ohlcv_df)
        assert len(st) == len(sample_ohlcv_df)
        assert len(upper) == len(sample_ohlcv_df)
        assert len(lower) == len(sample_ohlcv_df)

    def test_supertrend_atr_uses_ewm(self, sample_ohlcv_df):
        """Supertrend's internal ATR should use Wilder's EWM."""
        # After fix, supertrend should produce non-NaN bands earlier
        # because EWM doesn't wait for a full window
        st, upper, lower = self.engine.calculate_supertrend(sample_ohlcv_df, period=7)
        # With EWM, upper/lower bands should have valid values by row 2
        # With SMA (rolling(7)), first valid is at row 7
        first_valid = upper.first_valid_index()
        first_pos = sample_ohlcv_df.index.get_loc(first_valid)
        assert first_pos < 3, f"Supertrend bands valid at position {first_pos} — likely SMA"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestCalculateSupertrend::test_supertrend_atr_uses_ewm -v`

Expected: FAIL

**Step 3: Write minimal implementation**

In `app/strategies/strategy.py`, replace line 65 inside `calculate_supertrend`:

```python
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
```

(Change only the one line from `tr.rolling(window=period).mean()` to `tr.ewm(alpha=1/period, adjust=False).mean()`)

**Step 4: Run test to verify it passes**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestCalculateSupertrend -v`

Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/strategies/strategy.py tests/test_strategy.py
git commit -m "fix: use Wilder's smoothing for Supertrend ATR

Aligns Supertrend band calculation with standard implementations."
```

---

### Task 4: Add dampened Newton-Raphson + bisection fallback for IV solver

**Files:**
- Modify: `app/core/greeks.py:131-191`
- Test: `tests/test_greeks.py`

**Step 1: Write the failing test**

Add to `tests/test_greeks.py`:

```python
import pytest
from app.core.greeks import GreeksCalculator


class TestImpliedVolatility:

    def setup_method(self):
        self.calc = GreeksCalculator(risk_free_rate=0.06)

    def test_iv_atm_option(self):
        """ATM option should converge to a reasonable IV."""
        iv = self.calc.implied_volatility(
            market_price=200, S=24000, K=24000, T=7/365, option_type='CE'
        )
        assert 0.05 < iv < 1.0, f"IV={iv} out of reasonable range for ATM"

    def test_iv_deep_otm_converges(self):
        """Deep OTM option should converge without oscillation."""
        # Deep OTM CE: strike 25000 when spot is 23000, price is tiny
        iv = self.calc.implied_volatility(
            market_price=0.5, S=23000, K=25000, T=3/365, option_type='CE'
        )
        assert iv > 0, "IV should be positive for deep OTM"
        assert iv < 5.0, f"IV={iv} — solver likely oscillated"

    def test_iv_near_expiry_converges(self):
        """Near-expiry option should converge (T very small)."""
        iv = self.calc.implied_volatility(
            market_price=50, S=24000, K=24000, T=0.5/365, option_type='CE'
        )
        assert iv > 0, "IV should be positive near expiry"

    def test_iv_roundtrip(self):
        """Price -> IV -> Price should roundtrip within tolerance."""
        S, K, T = 24000, 24000, 10/365
        original_iv = 0.15
        price = self.calc.black_scholes_price(S, K, T, original_iv, 'CE')
        recovered_iv = self.calc.implied_volatility(price, S, K, T, 'CE')
        assert abs(recovered_iv - original_iv) < 0.01, \
            f"Roundtrip failed: {original_iv} -> price={price:.2f} -> {recovered_iv}"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_greeks.py::TestImpliedVolatility -v`

Expected: `test_iv_deep_otm_converges` may fail or timeout with current N-R

**Step 3: Write minimal implementation**

Replace `implied_volatility` method in `app/core/greeks.py` (lines 131-191):

```python
    def implied_volatility(self, market_price, S, K, T, option_type='CE', risk_free_rate=None):
        """
        Calculate Implied Volatility using dampened Newton-Raphson with bisection fallback.
        """
        if risk_free_rate is not None:
            r = risk_free_rate
        else:
            r = self.r

        if market_price <= 0 or S <= 0 or K <= 0:
            return 0.0001

        intrinsic = max(S - K, 0) if option_type == 'CE' else max(K - S, 0)
        time_value = market_price - intrinsic

        if time_value <= 0:
            return 0.01

        if T <= 0:
            return 0.0001

        PRECISION = 1.0e-5
        NR_ITERATIONS = 50
        BISECT_ITERATIONS = 50
        DAMPENING = 0.7

        # Heuristic initial guess
        sigma = np.sqrt(2 * np.pi / T) * (time_value / S)
        sigma = np.clip(sigma, 0.01, 2.0)

        # Phase 1: Dampened Newton-Raphson
        for _ in range(NR_ITERATIONS):
            price = self.black_scholes_price(S, K, T, sigma, option_type, r)
            diff = market_price - price

            if abs(diff) < PRECISION:
                return max(round(sigma, 4), 0.0001)

            d1 = self.d1(S, K, T, sigma)
            vega = S * np.sqrt(T) * norm.pdf(d1)

            if vega < 1e-10:
                break  # Fall through to bisection

            sigma = sigma + DAMPENING * (diff / vega)
            sigma = np.clip(sigma, 0.001, 5.0)

        # Phase 2: Bisection fallback (guaranteed convergence)
        lo, hi = 0.001, 5.0
        for _ in range(BISECT_ITERATIONS):
            mid = (lo + hi) / 2
            price = self.black_scholes_price(S, K, T, mid, option_type, r)
            diff = market_price - price

            if abs(diff) < PRECISION:
                return max(round(mid, 4), 0.0001)

            if diff > 0:
                lo = mid
            else:
                hi = mid

        return max(round((lo + hi) / 2, 4), 0.0001)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_greeks.py::TestImpliedVolatility -v`

Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/core/greeks.py tests/test_greeks.py
git commit -m "fix: add dampened Newton-Raphson + bisection fallback for IV solver

Prevents oscillation on deep OTM options. Bisection guarantees convergence."
```

---

### Task 5: Run full test suite to verify Phase 1 didn't break anything

**Step 1: Run all tests**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -40`

Expected: All tests pass. Some existing tests may need threshold adjustments if they relied on SMA-based RSI values.

**Step 2: Fix any broken tests**

If tests fail because RSI/ATR values shifted (expected due to formula change), update the test thresholds. The existing tests use loose assertions (`> 80`, `< 20`) which should still pass with Wilder's smoothing.

**Step 3: Commit if any test fixes were needed**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add tests/
git commit -m "test: adjust thresholds after Wilder's smoothing migration"
```

---

## Phase 2: Fix Data Pipeline

### Task 6: Fix IV Rank bug — compute before append

**Files:**
- Modify: `app/intelligence/iv_rank.py:74-111`
- Test: `tests/test_iv_rank_stability.py`

**Step 1: Write the failing test**

Create or add to `tests/test_iv_rank_stability.py`:

```python
import pytest
import time
from unittest.mock import patch
from app.intelligence.iv_rank import IVRankModule


class TestIVRankComputeOrder:

    def test_current_iv_excluded_from_range(self):
        """Current IV should NOT be in the history when computing rank.

        If we feed history [0.10, 0.20] and then current_iv=0.25,
        rank should be computed against range [0.10, 0.20] → rank = 150%.
        If bug exists, current_iv is IN history → range [0.10, 0.25] → rank = 100%.
        """
        module = IVRankModule(history_size=100, history_interval=0)
        # Manually disable disk persistence for test
        module.save_state = lambda: None
        module.load_state = lambda: None
        module._history.clear()

        # Seed history with known range: low=0.10, high=0.20
        module._history.append(0.10)
        module._history.append(0.20)
        module._last_history_update_time = 0  # Force next append to succeed

        # Feed current IV = 0.25 (above historical range)
        with patch('time.time', return_value=1000.0):
            module.update({"iv": 0.25})

        ctx = module.get_context()
        iv_rank = ctx["iv_rank"]

        # Correct: rank = (0.25 - 0.10) / (0.20 - 0.10) * 100 = 150
        # Bug:     rank = (0.25 - 0.10) / (0.25 - 0.10) * 100 = 100
        assert iv_rank is not None
        assert iv_rank > 100, \
            f"IV Rank={iv_rank:.1f} — current IV should exceed range (expect >100, got ≤100)"

    def test_current_iv_at_new_low_gives_negative_rank(self):
        """When current IV is below all history, rank should be < 0."""
        module = IVRankModule(history_size=100, history_interval=0)
        module.save_state = lambda: None
        module.load_state = lambda: None
        module._history.clear()

        module._history.append(0.15)
        module._history.append(0.25)
        module._last_history_update_time = 0

        with patch('time.time', return_value=1000.0):
            module.update({"iv": 0.10})

        ctx = module.get_context()
        iv_rank = ctx["iv_rank"]

        # Correct: rank = (0.10 - 0.15) / (0.25 - 0.15) * 100 = -50
        assert iv_rank is not None
        assert iv_rank < 0, \
            f"IV Rank={iv_rank:.1f} — below all history should give negative rank"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_iv_rank_stability.py::TestIVRankComputeOrder -v`

Expected: FAIL (current code includes current IV in range, so rank=100 not 150)

**Step 3: Write minimal implementation**

In `app/intelligence/iv_rank.py`, modify the `update` method (lines 97-111). Replace:

```python
        if now - self._last_history_update_time >= interval:
            self._history.append(self._current_iv)
            self._last_history_update_time = now
            # Persist state after successful update
            self.save_state()

        # Always re-compute rank with latest current_iv against history
        self._compute()
```

With:

```python
        # Always re-compute rank FIRST against existing history (before appending)
        self._compute()

        # Then add current IV to history for future calculations (throttled)
        if now - self._last_history_update_time >= interval:
            self._history.append(self._current_iv)
            self._last_history_update_time = now
            self.save_state()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_iv_rank_stability.py -v`

Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/intelligence/iv_rank.py tests/test_iv_rank_stability.py
git commit -m "fix: compute IV Rank before appending current IV to history

Current IV was being included in its own historical range, making
rank always cap at 100. Now rank can exceed 100 or go below 0 at
extremes, matching the documented behavior."
```

---

### Task 7: Add synthetic volume proxy from ATM options

**Files:**
- Modify: `app/core/market_data.py` (add `synthetic_volume` field + expose in `get_market_state`)
- Modify: `app/core/strategy_runner.py:86` (pass real volume)

**Step 1: Modify market_data.py — add synthetic_volume state**

In `app/core/market_data.py`, add to `__init__` (after line 49, near other state vars):

```python
        self.synthetic_volume: float = 0.0  # ATM CE+PE combined volume
```

**Step 2: Compute synthetic_volume in _on_streamer_message**

In `app/core/market_data.py`, after updating `pcr_volume_data` (around line 305), add computation that recalculates synthetic volume whenever ATM option volume updates:

After the existing block that stores `pcr_volume_data[key]`, add:

```python
                        # Update synthetic volume (ATM CE + PE combined)
                        if self.option_ce_key and self.option_pe_key:
                            ce_vol = self.pcr_volume_data.get(self.option_ce_key, 0)
                            pe_vol = self.pcr_volume_data.get(self.option_pe_key, 0)
                            self.synthetic_volume = float(ce_vol) + float(pe_vol)
```

**Step 3: Expose in get_market_state**

In `app/core/market_data.py`, in `get_market_state()` return dict (line 1311-1321), add:

```python
            "synthetic_volume": self.synthetic_volume,
```

**Step 4: Pass volume to CandleManager in strategy_runner.py**

In `app/core/strategy_runner.py`, change line 86 from:

```python
            is_new_candle, df = self.candle_manager.update(current_price, volume=0)
```

To:

```python
            synthetic_vol = market_state.get('synthetic_volume', 0)
            is_new_candle, df = self.candle_manager.update(current_price, volume=synthetic_vol)
```

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/core/market_data.py app/core/strategy_runner.py
git commit -m "feat: add synthetic volume proxy from ATM option CE+PE volume

Nifty index has no trading volume. ATM option combined volume
serves as activity proxy for volume ratio calculations."
```

---

### Task 8: Add thread safety lock to MarketDataManager

**Files:**
- Modify: `app/core/market_data.py`

**Step 1: Add lock to __init__**

In `app/core/market_data.py`, add after line 5 (imports):

```python
import threading
```

In `__init__`, add (after line 99, near other state):

```python
        self._data_lock = threading.Lock()
```

**Step 2: Wrap get_market_state with lock**

In `get_market_state()` (line 1285), wrap the return dict construction:

```python
    def get_market_state(self):
        # ... existing fallback code stays the same ...

        with self._data_lock:
            return {
                "current_price": self.current_price,
                "atm_strike": self.atm_strike,
                "pcr": self.latest_pcr,
                "pcr_analysis": self.latest_pcr_analysis,
                "vix": self.latest_vix,
                "sentiment": self.latest_sentiment,
                "greeks": self.latest_greeks,
                "previous_close": self.previous_close,
                "market_movement": self.market_movement,
                "synthetic_volume": self.synthetic_volume,
            }
```

**Step 3: Wrap PCR calculation with lock**

Find the method that calculates PCR (the `_websocket_pcr_loop` or similar) and wrap the read of `self.pcr_oi_data` and `self.pcr_volume_data` with `self._data_lock`.

**Step 4: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/core/market_data.py
git commit -m "fix: add threading lock for shared state in MarketDataManager

Prevents race conditions between WebSocket thread and async strategy runner."
```

---

### Task 9: Add timezone verification to CandleManager

**Files:**
- Modify: `app/core/streaming.py:88-117`

**Step 1: Add verification logging**

In `app/core/streaming.py`, at the end of `CandleManager.initialize()` (after line 117), add:

```python
        # Timezone alignment check
        first_ts = self.df.index[0]
        last_ts = self.df.index[-1]
        logger.info(
            f"📅 Timezone verification: First={first_ts} Last={last_ts} TZ={self.df.index.tz} "
            f"Candles={len(self.df)}"
        )
        # Sanity: last candle should be during Indian market hours (09:15-15:30 IST)
        last_hour = last_ts.hour
        if last_hour < 9 or last_hour > 16:
            logger.warning(
                f"⚠️ TIMEZONE MISMATCH: Last candle at hour {last_hour} is outside "
                f"Indian market hours (09-16). Timestamps may be UTC instead of IST."
            )
```

**Step 2: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/core/streaming.py
git commit -m "fix: add timezone verification logging to CandleManager

Warns if candle timestamps appear to be UTC instead of IST."
```

---

### Task 10: Add PCR OI freshness tracking

**Files:**
- Modify: `app/core/market_data.py`
- Modify: `app/core/pcr_calculator.py`

**Step 1: Store timestamps with OI data**

In `app/core/market_data.py`, change the OI storage in `_on_streamer_message` from:

```python
self.pcr_oi_data[key] = float(oi)
```

To:

```python
self.pcr_oi_data[key] = (float(oi), time.time())
```

**Step 2: Update PCR calculation to filter stale entries**

In the PCR calculation loop (wherever `calculate_pcr_from_options` is called), extract only fresh OI values:

```python
# Build fresh-only OI dict (skip entries older than 30 seconds)
now = time.time()
fresh_oi = {k: v for k, (v, ts) in self.pcr_oi_data.items() if now - ts < 30}
```

Pass `fresh_oi` instead of raw `self.pcr_oi_data` to `calculate_pcr_from_options`.

**Step 3: Update volume data similarly**

Apply the same `(value, timestamp)` pattern to `pcr_volume_data`.

**Step 4: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/core/market_data.py
git commit -m "fix: track timestamps for PCR OI data freshness

Skip OI entries older than 30 seconds when calculating PCR
to avoid mixing fresh and stale values across strikes."
```

---

### Task 11: Run full test suite for Phase 2

**Step 1: Run all tests**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -40`

Expected: All pass. The PCR test `test_from_options_basic` may need updating if `calculate_pcr_from_options` signature changed.

**Step 2: Fix any broken tests and commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add tests/
git commit -m "test: fix tests after Phase 2 data pipeline changes"
```

---

## Phase 3: Fix Strategy Logic

### Task 12: Fix PCR documentation — align docstring with code

**Files:**
- Modify: `app/core/pcr_calculator.py:1-12, 232-255`

**Step 1: Replace module docstring**

Replace lines 1-12 of `app/core/pcr_calculator.py`:

```python
"""
Put-Call Ratio (PCR) Calculator for options sentiment analysis.

PCR = Total Put Open Interest / Total Call Open Interest

Contrarian Interpretation (used by this system):
- PCR > 1.5: Heavy put writing = strong support building = BULLISH
  (Extreme fear often precedes reversals upward)
- PCR 1.0-1.5: More puts than calls = moderate support = BULLISH
- PCR ~ 1.0: Balanced put-call activity = NEUTRAL
- PCR 0.5-1.0: More calls than puts = resistance building = BEARISH
- PCR < 0.5: Heavy call writing = strong resistance = BEARISH
  (Extreme greed often precedes reversals downward)

Note: This is the CONTRARIAN view. Raw sentiment is the opposite
(high PCR = bearish sentiment), but markets tend to reverse at
extremes, making the contrarian view more useful for trading.
"""
```

**Step 2: Fix _get_interpretation method**

Replace the `_get_interpretation` method (lines 232-255):

```python
    def _get_interpretation(self, week_pcr: float, intraday_pcr: Optional[float], sentiment: str, trend: Optional[str]) -> str:
        """Generate human-readable interpretation of PCR (contrarian view)."""
        interpretations = {
            "EXTREME_BULLISH": "Heavy put writing = strong support. Contrarian bullish (extreme fear often reverses).",
            "BULLISH": "More puts than calls. Put support building — bullish bias.",
            "NEUTRAL": "Balanced put-call activity. No clear directional bias.",
            "BEARISH": "More calls than puts. Call resistance building — bearish bias.",
            "EXTREME_BEARISH": "Heavy call writing = strong resistance. Contrarian bearish (extreme greed often reverses).",
        }

        base = interpretations.get(sentiment, "Unknown sentiment")

        if trend == "INCREASING":
            base += " PCR rising (more puts being added)."
        elif trend == "DECREASING":
            base += " PCR falling (more calls being added)."

        if intraday_pcr is not None:
            if intraday_pcr > 1.0 and week_pcr < 1.0:
                base += " Intraday: bullish divergence (day traders adding puts despite weekly bearish)."
            elif intraday_pcr < 1.0 and week_pcr > 1.0:
                base += " Intraday: bearish divergence (day traders adding calls despite weekly bullish)."

        return base
```

**Step 3: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/core/pcr_calculator.py
git commit -m "docs: fix PCR documentation to match contrarian interpretation

Docstring previously described raw sentiment (high PCR = bearish)
but code implements contrarian view (high PCR = bullish). Now
consistent throughout."
```

---

### Task 13: Add EMA filter mode configuration

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/strategies/strategy.py:586-601`
- Test: `tests/test_strategy.py`

**Step 1: Add config option**

In `app/core/config.py`, add after line 41 (after RSI_OVERSOLD):

```python
    # EMA filter mode: "trend" = passes when EMA_5 > EMA_20 (default)
    #                  "crossover" = passes only on actual crossover + 2 candle confirmation
    EMA_FILTER_MODE = "trend"
```

**Step 2: Write the test**

Add to `tests/test_strategy.py`:

```python
class TestEMAFilterMode:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_trend_mode_passes_when_ema_above(self, sample_ohlcv_df):
        """In trend mode, EMA filter passes whenever short EMA > long EMA."""
        result = self.engine.check_signal(sample_ohlcv_df, backtest_mode=True)
        if result == "WAITING_DATA":
            pytest.skip("Not enough data")
        # Filter should be evaluated (True or False) regardless of mode
        assert 'ema_crossover' in result.get('filters', {})
```

**Step 3: Implement the mode check**

In `app/strategies/strategy.py`, replace the EMA crossover section (lines 586-601):

```python
        # 2. EMA crossover
        ema_bullish = ema_bearish = False
        if len(df) >= 2:
            prev_ema_5  = df['ema_5'].iloc[-2]
            prev_ema_20 = df['ema_20'].iloc[-2]
            if pd.notna(prev_ema_5) and pd.notna(prev_ema_20) and pd.notna(ema_5) and pd.notna(ema_20):
                ema_bullish = (prev_ema_5 <= prev_ema_20) and (ema_5 > ema_20)
                ema_bearish = (prev_ema_5 >= prev_ema_20) and (ema_5 < ema_20)
            else:
                ema_bullish = ema_5 > ema_20
                ema_bearish = ema_5 < ema_20
        else:
            ema_bullish = ema_5 > ema_20
            ema_bearish = ema_5 < ema_20

        # Apply EMA filter based on configured mode
        from app.core.config import Config
        ema_mode = getattr(Config, 'EMA_FILTER_MODE', 'trend')

        if ema_mode == "crossover":
            # Strict: only pass on actual crossover (within last 2 candles)
            if len(df) >= 3:
                prev2_ema_5 = df['ema_5'].iloc[-3] if pd.notna(df['ema_5'].iloc[-3]) else None
                prev2_ema_20 = df['ema_20'].iloc[-3] if pd.notna(df['ema_20'].iloc[-3]) else None
                recent_bullish_cross = ema_bullish or (
                    prev2_ema_5 is not None and prev2_ema_20 is not None and
                    prev2_ema_5 <= prev2_ema_20 and prev_ema_5 > prev_ema_20
                )
                recent_bearish_cross = ema_bearish or (
                    prev2_ema_5 is not None and prev2_ema_20 is not None and
                    prev2_ema_5 >= prev2_ema_20 and prev_ema_5 < prev_ema_20
                )
                filter_checks['ema_crossover'] = recent_bullish_cross if dominant_direction == "BULLISH" else recent_bearish_cross
            else:
                filter_checks['ema_crossover'] = ema_bullish if dominant_direction == "BULLISH" else ema_bearish
        else:
            # Trend mode (default): pass when short EMA on correct side of long EMA
            filter_checks['ema_crossover'] = (ema_bullish or ema_5 > ema_20) if dominant_direction == "BULLISH" else (ema_bearish or ema_5 < ema_20)
```

**Step 4: Run tests**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py -v --tb=short`

Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/core/config.py app/strategies/strategy.py tests/test_strategy.py
git commit -m "feat: add configurable EMA filter mode (trend vs crossover)

Default 'trend' mode preserves current behavior. 'crossover' mode
only passes when a fresh crossover happened within 2 candles."
```

---

### Task 14: Simplify breakout detection

**Files:**
- Modify: `app/strategies/strategy.py:142-172`
- Test: `tests/test_strategy.py`

**Step 1: Write the test**

Add to `tests/test_strategy.py`:

```python
class TestDetectBreakout:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_single_candle_breakout(self):
        """Breakout should trigger on single candle close above threshold."""
        np.random.seed(42)
        n = 60
        # 58 candles of range-bound, then a breakout
        base = 24000.0
        prices = np.full(n, base)
        prices[:58] = base + np.random.uniform(-50, 50, 58)
        prices[58] = base + 200  # breakout candle (prev close still in range)
        prices[59] = base + 210  # current candle

        df = pd.DataFrame({
            'open': prices - 5,
            'high': prices + 10,
            'low': prices - 10,
            'close': prices,
            'volume': np.full(n, 500000),
        })

        result = self.engine.detect_breakout(df)
        assert result['is_breakout'] is True, "Single candle breakout should be detected"
        assert result['breakout_type'] == 'UPSIDE'
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestDetectBreakout::test_single_candle_breakout -v`

Expected: FAIL (current code requires prev_close > highest_high too)

**Step 3: Implement the fix**

In `app/strategies/strategy.py`, replace lines 162-170:

```python
        if current_price > threshold_up:
            return {'is_breakout': True,  'breakout_type': 'UPSIDE',
                    'breakout_level': round(highest_high, 2),
                    'strength': round(((current_price - highest_high) / highest_high) * 100, 2)}

        if current_price < threshold_down:
            return {'is_breakout': True,  'breakout_type': 'DOWNSIDE',
                    'breakout_level': round(lowest_low, 2),
                    'strength': round(((lowest_low - current_price) / lowest_low) * 100, 2)}
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestDetectBreakout -v`

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/strategies/strategy.py tests/test_strategy.py
git commit -m "fix: simplify breakout detection to single candle confirmation

Removed requirement for previous close to also be above the level.
Volume confirmation is handled at strategy level via synthetic volume."
```

---

### Task 15: Add support/resistance clustering

**Files:**
- Modify: `app/strategies/strategy.py:101-140`
- Test: `tests/test_strategy.py`

**Step 1: Write the test**

Add to `tests/test_strategy.py`:

```python
class TestSupportResistanceClustering:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_cluster_reduces_noise(self, sample_ohlcv_df):
        """Clustering should produce fewer levels than raw detection."""
        result = self.engine.calculate_support_resistance(sample_ohlcv_df)
        # After clustering, should have <= 5 support and <= 5 resistance levels
        assert len(result['support_levels']) <= 5
        assert len(result['resistance_levels']) <= 5

    def test_cluster_levels_helper(self):
        """Test the clustering helper directly."""
        # Levels very close together should merge
        levels = [24000, 24005, 24010, 24100, 24105, 24300]
        clustered = self.engine._cluster_levels(levels, threshold_pct=0.3)
        # 24000/24005/24010 should cluster (within 0.3%)
        # 24100/24105 should cluster
        # 24300 is separate
        assert len(clustered) <= 4, f"Expected <=4 clusters, got {len(clustered)}"

    def test_cluster_empty(self):
        """Empty input should return empty."""
        assert self.engine._cluster_levels([]) == []
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestSupportResistanceClustering -v`

Expected: FAIL (`_cluster_levels` doesn't exist yet)

**Step 3: Implement clustering**

Add method to `StrategyEngine` class in `app/strategies/strategy.py` (before `calculate_support_resistance`):

```python
    @staticmethod
    def _cluster_levels(levels, threshold_pct=0.3):
        """Group nearby price levels and return cluster averages.

        Levels within threshold_pct% of each other are merged into one.
        """
        if not levels:
            return []
        sorted_levels = sorted(levels)
        clusters = [[sorted_levels[0]]]
        for level in sorted_levels[1:]:
            if clusters[-1][-1] > 0 and (level - clusters[-1][-1]) / clusters[-1][-1] * 100 < threshold_pct:
                clusters[-1].append(level)
            else:
                clusters.append([level])
        return [round(sum(c) / len(c), 2) for c in clusters]
```

Then modify `calculate_support_resistance` to use it. Replace lines 121-122:

```python
        resistance_levels = sorted(list(set(resistance_levels + [round(max_high, 2)])), reverse=True)
        support_levels    = sorted(list(set(support_levels    + [round(min_low,  2)])), reverse=True)
```

With:

```python
        resistance_levels = list(set(resistance_levels + [round(max_high, 2)]))
        support_levels    = list(set(support_levels    + [round(min_low,  2)]))
        # Cluster nearby levels to reduce noise
        resistance_levels = sorted(self._cluster_levels(resistance_levels), reverse=True)
        support_levels    = sorted(self._cluster_levels(support_levels), reverse=True)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_strategy.py::TestSupportResistanceClustering -v`

Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add app/strategies/strategy.py tests/test_strategy.py
git commit -m "feat: add support/resistance level clustering

Groups levels within 0.3% of each other into single zones,
reducing 20+ noisy micro-levels to 3-5 meaningful zones."
```

---

### Task 16: Final full test suite run + cleanup

**Step 1: Run all tests**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --tb=short`

Expected: ALL PASS

**Step 2: Verify no regressions**

Check that:
- `test_strategy.py` — all indicator tests pass with new formulas
- `test_pcr_calculator.py` — PCR tests pass (may need signature fix if `calculate_pcr_from_options` changed)
- `test_greeks.py` — IV solver tests pass
- `test_iv_rank_stability.py` — IV rank compute-order tests pass

**Step 3: Final commit**

```bash
cd /Users/jitendrasonawane/Workpace/backend
git add -A
git commit -m "chore: final cleanup after fix-the-foundation implementation

All 14 issues addressed across 3 phases:
- Phase 1: RSI, ATR, Supertrend now use Wilder's smoothing; IV solver dampened
- Phase 2: IV Rank bug fixed; synthetic volume proxy added; thread safety added
- Phase 3: PCR docs fixed; EMA filter configurable; breakout simplified; S/R clustered"
```

---

## Summary of All Commits

| # | Commit Message | Phase |
|---|---------------|-------|
| 1 | `fix: use Wilder's smoothing for RSI calculation` | 1 |
| 2 | `fix: use Wilder's smoothing for ATR calculation` | 1 |
| 3 | `fix: use Wilder's smoothing for Supertrend ATR` | 1 |
| 4 | `fix: add dampened Newton-Raphson + bisection fallback for IV solver` | 1 |
| 5 | `test: adjust thresholds after Wilder's smoothing migration` (if needed) | 1 |
| 6 | `fix: compute IV Rank before appending current IV to history` | 2 |
| 7 | `feat: add synthetic volume proxy from ATM option CE+PE volume` | 2 |
| 8 | `fix: add threading lock for shared state in MarketDataManager` | 2 |
| 9 | `fix: add timezone verification logging to CandleManager` | 2 |
| 10 | `fix: track timestamps for PCR OI data freshness` | 2 |
| 11 | `test: fix tests after Phase 2 data pipeline changes` (if needed) | 2 |
| 12 | `docs: fix PCR documentation to match contrarian interpretation` | 3 |
| 13 | `feat: add configurable EMA filter mode (trend vs crossover)` | 3 |
| 14 | `fix: simplify breakout detection to single candle confirmation` | 3 |
| 15 | `feat: add support/resistance level clustering` | 3 |
| 16 | `chore: final cleanup after fix-the-foundation implementation` | 3 |
