"""Tests for Position and PositionManager."""

import pytest
import datetime
from unittest.mock import patch
from app.managers.position_manager import Position, PositionManager


class TestPosition:
    """Test Position dataclass-like object."""

    def test_create_position(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE")
        assert pos.instrument_key == "NSE_FO|12345"
        assert pos.entry_price == 100.0
        assert pos.quantity == 10
        assert pos.position_type == "CE"
        assert pos.id is not None

    def test_stop_loss_calculation(self):
        """Default SL is 30% below entry."""
        pos = Position("NSE_FO|12345", 100.0, 10, "CE", stop_loss_pct=0.30)
        assert pos.stop_loss == 70.0

    def test_target_calculation(self):
        """Default target is 1.5x entry."""
        pos = Position("NSE_FO|12345", 100.0, 10, "CE", target_multiplier=1.5)
        assert pos.target == 150.0

    def test_to_dict(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE")
        d = pos.to_dict()
        assert d['instrument_key'] == "NSE_FO|12345"
        assert d['entry_price'] == 100.0
        assert d['quantity'] == 10
        assert d['position_type'] == "CE"
        assert 'id' in d
        assert 'entry_time' in d


class TestTrailingStop:
    """Test trailing stop logic."""

    def test_trailing_not_activated_below_threshold(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE",
                       trailing_activation_pct=1.0, trailing_pct=0.5)
        pos.update_trailing_stop(100.5)  # 0.5% gain, below 1% activation
        assert pos.trailing_sl_activated is False
        assert pos.trailing_sl is None

    def test_trailing_activated_at_threshold(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE",
                       trailing_activation_pct=1.0, trailing_pct=0.5)
        pos.update_trailing_stop(101.0)  # 1% gain
        assert pos.trailing_sl_activated is True
        assert pos.trailing_sl is not None

    def test_trailing_sl_moves_up(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE",
                       trailing_activation_pct=1.0, trailing_pct=0.5)
        pos.update_trailing_stop(102.0)
        sl1 = pos.trailing_sl
        pos.update_trailing_stop(105.0)
        sl2 = pos.trailing_sl
        assert sl2 > sl1

    def test_trailing_sl_does_not_move_down(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE",
                       trailing_activation_pct=1.0, trailing_pct=0.5)
        pos.update_trailing_stop(105.0)
        sl_high = pos.trailing_sl
        pos.update_trailing_stop(103.0)
        assert pos.trailing_sl == sl_high


class TestShouldExit:
    """Test exit conditions."""

    def test_stop_loss_hit(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE", stop_loss_pct=0.30)
        now = datetime.datetime(2025, 1, 1, 10, 0)
        should, reason = pos.should_exit(69.0, now)
        assert should is True
        assert "STOP_LOSS" in reason

    def test_target_hit(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE", target_multiplier=1.5)
        now = datetime.datetime(2025, 1, 1, 10, 0)
        should, reason = pos.should_exit(151.0, now)
        assert should is True
        assert "TARGET_HIT" in reason

    def test_trailing_sl_hit(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE",
                       trailing_activation_pct=1.0, trailing_pct=0.5)
        now = datetime.datetime(2025, 1, 1, 10, 0)
        # Activate trailing SL
        pos.update_trailing_stop(110.0)
        # Price drops below trailing SL
        should, reason = pos.should_exit(pos.trailing_sl - 1, now)
        assert should is True
        assert "TRAILING_SL" in reason

    def test_time_based_exit(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE")
        close_time = datetime.datetime(2025, 1, 1, 15, 16)
        should, reason = pos.should_exit(100.0, close_time)
        assert should is True
        assert "TIME_BASED_EXIT" in reason

    def test_no_exit(self):
        pos = Position("NSE_FO|12345", 100.0, 10, "CE", stop_loss_pct=0.30,
                       target_multiplier=1.5)
        now = datetime.datetime(2025, 1, 1, 10, 0)
        should, reason = pos.should_exit(100.0, now)
        assert should is False
        assert reason == ""


class TestPositionManager:
    """Test PositionManager CRUD operations."""

    def test_open_position(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        pos = pm.open_position("NSE_FO|12345", 100.0, 10, "CE")
        assert pos.entry_price == 100.0
        assert pm.get_position_count() == 1

    def test_close_position(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        pos = pm.open_position("NSE_FO|12345", 100.0, 10, "CE")
        trade = pm.close_position(pos.id, 120.0, "TARGET")
        assert trade is not None
        assert trade['pnl'] == 200.0  # (120-100) * 10
        assert pm.get_position_count() == 0

    def test_close_nonexistent_position(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        assert pm.close_position("fake-id", 100, "TEST") is None

    def test_invalid_instrument_key(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        with pytest.raises(ValueError, match="Invalid instrument_key"):
            pm.open_position("INVALID", 100.0, 10, "CE")

    def test_valid_instrument_keys(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        assert pm._is_valid_instrument_key("NSE_FO|12345") is True
        assert pm._is_valid_instrument_key("NSE_INDEX|Nifty 50") is True
        assert pm._is_valid_instrument_key("NSE_EQ|RELIANCE") is True

    def test_invalid_instrument_keys(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        assert pm._is_valid_instrument_key("") is False
        assert pm._is_valid_instrument_key("INVALID") is False
        assert pm._is_valid_instrument_key("BSE_FO|123") is False
        assert pm._is_valid_instrument_key("NSE_FO|") is False
        assert pm._is_valid_instrument_key(None) is False

    def test_get_positions(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        pm.open_position("NSE_FO|11111", 100.0, 5, "CE")
        pm.open_position("NSE_FO|22222", 200.0, 3, "PE")
        positions = pm.get_positions()
        assert len(positions) == 2

    def test_unrealized_pnl(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        pos = pm.open_position("NSE_FO|12345", 100.0, 10, "CE")
        pnl = pm.calculate_unrealized_pnl({"NSE_FO|12345": 110.0})
        assert pnl == 100.0  # (110-100) * 10

    def test_unrealized_pnl_missing_price(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        pm.open_position("NSE_FO|12345", 100.0, 10, "CE")
        pnl = pm.calculate_unrealized_pnl({})
        assert pnl == 0.0

    def test_check_exits_stop_loss(self, tmp_json_file):
        pm = PositionManager(data_file=tmp_json_file)
        pos = pm.open_position("NSE_FO|12345", 100.0, 10, "CE")
        # SL is at 70.0 (30% default)
        closed = pm.check_exits({"NSE_FO|12345": 65.0})
        assert len(closed) == 1
        assert "STOP_LOSS" in closed[0]['reason']
        assert pm.get_position_count() == 0

    def test_persistence(self, tmp_json_file):
        """Positions should persist to file and be reloadable."""
        pm1 = PositionManager(data_file=tmp_json_file)
        pm1.open_position("NSE_FO|12345", 100.0, 10, "CE")

        pm2 = PositionManager(data_file=tmp_json_file)
        assert pm2.get_position_count() == 1
