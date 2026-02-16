"""
Portfolio Stream Manager.
Uses Upstox PortfolioDataStreamer to receive real-time order and position updates.
"""

import json
import logging
import threading
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class PortfolioStreamManager:
    """Streams real-time order fills, rejections, and position changes from Upstox."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.streamer = None
        self.is_running = False
        self._connect_thread = None
        self.on_order_update: List[Callable] = []
        self._lock = threading.Lock()

    async def start(self):
        """Start the portfolio stream."""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Starting PortfolioStreamManager...")
        self._start_streamer()
        
        # Start monitor loop
        import asyncio
        asyncio.create_task(self._monitor_loop())

    def _start_streamer(self):
        """Initialize and connect the streamer."""
        try:
            with self._lock:
                if self.streamer:
                    try:
                        self.streamer.disconnect()
                    except:
                        pass
                
                import upstox_client
                from upstox_client import ApiClient, Configuration

                config = Configuration()
                config.access_token = self.access_token

                self.streamer = upstox_client.PortfolioDataStreamer(
                    api_client=ApiClient(config),
                    order_update=True,
                    position_update=True,
                )

                self.streamer.on("message", self._on_message)
                self.streamer.on("open", self._on_open)
                self.streamer.on("error", self._on_error)
                self.streamer.on("close", self._on_close)

            def connect_wrapper():
                try:
                    logger.info("Portfolio stream: connecting...")
                    self.streamer.connect()
                except Exception as e:
                    logger.error(f"Portfolio stream connect error: {e}")

            self._connect_thread = threading.Thread(target=connect_wrapper, daemon=True)
            self._connect_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start portfolio stream: {e}", exc_info=True)

    async def stop(self):
        """Stop the portfolio stream."""
        self.is_running = False
        with self._lock:
            if self.streamer:
                try:
                    self.streamer.disconnect()
                except Exception as e:
                    logger.debug(f"Portfolio stream disconnect: {e}")
        logger.info("Portfolio stream stopped")

    def update_access_token(self, token: str):
        """Update access token and restart streamer."""
        logger.info("🔄 PortfolioStreamManager: Updating access token...")
        self.access_token = token
        if self.is_running:
            self._start_streamer()

    async def _monitor_loop(self):
        """Monitor connection and reconnect if needed."""
        import asyncio
        while self.is_running:
            await asyncio.sleep(10)
            # Simple check: if we are supposed to be running, ensure streamer exists.
            # Upstox SDK doesn't expose a simple 'is_connected' property easily on the wrapper,
            # but we can check if the thread is alive or if we got recent updates.
            # For now, we relies on _on_error / _on_close to log, but we can force restart if needed.
            # A more robust way is to track last heartbeat, but SDK handles some internally.
            pass

    def _on_open(self, *args):
        logger.info("✅ Portfolio stream connected")

    def _on_close(self, *args):
        logger.warning("⚠️ Portfolio stream disconnected. Reconnecting...")
        if self.is_running:
            import time
            time.sleep(2)
            self._start_streamer()

    def _on_error(self, error, *args):
        logger.error(f"❌ Portfolio stream error: {error}")
        # Error often implies disconnect, so we might want to restart
        if self.is_running:
             import time
             time.sleep(2)
             self._start_streamer()

    def _on_message(self, message):
        """Handle incoming order/position update from Upstox."""
        try:
            if isinstance(message, str):
                data = json.loads(message)
            elif isinstance(message, dict):
                data = message
            else:
                return

            update_type = data.get("type", data.get("update_type", "unknown"))

            if update_type in ("order", "order_update"):
                order_data = data.get("data", data)
                order_event = {
                    "order_id": order_data.get("order_id", ""),
                    "status": order_data.get("status", ""),
                    "transaction_type": order_data.get("transaction_type", ""),
                    "instrument_token": order_data.get("instrument_token", ""),
                    "quantity": order_data.get("quantity", 0),
                    "filled_quantity": order_data.get("filled_quantity", 0),
                    "average_price": order_data.get("average_price", 0.0),
                    "rejection_reason": order_data.get("status_message", ""),
                    "order_type": order_data.get("order_type", ""),
                    "tag": order_data.get("tag", ""),
                }
                logger.info(
                    f"Order update: {order_event['order_id']} | "
                    f"{order_event['status']} | "
                    f"{order_event['transaction_type']} {order_event['instrument_token']} | "
                    f"filled={order_event['filled_quantity']}/{order_event['quantity']} @ {order_event['average_price']}"
                )

                for callback in self.on_order_update:
                    try:
                        callback(order_event)
                    except Exception as e:
                        logger.error(f"Order callback error: {e}")

            elif update_type in ("position", "position_update"):
                logger.debug(f"Position update received: {data}")

        except Exception as e:
            logger.error(f"Error processing portfolio message: {e}", exc_info=True)
