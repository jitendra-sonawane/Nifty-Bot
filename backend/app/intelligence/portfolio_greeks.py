"""
Portfolio Greeks Aggregation Module.

Computes net portfolio-level Greeks by summing individual position Greeks
weighted by their sign (buy = +1, sell = -1) and quantity.

This tells us the aggregate directional exposure (delta), convexity (gamma),
time decay benefit/cost (theta) and volatility sensitivity (vega) of the
entire open book.

Inputs (via update):
    data['positions']        — list of position dicts from PositionManager / PaperTrading
    data['greeks']           — current ATM greeks dict from MarketDataManager

Outputs (via get_context):
    net_delta       : float — positive = net long delta (bullish bias)
    net_gamma       : float
    net_theta       : float — negative = paying theta (debit); positive = collecting
    net_vega        : float — positive = long vol exposure
    delta_bias      : "LONG_DELTA" | "SHORT_DELTA" | "NEUTRAL"
    hedge_needed    : bool — |net_delta| > threshold
    hedge_action    : "BUY_PE" | "BUY_CE" | None — how to hedge
    portfolio_risk  : "HIGH" | "MEDIUM" | "LOW"
    position_count  : int
"""

import logging
from typing import Any, Dict, List, Optional

from app.intelligence.base import IntelligenceModule

logger = logging.getLogger(__name__)


class PortfolioGreeksModule(IntelligenceModule):
    name = "portfolio_greeks"

    # Delta hedge threshold — trigger hedge if |net_delta| exceeds this
    DELTA_HEDGE_THRESHOLD = 0.30

    def __init__(self):
        self._net_delta:  float = 0.0
        self._net_gamma:  float = 0.0
        self._net_theta:  float = 0.0
        self._net_vega:   float = 0.0
        self._position_count: int = 0
        self._atm_greeks: Optional[Dict] = None

    # ── IntelligenceModule interface ────────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        positions: List[Dict] = data.get("positions", [])
        greeks: Optional[Dict] = data.get("greeks")

        if greeks:
            self._atm_greeks = greeks

        self._aggregate(positions)

    def get_context(self) -> Dict[str, Any]:
        bias        = self._delta_bias()
        hedge_needed = abs(self._net_delta) > self.DELTA_HEDGE_THRESHOLD
        hedge_action: Optional[str] = None
        if hedge_needed:
            hedge_action = "BUY_PE" if self._net_delta > 0 else "BUY_CE"

        risk = self._portfolio_risk()

        return {
            "net_delta":      round(self._net_delta, 4),
            "net_gamma":      round(self._net_gamma, 6),
            "net_theta":      round(self._net_theta, 2),
            "net_vega":       round(self._net_vega, 4),
            "delta_bias":     bias,
            "hedge_needed":   hedge_needed,
            "hedge_action":   hedge_action,
            "portfolio_risk": risk,
            "position_count": self._position_count,
        }

    def reset(self) -> None:
        self._net_delta = 0.0
        self._net_gamma = 0.0
        self._net_theta = 0.0
        self._net_vega  = 0.0
        self._position_count = 0

    # ── Private helpers ─────────────────────────────────────────────────────

    def _aggregate(self, positions: List[Dict]) -> None:
        """Sum Greeks across all open positions."""
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega  = 0.0
        count = 0

        atm_g = self._atm_greeks or {}
        ce_g  = atm_g.get("ce", {}) or {}
        pe_g  = atm_g.get("pe", {}) or {}

        for pos in positions:
            if not pos:
                continue

            qty  = float(pos.get("quantity", 0))
            ptype = pos.get("position_type", "CE")  # CE or PE
            # BUY positions → positive multiplier; SELL → negative
            side = 1.0 if pos.get("transaction_type", "BUY") == "BUY" else -1.0
            signed_qty = qty * side

            # Get Greeks from position dict (preferred) or fall back to ATM Greeks
            pos_greeks = pos.get("greeks") or (ce_g if ptype == "CE" else pe_g)
            if not pos_greeks:
                continue

            delta = float(pos_greeks.get("delta", 0) or 0)
            gamma = float(pos_greeks.get("gamma", 0) or 0)
            theta = float(pos_greeks.get("theta", 0) or 0)
            vega  = float(pos_greeks.get("vega",  0) or 0)

            # For multi-leg positions with sub-legs
            legs = pos.get("legs", [])
            if legs:
                for leg in legs:
                    leg_qty  = float(leg.get("quantity", qty))
                    leg_side = 1.0 if leg.get("transaction_type", "BUY") == "BUY" else -1.0
                    leg_g    = leg.get("greeks") or pos_greeks
                    total_delta += float(leg_g.get("delta", 0) or 0) * leg_qty * leg_side
                    total_gamma += float(leg_g.get("gamma", 0) or 0) * leg_qty * leg_side
                    total_theta += float(leg_g.get("theta", 0) or 0) * leg_qty * leg_side
                    total_vega  += float(leg_g.get("vega",  0) or 0) * leg_qty * leg_side
            else:
                total_delta += delta * signed_qty
                total_gamma += gamma * signed_qty
                total_theta += theta * signed_qty
                total_vega  += vega  * signed_qty

            count += 1

        self._net_delta  = total_delta
        self._net_gamma  = total_gamma
        self._net_theta  = total_theta
        self._net_vega   = total_vega
        self._position_count = count

    def _delta_bias(self) -> str:
        if self._net_delta > 0.10:
            return "LONG_DELTA"
        if self._net_delta < -0.10:
            return "SHORT_DELTA"
        return "NEUTRAL"

    def _portfolio_risk(self) -> str:
        delta_risk = abs(self._net_delta)
        vega_risk  = abs(self._net_vega)
        if delta_risk > 0.5 or vega_risk > 0.05:
            return "HIGH"
        if delta_risk > 0.25 or vega_risk > 0.02:
            return "MEDIUM"
        return "LOW"
