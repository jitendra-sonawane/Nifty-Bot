import json
import os
import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

class PaperTradingManager:
    def __init__(self, data_file="paper_trading_data.json"):
        self.data_file = data_file
        self.data = self._load_data()
        self.daily_realized_pnl = 0.0  # Track realized P&L from closed positions
        self.last_reset_date = datetime.date.today()

    def _load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error loading paper trading data: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading paper trading data: {e}")
        
        # Default data
        return {
            "balance": 100000.0,  # Default starting balance
            "positions": [],
            "orders": [],
            "trade_history": [],
            "closed_trades": []  # Track closed trades for P&L calculation
        }

    def _save_data(self):
        try:
            with open(self.data_file, "w") as f:
                json.dump(self.data, f, indent=4)
        except (IOError, OSError) as e:
            logger.error(f"Error saving paper trading data: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving paper trading data: {e}")

    def get_balance(self):
        return self.data["balance"]

    def add_funds(self, amount):
        try:
            amount = float(amount)
            if amount <= 0:
                logger.warning(f"Invalid amount for add_funds: {amount}. Must be positive.")
                return self.data["balance"]
            self.data["balance"] += amount
            self._save_data()
            logger.info(f"Added ₹{amount:.2f} to paper trading balance. New balance: ₹{self.data['balance']:.2f}")
            return self.data["balance"]
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid amount type for add_funds: {e}")
            return self.data["balance"]

    def place_order(self, instrument_key, quantity, transaction_type, price=0.0, product='D'):
        """
        Simulates placing an order.
        """
        order_id = str(uuid.uuid4())
        total_value = quantity * price
        
        # Basic validation
        if transaction_type == "BUY":
            if total_value > self.data["balance"]:
                logger.warning(f"Insufficient funds for paper trade. Required: ₹{total_value:.2f}, Available: ₹{self.data['balance']:.2f}")
                return None
            self.data["balance"] -= total_value
        elif transaction_type == "SELL":
            # Check if position exists and has sufficient quantity
            position = next((p for p in self.data["positions"] if p["instrument_key"] == instrument_key), None)
            if not position or position["quantity"] < quantity:
                available = position['quantity'] if position else 0
                logger.warning(f"Insufficient position to sell. Available: {available}, Requested: {quantity}")
                return None
            self.data["balance"] += total_value

        order = {
            "order_id": order_id,
            "instrument_key": instrument_key,
            "quantity": quantity,
            "transaction_type": transaction_type,
            "price": price,
            "product": product,
            "status": "COMPLETE",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        self.data["orders"].append(order)
        self._update_positions(order)
        self._save_data()
        
        logger.info(f"Paper Order Placed: {transaction_type} {quantity} x {instrument_key} @ {price}")
        return order_id

    def _reset_daily_pnl(self):
        """Reset daily P&L tracking at start of new trading day."""
        today = datetime.date.today()
        if today > self.last_reset_date:
            self.daily_realized_pnl = 0.0
            self.last_reset_date = today
            print(f"📅 Daily P&L reset for {today}")

    def _update_positions(self, order):
        # Simple position tracking
        # Check if position exists
        found = False
        for pos in self.data["positions"]:
            if pos["instrument_key"] == order["instrument_key"]:
                found = True
                if order["transaction_type"] == "BUY":
                    # Update average price
                    total_cost = (pos["quantity"] * pos["average_price"]) + (order["quantity"] * order["price"])
                    pos["quantity"] += order["quantity"]
                    pos["average_price"] = total_cost / pos["quantity"] if pos["quantity"] > 0 else 0
                elif order["transaction_type"] == "SELL":
                    # Calculate realized P&L when closing position
                    sell_qty = min(order["quantity"], pos["quantity"])
                    pnl = (order["price"] - pos["average_price"]) * sell_qty
                    pnl_pct = ((order["price"] - pos["average_price"]) / pos["average_price"] * 100) if pos["average_price"] > 0 else 0
                    
                    # Track realized P&L
                    today = datetime.date.today()
                    if today == self.last_reset_date:
                        self.daily_realized_pnl += pnl
                    else:
                        self.daily_realized_pnl = pnl
                        self.last_reset_date = today
                    
                    # Record closed trade
                    closed_trade = {
                        "instrument_key": order["instrument_key"],
                        "entry_price": pos["average_price"],
                        "exit_price": order["price"],
                        "quantity": sell_qty,
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "entry_time": pos.get("entry_time", datetime.datetime.now().isoformat()),
                        "exit_time": datetime.datetime.now().isoformat(),
                        "reason": "PAPER_TRADE_CLOSE"
                    }
                    self.data["closed_trades"].append(closed_trade)
                    
                    logger.info(f"💰 Paper Trade Closed: P&L ₹{pnl:.2f} ({pnl_pct:.2f}%) | Daily Total: ₹{self.daily_realized_pnl:.2f}")
                    
                    pos["quantity"] -= sell_qty
                
                break
        
        # Remove closed positions after iteration (avoid modifying list during iteration)
        self.data["positions"] = [p for p in self.data["positions"] if p["quantity"] > 0]
        
        if not found and order["transaction_type"] == "BUY":
            self.data["positions"].append({
                "instrument_key": order["instrument_key"],
                "quantity": order["quantity"],
                "average_price": order["price"],
                "entry_time": datetime.datetime.now().isoformat()
            })

    def get_positions(self):
        return self.data["positions"]

    def get_daily_realized_pnl(self):
        """Get daily realized P&L from closed trades."""
        today = datetime.date.today()
        if today > self.last_reset_date:
            self.daily_realized_pnl = 0.0
            self.last_reset_date = today
        return self.daily_realized_pnl

    def get_closed_trades(self):
        """Get all closed trades."""
        return self.data.get("closed_trades", [])

    def get_pnl(self, current_prices=None):
        """
        Calculate unrealized P&L based on current market prices.
        current_prices: dict {instrument_key: price} or None
        If None, returns 0 (no price data available)
        """
        if not current_prices:
            return 0.0
        
        pnl = 0.0
        for pos in self.data["positions"]:
            if pos["instrument_key"] not in current_prices:
                logger.warning(f"Missing current price for {pos['instrument_key']}. Skipping P&L calculation for this position.")
                continue
            current_price = current_prices.get(pos["instrument_key"])
            # PnL = (Current Price - Avg Price) * Quantity
            pnl += (current_price - pos["average_price"]) * pos["quantity"]
        return pnl

    def get_total_pnl(self, current_prices=None):
        """
        Get total P&L (realized + unrealized).
        current_prices: dict {instrument_key: price} or None
        """
        today = datetime.date.today()
        if today > self.last_reset_date:
            self.daily_realized_pnl = 0.0
            self.last_reset_date = today
        unrealized = self.get_pnl(current_prices) if current_prices else 0.0
        return self.daily_realized_pnl + unrealized