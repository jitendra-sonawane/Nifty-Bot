"""Tests for Risk Manager."""

import pytest
import datetime
from unittest.mock import patch
from app.managers.risk_manager import RiskManager


class TestRiskManagerInit:

    def test_default_params(self):
        rm = RiskManager()
        assert rm.initial_capital == 100000
        assert rm.risk_per_trade_pct == 0.02
        assert rm.daily_loss_limit_pct == 0.05
        assert rm.max_concurrent_positions == 2

    def test_custom_params(self):
        rm = RiskManager(initial_capital=500000, risk_per_trade_pct=0.01,
                         daily_loss_limit_pct=0.03, max_concurrent_positions=5)
        assert rm.initial_capital == 500000
        assert rm.risk_per_trade_pct == 0.01
        assert rm.daily_loss_limit_pct == 0.03
        assert rm.max_concurrent_positions == 5

    def test_daily_pnl_starts_zero(self):
        rm = RiskManager()
        assert rm.daily_pnl == 0.0


class TestCanTrade:

    def setup_method(self):
        self.rm = RiskManager(initial_capital=100000, daily_loss_limit_pct=0.05,
                              max_concurrent_positions=2)

    def test_can_trade_ok(self):
        can, reason = self.rm.can_trade(50000, 0)
        assert can is True
        assert reason == "OK"

    def test_daily_loss_limit_blocks(self):
        """After losing more than 5% of capital, trading should be blocked."""
        self.rm.daily_pnl = -6000  # > 5% of 100000
        can, reason = self.rm.can_trade(94000, 0)
        assert can is False
        assert "Daily loss limit" in reason

    def test_max_positions_blocks(self):
        can, reason = self.rm.can_trade(50000, 2)
        assert can is False
        assert "Max concurrent positions" in reason

    def test_zero_balance_blocks(self):
        can, reason = self.rm.can_trade(0, 0)
        assert can is False
        assert "Insufficient balance" in reason

    def test_negative_balance_blocks(self):
        can, reason = self.rm.can_trade(-100, 0)
        assert can is False
        assert "Insufficient balance" in reason


class TestPositionSize:

    def setup_method(self):
        self.rm = RiskManager(initial_capital=100000, risk_per_trade_pct=0.02)

    def test_basic_position_size(self):
        """Risk amount = 100000 * 0.02 = 2000. Risk per unit = 100 * 0.30 = 30.
        Max qty = 2000 / 30 = 66."""
        qty = self.rm.calculate_position_size(100, 0.30, 100000)
        assert qty == 66

    def test_minimum_is_one(self):
        """Even with low balance, minimum is 1."""
        qty = self.rm.calculate_position_size(1000, 0.30, 100)
        assert qty == 1

    def test_max_is_100(self):
        """Max capped at 100."""
        qty = self.rm.calculate_position_size(1, 0.01, 1000000)
        assert qty == 100

    def test_zero_stop_loss_returns_zero(self):
        qty = self.rm.calculate_position_size(100, 0, 100000)
        assert qty == 0

    def test_zero_entry_price(self):
        qty = self.rm.calculate_position_size(0, 0.30, 100000)
        assert qty == 0


class TestDailyPnl:

    def setup_method(self):
        self.rm = RiskManager()

    def test_update_daily_pnl(self):
        self.rm.update_daily_pnl(500)
        assert self.rm.daily_pnl == 500

    def test_accumulate_pnl(self):
        self.rm.update_daily_pnl(500)
        self.rm.update_daily_pnl(-200)
        assert self.rm.daily_pnl == 300

    @patch('app.managers.risk_manager.datetime')
    def test_auto_reset_on_new_day(self, mock_dt):
        """PnL should reset when a new day starts."""
        self.rm.daily_pnl = -1000
        self.rm.last_reset_date = datetime.date(2025, 1, 1)
        mock_dt.date.today.return_value = datetime.date(2025, 1, 2)
        self.rm.reset_daily_stats()
        assert self.rm.daily_pnl == 0.0


class TestGetStats:

    def test_stats_keys(self):
        rm = RiskManager()
        stats = rm.get_stats()
        expected_keys = {"daily_pnl", "daily_loss_limit", "risk_per_trade_pct",
                         "max_concurrent_positions", "is_trading_allowed"}
        assert set(stats.keys()) == expected_keys

    def test_stats_values(self):
        rm = RiskManager(initial_capital=100000, daily_loss_limit_pct=0.05)
        stats = rm.get_stats()
        assert stats['daily_loss_limit'] == 5000.0
        assert stats['is_trading_allowed'] is True

    def test_trading_not_allowed_after_loss(self):
        rm = RiskManager(initial_capital=100000, daily_loss_limit_pct=0.05)
        rm.daily_pnl = -6000
        stats = rm.get_stats()
        assert stats['is_trading_allowed'] is False
