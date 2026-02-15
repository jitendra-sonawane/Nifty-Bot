"""
Bull Call Spread / Bear Put Spread Strategy for Nifty 50.

Directional debit spreads that use the existing StrategyEngine's
technical signals (BUY_CE / BUY_PE) to determine direction.

Bull Call Spread (bullish signal):
  1. BUY ATM Call
  2. SELL OTM Call (ATM + spread_width)
  → Reduces cost vs naked call, with capped risk and reward

Bear Put Spread (bearish signal):
  1. BUY ATM Put
  2. SELL OTM Put (ATM - spread_width)
  → Reduces cost vs naked put, with capped risk and reward

Max Profit = Spread width - Net debit paid
Max Loss   = Net debit paid
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


class BullCallSpreadStrategy(BaseStrategy):
    """
    Bull Call Spread — Directional bullish strategy.
    
    Triggered by: BUY_CE signal from StrategyEngine
    
    Best when:
    - Strong bullish technical signal (RSI > 55, EMA crossover up)
    - Moderate IV (not too expensive to buy)
    - Clear support holding below
    """
    
    def __init__(self):
        self.params = dict(Config.DIRECTIONAL_SPREAD)
    
    @property
    def name(self) -> str:
        return "bull_call_spread"
    
    @property
    def display_name(self) -> str:
        return "Bull Call Spread"
    
    @property
    def description(self) -> str:
        return ("Buys ATM Call + sells OTM Call. Directional bullish play "
                "with reduced cost and capped risk. Uses technical signals for entry.")
    
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
        Generate Bull Call Spread entry signal.
        
        Entry requires:
        - BUY_CE signal from indicator engine (or RSI > 55 + bullish supertrend)
        - Market hours + past entry time
        - Minimum signal confidence
        """
        if current_time is None:
            current_time = datetime.datetime.now()
        
        hold_signal = StrategySignal(
            strategy_name=self.name,
            action=SignalAction.HOLD,
            reasoning="No bullish signal",
        )
        
        if not is_market_hours(current_time):
            hold_signal.reasoning = "Market closed"
            return hold_signal
        
        if not is_entry_time(self.params["entry_time"], current_time):
            hold_signal.reasoning = f"Before entry time ({self.params['entry_time']})"
            return hold_signal
        
        # ── Check for bullish signal ──────────────────────────────────
        signal = indicators.get("signal", "HOLD")
        confidence = indicators.get("confidence", 0)
        rsi = indicators.get("rsi", 50)
        
        is_bullish = (
            signal == "BUY_CE"
            or (rsi > 55 and indicators.get("supertrend_direction") == "UP")
        )
        
        if not is_bullish:
            hold_signal.reasoning = f"No bullish signal (signal={signal}, RSI={rsi:.1f})"
            return hold_signal
        
        if confidence < self.params["min_signal_confidence"]:
            hold_signal.reasoning = f"Low confidence: {confidence:.2f} < {self.params['min_signal_confidence']}"
            return hold_signal
        
        # ── Build legs ────────────────────────────────────────────────
        legs = self._build_legs(spot_price, chain)
        if not legs:
            hold_signal.reasoning = "Cannot build legs — missing chain data"
            return hold_signal
        
        max_risk = self.calculate_max_risk(legs)
        max_reward = self.calculate_max_reward(legs)
        net_debit = abs(sum(leg.premium_flow for leg in legs))
        
        reasoning = (
            f"🐂 Bull Call Spread | "
            f"Buy {legs[0].strike} CE @ ₹{legs[0].price:.0f} + "
            f"Sell {legs[1].strike} CE @ ₹{legs[1].price:.0f} | "
            f"Net Debit: ₹{net_debit:.0f} | RSI: {rsi:.1f} | "
            f"Max Risk: ₹{max_risk:.0f} | Max Reward: ₹{max_reward:.0f}"
        )
        
        return StrategySignal(
            strategy_name=self.name,
            action=SignalAction.ENTER,
            legs=legs,
            reasoning=reasoning,
            confidence=confidence,
            max_risk=max_risk,
            max_reward=max_reward,
            timestamp=current_time,
        )
    
    def _build_legs(self, spot_price: float, chain: OptionChainManager) -> List[OrderLeg]:
        """Build Bull Call Spread: Buy ATM CE + Sell OTM CE."""
        spread_strikes = chain.get_spread_strikes("bull", self.params["spread_width"])
        
        buy_entry = chain.get_entry(spread_strikes["buy_strike"])
        sell_entry = chain.get_entry(spread_strikes["sell_strike"])
        
        if not buy_entry or not sell_entry:
            return []
        
        lots = min(self.params["max_lots"], 4)
        qty = lots * Config.NIFTY_LOT_SIZE
        
        return [
            OrderLeg(
                instrument_key=buy_entry.ce_instrument_key,
                strike=spread_strikes["buy_strike"],
                option_type=OptionType.CE,
                transaction_type=TransactionType.BUY,
                quantity=qty,
                price=buy_entry.ce_price,
                greeks=buy_entry.ce_greeks,
            ),
            OrderLeg(
                instrument_key=sell_entry.ce_instrument_key,
                strike=spread_strikes["sell_strike"],
                option_type=OptionType.CE,
                transaction_type=TransactionType.SELL,
                quantity=qty,
                price=sell_entry.ce_price,
                greeks=sell_entry.ce_greeks,
            ),
        ]
    
    def get_exit_conditions(self, position: MultiLegPosition) -> ExitCondition:
        net_debit = abs(position.net_entry_premium)
        max_profit = position.max_reward
        
        return ExitCondition(
            target_pnl=max_profit * self.params["target_pct"],
            stop_loss_pnl=-net_debit * self.params["sl_pct"],
            exit_time=self.params["exit_time"],
        )
    
    def calculate_max_risk(self, legs: List[OrderLeg]) -> float:
        """Max risk = net debit paid."""
        if len(legs) < 2:
            return 0
        net_debit = abs(sum(leg.premium_flow for leg in legs))
        return net_debit
    
    def calculate_max_reward(self, legs: List[OrderLeg]) -> float:
        """Max reward = (spread width × qty) - net debit."""
        if len(legs) < 2:
            return 0
        spread_width = abs(legs[1].strike - legs[0].strike) * legs[0].quantity
        net_debit = abs(sum(leg.premium_flow for leg in legs))
        return max(0, spread_width - net_debit)


class BearPutSpreadStrategy(BaseStrategy):
    """
    Bear Put Spread — Directional bearish strategy.
    
    Triggered by: BUY_PE signal from StrategyEngine
    
    Best when:
    - Strong bearish technical signal (RSI < 45, EMA crossover down)
    - Resistance holding above
    - Moderate IV
    """
    
    def __init__(self):
        self.params = dict(Config.DIRECTIONAL_SPREAD)
    
    @property
    def name(self) -> str:
        return "bear_put_spread"
    
    @property
    def display_name(self) -> str:
        return "Bear Put Spread"
    
    @property
    def description(self) -> str:
        return ("Buys ATM Put + sells OTM Put. Directional bearish play "
                "with reduced cost and capped risk. Uses technical signals for entry.")
    
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
        if current_time is None:
            current_time = datetime.datetime.now()
        
        hold_signal = StrategySignal(
            strategy_name=self.name,
            action=SignalAction.HOLD,
            reasoning="No bearish signal",
        )
        
        if not is_market_hours(current_time):
            hold_signal.reasoning = "Market closed"
            return hold_signal
        
        if not is_entry_time(self.params["entry_time"], current_time):
            hold_signal.reasoning = f"Before entry time ({self.params['entry_time']})"
            return hold_signal
        
        # ── Check for bearish signal ──────────────────────────────────
        signal = indicators.get("signal", "HOLD")
        confidence = indicators.get("confidence", 0)
        rsi = indicators.get("rsi", 50)
        
        is_bearish = (
            signal == "BUY_PE"
            or (rsi < 45 and indicators.get("supertrend_direction") == "DOWN")
        )
        
        if not is_bearish:
            hold_signal.reasoning = f"No bearish signal (signal={signal}, RSI={rsi:.1f})"
            return hold_signal
        
        if confidence < self.params["min_signal_confidence"]:
            hold_signal.reasoning = f"Low confidence: {confidence:.2f}"
            return hold_signal
        
        # ── Build legs ────────────────────────────────────────────────
        legs = self._build_legs(spot_price, chain)
        if not legs:
            hold_signal.reasoning = "Cannot build legs — missing chain data"
            return hold_signal
        
        max_risk = self.calculate_max_risk(legs)
        max_reward = self.calculate_max_reward(legs)
        net_debit = abs(sum(leg.premium_flow for leg in legs))
        
        reasoning = (
            f"🐻 Bear Put Spread | "
            f"Buy {legs[0].strike} PE @ ₹{legs[0].price:.0f} + "
            f"Sell {legs[1].strike} PE @ ₹{legs[1].price:.0f} | "
            f"Net Debit: ₹{net_debit:.0f} | RSI: {rsi:.1f} | "
            f"Max Risk: ₹{max_risk:.0f} | Max Reward: ₹{max_reward:.0f}"
        )
        
        return StrategySignal(
            strategy_name=self.name,
            action=SignalAction.ENTER,
            legs=legs,
            reasoning=reasoning,
            confidence=confidence,
            max_risk=max_risk,
            max_reward=max_reward,
            timestamp=current_time,
        )
    
    def _build_legs(self, spot_price: float, chain: OptionChainManager) -> List[OrderLeg]:
        """Build Bear Put Spread: Buy ATM PE + Sell OTM PE."""
        spread_strikes = chain.get_spread_strikes("bear", self.params["spread_width"])
        
        buy_entry = chain.get_entry(spread_strikes["buy_strike"])
        sell_entry = chain.get_entry(spread_strikes["sell_strike"])
        
        if not buy_entry or not sell_entry:
            return []
        
        lots = min(self.params["max_lots"], 4)
        qty = lots * Config.NIFTY_LOT_SIZE
        
        return [
            OrderLeg(
                instrument_key=buy_entry.pe_instrument_key,
                strike=spread_strikes["buy_strike"],
                option_type=OptionType.PE,
                transaction_type=TransactionType.BUY,
                quantity=qty,
                price=buy_entry.pe_price,
                greeks=buy_entry.pe_greeks,
            ),
            OrderLeg(
                instrument_key=sell_entry.pe_instrument_key,
                strike=spread_strikes["sell_strike"],
                option_type=OptionType.PE,
                transaction_type=TransactionType.SELL,
                quantity=qty,
                price=sell_entry.pe_price,
                greeks=sell_entry.pe_greeks,
            ),
        ]
    
    def get_exit_conditions(self, position: MultiLegPosition) -> ExitCondition:
        net_debit = abs(position.net_entry_premium)
        max_profit = position.max_reward
        
        return ExitCondition(
            target_pnl=max_profit * self.params["target_pct"],
            stop_loss_pnl=-net_debit * self.params["sl_pct"],
            exit_time=self.params["exit_time"],
        )
    
    def calculate_max_risk(self, legs: List[OrderLeg]) -> float:
        if len(legs) < 2:
            return 0
        return abs(sum(leg.premium_flow for leg in legs))
    
    def calculate_max_reward(self, legs: List[OrderLeg]) -> float:
        if len(legs) < 2:
            return 0
        spread_width = abs(legs[0].strike - legs[1].strike) * legs[0].quantity
        net_debit = abs(sum(leg.premium_flow for leg in legs))
        return max(0, spread_width - net_debit)
