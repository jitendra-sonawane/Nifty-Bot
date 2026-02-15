import pandas as pd
import asyncio
from datetime import datetime

class VolumeTracker:
    def __init__(self):
        # 1. The Cheat Sheet (Fast Lookup)
        # Key: Instrument Token -> Value: Last Volume INT
        self.last_volume_map = {} 
        
        # Buffer to store processed ticks before moving to Pandas
        self.tick_buffer = []
        
        # The main storage for analysis
        self.history_df = pd.DataFrame()

    async def process_tick(self, tick):
        """
        High frequency entry point.
        Calculates change instantly using Dictionary.
        """
        token = tick['token']
        current_vol = tick['volume']
        
        # --- FAST STEP: Calculate Change (Dictionary) ---
        # Get previous volume (default to 0 if new)
        prev_vol = self.last_volume_map.get(token, 0)
        
        # Calculate instant change
        change = current_vol - prev_vol
        
        # Update cheat sheet
        self.last_volume_map[token] = current_vol
        
        # --- STORAGE STEP: Prepare for Pandas ---
        processed_data = {
            'timestamp': datetime.now(),
            'token': token,
            'strike': tick['strike'],
            'type': tick['type'],  # CE or PE
            'volume': current_vol,
            'change': change        # <--- We calculated this without Pandas!
        }
        
        self.tick_buffer.append(processed_data)
        
        print(f"Tick: {tick['type']} {tick['strike']} | Vol: {current_vol} | Change: {change}")

    async def flush_to_pandas(self):
        """
        Call this periodically (e.g. every 1 sec) to update the main DataFrame
        """
        if not self.tick_buffer:
            return

        print("\n--- Flushing buffer to DataFrame for Strategy Analysis ---")
        new_df = pd.DataFrame(self.tick_buffer)
        
        if self.history_df.empty:
            self.history_df = new_df
        else:
            self.history_df = pd.concat([self.history_df, new_df], ignore_index=True)
            
        # Clear buffer
        self.tick_buffer = []
        
        # Show what the strategy would see
        print(self.history_df.tail(5))
        print("----------------------------------------------------------\n")

if __name__ == "__main__":
    async def main():
        tracker = VolumeTracker()
        
        # Simulate a stream of data for NIFTY 19500 CE and PE
        
        # 1. First tick (Initialization)
        await tracker.process_tick({'token': '123456', 'strike': 19500, 'type': 'CE', 'volume': 1000})
        await tracker.process_tick({'token': '987654', 'strike': 19500, 'type': 'PE', 'volume': 500})
        
        # 2. Second tick (Volume Increases)
        await tracker.process_tick({'token': '123456', 'strike': 19500, 'type': 'CE', 'volume': 1050}) # +50
        await tracker.process_tick({'token': '987654', 'strike': 19500, 'type': 'PE', 'volume': 520})  # +20
        
        # Update DataFrame
        await tracker.flush_to_pandas()
        
        # 3. Third tick (Big Jump)
        await tracker.process_tick({'token': '123456', 'strike': 19500, 'type': 'CE', 'volume': 2000}) # +950
        
        # Update DataFrame again
        await tracker.flush_to_pandas()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
