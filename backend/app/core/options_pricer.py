"""
Black-Scholes Option Pricing Engine.
Used for backtesting option strategies when live market prices aren't available.

Provides:
- European option pricing (Black-Scholes)
- Greeks calculation (Delta, Gamma, Theta, Vega)
- Implied Volatility estimation via Newton-Raphson
"""

import math
from typing import Tuple
from scipy.stats import norm
from app.core.models import Greeks


# ─── Constants ──────────────────────────────────────────────────────────────

RISK_FREE_RATE = 0.07       # India 10-year govt bond yield (~7%)
TRADING_DAYS_PER_YEAR = 252
NIFTY_LOT_SIZE = 25


# ─── Black-Scholes Core ────────────────────────────────────────────────────

def _d1_d2(spot: float, strike: float, t: float, r: float, sigma: float) -> Tuple[float, float]:
    """
    Calculate d1 and d2 parameters for Black-Scholes formula.
    
    Args:
        spot: Current underlying price
        strike: Option strike price
        t: Time to expiry in years (e.g., 7/365 for 7 days)
        r: Risk-free interest rate (annualized, e.g., 0.07)
        sigma: Volatility (annualized, e.g., 0.15 for 15%)
    
    Returns:
        (d1, d2) tuple
    """
    if t <= 0 or sigma <= 0:
        return 0.0, 0.0
    
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return d1, d2


def black_scholes_price(
    spot: float,
    strike: float,
    expiry_days: float,
    sigma: float,
    option_type: str = "CE",
    r: float = RISK_FREE_RATE,
) -> float:
    """
    Calculate European option price using Black-Scholes model.
    
    Args:
        spot: Current Nifty 50 price
        strike: Strike price
        expiry_days: Days to expiry
        sigma: Implied volatility (annualized, e.g., 0.15)
        option_type: "CE" for Call, "PE" for Put
        r: Risk-free rate (default: 7% for India)
    
    Returns:
        Theoretical option premium
    
    Example:
        >>> black_scholes_price(23500, 23500, 7, 0.12, "CE")
        148.52  # Approximate ATM CE premium with 7 DTE and 12% IV
    """
    t = expiry_days / 365.0
    
    if t <= 0:
        # At expiry — intrinsic value only
        if option_type == "CE":
            return max(0.0, spot - strike)
        else:
            return max(0.0, strike - spot)
    
    d1, d2 = _d1_d2(spot, strike, t, r, sigma)
    
    if option_type == "CE":
        price = spot * norm.cdf(d1) - strike * math.exp(-r * t) * norm.cdf(d2)
    else:
        price = strike * math.exp(-r * t) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    
    return max(0.0, round(price, 2))


def calculate_greeks(
    spot: float,
    strike: float,
    expiry_days: float,
    sigma: float,
    option_type: str = "CE",
    r: float = RISK_FREE_RATE,
) -> Greeks:
    """
    Calculate option Greeks using Black-Scholes.
    
    Returns Greeks dataclass with delta, gamma, theta, vega, iv.
    
    Example:
        >>> g = calculate_greeks(23500, 23500, 7, 0.12, "CE")
        >>> g.delta  # ~0.52 for ATM call
        >>> g.theta  # Negative (time decay)
    """
    t = expiry_days / 365.0
    
    if t <= 0 or sigma <= 0:
        # At expiry — delta is 1 or 0, no theta/vega/gamma
        intrinsic_ce = 1.0 if spot > strike else 0.0
        delta = intrinsic_ce if option_type == "CE" else intrinsic_ce - 1.0
        return Greeks(delta=delta, gamma=0.0, theta=0.0, vega=0.0, iv=sigma * 100)
    
    d1, d2 = _d1_d2(spot, strike, t, r, sigma)
    sqrt_t = math.sqrt(t)
    pdf_d1 = norm.pdf(d1)
    
    # --- Gamma (same for CE and PE) ---
    gamma = pdf_d1 / (spot * sigma * sqrt_t)
    
    # --- Vega (same for CE and PE, per 1% IV move) ---
    vega = spot * sqrt_t * pdf_d1 / 100.0
    
    if option_type == "CE":
        delta = norm.cdf(d1)
        theta = (
            -(spot * pdf_d1 * sigma) / (2 * sqrt_t)
            - r * strike * math.exp(-r * t) * norm.cdf(d2)
        ) / 365.0  # Daily theta
    else:
        delta = norm.cdf(d1) - 1.0
        theta = (
            -(spot * pdf_d1 * sigma) / (2 * sqrt_t)
            + r * strike * math.exp(-r * t) * norm.cdf(-d2)
        ) / 365.0  # Daily theta
    
    return Greeks(
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta, 2),
        vega=round(vega, 2),
        iv=round(sigma * 100, 2),
    )


def estimate_iv(
    market_price: float,
    spot: float,
    strike: float,
    expiry_days: float,
    option_type: str = "CE",
    r: float = RISK_FREE_RATE,
    precision: float = 0.0001,
    max_iterations: int = 100,
) -> float:
    """
    Estimate implied volatility from market price using Newton-Raphson method.
    
    Args:
        market_price: Observed market premium
        spot: Current spot price
        strike: Strike price
        expiry_days: Days to expiry
        option_type: "CE" or "PE"
        r: Risk-free rate
        precision: Convergence threshold
        max_iterations: Max iterations before giving up
    
    Returns:
        Annualized implied volatility (e.g., 0.15 for 15%)
    
    Example:
        >>> iv = estimate_iv(150, 23500, 23500, 7, "CE")
        >>> iv  # ~0.12 (12% annualized volatility)
    """
    t = expiry_days / 365.0
    
    if t <= 0 or market_price <= 0:
        return 0.0
    
    # Initial guess based on ATM approximation
    # ATM option price ≈ 0.4 × S × σ × √t
    sigma = market_price / (0.4 * spot * math.sqrt(t))
    sigma = max(0.01, min(sigma, 5.0))  # Clamp to reasonable range
    
    for _ in range(max_iterations):
        price = black_scholes_price(spot, strike, expiry_days, sigma, option_type, r)
        diff = price - market_price
        
        if abs(diff) < precision:
            return round(sigma, 4)
        
        # Vega for Newton-Raphson step
        d1, _ = _d1_d2(spot, strike, t, r, sigma)
        vega = spot * math.sqrt(t) * norm.pdf(d1)
        
        if vega < 1e-10:
            break
        
        sigma -= diff / vega
        sigma = max(0.01, min(sigma, 5.0))  # Keep within bounds
    
    return round(sigma, 4)


def estimate_premium_change(
    spot_old: float,
    spot_new: float,
    strike: float,
    expiry_days: float,
    sigma: float,
    option_type: str = "CE",
    time_elapsed_minutes: float = 0,
) -> float:
    """
    Estimate how option premium changes given a move in underlying price.
    Useful for backtesting P&L without full option chain data.
    
    Args:
        spot_old: Previous Nifty price
        spot_new: New Nifty price
        strike: Option strike
        expiry_days: Days to expiry at start
        sigma: Implied volatility
        option_type: "CE" or "PE"
        time_elapsed_minutes: Minutes elapsed (for theta decay)
    
    Returns:
        New estimated premium
    """
    # Adjust time for elapsed minutes
    days_elapsed = time_elapsed_minutes / (60 * 6.25)  # 6.25 trading hours per day
    new_expiry = max(0, expiry_days - days_elapsed)
    
    return black_scholes_price(spot_new, strike, new_expiry, sigma, option_type)


# ─── Utility Functions ──────────────────────────────────────────────────────

def calculate_atm_strike(spot_price: float, step: float = 50.0) -> float:
    """
    Find the ATM (At-The-Money) strike for Nifty 50.
    Nifty strikes are in multiples of 50.
    
    Args:
        spot_price: Current Nifty 50 price
        step: Strike step size (50 for Nifty)
    
    Returns:
        Nearest ATM strike
    
    Example:
        >>> calculate_atm_strike(23547)
        23550.0
    """
    return round(spot_price / step) * step


def get_strike_range(
    atm_strike: float,
    num_strikes: int = 10,
    step: float = 50.0,
) -> list:
    """
    Generate a range of strikes around ATM.
    
    Args:
        atm_strike: ATM strike price
        num_strikes: Number of strikes on each side
        step: Strike step size
    
    Returns:
        List of strike prices [ATM-n*step, ..., ATM, ..., ATM+n*step]
    """
    return [atm_strike + i * step for i in range(-num_strikes, num_strikes + 1)]
