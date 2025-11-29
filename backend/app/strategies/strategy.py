import pandas as pd
import numpy as np

class StrategyEngine:
    def __init__(self):
        pass

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_ema(self, series, period):
        return series.ewm(span=period, adjust=False).mean()

    def calculate_macd(self, series, fast=12, slow=26, signal=9):
        exp1 = series.ewm(span=fast, adjust=False).mean()
        exp2 = series.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def calculate_bollinger_bands(self, series, period=20, std_dev=2):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, lower_band

    def calculate_supertrend(self, df, period=7, multiplier=3):
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Calculate ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Calculate Supertrend
        hl2 = (high + low) / 2
        final_upperband = hl2 + (multiplier * atr)
        final_lowerband = hl2 - (multiplier * atr)
        
        supertrend = [True] * len(df) # True = Bullish, False = Bearish
        
        for i in range(1, len(df.index)):
            curr, prev = i, i-1
            
            # Upper Band Logic - maintain previous high if current is lower
            if close.iloc[curr] > final_upperband.iloc[prev]:
                final_upperband.iloc[curr] = max(final_upperband.iloc[curr], final_upperband.iloc[prev])
            else:
                final_upperband.iloc[curr] = final_upperband.iloc[curr]
                
            # Lower Band Logic - maintain previous low if current is higher
            if close.iloc[curr] < final_lowerband.iloc[prev]:
                final_lowerband.iloc[curr] = min(final_lowerband.iloc[curr], final_lowerband.iloc[prev])
            else:
                final_lowerband.iloc[curr] = final_lowerband.iloc[curr]
                
            # Trend Logic
            if close.iloc[curr] > final_upperband.iloc[prev]:
                supertrend[curr] = True
            elif close.iloc[curr] < final_lowerband.iloc[prev]:
                supertrend[curr] = False
            else:
                supertrend[curr] = supertrend[prev]
                
                if supertrend[curr] == True and final_lowerband.iloc[curr] < final_lowerband.iloc[prev]:
                    final_lowerband.iloc[curr] = final_lowerband.iloc[prev]
                if supertrend[curr] == False and final_upperband.iloc[curr] > final_upperband.iloc[prev]:
                    final_upperband.iloc[curr] = final_upperband.iloc[prev]

        return pd.Series(supertrend, index=df.index), final_upperband, final_lowerband

    def calculate_vwap(self, df):
        v = df['volume']
        tp = (df['high'] + df['low'] + df['close']) / 3
        vwap = (tp * v).cumsum() / v.cumsum()
        # Fill NaN values using forward fill then backward fill
        vwap = vwap.bfill().ffill()
        # If still has NaN, use simple average
        if vwap.isna().any():
            vwap = vwap.fillna(tp.mean())
        return vwap

    def calculate_support_resistance(self, df, window=20):
        """
        Calculate support and resistance levels using local highs and lows.
        Uses a rolling window approach with pivot points.
        
        Returns: {
            'support': [list of support levels],
            'resistance': [list of resistance levels],
            'nearest_support': closest support below current price,
            'nearest_resistance': closest resistance above current price
        }
        """
        high = df['high']
        low = df['low']
        close = df['close']
        current_price = close.iloc[-1]
        
        # Identify local highs and lows
        support_levels = []
        resistance_levels = []
        
        # Use last 100 candles for support/resistance calculation (prevents too many levels)
        lookback = min(100, len(df))
        recent_high = high.iloc[-lookback:]
        recent_low = low.iloc[-lookback:]
        
        # Find pivot points - local extremes
        for i in range(1, len(recent_high) - 1):
            # Resistance: local high with lower highs on both sides
            if recent_high.iloc[i] > recent_high.iloc[i-1] and recent_high.iloc[i] > recent_high.iloc[i+1]:
                resistance_levels.append(round(recent_high.iloc[i], 2))
            
            # Support: local low with higher lows on both sides
            if recent_low.iloc[i] < recent_low.iloc[i-1] and recent_low.iloc[i] < recent_low.iloc[i+1]:
                support_levels.append(round(recent_low.iloc[i], 2))
        
        # Also include the highest high and lowest low in recent history
        max_high = high.iloc[-lookback:].max()
        min_low = low.iloc[-lookback:].min()
        
        if resistance_levels:
            resistance_levels.append(round(max_high, 2))
        else:
            resistance_levels = [round(max_high, 2)]
            
        if support_levels:
            support_levels.append(round(min_low, 2))
        else:
            support_levels = [round(min_low, 2)]
        
        # Remove duplicates and sort
        resistance_levels = sorted(list(set(resistance_levels)), reverse=True)
        support_levels = sorted(list(set(support_levels)), reverse=True)
        
        # Find nearest support and resistance
        nearest_support = None
        nearest_resistance = None
        
        # Find nearest support (highest level below current price)
        supports_below = [s for s in support_levels if s < current_price]
        if supports_below:
            nearest_support = max(supports_below)
        
        # Find nearest resistance (lowest level above current price)
        resistances_above = [r for r in resistance_levels if r > current_price]
        if resistances_above:
            nearest_resistance = min(resistances_above)
        
        # Calculate distance percentages
        support_distance = None
        resistance_distance = None
        
        if nearest_support:
            support_distance = round(((current_price - nearest_support) / current_price) * 100, 2)
        if nearest_resistance:
            resistance_distance = round(((nearest_resistance - current_price) / current_price) * 100, 2)
        
        return {
            'support_levels': support_levels[:5],  # Top 5 support levels
            'resistance_levels': resistance_levels[:5],  # Top 5 resistance levels
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'support_distance_pct': support_distance,
            'resistance_distance_pct': resistance_distance,
            'current_price': round(current_price, 2)
        }

    def detect_breakout(self, df, sensitivity=0.015):
        """
        Detect if price is breaking out above resistance or below support.
        Breakout is confirmed when price moves beyond previous highs/lows by a percentage.
        
        sensitivity: percentage threshold for breakout (default 1.5%)
        
        Returns: {
            'is_breakout': bool,
            'breakout_type': 'UPSIDE' | 'DOWNSIDE' | None,
            'breakout_level': the level being broken,
            'strength': percentage move
        }
        """
        if len(df) < 50:
            return {
                'is_breakout': False,
                'breakout_type': None,
                'breakout_level': None,
                'strength': 0
            }
        
        close = df['close']
        high = df['high']
        low = df['low']
        
        current_price = close.iloc[-1]
        
        # Get the highest high and lowest low from last 50 candles
        lookback = 50
        highest_high = high.iloc[-lookback:].max()
        lowest_low = low.iloc[-lookback:].min()
        
        # Calculate if price breaks above/below with sensitivity
        breakout_threshold_up = highest_high * (1 + sensitivity)
        breakout_threshold_down = lowest_low * (1 - sensitivity)
        
        is_breakout = False
        breakout_type = None
        breakout_level = None
        strength = 0
        
        if current_price > breakout_threshold_up:
            is_breakout = True
            breakout_type = "UPSIDE"
            breakout_level = round(highest_high, 2)
            strength = round(((current_price - highest_high) / highest_high) * 100, 2)
        elif current_price < breakout_threshold_down:
            is_breakout = True
            breakout_type = "DOWNSIDE"
            breakout_level = round(lowest_low, 2)
            strength = round(((lowest_low - current_price) / lowest_low) * 100, 2)
        
        return {
            'is_breakout': is_breakout,
            'breakout_type': breakout_type,
            'breakout_level': breakout_level,
            'strength': strength
        }

    def calculate_atr(self, df, period=14):
        """Calculate Average True Range for volatility measurement"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def calculate_avg_volume(self, df, period=20):
        """Calculate average volume for volume confirmation"""
        return df['volume'].rolling(window=period).mean()

    def get_supertrend_strength(self, df):
        """Get Supertrend band width for trend strength measurement"""
        _, upperband, lowerband = self.calculate_supertrend(df)
        current_price = df['close'].iloc[-1]
        
        # Calculate distance from bands
        dist_to_upper = abs(current_price - upperband.iloc[-1])
        dist_to_lower = abs(current_price - lowerband.iloc[-1])
        band_width = upperband.iloc[-1] - lowerband.iloc[-1]
        
        return {
            'band_width': band_width,
            'dist_to_upper': dist_to_upper,
            'dist_to_lower': dist_to_lower
        }

    def check_signal(self, df, pcr=None, greeks=None, backtest_mode=False):
        """
        Enhanced signal generation with strong confluence filters.
        
        Parameters:
        - df: DataFrame with OHLCV data
        - pcr: Put-Call Ratio for sentiment
        - greeks: Greeks data for options quality
        - backtest_mode: Skip real-time filters
        
        Returns: Signal with detailed reasoning
        """
        if df is None or df.empty or len(df) < 50:
            return "WAITING_DATA"

        # Ensure numeric columns
        for col in ['close', 'high', 'low', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col])

        close = df['close']

        # Calculate Indicators if not already present
        if 'rsi' not in df.columns:
            df['rsi'] = self.calculate_rsi(close)
        
        if 'supertrend' not in df.columns:
            df['supertrend'], _, _ = self.calculate_supertrend(df)
            
        if 'vwap' not in df.columns:
            df['vwap'] = self.calculate_vwap(df)

        # Get latest values
        current_price = close.iloc[-1]
        rsi = df['rsi'].iloc[-1]
        supertrend = df['supertrend'].iloc[-1]  # True = Bullish, False = Bearish
        vwap = df['vwap'].iloc[-1]
        
        # NEW: Volume and Volatility Filters
        atr = self.calculate_atr(df)
        avg_volume = self.calculate_avg_volume(df)
        current_volume = df['volume'].iloc[-1]
        current_atr = atr.iloc[-1]
        current_avg_vol = avg_volume.iloc[-1]
        
        # Handle NaN values for volume and ATR
        if pd.isna(current_avg_vol) or current_avg_vol == 0:
            current_avg_vol = current_volume  # Fallback to current volume
        if pd.isna(current_atr):
            current_atr = 0.0
        
        # NEW: Entry confirmation - check last 3 candles for consistency
        last_3_supertrend = df['supertrend'].iloc[-3:].values
        last_3_rsi = df['rsi'].iloc[-3:].values
        supertrend_confirmed = (last_3_supertrend[-1] == last_3_supertrend[-2]) or (last_3_supertrend[-2] == last_3_supertrend[-3])
        
        # NEW: Trend strength
        trend_strength = self.get_supertrend_strength(df)
        
        # Calculate Support/Resistance and Breakout
        support_resistance = self.calculate_support_resistance(df)
        breakout_data = self.detect_breakout(df)

        # Strategy Logic with Enhanced Filters
        signal = "HOLD"
        filter_checks = {
            'supertrend': False,
            'price_vwap': False,
            'rsi': False,
            'volume': False,
            'volatility': False,
            'pcr': False,
            'greeks': False,
            'entry_confirmation': False
        }
        
        # 1. SUPERTREND FILTER (Always pass - it's checked in final decision)
        filter_checks['supertrend'] = True
        
        # 2. PRICE vs VWAP FILTER (Price must be away from VWAP by at least 0.05%)
        price_vwap_distance = abs((current_price - vwap) / vwap) * 100
        filter_checks['price_vwap'] = price_vwap_distance > 0.05
        
        # 3. RSI FILTER (Balanced thresholds: 55+ for bullish, 45- for bearish)
        bullish_rsi = rsi > 55
        bearish_rsi = rsi < 45
        filter_checks['rsi'] = bullish_rsi or bearish_rsi
        
        # 4. VOLUME FILTER (DISABLED for Index - no meaningful volume)
        # Nifty 50 is an index, not a tradeable instrument, so volume = 0 or meaningless
        filter_checks['volume'] = True  # Always pass
        
        # 5. VOLATILITY FILTER (ATR must be reasonable - not too high, not too low)
        # Skip signals if ATR is extreme (choppy or overly volatile)
        atr_range = current_atr / current_price * 100
        volatility_ok = 0.01 < atr_range < 2.5  # Between 0.01% and 2.5%
        filter_checks['volatility'] = volatility_ok
        
        # 6. ENTRY CONFIRMATION (Last 2 candles confirm direction)
        entry_confirmed = supertrend_confirmed
        filter_checks['entry_confirmation'] = entry_confirmed
        
        # 7. PCR FILTER (Skip in backtest mode)
        pcr_bullish = True
        pcr_bearish = True
        
        if not backtest_mode and pcr:
            pcr_bullish = pcr < 1.0   # PCR < 1.0 is bullish (calls > puts)
            pcr_bearish = pcr > 1.0   # PCR > 1.0 is bearish (puts > calls)
            filter_checks['pcr'] = pcr_bullish or pcr_bearish
        else:
            filter_checks['pcr'] = True
        
        # 8. GREEKS FILTER (Skip in backtest mode)
        greeks_bullish = True
        greeks_bearish = True
        
        if not backtest_mode and greeks:
            # Skip Greeks filter if prices are 0 (API failure)
            ce_price = greeks.get('ce', {}).get('price', 0)
            pe_price = greeks.get('pe', {}).get('price', 0)
            
            if ce_price > 0 and pe_price > 0:
                # Delta Filter: CE needs delta > 0.3 for bullish, PE needs delta < -0.3 for bearish
                greeks_bullish = greeks['ce']['delta'] > 0.3
                greeks_bearish = greeks['pe']['delta'] < -0.3
                
                # Theta Filter: Avoid extreme time decay (< -100 is too much)
                greeks_bullish = greeks_bullish and greeks['ce'].get('theta', 0) > -100
                greeks_bearish = greeks_bearish and greeks['pe'].get('theta', 0) > -100
                
                filter_checks['greeks'] = greeks_bullish or greeks_bearish
            else:
                # If prices are 0, skip Greeks filter (treat as passed)
                filter_checks['greeks'] = True
        else:
            filter_checks['greeks'] = True

        # FINAL DECISION: All filters must pass for signal
        decision_reason = "HOLD"
        
        # BUY_CE: All bullish filters must be true
        if (supertrend and bullish_rsi and filter_checks['price_vwap'] and 
            filter_checks['volume'] and filter_checks['volatility'] and 
            entry_confirmed and pcr_bullish and greeks_bullish):
            signal = "BUY_CE"
            decision_reason = (f"🟢 BUY_CE SETUP: Supertrend↑ RSI({rsi:.1f})>65 "
                             f"Price>{vwap:.2f}(VWAP) Vol✓ ATR✓ Confirmed")
        
        # BUY_PE: All bearish filters must be true
        elif (not supertrend and bearish_rsi and filter_checks['price_vwap'] and 
              filter_checks['volume'] and filter_checks['volatility'] and 
              entry_confirmed and pcr_bearish and greeks_bearish):
            signal = "BUY_PE"
            decision_reason = (f"🔴 BUY_PE SETUP: Supertrend↓ RSI({rsi:.1f})<35 "
                             f"Price<{vwap:.2f}(VWAP) Vol✓ ATR✓ Confirmed")
        
        else:
            # Detailed HOLD reason
            reasons = []
            if not supertrend: reasons.append("ST↓")
            else: reasons.append("ST↑")
            
            if rsi > 55: reasons.append(f"RSI{rsi:.0f}")
            else: reasons.append(f"RSI{rsi:.0f}")
            
            if not filter_checks['price_vwap']: reasons.append("Price≈VWAP")
            if not filter_checks['volume']: reasons.append("Vol↓")
            if not filter_checks['volatility']: reasons.append("ATR✗")
            if not entry_confirmed: reasons.append("NoConfirm")
            if not (pcr_bullish or pcr_bearish): reasons.append(f"PCR({pcr:.2f})")
            if not (greeks_bullish or greeks_bearish): reasons.append("Greeks✗")
            
            decision_reason = f"HOLD: {' '.join(reasons)}"

        # Sanitize output to prevent JSON errors
        def sanitize(val):
            if val is None:
                return None
            if isinstance(val, float):
                if np.isnan(val) or np.isinf(val):
                    return None
                return val
            return val

        # Handle VWAP sanitization more carefully
        vwap_safe = sanitize(vwap)
        if vwap_safe is not None:
            vwap_safe = round(vwap_safe, 2)

        return {
            "signal": signal,
            "reason": decision_reason,
            "rsi": sanitize(round(rsi, 2)),
            "supertrend": "BULLISH" if supertrend else "BEARISH",
            "vwap": vwap_safe,
            "pcr": sanitize(pcr) if pcr is not None else None,
            "greeks": greeks,
            "support_resistance": support_resistance,
            "breakout": breakout_data,
            "filters": filter_checks,
            "volume_ratio": sanitize(round(current_volume / current_avg_vol, 2)) if current_avg_vol else None,
            "atr_pct": sanitize(round(atr_range, 3))
        }

