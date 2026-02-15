"""
IV Rank & Percentile Tracker.

Tracks the historical range of Implied Volatility over a rolling 30-day
window and computes IV Rank and IV Percentile — critical for deciding
*which type* of options strategy to deploy.

Inputs (via update):
    data['iv']     — float: current ATM IV (e.g. 0.15 = 15%)
    data['expiry'] — str: expiry date string (for labelling)

Outputs (via get_context):
    iv_rank        : 0-100 (where is current IV vs 30-day high-low range?)
    iv_percentile  : 0-100 (what % of past readings is current IV above?)
    current_iv     : latest IV value
    iv_30d_high    : 30-day IV high
    iv_30d_low     : 30-day IV low
    iv_avg         : 30-day IV average
    recommendation : "SELL_PREMIUM" | "BUY_DEBIT" | "NEUTRAL"
    premium_selling_ok : bool — True if IV Rank >= threshold

Decision rules:
    IV Rank >= 60  → premium selling conditions are good (Iron Condor, Straddle)
    IV Rank <= 30  → IV is cheap → buy debit spreads, avoid credit strategies
    30 < IV Rank < 60 → neutral, use with other filters
"""

import logging
from collections import deque
from typing import Any, Dict, List, Optional

from app.intelligence.base import IntelligenceModule

logger = logging.getLogger(__name__)


class IVRankModule(IntelligenceModule):
    name = "iv_rank"

    # Thresholds
    SELL_PREMIUM_THRESHOLD = 60   # IV Rank >= 60 → ok to sell premium
    BUY_DEBIT_THRESHOLD    = 30   # IV Rank <= 30 → buy debit spreads

    def __init__(self, history_size: int = 390):
        """
        history_size: number of IV samples to keep.
        390 samples ≈ 30 trading days × 13 five-minute candles/hour × ~1 sample per tick.
        For simplicity we store one reading per update call (throttle externally if needed).
        """
        self._history: deque[float] = deque(maxlen=history_size)
        self._current_iv: Optional[float] = None
        self._iv_rank: Optional[float] = None
        self._iv_percentile: Optional[float] = None
        self._expiry: Optional[str] = None

    # ── IntelligenceModule interface ────────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        iv = data.get("iv")
        if iv is None:
            # Try to pull from greeks dict if passed directly
            greeks = data.get("greeks") or {}
            ce_iv = (greeks.get("ce") or {}).get("iv")
            pe_iv = (greeks.get("pe") or {}).get("iv")
            if ce_iv and pe_iv:
                iv = (ce_iv + pe_iv) / 2
            elif ce_iv:
                iv = ce_iv
            elif pe_iv:
                iv = pe_iv

        if iv is None or iv <= 0:
            return

        self._current_iv = float(iv)
        self._expiry = data.get("expiry")
        self._history.append(self._current_iv)
        self._compute()

    def get_context(self) -> Dict[str, Any]:
        if self._iv_rank is None:
            return {
                "iv_rank":           None,
                "iv_percentile":     None,
                "current_iv":        self._current_iv,
                "iv_30d_high":       None,
                "iv_30d_low":        None,
                "iv_avg":            None,
                "recommendation":    "NEUTRAL",
                "premium_selling_ok": False,
                "history_size":      len(self._history),
            }

        rec = self._recommendation()
        return {
            "iv_rank":           round(self._iv_rank, 1),
            "iv_percentile":     round(self._iv_percentile, 1),
            "current_iv":        round(self._current_iv * 100, 2),   # as percentage
            "iv_30d_high":       round(max(self._history) * 100, 2),
            "iv_30d_low":        round(min(self._history) * 100, 2),
            "iv_avg":            round(sum(self._history) / len(self._history) * 100, 2),
            "recommendation":    rec,
            "premium_selling_ok": self._iv_rank >= self.SELL_PREMIUM_THRESHOLD,
            "history_size":      len(self._history),
        }

    def reset(self) -> None:
        pass  # IV history is rolling; no daily reset needed

    # ── Private helpers ─────────────────────────────────────────────────────

    def _compute(self) -> None:
        if len(self._history) < 5:
            return  # Not enough data yet

        iv_vals: List[float] = list(self._history)
        iv_high = max(iv_vals)
        iv_low  = min(iv_vals)
        cur     = self._current_iv

        # IV Rank: where is current IV in the high-low range?
        if iv_high > iv_low:
            self._iv_rank = ((cur - iv_low) / (iv_high - iv_low)) * 100
        else:
            self._iv_rank = 50.0

        # IV Percentile: what % of past readings is current IV above?
        below = sum(1 for v in iv_vals if v <= cur)
        self._iv_percentile = (below / len(iv_vals)) * 100

    def _recommendation(self) -> str:
        if self._iv_rank is None:
            return "NEUTRAL"
        if self._iv_rank >= self.SELL_PREMIUM_THRESHOLD:
            return "SELL_PREMIUM"
        if self._iv_rank <= self.BUY_DEBIT_THRESHOLD:
            return "BUY_DEBIT"
        return "NEUTRAL"
