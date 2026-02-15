"""
Short Straddle Strategy for Nifty 50.

A Short Straddle sells ATM Call and ATM Put simultaneously,
collecting maximum premium from theta decay. Best for
expiry-day trading when Nifty is expected to stay flat.

Structure:
  1. SELL ATM Call
  2. SELL ATM Put

Max Profit = Total premium collected
Max Loss   = Unlimited (uncapped risk — use strict SL)
Breakeven  = ATM ± total premium per unit

Risk Management:
- Strict stop loss based on Nifty point movement
- Time-based exit before close
- Adjustment: shift untested side if Nifty moves beyond threshold
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


class ShortStraddleStrategy(BaseStrategy):
    """
    Short Straddle — ATM option selling for theta decay.
    
    Best when:
    - Expecting low movement on the day (range-bound)
    - High IV (more premium to collect)
    - Expiry day (maximum theta decay)
    
    Risk Profile:
    - Unlimited risk (use strict SL)
    - Limited reward (net premium)
    - Very high theta positive
    - Delta neutral at entry
    """
    
    def __init__(self):
        self.params = dict(Config.SHORT_STRADDLE)
    
    @property
    def name(self) -> str:
        return "short_straddle"
    
    @property
    def display_name(self) -> str:
        return "Short Straddle"
    
    @property
    def description(self) -> str:
        return ("Sells ATM CE + PE for maximum theta decay. "
                "Profits when Nifty stays near ATM. Best on expiry days.")
    
    @property
    def strategy_type(self) -> str:
        return "credit"
    
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
        intelligence_context: Dict = None,
    ) -> StrategySignal:
        """
        Generate Short Straddle entry signal.

        Entry conditions:
        1. Market hours and past entry time
        2. Market regime must be RANGING (not TRENDING or HIGH_VOLATILITY)
        3. VIX must be below 18 (straddle has unlimited risk — stricter than condor)
        4. RSI near neutral (30-70) — no runaway trend
        5. Sufficient ATM premium
        """
        if current_time is None:
            current_time = datetime.datetime.now()

        hold_signal = StrategySignal(
            strategy_name=self.name,
            action=SignalAction.HOLD,
            reasoning="Waiting for conditions",
        )

        if not is_market_hours(current_time):
            hold_signal.reasoning = "Market closed"
            return hold_signal

        if not is_entry_time(self.params["entry_time"], current_time):
            hold_signal.reasoning = f"Before entry time ({self.params['entry_time']})"
            return hold_signal

        # ── Regime gate: block in TRENDING or HIGH_VOLATILITY ────────
        # Short Straddle has UNLIMITED risk — regime check is mandatory
        if intelligence_context:
            regime_ctx = intelligence_context.get("market_regime", {})
            regime = regime_ctx.get("regime", "RANGING")
            if regime == "TRENDING":
                hold_signal.reasoning = (
                    f"❌ Regime=TRENDING (ADX:{regime_ctx.get('adx', '-'):.0f}) — "
                    f"Short Straddle has unlimited loss in trending markets. Blocked."
                )
                return hold_signal
            if regime == "HIGH_VOLATILITY":
                hold_signal.reasoning = (
                    f"❌ Regime=HIGH_VOLATILITY — Short Straddle is extremely dangerous in "
                    f"high-vol regime. Blocked."
                )
                return hold_signal

        # ── VIX gate: stricter than Iron Condor (unlimited risk) ──────
        vix = indicators.get("vix")
        if vix is not None and vix > 18:
            hold_signal.reasoning = (
                f"❌ VIX={vix:.1f} > 18 — Short Straddle blocked. "
                f"Elevated fear = gap risk on unlimited-loss position."
            )
            return hold_signal

        # ── Time-of-day gate: avoid opening + expiry last 30min ───────
        opening_end = current_time.replace(hour=9, minute=45, second=0)
        late_close = current_time.replace(hour=15, minute=0, second=0)
        if current_time < opening_end:
            hold_signal.reasoning = "Waiting for opening volatility to settle (entry after 09:45)"
            return hold_signal
        if current_time >= late_close:
            hold_signal.reasoning = "Avoiding last 30 min before close — gamma risk too high"
            return hold_signal
        
        # ── Build legs ────────────────────────────────────────────────
        legs = self._build_legs(spot_price, chain)
        if not legs:
            hold_signal.reasoning = "Cannot build legs — missing chain data"
            return hold_signal
        
        # ── Check premium quality ─────────────────────────────────────
        net_premium = sum(leg.premium_flow for leg in legs)
        total_premium_per_unit = sum(leg.price for leg in legs)
        
        # Need at least some premium per unit
        if total_premium_per_unit < 50:
            hold_signal.reasoning = f"ATM premium too low: ₹{total_premium_per_unit:.0f}/unit"
            return hold_signal
        
        # ── Check for strong trend (avoid) ────────────────────────────
        rsi = indicators.get("rsi", 50)
        supertrend = indicators.get("supertrend_direction", None)
        
        # Relax RSI check slightly for straddle — wider range than Iron Condor
        if rsi < 30 or rsi > 70:
            hold_signal.reasoning = f"RSI {rsi:.1f} — strong trend, too risky for straddle"
            return hold_signal
        
        max_risk = self.calculate_max_risk(legs)
        max_reward = self.calculate_max_reward(legs)
        
        sl_points = self.params["sl_points"]
        
        reasoning = (
            f"📊 Short Straddle Entry | "
            f"ATM: {chain.atm_strike:.0f} | Spot: {spot_price:.0f} | "
            f"CE: ₹{legs[0].price:.0f} + PE: ₹{legs[1].price:.0f} = ₹{total_premium_per_unit:.0f}/unit | "
            f"Total Premium: ₹{net_premium:.0f} | SL: {sl_points} pts | RSI: {rsi:.1f}"
        )
        
        return StrategySignal(
            strategy_name=self.name,
            action=SignalAction.ENTER,
            legs=legs,
            reasoning=reasoning,
            confidence=0.7 if 40 <= rsi <= 60 else 0.5,
            max_risk=max_risk,
            max_reward=max_reward,
            timestamp=current_time,
        )
    
    def _build_legs(self, spot_price: float, chain: OptionChainManager) -> List[OrderLeg]:
        """Build the 2 legs: sell ATM CE + sell ATM PE."""
        straddle_strikes = chain.get_straddle_strikes()
        atm_entry = chain.get_entry(straddle_strikes["ce_strike"])
        
        if not atm_entry:
            return []
        
        lots = min(self.params["max_lots"], 4)
        qty = lots * Config.NIFTY_LOT_SIZE
        
        legs = [
            # Leg 1: Sell ATM CE
            OrderLeg(
                instrument_key=atm_entry.ce_instrument_key,
                strike=straddle_strikes["ce_strike"],
                option_type=OptionType.CE,
                transaction_type=TransactionType.SELL,
                quantity=qty,
                price=atm_entry.ce_price,
                greeks=atm_entry.ce_greeks,
            ),
            # Leg 2: Sell ATM PE
            OrderLeg(
                instrument_key=atm_entry.pe_instrument_key,
                strike=straddle_strikes["pe_strike"],
                option_type=OptionType.PE,
                transaction_type=TransactionType.SELL,
                quantity=qty,
                price=atm_entry.pe_price,
                greeks=atm_entry.pe_greeks,
            ),
        ]
        
        return legs
    
    def check_adjustment(
        self,
        position: MultiLegPosition,
        current_spot: float,
        chain: OptionChainManager,
    ) -> StrategySignal:
        """
        Check if straddle needs adjustment.
        
        If Nifty moves beyond adjustment_threshold from entry,
        shift the untested (profitable) side closer to collect more premium.
        """
        entry_atm = position.legs[0].strike  # ATM at entry
        movement = current_spot - entry_atm
        threshold = self.params["adjustment_threshold"]
        
        if abs(movement) < threshold:
            return StrategySignal(
                strategy_name=self.name,
                action=SignalAction.HOLD,
                reasoning=f"Movement {movement:.0f} pts < threshold {threshold} pts",
            )
        
        # Need adjustment — shift the winning side
        chain.update(current_spot)
        new_atm = chain.atm_strike
        
        return StrategySignal(
            strategy_name=self.name,
            action=SignalAction.ADJUST,
            reasoning=(
                f"⚡ Adjustment needed: Nifty moved {movement:.0f} pts from entry. "
                f"New ATM: {new_atm}. Consider rolling untested side."
            ),
        )
    
    def get_exit_conditions(self, position: MultiLegPosition) -> ExitCondition:
        """
        Short Straddle exit rules:
        - Target: 30% of collected premium
        - SL: based on Nifty point movement (translated to premium)
        - Time exit: 15:15
        """
        net_premium = abs(position.net_entry_premium)
        target = net_premium * self.params["target_pct"]
        
        # Approximate SL: if Nifty moves sl_points, the losing leg price
        # roughly increases by that amount per unit
        qty = position.legs[0].quantity if position.legs else Config.NIFTY_LOT_SIZE
        sl_premium = self.params["sl_points"] * qty
        
        return ExitCondition(
            target_pnl=target,
            stop_loss_pnl=-sl_premium,
            exit_time=self.params["exit_time"],
        )
    
    def calculate_max_risk(self, legs: List[OrderLeg]) -> float:
        """
        Theoretical max risk is unlimited for a naked straddle.
        We cap it at SL-based risk for practical purposes.
        """
        if not legs:
            return 0
        qty = legs[0].quantity
        return self.params["sl_points"] * qty
    
    def calculate_max_reward(self, legs: List[OrderLeg]) -> float:
        """Max reward = total premium collected."""
        return max(0, sum(leg.premium_flow for leg in legs))
