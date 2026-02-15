"""
Enhanced Backtesting Engine for Nifty 50 Option Strategies.

Supports multi-strategy backtesting with:
- Black-Scholes option premium simulation
- Virtual wallet with configurable capital
- Trade-by-trade analytics with reasoning
- Equity curve generation
- Performance metrics (Sharpe, Sortino, max drawdown, etc.)

Usage:
    backtester = StrategyBacktester(data_fetcher)
    result = backtester.run(
        strategy=IronCondorStrategy(),
        from_date="2025-01-01",
        to_date="2025-01-31",
        initial_capital=1000000,
    )
    print(result.metrics.to_dict())
"""

import datetime
import logging
import uuid
import math
from typing import List, Dict, Optional

import pandas as pd
import numpy as np

from app.core.config import Config
from app.core.models import (
    BacktestResult,
    PerformanceMetrics,
    TradeRecord,
    StrategySignal,
    MultiLegPosition,
    PositionLeg,
    SignalAction,
    TransactionType,
)
from app.core.option_chain import OptionChainManager
from app.core.options_pricer import (
    black_scholes_price,
    calculate_atm_strike,
    estimate_premium_change,
)
from app.data.data_fetcher import DataFetcher
from app.strategies.strategy import StrategyEngine
from app.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyBacktester:
    """
    Multi-strategy backtester with option premium simulation.
    
    Workflow:
    1. Fetch historical Nifty 50 OHLCV data
    2. Walk forward through each candle
    3. Update synthetic option chain at each step
    4. Ask the strategy for signals (ENTER/EXIT/HOLD)
    5. Simulate option P&L using Black-Scholes
    6. Track equity curve and compute performance metrics
    """
    
    def __init__(self, data_fetcher: DataFetcher = None):
        if data_fetcher:
            self.data_fetcher = data_fetcher
        else:
            try:
                self.data_fetcher = DataFetcher(Config.API_KEY, Config.ACCESS_TOKEN)
            except Exception:
                self.data_fetcher = None  # Will use mock data
        self.indicator_engine = StrategyEngine()
        self.chain_manager = OptionChainManager()

    
    def run(
        self,
        strategy: BaseStrategy,
        from_date: str,
        to_date: str,
        initial_capital: float = 1000000,
        interval: str = "5minute",
        default_iv: float = 0.13,
        default_expiry_days: float = 3.0,
    ) -> BacktestResult:
        """
        Run a full backtest for a given strategy.
        
        Args:
            strategy: Strategy instance to backtest
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            initial_capital: Starting paper capital in ₹
            interval: Candle interval
            default_iv: Default implied volatility for BS pricing
            default_expiry_days: Default days-to-expiry assumption
        
        Returns:
            BacktestResult with trades, equity curve, and metrics
        """
        logger.info(
            f"🔄 Backtesting {strategy.display_name} | "
            f"{from_date} → {to_date} | Capital: ₹{initial_capital:,.0f}"
        )
        
        # ── Fetch historical data ─────────────────────────────────────
        df = self._fetch_data(from_date, to_date, interval)
        if df is None or df.empty:
            logger.error("No historical data available for backtest")
            return BacktestResult(
                strategy_name=strategy.name,
                from_date=from_date,
                to_date=to_date,
                initial_capital=initial_capital,
                final_capital=initial_capital,
            )
        
        # ── Initialize tracking ───────────────────────────────────────
        capital = initial_capital
        equity_curve = [initial_capital]
        equity_timestamps = [from_date]
        trade_records: List[TradeRecord] = []
        open_position: Optional[MultiLegPosition] = None
        
        # Track simulated expiry cycling
        days_since_expiry_reset = 0.0
        current_expiry_days = default_expiry_days
        
        logger.info(f"📊 Processing {len(df)} candles...")
        
        # ── Walk forward through candles ──────────────────────────────
        for i in range(30, len(df)):  # Start after enough data for indicators
            row = df.iloc[i]
            spot_price = float(row["close"])
            current_time = row.name if isinstance(row.name, datetime.datetime) else datetime.datetime.now()
            
            # Calculate time elapsed (for theta decay)
            if i > 30:
                prev_time = df.index[i - 1] if isinstance(df.index[i - 1], datetime.datetime) else current_time
                minutes_elapsed = max(1, (current_time - prev_time).total_seconds() / 60)
            else:
                minutes_elapsed = 5  # Default 5-min candle
            
            # Simulate expiry cycling: reset every ~5 trading days
            days_since_expiry_reset += minutes_elapsed / (60 * 6.25)
            if days_since_expiry_reset >= 5:
                current_expiry_days = default_expiry_days
                days_since_expiry_reset = 0
            else:
                current_expiry_days = max(0.1, current_expiry_days - minutes_elapsed / (60 * 6.25))
            
            # ── Update option chain (synthetic) ───────────────────────
            self.chain_manager.update(spot_price, force=True)
            
            # ── Calculate indicators ──────────────────────────────────
            lookback = df.iloc[max(0, i - 100):i + 1].copy()
            indicators = self._calculate_indicators(lookback)
            
            # ── Check for exit if position is open ────────────────────
            if open_position and open_position.is_open:
                # Update position P&L
                self._update_position_pnl(
                    open_position, spot_price, current_expiry_days, default_iv, minutes_elapsed
                )
                
                # Check exit conditions
                exit_conditions = strategy.get_exit_conditions(open_position)
                current_pnl = open_position.total_unrealized_pnl
                should_exit, exit_reason = exit_conditions.should_exit(current_pnl, current_time)
                
                if should_exit:
                    # Close position
                    trade = self._close_position(open_position, current_time, exit_reason)
                    trade_records.append(trade)
                    capital += trade.pnl
                    open_position = None
                    logger.debug(f"  EXIT: {exit_reason} | P&L: ₹{trade.pnl:.0f}")
            
            # ── Check for entry if no position ────────────────────────
            if open_position is None:
                signal = strategy.generate_signal(
                    spot_price=spot_price,
                    chain=self.chain_manager,
                    indicators=indicators,
                    current_time=current_time,
                )
                
                if signal.action == SignalAction.ENTER and signal.legs:
                    # Check if we have enough capital
                    max_risk = strategy.calculate_max_risk(signal.legs)
                    if max_risk <= capital * 0.5:  # Don't risk more than 50% on one trade
                        open_position = self._open_position(signal, current_time)
                        logger.debug(
                            f"  ENTER: {signal.strategy_name} | "
                            f"Risk: ₹{max_risk:.0f} | Premium: ₹{signal.net_premium:.0f}"
                        )
            
            # Track equity
            unrealized = open_position.total_unrealized_pnl if open_position else 0
            equity_curve.append(capital + unrealized)
            equity_timestamps.append(current_time.isoformat() if isinstance(current_time, datetime.datetime) else str(current_time))
        
        # ── Force close any open position at end ──────────────────────
        if open_position and open_position.is_open:
            trade = self._close_position(
                open_position,
                df.index[-1] if isinstance(df.index[-1], datetime.datetime) else datetime.datetime.now(),
                "Backtest period ended",
            )
            trade_records.append(trade)
            capital += trade.pnl
        
        # ── Calculate metrics ─────────────────────────────────────────
        metrics = self._calculate_metrics(
            initial_capital, capital, trade_records, equity_curve
        )
        
        logger.info(
            f"✅ Backtest complete: {strategy.display_name} | "
            f"Trades: {metrics.total_trades} | "
            f"Win Rate: {metrics.win_rate:.0f}% | "
            f"P&L: ₹{metrics.total_pnl:,.0f} ({metrics.total_return_pct:.1f}%) | "
            f"Sharpe: {metrics.sharpe_ratio:.2f}"
        )
        
        return BacktestResult(
            strategy_name=strategy.name,
            from_date=from_date,
            to_date=to_date,
            initial_capital=initial_capital,
            final_capital=round(capital, 2),
            trades=trade_records,
            equity_curve=equity_curve,
            equity_timestamps=equity_timestamps,
            metrics=metrics,
        )
    
    # ─── Private Helpers ────────────────────────────────────────────────────
    
    def _fetch_data(self, from_date: str, to_date: str, interval: str) -> Optional[pd.DataFrame]:
        """Fetch historical data, with fallback to mock data."""
        if self.data_fetcher:
            try:
                df = self.data_fetcher.get_historical_data(
                    Config.SYMBOL_NIFTY_50, interval, from_date, to_date
                )
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"API data fetch failed: {e}")
        
        logger.info("Using generated mock data for backtest")
        return self._generate_mock_data(from_date, to_date, interval)

    
    def _generate_mock_data(self, from_date: str, to_date: str, interval: str) -> pd.DataFrame:
        """Generate realistic Nifty 50 mock OHLCV data."""
        freq = "5min" if "5" in interval else "1min"
        
        start = pd.Timestamp(from_date)
        end = pd.Timestamp(to_date)
        
        # Generate timestamps for market hours only (9:15 - 15:30)
        all_dates = pd.bdate_range(start, end)
        timestamps = []
        for date in all_dates:
            market_open = date.replace(hour=9, minute=15)
            market_close = date.replace(hour=15, minute=30)
            day_ts = pd.date_range(market_open, market_close, freq=freq)
            timestamps.extend(day_ts)
        
        if not timestamps:
            return pd.DataFrame()
        
        n = len(timestamps)
        
        # Simulate realistic price movement
        base_price = 23500.0
        returns = np.random.normal(0, 0.001, n)  # ~0.1% per candle
        
        # Add some trend and mean reversion
        trend = np.cumsum(returns) * base_price
        prices = base_price + trend
        
        # Add some noise for OHLC
        highs = prices + np.abs(np.random.normal(0, 15, n))
        lows = prices - np.abs(np.random.normal(0, 15, n))
        opens = prices + np.random.normal(0, 5, n)
        volumes = np.random.randint(5000, 50000, n)
        
        df = pd.DataFrame({
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
            "oi": 0,
        }, index=pd.DatetimeIndex(timestamps))
        
        return df
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators using existing StrategyEngine."""
        indicators = {}
        
        try:
            if len(df) < 20:
                return {"rsi": 50, "signal": "HOLD", "confidence": 0}
            
            # RSI
            rsi_series = self.indicator_engine.calculate_rsi(df["close"], Config.RSI_PERIOD)
            indicators["rsi"] = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50
            
            # EMAs
            ema_short = self.indicator_engine.calculate_ema(df["close"], Config.EMA_SHORT_PERIOD)
            ema_long = self.indicator_engine.calculate_ema(df["close"], Config.EMA_LONG_PERIOD)
            indicators["ema_short"] = float(ema_short.iloc[-1]) if not ema_short.empty else 0
            indicators["ema_long"] = float(ema_long.iloc[-1]) if not ema_long.empty else 0
            
            # VWAP
            if "volume" in df.columns:
                try:
                    vwap = self.indicator_engine.calculate_vwap(df)
                    indicators["vwap"] = float(vwap.iloc[-1]) if vwap is not None and not vwap.empty else 0
                except Exception:
                    indicators["vwap"] = 0
            
            # Supertrend
            try:
                st_result = self.indicator_engine.calculate_supertrend(df)
                if st_result is not None and "direction" in st_result.columns:
                    indicators["supertrend_direction"] = "UP" if st_result["direction"].iloc[-1] == 1 else "DOWN"
                else:
                    indicators["supertrend_direction"] = None
            except Exception:
                indicators["supertrend_direction"] = None
            
            # ATR
            try:
                atr = self.indicator_engine.calculate_atr(df)
                indicators["atr"] = float(atr.iloc[-1]) if atr is not None and not atr.empty else 0
            except Exception:
                indicators["atr"] = 30  # Default ~30 pts
            
            # Breakout detection
            try:
                breakout = self.indicator_engine.detect_breakout(df)
                indicators["breakout"] = breakout if breakout else {"is_breakout": False}
            except Exception:
                indicators["breakout"] = {"is_breakout": False}
            
            # Volume
            if "volume" in df.columns:
                indicators["current_volume"] = int(df["volume"].iloc[-1])
                try:
                    avg_vol = self.indicator_engine.calculate_avg_volume(df)
                    indicators["avg_volume"] = float(avg_vol) if avg_vol else 10000
                except Exception:
                    indicators["avg_volume"] = int(df["volume"].mean())
            
            # Get full signal from engine (for directional strategies)
            try:
                signal_result = self.indicator_engine.check_signal(df, backtest_mode=True)
                if signal_result:
                    indicators["signal"] = signal_result.get("signal", "HOLD")
                    indicators["confidence"] = signal_result.get("confidence", 0)
                else:
                    indicators["signal"] = "HOLD"
                    indicators["confidence"] = 0
            except Exception:
                indicators["signal"] = "HOLD"
                indicators["confidence"] = 0
            
        except Exception as e:
            logger.debug(f"Indicator calculation error: {e}")
            indicators = {"rsi": 50, "signal": "HOLD", "confidence": 0}
        
        return indicators
    
    def _open_position(self, signal: StrategySignal, entry_time: datetime.datetime) -> MultiLegPosition:
        """Convert a strategy signal into an open position."""
        position_id = str(uuid.uuid4())[:8]
        
        position_legs = []
        for i, leg in enumerate(signal.legs):
            position_legs.append(PositionLeg(
                leg_id=f"{position_id}_L{i}",
                instrument_key=leg.instrument_key,
                strike=leg.strike,
                option_type=leg.option_type,
                transaction_type=leg.transaction_type,
                quantity=leg.quantity,
                entry_price=leg.price,
                current_price=leg.price,
            ))
        
        return MultiLegPosition(
            position_id=position_id,
            strategy_name=signal.strategy_name,
            legs=position_legs,
            entry_time=entry_time,
            is_open=True,
            max_risk=signal.max_risk,
            max_reward=signal.max_reward,
        )
    
    def _update_position_pnl(
        self,
        position: MultiLegPosition,
        spot_price: float,
        expiry_days: float,
        iv: float,
        minutes_elapsed: float,
    ):
        """Update current prices for all legs using Black-Scholes."""
        for leg in position.legs:
            new_price = estimate_premium_change(
                spot_old=leg.entry_price,  # Correct reference: option's entry price
                spot_new=spot_price,
                strike=leg.strike,
                expiry_days=expiry_days,
                sigma=iv,
                option_type=leg.option_type.value,
                time_elapsed_minutes=minutes_elapsed,
            )
            leg.current_price = max(0.05, new_price)  # Min price 0.05
    
    def _close_position(
        self,
        position: MultiLegPosition,
        exit_time: datetime.datetime,
        exit_reason: str,
    ) -> TradeRecord:
        """Close position and create trade record."""
        position.is_open = False
        position.exit_time = exit_time
        position.exit_reason = exit_reason
        
        pnl = position.total_unrealized_pnl
        entry_premium = abs(position.net_entry_premium)

        # Calculate exit premium
        exit_premium = 0
        for leg in position.legs:
            sign = -1 if leg.transaction_type == TransactionType.BUY else 1
            exit_premium += sign * leg.current_price * leg.quantity

        # Realistic transaction costs (applied at close; same costs incurred at entry)
        # Slippage: 1 point per leg (bid-ask spread impact, each side)
        # Exchange charges: ~0.05% of gross premium turnover (NSE + SEBI charges)
        num_legs = len(position.legs)
        leg_qty = position.legs[0].quantity if position.legs else 1
        slippage = num_legs * 1.0 * leg_qty * 2  # 1 pt per leg × qty, entry + exit
        gross_turnover = entry_premium + abs(exit_premium)
        exchange_charges = gross_turnover * 0.0005
        transaction_costs = slippage + exchange_charges
        pnl -= transaction_costs

        pnl_pct = (pnl / max(entry_premium, 1)) * 100 if entry_premium > 0 else 0
        
        # Duration in minutes
        duration = 0
        if isinstance(position.entry_time, datetime.datetime) and isinstance(exit_time, datetime.datetime):
            duration = (exit_time - position.entry_time).total_seconds() / 60
        
        return TradeRecord(
            trade_id=position.position_id,
            strategy_name=position.strategy_name,
            entry_time=position.entry_time,
            exit_time=exit_time,
            legs=[leg.to_dict() for leg in position.legs],
            entry_premium=entry_premium,
            exit_premium=abs(exit_premium),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            exit_reason=exit_reason,
            market_conditions={"duration_minutes": duration},
        )
    
    def _calculate_metrics(
        self,
        initial_capital: float,
        final_capital: float,
        trades: List[TradeRecord],
        equity_curve: List[float],
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        metrics = PerformanceMetrics()
        
        if not trades:
            metrics.total_pnl = final_capital - initial_capital
            metrics.total_return_pct = (metrics.total_pnl / initial_capital) * 100
            return metrics
        
        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        
        metrics.total_trades = len(trades)
        metrics.winning_trades = len(wins)
        metrics.losing_trades = len(losses)
        metrics.win_rate = (len(wins) / len(trades)) * 100 if trades else 0
        metrics.total_pnl = sum(pnls)
        metrics.total_return_pct = (metrics.total_pnl / initial_capital) * 100
        metrics.avg_win = sum(wins) / len(wins) if wins else 0
        metrics.avg_loss = sum(losses) / len(losses) if losses else 0
        metrics.best_trade = max(pnls) if pnls else 0
        metrics.worst_trade = min(pnls) if pnls else 0
        
        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        metrics.profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")
        
        # Expectancy = (Win% × Avg Win) - (Loss% × |Avg Loss|)
        win_pct = len(wins) / len(trades) if trades else 0
        loss_pct = len(losses) / len(trades) if trades else 0
        metrics.expectancy = (win_pct * metrics.avg_win) - (loss_pct * abs(metrics.avg_loss))
        
        # Average trade duration
        durations = [t.market_conditions.get("duration_minutes", 0) for t in trades]
        metrics.avg_trade_duration = sum(durations) / len(durations) if durations else 0
        
        # Max drawdown
        if len(equity_curve) > 1:
            peak = equity_curve[0]
            max_dd = 0
            for value in equity_curve:
                if value > peak:
                    peak = value
                dd = peak - value
                if dd > max_dd:
                    max_dd = dd
            metrics.max_drawdown = max_dd
            metrics.max_drawdown_pct = (max_dd / peak) * 100 if peak > 0 else 0
        
        # Sharpe Ratio (annualized, assuming daily returns)
        if len(pnls) > 1:
            returns = np.array(pnls) / initial_capital
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                # Annualize: assume ~252 trading days
                metrics.sharpe_ratio = (mean_return / std_return) * math.sqrt(252)
        
        # Sortino Ratio (only downside deviation)
        if len(pnls) > 1:
            returns = np.array(pnls) / initial_capital
            mean_return = np.mean(returns)
            downside = returns[returns < 0]
            if len(downside) > 0:
                downside_std = np.std(downside)
                if downside_std > 0:
                    metrics.sortino_ratio = (mean_return / downside_std) * math.sqrt(252)
        
        return metrics


# ─── Backward Compatibility ────────────────────────────────────────────────

class Backtester(StrategyBacktester):
    """
    Legacy compatibility wrapper.
    Keeps the old run_backtest() interface working with the new engine.
    """
    
    def __init__(self, data_fetcher=None, strategy_engine=None):
        super().__init__(data_fetcher)
        if strategy_engine:
            self.indicator_engine = strategy_engine
    
    def run_backtest(
        self,
        symbol: str = "NSE_INDEX|Nifty 50",
        from_date: str = "2025-01-01",
        to_date: str = "2025-01-31",
        initial_capital: float = 100000,
        interval: str = "5minute",
    ) -> dict:
        """Legacy interface — runs Iron Condor by default."""
        from app.strategies.iron_condor import IronCondorStrategy
        
        strategy = IronCondorStrategy()
        result = self.run(strategy, from_date, to_date, initial_capital, interval)
        
        # Convert to legacy dict format
        return {
            "total_trades": result.metrics.total_trades,
            "winning_trades": result.metrics.winning_trades,
            "losing_trades": result.metrics.losing_trades,
            "trades": [t.to_dict() for t in result.trades],
            "metrics": result.metrics.to_dict(),
            "equity_curve": result.equity_curve,
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
        }
