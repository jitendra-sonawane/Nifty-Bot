import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class StreamingEMA:
    def __init__(self, period):
        self.period = period
        self.alpha = 2 / (period + 1)
        self.prev_ema = None
        self.current_ema = None
        self.initialized = False

    def initialize(self, historical_series: pd.Series, last_candle_incomplete=False):
        """
        Initialize with historical data series (close prices).
        
        Args:
            historical_series: Series of historical close prices
            last_candle_incomplete: If True, the last value in series is considered 
                                  an incomplete/forming candle, so prev_ema will be set 
                                  to the second-to-last value.
        """
        if historical_series.empty:
            return
            
        # Calculate initial EMA using pandas for the history
        # adjust=False matches the recursive formula: EMA_t = Price_t * alpha + EMA_t-1 * (1-alpha)
        ema_series = historical_series.ewm(span=self.period, adjust=False).mean()
        
        if last_candle_incomplete and len(ema_series) > 1:
            # The last value is the 'current' temporary EMA
            # The previous value is the 'finalized' previous EMA
            self.prev_ema = ema_series.iloc[-2]
            self.current_ema = ema_series.iloc[-1]
            logger.info(f"🔄 StreamingEMA Initialized (Incomplete Last): Prev={self.prev_ema:.2f}, Current={self.current_ema:.2f}")
        else:
            # Store the last finalized EMA (from the last closed candle)
            self.prev_ema = ema_series.iloc[-1]
            self.current_ema = self.prev_ema
            logger.info(f"✅ StreamingEMA Initialized (Complete Last): Prev={self.prev_ema:.2f}, Current={self.current_ema:.2f}")
            
        self.initialized = True

    def update(self, current_price):
        """
        Update with the latest live price (tick).
        Returns the temporary EMA for the current forming candle.
        """
        if not self.initialized:
            self.prev_ema = current_price
            self.current_ema = current_price
            self.initialized = True
            return self.current_ema
            
        # Calculate standard EMA
        self.current_ema = (current_price * self.alpha) + (self.prev_ema * (1 - self.alpha))
        return self.current_ema

    def on_candle_close(self):
        """
        Call this when the candle closes.
        The current temporary EMA becomes the finalized previous EMA.
        """
        if self.current_ema is not None:
            self.prev_ema = self.current_ema
            logger.debug(f"StreamingEMA({self.period}) rolled over. New Prev: {self.prev_ema:.2f}")

class CandleManager:
    def __init__(self, timeframe='5minute'):
        self.timeframe = timeframe
        self.df = pd.DataFrame()
        self.current_candle_start = None
        self.interval_minutes = self._parse_interval(timeframe)
        
    def _parse_interval(self, timeframe):
        if timeframe == '1minute': return 1
        if timeframe == '5minute': return 5
        if timeframe == '10minute': return 10
        if timeframe == '15minute': return 15
        if timeframe == '30minute': return 30
        if timeframe == '60minute': return 60
        if timeframe == 'day': return 1440 # Approximation
        return 5 # Default

    def initialize(self, historical_df: pd.DataFrame):
        """
        Load initial historical data.
        Expects DataFrame with index as datetime and columns: open, high, low, close, volume
        """
        if historical_df is None or historical_df.empty:
            return
            
        self.df = historical_df.copy()
        # Ensure index is datetime
        if not isinstance(self.df.index, pd.DatetimeIndex):
            self.df.index = pd.to_datetime(self.df.index)
            
        # Determine the start time of the next candle based on the last candle in history
        last_candle_time = self.df.index[-1]
        self.current_candle_start = last_candle_time + timedelta(minutes=self.interval_minutes)
        
        logger.info(f"✅ CandleManager initialized. Last candle: {last_candle_time}. Next start: {self.current_candle_start}")

    def update(self, price: float, volume: float = 0):
        """
        Update the current candle with new tick data.
        Handles rollover if time has passed.
        Returns: (is_new_candle, current_df)
        """
        # Use timezone-aware datetime to match DataFrame index
        from datetime import timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        
        # Calculate the start time of the candle for the current time
        # E.g. 10:52:30 with 5min interval -> 10:50:00
        minute_block = (now.minute // self.interval_minutes) * self.interval_minutes
        candle_start_time = now.replace(minute=minute_block, second=0, microsecond=0)
        
        is_new_candle = False
        
        if self.df.empty:
            # Initialize first candle
            self._start_new_candle(candle_start_time, price, volume)
            self.current_candle_start = candle_start_time
            is_new_candle = True
            
        elif candle_start_time > self.df.index[-1]:
            # New candle period started
            if self.current_candle_start and candle_start_time >= self.current_candle_start:
                 # Finalize previous candle (it's already in the DF, just moving to next)
                 is_new_candle = True
                 self._start_new_candle(candle_start_time, price, volume)
                 self.current_candle_start = candle_start_time
        
        # Update the current (last) candle
        self._update_last_candle(price, volume)
        
        return is_new_candle, self.df

    def _start_new_candle(self, timestamp, price, volume):
        """Append a new row for the new candle."""
        new_row = pd.DataFrame({
            'open': [price],
            'high': [price],
            'low': [price],
            'close': [price],
            'volume': [volume]
        }, index=[timestamp])
        
        self.df = pd.concat([self.df, new_row])
        # Keep buffer size manageable (e.g., last 500 candles)
        if len(self.df) > 500:
            self.df = self.df.iloc[-500:]

    def _update_last_candle(self, price, volume):
        """Update the high, low, close of the last row."""
        idx = self.df.index[-1]
        
        # Update High
        if price > self.df.at[idx, 'high']:
            self.df.at[idx, 'high'] = price
            
        # Update Low
        if price < self.df.at[idx, 'low']:
            self.df.at[idx, 'low'] = price
            
        # Update Close
        self.df.at[idx, 'close'] = price
        
        # Update Volume (Add to existing? Or is it cumulative? 
        # Usually tick volume is incremental, but if we get total volume, we replace.
        # Assuming we don't get reliable tick volume here, we might just ignore or set it)
        # For now, let's assume we might want to accumulate if provided, or just set.
        # Let's just set it if provided.
        if volume > 0:
             self.df.at[idx, 'volume'] = volume
