import datetime
from typing import Optional

class RiskManager:
    """Manages risk parameters and position sizing."""
    
    def __init__(self, initial_capital: float = 100000, 
                 risk_per_trade_pct: float = 0.02,
                 daily_loss_limit_pct: float = 0.05,
                 max_concurrent_positions: int = 2):
        """
        Initialize risk manager.
        
        Args:
            initial_capital: Starting capital
            risk_per_trade_pct: Max risk per trade (default 2%)
            daily_loss_limit_pct: Max daily loss (default 5%)
            max_concurrent_positions: Max open positions (default 2)
        """
        self.initial_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_concurrent_positions = max_concurrent_positions
        
        # Daily tracking
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.date.today()
    
    def reset_daily_stats(self):
        """Reset daily P&L tracking (call at start of each trading day)."""
        today = datetime.date.today()
        if today > self.last_reset_date:
            self.daily_pnl = 0.0
            self.last_reset_date = today
            print(f"📅 Daily stats reset for {today}")
    
    def update_daily_pnl(self, pnl: float):
        """Update daily P&L after a trade closes."""
        self.reset_daily_stats()  # Auto-reset if new day
        self.daily_pnl += pnl
        print(f"💰 Daily P&L: ₹{self.daily_pnl:.2f}")
    
    def can_trade(self, current_balance: float, current_positions: int) -> tuple[bool, str]:
        """
        Check if we can take a new trade.
        
        Returns:
            (can_trade, reason)
        """
        self.reset_daily_stats()
        
        # 1. Check daily loss limit
        daily_loss_limit = self.initial_capital * self.daily_loss_limit_pct
        if self.daily_pnl < -daily_loss_limit:
            return False, f"Daily loss limit reached (₹{self.daily_pnl:.2f} / -₹{daily_loss_limit:.2f})"
        
        # 2. Check max concurrent positions
        if current_positions >= self.max_concurrent_positions:
            return False, f"Max concurrent positions reached ({current_positions}/{self.max_concurrent_positions})"
        
        # 3. Check if balance is sufficient
        if current_balance <= 0:
            return False, "Insufficient balance"
        
        return True, "OK"
    
    def calculate_position_size(self, entry_price: float, stop_loss_pct: float, 
                               current_balance: float) -> int:
        """
        Calculate position size (quantity) based on risk per trade.
        
        Formula:
        Risk Amount = Balance × Risk %
        Position Size = Risk Amount / (Entry Price × Stop Loss %)
        
        Args:
            entry_price: Entry price of the option
            stop_loss_pct: Stop loss percentage (e.g., 0.30 for 30%)
            current_balance: Current account balance
        
        Returns:
            Quantity to trade
        """
        risk_amount = current_balance * self.risk_per_trade_pct
        
        # Calculate max quantity based on risk
        # If SL is 30%, we can lose 30% of entry price per unit
        risk_per_unit = entry_price * stop_loss_pct
        
        if risk_per_unit <= 0:
            return 0
        
        max_quantity = int(risk_amount / risk_per_unit)
        
        # Ensure at least 1 lot, but cap at reasonable limit
        quantity = max(1, min(max_quantity, 100))  # Max 100 lots
        
        print(f"💼 Position Size Calculated: {quantity} lots")
        print(f"   Risk Amount: ₹{risk_amount:.2f} | Entry: ₹{entry_price} | SL: {stop_loss_pct*100}%")
        
        return quantity
    
    def get_stats(self) -> dict:
        """Get current risk management stats."""
        self.reset_daily_stats()
        daily_loss_limit = self.initial_capital * self.daily_loss_limit_pct
        
        return {
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_loss_limit": round(daily_loss_limit, 2),
            "risk_per_trade_pct": self.risk_per_trade_pct * 100,
            "max_concurrent_positions": self.max_concurrent_positions,
            "is_trading_allowed": bool(self.daily_pnl > -daily_loss_limit)
        }
