"""
Order Book Imbalance Module.

Reads bid/ask depth from the Upstox V3 Full mode WebSocket feed and computes
an order-book imbalance ratio that indicates smart-money directional bias
at the option level.

Inputs (via update):
    data['bid_ask'] — dict keyed by instrument_key:
        {
            "<ce_key>": {"bids": [{"price":..,"qty":..}, ...], "asks": [...]},
            "<pe_key>": {"bids": [...], "asks": [...]},
        }
    data['option_ce_key'] — str: current ATM CE instrument key
    data['option_pe_key'] — str: current ATM PE instrument key

Outputs (via get_context):
    ce_imbalance      : float — bid_qty_sum / ask_qty_sum for CE (> 1 = buying pressure)
    pe_imbalance      : float — same for PE
    ce_spread_pct     : float — (best_ask - best_bid) / mid * 100 for CE
    pe_spread_pct     : float — same for PE
    imbalance_signal  : "BULLISH" | "BEARISH" | "NEUTRAL"
    ce_liquidity      : "EXCELLENT" | "GOOD" | "POOR"
    pe_liquidity      : "EXCELLENT" | "GOOD" | "POOR"
    entry_quality     : 0-100 composite score

Notes:
  - If bid/ask depth is unavailable (SDK may not decode all fields),
    the module returns NEUTRAL — it never blocks a trade on missing data.
  - EXCELLENT liquidity: spread < 0.3%  GOOD: 0.3-1%  POOR: > 1%
"""

import logging
from typing import Any, Dict, List, Optional

from app.intelligence.base import IntelligenceModule

logger = logging.getLogger(__name__)


class OrderBookModule(IntelligenceModule):
    name = "order_book"

    SPREAD_EXCELLENT = 0.3   # %
    SPREAD_GOOD      = 1.0   # %

    def __init__(self):
        self._ce_imbalance: Optional[float] = None
        self._pe_imbalance: Optional[float] = None
        self._ce_spread_pct: Optional[float] = None
        self._pe_spread_pct: Optional[float] = None
        self._ce_key: Optional[str] = None
        self._pe_key: Optional[str] = None

    # ── IntelligenceModule interface ────────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        bid_ask: Dict[str, Any] = data.get("bid_ask", {})
        ce_key = data.get("option_ce_key")
        pe_key = data.get("option_pe_key")

        if ce_key:
            self._ce_key = ce_key
        if pe_key:
            self._pe_key = pe_key

        if bid_ask:
            if self._ce_key and self._ce_key in bid_ask:
                self._ce_imbalance, self._ce_spread_pct = self._analyse(bid_ask[self._ce_key])
            if self._pe_key and self._pe_key in bid_ask:
                self._pe_imbalance, self._pe_spread_pct = self._analyse(bid_ask[self._pe_key])

    def get_context(self) -> Dict[str, Any]:
        signal = self._imbalance_signal()
        ce_liq = self._liquidity_label(self._ce_spread_pct)
        pe_liq = self._liquidity_label(self._pe_spread_pct)
        quality = self._entry_quality(signal, ce_liq, pe_liq)

        return {
            "ce_imbalance":   round(self._ce_imbalance, 3) if self._ce_imbalance is not None else None,
            "pe_imbalance":   round(self._pe_imbalance, 3) if self._pe_imbalance is not None else None,
            "ce_spread_pct":  round(self._ce_spread_pct, 3) if self._ce_spread_pct is not None else None,
            "pe_spread_pct":  round(self._pe_spread_pct, 3) if self._pe_spread_pct is not None else None,
            "imbalance_signal": signal,
            "ce_liquidity":   ce_liq,
            "pe_liquidity":   pe_liq,
            "entry_quality":  quality,
        }

    def reset(self) -> None:
        self._ce_imbalance = None
        self._pe_imbalance = None
        self._ce_spread_pct = None
        self._pe_spread_pct = None

    # ── Private helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _analyse(book: Dict[str, Any]):
        """
        Compute imbalance ratio and spread % from a bid/ask book dict.
        book = { "bids": [{"price": x, "qty": y}, ...], "asks": [...] }
        Returns (imbalance, spread_pct) or (None, None) if data missing.
        """
        bids: List[Dict] = book.get("bids", [])
        asks: List[Dict] = book.get("asks", [])

        if not bids or not asks:
            return None, None

        bid_qty = sum(float(b.get("qty", 0)) for b in bids)
        ask_qty = sum(float(a.get("qty", 0)) for a in asks)

        imbalance = (bid_qty / ask_qty) if ask_qty > 0 else None

        # Best bid/ask spread
        try:
            best_bid = float(bids[0]["price"])
            best_ask = float(asks[0]["price"])
            mid = (best_bid + best_ask) / 2
            spread_pct = ((best_ask - best_bid) / mid * 100) if mid > 0 else None
        except (KeyError, IndexError, ZeroDivisionError):
            spread_pct = None

        return imbalance, spread_pct

    def _imbalance_signal(self) -> str:
        """Derive directional signal from order book imbalance."""
        ce = self._ce_imbalance
        pe = self._pe_imbalance

        if ce is None and pe is None:
            return "NEUTRAL"

        # Heavy CE buying (calls) = bullish; heavy PE buying = bearish
        if ce is not None and ce > 1.5:
            return "BULLISH"
        if pe is not None and pe > 1.5:
            return "BEARISH"
        return "NEUTRAL"

    def _liquidity_label(self, spread_pct: Optional[float]) -> str:
        if spread_pct is None:
            return "UNKNOWN"
        if spread_pct < self.SPREAD_EXCELLENT:
            return "EXCELLENT"
        if spread_pct < self.SPREAD_GOOD:
            return "GOOD"
        return "POOR"

    @staticmethod
    def _entry_quality(signal: str, ce_liq: str, pe_liq: str) -> int:
        """0-100 composite entry quality score."""
        liq_score = {"EXCELLENT": 40, "GOOD": 25, "POOR": 5, "UNKNOWN": 20}
        base = liq_score.get(ce_liq, 20) + liq_score.get(pe_liq, 20)   # max 80
        if signal != "NEUTRAL":
            base += 20                                                   # bonus for directional signal
        return min(100, base)
