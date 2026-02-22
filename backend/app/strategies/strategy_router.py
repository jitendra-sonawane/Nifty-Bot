"""
Strategy Router — Dispatches signal generation to the appropriate strategy
based on Config.ACTIVE_STRATEGY.

Single-leg strategies ("single_leg") use the existing StrategyEngine.check_signal() path.
Multi-leg strategies use their respective BaseStrategy.generate_signal() method,
converting StrategySignal → signal_data dict for TradeExecutor.execute_spread_trade().
"""

import datetime
import logging
from typing import Dict, Optional

from app.core.config import Config
from app.core.option_chain import OptionChainManager
from app.core.models import SignalAction
from app.strategies.base_strategy import BaseStrategy
from app.strategies.iron_condor import IronCondorStrategy
from app.strategies.short_straddle import ShortStraddleStrategy
from app.strategies.bull_bear_spread import BullCallSpreadStrategy, BearPutSpreadStrategy
from app.strategies.breakout_strategy import BreakoutStrategy

logger = logging.getLogger(__name__)

# Registry: strategy_name → class
STRATEGY_CLASSES: Dict[str, type] = {
    "iron_condor": IronCondorStrategy,
    "short_straddle": ShortStraddleStrategy,
    "bull_call_spread": BullCallSpreadStrategy,
    "bear_put_spread": BearPutSpreadStrategy,
    "breakout": BreakoutStrategy,
}


class StrategyRouter:
    """Routes signal generation to the correct strategy implementation."""

    def __init__(self):
        self._instances: Dict[str, BaseStrategy] = {}
        self._option_chain = OptionChainManager()

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Lazy-instantiate and cache strategy instances."""
        if name not in STRATEGY_CLASSES:
            return None
        if name not in self._instances:
            self._instances[name] = STRATEGY_CLASSES[name]()
            logger.info(f"✅ Instantiated multi-leg strategy: {name}")
        return self._instances[name]

    @property
    def is_multi_leg(self) -> bool:
        """Check if the currently active strategy is multi-leg."""
        return Config.ACTIVE_STRATEGY in Config.MULTI_LEG_STRATEGIES

    def generate_multi_leg_signal(
        self,
        spot_price: float,
        indicators: Dict,
        market_state: Dict,
        intelligence_context: Optional[Dict] = None,
        current_time: Optional[datetime.datetime] = None,
    ) -> Optional[Dict]:
        """
        Generate a multi-leg signal_data dict suitable for execute_spread_trade().

        Returns None if no entry signal, or a dict with "legs" array.
        """
        strategy_name = Config.ACTIVE_STRATEGY
        strategy = self.get_strategy(strategy_name)
        if not strategy:
            logger.warning(f"Unknown multi-leg strategy: {strategy_name}")
            return None

        # Update option chain with current spot price
        self._option_chain.update(spot_price)

        # Generate signal via BaseStrategy interface
        try:
            signal = strategy.generate_signal(
                spot_price=spot_price,
                chain=self._option_chain,
                indicators=indicators,
                current_time=current_time or datetime.datetime.now(),
                intelligence_context=intelligence_context,
            )
        except Exception as e:
            logger.error(f"Error generating signal for {strategy_name}: {e}", exc_info=True)
            return None

        if signal.action != SignalAction.ENTER:
            logger.debug(f"[{strategy_name}] {signal.action.value}: {signal.reasoning}")
            return None

        if not signal.legs:
            logger.warning(f"[{strategy_name}] ENTER signal but no legs built")
            return None

        # Convert StrategySignal legs to signal_data dict for execute_spread_trade()
        legs_data = []
        for leg in signal.legs:
            legs_data.append({
                "instrument_key": leg.instrument_key,
                "quantity": leg.quantity,
                "transaction_type": leg.transaction_type.value,
                "price": leg.price,
                "option_type": leg.option_type.value,
                "strike": leg.strike,
            })

        signal_data = {
            "strategy_name": strategy_name,
            "signal": f"ENTER_{strategy_name.upper()}",
            "legs": legs_data,
            "price": spot_price,
            "timestamp": datetime.datetime.now().isoformat(),
            "reasoning": signal.reasoning,
            "confidence": signal.confidence,
            "max_risk": signal.max_risk,
            "max_reward": signal.max_reward,
            "market_data": market_state,
            "indicators": indicators,
            "intelligence_context": intelligence_context,
        }

        logger.info(
            f"🔀 [{strategy_name}] ENTER signal: {len(legs_data)} legs, "
            f"risk=₹{signal.max_risk:,.0f}, reward=₹{signal.max_reward:,.0f}, "
            f"confidence={signal.confidence:.0%}"
        )
        return signal_data
