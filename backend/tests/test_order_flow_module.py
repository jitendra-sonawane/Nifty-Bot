"""Tests for OrderFlowModule — Intelligence engine plugin for order flow scoring."""

import pytest
from app.core.order_flow import OrderFlowAnalyzer
from app.intelligence.order_flow_module import OrderFlowModule


class TestOrderFlowModule:
    """Unit tests for OrderFlowModule."""

    def _make_module(self) -> OrderFlowModule:
        analyzer = OrderFlowAnalyzer()
        return OrderFlowModule(analyzer)

    def _feed_bullish_data(self, analyzer: OrderFlowAnalyzer) -> None:
        """Feed data that produces a bullish order-flow picture.

        - Price around 25000 with heavy buy volume (POC > VWAP likely)
        - Book imbalance > 0.55 (heavy bids)
        - No bearish divergence
        """
        ts = 1709096100.0
        # Heavy buying at higher prices shifts POC above VWAP
        analyzer.on_tick(price=24900.0, volume=50, direction="sell", timestamp=ts)
        analyzer.on_tick(price=24950.0, volume=50, direction="sell", timestamp=ts + 1)
        analyzer.on_tick(price=25000.0, volume=200, direction="buy", timestamp=ts + 2)
        analyzer.on_tick(price=25050.0, volume=300, direction="buy", timestamp=ts + 3)
        analyzer.on_tick(price=25100.0, volume=100, direction="buy", timestamp=ts + 4)

        # Heavy bids (bullish book)
        bids = [(25000.0, 300), (24990.0, 250), (24980.0, 200)]
        asks = [(25010.0, 50), (25020.0, 50), (25030.0, 50)]
        analyzer.update_order_book(bids, asks)

    def _feed_bearish_data(self, analyzer: OrderFlowAnalyzer) -> None:
        """Feed data that produces a bearish order-flow picture.

        - Heavy sell volume (POC < VWAP likely)
        - Book imbalance < 0.45 (heavy asks)
        """
        ts = 1709096100.0
        # Heavy selling at lower prices shifts POC below VWAP
        analyzer.on_tick(price=25100.0, volume=50, direction="buy", timestamp=ts)
        analyzer.on_tick(price=25050.0, volume=50, direction="buy", timestamp=ts + 1)
        analyzer.on_tick(price=25000.0, volume=200, direction="sell", timestamp=ts + 2)
        analyzer.on_tick(price=24950.0, volume=300, direction="sell", timestamp=ts + 3)
        analyzer.on_tick(price=24900.0, volume=100, direction="sell", timestamp=ts + 4)

        # Heavy asks (bearish book)
        bids = [(25000.0, 50), (24990.0, 50), (24980.0, 50)]
        asks = [(25010.0, 300), (25020.0, 250), (25030.0, 200)]
        analyzer.update_order_book(bids, asks)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_module_name(self):
        """Module name must be 'order_flow'."""
        module = self._make_module()
        assert module.name == "order_flow"

    def test_get_context_empty_state(self):
        """Empty analyzer -> pass=True, score exists, no crash."""
        module = self._make_module()
        ctx = module.get_context()

        assert ctx["pass"] is True
        assert isinstance(ctx["score"], float)
        assert "components" in ctx
        assert "alerts" in ctx
        assert "snapshot" in ctx

    def test_update_does_not_crash(self):
        """update() with signal_direction should not crash."""
        module = self._make_module()
        # Should not raise
        module.update({"signal_direction": "PE"})
        module.update({"signal_direction": "CE"})
        module.update({})  # no signal_direction key

    def test_bullish_signal_passes_with_bullish_data(self):
        """Feed bullish data, CE direction -> score > 0."""
        analyzer = OrderFlowAnalyzer()
        module = OrderFlowModule(analyzer)
        self._feed_bullish_data(analyzer)
        module.update({"signal_direction": "CE"})

        ctx = module.get_context()
        assert ctx["score"] > 0

    def test_bearish_signal_passes_with_bearish_data(self):
        """Feed bearish data, PE direction -> score > 0."""
        analyzer = OrderFlowAnalyzer()
        module = OrderFlowModule(analyzer)
        self._feed_bearish_data(analyzer)
        module.update({"signal_direction": "PE"})

        ctx = module.get_context()
        assert ctx["score"] > 0

    def test_reset_works(self):
        """After reset, module returns safe defaults (pass=True)."""
        analyzer = OrderFlowAnalyzer()
        module = OrderFlowModule(analyzer)
        self._feed_bullish_data(analyzer)
        module.update({"signal_direction": "PE"})

        # Reset
        module.reset()

        ctx = module.get_context()
        assert ctx["pass"] is True
        assert ctx["score"] == 50.0

    def test_components_dict_has_expected_keys(self):
        """All 4 sub-score keys must be present in components."""
        module = self._make_module()
        ctx = module.get_context()

        expected_keys = {"vwap_alignment", "delta_momentum", "book_support", "volume_profile"}
        assert set(ctx["components"].keys()) == expected_keys

    def test_no_data_returns_safe_defaults(self):
        """No data ingested -> pass=True, score=50, all components=50."""
        module = self._make_module()
        ctx = module.get_context()

        assert ctx["pass"] is True
        assert ctx["score"] == 50.0
        assert ctx["components"]["vwap_alignment"] == 50.0
        assert ctx["components"]["delta_momentum"] == 50.0
        assert ctx["components"]["book_support"] == 50.0
        assert ctx["components"]["volume_profile"] == 50.0
        assert ctx["alerts"] == []
