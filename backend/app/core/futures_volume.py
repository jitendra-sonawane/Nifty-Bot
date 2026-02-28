"""FuturesVolumeTracker — builds 1-min volume candles with buy/sell delta and CVD
from Nifty 50 futures tick data."""

import threading
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

from app.core.logger_config import logger

# IST offset
_IST = timezone(timedelta(hours=5, minutes=30))


class FuturesVolumeTracker:
    """Tracks futures volume ticks, builds 1-minute candles with buy/sell
    classification (uptick/downtick rule), and accumulates CVD."""

    def __init__(self, instrument_key: str = "", max_candles: int = 375):
        self.instrument_key = instrument_key
        self._max_candles = max_candles
        self._lock = threading.Lock()

        # Tick state
        self._prev_price: Optional[float] = None
        self._last_direction: str = "buy"
        self._futures_ltp: float = 0.0

        # Current candle being built
        self._current_candle: Optional[Dict] = None
        self._current_minute: Optional[int] = None

        # Completed candles
        self._candles: List[Dict] = []
        self._cvd: float = 0.0
        self._total_volume: float = 0.0

    def on_tick(self, price: float, volume: float, timestamp: float) -> None:
        """Process a single futures tick. Thread-safe."""
        with self._lock:
            self._futures_ltp = price

            # Determine buy/sell direction
            if self._prev_price is None:
                direction = "buy"
            elif price > self._prev_price:
                direction = "buy"
            elif price < self._prev_price:
                direction = "sell"
            else:
                direction = self._last_direction

            self._prev_price = price
            self._last_direction = direction

            # Determine which minute this tick belongs to
            minute_start = int(timestamp) // 60 * 60

            # If new minute or no candle yet, finalize previous and start new
            if self._current_minute is None or minute_start != self._current_minute:
                if self._current_candle is not None:
                    self._finalize_candle()

                dt = datetime.fromtimestamp(minute_start, tz=_IST)
                self._current_candle = {
                    "time": dt.strftime("%H:%M"),
                    "timestamp": minute_start,
                    "total_volume": 0.0,
                    "buy_volume": 0.0,
                    "sell_volume": 0.0,
                    "delta": 0.0,
                    "cvd": 0.0,
                }
                self._current_minute = minute_start

            # Accumulate into current candle
            self._current_candle["total_volume"] += volume
            self._total_volume += volume

            if direction == "buy":
                self._current_candle["buy_volume"] += volume
            else:
                self._current_candle["sell_volume"] += volume

            self._current_candle["delta"] = (
                self._current_candle["buy_volume"] - self._current_candle["sell_volume"]
            )
            self._current_candle["cvd"] = self._cvd + self._current_candle["delta"]

    def _finalize_candle(self) -> None:
        """Move the current candle to the completed list. Must be called under lock."""
        if self._current_candle is None:
            return

        self._cvd += self._current_candle["delta"]
        self._current_candle["cvd"] = self._cvd

        self._candles.append(self._current_candle)

        if len(self._candles) > self._max_candles:
            self._candles = self._candles[-self._max_candles:]

        self._current_candle = None

    def get_snapshot(self) -> Dict:
        """Return a serializable snapshot for the status API. Thread-safe."""
        with self._lock:
            candles = list(self._candles)
            if self._current_candle is not None:
                candles.append(self._current_candle)

            # Respect rolling window limit
            if len(candles) > self._max_candles:
                candles = candles[-self._max_candles:]

            current_cvd = self._cvd
            current_delta = 0.0
            if self._current_candle is not None:
                current_cvd = self._current_candle["cvd"]
                current_delta = self._current_candle["delta"]

            return {
                "instrument_key": self.instrument_key,
                "futures_ltp": self._futures_ltp,
                "candles": candles,
                "current_cvd": current_cvd,
                "current_delta": current_delta,
                "total_volume": self._total_volume,
            }

    def reset(self) -> None:
        """Reset all state (e.g. at market open). Thread-safe."""
        with self._lock:
            self._prev_price = None
            self._last_direction = "buy"
            self._futures_ltp = 0.0
            self._current_candle = None
            self._current_minute = None
            self._candles = []
            self._cvd = 0.0
            self._total_volume = 0.0
