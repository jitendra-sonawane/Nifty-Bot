import numpy as np
from scipy.stats import norm
from datetime import datetime

class GreeksCalculator:
    def __init__(self, risk_free_rate=0.06):
        self.r = risk_free_rate

    def d1(self, S, K, T, sigma):
        """Calculate d1 from Black-Scholes formula."""
        if T <= 0 or sigma <= 0:
            return 0
        numerator = np.log(S / K) + (self.r + 0.5 * sigma ** 2) * T
        denominator = sigma * np.sqrt(T)
        return numerator / denominator

    def d2(self, S, K, T, sigma):
        """Calculate d2 from Black-Scholes formula."""
        if T <= 0 or sigma <= 0:
            return 0
        return self.d1(S, K, T, sigma) - sigma * np.sqrt(T)

    def calculate_greeks(self, S, K, T, sigma, option_type='CE', risk_free_rate=None):
        """
        Calculate Option Greeks using Black-Scholes Model.
        
        Args:
            S: Spot Price
            K: Strike Price
            T: Time to Expiry (in years)
            sigma: Implied Volatility (decimal, e.g., 0.25 for 25%)
            option_type: 'CE' or 'PE'
            risk_free_rate: Override instance risk-free rate
        
        Returns:
            Dict with delta, gamma, theta, vega, rho
        """
        if risk_free_rate is not None:
            r = risk_free_rate
        else:
            r = self.r
            
        if T <= 0 or sigma <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}

        d1 = self.d1(S, K, T, sigma)
        d2 = self.d2(S, K, T, sigma)
        
        # Delta
        if option_type == 'CE':
            delta = norm.cdf(d1)
        else:  # PE
            delta = norm.cdf(d1) - 1
        
        # Gamma (same for CE and PE)
        if sigma > 0 and S > 0:
            gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        else:
            gamma = 0
        
        # Theta (per day)
        if sigma > 0 and np.sqrt(T) > 0:
            theta_term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        else:
            theta_term1 = 0
        
        if option_type == 'CE':
            theta = theta_term1 - r * K * np.exp(-r * T) * norm.cdf(d2)
        else:  # PE
            theta = theta_term1 + r * K * np.exp(-r * T) * norm.cdf(-d2)
        
        # Normalize theta to per day (theta is annual, divide by 365)
        theta = theta / 365.0
        
        # Vega (per 1% change in volatility, not per 0.01 change)
        # Vega is the derivative w.r.t. volatility, typically quoted as "per 1% IV change"
        # Our sigma is already in decimal form (0.25 = 25%), so vega derivative / 100
        vega = S * np.sqrt(T) * norm.pdf(d1) / 100.0
        
        # Rho (per 1% change in interest rate)
        if option_type == 'CE':
            rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100.0
        else:  # PE
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100.0

        return {
            'delta': round(float(delta), 4),
            'gamma': round(float(gamma), 6),
            'theta': round(float(theta), 4),
            'vega': round(float(vega), 4),
            'rho': round(float(rho), 4)
        }

    def black_scholes_price(self, S, K, T, sigma, option_type='CE', risk_free_rate=None):
        """
        Calculate option price using Black-Scholes formula.
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (in years)
            sigma: Volatility (decimal)
            option_type: 'CE' or 'PE'
            risk_free_rate: Override instance risk-free rate
        
        Returns:
            Option price
        """
        if risk_free_rate is not None:
            r = risk_free_rate
        else:
            r = self.r
            
        if T <= 0 or sigma <= 0:
            return max(0, S - K) if option_type == 'CE' else max(0, K - S)
            
        d1 = self.d1(S, K, T, sigma)
        d2 = self.d2(S, K, T, sigma)
        
        if option_type == 'CE':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
        return price

    def implied_volatility(self, market_price, S, K, T, option_type='CE', risk_free_rate=None):
        """
        Calculate Implied Volatility using Newton-Raphson method.
        
        Args:
            market_price: Current option market price
            S: Spot price
            K: Strike price
            T: Time to expiry (in years)
            option_type: 'CE' or 'PE'
            risk_free_rate: Override instance risk-free rate
        
        Returns:
            Implied volatility as decimal (e.g., 0.25 for 25%)
        """
        if risk_free_rate is not None:
            r = risk_free_rate
        else:
            r = self.r
            
        MAX_ITERATIONS = 100
        PRECISION = 1.0e-5
        
        # Better initial guess for IV
        # Use simple formula for rough IV estimate
        intrinsic = max(S - K, 0) if option_type == 'CE' else max(K - S, 0)
        time_value = market_price - intrinsic
        
        if time_value <= 0:
            # Option is at or below intrinsic, return minimal IV
            return 0.01
        
        # Heuristic initial guess
        sigma = np.sqrt(2 * np.pi / T) * (time_value / S) if T > 0 else 0.3
        sigma = np.clip(sigma, 0.01, 2.0)  # Keep sigma in reasonable range (1% to 200%)

        for iteration in range(MAX_ITERATIONS):
            # Calculate price with current sigma
            price = self.black_scholes_price(S, K, T, sigma, option_type, r)
            
            # Calculate vega for Newton-Raphson update
            d1 = self.d1(S, K, T, sigma)
            vega = S * np.sqrt(T) * norm.pdf(d1)
            
            diff = market_price - price
            
            # Check convergence
            if abs(diff) < PRECISION:
                return max(round(sigma, 4), 0.0001)
            
            # Avoid division by zero
            if vega < 1e-10:
                return max(round(sigma, 4), 0.0001)
            
            # Newton-Raphson update
            sigma = sigma + diff / vega
            
            # Keep sigma in bounds
            sigma = np.clip(sigma, 0.001, 5.0)

        return max(round(sigma, 4), 0.0001)

    def time_to_expiry(self, expiry_date_str):
        """
        Calculate T (years) from expiry date string (YYYY-MM-DD).
        """
        try:
            expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d")
            now = datetime.now()
            diff = expiry - now
            days = diff.days + diff.seconds / 86400.0
            return max(days / 365.0, 0.0001) # Avoid division by zero
        except Exception as e:
            print(f"Error calculating time to expiry: {e}")
            return 0
