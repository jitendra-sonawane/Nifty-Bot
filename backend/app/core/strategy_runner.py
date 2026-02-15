import asyncio
import logging
import datetime
import pandas as pd
from typing import List, Callable, Dict, Optional, TYPE_CHECKING
from app.strategies.strategy import StrategyEngine
from app.strategies.reasoning import TradingReasoning
from app.data.data_fetcher import DataFetcher
from app.core.config import Config
from app.core.streaming import StreamingEMA, CandleManager

if TYPE_CHECKING:
    from app.intelligence import IntelligenceEngine

logger = logging.getLogger(__name__)

class StrategyRunner:
    def __init__(
        self,
        strategy_engine: StrategyEngine,
        data_fetcher: DataFetcher,
        intelligence_engine: Optional["IntelligenceEngine"] = None,
    ):
        self.strategy_engine = strategy_engine
        self.data_fetcher = data_fetcher
        self.reasoning_engine = TradingReasoning()
        self.intelligence_engine = intelligence_engine   # Optional: plug in at construction
        
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
        
        # Previous Day High/Low/Close
        self.pdh: Optional[float] = None
        self.pdl: Optional[float] = None
        self.pdc: Optional[float] = None

        # Callbacks
        self.on_signal: List[Callable] = []
        
        self.is_running = False
        self.lock = asyncio.Lock() # Fix race condition

    async def on_price_update(self, current_price: float, market_state: Dict):
        """Called whenever price updates."""
        if not self.is_running:
            return None
            
        try:
            # Synchronize execution to prevent race conditions on shared DataFrame
            async with self.lock:
                # Run in executor to avoid blocking
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._run_strategy, current_price, market_state)
        except Exception as e:
            logger.error(f"Error running strategy: {e}")
            return None

    def _run_strategy(self, current_price: float, market_state: Dict, dry_run: bool = False):
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
        stale_cols = [c for c in ['rsi', 'supertrend', 'atr'] if c in df.columns]
        if stale_cols:
            df.drop(columns=stale_cols, inplace=True)

        # 5. Run Strategy
        if df is not None and not df.empty:
            pcr = market_state.get('pcr')
            greeks = market_state.get('greeks')

            # Ensure Greeks are present for live execution
            if not dry_run and not greeks:
                logger.warning(f"⚠️ Greeks data missing in market_state. Skipping strategy run.")
                return None

            # Feed DataFrame to intelligence engine (MarketRegime needs it)
            intelligence_context = None
            if self.intelligence_engine and not dry_run:
                self.intelligence_engine.update({
                    "df":     df,
                    "greeks": greeks,
                    "iv":     (greeks.get("ce", {}).get("iv") if greeks else None),
                    "expiry": (greeks.get("expiry_date") if greeks else None),
                })
                intelligence_context = self.intelligence_engine.get_context()

            vix = market_state.get('vix')
            pcr_trend = market_state.get('pcr_trend')

            # Build PDH/PDL/PDC dict
            pdh_pdl_pdc = None
            if self.pdh is not None:
                pdh_pdl_pdc = {"pdh": self.pdh, "pdl": self.pdl, "pdc": self.pdc}

            result = self.strategy_engine.check_signal(
                df,
                pcr=pcr,
                greeks=greeks,
                intelligence_context=intelligence_context,
                vix=vix,
                pcr_trend=pcr_trend,
                current_time=datetime.datetime.now(),
                pdh_pdl_pdc=pdh_pdl_pdc,
            )
            
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
                    logger.info(f"🎯 Target Contract determined: {self.target_contract} for signal {signal}")
                else:
                    if not dry_run:
                        logger.warning(f"⚠️ Greeks missing or incomplete during signal generation, cannot determine target contract: {greeks}")
                
                # Check Cooldown and Emit
                if signal in ["BUY_CE", "BUY_PE"]:
                    current_time = datetime.datetime.now().timestamp()
                    last_time = self.last_signal_time.get(signal, 0)
                    diff = current_time - last_time
                    cooldown_ok = diff >= self.signal_cooldown_seconds
                    if not dry_run:
                        logger.info(f"🧐 Cooldown Check: Signal={signal}, Diff={diff:.2f}s, Cooldown={self.signal_cooldown_seconds}s")
                    
                    # If dry_run, we just return the result for validation, don't update cooldown
                    if dry_run:
                        return result

                    if cooldown_ok:
                        self.last_signal_time[signal] = current_time
                        logger.info(f"🚀 SIGNAL GENERATED: {signal} @ {current_price} | Contract: {self.target_contract}")
                        
                        # Extract specific indicators for signal_data
                        rsi = result.get('rsi')
                        supertrend = result.get('supertrend')

                        signal_data = {
                            "signal": signal,
                            "price": current_price,
                            "timestamp": datetime.datetime.now().isoformat(),
                            "reasoning": self.latest_reasoning,
                            "target_contract": self.target_contract,
                            "expiry": greeks.get('expiry_date') if greeks else None,
                            "strike": greeks.get('atm_strike') if greeks else None,
                            "greeks": greeks,
                            "market_data": market_state,
                            "indicators": {
                                "rsi": rsi,
                                "supertrend": supertrend,
                                "ema_5": cur_ema_5,
                                "ema_20": cur_ema_20,
                            }
                        }
                        return signal_data
                    else:
                        logger.info(f"⏳ Signal '{signal}' suppressed by cooldown. {self.signal_cooldown_seconds - diff:.2f}s remaining.")
            else:
                self.latest_signal = result.get('signal', 'HOLD')
                if result == "WAITING_DATA":
                    logger.debug(f"Strategy waiting for data (have {len(df)} candles)")
                else:
                    # Persist the full result dictionary so frontend can see progress/indicators
                    self.latest_strategy_data = result

        return None

    def _initialize_data(self):
        """Fetch initial historical data and setup managers."""
        try:
            from_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
            to_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            
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
            
            df_historical = self.data_fetcher.get_historical_data('NSE_INDEX|Nifty 50', interval, from_date, to_date)
            
            # Fetch Intraday (Today's) Data to fill the gap
            df_intraday = self.data_fetcher.get_intraday_data('NSE_INDEX|Nifty 50', interval)
            
            # Merge
            if df_historical is not None and not df_historical.empty:
                if df_intraday is not None and not df_intraday.empty:
                    logger.info(f"🔄 Merging Historical ({len(df_historical)}) + Intraday ({len(df_intraday)})")
                    # Combine, remove duplicates based on index (timestamp)
                    df = pd.concat([df_historical, df_intraday])
                    df = df[~df.index.duplicated(keep='last')] # Keep latest if duplicate
                    df = df.sort_index()
                else:
                    df = df_historical
            elif df_intraday is not None and not df_intraday.empty:
                df = df_intraday
                logger.warning("⚠️ Only Intraday data available")
            else:
                df = None
            
            if df is not None and not df.empty:
                # Extract Previous Day High/Low/Close (PDH/PDL/PDC)
                try:
                    today = datetime.datetime.now().date()
                    df_dates = df.index.date if hasattr(df.index, 'date') else pd.to_datetime(df.index).date
                    unique_dates = sorted(set(df_dates))
                    past_dates = [d for d in unique_dates if d < today]
                    if past_dates:
                        prev_day = past_dates[-1]
                        prev_day_mask = df_dates == prev_day
                        prev_day_df = df[prev_day_mask]
                        if not prev_day_df.empty:
                            self.pdh = float(prev_day_df['high'].max())
                            self.pdl = float(prev_day_df['low'].min())
                            self.pdc = float(prev_day_df['close'].iloc[-1])
                            logger.info(f"📊 PDH/PDL/PDC: High={self.pdh:.2f} Low={self.pdl:.2f} Close={self.pdc:.2f} (from {prev_day})")
                except Exception as e:
                    logger.warning(f"Could not extract PDH/PDL/PDC: {e}")

                self.candle_manager.initialize(df)

                # Check if last candle is incomplete (matches current time window)
                last_candle_incomplete = False
                try:
                    last_time = df.index[-1]
                    
                    # Robust comparison: Convert both to naive IST for comparison
                    # We assume last_time from Upstox is IST (or we strip tz to make it naive)
                    last_time_naive = last_time.replace(tzinfo=None) if last_time.tzinfo else last_time
                    
                    # Current time in IST
                    ist_offset = datetime.timedelta(hours=5, minutes=30)
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    now_ist = now_utc + ist_offset
                    
                    # Calculate start of current candle in IST
                    interval_mins = self.candle_manager.interval_minutes
                    minute_block = (now_ist.minute // interval_mins) * interval_mins
                    current_candle_start_ist = now_ist.replace(minute=minute_block, second=0, microsecond=0, tzinfo=None)
                    
                    logger.info(f"🔍 EMA Init Check: Last History Candle: {last_time_naive} | Current Time Block: {current_candle_start_ist}")
                    
                    # Check if they match (allow small tolerance just in case)
                    time_diff = abs((current_candle_start_ist - last_time_naive).total_seconds())
                    
                    if time_diff < 60: # Match if within 60 seconds
                        last_candle_incomplete = True
                        logger.info(f"🕯️ Last candle in history ({last_time}) is incomplete (current). Initializing EMAs accordingly.")
                    else:
                        logger.info(f"✅ Last candle in history ({last_time}) is considered COMPLETE. Standard initialization.")
                        if last_time_naive > current_candle_start_ist:
                             logger.warning(f"⚠️ Last candle ({last_time_naive}) is in the FUTURE compared to system time ({current_candle_start_ist})!")
                        elif (current_candle_start_ist - last_time_naive).total_seconds() > interval_mins * 60:
                             logger.warning(f"⚠️ Gap detected: Last candle ({last_time_naive}) is older than current block ({current_candle_start_ist}). Market might be closed or data missing.")
                except Exception as e:
                    logger.warning(f"Error checking incomplete candle: {e}")
                
                self.candle_manager.df['ema_5'] = self.candle_manager.df['close'].ewm(span=5, adjust=False).mean()
                self.candle_manager.df['ema_20'] = self.candle_manager.df['close'].ewm(span=20, adjust=False).mean()
                
                # Log the values before initialization
                if not self.candle_manager.df.empty:
                    last_ema_5 = self.candle_manager.df['ema_5'].iloc[-1]
                    prev_ema_5 = self.candle_manager.df['ema_5'].iloc[-2] if len(self.candle_manager.df) > 1 else 0
                    logger.info(f"📊 Pre-Init EMA_5: Last={last_ema_5:.2f}, Prev={prev_ema_5:.2f}")

                self.ema_5.initialize(self.candle_manager.df['close'], last_candle_incomplete)
                self.ema_20.initialize(self.candle_manager.df['close'], last_candle_incomplete)
                
                self.is_initialized = True
                logger.info(f"✅ StrategyRunner Initialized with {len(df)} candles")
            else:
                logger.warning("⚠️ Failed to fetch initial history for StrategyRunner")
                
        except Exception as e:
            logger.error(f"Error initializing StrategyRunner: {e}", exc_info=True)

    def start(self):
        logger.info("🚀 StrategyRunner started. Performing initial analysis...")
        self.is_running = True

        # Force initial run to populate state even if market is closed
        try:
            if not self.is_initialized:
                self._initialize_data()

            if self.is_initialized and not self.candle_manager.df.empty:
                last_close = self.candle_manager.df['close'].iloc[-1]
                logger.info(f"📊 Running initial strategy check on last close: {last_close}")

                # dry_run=True prevents triggering signals or cooldowns during cold start
                result = self._run_strategy(last_close, {}, dry_run=True)

                if result:
                    logger.info(f"✅ Initial strategy run completed with signal: {result.get('signal')}")
                elif self.latest_strategy_data:
                    logger.info(f"✅ Initial strategy data populated: Signal={self.latest_strategy_data.get('signal')}, RSI={self.latest_strategy_data.get('rsi')}, Filters={len(self.latest_strategy_data.get('filters', {}))}")
                else:
                    logger.warning("⚠️ Initial strategy run did not populate data")
        except Exception as e:
            logger.error(f"Error in initial strategy run: {e}", exc_info=True)

    def stop(self):
        self.is_running = False
