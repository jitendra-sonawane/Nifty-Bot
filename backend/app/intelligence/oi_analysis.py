"""
OI Analysis Module — Open Interest change tracking and Max Pain calculation.

Tracks OI snapshots over time to classify market activity:
    LONG_BUILDUP:    Price ↑ + OI ↑ (strong bullish — fresh longs)
    SHORT_COVERING:  Price ↑ + OI ↓ (weak bullish — shorts exiting)
    SHORT_BUILDUP:   Price ↓ + OI ↑ (strong bearish — fresh shorts)
    LONG_UNWINDING:  Price ↓ + OI ↓ (weak bearish — longs exiting)

Also calculates:
    - Max OI strikes (highest CE OI = resistance, highest PE OI = support)
    - Max Pain strike (strike where option writers lose least)

Consumes from engine.update():
    data["pcr_oi_data"]          — dict[instrument_key, float(oi)]
    data["pcr_option_metadata"]  — dict[instrument_key, {strike, option_type}]
    data["current_price"]        — float
"""

import time
import logging
from collections import deque
from typing import Any, Dict, Optional

from app.intelligence.base import IntelligenceModule

logger = logging.getLogger(__name__)


class OIAnalysisModule(IntelligenceModule):
    """Tracks OI changes to detect buildup/unwinding and calculates Max Pain."""

    name = "oi_analysis"

    # Minimum snapshots before we start classifying
    MIN_SNAPSHOTS = 5
    # Compare current vs N snapshots ago
    LOOKBACK = 5
    # Thresholds
    PRICE_FLAT_PCT = 0.05    # ±0.05% = flat
    OI_FLAT_PCT = 0.5        # ±0.5% = no meaningful OI change

    def __init__(self):
        self._snapshots: deque = deque(maxlen=60)  # ~5 min at 5s intervals
        self._last_snapshot_time: float = 0.0
        self._snapshot_interval: float = 5.0  # seconds between snapshots

        # Cached results
        self._buildup_signal: str = "NEUTRAL"
        self._oi_change_pct: float = 0.0
        self._ce_oi_change_pct: float = 0.0
        self._pe_oi_change_pct: float = 0.0
        self._price_direction: str = "FLAT"
        self._confirms_ce: bool = False
        self._confirms_pe: bool = False
        self._max_oi_ce_strike: Optional[float] = None
        self._max_oi_pe_strike: Optional[float] = None
        self._max_pain_strike: Optional[float] = None
        self._current_price: float = 0.0

    def update(self, data: Dict[str, Any]) -> None:
        pcr_oi_data = data.get("pcr_oi_data")
        metadata = data.get("pcr_option_metadata")
        price = data.get("current_price")

        if not pcr_oi_data or not metadata or not price:
            return

        self._current_price = price
        now = time.time()

        # Take snapshot at configured interval
        if now - self._last_snapshot_time < self._snapshot_interval:
            return

        self._last_snapshot_time = now

        # Aggregate OI by strike and type
        per_strike: Dict[float, Dict[str, float]] = {}
        total_ce_oi = 0.0
        total_pe_oi = 0.0

        for key, oi in pcr_oi_data.items():
            meta = metadata.get(key)
            if not meta:
                continue
            strike = meta["strike"]
            opt_type = meta["option_type"]

            if strike not in per_strike:
                per_strike[strike] = {"ce_oi": 0.0, "pe_oi": 0.0}

            if opt_type == "CE":
                per_strike[strike]["ce_oi"] = oi
                total_ce_oi += oi
            elif opt_type == "PE":
                per_strike[strike]["pe_oi"] = oi
                total_pe_oi += oi

        self._snapshots.append({
            "timestamp": now,
            "price": price,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "per_strike": per_strike,
        })

        # Calculate max OI strikes (from latest snapshot)
        self._update_max_oi_strikes(per_strike)

        # Calculate max pain (from latest snapshot)
        self._update_max_pain(per_strike)

        # Classify buildup/unwinding (need enough history)
        if len(self._snapshots) >= self.MIN_SNAPSHOTS:
            self._classify_buildup()

    def _update_max_oi_strikes(self, per_strike: Dict[float, Dict[str, float]]) -> None:
        """Find strikes with highest CE OI (resistance) and PE OI (support)."""
        if not per_strike:
            return

        max_ce_oi = 0.0
        max_pe_oi = 0.0
        max_ce_strike = None
        max_pe_strike = None

        for strike, oi_data in per_strike.items():
            if oi_data["ce_oi"] > max_ce_oi:
                max_ce_oi = oi_data["ce_oi"]
                max_ce_strike = strike
            if oi_data["pe_oi"] > max_pe_oi:
                max_pe_oi = oi_data["pe_oi"]
                max_pe_strike = strike

        self._max_oi_ce_strike = max_ce_strike
        self._max_oi_pe_strike = max_pe_strike

    def _update_max_pain(self, per_strike: Dict[float, Dict[str, float]]) -> None:
        """
        Calculate Max Pain — the strike where total loss to option writers is minimized.

        For each candidate expiry price (each strike), calculate the total intrinsic
        value that would be paid out by writers across all strikes.
        The strike with the minimum total payout is max pain.
        """
        strikes = sorted(per_strike.keys())
        if len(strikes) < 3:
            return

        min_pain = float("inf")
        max_pain_strike = None

        for candidate in strikes:
            total_pain = 0.0
            for strike, oi_data in per_strike.items():
                # CE writers pay if candidate > strike (CE is ITM)
                if candidate > strike:
                    total_pain += (candidate - strike) * oi_data["ce_oi"]
                # PE writers pay if candidate < strike (PE is ITM)
                if candidate < strike:
                    total_pain += (strike - candidate) * oi_data["pe_oi"]

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = candidate

        self._max_pain_strike = max_pain_strike

    def _classify_buildup(self) -> None:
        """Compare current snapshot vs LOOKBACK snapshots ago to classify activity."""
        current = self._snapshots[-1]
        lookback_idx = max(0, len(self._snapshots) - 1 - self.LOOKBACK)
        previous = self._snapshots[lookback_idx]

        # Price direction
        price_now = current["price"]
        price_then = previous["price"]
        if price_then == 0:
            self._buildup_signal = "NEUTRAL"
            return

        price_change_pct = ((price_now - price_then) / price_then) * 100
        if price_change_pct > self.PRICE_FLAT_PCT:
            self._price_direction = "UP"
        elif price_change_pct < -self.PRICE_FLAT_PCT:
            self._price_direction = "DOWN"
        else:
            self._price_direction = "FLAT"

        # OI direction (total OI = CE + PE)
        total_oi_now = current["total_ce_oi"] + current["total_pe_oi"]
        total_oi_then = previous["total_ce_oi"] + previous["total_pe_oi"]
        if total_oi_then == 0:
            self._buildup_signal = "NEUTRAL"
            return

        self._oi_change_pct = ((total_oi_now - total_oi_then) / total_oi_then) * 100

        # Per-side OI changes
        if previous["total_ce_oi"] > 0:
            self._ce_oi_change_pct = ((current["total_ce_oi"] - previous["total_ce_oi"]) / previous["total_ce_oi"]) * 100
        else:
            self._ce_oi_change_pct = 0.0

        if previous["total_pe_oi"] > 0:
            self._pe_oi_change_pct = ((current["total_pe_oi"] - previous["total_pe_oi"]) / previous["total_pe_oi"]) * 100
        else:
            self._pe_oi_change_pct = 0.0

        oi_up = self._oi_change_pct > self.OI_FLAT_PCT
        oi_down = self._oi_change_pct < -self.OI_FLAT_PCT

        # Classify
        if self._price_direction == "FLAT" or (not oi_up and not oi_down):
            self._buildup_signal = "NEUTRAL"
            self._confirms_ce = False
            self._confirms_pe = False
        elif self._price_direction == "UP" and oi_up:
            self._buildup_signal = "LONG_BUILDUP"
            self._confirms_ce = True
            self._confirms_pe = False
        elif self._price_direction == "UP" and oi_down:
            self._buildup_signal = "SHORT_COVERING"
            self._confirms_ce = True   # Weak bullish, still supports CE
            self._confirms_pe = False
        elif self._price_direction == "DOWN" and oi_up:
            self._buildup_signal = "SHORT_BUILDUP"
            self._confirms_ce = False
            self._confirms_pe = True
        elif self._price_direction == "DOWN" and oi_down:
            self._buildup_signal = "LONG_UNWINDING"
            self._confirms_ce = False
            self._confirms_pe = True   # Weak bearish, still supports PE
        else:
            self._buildup_signal = "NEUTRAL"
            self._confirms_ce = False
            self._confirms_pe = False

        logger.info(
            f"📊 OI Analysis: {self._buildup_signal} | "
            f"Price: {self._price_direction} ({price_change_pct:+.2f}%) | "
            f"OI: {self._oi_change_pct:+.2f}% | "
            f"Max Pain: {self._max_pain_strike}"
        )

    def get_context(self) -> Dict[str, Any]:
        distance = None
        distance_pct = None
        if self._max_pain_strike and self._current_price > 0:
            distance = self._current_price - self._max_pain_strike
            distance_pct = (distance / self._current_price) * 100

        return {
            "buildup_signal": self._buildup_signal,
            "oi_change_pct": round(self._oi_change_pct, 2),
            "ce_oi_change_pct": round(self._ce_oi_change_pct, 2),
            "pe_oi_change_pct": round(self._pe_oi_change_pct, 2),
            "price_direction": self._price_direction,
            "confirms_ce": self._confirms_ce,
            "confirms_pe": self._confirms_pe,
            "max_oi_ce_strike": self._max_oi_ce_strike,
            "max_oi_pe_strike": self._max_oi_pe_strike,
            "max_pain_strike": self._max_pain_strike,
            "distance_from_max_pain": round(distance, 2) if distance is not None else None,
            "distance_from_max_pain_pct": round(distance_pct, 3) if distance_pct is not None else None,
            "snapshots_count": len(self._snapshots),
        }

    def reset(self) -> None:
        """Reset daily state."""
        self._snapshots.clear()
        self._last_snapshot_time = 0.0
        self._buildup_signal = "NEUTRAL"
        self._oi_change_pct = 0.0
        self._ce_oi_change_pct = 0.0
        self._pe_oi_change_pct = 0.0
        self._price_direction = "FLAT"
        self._confirms_ce = False
        self._confirms_pe = False
        self._max_oi_ce_strike = None
        self._max_oi_pe_strike = None
        self._max_pain_strike = None
        logger.info("OI Analysis module reset for new session.")
