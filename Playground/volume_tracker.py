import pandas as pd
import asyncio
from datetime import datetime
from collections import deque
from typing import Dict, List, Optional
import numpy as np

class OptimizedVolumeTracker:
    """
    Production-ready volume tracker for trading signals.
    
    Architecture:
    - Fast Path: Dictionary + Deques (per-token rolling windows)
    - Analysis Path: Pandas (only when needed for strategy/backtesting)
    - Signal Generation: Instant calculations without Pandas overhead
    """
    
    def __init__(self, window_size: int = 100, signal_threshold: float = 2.0):
        """
        Args:
            window_size: Keep last N ticks per instrument in memory
            signal_threshold: Spike multiplier (e.g., 2.0 = 2x above average)
        """
        # Fast lookup: token -> last volume
        self.last_volume_map: Dict[str, int] = {}
        
        self.last_oi_map :Dict[str,int]={}

        # Per-token rolling windows (efficient memory, O(1) access)
        self.token_windows: Dict[str, deque] = {}
        
        # Signal history for backtesting/analysis
        self.signals_generated: List[Dict] = []
        
        # Configuration
        self.window_size = window_size
        self.signal_threshold = signal_threshold
        
        # Per-token metadata
        self.token_metadata: Dict[str, Dict] = {}

    async def process_tick(self, tick: Dict) -> tuple[Optional[Dict], Dict]:
        """
        High-frequency entry point.
        Returns (signal, stats).
        - signal: Alert dict if generated, else None
        - stats: Basic stats for UI/Logging (always returned)
        """
        token = tick['token']
        current_vol = tick['volume']
        current_oi = tick['open_interest']
        # print(f"Open Interest from here volume tracker:{current_oi}")

        # --- STEP 1: State Update (O(1)) ---
        prev_vol = self.last_volume_map.get(token, 0)
        prev_oi = self.last_oi_map.get(token,0)
        # print(f"last oi map {self.last_oi_map}")
        change_in_volume = current_vol - prev_vol
        change_in_oi = current_oi- prev_oi

        self.last_volume_map[token] = current_vol
        self.last_oi_map[token]=current_oi

        # --- STEP 2: Initialize token if new ---
        if token not in self.token_windows:
            self.token_windows[token] = deque(maxlen=self.window_size)
            self.token_metadata[token] = {
                'strike': tick['strike'],
                'type': tick['type'],
                'first_seen': datetime.now()
            }
        
        # --- STEP 3: Store in rolling window ---
        tick_data = {
            'timestamp': datetime.now(),
            'volume': current_vol,
            'change_in_volume': change_in_volume,
            'oi': current_oi,
            'change_in_oi': change_in_oi
        }

        self.token_windows[token].append(tick_data)
        
        # --- STEP 4: Check for signals (no Pandas) ---
        signal = await self._check_signal(token)
        
        # DEBUG: Print status for every tick so we know it's working
        meta = self.token_metadata.get(token, {})
        stats = {
            'token': token,
            'strike': meta.get('strike', 'UNK'),
            'type': meta.get('type', 'UNK'),
            'volume': current_vol,
            'change_in_oi': change_in_oi,
            'change_in_volume':change_in_volume
        }

        # print(f" open interest:=>>> {stats['change_in_oi']}")

        if change_in_volume != 0:
            print(f"📉 Tick: {stats['strike']} {stats['type']} | Vol: {current_vol} | Change: {change_in_volume}")
        
        return signal, stats

    async def _check_signal(self, token: str) -> Optional[Dict]:
        """
        Instant signal generation without Pandas.
        
        Logic:
        - Need at least 10 historical ticks for reliable average
        - Signal: current change > 2x average change
        """
        window = self.token_windows[token]
        
        # Minimum history required
        if len(window) < 10:
            return None
        
        # Extract changes (O(1) operation on deque)
        change_in_volume = [tick['change_in_volume'] for tick in window]
        
        # Calculate statistics
        avg_volume_change = np.mean(change_in_volume)
        std_volume_change = np.std(change_in_volume)
        current_volume_change = change_in_volume[-1]
        
        # Signal: Unusual spike
        if avg_volume_change > 0 and current_volume_change > (avg_volume_change * self.signal_threshold):
            signal = {
                'timestamp': datetime.now(),
                'token': token,
                'strike': self.token_metadata[token]['strike'],
                'type': self.token_metadata[token]['type'],
                'current_volume_change': current_volume_change,
                'avg_volume_change': avg_volume_change,
                'volume_spike_ratio': current_volume_change / avg_volume_change,
                'std_dev': std_volume_change,
                'signal_type': 'VOLUME_SPIKE'
            }
            
            # Store for later analysis
            self.signals_generated.append(signal)
            
            return signal
        
        return None

    async def get_token_stats(self, token: str) -> Optional[Dict]:
        """
        Analyze a specific token (uses deque, no Pandas).
        Useful for pre-trade checks.
        """
        if token not in self.token_windows:
            return None
        
        window = self.token_windows[token]
        if len(window) < 10:
            return None
        
        changes = [tick['change_in_volume'] for tick in window]
        volumes = [tick['volume'] for tick in window]
        
        return {
            'token': token,
            'current_volume': volumes[-1],
            'avg_change_last_10': np.mean(changes[-10:]),
            'avg_change_all_time': np.mean(changes),
            'max_change': max(changes),
            'min_change': min(changes),
            'volatility': np.std(changes),
            'ticks_recorded': len(window)
        }

    async def export_to_pandas(self, token: Optional[str] = None) -> pd.DataFrame:
        """
        Convert to Pandas for:
        - Backtesting
        - Feature engineering for ML
        - Post-market analysis
        
        Args:
            token: Export specific token, or all if None
        """
        data_to_export = []
        
        if token:
            tokens = [token] if token in self.token_windows else []
        else:
            tokens = list(self.token_windows.keys())
        
        for t in tokens:
            window = self.token_windows[t]
            metadata = self.token_metadata[t]
            
            for tick in window:
                data_to_export.append({
                    'timestamp': tick['timestamp'],
                    'token': t,
                    'strike': metadata['strike'],
                    'type': metadata['type'],
                    'volume': tick['volume'],
                    'change': tick['change_in_volume']
                })
        
        df = pd.DataFrame(data_to_export)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
        
        return df

    async def backtest_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Backtest signal generation on historical data.
        
        Args:
            df: Historical data with columns [timestamp, token, volume, change, type, strike]
        
        Returns:
            DataFrame with signal annotations
        """
        df = df.copy()
        df['signal'] = 0
        
        # Group by token
        for token, group in df.groupby('token'):
            changes = group['change'].values
            
            for i in range(10, len(changes)):
                window_changes = changes[max(0, i-10):i]
                avg_change = np.mean(window_changes)
                current_change = changes[i]
                
                if avg_change > 0 and current_change > (avg_change * self.signal_threshold):
                    df.loc[group.index[i], 'signal'] = 1
        
        return df

    def get_all_signals(self) -> pd.DataFrame:
        """
        Export all generated signals as DataFrame for analysis.
        """
        if not self.signals_generated:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.signals_generated)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df.sort_values('timestamp').reset_index(drop=True)

    def memory_usage(self) -> Dict:
        """
        Monitor memory footprint (important for 24/7 trading).
        """
        total_ticks = sum(len(window) for window in self.token_windows.values())
        
        return {
            'total_instruments_tracked': len(self.token_windows),
            'total_ticks_in_memory': total_ticks,
            'avg_ticks_per_instrument': total_ticks / len(self.token_windows) if self.token_windows else 0,
            'max_memory_per_instrument_mb': (self.window_size * 100) / 1024 / 1024,  # Rough estimate
            'signals_generated': len(self.signals_generated)
        }


# ============================================================================
# EVENT BUS INTEGRATION
# ============================================================================
from event_bus import event_bus, MarketEvent, ExceptionMode

# class OpenInterestAnalysisService:


class VolumeAnalysisService:
    def __init__(self):
        self.tracker = OptimizedVolumeTracker(window_size=100, signal_threshold=2.0)
        print("✅ Volume Analysis Service Initialized")

    async def handle_market_tick(self, event: MarketEvent):
        """
        Event subscriber callback.
        Receives MARKET_TICK, processes it, and publishes VOLUME_SPIKE if found.
        """
        data = event.data
        
        # Only process Options ticks
        if data.get('type') != 'OPTION':
            return
            
        # Structure data for tracker
        # Note: In a real scenario, we'd need to parse strike/type from token or have it passed
        # For now, we'll try to extract it or use placeholders if missing
        tick_data = {
            'token': data['token'],
            'strike': data.get('strike', 0),    # Streamer needs to provide this or we parse
            'type': data.get('option_type', 'UNK'), # Streamer needs to provide this
            'volume': data['volume'],
            'open_interest': data.get('open_interest', 0)
        }
        
        signal, stats = await self.tracker.process_tick(tick_data)
        
        # 1. Publish Real-time Update (For UI)
        if stats['change_in_volume'] != 0:
             await event_bus.publish(MarketEvent(
                event_type="VOLUME_UPDATE",
                data=stats
            ))
        
        # 2. Publish Spike Alert (For Trading/Notifications)
        if signal:
            print(f"🚨 VOLUME SPIKE DETECTED on {tick_data['token']}!")
            # Publish Alert back to bus
            await event_bus.publish(MarketEvent(
                event_type="VOLUME_SPIKE",
                data=signal
            ))

# Global service instance
volume_service = VolumeAnalysisService()

async def setup_volume_service():
    """Call this from your main entry point"""
    event_bus.subscribe(
        event_type="MARKET_TICK",
        callback=volume_service.handle_market_tick,
        mode=ExceptionMode.PARALLEL
    )
    print("subscribed to MARKET_TICK")

if __name__ == "__main__":
    # Standalone test (requires running streamer separately or mocking)
    pass