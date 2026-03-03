"""OrderFlowAnalyzer — VWAP, Volume Profile, Delta Divergence, Book Imbalance
from Nifty 50 futures tick data and order book depth."""

import math
import threading
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from app.core.logger_config import logger

# IST offset
_IST = timezone(timedelta(hours=5, minutes=30))


class OrderFlowAnalyzer:
    """Computes order flow metrics from futures tick data and order book depth.

    Thread-safe via threading.Lock (same pattern as FuturesVolumeTracker).

    Metrics:
        - VWAP with standard-deviation bands
        - Volume Profile with POC and Value Area
        - Delta Divergence (bearish / bullish)
        - Order Book Imbalance
    """

    def __init__(self, bin_size: float = 50.0, max_bins: int = 40):
        self._bin_size = bin_size
        self._max_bins = max_bins
        self._lock = threading.Lock()

        # --- VWAP accumulators ---
        self._cum_pv: float = 0.0       # sum(price * volume)
        self._cum_vol: float = 0.0      # sum(volume)
        self._cum_pv2: float = 0.0      # sum(volume * price^2)

        # --- Volume Profile ---
        # {bin_key: {"buy_vol": float, "sell_vol": float}}
        self._profile: Dict[float, Dict[str, float]] = {}

        # --- Order Book ---
        self._bid_total: float = 0.0
        self._ask_total: float = 0.0

        # --- Delta Divergence (8-candle lookback) ---
        self._candle_history: deque = deque(maxlen=8)

        # --- Daily reset tracking ---
        self._last_reset_date: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Tick processing
    # ------------------------------------------------------------------

    def on_tick(self, price: float, volume: float, direction: str, timestamp: float) -> None:
        """Process a single futures tick. Thread-safe.

        Args:
            price: trade price
            volume: trade quantity (contracts / lots)
            direction: "buy" or "sell"
            timestamp: epoch seconds
        """
        if volume <= 0:
            return

        with self._lock:
            # --- Daily auto-reset ---
            self._maybe_daily_reset(timestamp)

            # --- VWAP ---
            self._cum_pv += price * volume
            self._cum_vol += volume
            self._cum_pv2 += volume * price * price

            # --- Volume Profile ---
            bin_key = round(price / self._bin_size) * self._bin_size
            if bin_key not in self._profile:
                # Enforce max_bins cap
                if len(self._profile) >= self._max_bins:
                    return  # silently drop; profile is full
                self._profile[bin_key] = {"buy_vol": 0.0, "sell_vol": 0.0}

            if direction == "buy":
                self._profile[bin_key]["buy_vol"] += volume
            else:
                self._profile[bin_key]["sell_vol"] += volume

    # ------------------------------------------------------------------
    # Candle close (for divergence)
    # ------------------------------------------------------------------

    def on_candle_close(self, candle_close: float, cvd: float) -> None:
        """Record a candle close for divergence detection. Thread-safe."""
        with self._lock:
            self._candle_history.append({"close": candle_close, "cvd": cvd})

    # ------------------------------------------------------------------
    # Order Book
    # ------------------------------------------------------------------

    def update_order_book(self, bids: List[Tuple[float, float]],
                          asks: List[Tuple[float, float]]) -> None:
        """Update book imbalance from 5-level depth data. Thread-safe.

        Args:
            bids: list of (price, qty) best-bid levels
            asks: list of (price, qty) best-ask levels
        """
        with self._lock:
            self._bid_total = sum(qty for _, qty in bids) if bids else 0.0
            self._ask_total = sum(qty for _, qty in asks) if asks else 0.0

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def get_snapshot(self) -> Dict:
        """Return a serializable snapshot for the API. Thread-safe."""
        with self._lock:
            # --- VWAP ---
            if self._cum_vol > 0:
                vwap = self._cum_pv / self._cum_vol
                variance = self._cum_pv2 / self._cum_vol - vwap * vwap
                std_dev = math.sqrt(max(variance, 0.0))
            else:
                vwap = 0.0
                std_dev = 0.0

            vwap_upper = vwap + std_dev
            vwap_lower = vwap - std_dev

            # --- Volume Profile ---
            profile_list = self._build_profile_list()
            poc = self._compute_poc(profile_list)
            va_high, va_low = self._compute_value_area(profile_list, poc)

            # --- Book Imbalance ---
            total_book = self._bid_total + self._ask_total
            book_imbalance = (self._bid_total / total_book) if total_book > 0 else 0.5

            # --- Delta Divergence ---
            divergence = self._compute_divergence()

            return {
                "vwap": vwap,
                "vwap_upper": vwap_upper,
                "vwap_lower": vwap_lower,
                "std_dev": std_dev,
                "volume_profile": profile_list,
                "poc": poc,
                "value_area_high": va_high,
                "value_area_low": va_low,
                "book_imbalance": book_imbalance,
                "bid_total": self._bid_total,
                "ask_total": self._ask_total,
                "delta_divergence": divergence,
                "total_volume": self._cum_vol,
            }

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all state (e.g. at market open). Thread-safe."""
        with self._lock:
            self._cum_pv = 0.0
            self._cum_vol = 0.0
            self._cum_pv2 = 0.0
            self._profile = {}
            self._bid_total = 0.0
            self._ask_total = 0.0
            self._candle_history = deque(maxlen=8)
            self._last_reset_date = None

    # ------------------------------------------------------------------
    # Internal helpers (must be called under lock)
    # ------------------------------------------------------------------

    def _maybe_daily_reset(self, timestamp: float) -> None:
        """Reset accumulators if a new trading day has started (after 09:15 IST)."""
        dt = datetime.fromtimestamp(timestamp, tz=_IST)
        today = dt.date()

        if self._last_reset_date is None:
            self._last_reset_date = today
            return

        if today != self._last_reset_date and (dt.hour > 9 or (dt.hour == 9 and dt.minute >= 15)):
            logger.info("OrderFlowAnalyzer: daily reset triggered for %s", today)
            self._cum_pv = 0.0
            self._cum_vol = 0.0
            self._cum_pv2 = 0.0
            self._profile = {}
            self._candle_history = deque(maxlen=8)
            self._last_reset_date = today

    def _build_profile_list(self) -> List[Dict]:
        """Convert internal profile dict to sorted list of dicts."""
        result = []
        for price_key, vols in sorted(self._profile.items()):
            buy = vols["buy_vol"]
            sell = vols["sell_vol"]
            result.append({
                "price": price_key,
                "buy_vol": buy,
                "sell_vol": sell,
                "total": buy + sell,
            })
        return result

    @staticmethod
    def _compute_poc(profile_list: List[Dict]) -> float:
        """Return the price of the bin with highest total volume."""
        if not profile_list:
            return 0.0
        best = max(profile_list, key=lambda b: b["total"])
        return best["price"]

    @staticmethod
    def _compute_value_area(profile_list: List[Dict], poc: float) -> Tuple[float, float]:
        """Expand outward from POC until 70 % of total volume is enclosed."""
        if not profile_list:
            return (0.0, 0.0)

        total_vol = sum(b["total"] for b in profile_list)
        if total_vol <= 0:
            return (0.0, 0.0)

        target = total_vol * 0.70

        # Find POC index
        poc_idx = 0
        for i, b in enumerate(profile_list):
            if b["price"] == poc:
                poc_idx = i
                break

        included = total_vol * 0.0
        lo = poc_idx
        hi = poc_idx
        included = profile_list[poc_idx]["total"]

        while included < target:
            # Try expanding both sides; pick the one that adds more volume
            vol_below = profile_list[lo - 1]["total"] if lo > 0 else -1.0
            vol_above = profile_list[hi + 1]["total"] if hi < len(profile_list) - 1 else -1.0

            if vol_below < 0 and vol_above < 0:
                break  # nothing left

            if vol_below >= vol_above:
                lo -= 1
                included += profile_list[lo]["total"]
            else:
                hi += 1
                included += profile_list[hi]["total"]

        return (profile_list[hi]["price"], profile_list[lo]["price"])

    def _compute_divergence(self) -> Dict:
        """Detect price/CVD divergence from candle history."""
        bars = len(self._candle_history)
        if bars < 8:
            return {"active": False, "type": None, "strength": 0.0, "bars": bars}

        candles = list(self._candle_history)
        mid = bars // 2

        first_half = candles[:mid]
        second_half = candles[mid:]

        # Price trend: compare average of second half vs first half
        avg_price_first = sum(c["close"] for c in first_half) / len(first_half)
        avg_price_second = sum(c["close"] for c in second_half) / len(second_half)

        # CVD trend: same approach
        avg_cvd_first = sum(c["cvd"] for c in first_half) / len(first_half)
        avg_cvd_second = sum(c["cvd"] for c in second_half) / len(second_half)

        price_rising = avg_price_second > avg_price_first
        price_falling = avg_price_second < avg_price_first
        cvd_rising = avg_cvd_second > avg_cvd_first
        cvd_falling = avg_cvd_second < avg_cvd_first

        div_type = None
        if price_rising and cvd_falling:
            div_type = "bearish"
        elif price_falling and cvd_rising:
            div_type = "bullish"

        if div_type is None:
            return {"active": False, "type": None, "strength": 0.0, "bars": bars}

        # Strength: magnitude of divergence (0-1 clamped)
        price_range = abs(avg_price_second - avg_price_first)
        cvd_range = abs(avg_cvd_second - avg_cvd_first)
        if price_range == 0 or cvd_range == 0:
            strength = 0.0
        else:
            # Normalise by using the relative change magnitudes
            price_pct = price_range / max(abs(avg_price_first), 1e-9)
            cvd_pct = cvd_range / max(abs(avg_cvd_first), 1e-9)
            strength = min((price_pct + cvd_pct) / 2.0, 1.0)

        return {"active": True, "type": div_type, "strength": strength, "bars": bars}
