import asyncio
import time
import logging
import threading
from typing import List, Callable, Dict, Optional, TYPE_CHECKING
from app.core.config import Config
from app.data.data_fetcher import DataFetcher
from app.core.greeks import GreeksCalculator
from app.core.pcr_calculator import PCRCalculator
from app.data.nifty50_api import NIFTY50_STOCKS

if TYPE_CHECKING:
    from app.intelligence import IntelligenceEngine

# Import SDK's built-in market data streamer
try:
    from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
    HAS_SDK_STREAMER = True
except ImportError:
    HAS_SDK_STREAMER = False

from app.core.logger_config import logger

class MarketDataManager:
    def __init__(
        self,
        data_fetcher: DataFetcher,
        access_token: str,
        intelligence_engine: Optional["IntelligenceEngine"] = None,
    ):
        self.data_fetcher = data_fetcher
        self.access_token = access_token
        self.nifty_key = Config.SYMBOL_NIFTY_50
        self.pcr_calc = PCRCalculator()
        self.intelligence_engine = intelligence_engine  # Optional plug-in

        # Bid/Ask depth cache: instrument_key → {"bids": [...], "asks": [...]}
        self.bid_ask_cache: Dict[str, Dict] = {}
        
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

        # API-provided Greeks (from option_greeks subscription mode)
        self._api_greeks_ce = None  # {delta, gamma, theta, vega, iv}
        self._api_greeks_pe = None
        self._api_greeks_timestamp = 0.0
        self._use_api_greeks = True  # Prefer API greeks over local Black-Scholes

        # Price Cache for Real-time PnL
        self.instrument_prices: Dict[str, float] = {}  # key -> price
        self.subscribed_keys: set = set() # Track all keys we are subscribed to
        
        # Option instruments for WebSocket streaming (ATM options)
        self.option_ce_key = None
        self.option_pe_key = None
        self.option_ce_price = 0.0
        self.option_pe_price = 0.0
        self.option_expiry = None
        
        # Nifty 50 Heatmap Data
        self.nifty50_quotes = {}  # Map: symbol -> { price, change, percent_change }
        self.nifty50_isins = {}   # Map: instrument_key -> symbol

        
        # PCR Options - WebSocket subscriptions for all options in strike range
        self.pcr_option_keys = []  # List of all option instrument keys for PCR
        self.pcr_option_metadata = {}  # Map: instrument_key -> {strike, option_type, trading_symbol}
        self.pcr_oi_data = {}  # Map: instrument_key -> open_interest value
        self._oi_first_received_logged = False  # One-time log when first OI arrives
        self._pe_feed_debug_logged = False  # One-time raw feed dump for PE option
        self.last_pcr_calculation = 0  # Timestamp of last PCR calculation
        self.pcr_calculation_interval = 5  # Calculate PCR every 5 seconds (from WebSocket OI data)
        self._last_greeks_fallback_time = 0.0  # Throttle fallback greeks fetch (avoid hammering API)
        self._last_vix_fetch = 0.0  # Timestamp of last VIX API call
        self._vix_cache_interval = 30.0  # Fetch VIX at most every 30 seconds
        
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
        self.main_loop = None  # To capture the main event loop

    async def start(self):
        self.is_running = True
        self.main_loop = asyncio.get_running_loop() # Capture loop here
        logger.info("Starting MarketDataManager...")
        
        # Start connection logic
        self._start_streamer_logic()

    def _start_streamer_logic(self):
        """Internal method to initialize and connect streamer."""
        try:
            if not HAS_SDK_STREAMER:
                logger.error("❌ Upstox SDK streamer not available")
                raise ImportError("MarketDataStreamerV3 not available")

            # If streamer exists, close it first
            if self.streamer:
                try:
                    self.streamer.close()
                except:
                    pass

            logger.info("Creating MarketDataStreamerV3...")

            # ── Initial price fetch (needed for ATM, PCR setup) ───────────
            if self.current_price == 0:
                current_nifty_price = self.data_fetcher.get_current_price(self.nifty_key)
                if current_nifty_price and current_nifty_price > 0:
                    self.current_price = current_nifty_price
                    logger.info(f"📊 Initial Nifty price: ₹{current_nifty_price}")
                else:
                    logger.warning("⚠️ Could not fetch initial Nifty price")

            initial_price = self.current_price if self.current_price > 0 else 24000

            # ── ATM strike calculation ────────────────────────────────────
            self.atm_strike = round(initial_price / 50) * 50
            logger.info(f"🎯 ATM strike: {self.atm_strike}")

            # ── Option expiry & instrument keys ───────────────────────────
            if not self.option_expiry:
                self.option_expiry = self.data_fetcher.get_nearest_expiry()

            if self.option_expiry and (not self.option_ce_key or not self.option_pe_key):
                self.option_ce_key = self.data_fetcher.get_option_instrument_key(
                    "NIFTY", self.option_expiry, self.atm_strike, "CE"
                )
                self.option_pe_key = self.data_fetcher.get_option_instrument_key(
                    "NIFTY", self.option_expiry, self.atm_strike, "PE"
                )
                if self.option_ce_key and self.option_pe_key:
                    logger.info(f"✅ ATM Options: CE={self.option_ce_key}, PE={self.option_pe_key}, Expiry={self.option_expiry}")
                else:
                    logger.warning(f"⚠️ Could not find ATM option instruments for strike {self.atm_strike}")

            # ── PCR option keys (strike range ±500) ───────────────────────
            if not self.pcr_option_keys:
                pcr_options_data = self._get_pcr_option_keys(initial_price)
                self.pcr_option_keys = pcr_options_data['keys']
                self.pcr_option_metadata = pcr_options_data['metadata']
                if self.pcr_option_keys:
                    ce_count = sum(1 for meta in self.pcr_option_metadata.values() if meta['option_type'] == 'CE')
                    pe_count = sum(1 for meta in self.pcr_option_metadata.values() if meta['option_type'] == 'PE')
                    logger.info(f"✅ PCR Options: {len(self.pcr_option_keys)} ({ce_count} CE, {pe_count} PE)")

            # ── Build instrument subscription list ────────────────────────
            instrument_keys = [self.nifty_key]

            # Add Nifty 50 stocks and build ISIN mapping
            for symbol, isin in NIFTY50_STOCKS.items():
                key = f"NSE_EQ|{isin}"
                instrument_keys.append(key)
                self.nifty50_isins[key] = symbol
            logger.info(f"✅ Added {len(NIFTY50_STOCKS)} Nifty 50 stocks")

            # Add ATM Options
            if self.option_ce_key and self.option_pe_key:
                instrument_keys.extend([self.option_ce_key, self.option_pe_key])

            # Add PCR options
            if self.pcr_option_keys:
                instrument_keys.extend(self.pcr_option_keys)

            logger.info(f"📊 Total subscriptions: {len(instrument_keys)} instruments")

            # ── Create streamer ───────────────────────────────────────────
            from upstox_client import ApiClient, Configuration
            config = Configuration()
            config.access_token = self.access_token

            self.streamer = MarketDataStreamerV3(
                api_client=ApiClient(config),
                instrumentKeys=instrument_keys,
                mode="full"
            )
            
            self.streamer.on("message", self._on_streamer_message)
            self.streamer.on("open", self._on_streamer_open)
            self.streamer.on("error", self._on_streamer_error)
            self.streamer.on("close", self._on_streamer_close)
            
            logger.info("🌐 Connecting to market data stream...")
            
            def connect_wrapper():
                try:
                    logger.info("🧵 Background thread: Starting streamer.connect()...")
                    self.streamer.connect()
                    logger.info("🧵 Background thread: streamer.connect() returned")
                except Exception as e:
                    logger.error(f"🧵 Background thread error: {e}")
            
            connect_thread = threading.Thread(target=connect_wrapper, daemon=True)
            connect_thread.start()
            
            # Initial tasks start only once
            if not self.tasks:
                self.tasks.append(asyncio.create_task(self._price_monitor_loop()))
                self.tasks.append(asyncio.create_task(self._websocket_pcr_loop()))
                self.tasks.append(asyncio.create_task(self._connection_monitor()))
                # Fetch prev close once
                asyncio.create_task(self._fetch_previous_close())
                
        except Exception as e:
            logger.error(f"❌ Error starting MarketDataManager: {e}", exc_info=True)

    def update_access_token(self, token: str):
        """Update access token and restart streamer."""
        logger.info("🔄 MarketDataManager: Updating access token...")
        self.access_token = token
        if self.is_running:
            self._start_streamer_logic()


    def _on_streamer_message(self, message):
        """Callback when streamer receives and decodes market data.
        This is called from the streamer's background thread with a dict."""
        try:
            # message is a dict with decoded market data from the streamer
            
            if isinstance(message, dict) and "feeds" in message:
                for key, feed in message["feeds"].items():
                    # One-time: dump raw PE option feed to see actual structure
                    if not self._pe_feed_debug_logged and key in self.pcr_option_metadata:
                        meta = self.pcr_option_metadata[key]
                        if meta.get('option_type') == 'PE':
                            self._pe_feed_debug_logged = True
                            logger.info(f"🔍 RAW PE FEED DUMP for {key} (strike={meta.get('strike')}): {feed}")

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
                                
                                # Extract Open Interest from various V3 feed locations
                                mff = ff["marketFF"]
                                if "oi" in mff:
                                    oi = mff["oi"]
                                elif "eFeedDetails" in mff:
                                    oi = mff["eFeedDetails"].get("oi")
                                elif "marketOHLC" in mff:
                                    # OI can also be in OHLC entries
                                    ohlc_data = mff["marketOHLC"]
                                    if isinstance(ohlc_data, dict) and "ohlc" in ohlc_data:
                                        for ohlc_entry in ohlc_data["ohlc"]:
                                            if isinstance(ohlc_entry, dict) and "oi" in ohlc_entry:
                                                oi = ohlc_entry["oi"]
                                                break
                        
                        # Handle flat structure (if any)
                        elif "ltpc" in feed and isinstance(feed["ltpc"], dict):
                            price = feed["ltpc"].get("ltp")
                        elif "ltp" in feed:
                            price = feed["ltp"]
                        
                        # store OI data for PCR options
                        if oi is not None and key in self.pcr_option_metadata:
                            self.pcr_oi_data[key] = float(oi)
                            if not self._oi_first_received_logged:
                                self._oi_first_received_logged = True
                                logger.info(f"📊 OI DATA FLOWING: First OI received for {key} = {oi} (OI analysis will activate after 3 snapshots)")

                        # Extract bid/ask depth from fullFeed for order book intelligence
                        if "fullFeed" in feed:
                            self._extract_bid_ask(key, feed["fullFeed"])

                        # Extract API-provided option Greeks (from option_greeks subscription mode)
                        self._extract_api_greeks(key, feed)

                        # CACHE PRICE for PnL
                        if price is not None:
                            try:
                                price_val = float(price)
                                self.instrument_prices[key] = price_val
                                # Also update nifty50_quotes if applicable
                            except Exception as e:
                                logger.error(f"Error caching price for {key}: {e}")
                                
                        # Debug logging for PCR options (sample)
                        if oi is not None and key in self.pcr_option_metadata and len(self.pcr_oi_data) % 10 == 0:
                             logger.debug(f"📊 PCR OI Update: {key} -> {oi} (Total tracked: {len(self.pcr_oi_data)})")
                        
                        # Nifty 50 Stock Update
                        if key in self.nifty50_isins:
                            symbol = self.nifty50_isins[key]
                            
                            # Get existing data or defaults
                            current_data = self.nifty50_quotes.get(symbol, {
                                "symbol": symbol,
                                "price": 0.0,
                                "change": 0.0,
                                "changePercent": 0.0,
                                "open": 0.0,
                                "high": 0.0,
                                "low": 0.0,
                                "close": 0.0,
                                "volume": 0
                            })
                            
                            # Extract LTP
                            new_price = price if price is not None else current_data["price"]
                            if new_price:
                                current_data["price"] = float(new_price)

                            # Extract OHLC and Close
                            close_price = current_data["close"]
                            open_price = current_data["open"]
                            high_price = current_data["high"]
                            low_price = current_data["low"]
                            
                            if "fullFeed" in feed:
                                ff = feed.get("fullFeed", {})
                                mff = ff.get("marketFF", {})
                                
                                # Try to get OHLC
                                if "ohlc" in mff:
                                    ohlc = mff["ohlc"]
                                    if "open" in ohlc: open_price = float(ohlc["open"])
                                    if "high" in ohlc: high_price = float(ohlc["high"])
                                    if "low" in ohlc: low_price = float(ohlc["low"])
                                    if "close" in ohlc: close_price = float(ohlc["close"])
                                
                                # Try to get Close from LTPC if not in OHLC
                                if "ltpc" in mff and "cp" in mff["ltpc"]:
                                    close_price = float(mff["ltpc"]["cp"])

                            # Try to get Close from LTPC outside fullFeed
                            if "ltpc" in feed and "cp" in feed["ltpc"]:
                                close_price = float(feed["ltpc"]["cp"])

                            # Calculate Change
                            if close_price > 0 and current_data["price"] > 0:
                                change = current_data["price"] - close_price
                                change_percent = (change / close_price) * 100
                                current_data["change"] = round(change, 2)
                                current_data["changePercent"] = round(change_percent, 2)
                                current_data["close"] = close_price
                            
                            # Update OHLC
                            current_data["open"] = open_price
                            current_data["high"] = high_price
                            current_data["low"] = low_price
                            
                            # Ensure High/Low match current price if 0 (handling initial state)
                            if current_data["price"] > 0:
                                if current_data["high"] == 0 or current_data["price"] > current_data["high"]:
                                    current_data["high"] = current_data["price"]
                                if current_data["low"] == 0 or current_data["price"] < current_data["low"]:
                                    current_data["low"] = current_data["price"]
                                if current_data["open"] == 0:
                                     current_data["open"] = current_data["price"]

                            self.nifty50_quotes[symbol] = current_data
                            # After every stock update push breadth + book to intelligence
                            self._push_intelligence_updates()


                        if price is not None:
                            price = float(price)
                            
                            
                            # Check if this is Nifty 50
                            if key == self.nifty_key:
                                self.current_price = price
                                
                                # Calculate market movement from previous close
                                if self.previous_close and self.previous_close > 0:
                                    self.market_movement = self.current_price - self.previous_close
                                
                                # Update ATM strike and subscriptions if needed
                                self._update_atm_from_price(self.current_price)
                                
                                movement_str = f"{self.market_movement:+.2f}" if self.market_movement else "N/A"
                                logger.info(f"💰 Nifty price: ₹{price:.2f} (ATM: {self.atm_strike}) | Movement: {movement_str}")
                                
                                # Emit callback (copy list to avoid mutation during iteration)
                                for callback in list(self.on_price_update):
                                    if asyncio.iscoroutinefunction(callback):
                                        if self.main_loop:
                                            # Use proper threadsafe scheduling
                                            asyncio.run_coroutine_threadsafe(callback(price), self.main_loop)
                                        else:
                                            logger.warning(f"Skipping async callback - no main loop captured")
                                    else:
                                        try:
                                            callback(price)
                                        except Exception as e:
                                            logger.error(f"Error in callback: {e}")
                            
                            # Check if this is CE option
                            elif key == self.option_ce_key:
                                self.option_ce_price = price
                                logger.info(f"📈 CE option ({self.atm_strike}): ₹{price:.2f}")
                                # Use API greeks if available, otherwise local Black-Scholes
                                self._emit_greeks_best_source()

                            # Check if this is PE option
                            elif key == self.option_pe_key:
                                self.option_pe_price = price
                                logger.info(f"📉 PE option ({self.atm_strike}): ₹{price:.2f}")
                                # Use API greeks if available, otherwise local Black-Scholes
                                self._emit_greeks_best_source()
                
        except Exception as e:
            logger.error(f"Error processing streamer message: {e}", exc_info=True)

    def _update_atm_from_price(self, price: float):
        """Update ATM strike based on current price and trigger resubscription if changed."""
        try:
            new_atm = round(price / 50) * 50
            
            # Subscribe if ATM changed OR if we have no ATM yet (initial state)
            if new_atm != self.atm_strike:
                # ATM has changed, schedule async resubscription
                logger.info(f"🔔 ATM strike changing: {self.atm_strike} → {new_atm}")
                
                # Update current ATM immediately to prevent multiple triggers
                old_atm = self.atm_strike
                self.atm_strike = new_atm
                
                try:
                    # If main loop is running, schedule the coroutine
                    if self.main_loop and self.main_loop.is_running():
                        asyncio.run_coroutine_threadsafe(self._resubscribe_atm_options(new_atm), self.main_loop)
                    else:
                        # If we are in the main loop (e.g. during sync call), we can't schedule threadsafe easily?
                        # Actually _on_streamer_message runs in a thread, so run_coroutine_threadsafe is correct.
                        # But if called from _connection_monitor (async), we should await it if possible, 
                        # or just create a task.
                        
                        # We need to detect if we are in a loop or not, but `main_loop` should be set.
                        if self.main_loop:
                             asyncio.run_coroutine_threadsafe(self._resubscribe_atm_options(new_atm), self.main_loop)
                        else:
                            logger.warning("⚠️ Event loop not captured, cannot resubscribe ATM options")
                except RuntimeError:
                    logger.warning("⚠️ Runtime error scheduling ATM resubscription")
            else:
                # Just ensure it's set (redundant but safe)
                self.atm_strike = new_atm
        except Exception as e:
            logger.error(f"Error updating ATM from price: {e}")
    
    def _extract_bid_ask(self, key: str, full_feed: dict) -> None:
        """
        Extract 5-level bid/ask depth from a decoded V3 fullFeed dict and
        cache it for the OrderBook intelligence module.

        Upstox V3 full-mode protobuf decodes to:
          fullFeed.marketFF.marketLevel.bidAskQuote  (list of Quote objects)
        Each entry: { bidQ, bidP, askQ, askP }
        """
        try:
            mff = full_feed.get("marketFF", {})
            market_level = mff.get("marketLevel", {})
            raw_depth = market_level.get("bidAskQuote", [])
            if not raw_depth:
                return

            bids = []
            asks = []
            for entry in raw_depth:
                bid_price = entry.get("bidP")
                bid_qty   = entry.get("bidQ")
                ask_price = entry.get("askP")
                ask_qty   = entry.get("askQ")
                if bid_price is not None and bid_qty is not None:
                    bids.append({"price": float(bid_price), "qty": float(bid_qty)})
                if ask_price is not None and ask_qty is not None:
                    asks.append({"price": float(ask_price), "qty": float(ask_qty)})

            if bids or asks:
                self.bid_ask_cache[key] = {"bids": bids, "asks": asks}
        except Exception as e:
            logger.debug(f"bid/ask extraction error for {key}: {e}")

    def _push_intelligence_updates(self) -> None:
        """
        Push the latest market snapshots to the intelligence engine.
        Called after nifty50 quotes are updated and after Greeks/IV updates.
        """
        if not self.intelligence_engine:
            return
        try:
            # Extract current ATM IV directly for IVRankModule (avoids None-in-dict issues)
            iv = None
            if self.latest_greeks:
                ce_data = self.latest_greeks.get("ce") or {}
                pe_data = self.latest_greeks.get("pe") or {}
                ce_iv = ce_data.get("iv")
                pe_iv = pe_data.get("iv")
                if ce_iv and pe_iv:
                    iv = (float(ce_iv) + float(pe_iv)) / 2
                elif ce_iv:
                    iv = float(ce_iv)
                elif pe_iv:
                    iv = float(pe_iv)

            self.intelligence_engine.update({
                "nifty50_quotes":      dict(self.nifty50_quotes),
                "bid_ask":             dict(self.bid_ask_cache),
                "option_ce_key":       self.option_ce_key,
                "option_pe_key":       self.option_pe_key,
                "greeks":              self.latest_greeks,
                "iv":                  iv,  # Direct IV for IVRankModule
                "pcr_oi_data":         dict(self.pcr_oi_data),
                "pcr_option_metadata": dict(self.pcr_option_metadata),
                "current_price":       self.current_price,
            })
        except Exception as e:
            logger.debug(f"Intelligence push error: {e}")

    def _on_streamer_open(self, *args):
        """Called when streamer connection opens."""
        logger.info("✅ Market data stream connected")
        
        # Re-subscribe to tracked instruments (active positions)
        if self.subscribed_keys:
            logger.info(f"🔄 Re-subscribing to {len(self.subscribed_keys)} tracked instruments...")
            try:
                # Convert set to list
                keys_to_subscribe = list(self.subscribed_keys)
                self.streamer.subscribe(keys_to_subscribe, "full")
                logger.info("✅ Re-subscription successful")
            except Exception as e:
                logger.error(f"❌ Error re-subscribing: {e}")
    
    def _on_streamer_error(self, error):
        """Called when streamer has an error."""
        logger.error(f"❌ Market data stream error: {error}")
    
    def _on_streamer_close(self, *args):
        """Called when streamer connection closes."""
        logger.warning("⚠️ Market data stream disconnected")
    
    def _extract_api_greeks(self, key: str, feed: dict):
        """Extract option Greeks delivered by the option_greeks subscription mode."""
        try:
            greeks_data = None

            # Option greeks mode delivers data in optionGreeks field
            if "optionGreeks" in feed:
                greeks_data = feed["optionGreeks"]
            elif "fullFeed" in feed:
                ff = feed["fullFeed"]
                if "optionGreeks" in ff:
                    greeks_data = ff["optionGreeks"]
                elif "marketFF" in ff and "optionGreeks" in ff["marketFF"]:
                    greeks_data = ff["marketFF"]["optionGreeks"]

            if not greeks_data:
                return

            import time
            # Upstox may use 'iv' or 'impliedVolatility' depending on API version
            iv_val = greeks_data.get("iv") or greeks_data.get("impliedVolatility") or greeks_data.get("implied_volatility")
            parsed = {
                "delta": greeks_data.get("delta"),
                "gamma": greeks_data.get("gamma"),
                "theta": greeks_data.get("theta"),
                "vega": greeks_data.get("vega"),
                "iv": iv_val,
            }

            # Only accept if we have at least delta
            if parsed["delta"] is None:
                return

            logger.info(f"📊 API Greeks for {key}: delta={parsed['delta']}, iv={parsed['iv']}, keys={list(greeks_data.keys())}")

            if key == self.option_ce_key:
                self._api_greeks_ce = parsed
                self._api_greeks_timestamp = time.time()
                logger.debug(f"API Greeks CE: delta={parsed['delta']:.4f} iv={parsed['iv'] or 0:.2f}")
            elif key == self.option_pe_key:
                self._api_greeks_pe = parsed
                self._api_greeks_timestamp = time.time()
                logger.debug(f"API Greeks PE: delta={parsed['delta']:.4f} iv={parsed['iv'] or 0:.2f}")

        except Exception as e:
            logger.debug(f"Error extracting API greeks for {key}: {e}")

    def _emit_greeks_best_source(self):
        """Emit Greeks using API values if fresh, otherwise fall back to local Black-Scholes."""
        import time

        api_fresh = (
            self._use_api_greeks
            and self._api_greeks_ce is not None
            and self._api_greeks_pe is not None
            and (time.time() - self._api_greeks_timestamp) < 10  # Stale after 10 seconds
        )

        if api_fresh:
            self._emit_api_greeks()
        else:
            self._calculate_and_emit_greeks()

    def _emit_api_greeks(self):
        """Build latest_greeks from API-provided values and emit to callbacks."""
        try:
            if not self._api_greeks_ce or not self._api_greeks_pe:
                return

            # Get IV from API greeks; fall back to Black-Scholes if API IV is missing/zero
            ce_iv = self._api_greeks_ce.get('iv')
            pe_iv = self._api_greeks_pe.get('iv')

            if (not ce_iv or not pe_iv) and self.option_expiry and self.current_price > 0:
                try:
                    from app.core.greeks import GreeksCalculator
                    greeks_calc = GreeksCalculator()
                    T = greeks_calc.time_to_expiry(str(self.option_expiry))
                    if T > 0:
                        if not ce_iv and self.option_ce_price > 0:
                            ce_iv = greeks_calc.implied_volatility(
                                self.option_ce_price, self.current_price, self.atm_strike, T, 'CE'
                            )
                            logger.debug(f"IV fallback (BS) for CE: {ce_iv}")
                        if not pe_iv and self.option_pe_price > 0:
                            pe_iv = greeks_calc.implied_volatility(
                                self.option_pe_price, self.current_price, self.atm_strike, T, 'PE'
                            )
                            logger.debug(f"IV fallback (BS) for PE: {pe_iv}")
                except Exception as e:
                    logger.debug(f"IV fallback calculation error: {e}")

            self.latest_greeks = {
                'atm_strike': self.atm_strike,
                'expiry_date': str(self.option_expiry),
                'ce_instrument_key': self.option_ce_key,
                'pe_instrument_key': self.option_pe_key,
                'source': 'api',
                'ce': {
                    'price': self.option_ce_price,
                    'iv': ce_iv or 0,
                    'delta': self._api_greeks_ce.get('delta') or 0,
                    'gamma': self._api_greeks_ce.get('gamma') or 0,
                    'theta': self._api_greeks_ce.get('theta') or 0,
                    'vega': self._api_greeks_ce.get('vega') or 0,
                    'rho': 0,
                    'quality_score': 95,  # API greeks are exchange-accurate
                },
                'pe': {
                    'price': self.option_pe_price,
                    'iv': pe_iv or 0,
                    'delta': self._api_greeks_pe.get('delta') or 0,
                    'gamma': self._api_greeks_pe.get('gamma') or 0,
                    'theta': self._api_greeks_pe.get('theta') or 0,
                    'vega': self._api_greeks_pe.get('vega') or 0,
                    'rho': 0,
                    'quality_score': 95,
                },
            }

            logger.debug(f"Using API greeks: CE delta={self._api_greeks_ce.get('delta', 0):.4f}, PE delta={self._api_greeks_pe.get('delta', 0):.4f}")

            # Push IV data to intelligence engine (IV Rank, etc.)
            self._push_intelligence_updates()

            # Emit to callbacks
            data = {'greeks': self.latest_greeks}
            for callback in list(self.on_market_data_update):
                if asyncio.iscoroutinefunction(callback):
                    try:
                        if self.main_loop:
                            asyncio.run_coroutine_threadsafe(callback(data), self.main_loop)
                    except Exception as e:
                        logger.error(f"Error in async API greeks callback: {e}")
                else:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in API greeks callback: {e}")

        except Exception as e:
            logger.error(f"Error emitting API greeks: {e}", exc_info=True)

    def _calculate_and_emit_greeks(self):
        """Calculate Greeks from cached option prices and emit update (local Black-Scholes fallback)."""
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
            
            # Build Greeks data structure (include instrument keys for trade execution)
            self.latest_greeks = {
                'atm_strike': self.atm_strike,
                'expiry_date': str(self.option_expiry),
                'ce_instrument_key': self.option_ce_key,
                'pe_instrument_key': self.option_pe_key,
                'source': 'black_scholes',
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

            # Push IV data to intelligence engine (IV Rank, etc.)
            self._push_intelligence_updates()

            # Emit update to callbacks (similar to PCR updates)
            data = {'greeks': self.latest_greeks}
            for callback in list(self.on_market_data_update):
                if asyncio.iscoroutinefunction(callback):
                    try:
                        if self.main_loop:
                            asyncio.run_coroutine_threadsafe(callback(data), self.main_loop)
                        else:
                             # Fallback if loop not captured (shouldn't happen if started correctly)
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

            # Subscribe to new options in both full and option_greeks modes
            new_keys = [new_ce_key, new_pe_key]
            if self.streamer:
                self.streamer.subscribe(new_keys, "full")
                logger.info(f"✅ Subscribed to new options (full mode): {new_keys}")
                try:
                    self.streamer.subscribe(new_keys, "option_greeks")
                    logger.info(f"✅ Subscribed to new options (option_greeks mode): {new_keys}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not subscribe option_greeks mode: {e}")
            
            # Update state
            self.option_ce_key = new_ce_key
            self.option_pe_key = new_pe_key
            self.atm_strike = new_atm_strike
            
            # Reset prices and API greeks (will be updated by new ticks)
            self.option_ce_price = 0.0
            self.option_pe_price = 0.0
            self._api_greeks_ce = None
            self._api_greeks_pe = None
            
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
                    ce_keys_with_oi = 0
                    pe_keys_with_oi = 0

                    for key, oi in self.pcr_oi_data.items():
                        if key in self.pcr_option_metadata:
                            opt_type = self.pcr_option_metadata[key]['option_type']
                            if opt_type == 'CE':
                                total_ce_oi += oi
                                if oi > 0:
                                    ce_keys_with_oi += 1
                            elif opt_type == 'PE':
                                total_pe_oi += oi
                                if oi > 0:
                                    pe_keys_with_oi += 1
                    
                    # Calculate PCR
                    if total_ce_oi > 0:
                        pcr = total_pe_oi / total_ce_oi
                        self.latest_pcr = round(pcr, 4)
                        self.last_pcr_calculation = current_time
                        
                        # Get PCR analysis
                        self.latest_pcr_analysis = self.pcr_calc.get_pcr_analysis(pcr, total_pe_oi, total_ce_oi)
                        self.pcr_calc.record_pcr(pcr, total_pe_oi, total_ce_oi)
                        
                        logger.info(
                            f"📊 PCR Updated (WebSocket): {pcr:.4f} | CE OI: {total_ce_oi:,.0f} ({ce_keys_with_oi} keys) | "
                            f"PE OI: {total_pe_oi:,.0f} ({pe_keys_with_oi} keys) | Sentiment: {self.pcr_calc.get_sentiment(pcr)}"
                        )
                        if pe_keys_with_oi == 0:
                            logger.warning(f"⚠️ PE OI is ZERO — no PE instruments reporting OI. Total OI data points: {len(self.pcr_oi_data)}")
                        logger.debug(f"   OI data points: {len(self.pcr_oi_data)}")
                    else:
                        logger.warning(f"⚠️ PCR calculation skipped: CE OI is zero")
                    
                    # Fetch VIX (still using HTTP - no WebSocket alternative)
                    # Cached: only fetch every 30 seconds to avoid hammering the API
                    if current_time - self._last_vix_fetch >= self._vix_cache_interval:
                        loop = asyncio.get_running_loop()
                        vix = await loop.run_in_executor(None, self.data_fetcher.get_india_vix)
                        self.latest_vix = vix
                        self._last_vix_fetch = current_time
                    vix = self.latest_vix
                    
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
                    for callback in list(self.on_market_data_update):
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
                # Emit async callbacks (copy to avoid mutation during iteration)
                for callback in list(self.on_price_update):
                    if asyncio.iscoroutinefunction(callback):
                        try:
                            await callback(self.current_price)
                        except Exception as e:
                            logger.error(f"Error in async callback: {e}")
            
            await asyncio.sleep(0.1)

    async def _connection_monitor(self):
        """Monitor streamer connection status and auto-reconnect if needed."""
        errors_count = 0
        while self.is_running:
            try:
                # Check streamer state - look for feeder (WebSocket connection)
                feeder_connected = (
                    self.streamer is not None and
                    hasattr(self.streamer, 'feeder') and 
                    self.streamer.feeder is not None and
                    getattr(self.streamer.feeder, 'connected', False)
                )
                
                # Also check API client token validity
                if errors_count > 3:
                     logger.warning("⚠️ Multiple connection failures. Consider checking access token.")
                
                if not feeder_connected:
                    logger.warning(f"⚠️ Streamer disconnected (Attempt {errors_count + 1}). Reconnecting...")
                    errors_count += 1
                    try:
                         # Re-run start logic which handles restart
                         self._start_streamer_logic()
                         # Reset stats if successful (though start logic does it async, 
                         # we assume it spins up thread)
                         await asyncio.sleep(5) 
                    except Exception as e:
                        logger.error(f"Reconnection attempt failed: {e}")
                else:
                    errors_count = 0 
                
                # Check subscriptions
                has_subs = False
                if self.streamer and hasattr(self.streamer, 'subscriptions'):
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
                        # Ensure ATM is updated even from API fallback
                        self._update_atm_from_price(price)
                        logger.info(f"✅ Fetched price via API: ₹{price:.2f}")
                    
            except Exception as e:
                logger.error(f"Connection monitor error: {e}", exc_info=True)
            
            await asyncio.sleep(10)

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
                for callback in list(self.on_market_data_update):
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(data))
                    else:
                        callback(data)

            except Exception as e:
                logger.error(f"Error in PCR loop: {e}", exc_info=True)
            
            await asyncio.sleep(5)  # Check every 5 seconds

    def subscribe_instruments(self, keys: List[str]):
        """
        Subscribe to a list of instrument keys for real-time updates.
        Used for tracking PnL of open positions.
        """
        if not self.streamer:
            logger.warning("⚠️ Streamer not initialized, cannot subscribe")
            return
            
        # Filter out keys already subscribed
        new_keys = [k for k in keys if k not in self.subscribed_keys]
        
        if not new_keys:
            return
            
        try:
            # Add to set first
            self.subscribed_keys.update(new_keys)
            
            # Subscribe
            self.streamer.subscribe(new_keys, "full")
            logger.info(f"✅ Subscribed to {len(new_keys)} new instruments for PnL tracking")
            logger.debug(f"   Keys: {new_keys}")
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to instruments: {e}")

    def get_price(self, key: str) -> float:
        """Get cached price for an instrument key."""
        return self.instrument_prices.get(key, 0.0)

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
            if pcr_sentiment == "EXTREME_BEARISH": score -= 20
            elif pcr_sentiment == "BEARISH": score -= 10
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
        # Fallback: if WebSocket hasn't delivered option ticks yet, fetch option quotes once (throttled)
        # so strategy can run and executor has greeks + instrument keys.
        if (
            self.latest_greeks is None
            and self.option_ce_key
            and self.option_pe_key
            and self.current_price > 0
            and (time.time() - self._last_greeks_fallback_time) >= 5.0
        ):
            self._last_greeks_fallback_time = time.time()
            try:
                quotes = self.data_fetcher.get_quotes([self.option_ce_key, self.option_pe_key])
                if quotes:
                    ce_quote = quotes.get(self.option_ce_key) or {}
                    pe_quote = quotes.get(self.option_pe_key) or {}
                    ce_price = float(ce_quote.get("last_price") or 0)
                    pe_price = float(pe_quote.get("last_price") or 0)
                    if ce_price > 0 and pe_price > 0:
                        self.option_ce_price = ce_price
                        self.option_pe_price = pe_price
                        self._calculate_and_emit_greeks()
                        if self.latest_greeks:
                            logger.debug("Greeks populated via fallback (REST quotes)")
            except Exception as e:
                logger.debug(f"Greeks fallback fetch failed: {e}")
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
