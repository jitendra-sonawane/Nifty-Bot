"""Tests for Paper Trading Manager."""

import pytest
import os
from app.managers.paper_trading import PaperTradingManager


class TestPaperTradingInit:

    def test_default_balance(self, tmp_json_file):
        # Remove the temp file so PaperTradingManager creates defaults
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        assert pm.get_balance() == 100000.0

    def test_default_data_structure(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        assert pm.data['positions'] == []
        assert pm.data['orders'] == []


class TestAddFunds:

    def test_add_positive_amount(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        new_balance = pm.add_funds(5000)
        assert new_balance == 105000.0

    def test_add_zero_rejected(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        new_balance = pm.add_funds(0)
        assert new_balance == 100000.0

    def test_add_negative_rejected(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        new_balance = pm.add_funds(-500)
        assert new_balance == 100000.0

    def test_add_invalid_type(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        new_balance = pm.add_funds("abc")
        assert new_balance == 100000.0


class TestPlaceOrder:

    def test_buy_order(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        order_id = pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        assert order_id is not None
        assert pm.get_balance() == 99000.0  # 100000 - 10*100

    def test_buy_insufficient_funds(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        order_id = pm.place_order("NSE_FO|12345", 10000, "BUY", 100.0)
        assert order_id is None  # 10000 * 100 = 1M > 100K

    def test_sell_order(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        order_id = pm.place_order("NSE_FO|12345", 5, "SELL", 120.0)
        assert order_id is not None
        # Balance: 100000 - 1000 + 600 = 99600
        assert pm.get_balance() == 99600.0

    def test_sell_without_position(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        order_id = pm.place_order("NSE_FO|12345", 5, "SELL", 120.0)
        assert order_id is None

    def test_sell_more_than_held(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 5, "BUY", 100.0)
        order_id = pm.place_order("NSE_FO|12345", 10, "SELL", 120.0)
        assert order_id is None


class TestPositionTracking:

    def test_position_created_on_buy(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        positions = pm.get_positions()
        assert len(positions) == 1
        assert positions[0]['quantity'] == 10
        assert positions[0]['average_price'] == 100.0

    def test_position_averages_on_add(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        pm.place_order("NSE_FO|12345", 10, "BUY", 200.0)
        positions = pm.get_positions()
        assert positions[0]['quantity'] == 20
        assert positions[0]['average_price'] == 150.0  # (10*100 + 10*200) / 20

    def test_position_removed_on_full_sell(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        pm.place_order("NSE_FO|12345", 10, "SELL", 120.0)
        positions = pm.get_positions()
        assert len(positions) == 0

    def test_partial_sell(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        pm.place_order("NSE_FO|12345", 3, "SELL", 120.0)
        positions = pm.get_positions()
        assert len(positions) == 1
        assert positions[0]['quantity'] == 7


class TestPnL:

    def test_unrealized_pnl(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        pnl = pm.get_pnl({"NSE_FO|12345": 110.0})
        assert pnl == 100.0  # (110-100) * 10

    def test_pnl_no_prices(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        assert pm.get_pnl(None) == 0.0
        assert pm.get_pnl({}) == 0.0

    def test_realized_pnl_after_sell(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        pm.place_order("NSE_FO|12345", 10, "SELL", 120.0)
        assert pm.get_daily_realized_pnl() == 200.0  # (120-100)*10

    def test_closed_trades_recorded(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        pm.place_order("NSE_FO|12345", 10, "SELL", 120.0)
        closed = pm.get_closed_trades()
        assert len(closed) == 1
        assert closed[0]['pnl'] == 200.0

    def test_total_pnl(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm = PaperTradingManager(data_file=tmp_json_file)
        pm.place_order("NSE_FO|12345", 10, "BUY", 100.0)
        pm.place_order("NSE_FO|12345", 5, "SELL", 120.0)
        # Realized: (120-100)*5 = 100
        # Unrealized: (110-100)*5 = 50
        total = pm.get_total_pnl({"NSE_FO|12345": 110.0})
        assert total == 150.0


class TestPersistence:

    def test_save_and_load(self, tmp_json_file):
        os.unlink(tmp_json_file)
        pm1 = PaperTradingManager(data_file=tmp_json_file)
        pm1.place_order("NSE_FO|12345", 10, "BUY", 100.0)

        pm2 = PaperTradingManager(data_file=tmp_json_file)
        assert pm2.get_balance() == pm1.get_balance()
        assert len(pm2.get_positions()) == 1
