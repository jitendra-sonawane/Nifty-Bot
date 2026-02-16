"""
Option Chain Manager for Nifty 50.
Handles option chain data fetching, ATM strike calculation,
and optimal strike selection for multi-leg strategies.
"""

import logging
import time
import requests
from typing import Dict, List, Optional, Tuple
from app.core.config import Config
from app.core.models import OptionChainEntry, Greeks, OptionType
from app.core.options_pricer import calculate_atm_strike, calculate_greeks, estimate_iv

logger = logging.getLogger(__name__)


class OptionChainManager:
    """
    Manages real-time option chain data for Nifty 50.
    
    Responsibilities:
    - Fetch option chain from Upstox API
    - Cache data to reduce API calls
    - Calculate ATM strike from spot price
    - Select optimal strikes for each strategy
    - Track IV percentile for strategy entry decisions
    
    Usage:
        chain_mgr = OptionChainManager()
        chain_mgr.update(spot_price=23500)
        atm = chain_mgr.atm_strike
        iron_condor_strikes = chain_mgr.get_iron_condor_strikes(wing_width=200)
    """
    
    # Cache TTL in seconds — avoid hammering API
    CACHE_TTL = 30
    
    # Nifty 50 option parameters
    STRIKE_STEP = 50          # Nifty strikes are in multiples of 50
    EXPIRY_INSTRUMENT = "NSE_INDEX|Nifty 50"
    
    def __init__(self):
        self.spot_price: float = 0.0
        self.atm_strike: float = 0.0
        self.chain: Dict[float, OptionChainEntry] = {}  # strike -> entry
        self._last_update: float = 0.0
        self._iv_history: List[float] = []  # Track ATM IV over time
        self._current_expiry: str = ""      # Current weekly expiry date
    
    def update(self, spot_price: float, force: bool = False) -> bool:
        """
        Update option chain data.
        
        Args:
            spot_price: Current Nifty 50 spot price
            force: Force refresh even if cache is valid
        
        Returns:
            True if chain was updated, False if cached
        """
        self.spot_price = spot_price
        self.atm_strike = calculate_atm_strike(spot_price, self.STRIKE_STEP)
        
        # Check cache
        now = time.time()
        if not force and (now - self._last_update) < self.CACHE_TTL and self.chain:
            return False
        
        success = self._fetch_option_chain()
        if success:
            self._last_update = now
            self._update_iv_history()
        
        return success
    
    def _fetch_option_chain(self) -> bool:
        """Fetch option chain from Upstox API."""
        try:
            token = Config.ACCESS_TOKEN
            if not token:
                logger.warning("No access token — using synthetic chain")
                self._generate_synthetic_chain()
                return True
            
            url = "https://api.upstox.com/v2/option/chain"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
            params = {
                "instrument_key": self.EXPIRY_INSTRUMENT,
                "expiry_date": self._get_nearest_expiry(),
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self._parse_chain_response(data)
                logger.info(f"✅ Option chain fetched: {len(self.chain)} strikes, ATM={self.atm_strike}")
                return True
            else:
                logger.warning(f"Option chain API returned {response.status_code}, using synthetic")
                self._generate_synthetic_chain()
                return True
                
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            self._generate_synthetic_chain()
            return True
    
    def _parse_chain_response(self, data: dict):
        """Parse Upstox option chain API response."""
        self.chain.clear()
        
        try:
            chain_data = data.get("data", [])
            
            for entry in chain_data:
                strike = entry.get("strike_price", 0)
                
                ce_data = entry.get("call_options", {}).get("market_data", {})
                pe_data = entry.get("put_options", {}).get("market_data", {})
                ce_greeks_raw = entry.get("call_options", {}).get("option_greeks", {})
                pe_greeks_raw = entry.get("put_options", {}).get("option_greeks", {})
                
                ce_instrument = entry.get("call_options", {}).get("instrument_key", "")
                pe_instrument = entry.get("put_options", {}).get("instrument_key", "")
                
                ce_greeks = Greeks(
                    delta=ce_greeks_raw.get("delta", 0),
                    gamma=ce_greeks_raw.get("gamma", 0),
                    theta=ce_greeks_raw.get("theta", 0),
                    vega=ce_greeks_raw.get("vega", 0),
                    iv=ce_greeks_raw.get("iv", 0),
                )
                pe_greeks = Greeks(
                    delta=pe_greeks_raw.get("delta", 0),
                    gamma=pe_greeks_raw.get("gamma", 0),
                    theta=pe_greeks_raw.get("theta", 0),
                    vega=pe_greeks_raw.get("vega", 0),
                    iv=pe_greeks_raw.get("iv", 0),
                )
                
                self.chain[strike] = OptionChainEntry(
                    strike=strike,
                    ce_price=ce_data.get("ltp", 0),
                    pe_price=pe_data.get("ltp", 0),
                    ce_oi=ce_data.get("oi", 0),
                    pe_oi=pe_data.get("oi", 0),
                    ce_volume=ce_data.get("volume", 0),
                    pe_volume=pe_data.get("volume", 0),
                    ce_iv=ce_greeks_raw.get("iv", 0),
                    pe_iv=pe_greeks_raw.get("iv", 0),
                    ce_greeks=ce_greeks,
                    pe_greeks=pe_greeks,
                    ce_instrument_key=ce_instrument,
                    pe_instrument_key=pe_instrument,
                    ce_pop=ce_greeks_raw.get("pop", 0),
                    pe_pop=pe_greeks_raw.get("pop", 0),
                )
        except Exception as e:
            logger.error(f"Error parsing option chain: {e}")
            self._generate_synthetic_chain()
    
    def _generate_synthetic_chain(self):
        """
        Generate a synthetic option chain using Black-Scholes.
        Used when API is unavailable or for backtesting.
        """
        self.chain.clear()
        
        if self.spot_price <= 0:
            return
        
        expiry_days = self._get_days_to_expiry()
        base_iv = 0.13  # Default ~13% IV for Nifty
        
        # Generate ±15 strikes around ATM
        for offset in range(-15, 16):
            strike = self.atm_strike + offset * self.STRIKE_STEP
            
            # IV smile: OTM options have slightly higher IV
            moneyness = abs(strike - self.spot_price) / self.spot_price
            iv = base_iv + moneyness * 0.3  # Simple smile approximation
            
            from app.core.options_pricer import black_scholes_price
            
            ce_price = black_scholes_price(self.spot_price, strike, expiry_days, iv, "CE")
            pe_price = black_scholes_price(self.spot_price, strike, expiry_days, iv, "PE")
            
            ce_greeks = calculate_greeks(self.spot_price, strike, expiry_days, iv, "CE")
            pe_greeks = calculate_greeks(self.spot_price, strike, expiry_days, iv, "PE")
            
            self.chain[strike] = OptionChainEntry(
                strike=strike,
                ce_price=ce_price,
                pe_price=pe_price,
                ce_iv=round(iv * 100, 2),
                pe_iv=round(iv * 100, 2),
                ce_greeks=ce_greeks,
                pe_greeks=pe_greeks,
                ce_instrument_key=f"NSE_FO|NIFTY{strike}CE",
                pe_instrument_key=f"NSE_FO|NIFTY{strike}PE",
            )
        
        logger.info(f"📊 Synthetic chain generated: {len(self.chain)} strikes, ATM={self.atm_strike}")
    
    def _get_nearest_expiry(self) -> str:
        """Get nearest Thursday (weekly expiry for Nifty)."""
        import datetime
        today = datetime.date.today()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and datetime.datetime.now().hour >= 15:
            days_until_thursday = 7  # Next week if after market close on expiry day
        next_expiry = today + datetime.timedelta(days=days_until_thursday)
        self._current_expiry = next_expiry.strftime("%Y-%m-%d")
        return self._current_expiry
    
    @property
    def days_to_expiry(self) -> float:
        """Days remaining to nearest expiry."""
        return self._get_days_to_expiry()

    def _get_days_to_expiry(self) -> float:
        """Calculate days to nearest expiry."""
        import datetime
        if not self._current_expiry:
            self._get_nearest_expiry()

        try:
            expiry = datetime.datetime.strptime(self._current_expiry, "%Y-%m-%d")
            now = datetime.datetime.now()
            delta = expiry - now
            return max(0.1, delta.total_seconds() / 86400)  # At least 0.1 to avoid div-by-zero
        except Exception:
            return 3.0  # Default 3 days
    
    def _update_iv_history(self):
        """Track ATM IV for percentile calculation."""
        atm_entry = self.chain.get(self.atm_strike)
        if atm_entry:
            avg_iv = (atm_entry.ce_iv + atm_entry.pe_iv) / 2
            self._iv_history.append(avg_iv)
            # Keep last 100 readings
            if len(self._iv_history) > 100:
                self._iv_history = self._iv_history[-100:]
    
    # ─── Strike Selection Methods ───────────────────────────────────────────
    
    def get_entry(self, strike: float) -> Optional[OptionChainEntry]:
        """Get option chain entry for a specific strike."""
        return self.chain.get(strike)
    
    def get_atm_entry(self) -> Optional[OptionChainEntry]:
        """Get ATM option chain entry."""
        return self.chain.get(self.atm_strike)
    
    def get_strike_at_offset(self, offset_points: float) -> float:
        """Get strike at a given offset from ATM (in Nifty points)."""
        return self.atm_strike + round(offset_points / self.STRIKE_STEP) * self.STRIKE_STEP
    
    def get_iron_condor_strikes(
        self,
        short_offset: float = 100,
        wing_width: float = 200,
    ) -> Dict[str, float]:
        """
        Get strikes for an Iron Condor setup.
        
        Args:
            short_offset: Distance from ATM for short strikes (default 100 pts)
            wing_width: Width between short and long strikes (default 200 pts)
        
        Returns:
            {
                "short_ce": ATM + short_offset,
                "long_ce": ATM + short_offset + wing_width,
                "short_pe": ATM - short_offset,
                "long_pe": ATM - short_offset - wing_width,
            }
        """
        short_ce = self.get_strike_at_offset(short_offset)
        long_ce = self.get_strike_at_offset(short_offset + wing_width)
        short_pe = self.get_strike_at_offset(-short_offset)
        long_pe = self.get_strike_at_offset(-short_offset - wing_width)
        
        return {
            "short_ce": short_ce,
            "long_ce": long_ce,
            "short_pe": short_pe,
            "long_pe": long_pe,
        }
    
    def get_straddle_strikes(self) -> Dict[str, float]:
        """Get strikes for a Short Straddle (ATM CE + ATM PE)."""
        return {
            "ce_strike": self.atm_strike,
            "pe_strike": self.atm_strike,
        }
    
    def get_spread_strikes(
        self,
        direction: str,
        width: float = 100,
    ) -> Dict[str, float]:
        """
        Get strikes for directional spreads.
        
        Args:
            direction: "bull" (Bull Call Spread) or "bear" (Bear Put Spread)
            width: Spread width in Nifty points
        
        Returns:
            {"buy_strike": ..., "sell_strike": ...}
        """
        if direction == "bull":
            return {
                "buy_strike": self.atm_strike,
                "sell_strike": self.get_strike_at_offset(width),
            }
        else:
            return {
                "buy_strike": self.atm_strike,
                "sell_strike": self.get_strike_at_offset(-width),
            }
    
    @property
    def iv_percentile(self) -> float:
        """
        Current IV percentile relative to recent history.
        
        Returns:
            0-100 percentile. High = expensive options, better for selling.
        """
        if len(self._iv_history) < 5:
            return 50.0  # Default to neutral
        
        current_iv = self._iv_history[-1]
        below_count = sum(1 for iv in self._iv_history if iv <= current_iv)
        return round((below_count / len(self._iv_history)) * 100, 1)
    
    @property
    def pcr(self) -> float:
        """Put-Call Ratio based on OI from the chain."""
        total_ce_oi = sum(e.ce_oi for e in self.chain.values())
        total_pe_oi = sum(e.pe_oi for e in self.chain.values())
        
        if total_ce_oi == 0:
            return 1.0
        return round(total_pe_oi / total_ce_oi, 2)
    
    @property
    def max_pain(self) -> float:
        """
        Calculate Max Pain strike — where option writers have minimum payout.
        This is the strike where total option buyer losses are maximized.
        """
        if not self.chain:
            return self.atm_strike
        
        min_pain = float("inf")
        max_pain_strike = self.atm_strike
        
        strikes = sorted(self.chain.keys())
        
        for test_strike in strikes:
            total_pain = 0.0
            for strike, entry in self.chain.items():
                # CE buyer pain (if expiry at test_strike)
                ce_itm = max(0, test_strike - strike)
                total_pain += ce_itm * entry.ce_oi
                
                # PE buyer pain
                pe_itm = max(0, strike - test_strike)
                total_pain += pe_itm * entry.pe_oi
            
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_strike
        
        return max_pain_strike
    
    def get_chain_summary(self) -> dict:
        """Get summary for API/dashboard."""
        atm_entry = self.get_atm_entry()
        return {
            "spot_price": self.spot_price,
            "atm_strike": self.atm_strike,
            "expiry": self._current_expiry,
            "days_to_expiry": round(self._get_days_to_expiry(), 1),
            "iv_percentile": self.iv_percentile,
            "pcr": self.pcr,
            "max_pain": self.max_pain,
            "atm_ce_price": atm_entry.ce_price if atm_entry else 0,
            "atm_pe_price": atm_entry.pe_price if atm_entry else 0,
            "total_strikes": len(self.chain),
            "chain": [entry.to_dict() for entry in sorted(
                self.chain.values(), key=lambda e: e.strike
            )],
        }
