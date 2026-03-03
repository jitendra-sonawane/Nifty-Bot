"""Tests for OrderFlowAnalyzer — VWAP, Volume Profile, Delta Divergence, Book Imbalance."""

import threading
import pytest
from app.core.order_flow import OrderFlowAnalyzer


class TestOrderFlowAnalyzer:
    """Unit tests for OrderFlowAnalyzer."""

    # ------------------------------------------------------------------
    # VWAP tests
    # ------------------------------------------------------------------

    def test_initial_snapshot(self):
        """All defaults: vwap=0, std_dev=0, profile=[], poc=0, imbalance=0.5, divergence.active=False."""
        analyzer = OrderFlowAnalyzer()
        snap = analyzer.get_snapshot()

        assert snap["vwap"] == 0.0
        assert snap["std_dev"] == 0.0
        assert snap["volume_profile"] == []
        assert snap["poc"] == 0.0
        assert snap["book_imbalance"] == 0.5
        assert snap["delta_divergence"]["active"] is False
        assert snap["total_volume"] == 0.0
        assert snap["vwap_upper"] == 0.0
        assert snap["vwap_lower"] == 0.0
        assert snap["value_area_high"] == 0.0
        assert snap["value_area_low"] == 0.0
        assert snap["bid_total"] == 0.0
        assert snap["ask_total"] == 0.0

    def test_vwap_single_tick(self):
        """Single tick at 25000 with vol=100 -> vwap=25000."""
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=1709096100.0)
        snap = analyzer.get_snapshot()
        assert snap["vwap"] == pytest.approx(25000.0)

    def test_vwap_two_ticks(self):
        """Two equal-volume ticks at 25000 and 25100 -> vwap=25050."""
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=1709096100.0)
        analyzer.on_tick(price=25100.0, volume=100, direction="sell", timestamp=1709096101.0)
        snap = analyzer.get_snapshot()
        assert snap["vwap"] == pytest.approx(25050.0)

    def test_vwap_weighted_by_volume(self):
        """300@25000 + 100@25100 -> vwap=25025."""
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=300, direction="buy", timestamp=1709096100.0)
        analyzer.on_tick(price=25100.0, volume=100, direction="sell", timestamp=1709096101.0)
        snap = analyzer.get_snapshot()
        # (300*25000 + 100*25100) / 400 = (7500000 + 2510000) / 400 = 25025
        assert snap["vwap"] == pytest.approx(25025.0)

    def test_vwap_deviation_bands(self):
        """Verify upper > vwap > lower, and bands are symmetric around vwap."""
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=1709096100.0)
        analyzer.on_tick(price=25200.0, volume=100, direction="sell", timestamp=1709096101.0)
        snap = analyzer.get_snapshot()

        assert snap["vwap_upper"] > snap["vwap"]
        assert snap["vwap_lower"] < snap["vwap"]
        # Symmetry: upper - vwap == vwap - lower
        assert snap["vwap_upper"] - snap["vwap"] == pytest.approx(snap["vwap"] - snap["vwap_lower"])
        assert snap["std_dev"] > 0.0

    def test_zero_volume_tick_ignored(self):
        """vol=0 tick doesn't affect state."""
        analyzer = OrderFlowAnalyzer()
        analyzer.on_tick(price=25000.0, volume=0, direction="buy", timestamp=1709096100.0)
        snap = analyzer.get_snapshot()
        assert snap["vwap"] == 0.0
        assert snap["total_volume"] == 0.0
        assert snap["volume_profile"] == []

    # ------------------------------------------------------------------
    # Volume Profile tests
    # ------------------------------------------------------------------

    def test_volume_profile_single_bin(self):
        """Two ticks in same bin -> 1 bin, correct buy/sell split."""
        analyzer = OrderFlowAnalyzer(bin_size=50.0)
        # Both prices round to 25000 with bin_size=50
        analyzer.on_tick(price=25010.0, volume=100, direction="buy", timestamp=1709096100.0)
        analyzer.on_tick(price=24990.0, volume=50, direction="sell", timestamp=1709096101.0)
        snap = analyzer.get_snapshot()

        profile = snap["volume_profile"]
        assert len(profile) == 1
        assert profile[0]["buy_vol"] == 100.0
        assert profile[0]["sell_vol"] == 50.0
        assert profile[0]["total"] == 150.0

    def test_volume_profile_multiple_bins(self):
        """Ticks in different bins -> sorted by price."""
        analyzer = OrderFlowAnalyzer(bin_size=50.0)
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=1709096100.0)
        analyzer.on_tick(price=25100.0, volume=80, direction="sell", timestamp=1709096101.0)
        analyzer.on_tick(price=24900.0, volume=60, direction="buy", timestamp=1709096102.0)
        snap = analyzer.get_snapshot()

        profile = snap["volume_profile"]
        assert len(profile) == 3
        prices = [b["price"] for b in profile]
        assert prices == sorted(prices), "Profile should be sorted by price ascending"

    def test_poc_is_highest_volume_bin(self):
        """Heavy volume in one bin -> that bin is POC."""
        analyzer = OrderFlowAnalyzer(bin_size=50.0)
        # Pump heavy volume into the 25000 bin
        analyzer.on_tick(price=25000.0, volume=500, direction="buy", timestamp=1709096100.0)
        analyzer.on_tick(price=25100.0, volume=50, direction="sell", timestamp=1709096101.0)
        analyzer.on_tick(price=24900.0, volume=30, direction="buy", timestamp=1709096102.0)
        snap = analyzer.get_snapshot()

        assert snap["poc"] == pytest.approx(25000.0)

    def test_value_area_contains_poc(self):
        """Spread across 10 bins -> VA encloses POC."""
        analyzer = OrderFlowAnalyzer(bin_size=50.0)
        # Create 10 bins with varying volume
        for i in range(10):
            price = 24500.0 + i * 50.0
            vol = 100 if i == 5 else 20  # bin at 24750 gets heavy volume
            analyzer.on_tick(price=price, volume=vol, direction="buy", timestamp=1709096100.0 + i)
        snap = analyzer.get_snapshot()

        poc = snap["poc"]
        va_high = snap["value_area_high"]
        va_low = snap["value_area_low"]

        assert va_high >= poc
        assert va_low <= poc

    # ------------------------------------------------------------------
    # Book Imbalance tests
    # ------------------------------------------------------------------

    def test_book_imbalance_balanced(self):
        """Equal bids/asks -> 0.5."""
        analyzer = OrderFlowAnalyzer()
        bids = [(25000.0, 100), (24990.0, 100), (24980.0, 100), (24970.0, 100), (24960.0, 100)]
        asks = [(25010.0, 100), (25020.0, 100), (25030.0, 100), (25040.0, 100), (25050.0, 100)]
        analyzer.update_order_book(bids, asks)
        snap = analyzer.get_snapshot()
        assert snap["book_imbalance"] == pytest.approx(0.5)

    def test_book_imbalance_bid_heavy(self):
        """More bids -> > 0.6."""
        analyzer = OrderFlowAnalyzer()
        bids = [(25000.0, 200), (24990.0, 200), (24980.0, 200), (24970.0, 200), (24960.0, 200)]
        asks = [(25010.0, 50), (25020.0, 50), (25030.0, 50), (25040.0, 50), (25050.0, 50)]
        analyzer.update_order_book(bids, asks)
        snap = analyzer.get_snapshot()
        # bid_total=1000, ask_total=250 -> imbalance = 1000/1250 = 0.8
        assert snap["book_imbalance"] > 0.6

    def test_book_imbalance_ask_heavy(self):
        """More asks -> < 0.4."""
        analyzer = OrderFlowAnalyzer()
        bids = [(25000.0, 50), (24990.0, 50), (24980.0, 50), (24970.0, 50), (24960.0, 50)]
        asks = [(25010.0, 200), (25020.0, 200), (25030.0, 200), (25040.0, 200), (25050.0, 200)]
        analyzer.update_order_book(bids, asks)
        snap = analyzer.get_snapshot()
        # bid_total=250, ask_total=1000 -> imbalance = 250/1250 = 0.2
        assert snap["book_imbalance"] < 0.4

    def test_book_imbalance_empty_book(self):
        """No data -> 0.5."""
        analyzer = OrderFlowAnalyzer()
        analyzer.update_order_book([], [])
        snap = analyzer.get_snapshot()
        assert snap["book_imbalance"] == pytest.approx(0.5)

    # ------------------------------------------------------------------
    # Delta Divergence tests
    # ------------------------------------------------------------------

    def test_no_divergence_with_few_candles(self):
        """2 candles -> active=False."""
        analyzer = OrderFlowAnalyzer()
        analyzer.on_candle_close(25000.0, 100.0)
        analyzer.on_candle_close(25010.0, 110.0)
        snap = analyzer.get_snapshot()
        div = snap["delta_divergence"]
        assert div["active"] is False
        assert div["bars"] == 2

    def test_bearish_divergence_detected(self):
        """8 candles, price rising CVD falling -> bearish."""
        analyzer = OrderFlowAnalyzer()
        # First half: lower prices, higher CVD
        # Second half: higher prices, lower CVD
        for i in range(8):
            if i < 4:
                price = 25000.0 + i * 5        # 25000, 25005, 25010, 25015
                cvd = 1000.0 - i * 10           # 1000, 990, 980, 970
            else:
                price = 25040.0 + (i - 4) * 10  # 25040, 25050, 25060, 25070
                cvd = 900.0 - (i - 4) * 50      # 900, 850, 800, 750
            analyzer.on_candle_close(price, cvd)

        snap = analyzer.get_snapshot()
        div = snap["delta_divergence"]
        assert div["active"] is True
        assert div["type"] == "bearish"
        assert div["strength"] > 0.0
        assert div["bars"] == 8

    def test_bullish_divergence_detected(self):
        """8 candles, price falling CVD rising -> bullish."""
        analyzer = OrderFlowAnalyzer()
        for i in range(8):
            if i < 4:
                price = 25100.0 - i * 5         # 25100, 25095, 25090, 25085
                cvd = -1000.0 + i * 10           # -1000, -990, -980, -970
            else:
                price = 25060.0 - (i - 4) * 10   # 25060, 25050, 25040, 25030
                cvd = -900.0 + (i - 4) * 50      # -900, -850, -800, -750
            analyzer.on_candle_close(price, cvd)

        snap = analyzer.get_snapshot()
        div = snap["delta_divergence"]
        assert div["active"] is True
        assert div["type"] == "bullish"
        assert div["strength"] > 0.0
        assert div["bars"] == 8

    def test_no_divergence_when_aligned(self):
        """Both price and CVD rising -> active=False."""
        analyzer = OrderFlowAnalyzer()
        for i in range(8):
            price = 25000.0 + i * 10   # steadily rising
            cvd = 100.0 + i * 20       # steadily rising
            analyzer.on_candle_close(price, cvd)

        snap = analyzer.get_snapshot()
        div = snap["delta_divergence"]
        assert div["active"] is False

    def test_divergence_lookback_window(self):
        """12 candles added -> only 8 retained."""
        analyzer = OrderFlowAnalyzer()
        for i in range(12):
            analyzer.on_candle_close(25000.0 + i, 100.0 + i)
        snap = analyzer.get_snapshot()
        assert snap["delta_divergence"]["bars"] == 8

    # ------------------------------------------------------------------
    # Reset + Thread Safety
    # ------------------------------------------------------------------

    def test_reset_clears_all_state(self):
        """Feed data, reset, verify defaults."""
        analyzer = OrderFlowAnalyzer()
        # Feed some ticks
        analyzer.on_tick(price=25000.0, volume=100, direction="buy", timestamp=1709096100.0)
        analyzer.on_tick(price=25100.0, volume=50, direction="sell", timestamp=1709096101.0)
        analyzer.update_order_book(
            [(25000.0, 100)],
            [(25010.0, 200)],
        )
        analyzer.on_candle_close(25000.0, 100.0)

        # Verify state is non-default
        snap_before = analyzer.get_snapshot()
        assert snap_before["total_volume"] > 0

        # Reset
        analyzer.reset()
        snap = analyzer.get_snapshot()

        assert snap["vwap"] == 0.0
        assert snap["std_dev"] == 0.0
        assert snap["volume_profile"] == []
        assert snap["poc"] == 0.0
        assert snap["total_volume"] == 0.0
        assert snap["book_imbalance"] == 0.5
        assert snap["bid_total"] == 0.0
        assert snap["ask_total"] == 0.0
        assert snap["delta_divergence"]["active"] is False

    def test_thread_safety_no_crash(self):
        """Concurrent writer + reader threads, no exceptions."""
        analyzer = OrderFlowAnalyzer()
        errors = []

        def writer():
            try:
                for i in range(200):
                    analyzer.on_tick(
                        price=25000.0 + i * 0.05,
                        volume=10,
                        direction="buy" if i % 2 == 0 else "sell",
                        timestamp=1709096100.0 + i * 0.1,
                    )
                    if i % 10 == 0:
                        analyzer.on_candle_close(25000.0 + i, float(i))
                    if i % 20 == 0:
                        analyzer.update_order_book(
                            [(25000.0, 100)],
                            [(25010.0, 100)],
                        )
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(200):
                    analyzer.get_snapshot()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert errors == []
