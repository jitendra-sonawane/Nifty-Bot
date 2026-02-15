"""
Market Breadth Module — Advance-Decline Analysis on Nifty 50 constituents.

Already subscribed in MarketDataManager (50 stocks for the heatmap).
We re-use that data to derive *market breadth* — an independent confirmation
signal that tells us whether Nifty's move is backed by broad participation.

Inputs (via update):
    data['nifty50_quotes'] — dict:
        { "RELIANCE": {"price": .., "changePercent": .., "change": ..}, ... }

Outputs (via get_context):
    advancing         : int — number of Nifty50 stocks with positive change
    declining         : int — number of Nifty50 stocks with negative change
    unchanged         : int — flat stocks
    ad_ratio          : float — advancing / declining (> 1.5 → strong breadth)
    breadth_score     : 0-100 — 50 is neutral, > 60 bullish, < 40 bearish
    breadth_bias      : "STRONG_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "STRONG_BEARISH"
    top_movers_up     : list of top 5 advancing symbols (sorted by % change)
    top_movers_down   : list of top 5 declining symbols
    coverage          : int — number of stocks with live data
    breadth_confirms_ce : bool — breadth supports a BUY_CE signal
    breadth_confirms_pe : bool — breadth supports a BUY_PE signal
"""

import logging
from typing import Any, Dict, List, Optional

from app.intelligence.base import IntelligenceModule

logger = logging.getLogger(__name__)


class MarketBreadthModule(IntelligenceModule):
    name = "market_breadth"

    # Thresholds
    STRONG_BULLISH_THRESHOLD = 35   # >= 35/50 advancing → strong bullish
    BULLISH_THRESHOLD        = 28   # >= 28/50 advancing → bullish
    BEARISH_THRESHOLD        = 22   # <= 22/50 advancing → bearish
    STRONG_BEARISH_THRESHOLD = 15   # <= 15/50 advancing → strong bearish

    def __init__(self):
        self._advancing: int = 0
        self._declining: int = 0
        self._unchanged: int = 0
        self._coverage: int = 0
        self._top_up:   List[str] = []
        self._top_down: List[str] = []

    # ── IntelligenceModule interface ────────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        quotes: Dict[str, Any] = data.get("nifty50_quotes", {})
        if not quotes:
            return

        try:
            self._compute(quotes)
        except Exception as e:
            logger.error(f"MarketBreadthModule update error: {e}")

    def get_context(self) -> Dict[str, Any]:
        if self._coverage == 0:
            return {
                "advancing":           0,
                "declining":           0,
                "unchanged":           0,
                "ad_ratio":            None,
                "breadth_score":       50,
                "breadth_bias":        "NEUTRAL",
                "top_movers_up":       [],
                "top_movers_down":     [],
                "coverage":            0,
                "breadth_confirms_ce": False,
                "breadth_confirms_pe": False,
            }

        ad_ratio = (self._advancing / max(self._declining, 1))
        score = self._score()
        bias  = self._bias(score)

        return {
            "advancing":           self._advancing,
            "declining":           self._declining,
            "unchanged":           self._unchanged,
            "ad_ratio":            round(ad_ratio, 2),
            "breadth_score":       score,
            "breadth_bias":        bias,
            "top_movers_up":       self._top_up,
            "top_movers_down":     self._top_down,
            "coverage":            self._coverage,
            "breadth_confirms_ce": bias in ("STRONG_BULLISH", "BULLISH"),
            "breadth_confirms_pe": bias in ("STRONG_BEARISH", "BEARISH"),
        }

    def reset(self) -> None:
        # Quotes are live — no daily reset needed
        pass

    # ── Private helpers ─────────────────────────────────────────────────────

    def _compute(self, quotes: Dict[str, Any]) -> None:
        advancing = 0
        declining = 0
        unchanged = 0
        moves = []

        for symbol, data in quotes.items():
            chg_pct = data.get("changePercent", data.get("change_percent", 0))
            if chg_pct is None:
                continue
            chg_pct = float(chg_pct)
            moves.append((symbol, chg_pct))

            if chg_pct > 0.05:
                advancing += 1
            elif chg_pct < -0.05:
                declining += 1
            else:
                unchanged += 1

        self._advancing = advancing
        self._declining = declining
        self._unchanged = unchanged
        self._coverage  = len(moves)

        moves.sort(key=lambda x: x[1], reverse=True)
        self._top_up   = [s for s, _ in moves[:5]]
        self._top_down = [s for s, _ in moves[-5:]]

    def _score(self) -> int:
        """0-100 breadth score.  50 = neutral."""
        total = self._advancing + self._declining
        if total == 0:
            return 50
        bull_ratio = self._advancing / total  # 0→1
        # Map [0, 1] → [0, 100]
        return min(100, max(0, int(bull_ratio * 100)))

    def _bias(self, score: int) -> str:
        adv = self._advancing
        if adv >= self.STRONG_BULLISH_THRESHOLD:
            return "STRONG_BULLISH"
        if adv >= self.BULLISH_THRESHOLD:
            return "BULLISH"
        if adv <= self.STRONG_BEARISH_THRESHOLD:
            return "STRONG_BEARISH"
        if adv <= self.BEARISH_THRESHOLD:
            return "BEARISH"
        return "NEUTRAL"
