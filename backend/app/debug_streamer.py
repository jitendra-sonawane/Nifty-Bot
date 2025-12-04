import asyncio
import os
import logging
import threading
from dotenv import load_dotenv
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
from upstox_client import ApiClient, Configuration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load env
# We are in backend/app, so .env is in ../.env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)
access_token = os.getenv("UPSTOX_ACCESS_TOKEN")

if not access_token:
    logger.error(f"No access token found in {env_path}!")
    exit(1)

logger.info(f"Access Token: {access_token[:10]}...")

def on_message(message):
    logger.info(f"Received message: {str(message)[:200]}...")

def on_open():
    logger.info("Streamer Connected")

def on_error(error):
    logger.error(f"Streamer Error: {error}")

def on_close():
    logger.info("Streamer Closed")

async def main():
    instrument_keys = ["NSE_INDEX|Nifty 50"]
    logger.info(f"Subscribing to: {instrument_keys}")

    streamer = MarketDataStreamerV3(
        api_client=None,
        instrumentKeys=instrument_keys,
        mode="full"
    )

    config = Configuration()
    config.access_token = access_token
    streamer.api_client = ApiClient(config)

    streamer.on("message", on_message)
    streamer.on("open", on_open)
    streamer.on("error", on_error)
    streamer.on("close", on_close)

    logger.info("Connecting...")
    
    # Connect in background thread
    t = threading.Thread(target=streamer.connect, daemon=True)
    t.start()

    logger.info("Waiting for data...")
    await asyncio.sleep(30)
    logger.info("Done waiting.")

if __name__ == "__main__":
    asyncio.run(main())
