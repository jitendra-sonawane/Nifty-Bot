"""
Base Strategy — Abstract interface for all option strategies.

All strategies inherit from BaseStrategy and implement:
- Signal generation (when to enter/exit)
- Leg construction (which options to buy/sell)
- Exit condition evaluation
- Risk/reward calculation
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import datetime
import logging

from app.core.models import (
    StrategySignal,
    OrderLeg,
    MultiLegPosition,
    SignalAction,
    OptionType,
    TransactionType,
)
from app.core.option_chain import OptionChainManager
from app.core.config import Config

logger = logging.getLogger(__name__)


class ExitCondition:
    """Defines when a position should be exited."""
    
    def __init__(
        self,
        target_pnl: float = 0,        # Target P&L in ₹
        stop_loss_pnl: float = 0,      # Stop loss P&L in ₹ (negative)
        exit_time: str = "15:15",       # Time-based exit (HH:MM)
        trailing_sl: bool = False,      # Enable trailing stop loss
        trailing_sl_pct: float = 0.0,   # Trailing SL as % of peak profit
    ):
        self.target_pnl = target_pnl
        self.stop_loss_pnl = stop_loss_pnl
        self.exit_time = exit_time
        self.trailing_sl = trailing_sl
        self.trailing_sl_pct = trailing_sl_pct
        self._peak_pnl: float = 0.0
    
    def should_exit(self, current_pnl: float, current_time: datetime.datetime) -> tuple:
        """
        Check if exit conditions are met.
        
        Returns:
            (should_exit: bool, reason: str)
        """
        # Update peak P&L for trailing stop
        if current_pnl > self._peak_pnl:
            self._peak_pnl = current_pnl
        
        # 1. Target hit
        if self.target_pnl > 0 and current_pnl >= self.target_pnl:
            return True, f"🎯 Target hit: ₹{current_pnl:.0f} ≥ ₹{self.target_pnl:.0f}"
        
        # 2. Stop loss hit
        if self.stop_loss_pnl < 0 and current_pnl <= self.stop_loss_pnl:
            return True, f"🛑 Stop loss: ₹{current_pnl:.0f} ≤ ₹{self.stop_loss_pnl:.0f}"
        
        # 3. Trailing stop loss
        if self.trailing_sl and self._peak_pnl > 0:
            trail_threshold = self._peak_pnl * (1 - self.trailing_sl_pct)
            if current_pnl < trail_threshold:
                return True, f"📉 Trailing SL: ₹{current_pnl:.0f} < ₹{trail_threshold:.0f} (peak: ₹{self._peak_pnl:.0f})"
        
        # 4. Time-based exit
        exit_h, exit_m = map(int, self.exit_time.split(":"))
        if current_time.hour > exit_h or (current_time.hour == exit_h and current_time.minute >= exit_m):
            return True, f"⏰ Time exit at {self.exit_time}"
        
        return False, ""


def is_market_hours(current_time: datetime.datetime = None) -> bool:
    """Check if current time is within market hours (9:15 AM - 3:30 PM IST)."""
    if current_time is None:
        current_time = datetime.datetime.now()
    
    market_open = current_time.replace(hour=9, minute=15, second=0)
    market_close = current_time.replace(hour=15, minute=30, second=0)
    
    return market_open <= current_time <= market_close


def is_entry_time(entry_time_str: str, current_time: datetime.datetime = None) -> bool:
    """Check if current time is past the configured entry time."""
    if current_time is None:
        current_time = datetime.datetime.now()
    
    h, m = map(int, entry_time_str.split(":"))
    entry_time = current_time.replace(hour=h, minute=m, second=0)
    
    return current_time >= entry_time


class BaseStrategy(ABC):
    """
    Abstract base class for all option trading strategies.
    
    Subclasses must implement:
    - name: Strategy identifier
    - generate_signal: Analyze market and decide to enter/exit/hold
    - get_legs: Construct option legs for the trade
    - get_exit_conditions: Define exit rules for open positions
    - calculate_max_risk: Maximum possible loss
    - calculate_max_reward: Maximum possible profit
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier."""
        ...
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable strategy name."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Brief strategy description."""
        ...
    
    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """'credit' or 'debit' — whether strategy collects or pays premium."""
        ...
    
    @abstractmethod
    def generate_signal(
        self,
        spot_price: float,
        chain: OptionChainManager,
        indicators: Dict,
        current_time: datetime.datetime = None,
        intelligence_context: Dict = None,
    ) -> StrategySignal:
        """
        Analyze market conditions and generate a trading signal.

        Args:
            spot_price: Current Nifty 50 price
            chain: Option chain manager with current data
            indicators: Technical indicator values from StrategyEngine
            current_time: Current timestamp (for time-based rules)
            intelligence_context: AI-driven market regime and context data

        Returns:
            StrategySignal with action (ENTER/EXIT/HOLD) and legs
        """
        ...
    
    @abstractmethod
    def get_exit_conditions(self, position: MultiLegPosition) -> ExitCondition:
        """
        Get exit conditions for an open position.
        
        Args:
            position: The current open position
        
        Returns:
            ExitCondition object defining target, SL, and time rules
        """
        ...
    
    @abstractmethod
    def calculate_max_risk(self, legs: List[OrderLeg]) -> float:
        """
        Calculate maximum possible loss for a set of legs.
        
        Args:
            legs: Order legs of the strategy
        
        Returns:
            Maximum risk in ₹ (positive number)
        """
        ...
    
    @abstractmethod
    def calculate_max_reward(self, legs: List[OrderLeg]) -> float:
        """
        Calculate maximum possible profit for a set of legs.
        
        Args:
            legs: Order legs of the strategy
        
        Returns:
            Maximum reward in ₹ (positive number)
        """
        ...
    
    def get_config(self) -> Dict:
        """Get strategy-specific configuration. Override in subclass."""
        return {}
    
    def update_config(self, params: Dict) -> None:
        """Update strategy parameters. Override in subclass."""
        pass
    
    def get_info(self) -> Dict:
        """Get strategy summary for API responses."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "strategy_type": self.strategy_type,
            "config": self.get_config(),
        }
