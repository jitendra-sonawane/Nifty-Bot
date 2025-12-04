import asyncio
import logging
import datetime
import pandas as pd
from typing import List, Callable, Dict, Optional
from app.strategies.strategy import StrategyEngine
from app.strategies.reasoning import TradingReasoning
from app.data.data_fetcher import DataFetcher
from app.core.config import Config
from app.core.streaming import StreamingEMA, CandleManager

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
        
        # Streaming Managers
        self.timeframe = Config.TIMEFRAME
        self.candle_manager = CandleManager(self.timeframe)
        self.ema_5 = StreamingEMA(5)
        self.ema_20 = StreamingEMA(20)
        self.is_initialized = False
        
        # Callbacks
        self.on_signal: List[Callable] = []
        
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
        if not self.is_initialized:
            self._initialize_data()
            if not self.is_initialized:
                return None

        # 1. Update Candle
        is_new_candle, df = self.candle_manager.update(current_price, volume=0)
        
        if is_new_candle:
            self.ema_5.on_candle_close()
            self.ema_20.on_candle_close()
            logger.info(f"🕯️ New Candle Started. Prev EMA5: {self.ema_5.prev_ema:.2f}")

        # 2. Update Streaming Indicators
        cur_ema_5 = self.ema_5.update(current_price)
        cur_ema_20 = self.ema_20.update(current_price)
        
        # 3. Inject into DataFrame
        if 'ema_5' not in df.columns:
            df['ema_5'] = pd.Series(dtype='float64')
        if 'ema_20' not in df.columns:
            df['ema_20'] = pd.Series(dtype='float64')
            
        idx = df.index[-1]
        df.at[idx, 'ema_5'] = cur_ema_5
        df.at[idx, 'ema_20'] = cur_ema_20
        
        # 4. Clean up other indicators to force recalculation
        cols_to_drop = ['rsi', 'supertrend', 'vwap', 'atr']
        for col in cols_to_drop:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)
        
        # 5. Run Strategy
        if df is not None and not df.empty:
            pcr = market_state.get('pcr')
            greeks = market_state.get('greeks')
            
            result = self.strategy_engine.check_signal(df, pcr=pcr, greeks=greeks)
            
            # DEBUG: Log what check_signal returned
            logger.info(f"🐛 DEBUG: check_signal result type: {type(result)}")
            if isinstance(result, dict):
                logger.info(f"🐛 DEBUG: Result keys: {result.keys()}")
                logger.info(f"🐛 DEBUG: Signal: {result.get('signal')}")
                logger.info(f"🐛 DEBUG: RSI: {result.get('rsi')}")
                logger.info(f"🐛 DEBUG: EMA 5: {result.get('ema_5')}")
                logger.info(f"🐛 DEBUG: EMA 20: {result.get('ema_20')}")
                logger.info(f"🐛 DEBUG: Filters: {result.get('filters')}")
            
            if isinstance(result, dict):
                signal = result.get('signal', 'HOLD')
                
                # Cache S/R
                current_time = datetime.datetime.now().timestamp()
                if current_time - self.last_sr_calculation_time >= self.sr_cache_duration:
                    self.cached_support_resistance = result.get('support_resistance', {})
                    self.cached_breakout = result.get('breakout', {})
                    self.last_sr_calculation_time = current_time
                else:
                    result['support_resistance'] = self.cached_support_resistance
                    result['breakout'] = self.cached_breakout
                
                self.latest_strategy_data = result
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
                        return signal_data
            else:
                self.latest_signal = str(result)
                if result == "WAITING_DATA":
                    logger.debug(f"Strategy waiting for data (have {len(df)} candles)")
                else:
                    self.latest_strategy_data = {}

        return None

    def _initialize_data(self):
        """Fetch initial historical data and setup managers."""
        try:
            from_date = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime('%Y-%m-%d')
            to_date = datetime.datetime.now().strftime('%Y-%m-%d')
            
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
            
            logger.info(f"📊 Initializing StrategyRunner: timeframe={self.timeframe}, interval={interval}")
            
            df = self.data_fetcher.get_historical_data('NSE_INDEX|Nifty 50', interval, from_date, to_date)
            
            if df is not None and not df.empty:
                self.candle_manager.initialize(df)
                
                self.candle_manager.df['ema_5'] = self.candle_manager.df['close'].ewm(span=5, adjust=False).mean()
                self.candle_manager.df['ema_20'] = self.candle_manager.df['close'].ewm(span=20, adjust=False).mean()
                
                self.ema_5.initialize(self.candle_manager.df['close'])
                self.ema_20.initialize(self.candle_manager.df['close'])
                
                self.is_initialized = True
                logger.info(f"✅ StrategyRunner Initialized with {len(df)} candles")
            else:
                logger.warning("⚠️ Failed to fetch initial history for StrategyRunner")
                
        except Exception as e:
            logger.error(f"Error initializing StrategyRunner: {e}", exc_info=True)

    def start(self):
        self.is_running = True
        logger.info("🚀 StrategyRunner started. Performing initial analysis...")
        
        # Force initial run to populate state even if market is closed
        try:
            if not self.is_initialized:
                self._initialize_data()
            
            if self.is_initialized and not self.candle_manager.df.empty:
                last_close = self.candle_manager.df['close'].iloc[-1]
                logger.info(f"📊 Running initial strategy check on last close: {last_close}")
                
                # DEBUG: Log DataFrame details
                df = self.candle_manager.df
                logger.info(f"🐛 DEBUG: DataFrame Shape: {df.shape}")
                if not df.empty:
                    logger.info(f"🐛 DEBUG: Date Range: {df.index[0]} to {df.index[-1]}")
                    logger.info(f"🐛 DEBUG: Columns: {df.columns.tolist()}")
                    if 'ema_5' in df.columns:
                        logger.info(f"🐛 DEBUG: Last EMA 5: {df['ema_5'].iloc[-1]}")
                    if 'ema_20' in df.columns:
                        logger.info(f"🐛 DEBUG: Last EMA 20: {df['ema_20'].iloc[-1]}")
                
                self._run_strategy(last_close, {})
        except Exception as e:
            logger.error(f"Error in initial strategy run: {e}")

    def stop(self):
        self.is_running = False
