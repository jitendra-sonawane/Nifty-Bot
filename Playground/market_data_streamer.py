import os
import upstox_client
from upstox_client.rest import ApiException
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
from upstox_client import ApiClient, Configuration
from threading import Thread
import asyncio

class MarketDataStreamer:
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token
        self.feeder = None

    def on_open(self):
        print("WebSocket Connection Opened")

    def on_message(self, message):
        print(f"Received Message: {message}")

    def on_error(self, error):
        print(f"WebSocket Error: {error}")

    def on_close(self, close_status_code, close_msg):
        print(f"WebSocket Connection Closed: {close_status_code} - {close_msg}")

    def connect(self):
        try:
            # Create API client and configuration
            config = Configuration()
            config.access_token = self.access_token
            api_client = ApiClient(config)
            
            # Initialize the streamer with ApiClient and empty instrument list
            self.feeder = MarketDataStreamerV3(api_client=api_client, instrumentKeys=[], mode="full")
            
            # Register event handlers
            self.feeder.on('open', lambda: self.on_open())
            self.feeder.on('message', lambda msg: self._on_streamer_message(msg))
            self.feeder.on('error', lambda err: self.on_error(err))
            self.feeder.on('close', lambda code, msg: self.on_close(code, msg))
            
            # Connect
            self.feeder.connect()
        except Exception as e:
            print(f"Connection failed: {e}")

    def subscribe(self, instrument_keys, mode="full"):
        if self.feeder:
            try:
                self.feeder.subscribe(instrument_keys, mode)
                print(f"Subscribed to {instrument_keys} in {mode} mode")
            except Exception as e:
                print(f"Subscription failed: {e}")
        else:
            print("Feeder not connected")

    def _on_streamer_message(self, message):

        try:
            print(f"Streamer Message: {message}")
            if isinstance(message, dict) and 'feeds' in message:
                feeds = message.get('feeds') or []
                # handle list of feeds or single feed dict
                if isinstance(feeds, list):
                    for feed in feeds:
                        print(f"Feed: {feed}")
                else:
                    print(f"Feed: {feeds}")
            elif isinstance(message, list):
                for item in message:
                    print(f"Item: {item}")
        except Exception as e:
            print(f"Message handling error: {e}")

    def disconnect(self):
        if self.feeder:
            try:
                self.feeder.disconnect()
            except Exception as e:
                print(f"Disconnect error: {e}")
