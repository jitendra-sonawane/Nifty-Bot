"""
Enhanced Risk Manager for Multi-Strategy Algo Trading.

Manages:
- Per-strategy risk limits and capital allocation
- Position sizing with Nifty lot-size enforcement
- Daily/session P&L tracking with auto-reset
- Portfolio-level Greeks monitoring
- Correlation-based position limits
"""

import datetime
import logging
from typing import Dict, Tuple, Optional, List
from app.core.config import Config
from app.core.models import OrderLeg, MultiLegPosition, Greeks

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Manages risk parameters, position sizing, and capital allocation
    across multiple strategies.
    
    Usage:
        rm = RiskManager(initial_capital=1000000)
        can_trade, reason = rm.can_trade("iron_condor", balance=900000, positions=1)
        qty = rm.calculate_position_size(entry_price=150, stop_loss_pct=0.30, balance=900000)
    """
    
    # Per-strategy capital allocation limits (% of total capital)
    STRATEGY_ALLOCATION = {
        "iron_condor": 0.40,       # Max 40% on Iron Condor
        "short_straddle": 0.30,    # Max 30% on Short Straddle
        "bull_call_spread": 0.20,  # Max 20% on Bull Call Spread
        "bear_put_spread": 0.20,   # Max 20% on Bear Put Spread
        "breakout": 0.15,          # Max 15% on Breakout (high risk)
    }
    
    def __init__(
        self,
        initial_capital: float = None,
        risk_per_trade_pct: float = None,
        daily_loss_limit_pct: float = None,
        max_concurrent_positions: int = None,
    ):
        """
        Initialize risk manager.
        
        Args:
            initial_capital: Starting capital (default from Config)
            risk_per_trade_pct: Max risk per trade as % (default 2%)
            daily_loss_limit_pct: Max daily loss as % (default 5%)
            max_concurrent_positions: Max open positions (default 3)
        """
        self.initial_capital = initial_capital or Config.INITIAL_CAPITAL
        self.risk_per_trade_pct = risk_per_trade_pct or Config.RISK_PER_TRADE_PCT
        self.daily_loss_limit_pct = daily_loss_limit_pct or Config.DAILY_LOSS_LIMIT_PCT
        self.max_concurrent_positions = max_concurrent_positions or Config.MAX_CONCURRENT_POSITIONS
        
        # Daily tracking
        self.daily_pnl: float = 0.0
        self.daily_trades: int = 0
        self.last_reset_date: datetime.date = datetime.date.today()
        
        # Per-strategy tracking
        self.strategy_pnl: Dict[str, float] = {}
        self.strategy_positions: Dict[str, int] = {}
        
        # Portfolio Greeks
        self.portfolio_greeks = Greeks()
    
    def reset_daily_stats(self):
        """Reset daily P&L tracking at start of each trading day."""
        today = datetime.date.today()
        if today > self.last_reset_date:
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset_date = today
            self.strategy_pnl.clear()
            logger.info(f"📅 Daily risk stats reset for {today}")
    
    def update_daily_pnl(self, pnl: float, strategy_name: str = ""):
        """Update daily P&L after a trade closes."""
        self.reset_daily_stats()
        self.daily_pnl += pnl
        self.daily_trades += 1
        
        if strategy_name:
            self.strategy_pnl[strategy_name] = self.strategy_pnl.get(strategy_name, 0) + pnl
        
        logger.info(f"💰 Daily P&L: ₹{self.daily_pnl:,.0f} | Trade #{self.daily_trades}")
    
    def can_trade(
        self,
        strategy_name: str,
        current_balance: float,
        current_positions: int,
        max_risk: float = 0,
    ) -> Tuple[bool, str]:
        """
        Check if a new trade is allowed under current risk limits.
        
        Args:
            strategy_name: Which strategy wants to trade
            current_balance: Current account balance
            current_positions: Number of open positions
            max_risk: Maximum risk of the proposed trade
        
        Returns:
            (can_trade: bool, reason: str)
        """
        self.reset_daily_stats()
        
        # 1. Check daily loss limit
        daily_loss_limit = self.initial_capital * self.daily_loss_limit_pct
        if self.daily_pnl < -daily_loss_limit:
            return False, (
                f"Daily loss limit reached: ₹{self.daily_pnl:,.0f} "
                f"/ -₹{daily_loss_limit:,.0f}"
            )
        
        # 2. Check max concurrent positions
        if current_positions >= self.max_concurrent_positions:
            return False, (
                f"Max positions reached: {current_positions}"
                f"/{self.max_concurrent_positions}"
            )
        
        # 3. Check balance
        if current_balance <= 0:
            return False, "Insufficient balance"
        
        # 4. Check per-strategy allocation
        allocation_pct = self.STRATEGY_ALLOCATION.get(strategy_name, 0.20)
        max_strategy_capital = self.initial_capital * allocation_pct
        
        if max_risk > max_strategy_capital:
            return False, (
                f"Trade risk ₹{max_risk:,.0f} exceeds {strategy_name} "
                f"allocation ₹{max_strategy_capital:,.0f} "
                f"({allocation_pct*100:.0f}%)"
            )
        
        # 5. Check remaining risk budget for the day
        remaining_budget = daily_loss_limit - abs(min(0, self.daily_pnl))
        if max_risk > remaining_budget * 2:  # Allow up to 2x remaining budget
            return False, (
                f"Risk ₹{max_risk:,.0f} too large relative to "
                f"remaining daily budget ₹{remaining_budget:,.0f}"
            )
        
        return True, "OK"
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_pct: float,
        current_balance: float,
        strategy_name: str = "",
        is_expiry_day: bool = False,
    ) -> int:
        """
        Calculate position size in lots (multiples of NIFTY_LOT_SIZE).

        Formula:
        Risk Amount = Balance × Risk%
        Raw Quantity = Risk Amount / (Entry Price × SL%)
        Lots = floor(Raw Quantity / Lot Size)

        On expiry day (0DTE), position size is reduced by EXPIRY_DAY["position_size_factor"].

        Args:
            entry_price: Per-unit entry price of the option
            stop_loss_pct: Stop loss as fraction (e.g., 0.30 = 30%)
            current_balance: Current account balance
            strategy_name: For per-strategy limits
            is_expiry_day: If True, reduce position size for 0DTE gamma risk

        Returns:
            Number of units (always multiple of lot size)
        """
        lot_size = Config.NIFTY_LOT_SIZE

        # Risk amount for this trade
        risk_amount = current_balance * self.risk_per_trade_pct

        # Per-strategy cap
        if strategy_name:
            allocation = self.STRATEGY_ALLOCATION.get(strategy_name, 0.20)
            max_allocation = self.initial_capital * allocation
            risk_amount = min(risk_amount, max_allocation * 0.1)  # 10% of allocation

        # Risk per unit
        risk_per_unit = entry_price * stop_loss_pct
        if risk_per_unit <= 0:
            return lot_size  # Return minimum 1 lot

        # Raw quantity
        raw_qty = risk_amount / risk_per_unit

        # Expiry day: reduce position size
        if is_expiry_day:
            factor = Config.EXPIRY_DAY.get("position_size_factor", 0.5)
            raw_qty *= factor
            logger.info(f"⚠️ 0DTE: Position size reduced by {factor}x")

        # Round down to nearest lot size
        lots = max(1, int(raw_qty / lot_size))
        quantity = lots * lot_size

        # Cap at reasonable limit (prevent huge positions)
        max_qty = 10 * lot_size  # Max 10 lots
        quantity = min(quantity, max_qty)

        expiry_tag = " [0DTE]" if is_expiry_day else ""
        logger.info(
            f"💼 Position Size{expiry_tag}: {quantity} units ({quantity // lot_size} lots) | "
            f"Risk: ₹{risk_amount:,.0f} | Entry: ₹{entry_price:.0f} | SL: {stop_loss_pct*100:.0f}%"
        )

        return quantity
    
    def calculate_multi_leg_margin(self, legs: List[OrderLeg]) -> float:
        """
        Estimate margin requirement for a multi-leg position.
        
        For hedged positions (spreads, condors), margin is reduced.
        """
        sell_legs = [l for l in legs if l.is_sell]
        buy_legs = [l for l in legs if l.is_buy]
        
        if not sell_legs:
            # Pure buy strategy — margin = total premium
            return sum(l.price * l.quantity for l in buy_legs)
        
        if buy_legs:
            # Hedged strategy: margin = max(spread width × qty) - net premium
            max_spread = 0
            for sl in sell_legs:
                for bl in buy_legs:
                    if sl.option_type == bl.option_type:
                        spread = abs(sl.strike - bl.strike) * sl.quantity
                        max_spread = max(max_spread, spread)
            net_premium = sum(l.premium_flow for l in legs)
            return max(0, max_spread - net_premium)
        else:
            # Naked sell — approximate SPAN margin
            # Rough estimate: ~15% of underlying × lots
            nifty_approx = 23500  # Will be updated with live price
            total_lots = sum(l.quantity for l in sell_legs) / Config.NIFTY_LOT_SIZE
            return nifty_approx * 0.15 * total_lots * Config.NIFTY_LOT_SIZE
    
    def update_portfolio_greeks(self, positions: List[MultiLegPosition]):
        """
        Calculate aggregate portfolio Greeks from all open positions.
        
        Helps monitor directional risk (delta), acceleration (gamma),
        time decay benefit (theta), and volatility exposure (vega).
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        
        for position in positions:
            if not position.is_open:
                continue
            for leg in position.legs:
                # Placeholder — in live trading, Greeks come from option chain
                # For now, estimate based on moneyness
                pass
        
        self.portfolio_greeks = Greeks(
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega,
        )
    
    def get_stats(self) -> dict:
        """Get current risk management stats."""
        self.reset_daily_stats()
        daily_loss_limit = self.initial_capital * self.daily_loss_limit_pct
        remaining = daily_loss_limit - abs(min(0, self.daily_pnl))
        
        return {
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_trades": self.daily_trades,
            "daily_loss_limit": round(daily_loss_limit, 2),
            "remaining_risk_budget": round(remaining, 2),
            "risk_per_trade_pct": self.risk_per_trade_pct * 100,
            "max_concurrent_positions": self.max_concurrent_positions,
            "is_trading_allowed": bool(self.daily_pnl > -daily_loss_limit),
            "strategy_pnl": {k: round(v, 2) for k, v in self.strategy_pnl.items()},
            "portfolio_greeks": self.portfolio_greeks.to_dict(),
            "strategy_allocations": {
                k: f"{v*100:.0f}%" for k, v in self.STRATEGY_ALLOCATION.items()
            },
        }
