"""
StrategyEngine — core signal generation with pluggable intelligence filters.

check_signal() accepts an optional `intelligence_context` dict produced by
IntelligenceEngine.get_context().  When present, three additional filters are
evaluated:

    market_regime   — gate credit strategies in trending/high-vol regimes
    iv_rank         — require IV Rank ≥ 40 for premium-selling strategies
    market_breadth  — use A/D breadth as confluence confirmation
    order_book      — check entry quality / liquidity before firing

All intelligence filters degrade gracefully: if context is None or the module
key is missing, the filter defaults to PASS so that legacy behaviour is preserved.
"""

import datetime
import pandas as pd
import numpy as np
from typing import Any, Dict, Optional


class StrategyEngine:
    def __init__(self):
        pass

    # ── Technical Indicators ────────────────────────────────────────────────

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain  = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs    = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_ema(self, series, period):
        return series.ewm(span=period, adjust=False).mean()

    def calculate_macd(self, series, fast=12, slow=26, signal=9):
        exp1        = series.ewm(span=fast,   adjust=False).mean()
        exp2        = series.ewm(span=slow,   adjust=False).mean()
        macd        = exp1 - exp2
        signal_line = macd.ewm(span=signal,   adjust=False).mean()
        return macd, signal_line

    def calculate_bollinger_bands(self, series, period=20, std_dev=2):
        sma        = series.rolling(window=period).mean()
        std        = series.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, lower_band

    def calculate_supertrend(self, df, period=7, multiplier=3):
        high  = df['high']
        low   = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low  - close.shift(1))
        tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        hl2              = (high + low) / 2
        basic_upperband  = hl2 + (multiplier * atr)
        basic_lowerband  = hl2 - (multiplier * atr)

        final_upperband  = basic_upperband.copy()
        final_lowerband  = basic_lowerband.copy()
        supertrend       = [True] * len(df)

        for i in range(1, len(df.index)):
            curr, prev = i, i - 1
            if pd.isna(atr.iloc[curr]):
                continue

            if pd.isna(final_upperband.iloc[prev]):
                final_upperband.iloc[curr] = basic_upperband.iloc[curr]
            elif basic_upperband.iloc[curr] < final_upperband.iloc[prev] or close.iloc[prev] > final_upperband.iloc[prev]:
                final_upperband.iloc[curr] = basic_upperband.iloc[curr]
            else:
                final_upperband.iloc[curr] = final_upperband.iloc[prev]

            if pd.isna(final_lowerband.iloc[prev]):
                final_lowerband.iloc[curr] = basic_lowerband.iloc[curr]
            elif basic_lowerband.iloc[curr] > final_lowerband.iloc[prev] or close.iloc[prev] < final_lowerband.iloc[prev]:
                final_lowerband.iloc[curr] = basic_lowerband.iloc[curr]
            else:
                final_lowerband.iloc[curr] = final_lowerband.iloc[prev]

            if supertrend[prev]:
                supertrend[curr] = False if close.iloc[curr] <= final_lowerband.iloc[prev] else True
            else:
                supertrend[curr] = True  if close.iloc[curr] >= final_upperband.iloc[prev] else False

        return pd.Series(supertrend, index=df.index), final_upperband, final_lowerband

    def calculate_support_resistance(self, df, window=20):
        high          = df['high']
        low           = df['low']
        close         = df['close']
        current_price = close.iloc[-1]

        support_levels    = []
        resistance_levels = []
        lookback          = min(100, len(df))
        recent_high       = high.iloc[-lookback:]
        recent_low        = low.iloc[-lookback:]

        for i in range(1, len(recent_high) - 1):
            if recent_high.iloc[i] > recent_high.iloc[i-1] and recent_high.iloc[i] > recent_high.iloc[i+1]:
                resistance_levels.append(round(recent_high.iloc[i], 2))
            if recent_low.iloc[i] < recent_low.iloc[i-1] and recent_low.iloc[i] < recent_low.iloc[i+1]:
                support_levels.append(round(recent_low.iloc[i], 2))

        max_high = high.iloc[-lookback:].max()
        min_low  = low.iloc[-lookback:].min()
        resistance_levels = sorted(list(set(resistance_levels + [round(max_high, 2)])), reverse=True)
        support_levels    = sorted(list(set(support_levels    + [round(min_low,  2)])), reverse=True)

        supports_below    = [s for s in support_levels    if s < current_price]
        resistances_above = [r for r in resistance_levels if r > current_price]
        nearest_support    = max(supports_below)    if supports_below    else None
        nearest_resistance = min(resistances_above) if resistances_above else None

        support_distance    = round(((current_price - nearest_support)    / current_price) * 100, 2) if nearest_support    else None
        resistance_distance = round(((nearest_resistance - current_price) / current_price) * 100, 2) if nearest_resistance else None

        return {
            'support_levels':          support_levels[:5],
            'resistance_levels':       resistance_levels[:5],
            'nearest_support':         nearest_support,
            'nearest_resistance':      nearest_resistance,
            'support_distance_pct':    support_distance,
            'resistance_distance_pct': resistance_distance,
            'current_price':           round(current_price, 2),
        }

    def detect_breakout(self, df, sensitivity=0.015):
        no_breakout = {'is_breakout': False, 'breakout_type': None, 'breakout_level': None, 'strength': 0}
        lookback    = 50
        if len(df) < lookback + 2:
            return no_breakout

        close         = df['close']
        high          = df['high']
        low           = df['low']
        current_price = close.iloc[-1]
        prev_close    = close.iloc[-2]

        ref_high        = high.iloc[-lookback - 2:-2]
        ref_low         = low.iloc[ -lookback - 2:-2]
        highest_high    = ref_high.max()
        lowest_low      = ref_low.min()

        threshold_up   = highest_high * (1 + sensitivity)
        threshold_down = lowest_low   * (1 - sensitivity)

        if current_price > threshold_up and prev_close > highest_high:
            return {'is_breakout': True,  'breakout_type': 'UPSIDE',
                    'breakout_level': round(highest_high, 2),
                    'strength': round(((current_price - highest_high) / highest_high) * 100, 2)}

        if current_price < threshold_down and prev_close < lowest_low:
            return {'is_breakout': True,  'breakout_type': 'DOWNSIDE',
                    'breakout_level': round(lowest_low, 2),
                    'strength': round(((lowest_low - current_price) / lowest_low) * 100, 2)}

        return no_breakout

    def calculate_atr(self, df, period=14):
        high  = df['high']
        low   = df['low']
        close = df['close']
        tr    = pd.concat([high - low,
                           (high - close.shift(1)).abs(),
                           (low  - close.shift(1)).abs()], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def calculate_avg_volume(self, df, period=20):
        return df['volume'].rolling(window=period).mean()

    def get_supertrend_strength(self, df):
        _, upperband, lowerband = self.calculate_supertrend(df)
        current_price = df['close'].iloc[-1]
        return {
            'band_width':    upperband.iloc[-1] - lowerband.iloc[-1],
            'dist_to_upper': abs(current_price - upperband.iloc[-1]),
            'dist_to_lower': abs(current_price - lowerband.iloc[-1]),
        }

    # ── Intelligence Filter Helpers ─────────────────────────────────────────

    @staticmethod
    def _check_regime_filter(intel: Dict, signal_direction: str) -> tuple[bool, str]:
        """
        Gate trades based on market regime.
        Returns (passes: bool, reason: str)
        """
        regime_ctx = intel.get("market_regime", {})
        if not regime_ctx:
            return True, ""

        regime = regime_ctx.get("regime", "RANGING")
        allowed = regime_ctx.get("allowed_strategies", [])

        # Map signal direction to strategy category
        if signal_direction == "BUY_CE":
            needed_strategies = {"breakout", "bull_call_spread", "iron_condor", "short_straddle"}
        else:
            needed_strategies = {"breakout", "bear_put_spread", "iron_condor", "short_straddle"}

        if regime == "HIGH_VOLATILITY":
            # Only debit spreads allowed — no naked directional entries with index options
            return False, f"Regime=HIGH_VOL (ADX:{regime_ctx.get('adx','-')})"

        if regime == "TRENDING":
            # In trending regime, credit strategies (condor/straddle) are blocked
            # but directional entries are fine
            return True, f"Regime=TRENDING✓"

        return True, f"Regime=RANGING✓"

    @staticmethod
    def _check_iv_rank_filter(intel: Dict) -> tuple[bool, str]:
        """
        Block premium-selling strategies when IV Rank is too low.
        Allow all strategies when IV Rank data is not yet available.
        """
        iv_ctx = intel.get("iv_rank", {})
        if not iv_ctx:
            return True, ""

        iv_rank = iv_ctx.get("iv_rank")
        if iv_rank is None:
            return True, ""  # Not enough history yet — pass

        rec = iv_ctx.get("recommendation", "NEUTRAL")
        # Block entry if IV is extremely cheap (rank < 20) — premium too thin
        if iv_rank < 20:
            return False, f"IV_Rank={iv_rank:.0f}<20 (IV cheap, poor premium)"

        return True, f"IV_Rank={iv_rank:.0f}✓"

    @staticmethod
    def _check_breadth_filter(intel: Dict, signal_direction: str) -> tuple[bool, str]:
        """
        Use market breadth as soft confirmation.
        Only blocks when breadth strongly contradicts the signal direction.
        """
        breadth_ctx = intel.get("market_breadth", {})
        if not breadth_ctx or breadth_ctx.get("coverage", 0) < 10:
            return True, ""

        bias = breadth_ctx.get("breadth_bias", "NEUTRAL")

        # Only hard-block on strong contradiction
        if signal_direction == "BUY_CE" and bias == "STRONG_BEARISH":
            adv = breadth_ctx.get("advancing", "?")
            return False, f"Breadth=STRONG_BEARISH ({adv}/50 advancing)"

        if signal_direction == "BUY_PE" and bias == "STRONG_BULLISH":
            adv = breadth_ctx.get("advancing", "?")
            return False, f"Breadth=STRONG_BULLISH ({adv}/50 advancing)"

        return True, f"Breadth={bias}✓"

    @staticmethod
    def _check_order_book_filter(intel: Dict, signal_direction: str) -> tuple[bool, str]:
        """
        Block entry if option liquidity is POOR (spread > 1%).
        """
        ob_ctx = intel.get("order_book", {})
        if not ob_ctx:
            return True, ""

        if signal_direction == "BUY_CE":
            liq = ob_ctx.get("ce_liquidity", "UNKNOWN")
            spread = ob_ctx.get("ce_spread_pct")
        else:
            liq = ob_ctx.get("pe_liquidity", "UNKNOWN")
            spread = ob_ctx.get("pe_spread_pct")

        if liq == "POOR":
            return False, f"Liquidity=POOR (spread={spread:.2f}%)" if spread else "Liquidity=POOR"

        return True, f"Liquidity={liq}✓"

    @staticmethod
    def _check_vix_filter(vix: Optional[float], signal_direction: str) -> tuple[bool, str]:
        """
        Gate trades based on India VIX (fear index).

        VIX > 20: Block all entries — panic/gap risk too high.
        VIX 18-20: Allow debit strategies only (no premium selling).
        VIX < 18: Normal trading conditions.
        """
        if vix is None:
            return True, ""
        if vix > 20:
            return False, f"VIX={vix:.1f}>20 (high fear, gap risk)"
        if vix > 18:
            # Allow debit (BUY_CE/BUY_PE) but flag elevated risk
            return True, f"VIX={vix:.1f} elevated (monitor)"
        return True, f"VIX={vix:.1f}✓"

    @staticmethod
    def _check_pcr_trend_filter(pcr: Optional[float], pcr_trend: Optional[str],
                                 signal_direction: str) -> tuple[bool, str]:
        """
        Use PCR trend (direction of change) as stronger confluence than absolute value.

        A rising PCR with BUY_CE confirms bullish setup (more puts = support).
        A falling PCR with BUY_PE confirms bearish setup (fewer puts = less support).
        Divergence (PCR contradicts signal) reduces confidence but does not hard-block.
        """
        if pcr is None or pcr_trend is None:
            return True, ""

        if signal_direction == "BUY_CE":
            # Bullish signal: PCR should be ≥1.0 (protective puts) and rising or stable
            if pcr < 0.8:
                return False, f"PCR={pcr:.2f}<0.8 divergence (too many calls vs puts)"
            trend_label = {"INCREASING": "rising✓", "DECREASING": "falling⚠", "STABLE": "stable✓"}.get(pcr_trend, pcr_trend)
            return True, f"PCR={pcr:.2f}({trend_label})"

        if signal_direction == "BUY_PE":
            # Bearish signal: PCR should be <1.0 and falling
            if pcr > 1.3:
                return False, f"PCR={pcr:.2f}>1.3 divergence (heavy put buying contradicts short)"
            trend_label = {"INCREASING": "rising⚠", "DECREASING": "falling✓", "STABLE": "stable✓"}.get(pcr_trend, pcr_trend)
            return True, f"PCR={pcr:.2f}({trend_label})"

        return True, ""

    @staticmethod
    def _check_time_of_day_filter(current_time: Optional[datetime.datetime],
                                   signal_direction: str) -> tuple[bool, str]:
        """
        Gate entries by time-of-day to avoid low-quality signal windows.

        09:15–09:45: Opening volatility — price discovery, avoid entries.
        09:45–10:30: Settling period — allow with confirmation.
        10:30–14:30: Prime window — best signal quality.
        14:30–15:00: Pre-close — allow but flag.
        15:00–15:30: Last 30 min — avoid (expiry gamma, thin book).
        """
        if current_time is None:
            return True, ""

        h, m = current_time.hour, current_time.minute
        minutes_from_open = (h - 9) * 60 + m - 15  # mins since 09:15

        if minutes_from_open < 30:  # before 09:45
            return False, f"TimeFilter=OpeningVolatility({current_time.strftime('%H:%M')})"

        if h >= 15 and m >= 0:  # after 15:00
            return False, f"TimeFilter=PreClose({current_time.strftime('%H:%M')})"

        if h >= 14 and m >= 30:  # 14:30–15:00
            return True, f"Time={current_time.strftime('%H:%M')} pre-close⚠"

        return True, f"Time={current_time.strftime('%H:%M')}✓"

    @staticmethod
    def _check_oi_buildup_filter(intel: Dict, signal_direction: str) -> tuple[bool, str]:
        """
        Gate trades based on OI buildup/unwinding analysis.

        LONG_BUILDUP (Price↑ OI↑) contradicts BUY_PE → block PE.
        SHORT_BUILDUP (Price↓ OI↑) contradicts BUY_CE → block CE.
        SHORT_COVERING / LONG_UNWINDING are weak signals → allow with warning.
        """
        oi_ctx = intel.get("oi_analysis", {})
        if not oi_ctx or oi_ctx.get("snapshots_count", 0) < 5:
            return True, ""  # Not enough data yet

        buildup = oi_ctx.get("buildup_signal", "NEUTRAL")
        oi_change = oi_ctx.get("oi_change_pct", 0)

        if buildup == "NEUTRAL":
            return True, f"OI=Neutral({oi_change:+.1f}%)"

        if signal_direction == "BUY_CE":
            if buildup == "SHORT_BUILDUP":
                return False, f"OI=ShortBuildup({oi_change:+.1f}%) contradicts CE"
            if buildup == "LONG_UNWINDING":
                return True, f"OI=LongUnwinding({oi_change:+.1f}%)⚠"
            if buildup == "LONG_BUILDUP":
                return True, f"OI=LongBuildup({oi_change:+.1f}%)✓"
            return True, f"OI=ShortCovering({oi_change:+.1f}%)"

        if signal_direction == "BUY_PE":
            if buildup == "LONG_BUILDUP":
                return False, f"OI=LongBuildup({oi_change:+.1f}%) contradicts PE"
            if buildup == "SHORT_COVERING":
                return True, f"OI=ShortCovering({oi_change:+.1f}%)⚠"
            if buildup == "SHORT_BUILDUP":
                return True, f"OI=ShortBuildup({oi_change:+.1f}%)✓"
            return True, f"OI=LongUnwinding({oi_change:+.1f}%)"

        return True, ""

    @staticmethod
    def _is_expiry_day(greeks: Optional[Dict], current_time: Optional[datetime.datetime]) -> bool:
        """Check if today is the expiry day based on greeks expiry_date."""
        if not greeks or not current_time:
            return False
        expiry_str = greeks.get("expiry_date")
        if not expiry_str:
            return False
        try:
            expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
            return current_time.date() == expiry_date
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _check_expiry_day_filter(greeks: Optional[Dict], current_time: Optional[datetime.datetime],
                                  signal_direction: str) -> tuple[bool, str]:
        """
        Gate trades on expiry day (0DTE).

        - After 14:00 on expiry day → block all entries (gamma explosion risk).
        - Before 14:00 on expiry day → allow with warning.
        - Not expiry day → pass.
        """
        if not greeks or not current_time:
            return True, ""

        expiry_str = greeks.get("expiry_date")
        if not expiry_str:
            return True, ""

        try:
            expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return True, ""

        if current_time.date() != expiry_date:
            return True, "NotExpiryDay✓"

        # It's expiry day
        from app.core.config import Config
        block_after = Config.EXPIRY_DAY.get("block_new_entries_after", "14:00")
        block_h, block_m = map(int, block_after.split(":"))

        if current_time.hour > block_h or (current_time.hour == block_h and current_time.minute >= block_m):
            return False, f"0DTE: blocked after {block_after} (gamma risk)"

        return True, "0DTE: tightened SL, reduced size⚠"

    # ── Main Signal Method ──────────────────────────────────────────────────

    def check_signal(
        self,
        df: pd.DataFrame,
        pcr=None,
        greeks=None,
        backtest_mode: bool = False,
        intelligence_context: Optional[Dict[str, Any]] = None,
        vix: Optional[float] = None,
        pcr_trend: Optional[str] = None,
        current_time: Optional[datetime.datetime] = None,
        pdh_pdl_pdc: Optional[Dict[str, float]] = None,
    ):
        """
        Signal generation with 9 base confluence filters + up to 10 intelligence filters.

        Parameters:
            df                   : OHLCV DataFrame
            pcr                  : Put-Call Ratio (current)
            pcr_trend            : PCR trend direction ('INCREASING'/'DECREASING'/'STABLE')
            greeks               : Greeks dict from MarketDataManager
            backtest_mode        : Skip real-time filters
            intelligence_context : Output of IntelligenceEngine.get_context() (optional)
            vix                  : India VIX value (optional)
            current_time         : Current datetime for time-of-day gating (optional)
            pdh_pdl_pdc          : Previous day High/Low/Close levels (optional)

        Returns:
            dict with signal, filters, progress, indicators  |  "WAITING_DATA"
        """
        if df is None or df.empty or len(df) < 50:
            return "WAITING_DATA"

        intel = intelligence_context or {}

        for col in ['close', 'high', 'low', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col])

        close = df['close']

        # ── Calculate indicators ────────────────────────────────────────────
        if 'rsi' not in df.columns:
            df['rsi'] = self.calculate_rsi(close)
        if 'supertrend' not in df.columns:
            df['supertrend'], _, _ = self.calculate_supertrend(df)
        if 'ema_5' not in df.columns:
            df['ema_5'] = self.calculate_ema(close, 5)
        if 'ema_20' not in df.columns:
            df['ema_20'] = self.calculate_ema(close, 20)
        current_price = close.iloc[-1]
        rsi           = df['rsi'].iloc[-1]
        supertrend    = df['supertrend'].iloc[-1]
        ema_5         = df['ema_5'].iloc[-1]
        ema_20        = df['ema_20'].iloc[-1]

        atr            = self.calculate_atr(df)
        avg_volume     = self.calculate_avg_volume(df)
        current_volume = df['volume'].iloc[-1]
        current_atr    = atr.iloc[-1]
        current_avg_vol = avg_volume.iloc[-1]

        if pd.isna(current_avg_vol) or current_avg_vol == 0:
            current_avg_vol = current_volume
        if pd.isna(current_atr):
            current_atr = 0.0

        last_2_supertrend    = df['supertrend'].iloc[-2:].values
        supertrend_confirmed = (last_2_supertrend[-1] == last_2_supertrend[-2])

        support_resistance = self.calculate_support_resistance(df)
        breakout_data      = self.detect_breakout(df)

        # ── Base filter checks ──────────────────────────────────────────────
        filter_checks = {
            'supertrend':        False,
            'ema_crossover':     False,
            'rsi':               False,
            'volume':            True,   # Disabled for index
            'volatility':        False,
            'pcr':               False,
            'greeks':            False,
            'entry_confirmation':False,
            # Intelligence filters (default PASS)
            'market_regime':     True,
            'iv_rank':           True,
            'market_breadth':    True,
            'order_book':        True,
            'vix':               True,
            'pcr_trend':         True,
            'time_of_day':       True,
            'oi_buildup':        True,
            'expiry_day':        True,
        }

        # 1. Supertrend (evaluated in final decision)
        filter_checks['supertrend'] = True

        # 2. EMA crossover
        ema_bullish = ema_bearish = False
        if len(df) >= 2:
            prev_ema_5  = df['ema_5'].iloc[-2]
            prev_ema_20 = df['ema_20'].iloc[-2]
            if pd.notna(prev_ema_5) and pd.notna(prev_ema_20) and pd.notna(ema_5) and pd.notna(ema_20):
                ema_bullish = (prev_ema_5 <= prev_ema_20) and (ema_5 > ema_20)
                ema_bearish = (prev_ema_5 >= prev_ema_20) and (ema_5 < ema_20)
            else:
                ema_bullish = ema_5 > ema_20
                ema_bearish = ema_5 < ema_20
        else:
            ema_bullish = ema_5 > ema_20
            ema_bearish = ema_5 < ema_20
        filter_checks['ema_crossover'] = ema_bullish or ema_bearish

        # 3. RSI
        bullish_rsi = rsi > 55
        bearish_rsi = rsi < 45
        filter_checks['rsi'] = bullish_rsi or bearish_rsi

        # 4. Volatility
        atr_range    = current_atr / current_price * 100
        volatility_ok = 0.01 < atr_range < 2.5
        filter_checks['volatility'] = volatility_ok

        # 5. Entry confirmation
        filter_checks['entry_confirmation'] = supertrend_confirmed

        # 6. PCR
        pcr_bullish = pcr_bearish = True
        if not backtest_mode and pcr:
            pcr_bullish = pcr >= 1.0
            pcr_bearish = pcr <  1.0
            filter_checks['pcr'] = pcr_bullish or pcr_bearish
        else:
            filter_checks['pcr'] = True

        # 7. Greeks quality
        greeks_bullish = greeks_bearish = True
        if not backtest_mode and greeks:
            ce_quality = greeks.get('ce', {}).get('quality_score', 0)
            pe_quality = greeks.get('pe', {}).get('quality_score', 0)
            greeks_bullish = ce_quality >= 50
            greeks_bearish = pe_quality >= 50
            filter_checks['greeks'] = greeks_bullish or greeks_bearish
        else:
            filter_checks['greeks'] = True

        # ── Intelligence filters (only evaluated if context provided) ───────
        intelligence_filter_reasons: Dict[str, str] = {}

        if not backtest_mode:
            # Evaluate against both candidate directions and store per-direction results
            for direction in ("BUY_CE", "BUY_PE"):
                passes_regime,   r_regime  = self._check_regime_filter(intel, direction) if intel else (True, "")
                passes_iv,       r_iv      = self._check_iv_rank_filter(intel) if intel else (True, "")
                passes_breadth,  r_breadth = self._check_breadth_filter(intel, direction) if intel else (True, "")
                passes_ob,       r_ob      = self._check_order_book_filter(intel, direction) if intel else (True, "")
                passes_vix,      r_vix     = self._check_vix_filter(vix, direction)
                passes_pcr_trend, r_pcr_tr = self._check_pcr_trend_filter(pcr, pcr_trend, direction)
                passes_tod,      r_tod     = self._check_time_of_day_filter(current_time, direction)
                passes_oi,       r_oi      = self._check_oi_buildup_filter(intel, direction) if intel else (True, "")
                passes_expiry,   r_expiry  = self._check_expiry_day_filter(greeks, current_time, direction)

                intelligence_filter_reasons[direction] = {
                    "market_regime":  (passes_regime,    r_regime),
                    "iv_rank":        (passes_iv,         r_iv),
                    "market_breadth": (passes_breadth,    r_breadth),
                    "order_book":     (passes_ob,         r_ob),
                    "vix":            (passes_vix,        r_vix),
                    "pcr_trend":      (passes_pcr_trend,  r_pcr_tr),
                    "time_of_day":    (passes_tod,        r_tod),
                    "oi_buildup":     (passes_oi,         r_oi),
                    "expiry_day":     (passes_expiry,     r_expiry),
                }

        def intel_pass(direction: str) -> bool:
            """Return True if all intelligence filters pass for this direction."""
            if not intelligence_filter_reasons:
                return True
            results = intelligence_filter_reasons.get(direction, {})
            return all(ok for ok, _ in results.values())

        def intel_fail_reason(direction: str) -> str:
            """Collect reason strings for failed filters."""
            if not intelligence_filter_reasons:
                return ""
            results = intelligence_filter_reasons.get(direction, {})
            failed  = [reason for ok, reason in results.values() if not ok and reason]
            return " | ".join(failed)

        # Populate aggregate filter booleans for frontend display
        if not backtest_mode and intelligence_filter_reasons:
            ce_intel_ok = intel_pass("BUY_CE")
            pe_intel_ok = intel_pass("BUY_PE")
            filter_checks['market_regime']  = ce_intel_ok or pe_intel_ok
            filter_checks['iv_rank']        = ce_intel_ok or pe_intel_ok
            filter_checks['market_breadth'] = ce_intel_ok or pe_intel_ok
            filter_checks['order_book']     = ce_intel_ok or pe_intel_ok
            # Per-filter display for new gates
            def _filter_ok(key: str) -> bool:
                ce = intelligence_filter_reasons.get("BUY_CE", {}).get(key, (True, ""))[0]
                pe = intelligence_filter_reasons.get("BUY_PE", {}).get(key, (True, ""))[0]
                return ce or pe
            filter_checks['vix']         = _filter_ok('vix')
            filter_checks['pcr_trend']   = _filter_ok('pcr_trend')
            filter_checks['time_of_day'] = _filter_ok('time_of_day')
            filter_checks['oi_buildup']  = _filter_ok('oi_buildup')
            filter_checks['expiry_day']  = _filter_ok('expiry_day')

        # ── Final decision ──────────────────────────────────────────────────
        signal = "HOLD"
        decision_reason = "HOLD"

        ce_base_ok = (supertrend and bullish_rsi and (ema_bullish or ema_5 > ema_20) and
                      filter_checks['volume'] and
                      volatility_ok and supertrend_confirmed and pcr_bullish and greeks_bullish)

        pe_base_ok = (not supertrend and bearish_rsi and (ema_bearish or ema_5 < ema_20) and
                      filter_checks['volume'] and
                      volatility_ok and supertrend_confirmed and pcr_bearish and greeks_bearish)

        # PDH/PDL/PDC confluence (soft — adds to reason, does not block)
        pdh_pdl_note = ""
        if pdh_pdl_pdc and current_price:
            pdh = pdh_pdl_pdc.get("pdh")
            pdl = pdh_pdl_pdc.get("pdl")
            if pdh and current_price > pdh:
                pdh_pdl_note = f" | Above PDH({pdh:.0f})"
            elif pdl and current_price < pdl:
                pdh_pdl_note = f" | Below PDL({pdl:.0f})"

        if ce_base_ok and intel_pass("BUY_CE"):
            signal = "BUY_CE"
            decision_reason = (
                f"🟢 BUY_CE: ST↑ EMA↑({ema_5:.0f}>{ema_20:.0f}) "
                f"RSI({rsi:.1f})>55 ATR✓ Confirmed{pdh_pdl_note}"
            )
        elif pe_base_ok and intel_pass("BUY_PE"):
            signal = "BUY_PE"
            decision_reason = (
                f"🔴 BUY_PE: ST↓ EMA↓({ema_5:.0f}<{ema_20:.0f}) "
                f"RSI({rsi:.1f})<45 ATR✓ Confirmed{pdh_pdl_note}"
            )
        else:
            # Build HOLD reason
            reasons = []
            if not supertrend:       reasons.append("ST↓")
            else:                    reasons.append("ST↑")
            reasons.append(f"RSI{rsi:.0f}")
            if not (ema_bullish or ema_bearish): reasons.append("EMA✗")
            if not volatility_ok:    reasons.append("ATR✗")
            if not supertrend_confirmed: reasons.append("NoConfirm")
            if not (pcr_bullish or pcr_bearish): reasons.append(f"PCR({pcr:.2f})" if pcr else "PCR✗")

            # Append intelligence block reasons
            for direction in ("BUY_CE", "BUY_PE"):
                fr = intel_fail_reason(direction)
                if fr:
                    reasons.append(fr)

            decision_reason = f"HOLD: {' '.join(reasons)}"

        # ── Progress score ──────────────────────────────────────────────────
        def sanitize(val):
            if val is None: return None
            if isinstance(val, float) and (np.isnan(val) or np.isinf(val)): return None
            return val

        base_denominator = 6   # Supertrend, RSI, EMA, Volatility, PCR, Greeks

        bullish_score = sum([
            1 if supertrend else 0,
            1 if bullish_rsi else 0,
            1 if (ema_bullish or ema_5 > ema_20) else 0,
            1 if volatility_ok else 0,
            1 if pcr_bullish else 0,
            1 if greeks_bullish else 0,
        ])
        bearish_score = sum([
            1 if not supertrend else 0,
            1 if bearish_rsi else 0,
            1 if (ema_bearish or ema_5 < ema_20) else 0,
            1 if volatility_ok else 0,
            1 if pcr_bearish else 0,
            1 if greeks_bearish else 0,
        ])

        # Intelligence bonus: +1 if all intel filters pass (VIX, PCR trend, time-of-day always evaluated)
        intel_denominator = base_denominator
        if not backtest_mode and intelligence_filter_reasons:
            intel_denominator += 1
            if intel_pass("BUY_CE"): bullish_score += 1
            if intel_pass("BUY_PE"): bearish_score += 1

        # PDH/PDL confluence bonus: +0.5 if price broke above PDH (bullish) or below PDL (bearish)
        if pdh_pdl_pdc and current_price:
            pdh = pdh_pdl_pdc.get("pdh")
            pdl = pdh_pdl_pdc.get("pdl")
            if pdh and current_price > pdh:
                bullish_score += 0.5
                intel_denominator += 0.5
            if pdl and current_price < pdl:
                bearish_score += 0.5
                intel_denominator += 0.5

        # ── ML model win-probability (optional, degrades gracefully) ─────────
        ml_win_prob: Optional[float] = None
        if not backtest_mode:
            try:
                from app.intelligence.signal_model import get_model
                ml = get_model()
                if ml.is_available:
                    regime_ctx_ml = (intelligence_context or {}).get("market_regime", {})
                    iv_ctx_ml = (intelligence_context or {}).get("iv_rank", {})
                    breadth_ctx_ml = (intelligence_context or {}).get("market_breadth", {})
                    ml_features = {
                        "rsi": sanitize(round(rsi, 2)),
                        "supertrend": 1 if supertrend else -1,
                        "ema_diff_pct": sanitize(round((ema_5 - ema_20) / ema_20 * 100, 4)) if ema_20 else None,
                        "atr_pct": sanitize(round(atr_range, 3)),
                        "pcr": sanitize(pcr),
                        "pcr_trend": pcr_trend,
                        "ce_delta": (greeks or {}).get("ce", {}).get("delta") if greeks else None,
                        "pe_delta": (greeks or {}).get("pe", {}).get("delta") if greeks else None,
                        "ce_theta": (greeks or {}).get("ce", {}).get("theta") if greeks else None,
                        "pe_theta": (greeks or {}).get("pe", {}).get("theta") if greeks else None,
                        "ce_iv":    (greeks or {}).get("ce", {}).get("iv") if greeks else None,
                        "pe_iv":    (greeks or {}).get("pe", {}).get("iv") if greeks else None,
                        "vix":      vix,
                        "regime":   regime_ctx_ml.get("regime"),
                        "adx":      regime_ctx_ml.get("adx"),
                        "iv_rank":  iv_ctx_ml.get("iv_rank"),
                        "breadth_bias": breadth_ctx_ml.get("breadth_bias"),
                        "signal":   signal,  # what we decided before ML
                        "hour":     current_time.hour if current_time else None,
                        "minute":   current_time.minute if current_time else None,
                        "day_of_week": current_time.weekday() if current_time else None,
                    }
                    ml_win_prob = ml.predict_win_probability(ml_features)
                    if ml_win_prob is not None:
                        # Add fractional bonus: +0.5 check if model is confident (>0.65)
                        ml_bonus = 0.5 if ml_win_prob >= 0.65 else (0.25 if ml_win_prob >= 0.55 else 0.0)
                        if signal == "BUY_CE":
                            bullish_score += ml_bonus
                        elif signal == "BUY_PE":
                            bearish_score += ml_bonus
                        intel_denominator += 0.5  # keep denominator proportional
            except ImportError:
                pass

        bullish_progress = min(100, int((bullish_score / intel_denominator) * 100))
        bearish_progress = min(100, int((bearish_score / intel_denominator) * 100))

        progress_data = {
            "score":           bullish_progress if bullish_progress > bearish_progress else bearish_progress,
            "direction":       "BULLISH" if bullish_progress > bearish_progress else "BEARISH",
            "required_checks": intel_denominator,
            "passed_checks":   bullish_score if bullish_progress > bearish_progress else bearish_score,
        }

        # Attach intelligence context snapshot for frontend display
        intel_snapshot: Dict[str, Any] = {}
        if intel or vix is not None or pcr_trend is not None:
            regime_ctx  = intel.get("market_regime", {}) if intel else {}
            iv_ctx      = intel.get("iv_rank", {}) if intel else {}
            breadth_ctx = intel.get("market_breadth", {}) if intel else {}
            ob_ctx      = intel.get("order_book", {}) if intel else {}
            pg_ctx      = intel.get("portfolio_greeks", {}) if intel else {}
            oi_ctx      = intel.get("oi_analysis", {}) if intel else {}
            intel_snapshot = {
                "regime":            regime_ctx.get("regime"),
                "adx":               regime_ctx.get("adx"),
                "iv_rank":           iv_ctx.get("iv_rank"),
                "iv_recommendation": iv_ctx.get("recommendation"),
                "breadth_bias":      breadth_ctx.get("breadth_bias"),
                "advancing":         breadth_ctx.get("advancing"),
                "declining":         breadth_ctx.get("declining"),
                "ob_signal":         ob_ctx.get("imbalance_signal"),
                "entry_quality":     ob_ctx.get("entry_quality"),
                "net_delta":         pg_ctx.get("net_delta"),
                "hedge_needed":      pg_ctx.get("hedge_needed"),
                "vix":               vix,
                "pcr_trend":         pcr_trend,
                "time_of_day":       current_time.strftime("%H:%M") if current_time else None,
                "ml_win_prob":       ml_win_prob,
                # OI Analysis
                "oi_buildup":        oi_ctx.get("buildup_signal"),
                "oi_change_pct":     oi_ctx.get("oi_change_pct"),
                "max_oi_ce_strike":  oi_ctx.get("max_oi_ce_strike"),
                "max_oi_pe_strike":  oi_ctx.get("max_oi_pe_strike"),
                "max_pain_strike":   oi_ctx.get("max_pain_strike"),
                "distance_from_max_pain_pct": oi_ctx.get("distance_from_max_pain_pct"),
                # Expiry day
                "is_expiry_day":     self._is_expiry_day(greeks, current_time),
            }

        return {
            "signal":             signal,
            "reason":             decision_reason,
            "rsi":                sanitize(round(rsi, 2)),
            "supertrend":         "BULLISH" if supertrend else "BEARISH",
            "ema_5":              sanitize(round(ema_5, 2)),
            "ema_20":             sanitize(round(ema_20, 2)),
            "pcr":                sanitize(pcr) if pcr is not None else None,
            "greeks":             greeks,
            "support_resistance": support_resistance,
            "breakout":           breakout_data,
            "filters":            filter_checks,
            "volume_ratio":       sanitize(round(current_volume / current_avg_vol, 2)) if current_avg_vol else None,
            "atr_pct":            sanitize(round(atr_range, 3)),
            "progress":           progress_data,
            "intelligence":       intel_snapshot,
            "pdh_pdl_pdc":        pdh_pdl_pdc,
        }
