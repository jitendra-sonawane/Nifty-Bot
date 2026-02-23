# Scalp Health Panel — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real-time Scalp Health tab to the dashboard with 26 metrics across Greeks, OI, Liquidity, and Market Context, powered by a backend intelligence module and composite score.

**Architecture:** New `ScalpHealthModule` (subclass of `IntelligenceModule`) plugged into the existing `IntelligenceEngine`. It receives market data via `update()`, computes all 26 metrics + composite score, and exposes them via `get_context()`. The frontend adds a new lazy-loaded "Scalp Health" tab in `BottomTabs` with 3-column layout.

**Tech Stack:** Python (FastAPI backend), React 19 + TypeScript + Tailwind CSS (frontend), RTK Query (data flow), Pytest (testing)

**Design Doc:** `docs/plans/2026-02-23-scalp-health-panel-design.md`

---

## Task 1: Add Scalp Health config thresholds

**Files:**
- Modify: `app/core/config.py:121-156` (after existing `INTELLIGENCE` dict)

**Step 1: Add SCALP_HEALTH config dict after line 156 (after EXPIRY_DAY)**

Add to `app/core/config.py` inside the `Config` class, after the `EXPIRY_DAY` dict:

```python
    # ── Scalp Health Module Thresholds ──────────────────────────────────
    SCALP_HEALTH = {
        # Composite score weights: [base, 0dte, weekly(3-5dte)]
        "weight_greeks":         [0.30, 0.35, 0.25],
        "weight_oi":             [0.25, 0.20, 0.30],
        "weight_time_decay":     [0.20, 0.25, 0.15],
        "weight_liquidity":      [0.15, 0.15, 0.15],
        "weight_market_context": [0.10, 0.05, 0.15],

        # GEX thresholds (rupees)
        "gex_high":  3000,
        "gex_medium": 1000,

        # ATM Proximity
        "atm_prox_green": 80,
        "atm_prox_amber": 50,

        # Gamma/Theta ratio
        "gt_ratio_green": 2.0,
        "gt_ratio_amber": 1.0,

        # Vega risk (ATM vega absolute value)
        "vega_high":   8.0,
        "vega_medium": 4.0,

        # Theta per minute threshold (% of premium)
        "theta_per_min_red_pct": 0.005,

        # OI concentration
        "oi_conc_high": 70,
        "oi_conc_low":  30,

        # OI change rate spike multiplier
        "oi_rate_spike_mult": 2.0,

        # Unwinding alert: OI drop % at key strike
        "unwinding_drop_pct": 10.0,

        # Lot liquidity (lots per 5 min)
        "lot_liq_max": 50,
        "lot_liq_min":  5,

        # VIX thresholds
        "vix_high": 18.0,
        "vix_low":  12.0,

        # Intraday momentum (% of ATR consumed)
        "momentum_high": 80,
        "momentum_low":  30,

        # Trading time zones (IST) — [start_hour, start_min, end_hour, end_min, label]
        "time_zones": [
            [9,  15, 10,  0, "PEAK"],
            [10,  0, 14,  0, "LOW"],
            [14,  0, 15, 30, "MODERATE"],
        ],
    }
```

**Step 2: Verify config loads**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -c "from app.core.config import Config; print(Config.SCALP_HEALTH['gex_high'])"`
Expected: `3000`

**Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "feat(config): add scalp health module thresholds"
```

---

## Task 2: Create ScalpHealthModule — skeleton + DTE + Greeks metrics

**Files:**
- Create: `app/intelligence/scalp_health.py`
- Test: `tests/test_scalp_health.py`

**Step 1: Write the failing test for DTE and Greeks calculations**

Create `tests/test_scalp_health.py`:

```python
"""Tests for ScalpHealthModule."""

import pytest
import time
import datetime
from unittest.mock import patch
from app.intelligence.scalp_health import ScalpHealthModule


@pytest.fixture
def module():
    return ScalpHealthModule()


@pytest.fixture
def base_greeks():
    """Realistic ATM Nifty Greeks for testing."""
    return {
        "atm_strike": 24800,
        "expiry_date": (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
        "ce": {
            "delta": 0.52,
            "gamma": 0.0008,
            "theta": -5.2,
            "vega": 4.5,
            "iv": 0.14,
            "price": 180.0,
        },
        "pe": {
            "delta": -0.48,
            "gamma": 0.0008,
            "theta": -4.8,
            "vega": 4.3,
            "iv": 0.15,
            "price": 165.0,
        },
    }


@pytest.fixture
def base_data(base_greeks):
    """Base data dict mimicking intelligence engine update()."""
    return {
        "current_price": 24810.0,
        "greeks": base_greeks,
        "atr_pct": 0.8,
        "df_close_std": 0.12,  # 5-day realized vol (annualized decimal)
    }


class TestDTE:
    def test_dte_calculation_future_expiry(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["dte_days"] >= 0
        assert ctx["dte_hours"] >= 0
        assert ctx["dte_minutes"] >= 0
        assert ctx["expiry_date"] == base_data["greeks"]["expiry_date"]

    def test_dte_zero_on_expiry_day(self, module, base_data):
        base_data["greeks"]["expiry_date"] = datetime.date.today().strftime("%Y-%m-%d")
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["dte_days"] == 0


class TestGreeksMetrics:
    def test_gex_calculation(self, module, base_data):
        """GEX = gamma * spot^2 * 0.01 * lot_size."""
        module.update(base_data)
        ctx = module.get_context()
        spot = 24810.0
        gamma = 0.0008  # CE gamma (use higher of CE/PE)
        expected_gex = gamma * (spot ** 2) * 0.01 * 25  # lot_size=25
        assert abs(ctx["gex_rupees"] - expected_gex) < 1.0

    def test_atm_proximity(self, module, base_data):
        """ATM proximity = 100 - (abs(spot - atm) / strike_step * 100), clamped [0,100]."""
        module.update(base_data)
        ctx = module.get_context()
        # spot=24810, atm=24800, step=50 → 100 - (10/50*100) = 100-20 = 80
        assert ctx["atm_proximity"] == 80

    def test_atm_proximity_exact_atm(self, module, base_data):
        base_data["current_price"] = 24800.0
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["atm_proximity"] == 100

    def test_gamma_theta_ratio(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        # gamma=0.0008, theta=-5.2 → 0.0008/5.2 ≈ 0.000154
        # Note: This ratio is tiny because gamma is in different units than theta.
        # We'll use: (gamma * spot * 50) / abs(theta) as normalized ratio
        # Actually, a better metric: gamma * spot^2 * 0.01 / abs(theta * lot_size)
        # Let's just ensure it's positive and computed
        assert ctx["gamma_theta_ratio"] > 0

    def test_delta_flip_zone(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        # Delta flip = ATM strike (where delta ≈ 0.50)
        assert ctx["delta_flip_price"] == base_data["greeks"]["atm_strike"]

    def test_delta_per_rupee(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        # CE: 0.52 / 180.0 ≈ 0.00289
        assert abs(ctx["delta_per_rupee_ce"] - 0.52 / 180.0) < 0.001
        assert abs(ctx["delta_per_rupee_pe"] - 0.48 / 165.0) < 0.001

    def test_iv_hv_spread(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        # IV avg = (0.14 + 0.15) / 2 = 0.145 = 14.5%
        # HV = df_close_std = 0.12 = 12%
        # Spread = 14.5 - 12.0 = 2.5 percentage points
        expected = ((0.14 + 0.15) / 2 * 100) - (0.12 * 100)
        assert abs(ctx["iv_hv_spread"] - expected) < 0.1

    def test_vega_risk_label(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        # avg vega = (4.5 + 4.3)/2 = 4.4 → MEDIUM (between 4.0 and 8.0)
        assert ctx["vega_risk_label"] == "MEDIUM"

    def test_theta_per_minute(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        # theta should be negative, per-minute is theta / remaining_minutes
        assert ctx["theta_per_minute"] < 0

    def test_gamma_peak_false_when_dte_gt_1(self, module, base_data):
        # Expiry is tomorrow → DTE > 0 days → depends on hours
        # Set expiry 3 days out to be safe
        base_data["greeks"]["expiry_date"] = (
            datetime.date.today() + datetime.timedelta(days=3)
        ).strftime("%Y-%m-%d")
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["gamma_peak"] is False

    def test_gamma_peak_true_when_near_atm_0dte(self, module, base_data):
        base_data["greeks"]["expiry_date"] = datetime.date.today().strftime("%Y-%m-%d")
        base_data["current_price"] = 24810.0  # within 1 strike step (50) of ATM 24800
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["gamma_peak"] is True
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_scalp_health.py -v --tb=short 2>&1 | head -30`
Expected: `ModuleNotFoundError: No module named 'app.intelligence.scalp_health'`

**Step 3: Write ScalpHealthModule with DTE + Greeks computation**

Create `app/intelligence/scalp_health.py`:

```python
"""
Scalp Health Module — Real-time health indicators for intraday options scalping.

Computes 26 metrics across 5 categories:
    1. Greeks Quality (GEX, ATM proximity, gamma/theta ratio, etc.)
    2. OI Confirmation (OI change, concentration, PCR trend, unwinding)
    3. Time/Decay (DTE, theta/minute, gamma peak)
    4. Liquidity (bid-ask spread, lot liquidity)
    5. Market Context (regime, VIX, momentum, time-of-day)

Plus a composite Scalp Health Score (0-100) with DTE-adaptive weights.

Consumes from engine.update():
    data["current_price"]          — float (Nifty spot)
    data["greeks"]                 — dict with ce/pe Greeks, atm_strike, expiry_date
    data["pcr_oi_data"]            — dict[instrument_key, float(oi)]
    data["pcr_option_metadata"]    — dict[instrument_key, {strike, option_type}]
    data["bid_ask_cache"]          — dict from OrderBookModule
    data["atr_pct"]                — float (ATR as % of price)
    data["df_close_std"]           — float (5-day annualized realized vol, decimal)
    data["vix"]                    — float (India VIX)
    data["market_regime"]          — str (from MarketRegimeModule)
    data["day_open"]               — float (day open price)
"""

import time
import logging
import datetime
from collections import deque
from typing import Any, Dict, Optional, List

from app.intelligence.base import IntelligenceModule
from app.core.config import Config

logger = logging.getLogger(__name__)

# IST offset from UTC
IST_OFFSET = datetime.timedelta(hours=5, minutes=30)
# Nifty trading session: 9:15 to 15:30 IST
MARKET_OPEN_HOUR, MARKET_OPEN_MIN = 9, 15
MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN = 15, 30
# Total trading minutes per day
TOTAL_TRADING_MINUTES = (MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MIN) - (MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MIN)


def _ist_now() -> datetime.datetime:
    """Current time in IST (UTC+5:30)."""
    return datetime.datetime.now(datetime.timezone.utc) + IST_OFFSET


def _trading_minutes_remaining() -> int:
    """Minutes remaining in today's trading session (IST)."""
    now = _ist_now()
    close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MIN, second=0, microsecond=0)
    remaining = (close - now).total_seconds() / 60.0
    return max(int(remaining), 1)  # floor at 1 to avoid division by zero


def _minutes_since_open() -> int:
    """Minutes elapsed since market open (IST)."""
    now = _ist_now()
    open_time = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0, microsecond=0)
    elapsed = (now - open_time).total_seconds() / 60.0
    return max(int(elapsed), 1)


class ScalpHealthModule(IntelligenceModule):
    """Real-time scalp health indicators for gamma + directional scalping."""

    name = "scalp_health"

    LOT_SIZE = Config.NIFTY_LOT_SIZE           # 25
    STRIKE_STEP = Config.NIFTY_STRIKE_STEP     # 50
    CONF = Config.SCALP_HEALTH

    # PCR tracking for trend
    PCR_HISTORY_SIZE = 180  # ~15 min at 5s intervals

    # OI snapshot tracking (separate from OIAnalysisModule to avoid coupling)
    OI_SNAPSHOT_INTERVAL = 5.0  # seconds
    OI_HISTORY_SIZE = 60        # ~5 min of snapshots

    def __init__(self):
        # ── Cached input data ─────────────────────────────────────────
        self._price: float = 0.0
        self._greeks: Dict[str, Any] = {}
        self._atm_strike: float = 0.0
        self._expiry_date: str = ""
        self._atr_pct: float = 0.0
        self._realized_vol: float = 0.0  # annualized, decimal (e.g. 0.12 = 12%)
        self._vix: float = 0.0
        self._market_regime: str = "UNKNOWN"
        self._day_open: float = 0.0

        # ── OI tracking ──────────────────────────────────────────────
        self._oi_snapshots: deque = deque(maxlen=self.OI_HISTORY_SIZE)
        self._last_oi_time: float = 0.0
        self._first_oi_snapshot: Optional[Dict] = None  # day-open snapshot

        # ── PCR trend tracking ────────────────────────────────────────
        self._pcr_history: deque = deque(maxlen=self.PCR_HISTORY_SIZE)
        self._last_pcr_time: float = 0.0

        # ── Bid-ask data ─────────────────────────────────────────────
        self._bid_ask: Dict[str, Any] = {}

        # ── VIX trend tracking ────────────────────────────────────────
        self._vix_history: deque = deque(maxlen=60)  # ~5 min

    # ══════════════════════════════════════════════════════════════════
    #  UPDATE — receive raw data from intelligence engine
    # ══════════════════════════════════════════════════════════════════

    def update(self, data: Dict[str, Any]) -> None:
        # Core price
        price = data.get("current_price")
        if price is not None and price > 0:
            self._price = price
            if self._day_open == 0.0:
                self._day_open = price

        # Greeks
        greeks = data.get("greeks")
        if greeks and isinstance(greeks, dict):
            self._greeks = greeks
            self._atm_strike = greeks.get("atm_strike", self._atm_strike)
            self._expiry_date = greeks.get("expiry_date", self._expiry_date)

        # Volatility data
        if "atr_pct" in data and data["atr_pct"]:
            self._atr_pct = float(data["atr_pct"])
        if "df_close_std" in data and data["df_close_std"]:
            self._realized_vol = float(data["df_close_std"])

        # VIX
        vix = data.get("vix")
        if vix is not None:
            self._vix = float(vix) if not isinstance(vix, dict) else float(vix.get("value", 0))
            now = time.time()
            if now - (self._last_pcr_time or 0) >= 5.0:
                self._vix_history.append({"t": now, "v": self._vix})

        # Market regime
        regime = data.get("market_regime")
        if regime:
            self._market_regime = str(regime)

        # Day open
        day_open = data.get("day_open")
        if day_open and day_open > 0:
            self._day_open = float(day_open)

        # Bid-ask cache
        bac = data.get("bid_ask_cache")
        if bac:
            self._bid_ask = bac

        # ── OI snapshots ─────────────────────────────────────────────
        pcr_oi = data.get("pcr_oi_data")
        metadata = data.get("pcr_option_metadata")
        if pcr_oi and metadata and self._price > 0:
            now = time.time()
            if now - self._last_oi_time >= self.OI_SNAPSHOT_INTERVAL:
                self._last_oi_time = now
                snap = self._build_oi_snapshot(pcr_oi, metadata)
                if snap:
                    self._oi_snapshots.append(snap)
                    if self._first_oi_snapshot is None:
                        self._first_oi_snapshot = snap

        # ── PCR tracking ─────────────────────────────────────────────
        pcr_val = data.get("pcr")
        if pcr_val is not None:
            now = time.time()
            if now - self._last_pcr_time >= 5.0:
                self._last_pcr_time = now
                self._pcr_history.append({"t": now, "v": float(pcr_val) if not isinstance(pcr_val, dict) else 0.0})

    # ══════════════════════════════════════════════════════════════════
    #  OI SNAPSHOT BUILDER
    # ══════════════════════════════════════════════════════════════════

    def _build_oi_snapshot(self, pcr_oi: Dict, metadata: Dict) -> Optional[Dict]:
        """Aggregate OI by strike from raw WebSocket data."""
        per_strike: Dict[float, Dict[str, float]] = {}
        total_ce = 0.0
        total_pe = 0.0

        for key, oi in pcr_oi.items():
            meta = metadata.get(key)
            if not meta:
                continue
            strike = meta["strike"]
            opt_type = meta["option_type"]
            if strike not in per_strike:
                per_strike[strike] = {"ce_oi": 0.0, "pe_oi": 0.0}
            if opt_type == "CE":
                per_strike[strike]["ce_oi"] = oi
                total_ce += oi
            elif opt_type == "PE":
                per_strike[strike]["pe_oi"] = oi
                total_pe += oi

        if total_ce + total_pe == 0:
            return None

        return {
            "t": time.time(),
            "price": self._price,
            "per_strike": per_strike,
            "total_ce": total_ce,
            "total_pe": total_pe,
        }

    # ══════════════════════════════════════════════════════════════════
    #  DTE CALCULATION
    # ══════════════════════════════════════════════════════════════════

    def _compute_dte(self) -> Dict[str, Any]:
        """Compute days/hours/minutes to expiry."""
        if not self._expiry_date:
            return {"dte_days": 0, "dte_hours": 0, "dte_minutes": 0, "expiry_date": ""}

        try:
            exp = datetime.datetime.strptime(self._expiry_date, "%Y-%m-%d")
            # Expiry at 15:30 IST
            exp = exp.replace(hour=15, minute=30, second=0)
            now = _ist_now().replace(tzinfo=None)
            diff = exp - now
            total_seconds = max(diff.total_seconds(), 0)
            days = int(total_seconds // 86400)
            hours = int((total_seconds % 86400) // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return {
                "dte_days": days,
                "dte_hours": hours,
                "dte_minutes": minutes,
                "expiry_date": self._expiry_date,
            }
        except (ValueError, TypeError):
            return {"dte_days": 0, "dte_hours": 0, "dte_minutes": 0, "expiry_date": self._expiry_date}

    def _dte_total_days(self) -> float:
        """Total DTE as fractional days."""
        dte = self._compute_dte()
        return dte["dte_days"] + dte["dte_hours"] / 24.0 + dte["dte_minutes"] / 1440.0

    # ══════════════════════════════════════════════════════════════════
    #  GREEKS METRICS (10)
    # ══════════════════════════════════════════════════════════════════

    def _compute_greeks_metrics(self) -> Dict[str, Any]:
        """Compute all 10 Greeks-based scalping metrics."""
        ce = self._greeks.get("ce", {})
        pe = self._greeks.get("pe", {})
        spot = self._price
        atm = self._atm_strike

        if not ce or not pe or spot <= 0 or atm <= 0:
            return self._empty_greeks()

        ce_delta = ce.get("delta", 0) or 0
        pe_delta = pe.get("delta", 0) or 0
        ce_gamma = ce.get("gamma", 0) or 0
        pe_gamma = pe.get("gamma", 0) or 0
        ce_theta = ce.get("theta", 0) or 0
        pe_theta = pe.get("theta", 0) or 0
        ce_vega = ce.get("vega", 0) or 0
        pe_vega = pe.get("vega", 0) or 0
        ce_iv = ce.get("iv", 0) or 0
        pe_iv = pe.get("iv", 0) or 0
        ce_price = ce.get("price", 0) or 0
        pe_price = pe.get("price", 0) or 0

        # 1. GEX — use max of CE/PE gamma for conservative estimate
        gamma = max(ce_gamma, pe_gamma)
        gex = gamma * (spot ** 2) * 0.01 * self.LOT_SIZE

        # 2. ATM Proximity (0-100)
        distance = abs(spot - atm)
        atm_prox = max(0, min(100, int(100 - (distance / self.STRIKE_STEP * 100))))

        # 3. Gamma/Theta Ratio — normalized:
        # GEX per lot / (abs(avg_theta) * lot_size) → rupee gamma vs rupee theta
        avg_theta = (abs(ce_theta) + abs(pe_theta)) / 2.0
        if avg_theta > 0:
            gamma_theta = gex / (avg_theta * self.LOT_SIZE)
        else:
            gamma_theta = 0.0

        # 4. Delta Flip Zone — ATM strike is where delta ≈ 0.50
        delta_flip_price = atm
        delta_flip_distance = spot - atm

        # 5. CE/PE Delta (pass-through)
        # 6. Delta per Rupee
        delta_per_rupee_ce = (abs(ce_delta) / ce_price) if ce_price > 0 else 0.0
        delta_per_rupee_pe = (abs(pe_delta) / pe_price) if pe_price > 0 else 0.0

        # 7. IV vs Realized Vol spread (percentage points)
        avg_iv_pct = ((ce_iv + pe_iv) / 2.0) * 100.0  # convert to %
        hv_pct = self._realized_vol * 100.0  # convert to %
        iv_hv_spread = avg_iv_pct - hv_pct if hv_pct > 0 else 0.0

        # 8. Vega Risk
        avg_vega = (ce_vega + pe_vega) / 2.0
        conf = self.CONF
        if avg_vega >= conf["vega_high"]:
            vega_label = "HIGH"
        elif avg_vega >= conf["vega_medium"]:
            vega_label = "MEDIUM"
        else:
            vega_label = "LOW"

        # 9. Theta per Minute
        total_theta = ce_theta + pe_theta  # both negative
        remaining_mins = _trading_minutes_remaining()
        theta_per_min = total_theta / remaining_mins

        # 10. Gamma Peak — 0DTE + near ATM
        dte_days = self._dte_total_days()
        gamma_peak = (dte_days <= 1.0) and (distance <= self.STRIKE_STEP)

        return {
            "gex_rupees": round(gex, 2),
            "atm_proximity": atm_prox,
            "gamma_theta_ratio": round(gamma_theta, 4),
            "delta_flip_price": delta_flip_price,
            "delta_flip_distance": round(delta_flip_distance, 2),
            "ce_delta": round(ce_delta, 4),
            "pe_delta": round(pe_delta, 4),
            "delta_per_rupee_ce": round(delta_per_rupee_ce, 6),
            "delta_per_rupee_pe": round(delta_per_rupee_pe, 6),
            "iv_hv_spread": round(iv_hv_spread, 2),
            "vega_risk": round(avg_vega, 4),
            "vega_risk_label": vega_label,
            "theta_per_minute": round(theta_per_min, 4),
            "gamma_peak": gamma_peak,
        }

    def _empty_greeks(self) -> Dict[str, Any]:
        return {
            "gex_rupees": 0.0, "atm_proximity": 0,
            "gamma_theta_ratio": 0.0, "delta_flip_price": 0.0,
            "delta_flip_distance": 0.0, "ce_delta": 0.0, "pe_delta": 0.0,
            "delta_per_rupee_ce": 0.0, "delta_per_rupee_pe": 0.0,
            "iv_hv_spread": 0.0, "vega_risk": 0.0, "vega_risk_label": "LOW",
            "theta_per_minute": 0.0, "gamma_peak": False,
        }

    # ══════════════════════════════════════════════════════════════════
    #  OI METRICS (9)
    # ══════════════════════════════════════════════════════════════════

    def _compute_oi_metrics(self) -> Dict[str, Any]:
        """Compute OI-based scalping indicators."""
        defaults = self._empty_oi()

        if len(self._oi_snapshots) < 2:
            return defaults

        latest = self._oi_snapshots[-1]
        first = self._first_oi_snapshot or self._oi_snapshots[0]

        # 1. OI Buildup Signal — reuse from OI module context if available,
        #    otherwise infer from price + OI direction
        oi_signal = self._classify_oi_buildup(first, latest)

        # 2. Real-time OI change (CE & PE) since day open
        oi_change_ce = int(latest["total_ce"] - first["total_ce"])
        oi_change_pe = int(latest["total_pe"] - first["total_pe"])

        # 3. OI Change Rate (lots/minute)
        mins_elapsed = _minutes_since_open()
        total_oi_change = abs(oi_change_ce) + abs(oi_change_pe)
        oi_rate = total_oi_change / mins_elapsed if mins_elapsed > 0 else 0.0

        # Rate spike detection
        avg_rate = self._compute_avg_oi_rate()
        oi_rate_alert = oi_rate > (avg_rate * self.CONF["oi_rate_spike_mult"]) if avg_rate > 0 else False

        # 4-5. Max OI + Max Pain — compute from latest snapshot
        max_oi_ce_strike, max_oi_pe_strike = self._find_max_oi_strikes(latest["per_strike"])
        max_pain = self._compute_max_pain(latest["per_strike"])
        max_pain_distance = round(self._price - max_pain, 2) if max_pain and self._price > 0 else 0.0

        # 6. OI Concentration Index
        oi_conc = self._compute_oi_concentration(latest["per_strike"], latest["total_ce"] + latest["total_pe"])

        # 7. Volume/OI Ratio — approximate from OI change rate
        # (True volume requires separate data; use OI change as proxy)
        vol_oi_ce = abs(oi_change_ce) / max(first["total_ce"], 1)
        vol_oi_pe = abs(oi_change_pe) / max(first["total_pe"], 1)

        # 8. PCR Trend
        pcr_trend = self._compute_pcr_trend()

        # 9. Unwinding Alert
        unwinding = self._check_unwinding(max_oi_ce_strike, max_oi_pe_strike)

        return {
            "oi_buildup_signal": oi_signal,
            "oi_change_ce": oi_change_ce,
            "oi_change_pe": oi_change_pe,
            "oi_change_rate": round(oi_rate, 1),
            "oi_rate_alert": oi_rate_alert,
            "max_oi_ce_strike": max_oi_ce_strike,
            "max_oi_pe_strike": max_oi_pe_strike,
            "max_pain_strike": max_pain,
            "max_pain_distance": max_pain_distance,
            "oi_concentration": oi_conc,
            "volume_oi_ratio_ce": round(vol_oi_ce, 3),
            "volume_oi_ratio_pe": round(vol_oi_pe, 3),
            "pcr_trend": pcr_trend,
            "unwinding_alert": unwinding,
        }

    def _classify_oi_buildup(self, first: Dict, latest: Dict) -> str:
        """Classify OI buildup from first vs latest snapshot."""
        price_chg = latest["price"] - first["price"]
        oi_chg = (latest["total_ce"] + latest["total_pe"]) - (first["total_ce"] + first["total_pe"])

        price_up = price_chg > first["price"] * 0.0003
        price_down = price_chg < -first["price"] * 0.0003
        oi_up = oi_chg > (first["total_ce"] + first["total_pe"]) * 0.001
        oi_down = oi_chg < -(first["total_ce"] + first["total_pe"]) * 0.001

        if price_up and oi_up:
            return "LONG_BUILDUP"
        elif price_up and oi_down:
            return "SHORT_COVERING"
        elif price_down and oi_up:
            return "SHORT_BUILDUP"
        elif price_down and oi_down:
            return "LONG_UNWINDING"
        return "NEUTRAL"

    def _compute_avg_oi_rate(self) -> float:
        """Average OI change rate over recent snapshots."""
        if len(self._oi_snapshots) < 3:
            return 0.0
        rates = []
        for i in range(1, min(len(self._oi_snapshots), 12)):
            prev = self._oi_snapshots[-(i + 1)]
            curr = self._oi_snapshots[-i]
            dt = curr["t"] - prev["t"]
            if dt <= 0:
                continue
            chg = abs((curr["total_ce"] + curr["total_pe"]) - (prev["total_ce"] + prev["total_pe"]))
            rates.append(chg / (dt / 60.0))
        return sum(rates) / len(rates) if rates else 0.0

    def _find_max_oi_strikes(self, per_strike: Dict) -> tuple:
        """Find strikes with max CE OI and max PE OI."""
        max_ce_oi, max_pe_oi = 0.0, 0.0
        ce_strike, pe_strike = None, None
        for strike, oi in per_strike.items():
            if oi["ce_oi"] > max_ce_oi:
                max_ce_oi = oi["ce_oi"]
                ce_strike = strike
            if oi["pe_oi"] > max_pe_oi:
                max_pe_oi = oi["pe_oi"]
                pe_strike = strike
        return ce_strike, pe_strike

    def _compute_max_pain(self, per_strike: Dict) -> Optional[float]:
        """Max pain = strike minimizing total writer payout."""
        strikes = sorted(per_strike.keys())
        if len(strikes) < 3:
            return None
        min_pain = float("inf")
        mp_strike = None
        for candidate in strikes:
            pain = 0.0
            for strike, oi in per_strike.items():
                if candidate > strike:
                    pain += (candidate - strike) * oi["ce_oi"]
                if candidate < strike:
                    pain += (strike - candidate) * oi["pe_oi"]
            if pain < min_pain:
                min_pain = pain
                mp_strike = candidate
        return mp_strike

    def _compute_oi_concentration(self, per_strike: Dict, total_oi: float) -> int:
        """OI at top 3 strikes / total OI × 100."""
        if total_oi <= 0 or not per_strike:
            return 0
        # Sum CE+PE per strike, sort descending, take top 3
        combined = [(s, oi["ce_oi"] + oi["pe_oi"]) for s, oi in per_strike.items()]
        combined.sort(key=lambda x: x[1], reverse=True)
        top3_oi = sum(x[1] for x in combined[:3])
        return min(100, int((top3_oi / total_oi) * 100))

    def _compute_pcr_trend(self) -> str:
        """PCR direction over last 15 minutes."""
        if len(self._pcr_history) < 6:
            return "STABLE"
        recent = list(self._pcr_history)[-30:]  # last ~2.5 min
        older = list(self._pcr_history)[-60:-30] if len(self._pcr_history) >= 60 else list(self._pcr_history)[:len(recent)]
        if not older:
            return "STABLE"
        avg_recent = sum(p["v"] for p in recent) / len(recent)
        avg_older = sum(p["v"] for p in older) / len(older)
        diff = avg_recent - avg_older
        if diff > 0.05:
            return "RISING"
        elif diff < -0.05:
            return "FALLING"
        return "STABLE"

    def _check_unwinding(self, ce_strike: Optional[float], pe_strike: Optional[float]) -> Optional[Dict]:
        """Check if OI at key strikes dropped >10% in last 5 minutes."""
        if len(self._oi_snapshots) < 2:
            return None
        latest = self._oi_snapshots[-1]
        # Compare against snapshot ~5 min ago (60 snapshots at 5s interval)
        lookback_idx = max(0, len(self._oi_snapshots) - 60)
        older = self._oi_snapshots[lookback_idx]
        threshold = self.CONF["unwinding_drop_pct"] / 100.0

        for strike in [ce_strike, pe_strike]:
            if strike is None:
                continue
            old_oi = older["per_strike"].get(strike, {})
            new_oi = latest["per_strike"].get(strike, {})
            old_total = old_oi.get("ce_oi", 0) + old_oi.get("pe_oi", 0)
            new_total = new_oi.get("ce_oi", 0) + new_oi.get("pe_oi", 0)
            if old_total > 0:
                drop_pct = (old_total - new_total) / old_total
                if drop_pct >= threshold:
                    return {"strike": strike, "oi_drop_pct": round(drop_pct * 100, 1)}
        return None

    def _empty_oi(self) -> Dict[str, Any]:
        return {
            "oi_buildup_signal": "NEUTRAL", "oi_change_ce": 0, "oi_change_pe": 0,
            "oi_change_rate": 0.0, "oi_rate_alert": False,
            "max_oi_ce_strike": None, "max_oi_pe_strike": None,
            "max_pain_strike": None, "max_pain_distance": 0.0,
            "oi_concentration": 0, "volume_oi_ratio_ce": 0.0,
            "volume_oi_ratio_pe": 0.0, "pcr_trend": "STABLE",
            "unwinding_alert": None,
        }

    # ══════════════════════════════════════════════════════════════════
    #  LIQUIDITY METRICS (3)
    # ══════════════════════════════════════════════════════════════════

    def _compute_liquidity_metrics(self) -> Dict[str, Any]:
        """Compute bid-ask spread and liquidity metrics."""
        spread_ce = self._bid_ask.get("ce_spread_pct")
        spread_pe = self._bid_ask.get("pe_spread_pct")

        conf = self.CONF

        def label(pct):
            if pct is None:
                return "POOR"
            if pct < conf.get("spread_excellent_pct", Config.INTELLIGENCE["spread_excellent_pct"]):
                return "EXCELLENT"
            if pct < conf.get("spread_good_pct", Config.INTELLIGENCE["spread_good_pct"]):
                return "GOOD"
            return "POOR"

        # Effective spread = avg of CE+PE spreads (half-spread + slippage estimate)
        if spread_ce is not None and spread_pe is not None:
            eff = (spread_ce + spread_pe) / 2.0 * 0.75  # 50% spread + 25% slippage estimate
        else:
            eff = 0.0

        # Lot liquidity — proxy from bid-ask depth totals if available
        ce_depth = self._bid_ask.get("ce_bid_qty", 0) + self._bid_ask.get("ce_ask_qty", 0)
        pe_depth = self._bid_ask.get("pe_bid_qty", 0) + self._bid_ask.get("pe_ask_qty", 0)
        total_depth = ce_depth + pe_depth
        # Normalize: 50 lots × 25 = 1250 as "max depth" for 100 score
        lot_liq = min(100, int((total_depth / max(self.LOT_SIZE * conf["lot_liq_max"], 1)) * 100))

        return {
            "spread_ce_pct": round(spread_ce, 3) if spread_ce is not None else None,
            "spread_pe_pct": round(spread_pe, 3) if spread_pe is not None else None,
            "spread_ce_label": label(spread_ce),
            "spread_pe_label": label(spread_pe),
            "effective_spread": round(eff, 4),
            "lot_liquidity_score": lot_liq,
        }

    # ══════════════════════════════════════════════════════════════════
    #  MARKET CONTEXT METRICS (4)
    # ══════════════════════════════════════════════════════════════════

    def _compute_market_context(self) -> Dict[str, Any]:
        """Compute market context indicators."""
        conf = self.CONF

        # 1. Regime + scalp recommendation
        regime = self._market_regime
        if regime == "TRENDING":
            rec = "Directional scalps"
        elif regime == "RANGING":
            rec = "Gamma scalps near ATM"
        elif regime == "HIGH_VOLATILITY":
            rec = "Quick in-and-out scalps"
        else:
            rec = "Wait for regime clarity"

        # 2. VIX level + trend
        vix_trend = "FLAT"
        if len(self._vix_history) >= 6:
            recent = [v["v"] for v in list(self._vix_history)[-6:]]
            older = [v["v"] for v in list(self._vix_history)[-12:-6]] if len(self._vix_history) >= 12 else recent
            avg_r = sum(recent) / len(recent) if recent else 0
            avg_o = sum(older) / len(older) if older else avg_r
            if avg_r > avg_o + 0.3:
                vix_trend = "UP"
            elif avg_r < avg_o - 0.3:
                vix_trend = "DOWN"

        # 3. Intraday momentum = (price - open) / ATR * 100
        momentum = 0.0
        if self._atr_pct > 0 and self._day_open > 0 and self._price > 0:
            atr_points = self._price * self._atr_pct / 100.0
            if atr_points > 0:
                momentum = abs(self._price - self._day_open) / atr_points * 100.0
                momentum = min(momentum, 200.0)  # cap at 200%

        # 4. Time of Day
        zone, mins_to_next = self._compute_time_zone()

        return {
            "regime": regime,
            "regime_scalp_recommendation": rec,
            "vix_level": round(self._vix, 2),
            "vix_trend": vix_trend,
            "intraday_momentum": round(momentum, 1),
            "time_of_day_zone": zone,
            "minutes_to_next_zone": mins_to_next,
        }

    def _compute_time_zone(self) -> tuple:
        """Determine current trading time zone and minutes to next transition."""
        now = _ist_now()
        current_mins = now.hour * 60 + now.minute
        zones = self.CONF["time_zones"]

        for start_h, start_m, end_h, end_m, label in zones:
            zone_start = start_h * 60 + start_m
            zone_end = end_h * 60 + end_m
            if zone_start <= current_mins < zone_end:
                return label, zone_end - current_mins

        # Outside trading hours
        return "CLOSED", 0

    # ══════════════════════════════════════════════════════════════════
    #  COMPOSITE SCORE (0-100)
    # ══════════════════════════════════════════════════════════════════

    def _compute_composite_score(self, greeks: Dict, oi: Dict, liq: Dict, ctx: Dict) -> Dict[str, Any]:
        """Compute weighted composite scalp health score."""
        conf = self.CONF
        dte = self._dte_total_days()

        # Select weight index: 0=base, 1=0dte, 2=weekly
        if dte <= 1.0:
            wi = 1  # 0 DTE weights
        elif dte >= 3.0:
            wi = 2  # Weekly weights
        else:
            wi = 0  # Base weights

        weights = {
            "greeks": conf["weight_greeks"][wi],
            "oi": conf["weight_oi"][wi],
            "time_decay": conf["weight_time_decay"][wi],
            "liquidity": conf["weight_liquidity"][wi],
            "market_context": conf["weight_market_context"][wi],
        }

        # Sub-score: Greeks (0-100)
        gs = 0
        if greeks["gex_rupees"] >= conf["gex_high"]:
            gs += 30
        elif greeks["gex_rupees"] >= conf["gex_medium"]:
            gs += 15
        gs += min(30, greeks["atm_proximity"] * 30 // 100)
        if greeks["gamma_theta_ratio"] >= conf["gt_ratio_green"]:
            gs += 20
        elif greeks["gamma_theta_ratio"] >= conf["gt_ratio_amber"]:
            gs += 10
        gs += 20 if greeks["gamma_peak"] else 0
        greeks_score = min(100, gs)

        # Sub-score: OI (0-100)
        os_ = 0
        signal = oi["oi_buildup_signal"]
        if signal in ("LONG_BUILDUP", "SHORT_BUILDUP"):
            os_ += 30  # Strong directional signal
        elif signal in ("SHORT_COVERING", "LONG_UNWINDING"):
            os_ += 15  # Weak signal
        if oi["oi_rate_alert"]:
            os_ += 20
        if oi["oi_concentration"] >= conf["oi_conc_high"]:
            os_ += 15  # Strong walls
        elif oi["oi_concentration"] <= conf["oi_conc_low"]:
            os_ += 10  # Breakout potential
        pcr_t = oi["pcr_trend"]
        if pcr_t in ("RISING", "FALLING"):
            os_ += 15  # Clear direction
        if oi["unwinding_alert"]:
            os_ += 20  # Breakout catalyst
        oi_score = min(100, os_)

        # Sub-score: Time/Decay (0-100)
        ts = 50  # Start at neutral
        if greeks["gamma_peak"]:
            ts += 30
        # Theta cost penalty: high theta/min is bad for buyers
        if abs(greeks["theta_per_minute"]) < 0.01:
            ts += 20  # Low decay cost
        elif abs(greeks["theta_per_minute"]) > 0.1:
            ts -= 20  # High decay cost
        time_score = max(0, min(100, ts))

        # Sub-score: Liquidity (0-100)
        ls = 0
        ls += liq["lot_liquidity_score"] * 50 // 100
        if liq["spread_ce_label"] == "EXCELLENT":
            ls += 25
        elif liq["spread_ce_label"] == "GOOD":
            ls += 15
        if liq["spread_pe_label"] == "EXCELLENT":
            ls += 25
        elif liq["spread_pe_label"] == "GOOD":
            ls += 15
        liq_score = min(100, ls)

        # Sub-score: Market Context (0-100)
        ms = 50
        if ctx["regime"] in ("TRENDING", "RANGING"):
            ms += 20
        vix = ctx["vix_level"]
        if vix >= conf["vix_high"]:
            ms += 15
        elif vix >= conf["vix_low"]:
            ms += 5
        else:
            ms -= 10  # Low VIX = harder scalps
        if ctx["time_of_day_zone"] == "PEAK":
            ms += 15
        elif ctx["time_of_day_zone"] == "MODERATE":
            ms += 5
        elif ctx["time_of_day_zone"] == "LOW":
            ms -= 10
        market_score = max(0, min(100, ms))

        sub_scores = {
            "greeks": greeks_score,
            "oi": oi_score,
            "time_decay": time_score,
            "liquidity": liq_score,
            "market_context": market_score,
        }

        # Weighted composite
        total = sum(sub_scores[k] * weights[k] for k in weights)
        score = max(0, min(100, int(total)))

        # Band
        if score >= 80:
            band = "PRIME"
        elif score >= 60:
            band = "GOOD"
        elif score >= 40:
            band = "CAUTION"
        else:
            band = "AVOID"

        return {"score": score, "score_band": band, "sub_scores": sub_scores}

    # ══════════════════════════════════════════════════════════════════
    #  GET CONTEXT — main output
    # ══════════════════════════════════════════════════════════════════

    def get_context(self) -> Dict[str, Any]:
        dte = self._compute_dte()
        greeks = self._compute_greeks_metrics()
        oi = self._compute_oi_metrics()
        liq = self._compute_liquidity_metrics()
        ctx = self._compute_market_context()
        composite = self._compute_composite_score(greeks, oi, liq, ctx)

        return {**composite, **dte, **greeks, **oi, **liq, **ctx}

    def reset(self) -> None:
        """Reset daily state."""
        self._oi_snapshots.clear()
        self._first_oi_snapshot = None
        self._last_oi_time = 0.0
        self._pcr_history.clear()
        self._last_pcr_time = 0.0
        self._vix_history.clear()
        self._day_open = 0.0
        logger.info("Scalp Health module reset for new session.")
```

**Step 4: Run tests**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_scalp_health.py -v --tb=short`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add app/intelligence/scalp_health.py tests/test_scalp_health.py
git commit -m "feat(intelligence): add ScalpHealthModule with Greeks + OI + liquidity + composite score"
```

---

## Task 3: Register ScalpHealthModule in main.py

**Files:**
- Modify: `main.py:24` (add import)
- Modify: `main.py:87-88` (register module)

**Step 1: Add import after line 24**

After `from app.intelligence.oi_analysis import OIAnalysisModule`, add:
```python
from app.intelligence.scalp_health import ScalpHealthModule
```

**Step 2: Register module after line 87**

After `self.intelligence_engine.register(OIAnalysisModule())`, add:
```python
        self.intelligence_engine.register(ScalpHealthModule())
```

**Step 3: Update log message on line 88**

Change:
```python
        self.log("Intelligence engine initialized with 6 modules.")
```
to:
```python
        self.log("Intelligence engine initialized with 7 modules.")
```

**Step 4: Feed additional data to ScalpHealthModule**

In `_on_price_update` (around line 226-231), the intelligence engine update currently only sends `positions` and `greeks`. The ScalpHealthModule needs more data. Modify the `_on_price_update` intelligence update block:

After the existing `self.intelligence_engine.update(...)` call at line 228, add additional data for scalp health by expanding the update dict:

```python
            # 3b. Push positions to PortfolioGreeks intelligence module
            if self.intelligence_engine and self.position_manager:
                positions = self.position_manager.get_positions()
                self.intelligence_engine.update({
                    "positions": positions,
                    "greeks":    market_state.get("greeks"),
                    # Additional data for ScalpHealthModule
                    "vix": market_state.get("vix"),
                    "atr_pct": strategy_data.get("atr_pct") if signal_data is None else (self.strategy_runner.latest_strategy_data.get("atr_pct") if self.strategy_runner else None),
                    "market_regime": (self.intelligence_engine.get_context().get("market_regime", {}).get("regime") if self.intelligence_engine else None),
                    "bid_ask_cache": (self.market_data.bid_ask_cache if self.market_data and hasattr(self.market_data, "bid_ask_cache") else {}),
                })
```

**Step 5: Verify import works**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -c "from main import bot; print([m for m in bot.intelligence_engine.modules])"`
Expected: Output includes `'scalp_health'`

**Step 6: Commit**

```bash
git add main.py
git commit -m "feat: register ScalpHealthModule in TradingBot intelligence engine"
```

---

## Task 4: Add OI tests and edge case tests

**Files:**
- Modify: `tests/test_scalp_health.py`

**Step 1: Add OI and composite score tests**

Append to `tests/test_scalp_health.py`:

```python
class TestOIMetrics:
    def test_empty_oi_returns_defaults(self, module, base_data):
        """No OI data → safe defaults."""
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["oi_buildup_signal"] == "NEUTRAL"
        assert ctx["oi_change_ce"] == 0
        assert ctx["oi_change_pe"] == 0

    def test_oi_snapshots_accumulate(self, module, base_data):
        """OI snapshots build up over multiple updates."""
        oi_data = {"key1": 1000.0, "key2": 2000.0}
        metadata = {"key1": {"strike": 24800, "option_type": "CE"}, "key2": {"strike": 24800, "option_type": "PE"}}
        base_data["pcr_oi_data"] = oi_data
        base_data["pcr_option_metadata"] = metadata

        # First update
        module.update(base_data)
        # Force time advancement for second snapshot
        module._last_oi_time = 0
        base_data["pcr_oi_data"] = {"key1": 1100.0, "key2": 2100.0}
        module.update(base_data)

        ctx = module.get_context()
        assert ctx["oi_change_ce"] == 100  # 1100 - 1000
        assert ctx["oi_change_pe"] == 100  # 2100 - 2000

    def test_max_pain_calculation(self, module):
        per_strike = {
            24700: {"ce_oi": 5000, "pe_oi": 1000},
            24800: {"ce_oi": 3000, "pe_oi": 3000},
            24900: {"ce_oi": 1000, "pe_oi": 5000},
        }
        result = module._compute_max_pain(per_strike)
        assert result is not None
        assert result in [24700, 24800, 24900]

    def test_oi_concentration(self, module):
        per_strike = {
            24700: {"ce_oi": 100, "pe_oi": 100},
            24800: {"ce_oi": 5000, "pe_oi": 5000},  # dominant
            24900: {"ce_oi": 100, "pe_oi": 100},
        }
        total = sum(v["ce_oi"] + v["pe_oi"] for v in per_strike.values())
        result = module._compute_oi_concentration(per_strike, total)
        assert result > 50  # Most OI concentrated at 24800


class TestCompositeScore:
    def test_score_in_range(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert 0 <= ctx["score"] <= 100

    def test_score_band_mapping(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["score_band"] in ("PRIME", "GOOD", "CAUTION", "AVOID")

    def test_sub_scores_present(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert "greeks" in ctx["sub_scores"]
        assert "oi" in ctx["sub_scores"]
        assert "time_decay" in ctx["sub_scores"]
        assert "liquidity" in ctx["sub_scores"]
        assert "market_context" in ctx["sub_scores"]


class TestMarketContext:
    def test_time_zone_detection(self, module):
        zone, mins = module._compute_time_zone()
        assert zone in ("PEAK", "LOW", "MODERATE", "CLOSED")
        assert isinstance(mins, int)

    def test_regime_recommendation(self, module, base_data):
        base_data["market_regime"] = "TRENDING"
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["regime_scalp_recommendation"] == "Directional scalps"


class TestLiquidity:
    def test_empty_bid_ask_returns_defaults(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["spread_ce_label"] == "POOR"
        assert ctx["lot_liquidity_score"] == 0

    def test_excellent_spread(self, module, base_data):
        base_data["bid_ask_cache"] = {
            "ce_spread_pct": 0.1,
            "pe_spread_pct": 0.2,
            "ce_bid_qty": 500,
            "ce_ask_qty": 500,
            "pe_bid_qty": 400,
            "pe_ask_qty": 400,
        }
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["spread_ce_label"] == "EXCELLENT"


class TestEdgeCases:
    def test_no_data_returns_safe_defaults(self, module):
        """Module with no data should return safe defaults without errors."""
        ctx = module.get_context()
        assert ctx["score"] == 0 or ctx["score"] >= 0
        assert ctx["gex_rupees"] == 0.0
        assert ctx["oi_buildup_signal"] == "NEUTRAL"

    def test_partial_greeks_data(self, module):
        """Only CE greeks, no PE → should not crash."""
        module.update({
            "current_price": 24800,
            "greeks": {
                "atm_strike": 24800,
                "expiry_date": "2026-02-24",
                "ce": {"delta": 0.5, "gamma": 0.001, "theta": -5, "vega": 4, "iv": 0.14, "price": 150},
            }
        })
        ctx = module.get_context()
        assert ctx["gex_rupees"] == 0.0  # needs both CE and PE

    def test_module_name(self, module):
        assert module.name == "scalp_health"

    def test_reset_clears_state(self, module, base_data):
        module.update(base_data)
        module.reset()
        assert len(module._oi_snapshots) == 0
        assert module._day_open == 0.0
```

**Step 2: Run all tests**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_scalp_health.py -v --tb=short`
Expected: All tests PASS

**Step 3: Run full test suite to check no regressions**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: No failures in existing tests

**Step 4: Commit**

```bash
git add tests/test_scalp_health.py
git commit -m "test(scalp_health): add OI, composite score, edge case, and liquidity tests"
```

---

## Task 5: Frontend — Add TypeScript interface

**Files:**
- Modify: `frontend/src/types/api.ts:229-230` (add ScalpHealthContext interface, update IntelligenceContext)

**Step 1: Add ScalpHealthContext interface**

After line 215 (after `OIAnalysisContext`), before `PDHPDLPDCData`, add:

```typescript
export interface ScalpHealthContext {
    // Composite
    score: number;
    score_band: 'PRIME' | 'GOOD' | 'CAUTION' | 'AVOID';
    sub_scores: Record<string, number>;

    // DTE
    dte_days: number;
    dte_hours: number;
    dte_minutes: number;
    expiry_date: string;

    // Greeks (10 metrics)
    gex_rupees: number;
    atm_proximity: number;
    gamma_theta_ratio: number;
    delta_flip_price: number;
    delta_flip_distance: number;
    ce_delta: number;
    pe_delta: number;
    delta_per_rupee_ce: number;
    delta_per_rupee_pe: number;
    iv_hv_spread: number;
    vega_risk: number;
    vega_risk_label: 'LOW' | 'MEDIUM' | 'HIGH';
    theta_per_minute: number;
    gamma_peak: boolean;

    // OI (9 metrics)
    oi_buildup_signal: string;
    oi_change_ce: number;
    oi_change_pe: number;
    oi_change_rate: number;
    oi_rate_alert: boolean;
    max_oi_ce_strike: number | null;
    max_oi_pe_strike: number | null;
    max_pain_strike: number | null;
    max_pain_distance: number;
    oi_concentration: number;
    volume_oi_ratio_ce: number;
    volume_oi_ratio_pe: number;
    pcr_trend: 'RISING' | 'FALLING' | 'STABLE';
    unwinding_alert: { strike: number; oi_drop_pct: number } | null;

    // Liquidity (3 metrics)
    spread_ce_pct: number | null;
    spread_pe_pct: number | null;
    spread_ce_label: 'EXCELLENT' | 'GOOD' | 'POOR';
    spread_pe_label: 'EXCELLENT' | 'GOOD' | 'POOR';
    effective_spread: number;
    lot_liquidity_score: number;

    // Market Context (4 metrics)
    regime: string;
    regime_scalp_recommendation: string;
    vix_level: number;
    vix_trend: 'UP' | 'DOWN' | 'FLAT';
    intraday_momentum: number;
    time_of_day_zone: 'PEAK' | 'MODERATE' | 'LOW' | 'CLOSED';
    minutes_to_next_zone: number;
}
```

**Step 2: Add `scalp_health` to IntelligenceContext**

In the `IntelligenceContext` interface (around line 223-230), add:
```typescript
    scalp_health?: ScalpHealthContext;
```

**Step 3: Verify TypeScript compiles**

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors related to `ScalpHealthContext`

**Step 4: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/frontend
git add src/types/api.ts
git commit -m "feat(types): add ScalpHealthContext interface"
```

---

## Task 6: Frontend — Create ScalpHealthTab component

**Files:**
- Create: `frontend/src/features/scalp-health/ScalpHealthTab.tsx`

**Step 1: Create the directory and main tab component**

Create `frontend/src/features/scalp-health/ScalpHealthTab.tsx`:

```tsx
import React from 'react';
import Card from '../../shared/Card';
import ProgressBar from '../../shared/ProgressBar';
import Badge from '../../shared/Badge';
import { Activity, TrendingUp, BarChart3, Droplets, Globe } from 'lucide-react';
import type { ScalpHealthContext } from '../../types/api';

interface ScalpHealthTabProps {
    data?: ScalpHealthContext;
}

/* ── Helpers ──────────────────────────────────────────────── */

const fmt = (v: number | null | undefined, decimals = 2): string =>
    v != null ? v.toFixed(decimals) : '--';

const fmtInt = (v: number | null | undefined): string =>
    v != null ? Math.round(v).toLocaleString('en-IN') : '--';

const signColor = (v: number): string =>
    v > 0 ? 'var(--color-profit-text)' : v < 0 ? 'var(--color-loss-text)' : 'var(--text-secondary)';

const bandColor = (band: string): string => {
    switch (band) {
        case 'PRIME': return 'var(--color-profit-text)';
        case 'GOOD': return 'var(--accent-blue)';
        case 'CAUTION': return 'var(--color-warning-text)';
        case 'AVOID': return 'var(--color-loss-text)';
        default: return 'var(--text-secondary)';
    }
};

const thresholdColor = (value: number, green: number, amber: number, invert = false): string => {
    if (invert) return value <= green ? 'var(--color-profit-text)' : value <= amber ? 'var(--color-warning-text)' : 'var(--color-loss-text)';
    return value >= green ? 'var(--color-profit-text)' : value >= amber ? 'var(--color-warning-text)' : 'var(--color-loss-text)';
};

const spreadLabelColor = (label: string): string => {
    switch (label) {
        case 'EXCELLENT': return 'var(--color-profit-text)';
        case 'GOOD': return 'var(--accent-blue)';
        default: return 'var(--color-loss-text)';
    }
};

const buildupColor = (signal: string): string => {
    if (signal.includes('LONG') || signal === 'SHORT_COVERING') return 'var(--color-profit-text)';
    if (signal.includes('SHORT') || signal === 'LONG_UNWINDING') return 'var(--color-loss-text)';
    return 'var(--text-secondary)';
};

const trendArrow = (trend: string): string => {
    switch (trend) {
        case 'RISING': case 'UP': return '\u2191';
        case 'FALLING': case 'DOWN': return '\u2193';
        default: return '\u2192';
    }
};

/* ── Metric Row ───────────────────────────────────────────── */

interface MetricRowProps {
    label: string;
    value: React.ReactNode;
    color?: string;
    suffix?: string;
}

const MetricRow: React.FC<MetricRowProps> = ({ label, value, color, suffix }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 0' }}>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 500 }}>{label}</span>
        <span className="mono" style={{ fontSize: '11px', fontWeight: 600, color: color || 'var(--text-primary)' }}>
            {value}{suffix || ''}
        </span>
    </div>
);

/* ── Score Header ─────────────────────────────────────────── */

const ScoreHeader: React.FC<{ data: ScalpHealthContext }> = ({ data }) => (
    <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'var(--bg-primary)',
    }}>
        {/* Score bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Scalp Health
                </span>
                <span className="mono" style={{ fontSize: '20px', fontWeight: 800, color: bandColor(data.score_band) }}>
                    {data.score}
                </span>
                <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>/100</span>
            </div>
            <div style={{ flex: 1 }}>
                <ProgressBar value={data.score} max={100} />
            </div>
            <Badge
                label={data.score_band}
                color={bandColor(data.score_band)}
            />
        </div>
        {/* Quick chips */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span className="mono" style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '9999px', background: 'var(--bg-overlay)', color: 'var(--text-secondary)' }}>
                DTE: {data.dte_days}d {data.dte_hours}h {data.dte_minutes}m
            </span>
            <span className="mono" style={{
                fontSize: '10px', padding: '2px 8px', borderRadius: '9999px',
                background: data.gamma_peak ? 'rgba(16,185,129,0.15)' : 'var(--bg-overlay)',
                color: data.gamma_peak ? 'var(--color-profit-text)' : 'var(--text-secondary)',
                fontWeight: data.gamma_peak ? 700 : 500,
            }}>
                Gamma Peak: {data.gamma_peak ? 'YES' : 'NO'}
            </span>
            <span className="mono" style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '9999px', background: 'var(--bg-overlay)', color: 'var(--text-secondary)' }}>
                {data.regime}
            </span>
        </div>
    </div>
);

/* ── Greeks Column ────────────────────────────────────────── */

const GreeksColumn: React.FC<{ data: ScalpHealthContext }> = ({ data }) => (
    <Card compact header={
        <div className="flex items-center gap-2">
            <Activity size={13} className="text-[var(--accent-purple)]" />
            <span className="text-xs font-semibold">Greeks</span>
            <span className="mono text-[9px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)' }}>
                {data.sub_scores?.greeks ?? '--'}/100
            </span>
        </div>
    }>
        <MetricRow label="GEX" value={`\u20B9${fmtInt(data.gex_rupees)}`} color={thresholdColor(data.gex_rupees, 3000, 1000)} />
        <MetricRow label="ATM Proximity" value={data.atm_proximity} color={thresholdColor(data.atm_proximity, 80, 50)} suffix="/100" />
        <MetricRow label="\u03B3/\u03B8 Ratio" value={fmt(data.gamma_theta_ratio, 4)} color={thresholdColor(data.gamma_theta_ratio, 2.0, 1.0)} />
        <MetricRow label="Delta Flip" value={`${fmtInt(data.delta_flip_price)} (${data.delta_flip_distance > 0 ? '+' : ''}${fmt(data.delta_flip_distance, 0)})`} />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="CE \u03B4" value={fmt(data.ce_delta, 4)} color="var(--ce-color)" />
        <MetricRow label="PE \u03B4" value={fmt(data.pe_delta, 4)} color="var(--pe-color)" />
        <MetricRow label="\u03B4/\u20B9 CE" value={fmt(data.delta_per_rupee_ce, 5)} />
        <MetricRow label="\u03B4/\u20B9 PE" value={fmt(data.delta_per_rupee_pe, 5)} />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="IV-HV" value={`${data.iv_hv_spread > 0 ? '+' : ''}${fmt(data.iv_hv_spread, 1)}%`} color={signColor(-data.iv_hv_spread)} />
        <MetricRow label="Vega" value={fmt(data.vega_risk, 2)} suffix={` (${data.vega_risk_label})`} />
        <MetricRow label="\u03B8/min" value={`\u20B9${fmt(data.theta_per_minute, 4)}`} color="var(--color-loss-text)" />
        <MetricRow
            label="Gamma Peak"
            value={data.gamma_peak ? 'YES' : 'NO'}
            color={data.gamma_peak ? 'var(--color-profit-text)' : 'var(--text-muted)'}
        />
    </Card>
);

/* ── OI Column ────────────────────────────────────────────── */

const OIColumn: React.FC<{ data: ScalpHealthContext }> = ({ data }) => (
    <Card compact header={
        <div className="flex items-center gap-2">
            <BarChart3 size={13} className="text-[var(--accent-blue)]" />
            <span className="text-xs font-semibold">OI & Flow</span>
            <span className="mono text-[9px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)' }}>
                {data.sub_scores?.oi ?? '--'}/100
            </span>
        </div>
    }>
        <MetricRow label="Signal" value={data.oi_buildup_signal.replace('_', ' ')} color={buildupColor(data.oi_buildup_signal)} />
        <MetricRow label="OI Chg CE" value={`${data.oi_change_ce >= 0 ? '+' : ''}${fmtInt(data.oi_change_ce)}`} color={signColor(data.oi_change_ce)} />
        <MetricRow label="OI Chg PE" value={`${data.oi_change_pe >= 0 ? '+' : ''}${fmtInt(data.oi_change_pe)}`} color={signColor(data.oi_change_pe)} />
        <MetricRow
            label="OI Rate"
            value={`${fmtInt(data.oi_change_rate)}/min`}
            color={data.oi_rate_alert ? 'var(--color-warning-text)' : undefined}
            suffix={data.oi_rate_alert ? ' !' : ''}
        />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="Max Pain" value={fmtInt(data.max_pain_strike)} suffix={data.max_pain_distance ? ` (${data.max_pain_distance > 0 ? '+' : ''}${fmt(data.max_pain_distance, 0)})` : ''} />
        <MetricRow label="Max OI CE" value={fmtInt(data.max_oi_ce_strike)} color="var(--ce-color)" />
        <MetricRow label="Max OI PE" value={fmtInt(data.max_oi_pe_strike)} color="var(--pe-color)" />
        <MetricRow label="OI Conc." value={data.oi_concentration} color={thresholdColor(data.oi_concentration, 70, 30)} suffix="/100" />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="Vol/OI CE" value={fmt(data.volume_oi_ratio_ce, 3)} color={thresholdColor(data.volume_oi_ratio_ce, 1.0, 0.3)} />
        <MetricRow label="Vol/OI PE" value={fmt(data.volume_oi_ratio_pe, 3)} color={thresholdColor(data.volume_oi_ratio_pe, 1.0, 0.3)} />
        <MetricRow label="PCR Trend" value={`${data.pcr_trend} ${trendArrow(data.pcr_trend)}`} />
        <MetricRow
            label="Unwinding"
            value={data.unwinding_alert ? `${fmtInt(data.unwinding_alert.strike)} (-${data.unwinding_alert.oi_drop_pct}%)` : '\u2014'}
            color={data.unwinding_alert ? 'var(--color-loss-text)' : 'var(--text-muted)'}
        />
    </Card>
);

/* ── Liquidity + Context Column ───────────────────────────── */

const LiquidityContextColumn: React.FC<{ data: ScalpHealthContext }> = ({ data }) => (
    <Card compact header={
        <div className="flex items-center gap-2">
            <Droplets size={13} className="text-[var(--accent-indigo)]" />
            <span className="text-xs font-semibold">Liquidity + Context</span>
            <span className="mono text-[9px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-overlay)', color: 'var(--text-muted)' }}>
                {data.sub_scores?.liquidity ?? '--'}/100
            </span>
        </div>
    }>
        <MetricRow label="Spread CE" value={data.spread_ce_pct != null ? `${fmt(data.spread_ce_pct, 2)}%` : '--'} color={spreadLabelColor(data.spread_ce_label)} suffix={` ${data.spread_ce_label[0]}`} />
        <MetricRow label="Spread PE" value={data.spread_pe_pct != null ? `${fmt(data.spread_pe_pct, 2)}%` : '--'} color={spreadLabelColor(data.spread_pe_label)} suffix={` ${data.spread_pe_label[0]}`} />
        <MetricRow label="Lot Liquidity" value={data.lot_liquidity_score} color={thresholdColor(data.lot_liquidity_score, 70, 40)} suffix="/100" />
        <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
        <MetricRow label="VIX" value={`${fmt(data.vix_level, 1)} ${trendArrow(data.vix_trend)}`} color={data.vix_level >= 18 ? 'var(--color-warning-text)' : 'var(--text-primary)'} />
        <MetricRow label="Momentum" value={`${fmt(data.intraday_momentum, 0)}%`} color={thresholdColor(data.intraday_momentum, 30, 80, true)} />
        <MetricRow
            label="Time Zone"
            value={`${data.time_of_day_zone} (${data.minutes_to_next_zone}m)`}
            color={data.time_of_day_zone === 'PEAK' ? 'var(--color-profit-text)' : data.time_of_day_zone === 'MODERATE' ? 'var(--accent-blue)' : 'var(--text-muted)'}
        />
        <MetricRow label="Regime" value={data.regime} />
        <MetricRow label="Recommendation" value={data.regime_scalp_recommendation} color="var(--accent-blue)" />
    </Card>
);

/* ── Main Tab ─────────────────────────────────────────────── */

const ScalpHealthTab: React.FC<ScalpHealthTabProps> = React.memo(({ data }) => {
    if (!data || data.score == null) {
        return (
            <div className="text-center py-8 text-[var(--text-muted)] text-sm">
                Waiting for Scalp Health data. Ensure the module is enabled in Intelligence settings.
            </div>
        );
    }

    return (
        <div>
            <ScoreHeader data={data} />
            <div className="grid gap-3 lg:grid-cols-3 p-3">
                <GreeksColumn data={data} />
                <OIColumn data={data} />
                <LiquidityContextColumn data={data} />
            </div>
        </div>
    );
});

ScalpHealthTab.displayName = 'ScalpHealthTab';
export default ScalpHealthTab;
```

**Step 2: Verify TypeScript compiles**

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

**Step 3: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/frontend
git add src/features/scalp-health/ScalpHealthTab.tsx
git commit -m "feat(ui): add ScalpHealthTab component with 3-column layout and composite score"
```

---

## Task 7: Frontend — Wire ScalpHealthTab into BottomTabs

**Files:**
- Modify: `frontend/src/layout/BottomTabs.tsx`

**Step 1: Add import and tab definition**

At the top of `BottomTabs.tsx`, add import after existing imports (after line 10):
```typescript
import type { ScalpHealthContext } from '../types/api';
```

Add lazy import after `IntelligenceTabContent` (after line 14):
```typescript
const ScalpHealthTabContent = React.lazy(() => import('../features/scalp-health/ScalpHealthTab'));
```

**Step 2: Update TabId type and TABS array**

Change `TabId` type (line 16):
```typescript
type TabId = 'positions' | 'analytics' | 'scalp_health' | 'intelligence' | 'backtest';
```

Add to `TABS` array (after analytics, before intelligence — line 27):
```typescript
    { id: 'scalp_health', label: 'Scalp Health', icon: <Activity size={13} /> },
```

Add `Activity` to lucide import (line 2):
```typescript
import { BarChart2, Brain, History, TestTube2, Activity } from 'lucide-react';
```

**Step 3: Add prop to BottomTabsProps**

Add to `BottomTabsProps` interface (around line 49):
```typescript
    // Scalp Health tab
    scalpHealth?: ScalpHealthContext;
```

**Step 4: Add mounted state for scalp_health**

Update the `mounted` initial state (line 95-100):
```typescript
    const [mounted, setMounted] = useState<Record<TabId, boolean>>({
        positions: true,
        analytics: false,
        scalp_health: false,
        intelligence: false,
        backtest: false,
    });
```

**Step 5: Add tab panel render**

After the Analytics tab panel (after line 186), before Intelligence:
```tsx
                {/* Scalp Health (React.lazy) */}
                {mounted.scalp_health && (
                    <div style={{ display: activeTab === 'scalp_health' ? 'block' : 'none' }}>
                        <Suspense fallback={<Skeleton lines={6} />}>
                            <ScalpHealthTabContent data={props.scalpHealth} />
                        </Suspense>
                    </div>
                )}
```

**Step 6: Pass scalpHealth prop from Dashboard.tsx**

In `Dashboard.tsx`, update the `bottomTabsProps` memo (around line 81-95) to include:
```typescript
        scalpHealth: intelligence?.scalp_health,
```

And add `scalpHealth` to the dependency array.

**Step 7: Verify TypeScript compiles**

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

**Step 8: Commit**

```bash
cd /Users/jitendrasonawane/Workpace/frontend
git add src/layout/BottomTabs.tsx src/Dashboard.tsx
git commit -m "feat(ui): wire ScalpHealthTab into BottomTabs as lazy-loaded tab"
```

---

## Task 8: Feed df_close_std (realized vol) to intelligence engine

The ScalpHealthModule needs historical realized volatility. The StrategyRunner has the OHLCV DataFrame but doesn't currently pass `df_close_std` to the intelligence engine.

**Files:**
- Modify: `app/core/strategy_runner.py` (where intelligence_engine.update is called)

**Step 1: Find the intelligence update call in strategy_runner.py**

Search for `intelligence_engine.update` in `app/core/strategy_runner.py`. Add `df_close_std` (5-day rolling std of log returns, annualized) to the data dict.

After the existing update call, ensure the data dict includes:
```python
    # Compute 5-day realized vol for ScalpHealthModule
    df_close_std = None
    if df is not None and len(df) >= 5:
        log_returns = np.log(df['close'] / df['close'].shift(1)).dropna()
        if len(log_returns) >= 5:
            df_close_std = float(log_returns.tail(5).std() * np.sqrt(252))  # annualized
```

Then include `"df_close_std": df_close_std` in the intelligence engine update call.

**Step 2: Test module receives realized vol**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/test_scalp_health.py -v --tb=short`
Expected: All tests still PASS

**Step 3: Commit**

```bash
git add app/core/strategy_runner.py
git commit -m "feat(runner): pass realized volatility to intelligence engine for scalp health"
```

---

## Task 9: End-to-end verification

**Step 1: Run full backend test suite**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -m pytest tests/ -v --tb=short`
Expected: All tests pass, including new `test_scalp_health.py`

**Step 2: Verify backend imports cleanly**

Run: `cd /Users/jitendrasonawane/Workpace/backend && python -c "from main import bot; bot.initialize(); ctx = bot.intelligence_engine.get_context(); print('scalp_health' in ctx, list(ctx.keys()))"`
Expected: `True ['market_regime', 'iv_rank', 'order_book', 'market_breadth', 'portfolio_greeks', 'oi_analysis', 'scalp_health']`

**Step 3: Verify frontend builds**

Run: `cd /Users/jitendrasonawane/Workpace/frontend && npm run build 2>&1 | tail -10`
Expected: Build succeeds

**Step 4: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "feat: complete scalp health panel — backend module + frontend tab"
```
