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

        # 1. OI Buildup Signal
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

        # 4-5. Max OI + Max Pain
        max_oi_ce_strike, max_oi_pe_strike = self._find_max_oi_strikes(latest["per_strike"])
        max_pain = self._compute_max_pain(latest["per_strike"])
        max_pain_distance = round(self._price - max_pain, 2) if max_pain and self._price > 0 else 0.0

        # 6. OI Concentration Index
        oi_conc = self._compute_oi_concentration(latest["per_strike"], latest["total_ce"] + latest["total_pe"])

        # 7. Volume/OI Ratio — approximate from OI change rate
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
        """OI at top 3 strikes / total OI x 100."""
        if total_oi <= 0 or not per_strike:
            return 0
        combined = [(s, oi["ce_oi"] + oi["pe_oi"]) for s, oi in per_strike.items()]
        combined.sort(key=lambda x: x[1], reverse=True)
        top3_oi = sum(x[1] for x in combined[:3])
        return min(100, int((top3_oi / total_oi) * 100))

    def _compute_pcr_trend(self) -> str:
        """PCR direction over last 15 minutes."""
        if len(self._pcr_history) < 6:
            return "STABLE"
        recent = list(self._pcr_history)[-30:]
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

        # Effective spread
        if spread_ce is not None and spread_pe is not None:
            eff = (spread_ce + spread_pe) / 2.0 * 0.75
        else:
            eff = 0.0

        # Lot liquidity — proxy from bid-ask depth totals if available
        ce_depth = self._bid_ask.get("ce_bid_qty", 0) + self._bid_ask.get("ce_ask_qty", 0)
        pe_depth = self._bid_ask.get("pe_bid_qty", 0) + self._bid_ask.get("pe_ask_qty", 0)
        total_depth = ce_depth + pe_depth
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
                momentum = min(momentum, 200.0)

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
            os_ += 30
        elif signal in ("SHORT_COVERING", "LONG_UNWINDING"):
            os_ += 15
        if oi["oi_rate_alert"]:
            os_ += 20
        if oi["oi_concentration"] >= conf["oi_conc_high"]:
            os_ += 15
        elif oi["oi_concentration"] <= conf["oi_conc_low"]:
            os_ += 10
        pcr_t = oi["pcr_trend"]
        if pcr_t in ("RISING", "FALLING"):
            os_ += 15
        if oi["unwinding_alert"]:
            os_ += 20
        oi_score = min(100, os_)

        # Sub-score: Time/Decay (0-100)
        ts = 50
        if greeks["gamma_peak"]:
            ts += 30
        if abs(greeks["theta_per_minute"]) < 0.01:
            ts += 20
        elif abs(greeks["theta_per_minute"]) > 0.1:
            ts -= 20
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
            ms -= 10
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
