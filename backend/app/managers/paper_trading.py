import json
import os
import datetime
import uuid

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
            except Exception as e:
                print(f"Error loading paper trading data: {e}")
        
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
        except Exception as e:
            print(f"Error saving paper trading data: {e}")

    def get_balance(self):
        return self.data["balance"]

    def add_funds(self, amount):
        self.data["balance"] += amount
        self._save_data()
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
                print("Insufficient funds for paper trade.")
                return None
            self.data["balance"] -= total_value
        elif transaction_type == "SELL":
            # For simplicity in this version, we allow short selling or closing positions
            # In a real scenario, we'd check if we have the position to sell
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
        
        print(f"Paper Order Placed: {transaction_type} {quantity} x {instrument_key} @ {price}")
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
                    pnl = (order["price"] - pos["average_price"]) * min(order["quantity"], pos["quantity"])
                    pnl_pct = ((order["price"] - pos["average_price"]) / pos["average_price"] * 100) if pos["average_price"] > 0 else 0
                    
                    # Track realized P&L
                    self._reset_daily_pnl()
                    self.daily_realized_pnl += pnl
                    
                    # Record closed trade
                    closed_trade = {
                        "instrument_key": order["instrument_key"],
                        "entry_price": pos["average_price"],
                        "exit_price": order["price"],
                        "quantity": min(order["quantity"], pos["quantity"]),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "entry_time": pos.get("entry_time", datetime.datetime.now().isoformat()),
                        "exit_time": datetime.datetime.now().isoformat(),
                        "reason": "PAPER_TRADE_CLOSE"
                    }
                    self.data["closed_trades"].append(closed_trade)
                    
                    print(f"💰 Paper Trade Closed: P&L ₹{pnl:.2f} ({pnl_pct:.2f}%) | Daily Total: ₹{self.daily_realized_pnl:.2f}")
                    
                    pos["quantity"] -= order["quantity"]
                
                # Remove if closed
                if pos["quantity"] == 0:
                    self.data["positions"].remove(pos)
                break
        
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
        self._reset_daily_pnl()
        return self.daily_realized_pnl

    def get_closed_trades(self):
        """Get all closed trades."""
        return self.data.get("closed_trades", [])

    def get_pnl(self, current_prices):
        """
        Calculate unrealized P&L based on current market prices.
        current_prices: dict {instrument_key: price}
        """
        pnl = 0.0
        for pos in self.data["positions"]:
            current_price = current_prices.get(pos["instrument_key"], pos["average_price"])
            # PnL = (Current Price - Avg Price) * Quantity
            pnl += (current_price - pos["average_price"]) * pos["quantity"]
        return pnl

    def get_total_pnl(self, current_prices):
        """
        Get total P&L (realized + unrealized).
        current_prices: dict {instrument_key: price}
        """
        self._reset_daily_pnl()
        unrealized = self.get_pnl(current_prices)
        return self.daily_realized_pnl + unrealized