"""
Greeks Quality Validator - Validates calculated Greeks against expected ranges and patterns.
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class GreeksValidator:
    """Validates Greeks calculations for quality and reasonableness."""
    
    def __init__(self):
        self.validation_errors = []
        self.warnings = []
    
    def validate_greeks(self, greeks_data: Dict, spot_price: float, 
                       strike: float, time_to_expiry: float, 
                       option_type: str, market_price: float) -> Dict:
        """
        Comprehensive Greeks validation.
        
        Returns:
            Dict with validation results and quality score
        """
        self.validation_errors.clear()
        self.warnings.clear()
        
        # Extract Greeks
        delta = greeks_data.get('delta', 0)
        gamma = greeks_data.get('gamma', 0)
        theta = greeks_data.get('theta', 0)
        vega = greeks_data.get('vega', 0)
        rho = greeks_data.get('rho', 0)
        iv = greeks_data.get('iv', 0)
        
        # Run validations
        self._validate_delta(delta, option_type, spot_price, strike)
        self._validate_gamma(gamma)
        self._validate_theta(theta, option_type)
        self._validate_vega(vega)
        self._validate_rho(rho, option_type)
        self._validate_iv(iv, market_price, spot_price, strike, time_to_expiry)
        self._validate_relationships(delta, gamma, theta, vega, time_to_expiry)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score()
        
        return {
            'quality_score': quality_score,
            'is_valid': len(self.validation_errors) == 0,
            'errors': self.validation_errors.copy(),
            'warnings': self.warnings.copy(),
            'summary': self._get_quality_summary(quality_score)
        }
    
    def _validate_delta(self, delta: float, option_type: str, spot: float, strike: float):
        """Validate Delta ranges and behavior."""
        if option_type == 'CE':
            if not (0 <= delta <= 1):
                self.validation_errors.append(f"CE Delta {delta} outside range [0,1]")
            # ITM CE should have higher delta
            if spot > strike and delta < 0.5:
                self.warnings.append(f"ITM CE Delta {delta} seems low for S={spot}, K={strike}")
        else:  # PE
            if not (-1 <= delta <= 0):
                self.validation_errors.append(f"PE Delta {delta} outside range [-1,0]")
            # ITM PE should have lower (more negative) delta
            if spot < strike and delta > -0.5:
                self.warnings.append(f"ITM PE Delta {delta} seems high for S={spot}, K={strike}")
    
    def _validate_gamma(self, gamma: float):
        """Validate Gamma is positive."""
        if gamma < 0:
            self.validation_errors.append(f"Gamma {gamma} is negative (should be positive)")
        if gamma > 0.01:  # Very high gamma
            self.warnings.append(f"Gamma {gamma} is very high (>0.01)")
    
    def _validate_theta(self, theta: float, option_type: str):
        """Validate Theta signs and ranges."""
        # Most options lose value over time (negative theta)
        if option_type == 'CE' and theta > 0:
            self.warnings.append(f"CE Theta {theta} is positive (unusual)")
        if abs(theta) > 50:  # Very high time decay
            self.warnings.append(f"Theta {theta} is very high (>50 per day)")
    
    def _validate_vega(self, vega: float):
        """Validate Vega is reasonable."""
        if vega < 0:
            self.validation_errors.append(f"Vega {vega} is negative (should be positive)")
        if vega > 100:  # Very high vega
            self.warnings.append(f"Vega {vega} is very high (>100)")
    
    def _validate_rho(self, rho: float, option_type: str):
        """Validate Rho signs."""
        if option_type == 'CE' and rho < 0:
            self.warnings.append(f"CE Rho {rho} is negative (usually positive)")
        elif option_type == 'PE' and rho > 0:
            self.warnings.append(f"PE Rho {rho} is positive (usually negative)")
    
    def _validate_iv(self, iv: float, market_price: float, spot: float, 
                    strike: float, time_to_expiry: float):
        """Validate Implied Volatility reasonableness."""
        if iv <= 0:
            self.validation_errors.append(f"IV {iv} is zero or negative")
        elif iv < 0.05:  # Less than 5%
            self.warnings.append(f"IV {iv*100:.1f}% is very low")
        elif iv > 1.0:  # More than 100%
            self.warnings.append(f"IV {iv*100:.1f}% is very high")
        
        # Check if IV makes sense given option price
        intrinsic = max(0, spot - strike) if market_price > 0 else max(0, strike - spot)
        time_value = market_price - intrinsic
        
        if time_value <= 0 and iv > 0.1:
            self.warnings.append(f"High IV {iv*100:.1f}% for option with no time value")
    
    def _validate_relationships(self, delta: float, gamma: float, theta: float, 
                              vega: float, time_to_expiry: float):
        """Validate relationships between Greeks."""
        # Gamma-Theta relationship (rough check)
        if time_to_expiry > 0.01:  # Not near expiry
            if gamma > 0.001 and abs(theta) < 1:
                self.warnings.append("High Gamma but low Theta (unusual relationship)")
        
        # Delta-Gamma relationship
        if abs(delta) > 0.8 and gamma > 0.005:  # Deep ITM/OTM with high gamma
            self.warnings.append("Deep ITM/OTM option with high Gamma (unusual)")
    
    def _calculate_quality_score(self) -> int:
        """Calculate quality score 0-100."""
        score = 100
        score -= len(self.validation_errors) * 30  # Major penalty for errors
        score -= len(self.warnings) * 10  # Minor penalty for warnings
        return max(0, score)
    
    def _get_quality_summary(self, score: int) -> str:
        """Get quality summary text."""
        if score >= 90:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 50:
            return "Fair"
        else:
            return "Poor"

def validate_greeks_quality(greeks_data: Dict, spot_price: float, 
                          strike: float, time_to_expiry: float, 
                          option_type: str, market_price: float) -> Dict:
    """Convenience function for Greeks validation."""
    validator = GreeksValidator()
    return validator.validate_greeks(
        greeks_data, spot_price, strike, time_to_expiry, option_type, market_price
    )