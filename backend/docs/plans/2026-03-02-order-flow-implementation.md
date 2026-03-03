# Order Flow & Microstructure Analytics — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add order flow analytics (VWAP, volume profile, delta divergence, book imbalance) as a backend analyzer, intelligence engine filter, and frontend dashboard tab.

**Architecture:** Dedicated `OrderFlowAnalyzer` class consumes futures ticks + order book depth from `MarketDataManager`, produces a snapshot consumed by both the status API (for frontend) and `OrderFlowModule` (intelligence filter). FuturesVolumeTracker stays unchanged.

**Tech Stack:** Python 3.11+, threading.Lock, pytest; React 18, TypeScript, pure SVG, Tailwind CSS, useMemo.

**Design doc:** `docs/plans/2026-03-02-order-flow-microstructure-design.md`

---

## Task 1: OrderFlowAnalyzer — VWAP + Volume Profile Core

**Files:**
- Create: `backend/app/core/order_flow.py`
- Create: `backend/tests/test_order_flow.py`

### Step 1: Write failing tests for VWAP and volume profile

```python
# backend/tests/test_order_flow.py
"""Tests for OrderFlowAnalyzer — VWAP, volume profile, divergence, book imbalance."""

import time
import pytest
from app.core.order_flow import OrderFlowAnalyzer


class TestOrderFlowAnalyzer:
    """Unit tests for OrderFlowAnalyzer."""

    # ── Initial state ────────────────────────────────────────────

    def test_initial_snapshot(self):
        analyzer = OrderFlowAnalyzer()
        snap = analyzer.get_snapshot()
        assert snap["vwap"] == 0.0
        assert snap["std_dev"] == 0.0
        assert snap["volume_profile"] == []
        assert snap["poc"] == 0.0
        assert snap["value_area_high"] == 0.0
        assert snap["value_area_low"] == 0.0
        assert snap["book_imbalance"] == 0.5
        assert snap["total_volume"] == 0.0
        assert snap["delta_divergence"]["active"] is False

    # ── VWAP ─────────────────────────────────────────────────────

    def test_vwap_single_tick(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=time.time())
        snap = analyzer.get_snapshot()
        assert snap["vwap"] == 25000.0
        assert snap["std_dev"] == 0.0

    def test_vwap_two_ticks(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=time.time())
        analyzer.on_tick(price=25100.0, volume=100, direction="buy", timestamp=time.time())
        snap = analyzer.get_snapshot()
        # VWAP = (25000*100 + 25100*100) / 200 = 25050
        assert snap["vwap"] == 25050.0

    def test_vwap_weighted_by_volume(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=300, direction="buy", timestamp=time.time())
        analyzer.on_tick(price=25100.0, volume=100, direction="sell", timestamp=time.time())
        snap = analyzer.get_snapshot()
        # VWAP = (25000*300 + 25100*100) / 400 = 25025
        assert snap["vwap"] == 25025.0

    def test_vwap_deviation_bands(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=time.time())
        analyzer.on_tick(price=25100.0, volume=100, direction="buy", timestamp=time.time())
        snap = analyzer.get_snapshot()
        assert snap["vwap_upper"] > snap["vwap"]
        assert snap["vwap_lower"] < snap["vwap"]
        assert snap["vwap_upper"] - snap["vwap"] == pytest.approx(snap["vwap"] - snap["vwap_lower"])

    def test_zero_volume_tick_ignored(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=0, direction="buy", timestamp=time.time())
        snap = analyzer.get_snapshot()
        assert snap["vwap"] == 0.0
        assert snap["total_volume"] == 0.0

    # ── Volume Profile ───────────────────────────────────────────

    def test_volume_profile_single_bin(self):
        analyzer = OrderFlowAnalyzer(bin_size=50.0)
        analyzer.on_tick(price=25010.0, volume=100, direction="buy", timestamp=time.time())
        analyzer.on_tick(price=25020.0, volume=50, direction="sell", timestamp=time.time())
        snap = analyzer.get_snapshot()
        assert len(snap["volume_profile"]) == 1
        bin_data = snap["volume_profile"][0]
        assert bin_data["price"] == 25000.0
        assert bin_data["buy_vol"] == 100
        assert bin_data["sell_vol"] == 50
        assert bin_data["total"] == 150

    def test_volume_profile_multiple_bins(self):
        analyzer = OrderFlowAnalyzer(bin_size=50.0)
        analyzer.on_tick(price=25010.0, volume=100, direction="buy", timestamp=time.time())
        analyzer.on_tick(price=25060.0, volume=200, direction="buy", timestamp=time.time())
        snap = analyzer.get_snapshot()
        assert len(snap["volume_profile"]) == 2
        # Sorted by price
        assert snap["volume_profile"][0]["price"] < snap["volume_profile"][1]["price"]

    def test_poc_is_highest_volume_bin(self):
        analyzer = OrderFlowAnalyzer(bin_size=50.0)
        analyzer.on_tick(price=25010.0, volume=100, direction="buy", timestamp=time.time())
        analyzer.on_tick(price=25060.0, volume=500, direction="buy", timestamp=time.time())
        snap = analyzer.get_snapshot()
        assert snap["poc"] == 25050.0  # 25060 rounds to 25050 bin

    def test_value_area_contains_poc(self):
        analyzer = OrderFlowAnalyzer(bin_size=50.0)
        # Spread volume across several bins
        for i in range(10):
            price = 24800.0 + i * 50
            vol = 500 if i == 5 else 100  # Heavy volume at bin 5
            analyzer.on_tick(price=price, volume=vol, direction="buy", timestamp=time.time())
        snap = analyzer.get_snapshot()
        assert snap["value_area_low"] <= snap["poc"] <= snap["value_area_high"]
```

### Step 2: Run tests to verify they fail

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_order_flow.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.order_flow'`

### Step 3: Write OrderFlowAnalyzer implementation

```python
# backend/app/core/order_flow.py
"""OrderFlowAnalyzer — computes VWAP, volume profile (POC + value area),
delta divergence alerts, and order book imbalance from futures tick data.

Thread-safe — called from the WebSocket background thread.
Resets at market open (09:15 IST) each trading day.
"""

import threading
from datetime import date, datetime, timezone, timedelta
from typing import Dict, List, Optional

from app.core.logger_config import logger

_IST = timezone(timedelta(hours=5, minutes=30))


class OrderFlowAnalyzer:
    """Computes order flow metrics from futures tick data and order book depth."""

    def __init__(self, bin_size: float = 50.0, max_bins: int = 40):
        self._lock = threading.Lock()
        self._bin_size = bin_size
        self._max_bins = max_bins

        # VWAP accumulators
        self._cum_pv: float = 0.0        # Σ(price * volume)
        self._cum_vol: float = 0.0       # Σ(volume)
        self._cum_pv2: float = 0.0       # Σ(volume * price²) — for deviation bands

        # Volume profile: {bin_price: {"buy": float, "sell": float}}
        self._profile: Dict[float, Dict[str, float]] = {}

        # Order book totals
        self._book_bids: float = 0.0
        self._book_asks: float = 0.0

        # Delta divergence tracking (candle-level)
        self._recent_prices: List[float] = []
        self._recent_cvds: List[float] = []
        self._divergence_lookback: int = 8

        # Daily reset
        self._last_reset_date: Optional[date] = None

    # ── Tick ingestion ───────────────────────────────────────────

    def on_tick(self, price: float, volume: float, direction: str, timestamp: float) -> None:
        """Process a single futures tick. Called from MarketDataManager."""
        with self._lock:
            self._maybe_reset(timestamp)
            if volume <= 0:
                return

            # VWAP accumulation
            self._cum_pv += price * volume
            self._cum_vol += volume
            self._cum_pv2 += volume * price * price

            # Volume profile binning
            bin_key = round(price / self._bin_size) * self._bin_size
            if bin_key not in self._profile:
                if len(self._profile) >= self._max_bins:
                    return  # Safety cap
                self._profile[bin_key] = {"buy": 0.0, "sell": 0.0}
            side = "buy" if direction == "buy" else "sell"
            self._profile[bin_key][side] += volume

    def on_candle_close(self, candle_close: float, cvd: float) -> None:
        """Track candle closes for divergence detection."""
        with self._lock:
            self._recent_prices.append(candle_close)
            self._recent_cvds.append(cvd)
            if len(self._recent_prices) > self._divergence_lookback:
                self._recent_prices.pop(0)
                self._recent_cvds.pop(0)

    def update_order_book(self, bids: List[Dict], asks: List[Dict]) -> None:
        """Update order book state from 5-level depth data."""
        with self._lock:
            self._book_bids = sum(float(b.get("qty", 0)) for b in bids)
            self._book_asks = sum(float(a.get("qty", 0)) for a in asks)

    # ── Snapshot ─────────────────────────────────────────────────

    def get_snapshot(self) -> Dict:
        """Return complete order flow state for API/frontend."""
        with self._lock:
            # VWAP + deviation bands
            vwap = self._cum_pv / self._cum_vol if self._cum_vol > 0 else 0.0
            variance = (self._cum_pv2 / self._cum_vol - vwap * vwap) if self._cum_vol > 0 else 0.0
            std_dev = variance ** 0.5 if variance > 0 else 0.0

            # Volume profile sorted by price
            profile = sorted(
                [
                    {
                        "price": p,
                        "buy_vol": v["buy"],
                        "sell_vol": v["sell"],
                        "total": v["buy"] + v["sell"],
                    }
                    for p, v in self._profile.items()
                ],
                key=lambda x: x["price"],
            )

            # POC
            poc = max(profile, key=lambda x: x["total"])["price"] if profile else 0.0

            # Value area
            va_high, va_low = self._compute_value_area(profile, poc)

            # Book imbalance (0.5 = balanced)
            total_book = self._book_bids + self._book_asks
            imbalance = self._book_bids / total_book if total_book > 0 else 0.5

            # Delta divergence
            divergence = self._detect_divergence()

            return {
                "vwap": round(vwap, 2),
                "vwap_upper": round(vwap + std_dev, 2),
                "vwap_lower": round(vwap - std_dev, 2),
                "std_dev": round(std_dev, 2),
                "volume_profile": profile,
                "poc": poc,
                "value_area_high": va_high,
                "value_area_low": va_low,
                "book_imbalance": round(imbalance, 3),
                "bid_total": self._book_bids,
                "ask_total": self._book_asks,
                "delta_divergence": divergence,
                "total_volume": self._cum_vol,
            }

    def reset(self) -> None:
        """Reset all state (e.g. at market open). Thread-safe."""
        with self._lock:
            self._cum_pv = 0.0
            self._cum_vol = 0.0
            self._cum_pv2 = 0.0
            self._profile = {}
            self._book_bids = 0.0
            self._book_asks = 0.0
            self._recent_prices = []
            self._recent_cvds = []
            self._last_reset_date = None

    # ── Private helpers ──────────────────────────────────────────

    def _maybe_reset(self, timestamp: float) -> None:
        """Reset at market open (09:15 IST) each trading day."""
        dt = datetime.fromtimestamp(timestamp, tz=_IST)
        today = dt.date()
        if self._last_reset_date == today:
            return
        if dt.hour > 9 or (dt.hour == 9 and dt.minute >= 15):
            if self._last_reset_date is not None and self._last_reset_date < today:
                # New trading day — clear accumulators
                self._cum_pv = 0.0
                self._cum_vol = 0.0
                self._cum_pv2 = 0.0
                self._profile = {}
                self._book_bids = 0.0
                self._book_asks = 0.0
                self._recent_prices = []
                self._recent_cvds = []
                logger.info("OrderFlowAnalyzer: daily reset (new trading day)")
            self._last_reset_date = today

    def _compute_value_area(self, profile: List[Dict], poc: float) -> tuple:
        """Value Area: expand outward from POC until 70% of total volume enclosed."""
        if not profile:
            return 0.0, 0.0

        total_vol = sum(b["total"] for b in profile)
        if total_vol <= 0:
            return 0.0, 0.0

        target = total_vol * 0.70
        # Find POC index
        poc_idx = 0
        for i, b in enumerate(profile):
            if b["price"] == poc:
                poc_idx = i
                break

        accumulated = profile[poc_idx]["total"]
        lo = poc_idx
        hi = poc_idx

        while accumulated < target and (lo > 0 or hi < len(profile) - 1):
            # Compare next bin above vs below; add the larger one
            vol_below = profile[lo - 1]["total"] if lo > 0 else -1
            vol_above = profile[hi + 1]["total"] if hi < len(profile) - 1 else -1

            if vol_below >= vol_above:
                lo -= 1
                accumulated += profile[lo]["total"]
            else:
                hi += 1
                accumulated += profile[hi]["total"]

        return profile[hi]["price"], profile[lo]["price"]

    def _detect_divergence(self) -> Dict:
        """Detect price vs CVD divergence over recent candles."""
        n = len(self._recent_prices)
        if n < 3:
            return {"active": False, "type": None, "strength": 0.0, "bars": 0}

        prices = self._recent_prices
        cvds = self._recent_cvds

        # Simple: compare first half vs second half trend
        mid = n // 2
        price_early = sum(prices[:mid]) / mid
        price_late = sum(prices[mid:]) / (n - mid)
        cvd_early = sum(cvds[:mid]) / mid
        cvd_late = sum(cvds[mid:]) / (n - mid)

        price_rising = price_late > price_early
        cvd_rising = cvd_late > cvd_early

        if price_rising and not cvd_rising:
            # Price up but CVD down → bearish divergence
            strength = min(1.0, abs(cvd_early - cvd_late) / max(abs(cvd_early), 1))
            return {"active": True, "type": "bearish", "strength": round(strength, 2), "bars": n}
        elif not price_rising and cvd_rising:
            # Price down but CVD up → bullish divergence
            strength = min(1.0, abs(cvd_late - cvd_early) / max(abs(cvd_early), 1))
            return {"active": True, "type": "bullish", "strength": round(strength, 2), "bars": n}

        return {"active": False, "type": None, "strength": 0.0, "bars": 0}
```

### Step 4: Run tests to verify they pass

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_order_flow.py -v`
Expected: All 12 tests PASS

### Step 5: Commit

```bash
git add app/core/order_flow.py tests/test_order_flow.py
git commit -m "feat: add OrderFlowAnalyzer with VWAP, volume profile, divergence, book imbalance"
```

---

## Task 2: OrderFlowAnalyzer — Divergence + Book Imbalance + Reset Tests

**Files:**
- Modify: `backend/tests/test_order_flow.py`

### Step 1: Add divergence, book imbalance, reset, and thread safety tests

Append to the `TestOrderFlowAnalyzer` class in `tests/test_order_flow.py`:

```python
    # ── Book Imbalance ───────────────────────────────────────────

    def test_book_imbalance_balanced(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.update_order_book(
            bids=[{"qty": 100}, {"qty": 100}],
            asks=[{"qty": 100}, {"qty": 100}],
        )
        snap = analyzer.get_snapshot()
        assert snap["book_imbalance"] == 0.5

    def test_book_imbalance_bid_heavy(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.update_order_book(
            bids=[{"qty": 300}, {"qty": 200}],
            asks=[{"qty": 100}, {"qty": 100}],
        )
        snap = analyzer.get_snapshot()
        # 500 / 700 ≈ 0.714
        assert snap["book_imbalance"] > 0.6

    def test_book_imbalance_ask_heavy(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.update_order_book(
            bids=[{"qty": 50}],
            asks=[{"qty": 200}, {"qty": 300}],
        )
        snap = analyzer.get_snapshot()
        assert snap["book_imbalance"] < 0.4

    def test_book_imbalance_empty_book(self):
        analyzer = OrderFlowAnalyzer()
        snap = analyzer.get_snapshot()
        assert snap["book_imbalance"] == 0.5  # default neutral

    # ── Delta Divergence ─────────────────────────────────────────

    def test_no_divergence_with_few_candles(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.on_candle_close(25000.0, 100.0)
        analyzer.on_candle_close(25010.0, 110.0)
        snap = analyzer.get_snapshot()
        assert snap["delta_divergence"]["active"] is False

    def test_bearish_divergence_detected(self):
        analyzer = OrderFlowAnalyzer()
        # Price rising, CVD falling
        for i in range(8):
            analyzer.on_candle_close(
                candle_close=25000.0 + i * 10,   # Rising
                cvd=1000.0 - i * 50,              # Falling
            )
        snap = analyzer.get_snapshot()
        assert snap["delta_divergence"]["active"] is True
        assert snap["delta_divergence"]["type"] == "bearish"

    def test_bullish_divergence_detected(self):
        analyzer = OrderFlowAnalyzer()
        # Price falling, CVD rising
        for i in range(8):
            analyzer.on_candle_close(
                candle_close=25100.0 - i * 10,   # Falling
                cvd=500.0 + i * 50,               # Rising
            )
        snap = analyzer.get_snapshot()
        assert snap["delta_divergence"]["active"] is True
        assert snap["delta_divergence"]["type"] == "bullish"

    def test_no_divergence_when_aligned(self):
        analyzer = OrderFlowAnalyzer()
        # Both rising — no divergence
        for i in range(8):
            analyzer.on_candle_close(25000.0 + i * 10, 500.0 + i * 50)
        snap = analyzer.get_snapshot()
        assert snap["delta_divergence"]["active"] is False

    def test_divergence_lookback_window(self):
        analyzer = OrderFlowAnalyzer()
        # Add 12 candles — only last 8 should matter
        for i in range(12):
            analyzer.on_candle_close(25000.0 + i, 500.0 + i * 10)
        assert len(analyzer._recent_prices) == 8

    # ── Reset ────────────────────────────────────────────────────

    def test_reset_clears_all_state(self):
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=time.time())
        analyzer.update_order_book([{"qty": 100}], [{"qty": 100}])
        analyzer.on_candle_close(25000.0, 100.0)
        analyzer.reset()
        snap = analyzer.get_snapshot()
        assert snap["vwap"] == 0.0
        assert snap["total_volume"] == 0.0
        assert snap["volume_profile"] == []
        assert snap["book_imbalance"] == 0.5
        assert snap["delta_divergence"]["active"] is False

    # ── Thread safety ────────────────────────────────────────────

    def test_thread_safety_no_crash(self):
        import threading
        analyzer = OrderFlowAnalyzer()
        errors = []

        def writer():
            try:
                for i in range(200):
                    analyzer.on_tick(25000.0 + i * 0.05, 10, "buy", time.time())
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(200):
                    analyzer.get_snapshot()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start(); t2.start()
        t1.join(); t2.join()
        assert errors == []
```

### Step 2: Run tests

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_order_flow.py -v`
Expected: All ~24 tests PASS

### Step 3: Commit

```bash
git add tests/test_order_flow.py
git commit -m "test: add divergence, book imbalance, reset, and thread safety tests for OrderFlowAnalyzer"
```

---

## Task 3: OrderFlowModule (Intelligence Engine Plugin)

**Files:**
- Create: `backend/app/intelligence/order_flow_module.py`
- Create: `backend/tests/test_order_flow_module.py`

### Step 1: Write failing tests

```python
# backend/tests/test_order_flow_module.py
"""Tests for OrderFlowModule — intelligence engine plugin for order flow filtering."""

import time
import pytest
from app.core.order_flow import OrderFlowAnalyzer
from app.intelligence.order_flow_module import OrderFlowModule


class TestOrderFlowModule:
    """Unit tests for OrderFlowModule."""

    def _make_module(self) -> OrderFlowModule:
        analyzer = OrderFlowAnalyzer()
        return OrderFlowModule(analyzer)

    def _feed_analyzer(self, module: OrderFlowModule, price: float = 25000.0,
                       volume: float = 100, direction: str = "buy",
                       bids_qty: float = 200, asks_qty: float = 100):
        """Feed data into the module's underlying analyzer."""
        module._analyzer.on_tick(price, volume, direction, time.time())
        module._analyzer.update_order_book(
            [{"qty": bids_qty}], [{"qty": asks_qty}]
        )

    def test_module_name(self):
        module = self._make_module()
        assert module.name == "order_flow"

    def test_get_context_empty_state(self):
        module = self._make_module()
        ctx = module.get_context()
        assert "score" in ctx
        assert "pass" in ctx
        assert ctx["pass"] is True  # Default: don't block with no data

    def test_update_does_not_crash(self):
        module = self._make_module()
        module.update({"price": 25000, "signal_direction": "CE"})

    def test_bullish_signal_passes_with_bullish_data(self):
        module = self._make_module()
        # Feed bullish data: price above VWAP, bid-heavy book
        for i in range(5):
            module._analyzer.on_tick(24900.0 + i * 50, 100, "buy", time.time())
        module._analyzer.update_order_book(
            [{"qty": 300}, {"qty": 200}],
            [{"qty": 100}, {"qty": 50}],
        )
        module.update({"signal_direction": "CE"})
        ctx = module.get_context()
        assert ctx["score"] > 0

    def test_bearish_signal_passes_with_bearish_data(self):
        module = self._make_module()
        for i in range(5):
            module._analyzer.on_tick(25100.0 - i * 50, 100, "sell", time.time())
        module._analyzer.update_order_book(
            [{"qty": 50}],
            [{"qty": 300}, {"qty": 200}],
        )
        module.update({"signal_direction": "PE"})
        ctx = module.get_context()
        assert ctx["score"] > 0

    def test_reset_works(self):
        module = self._make_module()
        module._analyzer.on_tick(25000.0, 100, "buy", time.time())
        module.reset()
        ctx = module.get_context()
        assert ctx["pass"] is True  # Safe default after reset

    def test_components_dict_has_expected_keys(self):
        module = self._make_module()
        module._analyzer.on_tick(25000.0, 100, "buy", time.time())
        module.update({"signal_direction": "CE"})
        ctx = module.get_context()
        assert "components" in ctx
        components = ctx["components"]
        assert "vwap_alignment" in components
        assert "delta_momentum" in components
        assert "book_support" in components
        assert "volume_profile" in components
```

### Step 2: Run tests to verify they fail

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_order_flow_module.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.intelligence.order_flow_module'`

### Step 3: Write OrderFlowModule implementation

```python
# backend/app/intelligence/order_flow_module.py
"""OrderFlowModule — intelligence engine plugin that wraps OrderFlowAnalyzer
for signal confirmation/rejection.

Inputs (via update):
    data['signal_direction'] — "CE" or "PE" (current signal candidate)

Outputs (via get_context):
    pass       : bool — True if composite score >= 40
    score      : float — 0-100 composite
    components : dict of sub-scores (vwap_alignment, delta_momentum, etc.)
    alerts     : list of string alerts
    snapshot   : full OrderFlowAnalyzer snapshot (for frontend)
"""

import logging
from typing import Any, Dict

from app.intelligence.base import IntelligenceModule

logger = logging.getLogger(__name__)


class OrderFlowModule(IntelligenceModule):
    name = "order_flow"

    def __init__(self, analyzer):
        self._analyzer = analyzer
        self._signal_direction: str = "CE"  # Default

    # ── IntelligenceModule interface ─────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        direction = data.get("signal_direction")
        if direction:
            self._signal_direction = direction

    def get_context(self) -> Dict[str, Any]:
        snapshot = self._analyzer.get_snapshot()

        # No data yet — don't block
        if snapshot["total_volume"] == 0:
            return {
                "pass": True,
                "score": 50,
                "components": {
                    "vwap_alignment": 50,
                    "delta_momentum": 50,
                    "book_support": 50,
                    "volume_profile": 50,
                },
                "alerts": [],
                "snapshot": snapshot,
            }

        scores = {
            "vwap_alignment": self._score_vwap(snapshot),
            "delta_momentum": self._score_delta(snapshot),
            "book_support": self._score_book(snapshot),
            "volume_profile": self._score_profile(snapshot),
        }

        composite = sum(scores.values()) / len(scores)

        return {
            "pass": composite >= 40,
            "score": round(composite, 1),
            "components": scores,
            "alerts": self._build_alerts(snapshot),
            "snapshot": snapshot,
        }

    def reset(self) -> None:
        self._analyzer.reset()
        self._signal_direction = "CE"

    # ── Scoring helpers ──────────────────────────────────────────

    def _score_vwap(self, snap: Dict) -> float:
        """Score VWAP alignment: is price positioned correctly for direction?"""
        vwap = snap["vwap"]
        if vwap == 0:
            return 50

        # Use last known price from volume profile (highest volume bin approximation)
        # Since we don't track LTP, use POC as proxy for "current area"
        poc = snap["poc"]
        if poc == 0:
            return 50

        if self._signal_direction == "CE":
            if poc > vwap:
                return 80
            elif poc >= snap["vwap_lower"]:
                return 50
            else:
                return 20
        else:  # PE
            if poc < vwap:
                return 80
            elif poc <= snap["vwap_upper"]:
                return 50
            else:
                return 20

    def _score_delta(self, snap: Dict) -> float:
        """Score delta/CVD momentum: no divergence against signal = good."""
        div = snap["delta_divergence"]
        if not div["active"]:
            return 80  # No divergence — neutral-to-positive

        if self._signal_direction == "CE" and div["type"] == "bearish":
            return max(20, 80 - div["strength"] * 60)
        elif self._signal_direction == "PE" and div["type"] == "bullish":
            return max(20, 80 - div["strength"] * 60)

        return 80  # Divergence supports our direction

    def _score_book(self, snap: Dict) -> float:
        """Score order book imbalance alignment."""
        imb = snap["book_imbalance"]

        if self._signal_direction == "CE":
            if imb > 0.55:
                return 80
            elif imb >= 0.45:
                return 50
            else:
                return 20
        else:  # PE
            if imb < 0.45:
                return 80
            elif imb <= 0.55:
                return 50
            else:
                return 20

    def _score_profile(self, snap: Dict) -> float:
        """Score volume profile: is price within value area?"""
        poc = snap["poc"]
        va_high = snap["value_area_high"]
        va_low = snap["value_area_low"]

        if poc == 0:
            return 50

        if self._signal_direction == "CE":
            if poc >= va_low:
                return 80 if poc >= snap.get("vwap", 0) else 60
            return 30
        else:  # PE
            if poc <= va_high:
                return 80 if poc <= snap.get("vwap", 0) else 60
            return 30

    def _build_alerts(self, snap: Dict) -> list:
        """Build human-readable alerts for the frontend."""
        alerts = []
        div = snap["delta_divergence"]
        if div["active"]:
            alerts.append(
                f"{'⚠️ Bearish' if div['type'] == 'bearish' else '📈 Bullish'} "
                f"divergence (strength {div['strength']:.0%}, {div['bars']} bars)"
            )
        imb = snap["book_imbalance"]
        if imb > 0.65:
            alerts.append(f"🟢 Strong bid pressure ({imb:.1%})")
        elif imb < 0.35:
            alerts.append(f"🔴 Strong ask pressure ({imb:.1%})")
        return alerts
```

### Step 4: Run tests to verify they pass

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_order_flow_module.py -v`
Expected: All 8 tests PASS

### Step 5: Run all order flow tests together

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_order_flow.py tests/test_order_flow_module.py -v`
Expected: All ~32 tests PASS

### Step 6: Commit

```bash
git add app/intelligence/order_flow_module.py tests/test_order_flow_module.py
git commit -m "feat: add OrderFlowModule intelligence plugin with composite scoring"
```

---

## Task 4: Wire OrderFlowAnalyzer into Backend

**Files:**
- Modify: `backend/main.py` (lines 80-102 and line 468)
- Modify: `backend/app/core/market_data.py` (lines 366-393)
- Modify: `backend/app/core/futures_volume.py` (line 95-103, `_finalize_candle`)
- Modify: `backend/app/strategies/strategy.py` (lines 706-729 and 753-761)

### Step 1: Wire OrderFlowAnalyzer in main.py

In `backend/main.py`:

**Add import** (near top, after other core imports):
```python
from app.core.order_flow import OrderFlowAnalyzer
from app.intelligence.order_flow_module import OrderFlowModule
```

**Create analyzer + register module** (after line 102, before strategy_runner creation):
```python
        # ── Order Flow Analyzer ───────────────────────────────────────
        self.order_flow_analyzer = OrderFlowAnalyzer()
        self.market_data.order_flow_analyzer = self.order_flow_analyzer
        self.intelligence_engine.register(OrderFlowModule(self.order_flow_analyzer))
```

**Update module count log** (line 91): Change `"7 modules"` → `"8 modules"`

**Add to get_status()** (line 468, after `futures_volume` entry):
```python
            "order_flow": self.order_flow_analyzer.get_snapshot() if hasattr(self, 'order_flow_analyzer') and self.order_flow_analyzer else None,
```

### Step 2: Wire tick feeding in market_data.py

In `backend/app/core/market_data.py`:

**Add attribute** at class init level (add `self.order_flow_analyzer = None` near where `self.futures_volume_tracker = None` is declared).

**Feed ticks** — insert after line 391 (after `self.futures_volume_tracker.on_tick(...)`) but still inside the `try` block:

```python
                                # Feed OrderFlowAnalyzer (same tick data + direction)
                                if self.order_flow_analyzer is not None:
                                    # Reuse direction from FuturesVolumeTracker
                                    ofa_dir = self.futures_volume_tracker._last_direction if self.futures_volume_tracker else "buy"
                                    self.order_flow_analyzer.on_tick(
                                        price=float(price),
                                        volume=fut_vol,
                                        direction=ofa_dir,
                                        timestamp=time.time(),
                                    )
```

**Feed order book** — insert right after the above, still inside the same `try` block:

```python
                                    # Feed futures order book depth
                                    if "fullFeed" in feed:
                                        mff = feed["fullFeed"].get("marketFF", {})
                                        market_level = mff.get("marketLevel", {})
                                        raw_depth = market_level.get("bidAskQuote", [])
                                        if raw_depth:
                                            bids = [{"price": float(e.get("bidP", 0)), "qty": float(e.get("bidQ", 0))} for e in raw_depth if e.get("bidP")]
                                            asks = [{"price": float(e.get("askP", 0)), "qty": float(e.get("askQ", 0))} for e in raw_depth if e.get("askP")]
                                            if bids or asks:
                                                self.order_flow_analyzer.update_order_book(bids, asks)
```

### Step 3: Wire candle-close callback in futures_volume.py

In `backend/app/core/futures_volume.py`, add a callback mechanism to `_finalize_candle()`:

**Add callback attribute** in `__init__` (after line 36):
```python
        self._on_candle_close_cb = None  # Optional callback: fn(candle_close, cvd)
```

**Call it in `_finalize_candle`** (after line 96, `self._current_candle["cvd"] = self._cvd`):
```python
        if self._on_candle_close_cb:
            try:
                self._on_candle_close_cb(
                    self._current_candle.get("buy_volume", 0) + self._current_candle.get("sell_volume", 0),
                    self._cvd,
                )
            except Exception as e:
                logger.debug(f"Candle close callback error: {e}")
```

Wait — actually that passes total_volume, not candle_close price. The design says `on_candle_close(candle_close: float, cvd: float)` where candle_close is the **price**. We don't store close price in FuturesVolumeTracker candles (it only has volume data). So we need to pass the last tick price instead.

**Better approach:** In `_finalize_candle`, use `self._futures_ltp` as the candle close price:

```python
        if self._on_candle_close_cb:
            try:
                self._on_candle_close_cb(self._futures_ltp, self._cvd)
            except Exception as e:
                logger.debug(f"Candle close callback error: {e}")
```

**Wire the callback in main.py** (after creating order_flow_analyzer):
```python
        self.futures_volume_tracker._on_candle_close_cb = self.order_flow_analyzer.on_candle_close
```

### Step 4: Add `order_flow` as intelligence filter in strategy.py

In `backend/app/strategies/strategy.py`:

**Add the filter evaluation** (after line 716, inside the `for direction in ("BUY_CE", "BUY_PE"):` loop):
```python
                passes_of, r_of = self._check_order_flow_filter(intel, direction) if intel else (True, "")
```

**Add to the filter dict** (after line 728, inside `intelligence_filter_reasons[direction]`):
```python
                    "order_flow":     (passes_of,         r_of),
```

**Add to filter_checks** (after line 761):
```python
            filter_checks['order_flow'] = _filter_ok('order_flow')
```

**Add the filter method** (anywhere in the class, near the other `_check_*_filter` methods):
```python
    def _check_order_flow_filter(self, intel: Dict, direction: str) -> tuple:
        """Check order flow analysis supports the signal direction."""
        of_ctx = intel.get("order_flow")
        if not of_ctx:
            return True, ""  # No data — don't block
        if not of_ctx.get("pass", True):
            score = of_ctx.get("score", 0)
            return False, f"Order flow score {score:.0f}/100 (needs ≥40)"
        return True, ""
```

### Step 5: Verify existing tests still pass

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests PASS (no regressions)

### Step 6: Commit

```bash
git add main.py app/core/market_data.py app/core/futures_volume.py app/strategies/strategy.py
git commit -m "feat: wire OrderFlowAnalyzer into market data pipeline, intelligence engine, and strategy filters"
```

---

## Task 5: Frontend — TypeScript Types + OrderFlowHeader

**Files:**
- Modify: `frontend/src/types/api.ts` (append after line 318)
- Create: `frontend/src/features/order-flow/OrderFlowHeader.tsx`

### Step 1: Add TypeScript types

Append to `frontend/src/types/api.ts` after line 318 (after FuturesVolumeData interface):

```typescript
// ═══ Order Flow & Microstructure Types ════════════════════════════════════

export interface VolumeProfileBin {
    price: number;
    buy_vol: number;
    sell_vol: number;
    total: number;
}

export interface DeltaDivergence {
    active: boolean;
    type: 'bullish' | 'bearish' | null;
    strength: number;
    bars: number;
}

export interface OrderFlowData {
    vwap: number;
    vwap_upper: number;
    vwap_lower: number;
    std_dev: number;
    volume_profile: VolumeProfileBin[];
    poc: number;
    value_area_high: number;
    value_area_low: number;
    book_imbalance: number;
    bid_total: number;
    ask_total: number;
    delta_divergence: DeltaDivergence;
    total_volume: number;
}
```

### Step 2: Create OrderFlowHeader component

```typescript
// frontend/src/features/order-flow/OrderFlowHeader.tsx
import React from 'react';
import type { OrderFlowData } from '../../types/api';

interface OrderFlowHeaderProps {
    data: OrderFlowData | null | undefined;
    futuresLtp?: number;
}

function fmt(v: number): string {
    if (!v) return '--';
    return v.toLocaleString('en-IN', { maximumFractionDigits: 1 });
}

function fmtVol(v: number): string {
    const abs = Math.abs(v);
    if (abs >= 100000) return (abs / 100000).toFixed(1) + 'L';
    if (abs >= 1000) return (abs / 1000).toFixed(1) + 'K';
    return abs.toFixed(0);
}

const OrderFlowHeader: React.FC<OrderFlowHeaderProps> = ({ data, futuresLtp }) => {
    if (!data) {
        return (
            <div className="flex items-center gap-4 px-3 py-2 text-xs text-[var(--text-tertiary)]">
                Order Flow — waiting for data...
            </div>
        );
    }

    const { vwap, poc, book_imbalance, delta_divergence, total_volume } = data;
    const imb = book_imbalance;
    const imbLabel = imb > 0.55 ? 'BID' : imb < 0.45 ? 'ASK' : 'BAL';
    const imbColor = imb > 0.55
        ? 'var(--color-profit-text)'
        : imb < 0.45
        ? 'var(--color-loss-text)'
        : 'var(--text-secondary)';

    const priceVsVwap = futuresLtp && vwap > 0
        ? futuresLtp > vwap ? '▲ Above' : futuresLtp < vwap ? '▼ Below' : '— At'
        : '--';
    const priceVwapColor = futuresLtp && vwap > 0
        ? futuresLtp > vwap ? 'var(--color-profit-text)' : 'var(--color-loss-text)'
        : 'var(--text-tertiary)';

    return (
        <div className="flex items-center gap-5 px-3 py-2 text-xs border-b border-[var(--border-subtle)]">
            <span className="flex items-center gap-1.5">
                <span className="text-[var(--text-tertiary)]">VWAP</span>
                <span className="mono font-semibold">{fmt(vwap)}</span>
                <span className="mono" style={{ color: priceVwapColor }}>{priceVsVwap}</span>
            </span>
            <span className="flex items-center gap-1.5">
                <span className="text-[var(--text-tertiary)]">POC</span>
                <span className="mono font-semibold">{fmt(poc)}</span>
            </span>
            <span className="flex items-center gap-1.5">
                <span className="text-[var(--text-tertiary)]">Book</span>
                <span className="mono font-semibold" style={{ color: imbColor }}>
                    {(imb * 100).toFixed(0)}% {imbLabel}
                </span>
            </span>
            {delta_divergence?.active && (
                <span
                    className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                    style={{
                        background: delta_divergence.type === 'bearish'
                            ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)',
                        color: delta_divergence.type === 'bearish'
                            ? 'var(--color-loss-text)' : 'var(--color-profit-text)',
                    }}
                >
                    {delta_divergence.type === 'bearish' ? '⚠️ Bearish' : '📈 Bullish'} Div
                </span>
            )}
            <span className="ml-auto text-[var(--text-tertiary)]">
                Vol {fmtVol(total_volume)}
            </span>
        </div>
    );
};

export default React.memo(OrderFlowHeader);
```

### Step 3: Commit

```bash
git add frontend/src/types/api.ts frontend/src/features/order-flow/OrderFlowHeader.tsx
git commit -m "feat: add OrderFlow TypeScript types and OrderFlowHeader component"
```

---

## Task 6: Frontend — VolumeProfileChart

**Files:**
- Create: `frontend/src/features/order-flow/VolumeProfileChart.tsx`

### Step 1: Create VolumeProfileChart

```typescript
// frontend/src/features/order-flow/VolumeProfileChart.tsx
import React, { useMemo } from 'react';
import type { VolumeProfileBin } from '../../types/api';

interface VolumeProfileChartProps {
    profile: VolumeProfileBin[];
    poc: number;
    valueAreaHigh: number;
    valueAreaLow: number;
    height?: number;
}

const VolumeProfileChart: React.FC<VolumeProfileChartProps> = ({
    profile, poc, valueAreaHigh, valueAreaLow, height = 260,
}) => {
    const svgW = 320;
    const padX = 55;
    const padY = 10;
    const barAreaW = svgW - padX - 10;

    const bars = useMemo(() => {
        if (!profile || profile.length === 0) return [];

        const maxVol = Math.max(...profile.map(b => b.total));
        if (maxVol <= 0) return [];

        const barH = Math.max(4, Math.min(18, (height - padY * 2) / profile.length - 1));

        return profile.map((bin, i) => {
            const y = padY + i * (barH + 1);
            const buyW = (bin.buy_vol / maxVol) * barAreaW;
            const sellW = (bin.sell_vol / maxVol) * barAreaW;
            const inVA = bin.price >= valueAreaLow && bin.price <= valueAreaHigh;
            const isPOC = bin.price === poc;

            return { ...bin, y, barH, buyW, sellW, inVA, isPOC };
        });
    }, [profile, poc, valueAreaHigh, valueAreaLow, height]);

    if (bars.length === 0) {
        return (
            <div className="flex items-center justify-center text-xs text-[var(--text-tertiary)]" style={{ height }}>
                No volume profile data
            </div>
        );
    }

    const totalH = bars.length > 0 ? bars[bars.length - 1].y + bars[bars.length - 1].barH + padY : height;

    return (
        <div>
            <div className="text-[10px] font-semibold text-[var(--text-tertiary)] mb-1 px-1">VOLUME PROFILE</div>
            <svg viewBox={`0 0 ${svgW} ${totalH}`} width="100%" style={{ maxHeight: height }}>
                {bars.map((bar, i) => (
                    <g key={i}>
                        {/* Value area background */}
                        {bar.inVA && (
                            <rect x={padX} y={bar.y - 0.5} width={barAreaW} height={bar.barH + 1}
                                fill="rgba(99,102,241,0.06)" />
                        )}
                        {/* Buy bar (green, from left) */}
                        <rect x={padX} y={bar.y} width={bar.buyW} height={bar.barH}
                            fill={bar.isPOC ? 'rgba(34,197,94,0.8)' : 'rgba(34,197,94,0.45)'}
                            rx={1} />
                        {/* Sell bar (red, stacked after buy) */}
                        <rect x={padX + bar.buyW} y={bar.y} width={bar.sellW} height={bar.barH}
                            fill={bar.isPOC ? 'rgba(239,68,68,0.8)' : 'rgba(239,68,68,0.45)'}
                            rx={1} />
                        {/* POC marker */}
                        {bar.isPOC && (
                            <line x1={padX} y1={bar.y + bar.barH / 2} x2={padX + barAreaW}
                                y2={bar.y + bar.barH / 2} stroke="rgba(99,102,241,0.6)"
                                strokeWidth={1} strokeDasharray="3,3" />
                        )}
                        {/* Price label */}
                        <text x={padX - 4} y={bar.y + bar.barH / 2 + 3}
                            textAnchor="end" fontSize={9}
                            fill={bar.isPOC ? 'var(--accent-indigo)' : 'var(--text-tertiary)'}
                            fontWeight={bar.isPOC ? 700 : 400}
                            fontFamily="var(--font-mono)">
                            {bar.price.toFixed(0)}
                        </text>
                    </g>
                ))}
            </svg>
        </div>
    );
};

export default React.memo(VolumeProfileChart);
```

### Step 2: Commit

```bash
git add frontend/src/features/order-flow/VolumeProfileChart.tsx
git commit -m "feat: add VolumeProfileChart component with POC and value area highlighting"
```

---

## Task 7: Frontend — VWAPChart

**Files:**
- Create: `frontend/src/features/order-flow/VWAPChart.tsx`

### Step 1: Create VWAPChart

This chart shows the VWAP level with deviation bands as a simple gauge/status display (we don't have historical VWAP data for a line chart — we only get the current snapshot). Instead, render a vertical price scale with VWAP bands + POC + current position indicator.

```typescript
// frontend/src/features/order-flow/VWAPChart.tsx
import React, { useMemo } from 'react';
import type { OrderFlowData } from '../../types/api';

interface VWAPChartProps {
    data: OrderFlowData | null | undefined;
    futuresLtp?: number;
    height?: number;
}

const VWAPChart: React.FC<VWAPChartProps> = ({ data, futuresLtp, height = 260 }) => {
    const svgW = 400;
    const padX = 50;
    const padY = 25;
    const chartW = svgW - padX * 2;
    const chartH = height - padY * 2;

    const elements = useMemo(() => {
        if (!data || data.vwap === 0) return null;

        const { vwap, vwap_upper, vwap_lower, poc, value_area_high, value_area_low } = data;
        const ltp = futuresLtp || poc;

        // Determine price range for the chart
        const allPrices = [vwap, vwap_upper, vwap_lower, poc, value_area_high, value_area_low, ltp].filter(p => p > 0);
        const minP = Math.min(...allPrices) - 20;
        const maxP = Math.max(...allPrices) + 20;
        const range = maxP - minP || 1;

        const yOf = (p: number) => padY + chartH - ((p - minP) / range) * chartH;

        return {
            vwapY: yOf(vwap),
            upperY: yOf(vwap_upper),
            lowerY: yOf(vwap_lower),
            pocY: yOf(poc),
            vaHighY: yOf(value_area_high),
            vaLowY: yOf(value_area_low),
            ltpY: yOf(ltp),
            vwap, vwap_upper, vwap_lower, poc, ltp,
        };
    }, [data, futuresLtp, height]);

    if (!elements) {
        return (
            <div className="flex items-center justify-center text-xs text-[var(--text-tertiary)]" style={{ height }}>
                Waiting for VWAP data...
            </div>
        );
    }

    const { vwapY, upperY, lowerY, pocY, vaHighY, vaLowY, ltpY, vwap, vwap_upper, vwap_lower, poc, ltp } = elements;

    return (
        <div>
            <div className="text-[10px] font-semibold text-[var(--text-tertiary)] mb-1 px-1">VWAP & LEVELS</div>
            <svg viewBox={`0 0 ${svgW} ${height}`} width="100%" style={{ maxHeight: height }}>
                {/* Value area band */}
                <rect x={padX} y={vaHighY} width={chartW} height={Math.max(1, vaLowY - vaHighY)}
                    fill="rgba(99,102,241,0.08)" />

                {/* VWAP deviation band */}
                <rect x={padX} y={upperY} width={chartW} height={Math.max(1, lowerY - upperY)}
                    fill="rgba(251,191,36,0.08)" />

                {/* Upper band */}
                <line x1={padX} y1={upperY} x2={padX + chartW} y2={upperY}
                    stroke="rgba(251,191,36,0.4)" strokeWidth={1} strokeDasharray="4,4" />
                <text x={padX - 4} y={upperY + 3} textAnchor="end" fontSize={9}
                    fill="rgba(251,191,36,0.7)" fontFamily="var(--font-mono)">
                    {vwap_upper.toFixed(0)}
                </text>

                {/* VWAP line */}
                <line x1={padX} y1={vwapY} x2={padX + chartW} y2={vwapY}
                    stroke="rgba(251,191,36,0.9)" strokeWidth={2} />
                <text x={padX - 4} y={vwapY + 3} textAnchor="end" fontSize={10}
                    fill="rgba(251,191,36,1)" fontWeight={700} fontFamily="var(--font-mono)">
                    {vwap.toFixed(0)}
                </text>
                <text x={padX + chartW + 4} y={vwapY + 3} fontSize={9}
                    fill="rgba(251,191,36,0.8)">VWAP</text>

                {/* Lower band */}
                <line x1={padX} y1={lowerY} x2={padX + chartW} y2={lowerY}
                    stroke="rgba(251,191,36,0.4)" strokeWidth={1} strokeDasharray="4,4" />
                <text x={padX - 4} y={lowerY + 3} textAnchor="end" fontSize={9}
                    fill="rgba(251,191,36,0.7)" fontFamily="var(--font-mono)">
                    {vwap_lower.toFixed(0)}
                </text>

                {/* POC line */}
                <line x1={padX} y1={pocY} x2={padX + chartW} y2={pocY}
                    stroke="rgba(99,102,241,0.7)" strokeWidth={1.5} strokeDasharray="6,3" />
                <text x={padX + chartW + 4} y={pocY + 3} fontSize={9}
                    fill="rgba(99,102,241,0.9)">POC</text>

                {/* LTP marker */}
                <circle cx={padX + chartW / 2} cy={ltpY} r={5}
                    fill={ltp > vwap ? 'var(--color-profit-text)' : 'var(--color-loss-text)'}
                    stroke="var(--bg-primary)" strokeWidth={1.5} />
                <text x={padX + chartW / 2 + 10} y={ltpY + 3} fontSize={9}
                    fill="var(--text-primary)" fontWeight={600} fontFamily="var(--font-mono)">
                    {ltp.toFixed(0)} LTP
                </text>
            </svg>
        </div>
    );
};

export default React.memo(VWAPChart);
```

### Step 2: Commit

```bash
git add frontend/src/features/order-flow/VWAPChart.tsx
git commit -m "feat: add VWAPChart component with deviation bands and level visualization"
```

---

## Task 8: Frontend — OrderBookPanel

**Files:**
- Create: `frontend/src/features/order-flow/OrderBookPanel.tsx`

### Step 1: Create OrderBookPanel

```typescript
// frontend/src/features/order-flow/OrderBookPanel.tsx
import React, { useMemo } from 'react';
import type { OrderFlowData } from '../../types/api';

interface OrderBookPanelProps {
    data: OrderFlowData | null | undefined;
    height?: number;
}

function fmtQty(v: number): string {
    if (v >= 100000) return (v / 100000).toFixed(1) + 'L';
    if (v >= 1000) return (v / 1000).toFixed(1) + 'K';
    return v.toFixed(0);
}

const OrderBookPanel: React.FC<OrderBookPanelProps> = ({ data, height = 260 }) => {
    const gaugeData = useMemo(() => {
        if (!data) return null;
        const { bid_total, ask_total, book_imbalance } = data;
        const total = bid_total + ask_total;
        if (total <= 0) return null;
        const bidPct = (bid_total / total) * 100;
        const askPct = (ask_total / total) * 100;
        return { bid_total, ask_total, book_imbalance, bidPct, askPct };
    }, [data]);

    if (!gaugeData) {
        return (
            <div className="flex items-center justify-center text-xs text-[var(--text-tertiary)]" style={{ height }}>
                No order book data
            </div>
        );
    }

    const { bid_total, ask_total, book_imbalance, bidPct, askPct } = gaugeData;
    const imbPct = (book_imbalance * 100).toFixed(1);
    const biasLabel = book_imbalance > 0.55 ? 'BULLISH' : book_imbalance < 0.45 ? 'BEARISH' : 'NEUTRAL';
    const biasColor = book_imbalance > 0.55
        ? 'var(--color-profit-text)'
        : book_imbalance < 0.45
        ? 'var(--color-loss-text)'
        : 'var(--text-secondary)';

    // SVG gauge
    const svgW = 260;
    const svgH = 140;
    const barW = 200;
    const barH = 20;
    const barX = (svgW - barW) / 2;
    const barY = 60;

    return (
        <div>
            <div className="text-[10px] font-semibold text-[var(--text-tertiary)] mb-1 px-1">ORDER BOOK IMBALANCE</div>
            <div className="flex flex-col items-center" style={{ minHeight: height - 30 }}>
                <svg viewBox={`0 0 ${svgW} ${svgH}`} width="100%" style={{ maxHeight: svgH }}>
                    {/* Bias label */}
                    <text x={svgW / 2} y={25} textAnchor="middle" fontSize={16} fontWeight={700}
                        fill={biasColor}>{biasLabel}</text>
                    <text x={svgW / 2} y={42} textAnchor="middle" fontSize={11}
                        fill="var(--text-tertiary)" fontFamily="var(--font-mono)">{imbPct}%</text>

                    {/* Stacked bar: bids (green) | asks (red) */}
                    <rect x={barX} y={barY} width={barW} height={barH} rx={4}
                        fill="rgba(239,68,68,0.3)" />
                    <rect x={barX} y={barY} width={barW * (bidPct / 100)} height={barH} rx={4}
                        fill="rgba(34,197,94,0.6)" />

                    {/* Center line */}
                    <line x1={barX + barW / 2} y1={barY - 2} x2={barX + barW / 2} y2={barY + barH + 2}
                        stroke="var(--text-tertiary)" strokeWidth={1} opacity={0.4} />

                    {/* Labels */}
                    <text x={barX} y={barY + barH + 16} fontSize={10}
                        fill="var(--color-profit-text)" fontFamily="var(--font-mono)">
                        BID {fmtQty(bid_total)}
                    </text>
                    <text x={barX + barW} y={barY + barH + 16} textAnchor="end" fontSize={10}
                        fill="var(--color-loss-text)" fontFamily="var(--font-mono)">
                        ASK {fmtQty(ask_total)}
                    </text>

                    {/* Percentage labels */}
                    <text x={barX + 6} y={barY + barH / 2 + 4} fontSize={10} fontWeight={600}
                        fill="white" fontFamily="var(--font-mono)">{bidPct.toFixed(0)}%</text>
                    <text x={barX + barW - 6} y={barY + barH / 2 + 4} textAnchor="end"
                        fontSize={10} fontWeight={600} fill="white"
                        fontFamily="var(--font-mono)">{askPct.toFixed(0)}%</text>
                </svg>

                {/* Interpretation */}
                <div className="text-[10px] text-[var(--text-tertiary)] text-center mt-1 px-4">
                    {book_imbalance > 0.6
                        ? 'Strong buying pressure — bids significantly outweigh asks'
                        : book_imbalance < 0.4
                        ? 'Strong selling pressure — asks significantly outweigh bids'
                        : 'Balanced order book — no significant directional pressure'}
                </div>
            </div>
        </div>
    );
};

export default React.memo(OrderBookPanel);
```

### Step 2: Commit

```bash
git add frontend/src/features/order-flow/OrderBookPanel.tsx
git commit -m "feat: add OrderBookPanel component with imbalance gauge"
```

---

## Task 9: Frontend — OrderFlowTab + BottomTabs Integration

**Files:**
- Create: `frontend/src/features/order-flow/OrderFlowTab.tsx`
- Modify: `frontend/src/layout/BottomTabs.tsx`
- Modify: `frontend/src/Dashboard.tsx`

### Step 1: Create OrderFlowTab (orchestrator component)

```typescript
// frontend/src/features/order-flow/OrderFlowTab.tsx
import React from 'react';
import type { OrderFlowData } from '../../types/api';
import OrderFlowHeader from './OrderFlowHeader';
import VolumeProfileChart from './VolumeProfileChart';
import VWAPChart from './VWAPChart';
import OrderBookPanel from './OrderBookPanel';

interface OrderFlowTabProps {
    data: OrderFlowData | null | undefined;
    futuresLtp?: number;
}

const OrderFlowTab: React.FC<OrderFlowTabProps> = ({ data, futuresLtp }) => {
    return (
        <div>
            <OrderFlowHeader data={data} futuresLtp={futuresLtp} />
            <div className="grid gap-3 lg:grid-cols-3 p-2">
                <VolumeProfileChart
                    profile={data?.volume_profile ?? []}
                    poc={data?.poc ?? 0}
                    valueAreaHigh={data?.value_area_high ?? 0}
                    valueAreaLow={data?.value_area_low ?? 0}
                />
                <VWAPChart data={data} futuresLtp={futuresLtp} />
                <OrderBookPanel data={data} />
            </div>
        </div>
    );
};

export default React.memo(OrderFlowTab);
```

### Step 2: Modify BottomTabs.tsx

**Add import and tab type** — in `frontend/src/layout/BottomTabs.tsx`:

1. **Update TabId type** (line 17):
```typescript
type TabId = 'positions' | 'analytics' | 'scalp_health' | 'intelligence' | 'order_flow' | 'backtest';
```

2. **Add icon import** (line 2) — add `Waves` to the lucide-react import:
```typescript
import { BarChart2, Brain, History, TestTube2, Activity, Waves } from 'lucide-react';
```

3. **Add lazy import** (after line 15):
```typescript
const OrderFlowTabContent = React.lazy(() => import('../features/order-flow/OrderFlowTab'));
```

4. **Add tab to TABS array** (after line 28, the scalp_health entry):
```typescript
    { id: 'order_flow',  label: 'Order Flow', icon: <Waves size={13} /> },
```

5. **Add to BottomTabsProps interface** (after line 53):
```typescript
    // Order Flow tab
    orderFlowData?: any;
    futuresLtp?: number;
```

6. **Add to mounted state** (after line 102, the scalp_health entry):
```typescript
        order_flow: false,
```

7. **Add tab panel** (after the scalp_health panel block, before the intelligence panel block — after line 200):
```typescript
                {/* Order Flow (React.lazy) */}
                {mounted.order_flow && (
                    <div style={{ display: activeTab === 'order_flow' ? 'block' : 'none' }}>
                        <Suspense fallback={<Skeleton lines={6} />}>
                            <OrderFlowTabContent
                                data={props.orderFlowData}
                                futuresLtp={props.futuresLtp}
                            />
                        </Suspense>
                    </div>
                )}
```

### Step 3: Modify Dashboard.tsx

Pass `orderFlowData` and `futuresLtp` to `BottomTabs` via `bottomTabsProps`.

In `frontend/src/Dashboard.tsx`, update the `bottomTabsProps` useMemo (around line 82-97):

Add these two properties:
```typescript
        orderFlowData: (status as any)?.order_flow,
        futuresLtp: (status as any)?.futures_volume?.futures_ltp,
```

And add them to the dependency array.

### Step 4: Verify build succeeds

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npx tsc --noEmit`
Expected: No type errors

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npm run build`
Expected: Build succeeds

### Step 5: Commit

```bash
git add frontend/src/features/order-flow/OrderFlowTab.tsx frontend/src/layout/BottomTabs.tsx frontend/src/Dashboard.tsx
git commit -m "feat: add Order Flow tab to dashboard with lazy loading and BottomTabs integration"
```

---

## Task 10: Integration Verification

**Files:** None (verification only)

### Step 1: Run all backend tests

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --timeout=30`
Expected: All tests pass, including new `test_order_flow.py` and `test_order_flow_module.py`

### Step 2: Run frontend build

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npm run build`
Expected: Build succeeds with no errors

### Step 3: Verify backend starts cleanly

Run: `cd /Users/jitendrasonawane/Workpace/backend && timeout 10 python main.py 2>&1 || true`
Expected: No import errors. Server starts (may timeout due to auth, which is fine — we just check no crashes).

### Step 4: Final commit (if any fixes needed)

If any fixes were needed during verification, commit them:
```bash
git add -A && git commit -m "fix: address integration issues from order flow wiring"
```

---

## Summary

| Task | What | Files | Est. |
|------|------|-------|------|
| 1 | OrderFlowAnalyzer core + tests | `order_flow.py`, `test_order_flow.py` | 45 min |
| 2 | Additional analyzer tests | `test_order_flow.py` | 20 min |
| 3 | OrderFlowModule + tests | `order_flow_module.py`, `test_order_flow_module.py` | 30 min |
| 4 | Backend wiring | `main.py`, `market_data.py`, `futures_volume.py`, `strategy.py` | 30 min |
| 5 | TS types + OrderFlowHeader | `api.ts`, `OrderFlowHeader.tsx` | 20 min |
| 6 | VolumeProfileChart | `VolumeProfileChart.tsx` | 20 min |
| 7 | VWAPChart | `VWAPChart.tsx` | 20 min |
| 8 | OrderBookPanel | `OrderBookPanel.tsx` | 20 min |
| 9 | OrderFlowTab + BottomTabs | `OrderFlowTab.tsx`, `BottomTabs.tsx`, `Dashboard.tsx` | 25 min |
| 10 | Integration verification | — | 15 min |
| **Total** | | **14 files** | **~4 hours** |
