"""Tests for Backtester - metrics calculation and mock data generation."""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from app.strategies.backtester import Backtester


class TestBacktesterMetrics:
    """Test the _calculate_metrics method directly (no external deps)."""

    def _make_backtester(self):
        """Create a Backtester with mocked dependencies."""
        mock_fetcher = MagicMock()
        mock_strategy = MagicMock()
        bt = Backtester(data_fetcher=mock_fetcher, strategy_engine=mock_strategy)
        return bt

    def test_no_trades(self):
        bt = self._make_backtester()
        bt.trades = []
        metrics = bt._calculate_metrics(100000, 100000)
        assert metrics['total_return_pct'] == 0
        assert metrics['win_rate'] == 0
        assert metrics['profit_factor'] == 0

    def test_all_wins(self):
        bt = self._make_backtester()
        bt.trades = [
            {'pnl': 100, 'pnl_pct': 10},
            {'pnl': 200, 'pnl_pct': 20},
        ]
        metrics = bt._calculate_metrics(100000, 100300)
        assert metrics['win_rate'] == 100.0
        assert metrics['avg_win'] == 150.0
        assert metrics['avg_loss'] == 0

    def test_all_losses(self):
        bt = self._make_backtester()
        bt.trades = [
            {'pnl': -100, 'pnl_pct': -10},
            {'pnl': -200, 'pnl_pct': -20},
        ]
        metrics = bt._calculate_metrics(100000, 99700)
        assert metrics['win_rate'] == 0.0
        assert metrics['avg_loss'] == -150.0
        assert metrics['profit_factor'] == 0

    def test_mixed_trades(self):
        bt = self._make_backtester()
        bt.trades = [
            {'pnl': 300, 'pnl_pct': 30},
            {'pnl': -100, 'pnl_pct': -10},
        ]
        metrics = bt._calculate_metrics(100000, 100200)
        assert metrics['win_rate'] == 50.0
        assert metrics['avg_win'] == 300.0
        assert metrics['avg_loss'] == -100.0
        assert metrics['profit_factor'] == 3.0  # 300 / 100

    def test_max_drawdown(self):
        bt = self._make_backtester()
        bt.trades = [
            {'pnl': 1000, 'pnl_pct': 1},
            {'pnl': -3000, 'pnl_pct': -3},
            {'pnl': 500, 'pnl_pct': 0.5},
        ]
        metrics = bt._calculate_metrics(100000, 98500)
        # Peak: 101000, trough: 98000, drawdown = (101000-98000)/101000 * 100 ≈ 2.97%
        assert metrics['max_drawdown_pct'] > 0

    def test_return_pct(self):
        bt = self._make_backtester()
        bt.trades = [{'pnl': 10000, 'pnl_pct': 10}]
        metrics = bt._calculate_metrics(100000, 110000)
        assert metrics['total_return_pct'] == 10.0


class TestGenerateMockData:
    """Test mock data generation for backtesting."""

    def _make_backtester(self):
        mock_fetcher = MagicMock()
        mock_strategy = MagicMock()
        return Backtester(data_fetcher=mock_fetcher, strategy_engine=mock_strategy)

    def test_generates_dataframe(self):
        bt = self._make_backtester()
        df = bt._generate_mock_data("2025-01-01", "2025-01-05", "1minute")
        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_has_ohlcv_columns(self):
        bt = self._make_backtester()
        df = bt._generate_mock_data("2025-01-01", "2025-01-05", "1minute")
        for col in ['open', 'high', 'low', 'close', 'volume']:
            assert col in df.columns

    def test_max_500_candles(self):
        bt = self._make_backtester()
        df = bt._generate_mock_data("2020-01-01", "2025-01-01", "1minute")
        assert len(df) <= 500

    def test_invalid_dates_returns_none(self):
        bt = self._make_backtester()
        df = bt._generate_mock_data("2025-01-05", "2025-01-01", "1minute")
        # End before start should produce empty or None
        assert df is None or len(df) == 0


class TestRunBacktest:
    """Test the full backtest pipeline with mocked data fetcher."""

    def test_backtest_with_mock_data(self):
        """Run a minimal backtest using mock data generation."""
        mock_fetcher = MagicMock()
        mock_fetcher.get_historical_data.return_value = None  # Force mock data

        from app.strategies.strategy import StrategyEngine
        real_strategy = StrategyEngine()

        bt = Backtester(data_fetcher=mock_fetcher, strategy_engine=real_strategy)
        result = bt.run_backtest(
            symbol="NSE_INDEX|Nifty 50",
            from_date="2025-01-01",
            to_date="2025-01-10",
            initial_capital=100000,
            interval="1minute"
        )

        assert 'initial_capital' in result
        assert 'final_capital' in result
        assert 'total_trades' in result
        assert 'trades' in result
        assert 'metrics' in result
        assert result['initial_capital'] == 100000

    def test_backtest_returns_error_on_no_data(self):
        """When both real and mock data fail, return error."""
        mock_fetcher = MagicMock()
        mock_fetcher.get_historical_data.side_effect = Exception("API down")

        mock_strategy = MagicMock()
        bt = Backtester(data_fetcher=mock_fetcher, strategy_engine=mock_strategy)

        # Patch _generate_mock_data to also fail
        with patch.object(bt, '_generate_mock_data', return_value=None):
            result = bt.run_backtest("SYM", "2025-01-01", "2025-01-02")
            assert 'error' in result
