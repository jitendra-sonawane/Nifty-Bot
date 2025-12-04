"""
Put-Call Ratio (PCR) Calculator for options sentiment analysis.

PCR = Total Put Open Interest / Total Call Open Interest

Interpretation:
- PCR > 1.5: Extreme bearish sentiment (potential reversal - market oversold)
- PCR > 1.0: Bearish sentiment (more puts than calls)
- PCR ≈ 1.0: Neutral sentiment (balanced)
- PCR < 1.0: Bullish sentiment (more calls than puts)
- PCR < 0.5: Extreme bullish sentiment (potential reversal - market overbought)
"""

from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PCRCalculator:
    """Calculate Put-Call Ratio from option open interest data."""
    
    # PCR thresholds for sentiment classification
    EXTREME_BEARISH_THRESHOLD = 1.5
    BEARISH_THRESHOLD = 1.0
    BULLISH_THRESHOLD = 1.0
    EXTREME_BULLISH_THRESHOLD = 0.5
    
    def __init__(self):
        """Initialize PCR calculator."""
        self.pcr_history: List[Dict] = []
        self.max_history = 100  # Keep last 100 PCR readings
    
    def calculate_pcr(self, put_oi: float, call_oi: float) -> Optional[float]:
        """
        Calculate Put-Call Ratio.
        
        Args:
            put_oi: Total put open interest
            call_oi: Total call open interest
        
        Returns:
            PCR ratio or None if invalid
        """
        if call_oi <= 0:
            return None
        
        pcr = put_oi / call_oi
        return round(pcr, 4)
    
    def calculate_pcr_from_options(self, options_data: List[Dict]) -> Optional[float]:
        """
        Calculate PCR from list of option contracts.
        
        Args:
            options_data: List of dicts with keys: option_type, oi
                         option_type: 'CE' or 'PE'
                         oi: open interest
        
        Returns:
            PCR ratio or None if invalid
        """
        if not options_data:
            return None
        
        total_put_oi = sum(opt['oi'] for opt in options_data if opt.get('option_type') == 'PE')
        total_call_oi = sum(opt['oi'] for opt in options_data if opt.get('option_type') == 'CE')
        
        return self.calculate_pcr(total_put_oi, total_call_oi)
    
    def get_sentiment(self, pcr: Optional[float]) -> str:
        """
        Get sentiment classification from PCR value.
        
        Args:
            pcr: Put-Call Ratio
        
        Returns:
            Sentiment string: 'EXTREME_BEARISH', 'BEARISH', 'NEUTRAL', 'BULLISH', 'EXTREME_BULLISH'
        """
        if pcr is None:
            return "UNKNOWN"
        
        if pcr >= self.EXTREME_BEARISH_THRESHOLD:
            return "EXTREME_BEARISH"
        elif pcr >= self.BEARISH_THRESHOLD:
            return "BEARISH"
        elif pcr > self.BULLISH_THRESHOLD:
            return "NEUTRAL"
        elif pcr > self.EXTREME_BULLISH_THRESHOLD:
            return "BULLISH"
        else:
            return "EXTREME_BULLISH"
    
    def get_sentiment_emoji(self, sentiment: str) -> str:
        """Get emoji representation of sentiment."""
        emojis = {
            "EXTREME_BEARISH": "🔴🔴",
            "BEARISH": "🔴",
            "NEUTRAL": "🟡",
            "BULLISH": "🟢",
            "EXTREME_BULLISH": "🟢🟢",
            "UNKNOWN": "❓"
        }
        return emojis.get(sentiment, "❓")
    
    def is_bullish_signal(self, pcr: Optional[float]) -> bool:
        """
        Check if PCR indicates bullish signal.
        
        Args:
            pcr: Put-Call Ratio
        
        Returns:
            True if PCR < 1.0 (bullish), False otherwise
        """
        if pcr is None:
            return False
        return pcr < 1.0
    
    def is_bearish_signal(self, pcr: Optional[float]) -> bool:
        """
        Check if PCR indicates bearish signal.
        
        Args:
            pcr: Put-Call Ratio
        
        Returns:
            True if PCR > 1.0 (bearish), False otherwise
        """
        if pcr is None:
            return False
        return pcr > 1.0
    
    def is_extreme_signal(self, pcr: Optional[float]) -> bool:
        """
        Check if PCR indicates extreme sentiment (potential reversal).
        
        Args:
            pcr: Put-Call Ratio
        
        Returns:
            True if PCR > 1.5 or PCR < 0.5 (extreme), False otherwise
        """
        if pcr is None:
            return False
        return pcr >= self.EXTREME_BEARISH_THRESHOLD or pcr <= self.EXTREME_BULLISH_THRESHOLD
    
    def record_pcr(self, pcr: Optional[float], put_oi: float, call_oi: float) -> None:
        """
        Record PCR reading for historical tracking.
        
        Args:
            pcr: Put-Call Ratio
            put_oi: Total put open interest
            call_oi: Total call open interest
        """
        if pcr is None:
            return
        
        record = {
            'pcr': pcr,
            'put_oi': put_oi,
            'call_oi': call_oi,
            'sentiment': self.get_sentiment(pcr),
            'timestamp': datetime.now().isoformat()
        }
        
        self.pcr_history.append(record)
        
        # Keep only last N readings
        if len(self.pcr_history) > self.max_history:
            self.pcr_history = self.pcr_history[-self.max_history:]
    
    def get_pcr_trend(self, periods: int = 5) -> Optional[str]:
        """
        Get PCR trend over last N periods.
        
        Args:
            periods: Number of periods to analyze
        
        Returns:
            'INCREASING' (bearish trend), 'DECREASING' (bullish trend), or None
        """
        if len(self.pcr_history) < periods:
            return None
        
        recent = self.pcr_history[-periods:]
        pcr_values = [r['pcr'] for r in recent]
        
        # Check if PCR is increasing (bearish) or decreasing (bullish)
        if pcr_values[-1] > pcr_values[0]:
            return "INCREASING"  # Bearish trend
        elif pcr_values[-1] < pcr_values[0]:
            return "DECREASING"  # Bullish trend
        else:
            return "STABLE"
    
    def get_pcr_analysis(self, pcr: Optional[float], put_oi: float, call_oi: float) -> Dict:
        """
        Get comprehensive PCR analysis.
        
        Args:
            pcr: Put-Call Ratio
            put_oi: Total put open interest
            call_oi: Total call open interest
        
        Returns:
            Dict with PCR analysis details
        """
        if pcr is None:
            return {
                'pcr': None,
                'sentiment': 'UNKNOWN',
                'is_bullish': False,
                'is_bearish': False,
                'is_extreme': False,
                'trend': None,
                'interpretation': 'Insufficient data'
            }
        
        sentiment = self.get_sentiment(pcr)
        is_bullish = self.is_bullish_signal(pcr)
        is_bearish = self.is_bearish_signal(pcr)
        is_extreme = self.is_extreme_signal(pcr)
        trend = self.get_pcr_trend()
        
        # Generate interpretation
        interpretation = self._get_interpretation(pcr, sentiment, trend)
        
        return {
            'pcr': pcr,
            'put_oi': put_oi,
            'call_oi': call_oi,
            'sentiment': sentiment,
            'emoji': self.get_sentiment_emoji(sentiment),
            'is_bullish': is_bullish,
            'is_bearish': is_bearish,
            'is_extreme': is_extreme,
            'trend': trend,
            'interpretation': interpretation,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_interpretation(self, pcr: float, sentiment: str, trend: Optional[str]) -> str:
        """Generate human-readable interpretation of PCR."""
        interpretations = {
            "EXTREME_BEARISH": "Extreme bearish sentiment - potential reversal signal (market oversold)",
            "BEARISH": "Bearish sentiment - more puts than calls",
            "NEUTRAL": "Neutral sentiment - balanced put-call activity",
            "BULLISH": "Bullish sentiment - more calls than puts",
            "EXTREME_BULLISH": "Extreme bullish sentiment - potential reversal signal (market overbought)"
        }
        
        base = interpretations.get(sentiment, "Unknown sentiment")
        
        if trend == "INCREASING":
            base += " (trend: bearish)"
        elif trend == "DECREASING":
            base += " (trend: bullish)"
        
        return base
    
    def get_pcr_history(self, limit: int = 10) -> List[Dict]:
        """
        Get recent PCR history.
        
        Args:
            limit: Number of recent readings to return
        
        Returns:
            List of PCR records
        """
        return self.pcr_history[-limit:] if self.pcr_history else []
    
    def clear_history(self) -> None:
        """Clear PCR history."""
        self.pcr_history.clear()
