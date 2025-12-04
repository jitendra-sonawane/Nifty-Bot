"""
Trading Reasoning Module - Provides detailed explanation for trading decisions in real-time.
This module generates human-readable reasoning for why a trade is taken or avoided.
"""

import pandas as pd
import numpy as np
from datetime import datetime


class TradingReasoning:
    """
    Generates detailed reasoning for trading decisions based on multiple factors.
    Helps users understand the bot's decision-making process in real-time.
    """
    
    def __init__(self):
        self.reasoning_history = []
        self.max_history = 20
    
    def generate_reasoning(self, signal_data, current_price, support_resistance, breakout_data):
        """
        Generate detailed reasoning for a trade decision.
        
        Args:
            signal_data: Dict with signal info from strategy engine
            current_price: Current market price
            support_resistance: Support/Resistance levels
            breakout_data: Breakout detection data
            
        Returns:
            Dict with reasoning details and action points
        """
        
        signal = signal_data.get('signal', 'HOLD')
        reason = signal_data.get('reason', '')
        filters = signal_data.get('filters', {})
        
        # Initialize reasoning structure
        reasoning = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'signal': signal,
            'action': self._get_action(signal),
            'confidence': self._calculate_confidence(filters),
            'key_factors': [],
            'risk_factors': [],
            'target_levels': {},
            'stop_loss_levels': {},
            'trade_rationale': '',
            'why_now': '',
            'filter_summary': self._summarize_filters(filters),
        }
        
        # Generate detailed reasoning based on signal
        if signal == 'BUY_CE':
            reasoning.update(self._reason_buy_ce(signal_data, current_price, support_resistance, breakout_data))
        elif signal == 'BUY_PE':
            reasoning.update(self._reason_buy_pe(signal_data, current_price, support_resistance, breakout_data))
        else:
            reasoning.update(self._reason_hold(signal_data, filters))
        
        # Add to history
        self.reasoning_history.append(reasoning)
        if len(self.reasoning_history) > self.max_history:
            self.reasoning_history.pop(0)
        
        return reasoning
    
    def _get_action(self, signal):
        """Convert signal to user-friendly action"""
        if signal == 'BUY_CE':
            return '📈 BUY CALL - Bullish Setup'
        elif signal == 'BUY_PE':
            return '📉 BUY PUT - Bearish Setup'
        else:
            return '⏸️ WAIT - No Setup'
    
    def _calculate_confidence(self, filters):
        """
        Calculate confidence level (0-100%) based on filter passes.
        More filters passing = higher confidence.
        """
        if not filters:
            return 0
        
        passed_filters = sum(1 for v in filters.values() if v is True)
        total_filters = len(filters)
        confidence = (passed_filters / total_filters) * 100
        return round(confidence, 0)
    
    def _summarize_filters(self, filters):
        """Create a summary of which filters are passing/failing"""
        summary = {}
        filter_names = {
            'supertrend': '📊 Supertrend',
            'ema_crossover': '📈 EMA Crossover',
            'price_vwap': '📍 Price vs VWAP',
            'rsi': '🔢 RSI Level',
            'volume': '📊 Volume',
            'volatility': '📈 Volatility (ATR)',
            'pcr': '🎯 PCR Ratio',
            'greeks': '🧮 Greeks Quality',
            'entry_confirmation': '✅ Entry Confirmed'
        }
        
        for key, name in filter_names.items():
            if key in filters:
                status = '✅' if filters[key] else '❌'
                summary[name] = status
        
        return summary
    
    def _reason_buy_ce(self, signal_data, current_price, support_resistance, breakout_data):
        """Generate reasoning for BUY_CE (bullish call) signal"""
        
        rsi = signal_data.get('rsi', 0)
        ema_5 = signal_data.get('ema_5', 0)
        ema_20 = signal_data.get('ema_20', 0)
        vwap = signal_data.get('vwap', 0)
        supertrend = signal_data.get('supertrend', '')
        
        # Get support/resistance levels
        nearest_support = support_resistance.get('nearest_support', 0) if support_resistance else 0
        nearest_resistance = support_resistance.get('nearest_resistance', 0) if support_resistance else 0
        
        key_factors = [
            f"📈 EMA Crossover: {ema_5:.0f} > {ema_20:.0f} (Uptrend confirmed)",
            f"🔴 RSI: {rsi:.1f} (Strong momentum - above 50)",
            f"📊 Supertrend: {supertrend} (Price above moving trend)",
            f"💰 Price at ₹{current_price:.2f} (Above VWAP ₹{vwap:.2f})",
            f"🛡️ Support: ₹{nearest_support:.2f} (Downside protection)",
            f"🎯 Resistance: ₹{nearest_resistance:.2f} (Profit target)"
        ]
        
        # Breakout info
        if breakout_data and breakout_data.get('is_breakout'):
            key_factors.append(f"🔥 {breakout_data.get('breakout_type')} Breakout Detected (Strength: {breakout_data.get('strength', 0):.1f}%)")
        
        risk_factors = [
            f"If price closes below ₹{nearest_support:.2f}, invalidates bullish setup",
            "Watch for sudden volume drop - could indicate reversal",
            "Monitor RSI crossing below 50 - loss of momentum"
        ]
        
        trade_rationale = (
            f"Multiple bullish signals aligned: EMA crossover ({ema_5:.0f}>{ema_20:.0f}), "
            f"Strong uptrend (Supertrend), strong momentum (RSI {rsi:.1f}), and price above VWAP ({vwap:.2f}). "
            f"This suggests buyers are in control and willing to push prices higher."
        )
        
        why_now = (
            f"EMA just crossed above ({ema_5:.0f}>{ema_20:.0f}) with Supertrend confirmation and RSI {rsi:.1f}. "
            f"Price is {((current_price - vwap) / vwap * 100):.2f}% above VWAP. "
            f"Entry window is NOW - this is the start of the uptrend."
        )
        
        return {
            'key_factors': key_factors,
            'risk_factors': risk_factors,
            'target_levels': {
                'primary': nearest_resistance,
                'extended': nearest_resistance * 1.005 if nearest_resistance else 0,
                'reasoning': f'Resistance level at ₹{nearest_resistance:.2f}'
            },
            'stop_loss_levels': {
                'primary': nearest_support,
                'reasoning': f'Support level at ₹{nearest_support:.2f} - protect capital if trend reverses'
            },
            'trade_rationale': trade_rationale,
            'why_now': why_now
        }
    
    def _reason_buy_pe(self, signal_data, current_price, support_resistance, breakout_data):
        """Generate reasoning for BUY_PE (bearish put) signal"""
        
        rsi = signal_data.get('rsi', 0)
        ema_5 = signal_data.get('ema_5', 0)
        ema_20 = signal_data.get('ema_20', 0)
        vwap = signal_data.get('vwap', 0)
        supertrend = signal_data.get('supertrend', '')
        
        # Get support/resistance levels
        nearest_support = support_resistance.get('nearest_support', 0) if support_resistance else 0
        nearest_resistance = support_resistance.get('nearest_resistance', 0) if support_resistance else 0
        
        key_factors = [
            f"📉 EMA Crossover: {ema_5:.0f} < {ema_20:.0f} (Downtrend confirmed)",
            f"🔵 RSI: {rsi:.1f} (Weak momentum - below 50)",
            f"📊 Supertrend: {supertrend} (Price below moving trend)",
            f"💰 Price at ₹{current_price:.2f} (Below VWAP ₹{vwap:.2f})",
            f"🛡️ Resistance: ₹{nearest_resistance:.2f} (Downside protection ceiling)",
            f"🎯 Support: ₹{nearest_support:.2f} (Profit target)"
        ]
        
        # Breakout info
        if breakout_data and breakout_data.get('is_breakout'):
            key_factors.append(f"🔥 {breakout_data.get('breakout_type')} Breakout Detected (Strength: {breakout_data.get('strength', 0):.1f}%)")
        
        risk_factors = [
            f"If price closes above ₹{nearest_resistance:.2f}, invalidates bearish setup",
            "Watch for sudden volume spike upwards - could indicate reversal",
            "Monitor RSI crossing above 50 - loss of bearish momentum"
        ]
        
        trade_rationale = (
            f"Multiple bearish signals aligned: EMA crossover ({ema_5:.0f}<{ema_20:.0f}), "
            f"Strong downtrend (Supertrend), weak momentum (RSI {rsi:.1f}), and price below VWAP ({vwap:.2f}). "
            f"This suggests sellers are in control and willing to push prices lower."
        )
        
        why_now = (
            f"EMA just crossed below ({ema_5:.0f}<{ema_20:.0f}) with Supertrend confirmation and RSI {rsi:.1f}. "
            f"Price is {((vwap - current_price) / vwap * 100):.2f}% below VWAP. "
            f"Entry window is NOW - this is the start of the downtrend."
        )
        
        return {
            'key_factors': key_factors,
            'risk_factors': risk_factors,
            'target_levels': {
                'primary': nearest_support,
                'extended': nearest_support * 0.995 if nearest_support else 0,
                'reasoning': f'Support level at ₹{nearest_support:.2f}'
            },
            'stop_loss_levels': {
                'primary': nearest_resistance,
                'reasoning': f'Resistance level at ₹{nearest_resistance:.2f} - protect capital if trend reverses'
            },
            'trade_rationale': trade_rationale,
            'why_now': why_now
        }
    
    def _reason_hold(self, signal_data, filters):
        """Generate reasoning for HOLD signal"""
        
        rsi = signal_data.get('rsi', 0)
        vwap = signal_data.get('vwap', 0)
        
        # Find failing filters
        failing_reasons = []
        if not filters.get('supertrend'):
            failing_reasons.append("Supertrend not aligned with price momentum")
        if not filters.get('rsi'):
            failing_reasons.append("RSI not in extreme zone (weak momentum)")
        if not filters.get('price_vwap'):
            # Note: This filter is always passing for index instruments
            failing_reasons.append("Price vs VWAP (Info: VWAP informational only for indices)")
        if not filters.get('volume'):
            failing_reasons.append("Volume too low (weak confirmation)")
        if not filters.get('volatility'):
            failing_reasons.append("Volatility readings unusual")
        if not filters.get('entry_confirmation'):
            failing_reasons.append("No confirmation from last candles")
        if not filters.get('pcr'):
            failing_reasons.append("Put-Call ratio not aligned")
        if not filters.get('greeks'):
            failing_reasons.append("Greeks quality too low")
        
        key_factors = [
            f"📊 Supertrend: {signal_data.get('supertrend', 'UNKNOWN')} (Mixed signals)",
            f"🔢 RSI: {rsi:.1f} (In neutral zone 35-65)",
            f"📍 Price vs VWAP: Close proximity (₹{vwap:.2f})",
        ]
        
        trade_rationale = (
            f"Market is in a consolidation phase with mixed signals. "
            f"The alignment of multiple indicators is not strong enough to justify an entry. "
            f"RSI at {rsi:.1f} suggests indecision between buyers and sellers."
        )
        
        why_now = (
            f"Risk/reward is not favorable right now. Better setups will come. "
            f"Waiting for clearer confirmation: either stronger momentum or better volume support. "
            f"Patience is key in trading - missed trades are better than bad trades."
        )
        
        return {
            'key_factors': key_factors,
            'risk_factors': [
                "False breakouts possible due to low momentum",
                "Wide range of prices with no clear direction"
            ],
            'target_levels': {},
            'stop_loss_levels': {},
            'trade_rationale': trade_rationale,
            'why_now': why_now
        }
    
    def get_last_reasoning(self):
        """Get the most recent reasoning"""
        if self.reasoning_history:
            return self.reasoning_history[-1]
        return None
    
    def get_reasoning_history(self, limit=10):
        """Get recent reasoning history"""
        return self.reasoning_history[-limit:] if self.reasoning_history else []
