"""
IV Rank & Percentile Tracker.

Tracks the historical range of Implied Volatility over a rolling 30-trading-day
window (~2340 samples at 5-min intervals) and computes IV Rank and IV Percentile
— critical for deciding *which type* of options strategy to deploy.

IV Rank is computed against the historical range only (current IV is NOT included
in the high/low range), so rank can exceed 100 or go below 0 when IV is at
extremes beyond the lookback window. IV Percentile uses strict less-than
comparison (% of past readings strictly below current IV).

Inputs (via update):
    data['iv']     — float: current ATM IV (e.g. 0.15 = 15%)
    data['expiry'] — str: expiry date string (for labelling)

Outputs (via get_context):
    iv_rank        : float (where is current IV vs 30-day high-low range?)
    iv_percentile  : 0-100 (what % of past readings is current IV strictly above?)
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

    # Collect first N samples at a faster interval for quick cold-start
    WARMUP_SAMPLES = 10
    WARMUP_INTERVAL = 30  # seconds between samples during warmup

    def __init__(self, history_size: int = 2340, history_interval: int = 300):
        """
        history_size: number of IV samples to keep.
        history_interval: seconds between history updates (default 300s = 5 mins).

        78 samples/day (6.5h × 12/h) × 30 trading days = 2340 samples.
        """
        self._history: deque[float] = deque(maxlen=history_size)
        self._current_iv: Optional[float] = None
        self._iv_rank: Optional[float] = None
        self._iv_percentile: Optional[float] = None
        self._expiry: Optional[str] = None

        self._last_history_update_time = 0.0
        self._history_interval = history_interval
        
        # Load state from disk on startup
        self.load_state()

    # ── IntelligenceModule interface ────────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        import time
        
        iv = data.get("iv")
        if iv is None or iv <= 0:
            # Try to pull from greeks dict if passed directly
            greeks = data.get("greeks") or {}
            ce_iv = (greeks.get("ce") or {}).get("iv")
            pe_iv = (greeks.get("pe") or {}).get("iv")
            # Use explicit None checks (0.0 would be falsy but is a valid edge case)
            if ce_iv is not None and ce_iv > 0 and pe_iv is not None and pe_iv > 0:
                iv = (ce_iv + pe_iv) / 2
            elif ce_iv is not None and ce_iv > 0:
                iv = ce_iv
            elif pe_iv is not None and pe_iv > 0:
                iv = pe_iv

        if iv is None or iv <= 0:
            return

        self._current_iv = float(iv)
        self._expiry = data.get("expiry")
        
        # Throttled history update — faster during warmup for quick cold-start
        now = time.time()
        interval = (
            self.WARMUP_INTERVAL
            if len(self._history) < self.WARMUP_SAMPLES
            else self._history_interval
        )
        if now - self._last_history_update_time >= interval:
            self._history.append(self._current_iv)
            self._last_history_update_time = now
            # Persist state after successful update
            self.save_state()
            
        # Always re-compute rank with latest current_iv against history
        self._compute()

    def get_context(self) -> Dict[str, Any]:
        if self._iv_rank is None:
            # Return current_iv as percentage for consistency
            current_iv_pct = round(self._current_iv * 100, 2) if self._current_iv is not None else None
            return {
                "iv_rank":           None,
                "iv_percentile":     None,
                "current_iv":        current_iv_pct,
                "iv_30d_high":       None,
                "iv_30d_low":        None,
                "iv_avg":            None,
                "recommendation":    "NEUTRAL",
                "premium_selling_ok": False,
                "history_size":      len(self._history),
            }

        rec = self._recommendation()
        
        # Handle empty history case safe-guard (though _compute checks len >= 2)
        if not self._history:
             return {
                "iv_rank":           None,
                "iv_percentile":     None,
                "current_iv":        round(self._current_iv * 100, 2),
                "history_size":      0
             }

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

    # ── Persistence ─────────────────────────────────────────────────────────

    def _get_file_path(self) -> Any:
        try:
            from pathlib import Path
            import os
            
            # Use a data directory relative to the project root or current working directory
            # Assuming typical structure: backend/data/
            # If backend is CWD, then ./data
            data_dir = Path("data")
            if not data_dir.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
                
            return data_dir / "iv_rank_history.json"
        except Exception as e:
            logger.error(f"Error determining IV rank file path: {e}")
            return None

    def save_state(self) -> None:
        """Save history to disk to survive restarts."""
        try:
            import json
            file_path = self._get_file_path()
            if not file_path:
                return

            state = {
                "history": list(self._history),
                "last_update": self._last_history_update_time
            }
            
            with open(file_path, 'w') as f:
                json.dump(state, f)
                
        except Exception as e:
            logger.error(f"Failed to save IV rank state: {e}")

    def load_state(self) -> None:
        """Load history from disk."""
        try:
            import json
            file_path = self._get_file_path()
            if not file_path or not file_path.exists():
                return

            with open(file_path, 'r') as f:
                state = json.load(f)
                
            history_list = state.get("history", [])
            last_update = state.get("last_update", 0.0)
            
            if history_list:
                self._history.extend(history_list)
                self._last_history_update_time = last_update
                logger.info(f"Loaded {len(self._history)} IV samples from disk.")
                
        except Exception as e:
            logger.error(f"Failed to load IV rank state: {e}")

    # ── Private helpers ─────────────────────────────────────────────────────

    def _compute(self) -> None:
        # Need at least 2 history points for a meaningful range
        if len(self._history) < 2:
            return

        iv_vals: List[float] = list(self._history)

        iv_high = max(iv_vals)
        iv_low  = min(iv_vals)
        cur     = self._current_iv

        # IV Rank: where is current IV in the historical high-low range?
        # Current IV can legitimately exceed the historical range (rank > 100 or < 0),
        # which is valuable signal — it means IV is at an extreme.
        if iv_high > iv_low:
            self._iv_rank = ((cur - iv_low) / (iv_high - iv_low)) * 100
        else:
            self._iv_rank = 50.0

        # IV Percentile: what % of past readings is current IV strictly above?
        below = sum(1 for v in iv_vals if v < cur)
        self._iv_percentile = (below / len(iv_vals)) * 100

    def _recommendation(self) -> str:
        if self._iv_rank is None:
            return "NEUTRAL"
        if self._iv_rank >= self.SELL_PREMIUM_THRESHOLD:
            return "SELL_PREMIUM"
        if self._iv_rank <= self.BUY_DEBIT_THRESHOLD:
            return "BUY_DEBIT"
        return "NEUTRAL"
