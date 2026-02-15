import os
import time
from dotenv import load_dotenv
from market_data_streamer import MarketDataStreamer

# Load environment variables
load_dotenv()

API_KEY = os.getenv("UPSTOX_API_KEY")
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

def main():
    if not API_KEY or not ACCESS_TOKEN:
        print("Error: UPSTOX_API_KEY and UPSTOX_ACCESS_TOKEN must be set in .env file.")
        return

    print("Initializing Market Data Streamer...")
    streamer = MarketDataStreamer(API_KEY, ACCESS_TOKEN)

    try:
        # Connect to WebSocket
        streamer.connect()
        
        # Give it a moment to connect
        time.sleep(2)

        # Subscribe to a sample instrument
        # Example: NSE_INDEX|Nifty 50 is 'NSE_INDEX|Nifty 50' or similar key.
        # Ideally, we should fetch valid keys from the API, but for now we'll use a placeholder or a common one.
        # Let's try subscribing to Nifty 50 if we know the key, or just wait for connection.
        # Common key format: "NSE_INDEX|Nifty 50"
        sample_keys = ["NSE_INDEX|Nifty 50"] 
        streamer.subscribe(sample_keys)

        print("Press Ctrl+C to exit...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping streamer...")
        streamer.disconnect()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
