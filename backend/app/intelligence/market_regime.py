"""
Market Regime Classifier — determines whether the market is trending,
ranging, or in a high-volatility event state.

Inputs (via update):
    data['df'] — pandas DataFrame with OHLCV columns

Outputs (via get_context):
    regime          : "TRENDING" | "RANGING" | "HIGH_VOLATILITY"
    adx             : 0-100 trend strength (ADX)
    bb_width_pct    : Bollinger Band width as % of price
    atr_pct         : ATR as % of price (volatility proxy)
    allowed_strategies : list of strategy types suitable for this regime
    regime_confidence  : 0-100 confidence score

Strategy recommendations per regime:
    TRENDING       → use Breakout, Bull/Bear Spreads only
    RANGING        → use Iron Condor, Short Straddle (premium selling)
    HIGH_VOLATILITY → only defined-risk debit spreads; no naked selling
"""

import logging
from collections import deque
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from app.intelligence.base import IntelligenceModule

logger = logging.getLogger(__name__)


class MarketRegimeModule(IntelligenceModule):
    name = "market_regime"

    # ADX thresholds
    ADX_TRENDING = 25       # ADX > 25 → trending
    ADX_WEAK     = 20       # ADX < 20 → ranging

    # Bollinger Band width thresholds (% of price)
    BB_SQUEEZE   = 1.5      # Band width < 1.5% → ranging / squeeze
    BB_EXPANSION = 3.0      # Band width > 3.0% → trending / volatile

    # ATR thresholds (% of price)
    ATR_HIGH_VOL = 1.2      # ATR% > 1.2% → high volatility regime

    # Min candles needed before regime output is valid
    MIN_CANDLES = 30

    # Strategy sets per regime
    REGIME_STRATEGIES = {
        "TRENDING":        ["breakout", "bull_call_spread", "bear_put_spread"],
        "RANGING":         ["iron_condor", "short_straddle", "bull_call_spread", "bear_put_spread"],
        "HIGH_VOLATILITY": ["bull_call_spread", "bear_put_spread"],
    }

    def __init__(self, adx_period: int = 14, bb_period: int = 20, atr_period: int = 14):
        self._adx_period = adx_period
        self._bb_period = bb_period
        self._atr_period = atr_period

        self._regime: str = "RANGING"          # safe default
        self._adx: Optional[float] = None
        self._bb_width_pct: Optional[float] = None
        self._atr_pct: Optional[float] = None
        self._confidence: int = 0

    # ── IntelligenceModule interface ────────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        df: Optional[pd.DataFrame] = data.get("df")
        if df is None or len(df) < self.MIN_CANDLES:
            return

        try:
            self._adx = self._calculate_adx(df, self._adx_period)
            self._bb_width_pct = self._calculate_bb_width(df, self._bb_period)
            self._atr_pct = self._calculate_atr_pct(df, self._atr_period)
            self._regime, self._confidence = self._classify()
        except Exception as e:
            logger.error(f"MarketRegimeModule update error: {e}")

    def get_context(self) -> Dict[str, Any]:
        return {
            "regime":             self._regime,
            "adx":                round(self._adx, 2) if self._adx is not None else None,
            "bb_width_pct":       round(self._bb_width_pct, 3) if self._bb_width_pct is not None else None,
            "atr_pct":            round(self._atr_pct, 3) if self._atr_pct is not None else None,
            "regime_confidence":  self._confidence,
            "allowed_strategies": self.REGIME_STRATEGIES.get(self._regime, []),
            "is_trending":        self._regime == "TRENDING",
            "is_ranging":         self._regime == "RANGING",
            "is_high_volatility": self._regime == "HIGH_VOLATILITY",
        }

    def reset(self) -> None:
        pass  # Regime is stateless across days

    # ── Private helpers ─────────────────────────────────────────────────────

    def _classify(self):
        """Classify regime from ADX, BB width, ATR."""
        adx = self._adx or 0.0
        bb_w = self._bb_width_pct or 0.0
        atr_p = self._atr_pct or 0.0

        # High volatility overrides everything
        if atr_p > self.ATR_HIGH_VOL:
            confidence = min(100, int((atr_p / self.ATR_HIGH_VOL) * 60))
            return "HIGH_VOLATILITY", confidence

        # Trending: strong ADX + widening bands
        if adx >= self.ADX_TRENDING and bb_w >= self.BB_EXPANSION:
            confidence = min(100, int(((adx - self.ADX_TRENDING) / 30) * 50) + 50)
            return "TRENDING", confidence

        # Also trending if ADX alone is very strong
        if adx >= 30:
            return "TRENDING", min(100, int((adx / 50) * 80))

        # Ranging: weak ADX + tight bands (Bollinger Squeeze)
        if adx < self.ADX_WEAK or bb_w < self.BB_SQUEEZE:
            confidence = min(100, int(((self.ADX_WEAK - adx) / self.ADX_WEAK) * 60) + 40)
            return "RANGING", confidence

        # Default: mild trending
        if adx >= self.ADX_WEAK:
            return "TRENDING", 50

        return "RANGING", 50

    @staticmethod
    def _calculate_adx(df: pd.DataFrame, period: int) -> float:
        """Wilder's ADX."""
        high  = df["high"].astype(float)
        low   = df["low"].astype(float)
        close = df["close"].astype(float)

        plus_dm  = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        # Where the other DM is larger, zero out
        plus_dm  = plus_dm.where(plus_dm > minus_dm, 0)
        minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

        tr = pd.concat([high - low,
                        (high - close.shift()).abs(),
                        (low  - close.shift()).abs()], axis=1).max(axis=1)

        atr14  = tr.ewm(alpha=1/period, adjust=False).mean()
        pdi    = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr14
        mdi    = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr14
        dx     = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)).fillna(0)
        adx    = dx.ewm(alpha=1/period, adjust=False).mean()
        return float(adx.iloc[-1])

    @staticmethod
    def _calculate_bb_width(df: pd.DataFrame, period: int) -> float:
        """Bollinger Band width as % of midline (normalised volatility)."""
        close = df["close"].astype(float)
        sma   = close.rolling(period).mean()
        std   = close.rolling(period).std()
        upper = sma + 2 * std
        lower = sma - 2 * std
        width_pct = ((upper - lower) / sma * 100).iloc[-1]
        return float(width_pct) if not np.isnan(width_pct) else 0.0

    @staticmethod
    def _calculate_atr_pct(df: pd.DataFrame, period: int) -> float:
        """ATR as % of current price."""
        high  = df["high"].astype(float)
        low   = df["low"].astype(float)
        close = df["close"].astype(float)
        tr    = pd.concat([high - low,
                           (high - close.shift()).abs(),
                           (low  - close.shift()).abs()], axis=1).max(axis=1)
        atr   = tr.rolling(period).mean().iloc[-1]
        price = close.iloc[-1]
        return float(atr / price * 100) if price > 0 else 0.0
