import asyncio
import time
import logging
import threading
from typing import List, Callable, Dict, Optional
from app.core.config import Config
from app.data.data_fetcher import DataFetcher
from app.core.greeks import GreeksCalculator

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
        
        # State
        self.current_price = 0.0
        self.atm_strike = 0
        self.latest_pcr = None
        self.latest_vix = None
        self.latest_sentiment = {}
        self.latest_greeks = None

        
        # Option instruments for WebSocket streaming
        self.option_ce_key = None
        self.option_pe_key = None
        self.option_ce_price = 0.0
        self.option_pe_price = 0.0
        self.option_expiry = None
        
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
            
            # Get ATM option keys for WebSocket subscription
            # Use fallback price if current_price not yet available
            initial_price = self.current_price if self.current_price > 0 else 24000
            self.atm_strike = round(initial_price / 50) * 50
            
            # Get nearest expiry
            self.option_expiry = self.data_fetcher.get_nearest_expiry()
            
            # Get option instrument keys
            if self.option_expiry:
                self.option_ce_key = self.data_fetcher.get_option_instrument_key(
                    "NIFTY", self.option_expiry, self.atm_strike, "CE"
                )
                self.option_pe_key = self.data_fetcher.get_option_instrument_key(
                    "NIFTY", self.option_expiry, self.atm_strike, "PE"
                )
            
            # Build instrument keys array
            instrument_keys = [self.nifty_key]
            if self.option_ce_key and self.option_pe_key:
                instrument_keys.extend([self.option_ce_key, self.option_pe_key])
                logger.info(f"✅ Option instruments found for ATM {self.atm_strike}")
                logger.info(f"   CE: {self.option_ce_key}")
                logger.info(f"   PE: {self.option_pe_key}")
                logger.info(f"   Expiry: {self.option_expiry}")
            else:
                logger.warning(f"⚠️ Could not find option instruments for ATM {self.atm_strike}")
                logger.warning(f"   Will only stream Nifty 50 prices")
            
            # Initialize with access token and all instruments
            self.streamer = MarketDataStreamerV3(
                api_client=None,  # Will create internally
                instrumentKeys=instrument_keys,  # Nifty + Options!
                mode="full"  # Full mode for option data (bid/ask/oi)
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
            self.tasks.append(asyncio.create_task(self._pcr_loop()))
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
                    if isinstance(feed, dict):
                        # Extract LTP from various possible structures
                        price = None
                        
                        # Handle fullFeed structure (V3 API)
                        if "fullFeed" in feed:
                            ff = feed["fullFeed"]
                            # Check for Index Feed
                            if "indexFF" in ff and "ltpc" in ff["indexFF"]:
                                price = ff["indexFF"]["ltpc"].get("ltp")
                            # Check for Market Feed (Options/Stocks)
                            elif "marketFF" in ff and "ltpc" in ff["marketFF"]:
                                price = ff["marketFF"]["ltpc"].get("ltp")
                        
                        # Handle flat structure (if any)
                        elif "ltpc" in feed and isinstance(feed["ltpc"], dict):
                            price = feed["ltpc"].get("ltp")
                        elif "ltp" in feed:
                            price = feed["ltp"]
                        
                        if price is not None:
                            price = float(price)
                            
                            # Check if this is Nifty 50
                            if key == self.nifty_key:
                                self.current_price = price
                                
                                # Check if ATM has changed
                                new_atm = round(self.current_price / 50) * 50
                                if new_atm != self.atm_strike and self.atm_strike > 0:
                                    # ATM has changed, trigger async resubscription
                                    logger.info(f"🔔 ATM strike changing: {self.atm_strike} → {new_atm}")
                                    asyncio.create_task(self._resubscribe_atm_options(new_atm))
                                else:
                                    # Just update the ATM value for display
                                    self.atm_strike = new_atm
                                
                                logger.info(f"💰 Nifty price: ₹{price:.2f} (ATM: {self.atm_strike})")
                                
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
            
            # Import GreeksCalculator
            from app.core.greeks import GreeksCalculator
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
            
            # Build Greeks data structure
            self.latest_greeks = {
                'atm_strike': self.atm_strike,
                'expiry_date': str(self.option_expiry),
                'ce': {
                    'price': self.option_ce_price,
                    'iv': ce_iv,
                    **ce_greeks
                },
                'pe': {
                    'price': self.option_pe_price,
                    'iv': pe_iv,
                    **pe_greeks
                }
            }
            
            logger.debug(f"📊 Greeks calculated: CE ₹{self.option_ce_price:.2f}, PE ₹{self.option_pe_price:.2f}")
            
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
        consecutive_zeros = 0
        last_msg_count = 0
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
                
                
                logger.info(f"📊 Monitor: Connected={feeder_connected}, Subs={has_subs}, "
                           f"Price={self.current_price:.2f}, ATM={self.atm_strike}")
                    
            except Exception as e:
                logger.error(f"Connection monitor error: {e}", exc_info=True)
            
            await asyncio.sleep(5)  # Check every 5 seconds

    async def _pcr_loop(self):
        """Fetches PCR and VIX periodically."""
        while self.is_running:
            try:
                if self.current_price > 0:
                    # Run blocking calls in executor
                    loop = asyncio.get_running_loop()
                    
                    pcr = await loop.run_in_executor(None, self.data_fetcher.get_nifty_pcr, self.current_price)
                    vix = await loop.run_in_executor(None, self.data_fetcher.get_india_vix)
                    
                    self.latest_pcr = pcr
                    self.latest_vix = vix
                    
                    self._calculate_sentiment()
                    
                    # Notify listeners
                    data = {
                        "pcr": pcr,
                        "vix": vix,
                        "sentiment": self.latest_sentiment
                    }
                    for callback in self.on_market_data_update:
                        if asyncio.iscoroutinefunction(callback):
                            asyncio.create_task(callback(data))
                        else:
                            callback(data)
                            
            except Exception as e:
                logger.error(f"Error in PCR loop: {e}")
            
            await asyncio.sleep(60) # Every minute

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
            
            await asyncio.sleep(5) # Every 5 seconds

    def _calculate_sentiment(self):
        score = 50
        if self.latest_vix:
            if self.latest_vix < 12: score += 10
            elif 12 <= self.latest_vix < 15: score += 5
            elif 15 <= self.latest_vix < 20: score += 0
            else: score -= 10
        
        if self.latest_pcr:
            if self.latest_pcr > 1.2: score += 15
            elif 0.8 <= self.latest_pcr <= 1.2: score += 0
            else: score -= 15
            
        score = max(0, min(100, score))
        
        if score >= 80: label = "Extreme Greed"
        elif score >= 60: label = "Greed"
        elif score >= 40: label = "Neutral"
        elif score >= 20: label = "Fear"
        else: label = "Extreme Fear"
        
        self.latest_sentiment = {
            "score": score,
            "label": label,
            "vix": self.latest_vix,
            "pcr": self.latest_pcr
        }

    def get_market_state(self):
        return {
            "current_price": self.current_price,
            "atm_strike": self.atm_strike,
            "pcr": self.latest_pcr,
            "vix": self.latest_vix,
            "sentiment": self.latest_sentiment,
            "sentiment": self.latest_sentiment,
            "greeks": self.latest_greeks
        }
