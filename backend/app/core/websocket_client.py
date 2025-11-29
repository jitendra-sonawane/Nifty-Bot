import websocket
import json
import ssl
import threading
import time
import logging
from urllib.parse import quote

# Configure logging FIRST
logger = logging.getLogger(__name__)

# Import protobuf decoder from Upstox SDK
try:
    from upstox_client.feeder.proto import MarketDataFeedV3_pb2
    HAS_PROTOBUF = True
    logger.info("✅ Protobuf decoder loaded successfully")
except ImportError as e:
    HAS_PROTOBUF = False
    logger.warning("⚠️ Could not import Upstox protobuf. Binary messages cannot be decoded: %s", e)

class MarketDataSocket:
    def __init__(self, access_token, instruments=None, data_event=None):
        self.access_token = access_token
        self.instruments = instruments if instruments else []
        self.ws = None
        self.is_connected = False
        self.latest_data = {} # Map of instrument_key -> { price: float, timestamp: int }
        self.thread = None
        self.should_stop = False
        self.data_event = data_event
        
        # Upstox V3 requires fetching an authorized URL first
        self.api_url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

    def set_access_token(self, token):
        self.access_token = token
        logger.info("WebSocket Client: Access Token updated.")

    def get_authorized_url(self):
        import requests
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        try:
            response = requests.get(self.api_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                url = data.get('data', {}).get('authorizedRedirectUri')
                if url:
                    logger.info(f"Authorized URL obtained: {url[:20]}...{url[-20:]}")
                return url
            elif response.status_code == 401:
                logger.error("❌ WebSocket Authorization Failed: 401 Unauthorized")
                logger.error("   Possible reasons:")
                logger.error("   1. Access token has expired")
                logger.error("   2. Access token is invalid or revoked")
                logger.error("   3. Access token was not saved properly")
                logger.error("   ➜ Please generate a new token via Auth in the dashboard")
                return None
            else:
                logger.error(f"Failed to get authorized URL: {response.status_code}")
                if response.text:
                    logger.error(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error fetching authorized URL: {e}")
            return None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
            
        self.should_stop = False
        self.thread = threading.Thread(target=self._run_forever)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.should_stop = True
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=5)

    def subscribe(self, instrument_keys, mode="full"):
        """Subscribe to additional instrument keys.
        
        Args:
            instrument_keys: List of instrument keys or single key string
            mode: "full" for full data, "ltp" for last traded price only
        """
        if isinstance(instrument_keys, str):
            instrument_keys = [instrument_keys]
        
        # Add to existing instruments list
        for key in instrument_keys:
            if key not in self.instruments:
                self.instruments.append(key)
        
        # If already connected, send subscription update
        if self.is_connected and self.ws:
            payload = {
                "guid": "some_guid",
                "method": "sub",
                "data": {
                    "mode": mode,
                    "instrumentKeys": instrument_keys
                }
            }
            try:
                self.ws.send(json.dumps(payload).encode('utf-8'))
                logger.info(f"Subscribed to {len(instrument_keys)} additional instruments in {mode} mode")
            except Exception as e:
                logger.error(f"Error subscribing to instruments: {e}")

    def _run_forever(self):
        retry_count = 0
        while not self.should_stop:
            try:
                authorized_url = self.get_authorized_url()
                if not authorized_url:
                    retry_count += 1
                    logger.error(f"⏳ WebSocket URL failed. Retrying in 10s... (attempt {retry_count})")
                    time.sleep(10)
                    continue

                # Reset retry count on successful URL
                retry_count = 0

                # Add User-Agent to avoid potential blocking
                header = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }

                self.ws = websocket.WebSocketApp(
                    authorized_url,
                    header=header,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
                
            except Exception as e:
                logger.error(f"WebSocket Connection Error: {e}")
                time.sleep(5) # Wait before reconnecting

    def _on_open(self, ws):
        logger.info("✅ WebSocket Connected")
        self.is_connected = True
        logger.info("📤 Sending subscription...")
        self._subscribe()
        logger.info("⏳ WebSocket ready for market data")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"❌ WebSocket Disconnected. Status: {close_status_code}, Message: {close_msg}")
        self.is_connected = False

    def _on_error(self, ws, error):
        logger.error(f"⚠️ WebSocket Error: {error}")

    def _on_message(self, ws, message):
        try:
            # Log first message for debugging
            if isinstance(message, bytes):
                logger.info(f"📨 Received binary message ({len(message)} bytes)")
            else:
                logger.info(f"📨 Received text message ({len(message)} chars)")
            
            # Upstox V3 sends binary protobuf-encoded messages
            if isinstance(message, bytes):
                if not HAS_PROTOBUF:
                    logger.warning("Received binary message but protobuf decoder not available")
                    return
                
                logger.info("🔄 Attempting to decode protobuf...")
                try:
                    # Decode protobuf FeedResponse
                    feed_response = MarketDataFeedV3_pb2.FeedResponse()
                    feed_response.ParseFromString(message)
                    logger.info("✅ Protobuf parsed successfully")
                    
                    # Convert protobuf to dict-like structure
                    self._process_protobuf_data(feed_response)
                    
                except Exception as e:
                    logger.error(f"❌ Error decoding protobuf message: {e}", exc_info=True)
                    
            else:
                # Try JSON if not binary
                logger.info("🔄 Attempting to parse as JSON...")
                data = json.loads(message)
                logger.info("✅ JSON parsed successfully")
                self._process_data(data)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse message as JSON: {e}")
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}", exc_info=True)

    def _process_protobuf_data(self, feed_response):
        """Process protobuf FeedResponse and extract market data."""
        try:
            logger.info(f"🔍 Protobuf data received. Type: {feed_response.type}")
            logger.info(f"🔍 Number of feeds: {len(feed_response.feeds)}")
            
            # feed_response.feeds is a map of instrument_key -> Feed
            if len(feed_response.feeds) == 0:
                logger.warning("⚠️ FeedResponse has no feeds!")
                logger.info(f"   Timestamp: {feed_response.currentTs}")
                return
            
            feed_count = len(feed_response.feeds)
            logger.info(f"📊 Processing {feed_count} feeds from protobuf message")
            
            for instrument_key, feed in feed_response.feeds.items():
                logger.info(f"  Processing instrument: {instrument_key}")
                try:
                    # Extract LTP price from the appropriate feed type
                    price = None
                    
                    # Check if it's a LTPC (lightweight) feed
                    if feed.HasField('ltpc'):
                        price = feed.ltpc.ltp
                        logger.info(f"    LTPC feed for {instrument_key}: {price}")
                    # Check if it's a full feed
                    elif feed.HasField('ff'):
                        price = feed.ff.ltp
                        logger.info(f"    Full feed for {instrument_key}: {price}")
                    # Check if it's an OHLC feed
                    elif feed.HasField('market_ohlc'):
                        price = feed.market_ohlc.close
                        logger.info(f"    OHLC feed for {instrument_key}: {price}")
                    else:
                        logger.warning(f"    Unknown feed type for {instrument_key}")
                        logger.debug(f"      Feed fields: {[f.name for f in feed.DESCRIPTOR.fields]}")
                    
                    if price is not None:
                        self.latest_data[instrument_key] = {
                            "price": float(price),
                            "timestamp": int(time.time())
                        }
                        logger.info(f"✅ Updated price for {instrument_key}: {price}")
                        
                except Exception as e:
                    logger.error(f"Error processing feed for {instrument_key}: {e}", exc_info=True)
            
            # Signal that new data is available
            if self.data_event:
                self.data_event.set()
                logger.debug("✅ Data event signaled")
                
        except Exception as e:
            logger.error(f"Error processing protobuf data: {e}", exc_info=True)

    def _subscribe(self):
        if not self.instruments:
            return
            
        # V3 Subscription Payload - using LTPC (lightweight) mode for continuous updates
        # Modes: ltpc (lightweight), full (complete data), option (greeks only), d30 (30-min OHLC)
        payload = {
            "guid": "niftybot",
            "method": "sub",
            "data": {
                "mode": "ltpc",  # Use LTPC for fast updates with minimal data
                "instrumentKeys": self.instruments
            }
        }
        
        try:
            msg = json.dumps(payload).encode('utf-8')
            logger.info(f"📤 Sending subscription for {len(self.instruments)} instruments in LTPC mode")
            logger.info(f"   Instruments: {self.instruments}")
            logger.info(f"   Payload: {payload}")
            self.ws.send(msg)
            logger.info(f"✅ Subscription message sent successfully")
        except Exception as e:
            logger.error(f"❌ Subscription Error: {e}", exc_info=True)

    def _process_data(self, data):
        # Process incoming data and update self.latest_data
        # Structure depends on API. 
        # Example: { "feeds": { "NSE_INDEX|Nifty 50": { "ltp": 19500.0, ... } } }
        
        if "feeds" in data:
            for key, feed in data["feeds"].items():
                if "ltp" in feed:
                    self.latest_data[key] = {
                        "price": float(feed["ltp"]),
                        "timestamp": int(time.time())
                    }
                elif "ff" in feed and "ltp" in feed["ff"]: # Full feed structure sometimes
                     self.latest_data[key] = {
                        "price": float(feed["ff"]["ltp"]),
                        "timestamp": int(time.time())
                    }
        
        if self.data_event:
            self.data_event.set()

    def get_ltp(self, instrument_key):
        data = self.latest_data.get(instrument_key)
        if data:
            price = data["price"]
            logger.debug(f"🔍 get_ltp({instrument_key}): {price}")
            return price
        else:
            logger.debug(f"🔍 get_ltp({instrument_key}): NOT FOUND in latest_data. Available keys: {list(self.latest_data.keys())}")
            return None
        return None
