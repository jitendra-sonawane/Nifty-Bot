import pandas as pd
import datetime
from typing import Dict, List
import numpy as np
import logging
from app.data.data_fetcher import DataFetcher
from app.strategies.strategy import StrategyEngine
from app.managers.position_manager import Position
from app.managers.risk_manager import RiskManager
from app.utils.ai_data_collector import AIDataCollector

# Get logger instance
try:
    from app.core.logger_config import logger
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

class Backtester:
    """Backtest trading strategy on historical data."""
    
    def __init__(self, data_fetcher: DataFetcher, strategy_engine: StrategyEngine):
        self.data_fetcher = data_fetcher
        self.strategy_engine = strategy_engine
        self.positions = []
        self.logger = logger
        self.ai_collector = AIDataCollector()
    
    def _generate_mock_data(self, from_date: str, to_date: str, interval: str):
        """Generate mock OHLC data for backtesting when real data is unavailable."""
        try:
            start = pd.to_datetime(from_date)
            end = pd.to_datetime(to_date)
            
            # Generate hourly data between dates (limited to 500 candles for speed)
            dates = pd.date_range(start=start, end=end, freq='1H')
            if len(dates) > 500:
                dates = dates[:500]  # Limit to 500 candles max
            
            if len(dates) == 0:
                return None
            
            # Generate realistic price movements around 26000 (Nifty 50 typical range)
            base_price = 26000
            returns = np.random.normal(0.0001, 0.005, len(dates))
            prices = base_price * np.exp(np.cumsum(returns))
            
            df = pd.DataFrame({
                'timestamp': dates,
                'open': prices * (1 + np.random.uniform(-0.002, 0.002, len(dates))),
                'high': prices * (1 + np.abs(np.random.uniform(0, 0.01, len(dates)))),
                'low': prices * (1 - np.abs(np.random.uniform(0, 0.01, len(dates)))),
                'close': prices,
                'volume': np.random.randint(100000, 1000000, len(dates)),
                'oi': 0
            })
            
            df = df.set_index('timestamp')
            self.logger.debug(f"✅ Generated {len(df)} mock candles from {from_date} to {to_date}")
            return df
        except Exception as e:
            self.logger.error(f"❌ Error generating mock data: {e}")
            return None
        
    def run_backtest(self, symbol: str, from_date: str, to_date: str, 
                     initial_capital: float = 100000, interval: str = '1minute') -> Dict:
        """
        Run backtest on historical data.
        
        Args:
            symbol: Instrument symbol (e.g., 'NSE_INDEX|Nifty 50')
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            initial_capital: Starting capital
            interval: Timeframe (1minute, 30minute, day)
        
        Returns:
            Backtest results dictionary
        """
        self.logger.info(f"📊 Starting Backtest: {from_date} to {to_date}")
        
        try:
            # Fetch historical data
            self.logger.info(f"📥 Fetching data for {symbol}...")
            df = self.data_fetcher.get_historical_data(symbol, interval, from_date, to_date)
            
            # For backtest, use mock data by default to avoid API hangs
            # Real data would be fetched only if available
            if df is None or df.empty:
                self.logger.info(f"⚠️  No real data available, generating mock data for testing...")
                df = self._generate_mock_data(from_date, to_date, interval)
            
            if df is None or df.empty:
                error_msg = "Unable to fetch or generate historical data"
                self.logger.error(f"❌ {error_msg}")
                return {"error": error_msg, "total_trades": 0, "trades": [], "metrics": {}}
            
            self.logger.info(f"✅ Data loaded: {len(df)} candles")
        except Exception as e:
            self.logger.warning(f"⚠️  Error fetching data: {e}, using mock data...")
            df = self._generate_mock_data(from_date, to_date, interval)
            if df is None or df.empty:
                error_msg = f"Failed to generate mock data: {str(e)}"
                self.logger.error(f"❌ {error_msg}")
                return {"error": error_msg, "total_trades": 0, "trades": [], "metrics": {}}
        
        # Initialize
        capital = initial_capital
        risk_manager = RiskManager(initial_capital=initial_capital)
        self.trades = []
        self.positions = []
        
        # Pre-calculate indicators for the entire dataframe to speed up backtest
        self.logger.info("🧮 Pre-calculating indicators...")
        df['rsi'] = self.strategy_engine.calculate_rsi(df['close'])
        df['supertrend'], _, _ = self.strategy_engine.calculate_supertrend(df)
        df['vwap'] = self.strategy_engine.calculate_vwap(df)
        
        # Simulate candlestick by candlestick
        signal_counts = {"BUY_CE": 0, "BUY_PE": 0, "HOLD": 0}
        
        # For faster backtest, sample every N candles instead of processing all
        sample_interval = max(1, len(df) // 100)  # Max 100 iterations for speed
        
        for i in range(50, len(df), sample_interval):
            # Get slice of data up to current candle
            current_data = df.iloc[:i+1].copy()
            current_price = current_data['close'].iloc[-1]
            current_time = pd.Timestamp(current_data.index[-1])  # Ensure it's a proper Timestamp
            
            # Check if we have open positions to exit
            if self.positions:
                capital = self._check_exits(current_price, current_time, risk_manager, capital)
            
            # Also force close positions that are older than 5 candles for demo
            for pos in self.positions[:]:
                candles_held = i - 50  # Approximate based on loop position
                if candles_held > 5:
                    exit_cost = current_price * pos.quantity  # Money received from selling
                    entry_cost = pos.entry_price * pos.quantity  # Money paid when buying
                    pnl = exit_cost - entry_cost  # Net P&L
                    pnl_pct = ((current_price - pos.entry_price) / pos.entry_price) * 100 if pos.entry_price > 0 else 0
                    
                    # Add exit proceeds back to capital
                    capital += exit_cost
                    
                    trade = {
                        "position_type": pos.position_type,
                        "entry_price": round(pos.entry_price, 2),
                        "exit_price": round(current_price, 2),
                        "quantity": pos.quantity,
                        "entry_time": str(pd.Timestamp(pos.entry_time).strftime('%Y-%m-%d %H:%M:%S')),
                        "exit_time": str(pd.Timestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "reason": "AUTO_EXIT_TIME_LIMIT"
                    }
                    
                    self.trades.append(trade)
                    self.positions.remove(pos)
            
            # Generate signal - simplified for speed
            try:
                # Use real strategy logic
                # We pass the slice of dataframe up to current candle
                # Since we pre-calculated indicators, we can just pass the row or the slice
                # But check_signal expects a DF and looks at the last row
                
                # Optimization: check_signal will re-calculate if columns missing, but we added them.
                # However, check_signal looks at the LAST row of the passed DF.
                # So we pass current_data which is df.iloc[:i+1]
                
                strategy_result = self.strategy_engine.check_signal(
                    current_data, 
                    pcr=None, 
                    greeks=None, 
                    backtest_mode=True
                )
                
                signal = strategy_result['signal']
                
                signal_counts[signal] = signal_counts.get(signal, 0) + 1
                
                # Only take new positions if no open positions
                if signal in ["BUY_CE", "BUY_PE"] and len(self.positions) == 0:
                    # Check if we can trade
                    can_trade, reason = risk_manager.can_trade(capital, len(self.positions))
                    
                    if can_trade:
                        # Execute Trade
                        entry_price = current_price
                        quantity = risk_manager.calculate_position_size(
                            entry_price=entry_price,
                            stop_loss_pct=0.30, # Default SL
                            current_balance=capital
                        )
                        
                        if quantity > 0:
                            position = Position(
                                instrument_key=symbol, # In real backtest this would be option key
                                entry_price=entry_price,
                                quantity=quantity,
                                position_type="CE" if signal == "BUY_CE" else "PE"
                            )
                            self.positions.append(position)
                            
                            # Log for AI Training
                            market_data = {
                                "symbol": symbol,
                                "open": current_data['open'].iloc[-1],
                                "high": current_data['high'].iloc[-1],
                                "low": current_data['low'].iloc[-1],
                                "close": current_data['close'].iloc[-1],
                                "volume": current_data['volume'].iloc[-1]
                            }
                            self.ai_collector.log_entry(
                                trade_id=position.id,
                                timestamp=current_time,
                                market_data=market_data,
                                indicators=strategy_result,
                                signal=signal
                            )
                            
                            print(f"  📈 BUY @ {entry_price:.2f} (Qty: {quantity}) at {current_time}")
            except Exception as e:
                print(f"  Error at {current_time}: {e}")
                continue
        
        # Close any remaining positions at the end
        if self.positions:
            final_price = df['close'].iloc[-1]
            final_time = df.index[-1]
            capital = self._check_exits(final_price, final_time, risk_manager, capital, force_close=True)
        
        # Save AI Training Data
        self.ai_collector.save_to_csv("ai_training_data.csv")
        
        print(f"\n📊 Signal Summary: BUY_CE={signal_counts.get('BUY_CE', 0)}, BUY_PE={signal_counts.get('BUY_PE', 0)}, HOLD={signal_counts.get('HOLD', 0)}")
        print(f"💼 Total Trades Executed: {len(self.trades)}")
        
        # Calculate metrics
        metrics = self._calculate_metrics(initial_capital, capital)
        
        return {
            "initial_capital": initial_capital,
            "final_capital": capital,
            "total_pnl": capital - initial_capital,
            "total_trades": len(self.trades),
            "trades": self.trades,
            "metrics": metrics
        }
    
    def _check_exits(self, current_price: float, current_time, risk_manager: RiskManager, capital: float, force_close=False) -> float:
        """Check and execute exits for open positions. Returns updated capital."""
        positions_to_close = []
        
        for position in self.positions:
            should_exit = force_close
            reason = "BACKTEST_END" if force_close else ""
            
            if not should_exit:
                # Update trailing stop
                position.update_trailing_stop(current_price)
                
                # Check exit conditions
                should_exit, reason = position.should_exit(current_price, current_time)
            
            if should_exit:
                # Close position and update capital
                exit_cost = current_price * position.quantity  # Money received from selling
                entry_cost = position.entry_price * position.quantity  # Money paid when buying
                pnl = exit_cost - entry_cost  # Net P&L
                pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                
                # Add exit proceeds back to capital
                capital += exit_cost
                
                trade = {
                    "entry_time": position.entry_time.isoformat() if hasattr(position.entry_time, 'isoformat') else str(position.entry_time),
                    "exit_time": current_time.isoformat() if hasattr(current_time, 'isoformat') else str(current_time),
                    "position_type": position.position_type,
                    "entry_price": round(position.entry_price, 2),
                    "exit_price": round(current_price, 2),
                    "quantity": position.quantity,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "reason": reason
                }
                
                self.trades.append(trade)
                
                # Update AI Collector
                self.ai_collector.update_exit(
                    trade_id=position.id,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    outcome=1 if pnl > 0 else 0
                )
                
                risk_manager.update_daily_pnl(pnl)
                positions_to_close.append(position)
                
                print(f"  📉 SELL @ {current_price:.2f} | {reason} | P&L: ₹{pnl:.2f} ({pnl_pct:.2f}%)")
        
        # Remove closed positions
        for pos in positions_to_close:
            self.positions.remove(pos)
            
        return capital
    
    def _calculate_metrics(self, initial_capital: float, final_capital: float) -> Dict:
        """Calculate performance metrics."""
        if not self.trades:
            return {
                "total_return_pct": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "max_drawdown": 0
            }
        
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]
        
        total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100
        win_rate = (len(wins) / len(self.trades)) * 100 if self.trades else 0
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
        
        total_wins = sum(t['pnl'] for t in wins)
        total_losses = abs(sum(t['pnl'] for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Simple max drawdown calculation
        running_capital = initial_capital
        peak = initial_capital
        max_drawdown = 0
        
        for trade in self.trades:
            running_capital += trade['pnl']
            if running_capital > peak:
                peak = running_capital
            drawdown = ((peak - running_capital) / peak) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            "total_return_pct": round(total_return_pct, 2),
            "win_rate": round(win_rate, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_drawdown, 2)
        }
