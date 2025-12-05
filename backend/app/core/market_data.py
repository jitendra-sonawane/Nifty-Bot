import asyncio
import time
import logging
import threading
from typing import List, Callable, Dict, Optional
from app.core.config import Config
from app.data.data_fetcher import DataFetcher
from app.core.greeks import GreeksCalculator
from app.core.pcr_calculator import PCRCalculator

# Import SDK's built-in market data streamer
try:
    from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
    HAS_SDK_STREAMER = True
except ImportError:
    HAS_SDK_STREAMER = False

from app.core.logger_config import logger

class MarketDataManager:
    def __init__(self, data_fetcher: DataFetcher, access_token: str):
        self.data_fetcher = data_fetcher
        self.access_token = access_token
        self.nifty_key = Config.SYMBOL_NIFTY_50
        self.pcr_calc = PCRCalculator()
        
        # State
        self.current_price = 0.0
        self.atm_strike = 0
        self.latest_pcr = None
        self.latest_pcr_analysis = None
        self.latest_vix = None
        self.latest_sentiment = {}
        self.latest_greeks = None
        self.previous_close = None
        self.market_movement = None  # Points up/down from previous close

        
        # Option instruments for WebSocket streaming (ATM options)
        self.option_ce_key = None
        self.option_pe_key = None
        self.option_ce_price = 0.0
        self.option_pe_price = 0.0
        self.option_expiry = None
        
        # PCR Options - WebSocket subscriptions for all options in strike range
        self.pcr_option_keys = []  # List of all option instrument keys for PCR
        self.pcr_option_metadata = {}  # Map: instrument_key -> {strike, option_type, trading_symbol}
        self.pcr_oi_data = {}  # Map: instrument_key -> open_interest value
        self.last_pcr_calculation = 0  # Timestamp of last PCR calculation
        self.pcr_calculation_interval = 5  # Calculate PCR every 5 seconds (from WebSocket OI data)
        
        # Event Callbacks
        self.on_price_update: List[Callable] = []
        self.on_market_data_update: List[Callable] = [] # Slower update (PCR, Greeks)
        
        # WebSocket - use SDK streamer if available
        self.streamer = None
        if HAS_SDK_STREAMER:
            logger.info("✅ Upstox SDK streamer available, will use built-in MarketDataStreamerV3")
        else:
            logger.warning("⚠️ Upstox SDK streamer not available")
        
        # Tasks
        self.tasks = []
        self.is_running = False

    async def start(self):
        self.is_running = True
        logger.info("Starting MarketDataManager...")
        logger.info(f"  - NIFTY Key: {self.nifty_key}")
        logger.info(f"  - Access Token Present: {bool(self.access_token)}")
        
        try:
            if not HAS_SDK_STREAMER:
                logger.error("❌ Upstox SDK streamer not available")
                raise ImportError("MarketDataStreamerV3 not available")
            
            logger.info("Creating MarketDataStreamerV3...")
            
            # Fetch previous day close
            await self._fetch_previous_close()
            
            # Get ATM option keys for WebSocket subscription
            # Get current Nifty price first
            current_nifty_price = self.data_fetcher.get_current_price(self.nifty_key)
            if current_nifty_price and current_nifty_price > 0:
                initial_price = current_nifty_price
                logger.info(f"📊 Using current Nifty price for ATM: ₹{initial_price}")
            else:
                initial_price = self.current_price if self.current_price > 0 else 24000
                logger.warning(f"⚠️ Using fallback price for ATM: ₹{initial_price}")
            
            self.atm_strike = round(initial_price / 50) * 50
            logger.info(f"🎯 Calculated ATM strike: {self.atm_strike}")
            
            # Get nearest expiry
            self.option_expiry = self.data_fetcher.get_nearest_expiry()
            
            # Get option instrument keys for ATM
            if self.option_expiry:
                self.option_ce_key = self.data_fetcher.get_option_instrument_key(
                    "NIFTY", self.option_expiry, self.atm_strike, "CE"
                )
                self.option_pe_key = self.data_fetcher.get_option_instrument_key(
                    "NIFTY", self.option_expiry, self.atm_strike, "PE"
                )
            
            # Get all option keys for PCR calculation (strike range ±500)
            pcr_options_data = self._get_pcr_option_keys(initial_price)
            self.pcr_option_keys = pcr_options_data['keys']
            self.pcr_option_metadata = pcr_options_data['metadata']
            
            # Build comprehensive instrument keys array
            instrument_keys = [self.nifty_key]
            
            # Add ATM options
            if self.option_ce_key and self.option_pe_key:
                instrument_keys.extend([self.option_ce_key, self.option_pe_key])
                logger.info(f"✅ ATM Option instruments found for strike {self.atm_strike}")
                logger.info(f"   CE: {self.option_ce_key}")
                logger.info(f"   PE: {self.option_pe_key}")
                logger.info(f"   Expiry: {self.option_expiry}")
            else:
                logger.warning(f"⚠️ Could not find ATM option instruments for strike {self.atm_strike}")
            
            # Add PCR options
            if self.pcr_option_keys:
                instrument_keys.extend(self.pcr_option_keys)
                ce_count = sum(1 for meta in self.pcr_option_metadata.values() if meta['option_type'] == 'CE')
                pe_count = sum(1 for meta in self.pcr_option_metadata.values() if meta['option_type'] == 'PE')
                logger.info(f"✅ PCR Option instruments: {len(self.pcr_option_keys)} total ({ce_count} CE, {pe_count} PE)")
                logger.info(f"   Strike range: ±500 from spot price {initial_price}")
            else:
                logger.warning(f"⚠️ Could not find PCR option instruments")
            
            # Log subscription summary
            logger.info(f"📊 WebSocket Subscription Summary:")
            logger.info(f"   - Nifty 50: 1 instrument")
            logger.info(f"   - ATM Options: 2 instruments")
            logger.info(f"   - PCR Options: {len(self.pcr_option_keys)} instruments")
            logger.info(f"   - Total: {len(instrument_keys)} instruments")
            logger.info(f"   - Capacity remaining: {5000 - len(instrument_keys)} / 5000")
            
            # Initialize with access token and all instruments
            self.streamer = MarketDataStreamerV3(
                api_client=None,  # Will create internally
                instrumentKeys=instrument_keys,  # Nifty + ATM Options + PCR Options!
                mode="full"  # Full mode for option data (bid/ask/oi/greeks)
            )
            
            # Set access token
            from upstox_client import ApiClient, Configuration
            config = Configuration()
            config.access_token = self.access_token
            self.streamer.api_client = ApiClient(config)
            
            # Register event listeners for decoded market data
            # The streamer will automatically decode protobuf and emit "message" events with dicts
            self.streamer.on("message", self._on_streamer_message)
            self.streamer.on("open", self._on_streamer_open)
            self.streamer.on("error", self._on_streamer_error)
            self.streamer.on("close", self._on_streamer_close)
            
            logger.info("🌐 Connecting to market data stream...")
            # Connect in background thread
            def connect_wrapper():
                try:
                    logger.info("🧵 Background thread: Starting streamer.connect()...")
                    self.streamer.connect()
                    logger.info("🧵 Background thread: streamer.connect() returned")
                except Exception as e:
                    logger.error(f"🧵 Background thread error: {e}", exc_info=True)
            
            connect_thread = threading.Thread(target=connect_wrapper, daemon=True)
            connect_thread.start()
            logger.info("✅ Background thread started")
            
            logger.info("✅ Market data streamer initialized")
            
            # Start background tasks
            self.tasks.append(asyncio.create_task(self._price_monitor_loop()))
            self.tasks.append(asyncio.create_task(self._websocket_pcr_loop()))  # New WebSocket-based PCR loop
            # self.tasks.append(asyncio.create_task(self._greeks_loop()))  # Disabled in favor of WebSocket streaming
            self.tasks.append(asyncio.create_task(self._connection_monitor()))
            logger.info("✅ All background tasks started")
        except Exception as e:
            logger.error(f"❌ Error starting MarketDataManager: {e}", exc_info=True)
            raise

    def _on_streamer_message(self, message):
        """Callback when streamer receives and decodes market data.
        This is called from the streamer's background thread with a dict."""
        try:
            # message is a dict with decoded market data from the streamer
            
            if isinstance(message, dict) and "feeds" in message:
                for key, feed in message["feeds"].items():
                    if key in self.pcr_option_metadata:
                         pass 
                    
                    if isinstance(feed, dict):
                        # Extract LTP and OI from various possible structures
                        price = None
                        oi = None
                        
                        # Handle fullFeed structure (V3 API)
                        if "fullFeed" in feed:
                            ff = feed["fullFeed"]
                            # Check for Index Feed
                            if "indexFF" in ff and "ltpc" in ff["indexFF"]:
                                price = ff["indexFF"]["ltpc"].get("ltp")
                            # Check for Market Feed (Options/Stocks)
                            elif "marketFF" in ff and "ltpc" in ff["marketFF"]:
                                price = ff["marketFF"]["ltpc"].get("ltp")
                                
                                # Extract Open Interest
                                if "oi" in ff["marketFF"]:
                                    oi = ff["marketFF"]["oi"]
                                elif "eFeedDetails" in ff["marketFF"]:
                                    oi = ff["marketFF"]["eFeedDetails"].get("oi")
                        
                        # Handle flat structure (if any)
                        elif "ltpc" in feed and isinstance(feed["ltpc"], dict):
                            price = feed["ltpc"].get("ltp")
                        elif "ltp" in feed:
                            price = feed["ltp"]
                        
                        # Store OI data for PCR options
                        if oi is not None and key in self.pcr_option_metadata:
                            self.pcr_oi_data[key] = float(oi)
                            # logger.debug(f"📊 OI Update: {key} -> {oi}")  # Too noisy for production, useful for debug
                        
                        # Debug logging for PCR options (sample)
                        if oi is not None and key in self.pcr_option_metadata and len(self.pcr_oi_data) % 10 == 0:
                             logger.debug(f"📊 PCR OI Update: {key} -> {oi} (Total tracked: {len(self.pcr_oi_data)})")
                        
                        if price is not None:
                            price = float(price)
                            
                            # Check if this is Nifty 50
                            if key == self.nifty_key:
                                self.current_price = price
                                
                                # Calculate market movement from previous close
                                if self.previous_close and self.previous_close > 0:
                                    self.market_movement = self.current_price - self.previous_close
                                
                                # Check if ATM has changed
                                new_atm = round(self.current_price / 50) * 50
                                if new_atm != self.atm_strike and self.atm_strike > 0:
                                    # ATM has changed, schedule async resubscription
                                    logger.info(f"🔔 ATM strike changing: {self.atm_strike} → {new_atm}")
                                    try:
                                        loop = asyncio.get_event_loop()
                                        if loop.is_running():
                                            # Schedule the coroutine to run in the event loop
                                            asyncio.run_coroutine_threadsafe(self._resubscribe_atm_options(new_atm), loop)
                                        else:
                                            logger.warning("⚠️ Event loop not running, cannot resubscribe ATM options")
                                    except RuntimeError:
                                        logger.warning("⚠️ No event loop available, cannot resubscribe ATM options")
                                else:
                                    # Just update the ATM value for display
                                    self.atm_strike = new_atm
                                
                                movement_str = f"{self.market_movement:+.2f}" if self.market_movement else "N/A"
                                logger.info(f"💰 Nifty price: ₹{price:.2f} (ATM: {self.atm_strike}) | Movement: {movement_str}")
                                
                                # Emit callback
                                for callback in self.on_price_update:
                                    if asyncio.iscoroutinefunction(callback):
                                        logger.debug(f"Skipping async callback from thread context")
                                    else:
                                        try:
                                            callback(price)
                                        except Exception as e:
                                            logger.error(f"Error in callback: {e}")
                            
                            # Check if this is CE option
                            elif key == self.option_ce_key:
                                self.option_ce_price = price
                                logger.info(f"📈 CE option ({self.atm_strike}): ₹{price:.2f}")
                                # Calculate Greeks when we have both prices
                                self._calculate_and_emit_greeks()
                            
                            # Check if this is PE option
                            elif key == self.option_pe_key:
                                self.option_pe_price = price
                                logger.info(f"📉 PE option ({self.atm_strike}): ₹{price:.2f}")
                                # Calculate Greeks when we have both prices
                                self._calculate_and_emit_greeks()
                
        except Exception as e:
            logger.error(f"Error processing streamer message: {e}", exc_info=True)
    
    def _on_streamer_open(self):
        """Called when streamer connection opens."""
        logger.info("✅ Market data stream connected")
    
    def _on_streamer_error(self, error):
        """Called when streamer has an error."""
        logger.error(f"❌ Market data stream error: {error}")
    
    def _on_streamer_close(self):
        """Called when streamer connection closes."""
        logger.warning("⚠️ Market data stream disconnected")
    
    def _calculate_and_emit_greeks(self):
        """Calculate Greeks from cached option prices and emit update."""
        try:
            # Need all data to calculate Greeks
            if not all([
                self.current_price > 0,
                self.option_ce_price > 0,
                self.option_pe_price > 0,
                self.atm_strike > 0,
                self.option_expiry
            ]):
                return
            
            # Import GreeksCalculator and Validator
            from app.core.greeks import GreeksCalculator
            from app.core.greeks_validator import validate_greeks_quality
            greeks_calc = GreeksCalculator()
            
            # Calculate time to expiry
            T = greeks_calc.time_to_expiry(self.option_expiry)
            if T <= 0:
                logger.warning(f"⚠️ Expiry already passed: {self.option_expiry}")
                return
            
            # Calculate IV for CE and PE
            ce_iv = greeks_calc.implied_volatility(
                self.option_ce_price, self.current_price, self.atm_strike, T, 'CE'
            )
            pe_iv = greeks_calc.implied_volatility(
                self.option_pe_price, self.current_price, self.atm_strike, T, 'PE'
            )
            
            # Calculate Greeks
            ce_greeks = greeks_calc.calculate_greeks(
                self.current_price, self.atm_strike, T, ce_iv, 'CE'
            )
            pe_greeks = greeks_calc.calculate_greeks(
                self.current_price, self.atm_strike, T, pe_iv, 'PE'
            )
            
            # Validate Greeks quality
            ce_greeks_with_iv = {**ce_greeks, 'iv': ce_iv}
            pe_greeks_with_iv = {**pe_greeks, 'iv': pe_iv}
            
            ce_validation = validate_greeks_quality(
                ce_greeks_with_iv, self.current_price, self.atm_strike, T, 'CE', self.option_ce_price
            )
            pe_validation = validate_greeks_quality(
                pe_greeks_with_iv, self.current_price, self.atm_strike, T, 'PE', self.option_pe_price
            )
            
            # Log quality issues
            if ce_validation['quality_score'] < 70:
                logger.warning(f"⚠️ CE Greeks quality: {ce_validation['summary']} ({ce_validation['quality_score']})")
                for error in ce_validation['errors']:
                    logger.error(f"   CE Error: {error}")
            
            if pe_validation['quality_score'] < 70:
                logger.warning(f"⚠️ PE Greeks quality: {pe_validation['summary']} ({pe_validation['quality_score']})")
                for error in pe_validation['errors']:
                    logger.error(f"   PE Error: {error}")
            
            # Build Greeks data structure
            self.latest_greeks = {
                'atm_strike': self.atm_strike,
                'expiry_date': str(self.option_expiry),
                'ce': {
                    'price': self.option_ce_price,
                    'iv': ce_iv,
                    'quality_score': ce_validation['quality_score'],
                    **ce_greeks
                },
                'pe': {
                    'price': self.option_pe_price,
                    'iv': pe_iv,
                    'quality_score': pe_validation['quality_score'],
                    **pe_greeks
                }
            }
            
            logger.debug(f"📊 Greeks calculated: CE ₹{self.option_ce_price:.2f} (Q:{ce_validation['quality_score']}), PE ₹{self.option_pe_price:.2f} (Q:{pe_validation['quality_score']})")
            
            # Emit update to callbacks (similar to PCR updates)
            data = {'greeks': self.latest_greeks}
            for callback in self.on_market_data_update:
                if asyncio.iscoroutinefunction(callback):
                    try:
                        asyncio.create_task(callback(data))
                    except Exception as e:
                        logger.error(f"Error in async greeks callback: {e}")
                else:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in greeks callback: {e}")
            
        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}", exc_info=True)

    async def _resubscribe_atm_options(self, new_atm_strike: int):
        """
        Resubscribe to new ATM options when strike changes.
        
        Args:
            new_atm_strike: The new ATM strike price
        """
        try:
            logger.info(f"🔄 ATM changed: {self.atm_strike} → {new_atm_strike}")
            
            # Get new option instrument keys
            new_ce_key = self.data_fetcher.get_option_instrument_key(
                "NIFTY", self.option_expiry, new_atm_strike, "CE"
            )
            new_pe_key = self.data_fetcher.get_option_instrument_key(
                "NIFTY", self.option_expiry, new_atm_strike, "PE"
            )
            
            if not new_ce_key or not new_pe_key:
                logger.warning(f"⚠️ Could not find new ATM options for strike {new_atm_strike}")
                return
            
            logger.info(f"📊 New option contracts:")
            logger.info(f"   CE: {self.option_ce_key} → {new_ce_key}")
            logger.info(f"   PE: {self.option_pe_key} → {new_pe_key}")
            
            # Unsubscribe from old options
            old_keys = []
            if self.option_ce_key:
                old_keys.append(self.option_ce_key)
            if self.option_pe_key:
                old_keys.append(self.option_pe_key)
            
            if old_keys and self.streamer:
                try:
                    self.streamer.unsubscribe(old_keys)
                    logger.info(f"✅ Unsubscribed from old options: {old_keys}")
                except Exception as e:
                    logger.warning(f"⚠️ Error unsubscribing: {e}")
            
            # Subscribe to new options
            new_keys = [new_ce_key, new_pe_key]
            if self.streamer:
                self.streamer.subscribe(new_keys, "full")
                logger.info(f"✅ Subscribed to new options: {new_keys}")
            
            # Update state
            self.option_ce_key = new_ce_key
            self.option_pe_key = new_pe_key
            self.atm_strike = new_atm_strike
            
            # Reset prices (will be updated by new ticks)
            self.option_ce_price = 0.0
            self.option_pe_price = 0.0
            
            logger.info(f"🎯 ATM resubscription complete")
            
        except Exception as e:
            logger.error(f"❌ Error in ATM resubscription: {e}", exc_info=True)

    def _get_pcr_option_keys(self, spot_price):
        """Get all option instrument keys needed for PCR calculation.
        
        Args:
            spot_price: Current Nifty 50 price
            
        Returns:
            dict with 'keys' (list of instrument keys) and 'metadata' (dict mapping keys to option info)
        """
        try:
            if self.data_fetcher.instruments_df is None:
                logger.warning("⚠️ Instruments not loaded, cannot get PCR options")
                return {'keys': [], 'metadata': {}}
            
            # Get nearest expiry
            expiry = self.data_fetcher.get_nearest_expiry()
            if not expiry:
                logger.warning("⚠️ No expiry found for PCR options")
                return {'keys': [], 'metadata': {}}
            
            import pandas as pd
            expiry_dt = pd.to_datetime(expiry)
            
            # Get options in strike range (±500 from spot)
            strike_range = 500
            nifty_opts = self.data_fetcher.instruments_df[
                (self.data_fetcher.instruments_df['name'] == 'NIFTY') & 
                (self.data_fetcher.instruments_df['instrument_type'] == 'OPTIDX') &
                (self.data_fetcher.instruments_df['expiry'] == expiry_dt) &
                (self.data_fetcher.instruments_df['strike'] >= spot_price - strike_range) &
                (self.data_fetcher.instruments_df['strike'] <= spot_price + strike_range)
            ]
            
            if nifty_opts.empty:
                logger.warning(f"⚠️ No options found in strike range {spot_price - strike_range} to {spot_price + strike_range}")
                return {'keys': [], 'metadata': {}}
            
            # Build metadata map
            metadata = {}
            for _, row in nifty_opts.iterrows():
                key = row['instrument_key']
                metadata[key] = {
                    'strike': row['strike'],
                    'option_type': row['option_type'],
                    'trading_symbol': row['tradingsymbol']
                }
            
            keys = list(metadata.keys())
            logger.info(f"📊 Found {len(keys)} PCR options for strike range {spot_price - strike_range} to {spot_price + strike_range}")
            
            return {'keys': keys, 'metadata': metadata}
            
        except Exception as e:
            logger.error(f"❌ Error getting PCR option keys: {e}", exc_info=True)
            return {'keys': [], 'metadata': {}}

    async def _websocket_pcr_loop(self):
        """Calculate PCR from WebSocket OI data (replaces HTTP polling)."""
        logger.info("Starting WebSocket PCR loop...")
        await asyncio.sleep(10)  # Wait for initial WebSocket data
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # Calculate PCR every 5 seconds (configurable)
                if current_time - self.last_pcr_calculation >= self.pcr_calculation_interval:
                    # Check if we have OI data
                    if not self.pcr_oi_data:
                        logger.debug("⏳ Waiting for WebSocket OI data...")
                        await asyncio.sleep(2)
                        continue
                    
                    # Calculate total CE and PE OI from WebSocket data
                    total_ce_oi = 0
                    total_pe_oi = 0
                    
                    for key, oi in self.pcr_oi_data.items():
                        if key in self.pcr_option_metadata:
                            opt_type = self.pcr_option_metadata[key]['option_type']
                            if opt_type == 'CE':
                                total_ce_oi += oi
                            elif opt_type == 'PE':
                                total_pe_oi += oi
                    
                    # Calculate PCR
                    if total_ce_oi > 0:
                        pcr = total_pe_oi / total_ce_oi
                        self.latest_pcr = round(pcr, 4)
                        self.last_pcr_calculation = current_time
                        
                        # Get PCR analysis
                        self.latest_pcr_analysis = self.pcr_calc.get_pcr_analysis(pcr, total_pe_oi, total_ce_oi)
                        self.pcr_calc.record_pcr(pcr, total_pe_oi, total_ce_oi)
                        
                        logger.info(f"📊 PCR Updated (WebSocket): {pcr:.4f} | CE OI: {total_ce_oi:,.0f} | PE OI: {total_pe_oi:,.0f} | Sentiment: {self.pcr_calc.get_sentiment(pcr)}")
                        logger.debug(f"   OI data points: {len(self.pcr_oi_data)}")
                    else:
                        logger.warning(f"⚠️ PCR calculation skipped: CE OI is zero")
                    
                    # Fetch VIX (still using HTTP - no WebSocket alternative)
                    loop = asyncio.get_running_loop()
                    vix = await loop.run_in_executor(None, self.data_fetcher.get_india_vix)
                    self.latest_vix = vix
                    
                    # Calculate sentiment
                    self._calculate_sentiment()
                    
                    # Notify listeners with complete sentiment data
                    data = {
                        "pcr": self.latest_pcr,
                        "pcr_analysis": self.latest_pcr_analysis,
                        "vix": vix,
                        "sentiment": self.latest_sentiment,
                        "pcrAnalysis": self.latest_pcr_analysis,
                        "previous_close": self.previous_close,
                        "market_movement": self.market_movement
                    }
                    for callback in self.on_market_data_update:
                        if asyncio.iscoroutinefunction(callback):
                            asyncio.create_task(callback(data))
                        else:
                            callback(data)
                            
            except Exception as e:
                logger.error(f"Error in WebSocket PCR loop: {e}", exc_info=True)
            
            await asyncio.sleep(1)  # Check every second, but only calculate every 5 seconds

    async def stop(self):
        self.is_running = False
        if self.streamer:
            try:
                self.streamer.close()
            except:
                pass
        
        for task in self.tasks:
            task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("MarketDataManager stopped.")

    async def _price_monitor_loop(self):
        """Monitor and emit price updates asynchronously."""
        last_price = None
        while self.is_running:
            if self.current_price != last_price and self.current_price > 0:
                last_price = self.current_price
                # Emit async callbacks
                for callback in self.on_price_update:
                    if asyncio.iscoroutinefunction(callback):
                        try:
                            await callback(self.current_price)
                        except Exception as e:
                            logger.error(f"Error in async callback: {e}")
            
            await asyncio.sleep(0.1)

    async def _connection_monitor(self):
        """Monitor streamer connection status and provide fallback data."""
        while self.is_running:
            try:
                # Check streamer state - look for feeder (WebSocket connection)
                feeder_connected = (
                    self.streamer is not None and
                    hasattr(self.streamer, 'feeder') and 
                    self.streamer.feeder is not None
                )
                
                # Also check if streamer has any subscriptions
                has_subs = False
                if self.streamer and hasattr(self.streamer, 'subscriptions'):
                    # Check if any subscriptions exist in any mode
                    for mode_subs in self.streamer.subscriptions.values():
                        if mode_subs:
                            has_subs = True
                            break
                
                logger.info(f"📊 Monitor: Connected={feeder_connected}, Subs={has_subs}, Price={self.current_price:.2f}, ATM={self.atm_strike}")
                
                # Fallback: fetch price via API if streamer not delivering
                if self.current_price == 0:
                    logger.warning("⚠️ No price from streamer, fetching via API...")
                    loop = asyncio.get_running_loop()
                    price = await loop.run_in_executor(None, self.data_fetcher.get_current_price, self.nifty_key)
                    if price and price > 0:
                        self.current_price = price
                        logger.info(f"✅ Fetched price via API: ₹{price:.2f}")
                    
            except Exception as e:
                logger.error(f"Connection monitor error: {e}", exc_info=True)
            
            await asyncio.sleep(5)

    async def _pcr_loop(self):
        """Fetches PCR and VIX periodically."""
        logger.info("Starting PCR loop...")
        await asyncio.sleep(5)  # Wait for initial price data
        while self.is_running:
            try:
                # Use current price if available, otherwise use fallback
                price = self.current_price if self.current_price > 0 else 24000
                
                # Run blocking calls in executor
                loop = asyncio.get_running_loop()
                
                pcr = await loop.run_in_executor(None, self.data_fetcher.get_nifty_pcr, price)
                vix = await loop.run_in_executor(None, self.data_fetcher.get_india_vix)
                
                self.latest_pcr = pcr
                self.latest_vix = vix
                
                # Get PCR analysis if PCR is available
                if pcr is not None:
                    self.latest_pcr_analysis = self.pcr_calc.get_pcr_analysis(pcr, 1, 1)
                    self.pcr_calc.record_pcr(pcr, 1, 1)
                    logger.info(f"📊 PCR Updated: {pcr:.4f} | Sentiment: {self.pcr_calc.get_sentiment(pcr)}")
                else:
                    logger.warning(f"⚠️ PCR calculation returned None")
                
                self._calculate_sentiment()
                
                # Notify listeners with complete sentiment data
                data = {
                    "pcr": pcr,
                    "pcr_analysis": self.latest_pcr_analysis,
                    "vix": vix,
                    "sentiment": self.latest_sentiment,
                    "pcrAnalysis": self.latest_pcr_analysis,
                    "previous_close": self.previous_close,
                    "market_movement": self.market_movement
                }
                for callback in self.on_market_data_update:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(data))
                    else:
                        callback(data)
                        
            except Exception as e:
                logger.error(f"Error in PCR loop: {e}", exc_info=True)
            
            await asyncio.sleep(30)

    async def _greeks_loop(self):
        """Fetches Greeks periodically. (DEPRECATED: Using WebSocket streaming)"""
        while self.is_running:
            try:
                if self.current_price > 0:
                    loop = asyncio.get_running_loop()
                    greeks = await loop.run_in_executor(None, self.data_fetcher.get_option_greeks, self.current_price)
                    self.latest_greeks = greeks
            except Exception as e:
                logger.error(f"Error in Greeks loop: {e}")
            
            await asyncio.sleep(5)

    def _calculate_sentiment(self):
        score = 50
        if self.latest_vix:
            if self.latest_vix < 12: score += 10
            elif 12 <= self.latest_vix < 15: score += 5
            elif 15 <= self.latest_vix < 20: score += 0
            else: score -= 10
        
        pcr_sentiment = None
        if self.latest_pcr:
            pcr_sentiment = self.pcr_calc.get_sentiment(self.latest_pcr)
            if pcr_sentiment == "EXTREME_BEARISH": score += 20
            elif pcr_sentiment == "BEARISH": score += 10
            elif pcr_sentiment == "NEUTRAL": score += 0
            elif pcr_sentiment == "BULLISH": score += 10
            elif pcr_sentiment == "EXTREME_BULLISH": score += 20
            
        score = max(0, min(100, score))
        
        if score >= 80: label = "Extreme Greed"
        elif score >= 60: label = "Greed"
        elif score >= 40: label = "Neutral"
        elif score >= 20: label = "Fear"
        else: label = "Extreme Fear"
        
        pcr_trend = self.pcr_calc.get_pcr_trend() if self.latest_pcr else None
        
        self.latest_sentiment = {
            "score": score,
            "label": label,
            "vix": self.latest_vix,
            "pcr": self.latest_pcr,
            "pcr_sentiment": pcr_sentiment,
            "pcr_emoji": self.pcr_calc.get_sentiment_emoji(pcr_sentiment) if pcr_sentiment else None,
            "pcr_trend": pcr_trend,
            "pcr_analysis": self.latest_pcr_analysis,
            "previous_close": self.previous_close,
            "market_movement": self.market_movement
        }

    async def _fetch_previous_close(self):
        """Fetch previous day's close price for market movement calculation."""
        try:
            loop = asyncio.get_running_loop()
            # Fetch 1-day historical data (yesterday's close)
            from datetime import datetime, timedelta
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            
            # Get historical data for yesterday
            df = await loop.run_in_executor(
                None,
                self.data_fetcher.get_historical_data,
                self.nifty_key,
                'day',
                yesterday.strftime('%Y-%m-%d'),
                today.strftime('%Y-%m-%d')
            )
            
            if df is not None and not df.empty:
                # Get the close price from yesterday's candle
                self.previous_close = df.iloc[0]['close']
                logger.info(f"📈 Previous day close: ₹{self.previous_close:.2f}")
            else:
                logger.warning("⚠️ Could not fetch previous day close")
        except Exception as e:
            logger.error(f"Error fetching previous close: {e}")

    def get_market_state(self):
        return {
            "current_price": self.current_price,
            "atm_strike": self.atm_strike,
            "pcr": self.latest_pcr,
            "pcr_analysis": self.latest_pcr_analysis,
            "vix": self.latest_vix,
            "sentiment": self.latest_sentiment,
            "greeks": self.latest_greeks,
            "previous_close": self.previous_close,
            "market_movement": self.market_movement
        }
