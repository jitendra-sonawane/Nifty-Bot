"""
Iron Condor Strategy for Nifty 50.

An Iron Condor is a non-directional, credit strategy that profits
when the market stays within a defined range. It benefits from
theta decay and is ideal for low-to-moderate volatility sessions.

Structure:
  1. SELL OTM Call (ATM + short_offset)
  2. BUY further OTM Call (ATM + short_offset + wing_width)  <- hedge
  3. SELL OTM Put (ATM - short_offset)
  4. BUY further OTM Put (ATM - short_offset - wing_width)   <- hedge

Max Profit = Net premium collected
Max Loss   = Wing width x lot_size - Net premium
Breakeven  = Short strikes +/- net premium per unit
"""

import datetime
import logging
from typing import Dict, List, Optional

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


class IronCondorStrategy(BaseStrategy):
    """
    Iron Condor — Non-directional option selling strategy.

    Best when:
    - IV percentile is moderate to high (> configured minimum)
    - Market is range-bound (no strong trend)
    - Nifty is near max-pain or within recent range
    - DTE > configured minimum (avoids expiry-day gamma risk)

    Risk Profile:
    - Limited risk (hedged with long wings)
    - Limited reward (net premium collected)
    - Profits from time decay (theta positive)
    - Wins when Nifty stays between short strikes
    """

    def __init__(self):
        self.params = dict(Config.IRON_CONDOR)

    @property
    def name(self) -> str:
        return "iron_condor"

    @property
    def display_name(self) -> str:
        return "Iron Condor"

    @property
    def description(self) -> str:
        return ("Non-directional credit strategy. Sells OTM Call + Put spreads. "
                "Profits from theta decay when Nifty stays range-bound.")

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
        Generate Iron Condor entry signal.

        Entry conditions:
        1. Market hours and past entry time
        2. Market regime must be RANGING (not TRENDING or HIGH_VOLATILITY)
        3. VIX must be below configured max
        4. DTE above configured minimum (no expiry-day entries)
        5. IV percentile >= configured minimum
        6. RSI within configured neutral range
        7. Net delta of constructed legs is near-neutral
        8. Sufficient premium available on short strikes
        """
        if current_time is None:
            current_time = datetime.datetime.now()

        # Default: HOLD (do nothing)
        hold_signal = StrategySignal(
            strategy_name=self.name,
            action=SignalAction.HOLD,
            reasoning="Waiting for entry conditions",
        )

        # ── Check basic timing ────────────────────────────────────────
        if not is_market_hours(current_time):
            hold_signal.reasoning = "Market closed"
            return hold_signal

        if not is_entry_time(self.params["entry_time"], current_time):
            hold_signal.reasoning = f"Before entry time ({self.params['entry_time']})"
            return hold_signal

        # ── Regime gate: block in TRENDING or HIGH_VOLATILITY ────────
        if intelligence_context:
            regime_ctx = intelligence_context.get("market_regime", {})
            regime = regime_ctx.get("regime", "RANGING")
            if regime == "TRENDING":
                hold_signal.reasoning = (
                    f"Regime=TRENDING (ADX:{regime_ctx.get('adx', '-'):.0f}) — "
                    f"Iron Condor needs range-bound market. Use breakout/spread strategy instead."
                )
                return hold_signal
            if regime == "HIGH_VOLATILITY":
                hold_signal.reasoning = (
                    f"Regime=HIGH_VOLATILITY (ATR:{regime_ctx.get('atr_pct', '-')}) — "
                    f"Credit strategies are high-risk in volatile markets."
                )
                return hold_signal

        # ── VIX gate: block if fear index too high ────────────────────
        vix_max = self.params["vix_max"]
        vix = indicators.get("vix")
        if vix is not None and vix > vix_max:
            hold_signal.reasoning = (
                f"VIX={vix:.1f} > {vix_max} — Iron Condor blocked. "
                f"High fear reduces theta edge and increases gap risk."
            )
            return hold_signal

        # ── DTE gate: block on expiry day (gamma risk) ────────────────
        dte = chain.days_to_expiry
        min_dte = self.params["min_dte"]
        if dte < min_dte:
            hold_signal.reasoning = (
                f"DTE={dte:.1f} < {min_dte} — Expiry-day gamma risk too high for Iron Condor."
            )
            return hold_signal

        # ── Check IV conditions ───────────────────────────────────────
        iv_percentile = chain.iv_percentile
        if iv_percentile < self.params["iv_percentile_min"]:
            hold_signal.reasoning = (
                f"IV percentile too low: {iv_percentile:.0f}% "
                f"(need >= {self.params['iv_percentile_min']}%)"
            )
            return hold_signal

        # ── Check trend neutrality ────────────────────────────────────
        rsi_lower = self.params["rsi_lower"]
        rsi_upper = self.params["rsi_upper"]
        rsi = indicators.get("rsi", 50)
        if rsi < rsi_lower or rsi > rsi_upper:
            hold_signal.reasoning = (
                f"RSI {rsi:.1f} outside neutral range ({rsi_lower}-{rsi_upper}) "
                f"— not ideal for Iron Condor"
            )
            return hold_signal

        # ── Adjust center strike toward max pain if available ─────────
        center_strike = chain.atm_strike
        max_pain_note = ""
        if intelligence_context:
            oi_ctx = intelligence_context.get("oi_analysis", {})
            max_pain = oi_ctx.get("max_pain_strike")
            if max_pain and abs(max_pain - chain.atm_strike) <= 100:
                # Max pain is within ±100 pts of ATM — use it as center
                center_strike = round(max_pain / Config.NIFTY_STRIKE_STEP) * Config.NIFTY_STRIKE_STEP
                max_pain_note = f" | Center→MaxPain({center_strike:.0f})"

        # ── Build the legs ────────────────────────────────────────────
        legs = self._build_legs(spot_price, chain, center_strike=center_strike)
        if not legs:
            hold_signal.reasoning = "Could not build legs — option chain data missing"
            return hold_signal

        # ── Net delta check: ensure position is near-neutral ──────────
        net_delta = self._calculate_net_delta(legs)
        if net_delta is not None and abs(net_delta) > 0.30:
            hold_signal.reasoning = (
                f"Net delta {net_delta:+.2f} too skewed — "
                f"Iron Condor requires near-neutral delta"
            )
            return hold_signal

        max_risk = self.calculate_max_risk(legs)
        max_reward = self.calculate_max_reward(legs)

        # ── Validate minimum premium ─────────────────────────────────
        net_premium = sum(leg.premium_flow for leg in legs)
        if net_premium <= 0:
            hold_signal.reasoning = f"Insufficient premium collected: Rs.{net_premium:.0f}"
            return hold_signal

        reasoning = (
            f"Iron Condor Entry | "
            f"Spot: {spot_price:.0f} | ATM: {chain.atm_strike:.0f}{max_pain_note} | "
            f"IV%: {iv_percentile:.0f} | RSI: {rsi:.1f} | DTE: {dte:.1f} | "
            f"Premium: Rs.{net_premium:.0f} | "
            f"Max Risk: Rs.{max_risk:.0f} | Max Reward: Rs.{max_reward:.0f}"
        )

        return StrategySignal(
            strategy_name=self.name,
            action=SignalAction.ENTER,
            legs=legs,
            reasoning=reasoning,
            confidence=min(1.0, iv_percentile / 100 * 1.2),
            max_risk=max_risk,
            max_reward=max_reward,
            timestamp=current_time,
        )

    def _build_legs(self, spot_price: float, chain: OptionChainManager, center_strike: float = None) -> List[OrderLeg]:
        """Construct the 4 legs of the Iron Condor, optionally centered on max pain."""
        # If center_strike differs from ATM, temporarily adjust chain for strike calc
        original_atm = chain.atm_strike
        if center_strike and center_strike != chain.atm_strike:
            chain.atm_strike = center_strike

        strikes = chain.get_iron_condor_strikes(
            short_offset=self.params["short_offset"],
            wing_width=self.params["wing_width"],
        )

        # Restore original ATM
        if center_strike and center_strike != original_atm:
            chain.atm_strike = original_atm

        qty = self.params["max_lots"] * Config.NIFTY_LOT_SIZE

        legs = []

        # Leg 1: Sell OTM Call
        short_ce_entry = chain.get_entry(strikes["short_ce"])
        if not short_ce_entry or short_ce_entry.ce_price <= 0:
            logger.warning("Iron Condor: short CE strike %s missing or zero price", strikes["short_ce"])
            return []
        legs.append(OrderLeg(
            instrument_key=short_ce_entry.ce_instrument_key,
            strike=strikes["short_ce"],
            option_type=OptionType.CE,
            transaction_type=TransactionType.SELL,
            quantity=qty,
            price=short_ce_entry.ce_price,
            greeks=short_ce_entry.ce_greeks,
        ))

        # Leg 2: Buy further OTM Call (hedge)
        long_ce_entry = chain.get_entry(strikes["long_ce"])
        if not long_ce_entry:
            logger.warning("Iron Condor: long CE strike %s missing from chain", strikes["long_ce"])
            return []
        legs.append(OrderLeg(
            instrument_key=long_ce_entry.ce_instrument_key,
            strike=strikes["long_ce"],
            option_type=OptionType.CE,
            transaction_type=TransactionType.BUY,
            quantity=qty,
            price=long_ce_entry.ce_price,
            greeks=long_ce_entry.ce_greeks,
        ))

        # Leg 3: Sell OTM Put
        short_pe_entry = chain.get_entry(strikes["short_pe"])
        if not short_pe_entry or short_pe_entry.pe_price <= 0:
            logger.warning("Iron Condor: short PE strike %s missing or zero price", strikes["short_pe"])
            return []
        legs.append(OrderLeg(
            instrument_key=short_pe_entry.pe_instrument_key,
            strike=strikes["short_pe"],
            option_type=OptionType.PE,
            transaction_type=TransactionType.SELL,
            quantity=qty,
            price=short_pe_entry.pe_price,
            greeks=short_pe_entry.pe_greeks,
        ))

        # Leg 4: Buy further OTM Put (hedge)
        long_pe_entry = chain.get_entry(strikes["long_pe"])
        if not long_pe_entry:
            logger.warning("Iron Condor: long PE strike %s missing from chain", strikes["long_pe"])
            return []
        legs.append(OrderLeg(
            instrument_key=long_pe_entry.pe_instrument_key,
            strike=strikes["long_pe"],
            option_type=OptionType.PE,
            transaction_type=TransactionType.BUY,
            quantity=qty,
            price=long_pe_entry.pe_price,
            greeks=long_pe_entry.pe_greeks,
        ))

        return legs

    def _calculate_net_delta(self, legs: List[OrderLeg]) -> Optional[float]:
        """Calculate net delta across all legs. Returns None if Greeks unavailable."""
        if not all(leg.greeks for leg in legs):
            return None
        net_delta = 0.0
        for leg in legs:
            sign = -1 if leg.is_sell else 1
            net_delta += sign * leg.greeks.delta * leg.quantity
        return net_delta

    def get_exit_conditions(self, position: MultiLegPosition) -> ExitCondition:
        """
        Iron Condor exit rules:
        - Target: configured % of net premium collected
        - Stop loss: configured % of max risk
        - Trailing SL: lock profits at configured drawdown from peak
        - Time: Square off at configured exit time
        """
        net_premium = abs(position.net_entry_premium)
        target = net_premium * self.params["target_pct"]
        stop_loss = -position.max_risk * self.params["max_loss_pct"]

        return ExitCondition(
            target_pnl=target,
            stop_loss_pnl=stop_loss,
            exit_time=self.params["exit_time"],
            trailing_sl=self.params.get("trailing_sl", False),
            trailing_sl_pct=self.params.get("trailing_sl_pct", 0.40),
        )

    def calculate_max_risk(self, legs: List[OrderLeg]) -> float:
        """
        Iron Condor max risk:
        Max loss = (Wing width x qty) - Net premium collected

        Only one side can lose at a time, so max risk is the
        wider side minus net premium.
        """
        if len(legs) < 4:
            return 0

        # Net premium collected (positive for credit)
        net_premium = sum(leg.premium_flow for leg in legs)

        # Call side width
        call_width = abs(legs[1].strike - legs[0].strike) * legs[0].quantity
        # Put side width
        put_width = abs(legs[2].strike - legs[3].strike) * legs[2].quantity

        # Max risk = wider side - net premium
        wider_side = max(call_width, put_width)
        return max(0, wider_side - net_premium)

    def calculate_max_reward(self, legs: List[OrderLeg]) -> float:
        """Max reward = Net premium collected."""
        return max(0, sum(leg.premium_flow for leg in legs))
