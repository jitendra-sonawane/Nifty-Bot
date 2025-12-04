import asyncio
import logging
import datetime
from typing import List, Callable, Dict, Optional
from app.strategies.strategy import StrategyEngine
from app.strategies.reasoning import TradingReasoning
from app.data.data_fetcher import DataFetcher
from app.core.config import Config

logger = logging.getLogger(__name__)

class StrategyRunner:
    def __init__(self, strategy_engine: StrategyEngine, data_fetcher: DataFetcher):
        self.strategy_engine = strategy_engine
        self.data_fetcher = data_fetcher
        self.reasoning_engine = TradingReasoning()
        
        self.latest_signal = "WAITING"
        self.latest_strategy_data = {}
        self.latest_reasoning = {}
        self.target_contract = None
        
        # Signal Cooldown
        self.last_signal_time = {}
        self.signal_cooldown_seconds = 120
        
        # Support/Resistance Caching (recalculate every 5 minutes)
        self.last_sr_calculation_time = 0
        self.sr_cache_duration = 300
        self.cached_support_resistance = {}
        self.cached_breakout = {}
        
        # Callbacks
        self.on_signal: List[Callable] = []
        
        self.timeframe = Config.TIMEFRAME
        self.is_running = False

    async def on_price_update(self, current_price: float, market_state: Dict):
        """Called whenever price updates."""
        if not self.is_running:
            return None
            
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._run_strategy, current_price, market_state)
        except Exception as e:
            logger.error(f"Error running strategy: {e}")
            return None

    def _run_strategy(self, current_price: float, market_state: Dict):
        # Fetch historical data with correct date format (yyyy-mm-dd)
        from_date = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime('%Y-%m-%d')
        to_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Map timeframes to supported Upstox intervals
        # Upstox API supports: 1minute, 30minute, day, week, month
        # Note: 5minute is NOT supported, so we map it to 1minute
        interval_map = {
            '1minute': '1minute',
            '5minute': '5minute',
            '10minute': '10minute',
            '15minute': '15minute',
            '30minute': '30minute',
            '60minute': '60minute',
            'day': 'day',
            'week': 'week',
            'month': 'month'
        }
        interval = interval_map.get(self.timeframe, '5minute')
        
        logger.info(f"📊 Fetching v3 data: timeframe={self.timeframe}, interval={interval}, dates={from_date} to {to_date}")
        
        df = self.data_fetcher.get_historical_data('NSE_INDEX|Nifty 50', interval, from_date, to_date)
        # For 5-minute candles: EMA(5)=25min, EMA(20)=100min
        
        if df is not None and not df.empty:
            pcr = market_state.get('pcr')
            greeks = market_state.get('greeks')
            
            result = self.strategy_engine.check_signal(df, pcr=pcr, greeks=greeks)
            
            if isinstance(result, dict):
                signal = result.get('signal', 'HOLD')
                current_time = datetime.datetime.now().timestamp()
                if current_time - self.last_sr_calculation_time >= self.sr_cache_duration:
                    self.cached_support_resistance = result.get('support_resistance', {})
                    self.cached_breakout = result.get('breakout', {})
                    self.last_sr_calculation_time = current_time
                else:
                    result['support_resistance'] = self.cached_support_resistance
                    result['breakout'] = self.cached_breakout
                self.latest_strategy_data = result
            else:
                signal = result
                self.latest_strategy_data = {}
            
            self.latest_signal = signal
            
            # Generate Reasoning
            try:
                support_resistance = self.latest_strategy_data.get('support_resistance', {})
                breakout_data = self.latest_strategy_data.get('breakout', {})
                self.latest_reasoning = self.reasoning_engine.generate_reasoning(
                    self.latest_strategy_data,
                    current_price,
                    support_resistance,
                    breakout_data
                )
            except Exception as e:
                logger.error(f"Error generating reasoning: {e}")
            
            # Target Contract
            self.target_contract = None
            if greeks and 'expiry_date' in greeks:
                expiry = greeks['expiry_date']
                strike = greeks['atm_strike']
                if signal == "BUY_CE":
                    self.target_contract = f"NIFTY {expiry} {strike} CE"
                elif signal == "BUY_PE":
                    self.target_contract = f"NIFTY {expiry} {strike} PE"
            
            # Check Cooldown and Emit
            if signal in ["BUY_CE", "BUY_PE"]:
                current_time = datetime.datetime.now().timestamp()
                last_time = self.last_signal_time.get(signal, 0)
                
                if current_time - last_time >= self.signal_cooldown_seconds:
                    self.last_signal_time[signal] = current_time
                    logger.info(f"🚀 SIGNAL GENERATED: {signal} @ {current_price}")
                    
                    # Emit Signal
                    signal_data = {
                        "signal": signal,
                        "price": current_price,
                        "reasoning": self.latest_reasoning,
                        "target_contract": self.target_contract,
                        "greeks": greeks,
                        "market_data": {
                            "open": df['open'].iloc[-1],
                            "high": df['high'].iloc[-1],
                            "low": df['low'].iloc[-1],
                            "close": df['close'].iloc[-1],
                            "volume": df['volume'].iloc[-1]
                        },
                        "indicators": result
                    }
                    
                    # We need to call async callbacks from this sync method
                    # This is tricky because we are inside run_in_executor
                    # We should return the signal data and let the async caller handle emission
                    # OR we use a queue.
                    # For simplicity, let's just use the loop we know exists? No, thread safety.
                    # Best pattern: _run_strategy returns the signal payload, and the async wrapper emits it.
                    return signal_data
        
        return None

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False
