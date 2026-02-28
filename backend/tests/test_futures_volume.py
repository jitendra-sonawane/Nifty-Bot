"""Tests for FuturesVolumeTracker — 1-min candle building, delta classification, CVD."""

import time
import pytest
from app.core.futures_volume import FuturesVolumeTracker


class TestFuturesVolumeTracker:
    """Unit tests for FuturesVolumeTracker."""

    def test_initial_state(self):
        tracker = FuturesVolumeTracker()
        snapshot = tracker.get_snapshot()
        assert snapshot["current_cvd"] == 0
        assert snapshot["current_delta"] == 0
        assert snapshot["total_volume"] == 0
        assert snapshot["candles"] == []
        assert snapshot["futures_ltp"] == 0.0

    def test_single_tick_creates_candle(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        snapshot = tracker.get_snapshot()
        assert snapshot["futures_ltp"] == 24100.0
        assert snapshot["total_volume"] == 500

    def test_uptick_classified_as_buy(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.on_tick(price=24105.0, volume=300, timestamp=1709096101.0)
        snapshot = tracker.get_snapshot()
        assert len(snapshot["candles"]) == 1
        candle = snapshot["candles"][0]
        assert candle["buy_volume"] == 800
        assert candle["sell_volume"] == 0

    def test_downtick_classified_as_sell(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.on_tick(price=24095.0, volume=300, timestamp=1709096101.0)
        snapshot = tracker.get_snapshot()
        candle = snapshot["candles"][0]
        assert candle["buy_volume"] == 500
        assert candle["sell_volume"] == 300

    def test_equal_price_uses_previous_direction(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=100, timestamp=1709096100.0)
        tracker.on_tick(price=24105.0, volume=200, timestamp=1709096101.0)
        tracker.on_tick(price=24105.0, volume=150, timestamp=1709096102.0)
        candle = tracker.get_snapshot()["candles"][0]
        assert candle["buy_volume"] == 450
        assert candle["sell_volume"] == 0

    def test_new_minute_creates_new_candle(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.on_tick(price=24110.0, volume=300, timestamp=1709096160.0)
        snapshot = tracker.get_snapshot()
        assert len(snapshot["candles"]) == 2

    def test_cvd_accumulates_across_candles(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.on_tick(price=24090.0, volume=300, timestamp=1709096160.0)
        snapshot = tracker.get_snapshot()
        assert snapshot["current_cvd"] == 200

    def test_delta_calculation(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.on_tick(price=24095.0, volume=300, timestamp=1709096101.0)
        candle = tracker.get_snapshot()["candles"][0]
        assert candle["delta"] == 200
        assert candle["total_volume"] == 800

    def test_total_volume_tracks_all_ticks(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.on_tick(price=24110.0, volume=300, timestamp=1709096160.0)
        tracker.on_tick(price=24120.0, volume=200, timestamp=1709096220.0)
        assert tracker.get_snapshot()["total_volume"] == 1000

    def test_reset_clears_all_state(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=500, timestamp=1709096100.0)
        tracker.reset()
        snapshot = tracker.get_snapshot()
        assert snapshot["current_cvd"] == 0
        assert snapshot["candles"] == []
        assert snapshot["total_volume"] == 0

    def test_max_candles_rolling_window(self):
        tracker = FuturesVolumeTracker(max_candles=5)
        for i in range(7):
            tracker.on_tick(price=24100.0 + i, volume=100, timestamp=1709096100.0 + i * 60)
        snapshot = tracker.get_snapshot()
        assert len(snapshot["candles"]) == 5

    def test_candle_time_format(self):
        tracker = FuturesVolumeTracker()
        tracker.on_tick(price=24100.0, volume=100, timestamp=1709096100.0)
        candle = tracker.get_snapshot()["candles"][0]
        assert "time" in candle
        assert "timestamp" in candle
        assert isinstance(candle["time"], str)
        assert isinstance(candle["timestamp"], (int, float))

    def test_snapshot_includes_instrument_key(self):
        tracker = FuturesVolumeTracker(instrument_key="NSE_FO|12345")
        snapshot = tracker.get_snapshot()
        assert snapshot["instrument_key"] == "NSE_FO|12345"

    def test_thread_safety_no_crash(self):
        import threading
        tracker = FuturesVolumeTracker()
        errors = []

        def writer():
            try:
                for i in range(100):
                    tracker.on_tick(price=24100.0 + i * 0.05, volume=10, timestamp=1709096100.0 + i * 0.1)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    tracker.get_snapshot()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert errors == []


class TestGetFuturesInstrumentKey:
    """Test DataFetcher.get_futures_instrument_key() with a mock instruments DataFrame."""

    def _make_fetcher_with_df(self, df):
        """Create a DataFetcher-like object with a pre-loaded instruments_df."""
        import pandas as pd
        from unittest.mock import MagicMock
        fetcher = MagicMock()
        fetcher.instruments_df = df
        from app.data.data_fetcher import DataFetcher
        fetcher.get_futures_instrument_key = DataFetcher.get_futures_instrument_key.__get__(fetcher)
        return fetcher

    def test_finds_nearest_expiry_futures(self):
        import pandas as pd
        from datetime import datetime, timedelta
        today = datetime.now().date()
        near_expiry = today + timedelta(days=7)
        far_expiry = today + timedelta(days=37)

        df = pd.DataFrame({
            'name': ['NIFTY', 'NIFTY'],
            'instrument_type': ['FUTIDX', 'FUTIDX'],
            'expiry': pd.to_datetime([near_expiry, far_expiry]),
            'instrument_key': ['NSE_FO|11111', 'NSE_FO|22222'],
        })
        fetcher = self._make_fetcher_with_df(df)
        key = fetcher.get_futures_instrument_key()
        assert key == 'NSE_FO|11111'

    def test_returns_none_when_no_futures(self):
        import pandas as pd
        df = pd.DataFrame({
            'name': ['NIFTY'],
            'instrument_type': ['OPTIDX'],
            'expiry': pd.to_datetime(['2026-03-15']),
            'instrument_key': ['NSE_FO|99999'],
        })
        fetcher = self._make_fetcher_with_df(df)
        key = fetcher.get_futures_instrument_key()
        assert key is None

    def test_skips_expired_contracts(self):
        import pandas as pd
        from datetime import datetime, timedelta
        yesterday = datetime.now().date() - timedelta(days=1)
        future = datetime.now().date() + timedelta(days=14)

        df = pd.DataFrame({
            'name': ['NIFTY', 'NIFTY'],
            'instrument_type': ['FUTIDX', 'FUTIDX'],
            'expiry': pd.to_datetime([yesterday, future]),
            'instrument_key': ['NSE_FO|OLD', 'NSE_FO|VALID'],
        })
        fetcher = self._make_fetcher_with_df(df)
        key = fetcher.get_futures_instrument_key()
        assert key == 'NSE_FO|VALID'
