# Nifty 50 Futures Volume + CVD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time Nifty 50 futures volume bars with cumulative volume delta (CVD) line to the main dashboard, always visible above the IndicatorStrip.

**Architecture:** A new `FuturesVolumeTracker` class subscribes to the near-month Nifty futures instrument on the existing Upstox V3 WebSocket. It builds 1-minute candles, classifies buy/sell volume via the uptick/downtick rule, and accumulates CVD. The data flows through the existing `/ws/status` broadcast to a new `<FuturesVolumeStrip>` SVG component in the frontend.

**Tech Stack:** Python (backend), React 19 + TypeScript + Tailwind (frontend), pure SVG charting (no new libraries)

---

### Task 1: FuturesVolumeTracker — Core Class

**Files:**
- Create: `backend/app/core/futures_volume.py`
- Create: `backend/tests/test_futures_volume.py`

**Step 1: Write the test file**

```python
# tests/test_futures_volume.py
"""Tests for FuturesVolumeTracker — 1-min candle building, delta classification, CVD."""

import time
import pytest
from app.core.futures_volume import FuturesVolumeTracker


class TestFuturesVolumeTracker:
    """Unit tests for FuturesVolumeTracker."""

    def test_initial_state(self):
        tracker = FuturesVolumeTracker()
        snapshot = tracker.get_snapshot()
        assert snapshot["current_cvd"] == 0
        assert snapshot["current_delta"] == 0
        assert snapshot["total_volume"] == 0
        assert snapshot["candles"] == []
        assert snapshot["futures_ltp"] == 0.0

    def test_single_tick_creates_candle(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)  # 09:15:00 IST
        snapshot = tracker.get_snapshot()
        assert snapshot["futures_ltp"] == 24100.0
        assert snapshot["total_volume"] == 500

    def test_uptick_classified_as_buy(self):
        tracker = FuturesVolumeTracker()
        # First tick establishes price (no direction yet, classified as buy by default)
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        # Second tick is higher -> buy
        tracker.on_tick(price=24105.0, volume=300, timestamp=1709096101.0)
        snapshot = tracker.get_snapshot()
        # Both ticks in same 1-min candle
        assert len(snapshot["candles"]) == 1
        candle = snapshot["candles"][0]
        assert candle["buy_volume"] == 800  # 500 (first, default buy) + 300 (uptick)
        assert candle["sell_volume"] == 0

    def test_downtick_classified_as_sell(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        # Second tick is lower -> sell
        tracker.on_tick(price=24095.0, volume=300, timestamp=1709096101.0)
        snapshot = tracker.get_snapshot()
        candle = snapshot["candles"][0]
        assert candle["buy_volume"] == 500  # first tick default
        assert candle["sell_volume"] == 300  # downtick

    def test_equal_price_uses_previous_direction(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=100, timestamp=1709096100.0)
        tracker.on_tick(price=24105.0, volume=200, timestamp=1709096101.0)  # uptick -> buy
        tracker.on_tick(price=24105.0, volume=150, timestamp=1709096102.0)  # equal -> still buy
        candle = tracker.get_snapshot()["candles"][0]
        assert candle["buy_volume"] == 450  # 100 + 200 + 150
        assert candle["sell_volume"] == 0

    def test_new_minute_creates_new_candle(self):
        tracker = FuturesVolumeTracker()
        # Minute 1: 09:15:00
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        # Minute 2: 09:16:00 (60 seconds later)
        tracker.on_tick(price=24110.0, volume=300, timestamp=1709096160.0)
        snapshot = tracker.get_snapshot()
        assert len(snapshot["candles"]) == 2

    def test_cvd_accumulates_across_candles(self):
        tracker = FuturesVolumeTracker()
        # Candle 1: all buy -> delta = +500
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        # Candle 2: downtick -> sell delta = -300
        tracker.on_tick(price=24090.0, volume=300, timestamp=1709096160.0)
        snapshot = tracker.get_snapshot()
        # CVD = candle1.delta + candle2.delta = 500 + (-300) = 200
        assert snapshot["current_cvd"] == 200

    def test_delta_calculation(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)  # buy 500
        tracker.on_tick(price=24095.0, volume=300, timestamp=1709096101.0)  # sell 300
        candle = tracker.get_snapshot()["candles"][0]
        assert candle["delta"] == 200  # 500 - 300
        assert candle["total_volume"] == 800

    def test_total_volume_tracks_all_ticks(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.on_tick(price=24110.0, volume=300, timestamp=1709096160.0)
        tracker.on_tick(price=24120.0, volume=200, timestamp=1709096220.0)
        assert tracker.get_snapshot()["total_volume"] == 1000

    def test_reset_clears_all_state(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.reset()
        snapshot = tracker.get_snapshot()
        assert snapshot["current_cvd"] == 0
        assert snapshot["candles"] == []
        assert snapshot["total_volume"] == 0

    def test_max_candles_rolling_window(self):
        tracker = FuturesVolumeTracker(max_candles=5)
        # Create 7 candles (each 60s apart)
        for i in range(7):
            tracker.on_tick(price=24100.0 + i, volume=100, timestamp=1709096100.0 + i * 60)
        snapshot = tracker.get_snapshot()
        assert len(snapshot["candles"]) == 5  # Oldest 2 dropped

    def test_candle_time_format(self):
        tracker = FuturesVolumeTracker()
        # 1709096100.0 in IST (UTC+5:30) -> some time string
        tracker.on_tick(price=24100.0, volume=100, timestamp=1709096100.0)
        candle = tracker.get_snapshot()["candles"][0]
        assert "time" in candle
        assert "timestamp" in candle
        assert isinstance(candle["time"], str)
        assert isinstance(candle["timestamp"], (int, float))

    def test_snapshot_includes_instrument_key(self):
        tracker = FuturesVolumeTracker(instrument_key="NSE_FO|12345")
        snapshot = tracker.get_snapshot()
        assert snapshot["instrument_key"] == "NSE_FO|12345"

    def test_thread_safety_no_crash(self):
        """Verify concurrent access doesn't crash."""
        import threading
        tracker = FuturesVolumeTracker()
        errors = []

        def writer():
            try:
                for i in range(100):
                    tracker.on_tick(price=24100.0 + i * 0.05, volume=10, timestamp=1709096100.0 + i * 0.1)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    tracker.get_snapshot()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert errors == []
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_futures_volume.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.futures_volume'`

**Step 3: Write the FuturesVolumeTracker implementation**

```python
# app/core/futures_volume.py
"""FuturesVolumeTracker — builds 1-min volume candles with buy/sell delta and CVD
from Nifty 50 futures tick data."""

import threading
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

from app.core.logger_config import logger

# IST offset
_IST = timezone(timedelta(hours=5, minutes=30))


class FuturesVolumeTracker:
    """Tracks futures volume ticks, builds 1-minute candles with buy/sell
    classification (uptick/downtick rule), and accumulates CVD."""

    def __init__(self, instrument_key: str = "", max_candles: int = 375):
        self.instrument_key = instrument_key
        self._max_candles = max_candles
        self._lock = threading.Lock()

        # Tick state
        self._prev_price: Optional[float] = None
        self._last_direction: str = "buy"  # default for first tick
        self._futures_ltp: float = 0.0

        # Current candle being built
        self._current_candle: Optional[Dict] = None
        self._current_minute: Optional[int] = None  # minute-start timestamp

        # Completed candles
        self._candles: List[Dict] = []
        self._cvd: float = 0.0  # running cumulative volume delta
        self._total_volume: float = 0.0

    def on_tick(self, price: float, volume: float, timestamp: float) -> None:
        """Process a single futures tick. Thread-safe.

        Args:
            price: Last traded price
            volume: Volume for this tick (cumulative from exchange,
                    but we treat the delta from last seen as the tick volume)
            timestamp: Unix timestamp (seconds)
        """
        with self._lock:
            self._futures_ltp = price

            # Determine buy/sell direction
            if self._prev_price is None:
                direction = "buy"  # first tick defaults to buy
            elif price > self._prev_price:
                direction = "buy"
            elif price < self._prev_price:
                direction = "sell"
            else:
                direction = self._last_direction  # unchanged -> use previous

            self._prev_price = price
            self._last_direction = direction

            # Determine which minute this tick belongs to
            minute_start = int(timestamp) // 60 * 60

            # If new minute or no candle yet, finalize previous and start new
            if self._current_minute is None or minute_start != self._current_minute:
                # Finalize previous candle
                if self._current_candle is not None:
                    self._finalize_candle()

                # Start new candle
                dt = datetime.fromtimestamp(minute_start, tz=_IST)
                self._current_candle = {
                    "time": dt.strftime("%H:%M"),
                    "timestamp": minute_start,
                    "total_volume": 0.0,
                    "buy_volume": 0.0,
                    "sell_volume": 0.0,
                    "delta": 0.0,
                    "cvd": 0.0,
                }
                self._current_minute = minute_start

            # Accumulate into current candle
            self._current_candle["total_volume"] += volume
            self._total_volume += volume

            if direction == "buy":
                self._current_candle["buy_volume"] += volume
            else:
                self._current_candle["sell_volume"] += volume

            # Update delta on current candle
            self._current_candle["delta"] = (
                self._current_candle["buy_volume"] - self._current_candle["sell_volume"]
            )
            # CVD for current candle = accumulated CVD + current candle delta
            self._current_candle["cvd"] = self._cvd + self._current_candle["delta"]

    def _finalize_candle(self) -> None:
        """Move the current candle to the completed list. Must be called under lock."""
        if self._current_candle is None:
            return

        # Update running CVD
        self._cvd += self._current_candle["delta"]
        self._current_candle["cvd"] = self._cvd

        self._candles.append(self._current_candle)

        # Enforce rolling window
        if len(self._candles) > self._max_candles:
            self._candles = self._candles[-self._max_candles:]

        self._current_candle = None

    def get_snapshot(self) -> Dict:
        """Return a serializable snapshot for the status API. Thread-safe."""
        with self._lock:
            # Include completed candles + current in-progress candle
            candles = list(self._candles)
            if self._current_candle is not None:
                candles.append(self._current_candle)

            current_cvd = self._cvd
            current_delta = 0.0
            if self._current_candle is not None:
                current_cvd = self._current_candle["cvd"]
                current_delta = self._current_candle["delta"]

            return {
                "instrument_key": self.instrument_key,
                "futures_ltp": self._futures_ltp,
                "candles": candles,
                "current_cvd": current_cvd,
                "current_delta": current_delta,
                "total_volume": self._total_volume,
            }

    def reset(self) -> None:
        """Reset all state (e.g. at market open). Thread-safe."""
        with self._lock:
            self._prev_price = None
            self._last_direction = "buy"
            self._futures_ltp = 0.0
            self._current_candle = None
            self._current_minute = None
            self._candles = []
            self._cvd = 0.0
            self._total_volume = 0.0
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_futures_volume.py -v`
Expected: All 14 tests PASS

**Step 5: Commit**

```bash
git add app/core/futures_volume.py tests/test_futures_volume.py
git commit -m "feat: add FuturesVolumeTracker with 1-min candles, delta, CVD"
```

---

### Task 2: DataFetcher — Futures Instrument Key Lookup

**Files:**
- Modify: `backend/app/data/data_fetcher.py` (add method after `get_nearest_expiry` at ~line 589)

**Step 1: Write the test**

Add to the bottom of `tests/test_futures_volume.py`:

```python
class TestGetFuturesInstrumentKey:
    """Test DataFetcher.get_futures_instrument_key() with a mock instruments DataFrame."""

    def _make_fetcher_with_df(self, df):
        """Create a DataFetcher-like object with a pre-loaded instruments_df."""
        import pandas as pd
        from unittest.mock import MagicMock
        fetcher = MagicMock()
        fetcher.instruments_df = df
        # Bind the real method
        from app.data.data_fetcher import DataFetcher
        fetcher.get_futures_instrument_key = DataFetcher.get_futures_instrument_key.__get__(fetcher)
        return fetcher

    def test_finds_nearest_expiry_futures(self):
        import pandas as pd
        from datetime import datetime, timedelta
        today = datetime.now().date()
        near_expiry = today + timedelta(days=7)
        far_expiry = today + timedelta(days=37)

        df = pd.DataFrame({
            'name': ['NIFTY', 'NIFTY'],
            'instrument_type': ['FUTIDX', 'FUTIDX'],
            'expiry': pd.to_datetime([near_expiry, far_expiry]),
            'instrument_key': ['NSE_FO|11111', 'NSE_FO|22222'],
        })
        fetcher = self._make_fetcher_with_df(df)
        key = fetcher.get_futures_instrument_key()
        assert key == 'NSE_FO|11111'

    def test_returns_none_when_no_futures(self):
        import pandas as pd
        df = pd.DataFrame({
            'name': ['NIFTY'],
            'instrument_type': ['OPTIDX'],
            'expiry': pd.to_datetime(['2026-03-15']),
            'instrument_key': ['NSE_FO|99999'],
        })
        fetcher = self._make_fetcher_with_df(df)
        key = fetcher.get_futures_instrument_key()
        assert key is None

    def test_skips_expired_contracts(self):
        import pandas as pd
        from datetime import datetime, timedelta
        yesterday = datetime.now().date() - timedelta(days=1)
        future = datetime.now().date() + timedelta(days=14)

        df = pd.DataFrame({
            'name': ['NIFTY', 'NIFTY'],
            'instrument_type': ['FUTIDX', 'FUTIDX'],
            'expiry': pd.to_datetime([yesterday, future]),
            'instrument_key': ['NSE_FO|OLD', 'NSE_FO|VALID'],
        })
        fetcher = self._make_fetcher_with_df(df)
        key = fetcher.get_futures_instrument_key()
        assert key == 'NSE_FO|VALID'
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_futures_volume.py::TestGetFuturesInstrumentKey -v`
Expected: FAIL — `AttributeError: DataFetcher has no attribute 'get_futures_instrument_key'`

**Step 3: Add the method to DataFetcher**

In `backend/app/data/data_fetcher.py`, add after `get_nearest_expiry()` (after line 589):

```python
    def get_futures_instrument_key(self):
        """Find the near-month Nifty futures instrument key.
        Returns the instrument_key string (e.g. 'NSE_FO|12345') or None."""
        if self.instruments_df is None:
            self.load_instruments()

        today = datetime.now().date()

        nifty_futs = self.instruments_df[
            (self.instruments_df['name'] == 'NIFTY') &
            (self.instruments_df['instrument_type'] == 'FUTIDX')
        ].copy()

        if nifty_futs.empty:
            logger.warning("No Nifty futures found in instruments")
            return None

        nifty_futs['expiry_date'] = pd.to_datetime(nifty_futs['expiry']).dt.date
        future_futs = nifty_futs[nifty_futs['expiry_date'] >= today]

        if future_futs.empty:
            logger.warning("No unexpired Nifty futures found")
            return None

        nearest = future_futs.loc[future_futs['expiry_date'].idxmin()]
        key = nearest['instrument_key']

        if isinstance(key, str) and '|' in key:
            logger.info(f"Futures key: {key} (expiry: {nearest['expiry_date']})")
            return key

        logger.warning(f"Invalid futures key format: {key}")
        return None
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_futures_volume.py -v`
Expected: All tests PASS (both TestFuturesVolumeTracker and TestGetFuturesInstrumentKey)

**Step 5: Commit**

```bash
git add app/data/data_fetcher.py tests/test_futures_volume.py
git commit -m "feat: add get_futures_instrument_key() to DataFetcher"
```

---

### Task 3: MarketDataManager — Subscribe to Futures & Route Ticks

**Files:**
- Modify: `backend/app/core/market_data.py`

This task has no isolated unit test — it wires live WebSocket data to the tracker. We verify via integration (the bot running and seeing logs).

**Step 1: Add futures_volume_tracker attribute to `__init__`**

In `backend/app/core/market_data.py`, at the end of `__init__` (after line 99, before the closing of `__init__`), add:

```python
        # Futures Volume Tracker
        self.futures_volume_tracker = None  # Set by TradingBot after init
        self._futures_key: Optional[str] = None
```

Also add `Optional` to the typing import on line 5 if not already present (it is already there).

**Step 2: Subscribe to futures in `_start_streamer_logic`**

In `backend/app/core/market_data.py`, in `_start_streamer_logic()`, after the PCR option keys block (after line 169) and before the "Build instrument subscription list" comment (line 171), add:

```python
            # ── Futures instrument key ──────────────────────────────────────
            if not self._futures_key:
                self._futures_key = self.data_fetcher.get_futures_instrument_key()
                if self._futures_key:
                    logger.info(f"Nifty Futures: {self._futures_key}")
                else:
                    logger.warning("Could not find Nifty futures instrument")
```

Then in the subscription list building (after the PCR options block, around line 187), add:

```python
            # Add Nifty Futures
            if self._futures_key:
                instrument_keys.append(self._futures_key)
```

**Step 3: Route futures ticks in `_on_streamer_message`**

In `backend/app/core/market_data.py`, inside `_on_streamer_message()`, after the price caching block and before the Nifty 50 stock update check (around line 342, after the `logger.error` for price caching), add:

```python
                        # Route futures ticks to FuturesVolumeTracker
                        if (
                            key == self._futures_key
                            and self.futures_volume_tracker is not None
                            and price is not None
                        ):
                            # Extract traded volume for futures
                            fut_vol = traded_vol if traded_vol is not None else 0.0
                            self.futures_volume_tracker.on_tick(
                                price=float(price),
                                volume=float(fut_vol),
                                timestamp=time.time(),
                            )
```

**Step 4: Verify no syntax errors**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -c "from app.core.market_data import MarketDataManager; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add app/core/market_data.py
git commit -m "feat: subscribe to Nifty futures and route ticks to volume tracker"
```

---

### Task 4: TradingBot — Initialize Tracker & Add to Status

**Files:**
- Modify: `backend/main.py`

**Step 1: Add import at top of `main.py`**

After the intelligence imports (line 25), add:

```python
from app.core.futures_volume import FuturesVolumeTracker
```

**Step 2: Initialize tracker in `initialize()`**

In `main.py`, after `self.market_data` is created (after line 97), add:

```python
        # ── Futures Volume Tracker ──────────────────────────────────────
        self.futures_volume_tracker = FuturesVolumeTracker()
        self.market_data.futures_volume_tracker = self.futures_volume_tracker
```

**Step 3: Add `futures_volume` to `get_status()`**

In `main.py`, in `get_status()`, inside the `status = { ... }` dict (around line 461, before the closing `}`), add:

```python
            "futures_volume": self.futures_volume_tracker.get_snapshot() if self.futures_volume_tracker else None,
```

**Step 4: Verify no syntax errors**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -c "from main import TradingBot; print('OK')"`
Expected: `OK`

**Step 5: Run all existing tests to ensure nothing broke**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --ignore=tests/test_upstox.py`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add main.py
git commit -m "feat: wire FuturesVolumeTracker into TradingBot and status API"
```

---

### Task 5: Frontend Types — FuturesVolume TypeScript Interface

**Files:**
- Modify: `frontend/src/types/api.ts`

**Step 1: Add the FuturesVolume types**

At the bottom of `frontend/src/types/api.ts` (before the closing, after `ModuleToggleState` around line 297), add:

```typescript
// ═══ Futures Volume + CVD Types ═════════════════════════════════════════

export interface FuturesVolumeCandle {
    time: string;
    timestamp: number;
    total_volume: number;
    buy_volume: number;
    sell_volume: number;
    delta: number;
    cvd: number;
}

export interface FuturesVolumeData {
    instrument_key: string;
    futures_ltp: number;
    candles: FuturesVolumeCandle[];
    current_cvd: number;
    current_delta: number;
    total_volume: number;
}
```

**Step 2: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/frontend
git add src/types/api.ts
git commit -m "feat: add FuturesVolume TypeScript types"
```

---

### Task 6: FuturesVolumeStrip — React Component

**Files:**
- Create: `frontend/src/features/market/FuturesVolumeStrip.tsx`

**Step 1: Create the component**

```tsx
// src/features/market/FuturesVolumeStrip.tsx
import React, { useMemo } from 'react';
import type { FuturesVolumeData } from '../../types/api';

interface FuturesVolumeStripProps {
    data: FuturesVolumeData | null | undefined;
    height?: number;
}

/** Format large numbers: 1234567 -> "12.3L", 45000 -> "45.0K" */
function formatVolume(v: number): string {
    if (v >= 100000) return (v / 100000).toFixed(1) + 'L';
    if (v >= 1000) return (v / 1000).toFixed(1) + 'K';
    return v.toFixed(0);
}

const FuturesVolumeStrip: React.FC<FuturesVolumeStripProps> = ({ data, height = 160 }) => {
    const chartHeight = height - 52; // header ~32px + x-axis ~20px
    const svgWidth = 100; // viewBox width (percentage-based)

    const { bars, cvdPath, maxVol, cvdMin, cvdMax, timeLabels } = useMemo(() => {
        if (!data || !data.candles || data.candles.length === 0) {
            return { bars: [], cvdPath: '', maxVol: 0, cvdMin: 0, cvdMax: 0, timeLabels: [] };
        }

        const candles = data.candles;
        const n = candles.length;

        // Volume bar dimensions
        const maxVol = Math.max(...candles.map((c) => c.total_volume), 1);

        // CVD range
        const cvdValues = candles.map((c) => c.cvd);
        const cvdMin = Math.min(...cvdValues);
        const cvdMax = Math.max(...cvdValues);
        const cvdRange = cvdMax - cvdMin || 1;

        const pad = 4;
        const barGap = 0.4;
        const barW = Math.max((svgWidth - pad * 2) / n - barGap, 0.5);

        const bars = candles.map((c, i) => {
            const x = pad + i * ((svgWidth - pad * 2) / n);
            const barH = (c.total_volume / maxVol) * (chartHeight - pad * 2);
            const y = chartHeight - pad - barH;
            const isBuy = c.delta >= 0;
            return { x, y, w: barW, h: barH, isBuy, time: c.time };
        });

        // CVD polyline
        const cvdPts = candles.map((c, i) => {
            const x = pad + i * ((svgWidth - pad * 2) / n) + barW / 2;
            const y = pad + (1 - (c.cvd - cvdMin) / cvdRange) * (chartHeight - pad * 2);
            return `${x.toFixed(2)},${y.toFixed(2)}`;
        });
        const cvdPath = 'M' + cvdPts.join(' L');

        // Time labels (show every ~15 min = every 15th candle, or fewer if not enough)
        const labelInterval = Math.max(Math.floor(n / 6), 1);
        const timeLabels = candles
            .filter((_, i) => i % labelInterval === 0)
            .map((c, _i, arr) => {
                const idx = candles.indexOf(c);
                const x = pad + idx * ((svgWidth - pad * 2) / n) + barW / 2;
                return { x, label: c.time };
            });

        return { bars, cvdPath, maxVol, cvdMin, cvdMax, timeLabels };
    }, [data, chartHeight]);

    if (!data || !data.candles || data.candles.length === 0) {
        return (
            <div
                className="surface-elevated rounded-xl flex items-center justify-center text-[var(--text-muted)] text-sm"
                style={{ height }}
            >
                Waiting for futures volume data...
            </div>
        );
    }

    const cvdColor = data.current_cvd >= 0 ? 'var(--color-profit-text)' : 'var(--color-loss-text)';
    const deltaColor = data.current_delta >= 0 ? 'var(--color-profit-text)' : 'var(--color-loss-text)';

    return (
        <div className="surface-elevated rounded-xl overflow-hidden" style={{ height }}>
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 12px',
                    borderBottom: '1px solid var(--border-subtle)',
                }}
            >
                <span
                    style={{
                        fontSize: 'var(--text-sm)',
                        fontWeight: 600,
                        color: 'var(--text-secondary)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                    }}
                >
                    Futures Volume
                </span>
                <div style={{ display: 'flex', gap: '12px', fontSize: '11px' }}>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                        LTP{' '}
                        <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                            {data.futures_ltp.toFixed(1)}
                        </span>
                    </span>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                        CVD{' '}
                        <span style={{ color: cvdColor, fontWeight: 600 }}>
                            {data.current_cvd >= 0 ? '+' : ''}
                            {formatVolume(data.current_cvd)}
                        </span>
                    </span>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                        Delta{' '}
                        <span style={{ color: deltaColor, fontWeight: 600 }}>
                            {data.current_delta >= 0 ? '+' : ''}
                            {formatVolume(data.current_delta)}
                        </span>
                    </span>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                        Vol{' '}
                        <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                            {formatVolume(data.total_volume)}
                        </span>
                    </span>
                </div>
            </div>

            {/* Chart */}
            <svg
                viewBox={`0 0 ${svgWidth} ${chartHeight}`}
                className="w-full"
                style={{ height: chartHeight }}
                preserveAspectRatio="none"
            >
                {/* Volume bars */}
                {bars.map((bar, i) => (
                    <rect
                        key={i}
                        x={bar.x}
                        y={bar.y}
                        width={bar.w}
                        height={Math.max(bar.h, 0.3)}
                        fill={bar.isBuy ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)'}
                        rx={0.2}
                    />
                ))}

                {/* CVD line */}
                {cvdPath && (
                    <polyline
                        points={cvdPath.replace('M', '').replace(/L/g, ' ')}
                        fill="none"
                        stroke="var(--accent-blue)"
                        strokeWidth="0.6"
                        strokeLinejoin="round"
                    />
                )}
            </svg>

            {/* X-axis time labels */}
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '0 12px 4px',
                    fontSize: '9px',
                    color: 'var(--text-muted)',
                }}
            >
                {timeLabels.map((tl, i) => (
                    <span key={i}>{tl.label}</span>
                ))}
            </div>
        </div>
    );
};

export default FuturesVolumeStrip;
```

**Step 2: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/frontend
git add src/features/market/FuturesVolumeStrip.tsx
git commit -m "feat: add FuturesVolumeStrip component with volume bars + CVD line"
```

---

### Task 7: Dashboard — Wire FuturesVolumeStrip Into Layout

**Files:**
- Modify: `frontend/src/Dashboard.tsx`

**Step 1: Add import**

At the top of `Dashboard.tsx`, after the `IndicatorStrip` import (line 15), add:

```typescript
import FuturesVolumeStrip from './features/market/FuturesVolumeStrip';
```

**Step 2: Add the component to the layout**

In `Dashboard.tsx`, inside the left column `<div className="space-y-3 min-w-0">` block, between the chart card closing `</div>` (line 253) and the IndicatorStrip (line 256), add:

```tsx
                    {/* Futures Volume + CVD */}
                    <FuturesVolumeStrip data={(status as any)?.futures_volume} />
```

**Step 3: Verify the frontend builds**

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npx tsc --noEmit`
Expected: No type errors

**Step 4: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/frontend
git add src/Dashboard.tsx
git commit -m "feat: add FuturesVolumeStrip to dashboard layout"
```

---

### Task 8: Final Verification

**Step 1: Run all backend tests**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --ignore=tests/test_upstox.py`
Expected: All tests PASS

**Step 2: Verify backend imports clean**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -c "from main import TradingBot; bot = TradingBot(); print('TradingBot OK')"`
Expected: `TradingBot OK`

**Step 3: Verify frontend builds**

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npx tsc --noEmit && echo 'TypeScript OK'`
Expected: `TypeScript OK`

**Step 4: Final commit (if any fixes needed)**

Only commit if fixes were required in the verification steps.
