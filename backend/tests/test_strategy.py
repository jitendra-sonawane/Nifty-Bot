"""Tests for Strategy Engine - technical indicators and signal generation."""

import pytest
import pandas as pd
import numpy as np
from app.strategies.strategy import StrategyEngine


class TestCalculateRSI:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_rsi_range(self, sample_ohlcv_df):
        rsi = self.engine.calculate_rsi(sample_ohlcv_df['close'])
        valid = rsi.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_uptrend_high(self):
        """Consistently rising prices should produce RSI near 100."""
        prices = pd.Series(range(100, 200))
        rsi = self.engine.calculate_rsi(prices)
        assert rsi.iloc[-1] > 80

    def test_rsi_downtrend_low(self):
        """Consistently falling prices should produce RSI near 0."""
        prices = pd.Series(range(200, 100, -1))
        rsi = self.engine.calculate_rsi(prices)
        assert rsi.iloc[-1] < 20

    def test_rsi_custom_period(self):
        prices = pd.Series(range(100, 200))
        rsi = self.engine.calculate_rsi(prices, period=7)
        valid = rsi.dropna()
        assert len(valid) > 0


class TestCalculateEMA:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_ema_length(self, sample_ohlcv_df):
        ema = self.engine.calculate_ema(sample_ohlcv_df['close'], 20)
        assert len(ema) == len(sample_ohlcv_df)

    def test_ema_converges_to_price(self):
        """EMA of a constant series should equal the constant."""
        series = pd.Series([100.0] * 50)
        ema = self.engine.calculate_ema(series, 10)
        assert pytest.approx(ema.iloc[-1], abs=0.01) == 100.0

    def test_short_ema_reacts_faster(self, sample_ohlcv_df):
        """Short period EMA should track price more closely."""
        close = sample_ohlcv_df['close']
        ema_5 = self.engine.calculate_ema(close, 5)
        ema_20 = self.engine.calculate_ema(close, 20)
        # Short EMA should be closer to the last price
        last_price = close.iloc[-1]
        assert abs(ema_5.iloc[-1] - last_price) <= abs(ema_20.iloc[-1] - last_price)


class TestCalculateMACD:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_macd_returns_two_series(self, sample_ohlcv_df):
        macd, signal = self.engine.calculate_macd(sample_ohlcv_df['close'])
        assert len(macd) == len(sample_ohlcv_df)
        assert len(signal) == len(sample_ohlcv_df)

    def test_macd_constant_price_is_zero(self):
        """MACD of constant price should be ~0."""
        series = pd.Series([100.0] * 100)
        macd, signal = self.engine.calculate_macd(series)
        assert pytest.approx(macd.iloc[-1], abs=0.01) == 0


class TestCalculateBollingerBands:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_upper_above_lower(self, sample_ohlcv_df):
        upper, lower = self.engine.calculate_bollinger_bands(sample_ohlcv_df['close'])
        valid = upper.dropna() > lower.dropna()
        assert valid.all()

    def test_bands_around_sma(self, sample_ohlcv_df):
        close = sample_ohlcv_df['close']
        upper, lower = self.engine.calculate_bollinger_bands(close, period=20, std_dev=2)
        sma = close.rolling(20).mean()
        # Upper should be above SMA and lower below
        valid_idx = sma.dropna().index
        assert (upper[valid_idx] >= sma[valid_idx]).all()
        assert (lower[valid_idx] <= sma[valid_idx]).all()


class TestCalculateSupertrend:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_returns_three_series(self, sample_ohlcv_df):
        trend, upper, lower = self.engine.calculate_supertrend(sample_ohlcv_df)
        assert len(trend) == len(sample_ohlcv_df)
        assert len(upper) == len(sample_ohlcv_df)
        assert len(lower) == len(sample_ohlcv_df)

    def test_trend_is_boolean(self, sample_ohlcv_df):
        trend, _, _ = self.engine.calculate_supertrend(sample_ohlcv_df)
        for val in trend:
            assert val in (True, False)


class TestCalculateVWAP:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_vwap_no_nans(self, sample_ohlcv_df):
        vwap = self.engine.calculate_vwap(sample_ohlcv_df)
        assert not vwap.isna().any()

    def test_vwap_within_price_range(self, sample_ohlcv_df):
        vwap = self.engine.calculate_vwap(sample_ohlcv_df)
        # VWAP should be within the overall high-low range
        overall_high = sample_ohlcv_df['high'].max()
        overall_low = sample_ohlcv_df['low'].min()
        assert vwap.iloc[-1] >= overall_low * 0.95
        assert vwap.iloc[-1] <= overall_high * 1.05


class TestCalculateATR:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_atr_positive(self, sample_ohlcv_df):
        atr = self.engine.calculate_atr(sample_ohlcv_df)
        valid = atr.dropna()
        assert (valid >= 0).all()


class TestDetectBreakout:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_no_breakout_normal_data(self, sample_ohlcv_df):
        result = self.engine.detect_breakout(sample_ohlcv_df)
        assert 'is_breakout' in result
        assert 'breakout_type' in result

    def test_insufficient_data(self, small_ohlcv_df):
        result = self.engine.detect_breakout(small_ohlcv_df)
        assert result['is_breakout'] is False

    def test_upside_breakout(self):
        """Create data where close exceeds highest_high * (1+sensitivity).
        detect_breakout uses last 50 highs (including current candle) for threshold,
        so set high of the last candle at same level as others so threshold stays low,
        but close spikes above the threshold."""
        n = 60
        prices = np.full(n, 100.0)
        highs = np.full(n, 100.1)
        lows = np.full(n, 99.9)
        # Close spikes well above highest_high threshold: 100.1 * 1.015 = ~101.6
        prices[-1] = 105.0
        df = pd.DataFrame({
            'open': prices,
            'high': highs,
            'low': lows,
            'close': prices,
            'volume': [1000] * n
        })
        result = self.engine.detect_breakout(df, sensitivity=0.015)
        assert result['is_breakout'] is True
        assert result['breakout_type'] == "UPSIDE"


class TestCalculateSupportResistance:

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_returns_expected_keys(self, sample_ohlcv_df):
        result = self.engine.calculate_support_resistance(sample_ohlcv_df)
        assert 'support_levels' in result
        assert 'resistance_levels' in result
        assert 'nearest_support' in result
        assert 'nearest_resistance' in result
        assert 'current_price' in result


class TestCheckSignal:
    """Test the main signal generation."""

    def setup_method(self):
        self.engine = StrategyEngine()

    def test_waiting_data_for_none(self):
        assert self.engine.check_signal(None) == "WAITING_DATA"

    def test_waiting_data_for_empty(self):
        assert self.engine.check_signal(pd.DataFrame()) == "WAITING_DATA"

    def test_waiting_data_for_small(self, small_ohlcv_df):
        assert self.engine.check_signal(small_ohlcv_df) == "WAITING_DATA"

    def test_returns_dict_with_signal(self, sample_ohlcv_df):
        result = self.engine.check_signal(sample_ohlcv_df)
        assert isinstance(result, dict)
        assert 'signal' in result
        assert result['signal'] in ("BUY_CE", "BUY_PE", "HOLD")

    def test_result_has_all_keys(self, sample_ohlcv_df):
        result = self.engine.check_signal(sample_ohlcv_df)
        expected_keys = {'signal', 'reason', 'rsi', 'supertrend', 'ema_5', 'ema_20',
                         'vwap', 'pcr', 'greeks', 'support_resistance', 'breakout',
                         'filters', 'volume_ratio', 'atr_pct'}
        assert expected_keys.issubset(set(result.keys()))

    def test_filters_dict_present(self, sample_ohlcv_df):
        result = self.engine.check_signal(sample_ohlcv_df)
        filters = result['filters']
        expected = {'supertrend', 'ema_crossover', 'price_vwap', 'rsi',
                    'volume', 'volatility', 'pcr', 'greeks', 'entry_confirmation'}
        assert expected == set(filters.keys())

    def test_backtest_mode_skips_pcr_greeks(self, sample_ohlcv_df):
        result = self.engine.check_signal(sample_ohlcv_df, pcr=None, greeks=None,
                                          backtest_mode=True)
        assert result['filters']['pcr'] is True
        assert result['filters']['greeks'] is True

    def test_rsi_in_valid_range(self, sample_ohlcv_df):
        result = self.engine.check_signal(sample_ohlcv_df)
        if result['rsi'] is not None:
            assert 0 <= result['rsi'] <= 100

    def test_no_nan_in_output(self, sample_ohlcv_df):
        """Output should have no NaN values (sanitized)."""
        result = self.engine.check_signal(sample_ohlcv_df)
        for key in ['rsi', 'ema_5', 'ema_20', 'vwap', 'atr_pct']:
            val = result[key]
            if val is not None:
                assert not np.isnan(val), f"{key} is NaN"
