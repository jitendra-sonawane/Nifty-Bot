"""
Order Flow Intelligence Module.

Wraps OrderFlowAnalyzer as an IntelligenceModule plugin for signal
confirmation / rejection.  Computes four sub-scores — VWAP alignment,
delta momentum, book support, volume profile — and a composite pass/fail
gate that the strategy engine can use before entering a trade.

Inputs (via update):
    data['signal_direction'] — "CE" or "PE" (current trade direction)

Outputs (via get_context):
    pass       : bool   — True if composite >= 40
    score      : float  — composite score 0-100
    components : dict   — { vwap_alignment, delta_momentum, book_support,
                            volume_profile } each 0-100
    alerts     : list   — human-readable alert strings
    snapshot   : dict   — full OrderFlowAnalyzer snapshot

Notes:
  - When no data has been ingested yet (total_volume == 0) the module
    returns safe defaults (pass=True, score=50) so that it never blocks
    a trade on missing order-flow data.
"""

import logging
from statistics import mean
from typing import Any, Dict, List

from app.intelligence.base import IntelligenceModule
from app.core.order_flow import OrderFlowAnalyzer

logger = logging.getLogger(__name__)


class OrderFlowModule(IntelligenceModule):
    """Intelligence plugin that scores order-flow alignment with a signal."""

    name = "order_flow"

    def __init__(self, analyzer: OrderFlowAnalyzer):
        self._analyzer = analyzer
        self._signal_direction: str = "CE"  # Default

    # ── IntelligenceModule interface ──────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        """Extract signal_direction from data dict.

        Accepts:
            data['signal_direction'] — "CE" or "PE"
        """
        direction = data.get("signal_direction")
        if direction:
            self._signal_direction = direction

    def get_context(self) -> Dict[str, Any]:
        """Return composite scoring context. Never raises."""
        snap = self._analyzer.get_snapshot()

        # If no data yet, return safe defaults that don't block
        if snap["total_volume"] == 0:
            return {
                "pass": True,
                "score": 50.0,
                "components": {
                    "vwap_alignment": 50.0,
                    "delta_momentum": 50.0,
                    "book_support": 50.0,
                    "volume_profile": 50.0,
                },
                "alerts": [],
                "snapshot": snap,
            }

        direction = self._signal_direction

        # --- Compute 4 sub-scores ---
        vwap_alignment = self._score_vwap_alignment(snap, direction)
        delta_momentum = self._score_delta_momentum(snap, direction)
        book_support = self._score_book_support(snap, direction)
        volume_profile = self._score_volume_profile(snap, direction)

        components = {
            "vwap_alignment": vwap_alignment,
            "delta_momentum": delta_momentum,
            "book_support": book_support,
            "volume_profile": volume_profile,
        }

        composite = mean(components.values())
        passed = composite >= 40

        # --- Alerts ---
        alerts = self._build_alerts(snap)

        return {
            "pass": passed,
            "score": round(composite, 2),
            "components": components,
            "alerts": alerts,
            "snapshot": snap,
        }

    def reset(self) -> None:
        """Reset analyzer state and direction to defaults."""
        self._analyzer.reset()
        self._signal_direction = "CE"

    # ── Sub-score computations ───────────────────────────────────────────

    @staticmethod
    def _score_vwap_alignment(snap: Dict, direction: str) -> float:
        """Is POC positioned correctly for signal direction?"""
        poc = snap["poc"]
        vwap = snap["vwap"]
        vwap_lower = snap["vwap_lower"]
        vwap_upper = snap["vwap_upper"]

        if vwap == 0.0:
            return 50.0

        if direction == "CE":
            if poc > vwap:
                return 80.0
            elif poc >= vwap_lower:
                return 50.0
            else:
                return 20.0
        else:  # PE
            if poc < vwap:
                return 80.0
            elif poc <= vwap_upper:
                return 50.0
            else:
                return 20.0

    @staticmethod
    def _score_delta_momentum(snap: Dict, direction: str) -> float:
        """Is divergence against signal direction?"""
        div = snap["delta_divergence"]

        if not div["active"]:
            return 80.0

        div_type = div["type"]
        strength = div["strength"]

        if direction == "CE" and div_type == "bearish":
            return max(20.0, 80.0 - strength * 60.0)
        elif direction == "PE" and div_type == "bullish":
            return max(20.0, 80.0 - strength * 60.0)
        else:
            # Divergence supports direction (CE + bullish div, PE + bearish div)
            return 80.0

    @staticmethod
    def _score_book_support(snap: Dict, direction: str) -> float:
        """Order book alignment with direction."""
        imb = snap["book_imbalance"]

        if direction == "CE":
            if imb > 0.55:
                return 80.0
            elif imb >= 0.45:
                return 50.0
            else:
                return 20.0
        else:  # PE
            if imb < 0.45:
                return 80.0
            elif imb <= 0.55:
                return 50.0
            else:
                return 20.0

    @staticmethod
    def _score_volume_profile(snap: Dict, direction: str) -> float:
        """Is price within value area?"""
        poc = snap["poc"]
        vwap = snap["vwap"]
        va_high = snap["value_area_high"]
        va_low = snap["value_area_low"]

        if va_high == 0.0 and va_low == 0.0:
            return 50.0

        if direction == "CE":
            if poc >= va_low:
                if poc >= vwap:
                    return 80.0
                else:
                    return 60.0
            else:
                return 30.0
        else:  # PE
            if poc <= va_high:
                if poc <= vwap:
                    return 80.0
                else:
                    return 60.0
            else:
                return 30.0

    # ── Alert generation ─────────────────────────────────────────────────

    @staticmethod
    def _build_alerts(snap: Dict) -> List[str]:
        """Generate human-readable alerts from snapshot state."""
        alerts: List[str] = []

        # Divergence alerts
        div = snap["delta_divergence"]
        if div["active"]:
            strength_pct = round(div["strength"] * 100)
            bars = div["bars"]
            if div["type"] == "bearish":
                alerts.append(
                    f"Bearish divergence (strength {strength_pct}%, {bars} bars)"
                )
            elif div["type"] == "bullish":
                alerts.append(
                    f"Bullish divergence (strength {strength_pct}%, {bars} bars)"
                )

        # Book pressure alerts
        imb = snap["book_imbalance"]
        imb_pct = round(imb * 100)
        if imb > 0.65:
            alerts.append(f"Strong bid pressure ({imb_pct}%)")
        elif imb < 0.35:
            alerts.append(f"Strong ask pressure ({imb_pct}%)")

        return alerts
