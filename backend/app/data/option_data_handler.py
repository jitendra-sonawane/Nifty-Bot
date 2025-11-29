"""
Real-time option Greeks streaming via WebSocket tick data.
Subscribes to option instrument keys and calculates Greeks on each tick.
"""

import threading
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime
from functools import lru_cache

from app.core.websocket_client import MarketDataSocket
from app.data.data_fetcher import DataFetcher
from app.core.greeks import GreeksCalculator
from app.core.logger_config import logger


class OptionDataHandler:
    """
    Handles real-time option data collection via WebSocket.
    
    - Subscribes to option contracts (CE/PE pairs)
    - Caches latest tick data (price, OI, volume)
    - Calculates Greeks on each tick update
    - Maintains Put-Call Ratio (PCR) in real-time
    - Emits updates via callback for broadcasting to frontend
    """
    
    def __init__(self, data_fetcher: DataFetcher, greeks_calc: GreeksCalculator, access_token: str = ""):
        """
        Initialize option data handler.
        
        Args:
            data_fetcher: DataFetcher instance for instrument lookup
            greeks_calc: GreeksCalculator instance for Greeks computation
            access_token: Upstox API access token for WebSocket connection
        """
        self.data_fetcher = data_fetcher
        self.greeks_calc = greeks_calc
        # Initialize WebSocket with proper parameters
        self.ws_client = MarketDataSocket(access_token)
        
        # Cache for latest option tick data
        self.option_price_cache: Dict[str, Dict] = {}
        self.option_oi_cache: Dict[str, float] = {}
        
        # Subscription tracking
        self.subscribed_keys: List[str] = []
        self.atm_ce_key: Optional[str] = None
        self.atm_pe_key: Optional[str] = None
        
        # Callbacks for emitting updates
        self.on_greeks_update: Optional[Callable] = None
        self.on_pcr_update: Optional[Callable] = None
        
        # Thread safety
        self.lock = threading.RLock()
        self.is_running = False
        
        logger.info("OptionDataHandler initialized")
    
    def subscribe_to_atm_options(self, symbol: str = "NIFTY", 
                                  expiry: Optional[str] = None) -> bool:
        """
        Subscribe to ATM call and put options.
        
        Args:
            symbol: Index/stock symbol (default: NIFTY)
            expiry: Expiry date (YYYY-MM-DD). If None, uses nearest expiry.
        
        Returns:
            True if subscription successful, False otherwise
        """
        try:
            # Get current spot price
            spot_price = self.data_fetcher.get_current_price(f"NSE_INDEX|{self._get_index_token(symbol)}")
            if not spot_price:
                logger.warning(f"Could not fetch spot price for {symbol}")
                return False
            
            # Get ATM strike
            atm_strike = self.data_fetcher.get_atm_strike(spot_price)
            
            # Get expiry if not provided
            if not expiry:
                expiry = self.data_fetcher.get_nearest_expiry()
            
            # Find instrument keys
            self.atm_ce_key = self.data_fetcher.get_option_instrument_key(
                symbol, expiry, atm_strike, "CE"
            )
            self.atm_pe_key = self.data_fetcher.get_option_instrument_key(
                symbol, expiry, atm_strike, "PE"
            )
            
            if not self.atm_ce_key or not self.atm_pe_key:
                logger.warning(f"Could not find ATM option keys for {symbol} {expiry} {atm_strike}")
                return False
            
            # Subscribe via WebSocket
            instrument_keys = [self.atm_ce_key, self.atm_pe_key]
            self.ws_client.subscribe(instrument_keys, "full")
            
            with self.lock:
                self.subscribed_keys.extend(instrument_keys)
                self.is_running = True
            
            logger.info(
                f"Subscribed to ATM options: {symbol} {expiry} {atm_strike} "
                f"(CE: {self.atm_ce_key}, PE: {self.atm_pe_key})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing to ATM options: {e}", exc_info=True)
            return False
    
    def subscribe_to_option_range(self, symbol: str, expiry: str, 
                                   center_strike: float, range_points: int = 500) -> bool:
        """
        Subscribe to all options within strike range (for PCR calculation).
        
        Args:
            symbol: Index/stock symbol
            expiry: Expiry date (YYYY-MM-DD)
            center_strike: Center strike for range
            range_points: Points above/below center
        
        Returns:
            True if subscription successful
        """
        try:
            # Get all options within range
            option_instruments = self.data_fetcher.instruments_df[
                (self.data_fetcher.instruments_df['name'] == symbol) &
                (self.data_fetcher.instruments_df['instrument_type'] == 'OPTIDX') &
                (self.data_fetcher.instruments_df['expiry'] == expiry) &
                (self.data_fetcher.instruments_df['strike'] >= center_strike - range_points) &
                (self.data_fetcher.instruments_df['strike'] <= center_strike + range_points)
            ]
            
            if option_instruments.empty:
                logger.warning(f"No options found in range {center_strike}±{range_points}")
                return False
            
            instrument_keys = option_instruments['instrument_key'].tolist()
            
            # Subscribe via WebSocket
            self.ws_client.subscribe(instrument_keys, "ltp")  # LTP mode for PCR (faster)
            
            with self.lock:
                self.subscribed_keys.extend(instrument_keys)
                if not self.is_running:
                    self.is_running = True
            
            logger.info(
                f"Subscribed to {len(instrument_keys)} option contracts "
                f"({symbol} {expiry} {center_strike}±{range_points})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing to option range: {e}", exc_info=True)
            return False
    
    def _on_tick_data(self, tick: Dict) -> None:
        """
        WebSocket callback: Handle incoming tick data for any subscribed option.
        
        Args:
            tick: Tick data dict with keys: instrumentKey, ltp, oi, volume, timestamp, etc.
        """
        try:
            instrument_key = tick.get('instrumentKey')
            if not instrument_key:
                return
            
            # Cache tick data
            with self.lock:
                self.option_price_cache[instrument_key] = {
                    'price': tick.get('ltp', 0),
                    'oi': tick.get('oi', 0),
                    'volume': tick.get('volume', 0),
                    'bid': tick.get('bid', 0),
                    'ask': tick.get('ask', 0),
                    'timestamp': tick.get('timestamp', datetime.now().isoformat())
                }
                self.option_oi_cache[instrument_key] = tick.get('oi', 0)
            
            # If this is an ATM option, calculate and emit Greeks
            if instrument_key in [self.atm_ce_key, self.atm_pe_key]:
                self._emit_greeks_update(instrument_key)
            
            # Emit PCR update if we have subscriptions for full range
            if len(self.subscribed_keys) > 2:  # More than just ATM CE/PE
                self._emit_pcr_update()
        
        except Exception as e:
            logger.error(f"Error processing tick data: {e}", exc_info=True)
    
    def _emit_greeks_update(self, instrument_key: str) -> None:
        """
        Calculate Greeks for an option and emit update.
        
        Args:
            instrument_key: Instrument key of the option
        """
        try:
            if not self.on_greeks_update:
                return
            
            # Get option details
            option_row = self.data_fetcher.instruments_df[
                self.data_fetcher.instruments_df['instrument_key'] == instrument_key
            ]
            
            if option_row.empty:
                return
            
            option_info = option_row.iloc[0]
            
            # Get current spot price
            spot_price = self.data_fetcher.get_current_price(
                f"NSE_INDEX|{self._get_index_token(option_info['name'])}"
            )
            if not spot_price:
                return
            
            # Get cached price
            with self.lock:
                if instrument_key not in self.option_price_cache:
                    return
                last_price = self.option_price_cache[instrument_key]['price']
            
            # Calculate time to expiry
            time_to_expiry = self.greeks_calc.time_to_expiry(option_info['expiry'])
            
            # Calculate IV
            iv = self.greeks_calc.implied_volatility(
                market_price=last_price,
                S=spot_price,
                K=option_info['strike'],
                T=time_to_expiry,
                option_type=option_info['option_type'],
                risk_free_rate=0.06
            )
            
            # Calculate Greeks
            greeks = self.greeks_calc.calculate_greeks(
                S=spot_price,
                K=option_info['strike'],
                T=time_to_expiry,
                sigma=iv,
                option_type=option_info['option_type'],
                risk_free_rate=0.06
            )
            
            # Emit update
            update = {
                'instrumentKey': instrument_key,
                'symbol': option_info['name'],
                'strike': option_info['strike'],
                'type': option_info['option_type'],
                'expiry': option_info['expiry'],
                'price': last_price,
                'oi': self.option_oi_cache.get(instrument_key, 0),
                'iv': iv,
                'greeks': greeks,
                'timestamp': datetime.now().isoformat()
            }
            
            self.on_greeks_update(update)
            
        except Exception as e:
            logger.error(f"Error calculating Greeks for {instrument_key}: {e}", exc_info=True)
    
    def _emit_pcr_update(self) -> None:
        """
        Calculate Put-Call Ratio from cached OI and emit update.
        """
        try:
            if not self.on_pcr_update or len(self.subscribed_keys) <= 2:
                return
            
            with self.lock:
                # Separate CE and PE OI
                total_ce_oi = sum([
                    oi for key, oi in self.option_oi_cache.items()
                    if self._get_option_type_from_key(key) == 'CE'
                ])
                
                total_pe_oi = sum([
                    oi for key, oi in self.option_oi_cache.items()
                    if self._get_option_type_from_key(key) == 'PE'
                ])
            
            if total_ce_oi <= 0:
                return
            
            pcr = total_pe_oi / total_ce_oi
            
            update = {
                'pcr': pcr,
                'totalCeOi': total_ce_oi,
                'totalPeOi': total_pe_oi,
                'timestamp': datetime.now().isoformat()
            }
            
            self.on_pcr_update(update)
            
        except Exception as e:
            logger.error(f"Error calculating PCR: {e}", exc_info=True)
    
    def get_greeks_cache(self) -> Dict[str, Dict]:
        """
        Get cached Greeks data for current ATM options.
        
        Returns:
            Dict with CE and PE Greeks
        """
        with self.lock:
            return {
                'atm_ce': self.option_price_cache.get(self.atm_ce_key, {}),
                'atm_pe': self.option_price_cache.get(self.atm_pe_key, {}),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_pcr_cache(self) -> Optional[float]:
        """
        Get cached PCR value.
        
        Returns:
            PCR ratio or None if unavailable
        """
        with self.lock:
            total_ce_oi = sum([
                oi for key, oi in self.option_oi_cache.items()
                if self._get_option_type_from_key(key) == 'CE'
            ])
            
            total_pe_oi = sum([
                oi for key, oi in self.option_oi_cache.items()
                if self._get_option_type_from_key(key) == 'PE'
            ])
        
        if total_ce_oi <= 0:
            return None
        
        return total_pe_oi / total_ce_oi
    
    def unsubscribe(self) -> None:
        """Unsubscribe from all option updates."""
        try:
            with self.lock:
                self.subscribed_keys.clear()
                self.is_running = False
            
            # Stop the WebSocket client (it handles unsubscription internally)
            if self.ws_client and hasattr(self.ws_client, 'stop'):
                self.ws_client.stop()
            
            logger.info("Unsubscribed from all option updates")
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}", exc_info=True)
    
    def shutdown(self) -> None:
        """Clean shutdown of option data handler."""
        try:
            self.unsubscribe()
            logger.info("OptionDataHandler shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    @staticmethod
    def _get_index_token(symbol: str) -> str:
        """Get index token from symbol name."""
        tokens = {
            "NIFTY": "99926009",
            "SENSEX": "99926037",
            "MIDCPNIFTY": "99926029",
            "FINNIFTY": "99926030"
        }
        return tokens.get(symbol, "99926009")  # Default to NIFTY
    
    def _get_option_type_from_key(self, instrument_key: str) -> Optional[str]:
        """Extract option type (CE/PE) from instrument key by looking it up."""
        try:
            option_row = self.data_fetcher.instruments_df[
                self.data_fetcher.instruments_df['instrument_key'] == instrument_key
            ]
            if not option_row.empty:
                return option_row.iloc[0]['option_type']
            return None
        except Exception:
            return None
