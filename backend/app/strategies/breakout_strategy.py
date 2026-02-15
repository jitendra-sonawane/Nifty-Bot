"""
Breakout Strategy for Nifty 50 Options.

A momentum-based option buying strategy that identifies breakout
levels using support/resistance and volume confirmation.

Entry Logic:
- Buy CE when price breaks above resistance with volume spike
- Buy PE when price breaks below support with volume spike

Exit Logic:
- Trailing stop loss based on ATR
- Fixed risk:reward target (default 1:2)
- Time-based exit before market close

Uses the existing StrategyEngine's calculate_support_resistance()
and detect_breakout() methods for signal generation.
"""

import datetime
import logging
from typing import Dict, List

from app.core.config import Config
from app.core.models import (
    StrategySignal,
    OrderLeg,
    MultiLegPosition,
    SignalAction,
    OptionType,
    TransactionType,
)
from app.core.option_chain import OptionChainManager
from app.strategies.base_strategy import BaseStrategy, ExitCondition, is_entry_time, is_market_hours

logger = logging.getLogger(__name__)


class BreakoutStrategy(BaseStrategy):
    """
    Breakout Strategy — Momentum-based option buying.
    
    Best when:
    - Strong volume spike at support/resistance levels
    - Clear breakout on 15-minute chart
    - Moderate to high IV (for momentum continuation)
    
    Risk Profile:
    - Limited risk (option buying — max loss = premium paid)
    - Potentially high reward (momentum moves)
    - Requires accurate breakout detection
    - Quick exit if breakout fails (false breakout protection)
    """
    
    def __init__(self):
        self.params = dict(Config.BREAKOUT)
    
    @property
    def name(self) -> str:
        return "breakout"
    
    @property
    def display_name(self) -> str:
        return "Breakout Momentum"
    
    @property
    def description(self) -> str:
        return ("Buys CE/PE on support/resistance breakout with volume confirmation. "
                "Uses trailing SL and 1:2 risk-reward target.")
    
    @property
    def strategy_type(self) -> str:
        return "debit"
    
    def get_config(self) -> Dict:
        return dict(self.params)
    
    def update_config(self, params: Dict) -> None:
        self.params.update(params)
    
    def generate_signal(
        self,
        spot_price: float,
        chain: OptionChainManager,
        indicators: Dict,
        current_time: datetime.datetime = None,
    ) -> StrategySignal:
        """
        Generate Breakout entry signal.
        
        Entry requires:
        1. Clean breakout detected (from existing StrategyEngine)
        2. Volume spike confirmation (volume > avg_volume × multiplier)
        3. Market hours + past entry time
        """
        if current_time is None:
            current_time = datetime.datetime.now()
        
        hold_signal = StrategySignal(
            strategy_name=self.name,
            action=SignalAction.HOLD,
            reasoning="No breakout detected",
        )
        
        if not is_market_hours(current_time):
            hold_signal.reasoning = "Market closed"
            return hold_signal
        
        if not is_entry_time(self.params["entry_time"], current_time):
            hold_signal.reasoning = f"Before entry time ({self.params['entry_time']})"
            return hold_signal

        # ── Block on expiry day (0DTE false breakouts are common) ────
        if Config.EXPIRY_DAY.get("block_breakout", True):
            # Check if today is Thursday (Nifty weekly expiry)
            if current_time.weekday() == 3:  # Thursday
                hold_signal.reasoning = "0DTE: Breakout blocked on expiry day (gamma trap risk)"
                return hold_signal

        # ── Check for breakout ────────────────────────────────────────
        breakout = indicators.get("breakout", {})
        is_breakout = breakout.get("is_breakout", False)
        breakout_type = breakout.get("breakout_type")  # "UPSIDE" or "DOWNSIDE"
        breakout_strength = breakout.get("strength", 0)
        breakout_level = breakout.get("breakout_level", 0)
        
        if not is_breakout or not breakout_type:
            hold_signal.reasoning = "No active breakout"
            return hold_signal
        
        # ── Volume confirmation ───────────────────────────────────────
        current_volume = indicators.get("current_volume", 0)
        avg_volume = indicators.get("avg_volume", 1)
        volume_ratio = current_volume / max(avg_volume, 1)
        
        if volume_ratio < self.params["volume_multiplier"]:
            hold_signal.reasoning = (
                f"Breakout without volume: ratio {volume_ratio:.1f}x "
                f"(need {self.params['volume_multiplier']}x)"
            )
            return hold_signal
        
        # ── Build legs based on breakout direction ────────────────────
        if breakout_type == "UPSIDE":
            legs = self._build_bullish_legs(spot_price, chain)
            direction = "🔺 Upside Breakout"
        else:
            legs = self._build_bearish_legs(spot_price, chain)
            direction = "🔻 Downside Breakout"
        
        if not legs:
            hold_signal.reasoning = "Cannot build legs — missing chain data"
            return hold_signal
        
        max_risk = self.calculate_max_risk(legs)
        target_rr = self.params["target_rr_ratio"]
        max_reward = max_risk * target_rr
        
        atr = indicators.get("atr", 0)
        
        reasoning = (
            f"{direction} | "
            f"Spot: {spot_price:.0f} | Level: {breakout_level:.0f} | "
            f"Strength: {breakout_strength:.2%} | Vol: {volume_ratio:.1f}x | "
            f"ATR: {atr:.0f} | "
            f"Premium: ₹{legs[0].price:.0f} | R:R = 1:{target_rr}"
        )
        
        return StrategySignal(
            strategy_name=self.name,
            action=SignalAction.ENTER,
            legs=legs,
            reasoning=reasoning,
            confidence=min(1.0, volume_ratio / 3 + breakout_strength * 2),
            max_risk=max_risk,
            max_reward=max_reward,
            timestamp=current_time,
        )
    
    def _build_bullish_legs(self, spot_price: float, chain: OptionChainManager) -> List[OrderLeg]:
        """Buy ATM Call for upside breakout."""
        atm_entry = chain.get_atm_entry()
        
        if not atm_entry or atm_entry.ce_price <= 0:
            return []
        
        lots = min(self.params["max_lots"], 4)
        qty = lots * Config.NIFTY_LOT_SIZE
        
        return [
            OrderLeg(
                instrument_key=atm_entry.ce_instrument_key,
                strike=chain.atm_strike,
                option_type=OptionType.CE,
                transaction_type=TransactionType.BUY,
                quantity=qty,
                price=atm_entry.ce_price,
                greeks=atm_entry.ce_greeks,
            ),
        ]
    
    def _build_bearish_legs(self, spot_price: float, chain: OptionChainManager) -> List[OrderLeg]:
        """Buy ATM Put for downside breakout."""
        atm_entry = chain.get_atm_entry()
        
        if not atm_entry or atm_entry.pe_price <= 0:
            return []
        
        lots = min(self.params["max_lots"], 4)
        qty = lots * Config.NIFTY_LOT_SIZE
        
        return [
            OrderLeg(
                instrument_key=atm_entry.pe_instrument_key,
                strike=chain.atm_strike,
                option_type=OptionType.PE,
                transaction_type=TransactionType.BUY,
                quantity=qty,
                price=atm_entry.pe_price,
                greeks=atm_entry.pe_greeks,
            ),
        ]
    
    def get_exit_conditions(self, position: MultiLegPosition) -> ExitCondition:
        """
        Breakout exit rules:
        - Trailing stop loss (protect gains on momentum moves)
        - Target: 1:2 risk-reward ratio
        - Time exit: 15:15
        """
        premium_paid = abs(position.net_entry_premium)
        target = premium_paid * self.params["target_rr_ratio"]
        
        return ExitCondition(
            target_pnl=target,
            stop_loss_pnl=-premium_paid,  # Max loss = premium paid
            exit_time=self.params["exit_time"],
            trailing_sl=True,
            trailing_sl_pct=0.40,  # Trail at 40% of peak profit
        )
    
    def calculate_max_risk(self, legs: List[OrderLeg]) -> float:
        """Max risk = premium paid (option buying)."""
        if not legs:
            return 0
        return sum(leg.price * leg.quantity for leg in legs if leg.is_buy)
    
    def calculate_max_reward(self, legs: List[OrderLeg]) -> float:
        """Theoretical max reward is unlimited, but we target R:R ratio."""
        max_risk = self.calculate_max_risk(legs)
        return max_risk * self.params["target_rr_ratio"]
