import asyncio
import logging
import datetime
from typing import Optional
from app.core.config import Config
from app.core.authentication import Authenticator
from app.data.data_fetcher import DataFetcher
from app.strategies.strategy import StrategyEngine
from app.managers.order_manager import OrderManager
from app.managers.position_manager import PositionManager
from app.managers.risk_manager import RiskManager
from app.core.market_data import MarketDataManager
from app.core.strategy_runner import StrategyRunner
from app.core.trade_executor import TradeExecutor

# ── Intelligence Engine ────────────────────────────────────────────────────
from app.intelligence import IntelligenceEngine
from app.intelligence.market_regime import MarketRegimeModule
from app.intelligence.iv_rank import IVRankModule
from app.intelligence.order_book import OrderBookModule
from app.intelligence.market_breadth import MarketBreadthModule
from app.intelligence.portfolio_greeks import PortfolioGreeksModule
from app.intelligence.oi_analysis import OIAnalysisModule

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        self.is_running = False
        self.status_callback = None
        self.latest_log = []

        # Components
        self.market_data: Optional[MarketDataManager] = None
        self.strategy_runner: Optional[StrategyRunner] = None
        self.trade_executor: Optional[TradeExecutor] = None

        # Intelligence Engine
        self.intelligence_engine: Optional[IntelligenceEngine] = None

        # Legacy accessors for API
        self.order_manager = None
        self.position_manager = None
        self.risk_manager = None
        self.data_fetcher = None

        self.nifty_key = Config.SYMBOL_NIFTY_50
        self.timeframe = Config.TIMEFRAME
        self.access_token = Config.ACCESS_TOKEN

    def log(self, message):
        logger.info(message)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.latest_log.append(f"[{timestamp}] {message}")
        if len(self.latest_log) > 50:
            self.latest_log.pop(0)

    def initialize(self):
        self.log("Initializing Upstox Trading Bot (Async Architecture)...")

        # Auth
        if not self.access_token:
            self.log("Access Token not found in .env")

        # ── Base Components ────────────────────────────────────────────────
        self.data_fetcher = DataFetcher(Config.API_KEY, self.access_token)
        strategy_engine = StrategyEngine()
        self.order_manager = OrderManager(self.access_token)
        self.position_manager = PositionManager()

        initial_capital = self.order_manager.paper_manager.get_balance()
        self.risk_manager = RiskManager(initial_capital=initial_capital)

        # ── Intelligence Engine ────────────────────────────────────────────
        # Register all modules here. To add a new module, just register it.
        # To disable one, call self.intelligence_engine.disable("<name>").
        self.intelligence_engine = IntelligenceEngine()
        self.intelligence_engine.register(MarketRegimeModule())
        self.intelligence_engine.register(IVRankModule())
        self.intelligence_engine.register(OrderBookModule())
        self.intelligence_engine.register(MarketBreadthModule())
        self.intelligence_engine.register(PortfolioGreeksModule())
        self.intelligence_engine.register(OIAnalysisModule())
        self.log("Intelligence engine initialized with 6 modules.")

        # ── Core Modules (pass intelligence_engine for data feeding) ───────
        self.market_data = MarketDataManager(
            self.data_fetcher,
            self.access_token,
            intelligence_engine=self.intelligence_engine,
        )
        self.strategy_runner = StrategyRunner(
            strategy_engine,
            self.data_fetcher,
            intelligence_engine=self.intelligence_engine,
        )
        self.trade_executor = TradeExecutor(self.order_manager, self.position_manager, self.risk_manager)

        # Wire up events
        self.market_data.on_price_update.append(self._on_price_update)

        self.log("Loading instruments...")
        try:
            self.data_fetcher.load_instruments()
            self.log("Instruments loaded.")
        except Exception as e:
            self.log(f"Error loading instruments: {e}")

    async def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.log("Starting Bot...")

        # Reset daily state for intelligence modules
        if self.intelligence_engine:
            self.intelligence_engine.reset_daily()
            self.log("Intelligence modules reset for new session.")

        # Start Components
        if self.market_data:
            await self.market_data.start()
        if self.strategy_runner:
            self.strategy_runner.start()

        # Start periodic strategy update task (runs even when market is closed)
        asyncio.create_task(self._periodic_strategy_update())

        self.log("Bot Started.")

    async def stop(self):
        if not self.is_running:
            return
            
        self.is_running = False
        self.log("Stopping Bot...")
        
        if self.market_data:
            await self.market_data.stop()
        if self.strategy_runner:
            self.strategy_runner.stop()
            
        self.log("Bot Stopped.")

    async def _on_price_update(self, price: float):
        """Orchestrator for price updates."""
        if not self.is_running:
            return
            
        try:
            # 1. Get Market State
            market_state = self.market_data.get_market_state() if self.market_data else {}
            
            # 2. Run Strategy
            signal_data = None
            if self.strategy_runner:
                signal_data = await self.strategy_runner.on_price_update(price, market_state)
            
            # 3. Execute Trade if Signal
            if signal_data and self.trade_executor:
                await self.trade_executor.execute_trade(signal_data)
                
            # 3b. Push positions to PortfolioGreeks intelligence module
            if self.intelligence_engine and self.position_manager:
                positions = self.position_manager.get_positions()
                self.intelligence_engine.update({
                    "positions": positions,
                    "greeks":    market_state.get("greeks"),
                })

            # 4. Check Exits and Ensure Subscription
            if self.position_manager and self.position_manager.get_position_count() > 0:
                positions = self.position_manager.get_positions()
                if positions:
                    # Collect all keys
                    keys = [p['instrument_key'] for p in positions]
                    
                    # Ensure subscription for real-time PnL
                    if self.market_data:
                        self.market_data.subscribe_instruments(keys)
                        
                        # Get cached prices for exit check
                        current_prices = {}
                        for key in keys:
                            price = self.market_data.get_price(key)
                            if price > 0:
                                current_prices[key] = price
                                
                        # Use cached prices for exits
                        if self.trade_executor and current_prices:
                            await self.trade_executor.check_exits(current_prices)

            # 5. Broadcast Status
            if self.status_callback:
                if asyncio.iscoroutinefunction(self.status_callback):
                    await self.status_callback(self.get_status())
                else:
                    self.status_callback(self.get_status())
        except Exception as e:
            self.log(f"Error in price update handler: {e}")
    
    async def _periodic_strategy_update(self):
        """Periodically update strategy data even when market is closed."""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                
                if not self.is_running:
                    break
                
                # Get current price (use last known price if market is closed)
                current_price = self.market_data.current_price if self.market_data else 0
                
                if current_price > 0 and self.strategy_runner:
                    market_state = self.market_data.get_market_state() if self.market_data else {}
                    
                    # Run strategy to update indicators and filters
                    await self.strategy_runner.on_price_update(current_price, market_state)
                    
                    logger.debug(f"📊 Periodic strategy update completed. Price: {current_price}")
                    
                    # Broadcast updated status
                    if self.status_callback:
                        if asyncio.iscoroutinefunction(self.status_callback):
                            await self.status_callback(self.get_status())
                        else:
                            self.status_callback(self.get_status())
            except Exception as e:
                logger.error(f"Error in periodic strategy update: {e}")

    async def _run_strategy_wrapper(self, price, market_state):
        # Helper to run strategy which is sync but wrapped in runner
        # The runner's on_price_update is async but we need the return value here
        # So we modified StrategyRunner to return data if we call it directly?
        # Actually, StrategyRunner.on_price_update was void.
        # Let's call the internal logic or refactor StrategyRunner to return signal.
        # For now, let's use the internal method of StrategyRunner if possible or just rely on its state.
        
        # Better: StrategyRunner.on_price_update should return the signal if any.
        # I'll update StrategyRunner in a moment, but for now let's assume I can access it.
        # I will modify StrategyRunner to return the signal_data from on_price_update.
        
        # Wait, I can't easily modify it without another tool call. 
        # I'll just use the side effect: check latest_signal.
        
        await self.strategy_runner.on_price_update(price, market_state)
        
        # Check if a NEW signal was generated just now.
        # This is race-condition prone.
        # Ideally, StrategyRunner should return the signal.
        # I will assume I can fix StrategyRunner or just use it as is.
        # Actually, I implemented `_run_strategy` to return signal_data, but `on_price_update` ignores it.
        # I will fix StrategyRunner in the next step.
        return None 

    def get_status(self):
        # Aggregate status from components
        market_state = self.market_data.get_market_state() if self.market_data else {}
        strategy_data = self.strategy_runner.latest_strategy_data if self.strategy_runner else {}

        # Unrealized PnL: in paper mode positions live in position_manager (set below after price update).
        # Otherwise use paper_manager if it holds positions (e.g. multi-leg strategies).
        unrealized_pnl = 0.0
        in_paper_with_positions = (
            self.order_manager and self.order_manager.trading_mode == "PAPER"
            and self.position_manager and self.position_manager.positions
        )
        if not in_paper_with_positions and self.order_manager and self.order_manager.paper_manager:
            # Use cached prices from MarketDataManager for speed
            current_prices = {}
            positions = self.order_manager.paper_manager.get_positions()
            if positions:
                keys = []
                for p in positions:
                     # Extract keys from legs or single position
                     if p.get("legs"):
                         keys.extend([leg.get("instrument_key") for leg in p["legs"]])
                     elif p.get("instrument_key"):
                         keys.append(p.get("instrument_key"))
                
                # Get prices from cache
                if self.market_data:
                    for key in keys:
                        price = self.market_data.get_price(key)
                        if price > 0:
                            current_prices[key] = price
            
            unrealized_pnl = self.order_manager.paper_manager.get_pnl(current_prices)
        
        # Get Greeks from market_state or strategy_data
        greeks_data = market_state.get("greeks") or strategy_data.get("greeks")
        
        # Build complete strategy_data with all required fields and safe defaults
        complete_strategy_data = {
            "signal": self.strategy_runner.latest_signal if self.strategy_runner else "WAITING",
            "rsi": strategy_data.get("rsi", 0),
            "ema_50": strategy_data.get("ema_50", 0),
            "ema_5": strategy_data.get("ema_5", 0),
            "ema_20": strategy_data.get("ema_20", 0),
            "macd": strategy_data.get("macd", 0),
            "macd_signal": strategy_data.get("macd_signal", 0),
            "supertrend": strategy_data.get("supertrend", "N/A"),
            "vwap": strategy_data.get("vwap", 0),
            "bb_upper": strategy_data.get("bb_upper", 0),
            "bb_lower": strategy_data.get("bb_lower", 0),
            "greeks": greeks_data,
            "support_resistance": strategy_data.get("support_resistance", {}),
            "breakout": strategy_data.get("breakout", {}),
            "filters": strategy_data.get("filters", {}),
            "volume_ratio": strategy_data.get("volume_ratio", 0),
            "atr_pct": strategy_data.get("atr_pct", 0),
            "progress": strategy_data.get("progress", None),
        }
        
        # Update current_price on each position before serializing (real-time P&L)
        if self.position_manager:
            positions_objs = self.position_manager.positions
            if positions_objs:
                # Use cached prices
                for pos in positions_objs.values():
                    if self.market_data:
                        price = self.market_data.get_price(pos.instrument_key)
                        if price > 0:
                            pos.current_price = price
                            
                # In paper mode, aggregate unrealized P&L from position_manager (paper_manager has no positions)
                if self.order_manager and self.order_manager.trading_mode == "PAPER":
                    unrealized_pnl = sum(
                        (p.current_price - p.entry_price) * p.quantity for p in positions_objs.values()
                    )
        
        # Collect intelligence snapshot for frontend display
        intelligence_snapshot = {}
        if self.intelligence_engine:
            intelligence_snapshot = self.intelligence_engine.get_context()

        # Unified positions: single-leg (PositionManager) + multi-leg (PaperTradingManager)
        all_positions = self.position_manager.get_positions() if self.position_manager else []
        paper_mgr = self.order_manager.paper_manager if self.order_manager else None
        if paper_mgr:
            # Add multi-leg positions that aren't already covered by position_manager
            for pos in paper_mgr.get_open_positions():
                all_positions.append(pos)

        # Unified trade history from paper_mgr (ground truth)
        unified_trade_history = paper_mgr.get_trade_history(limit=20) if paper_mgr else []
        if not unified_trade_history and self.trade_executor:
            unified_trade_history = self.trade_executor.trade_history[-10:]

        status = {
            "is_running": self.is_running,
            "latest_signal": self.strategy_runner.latest_signal if self.strategy_runner else "WAITING",
            "current_price": self.market_data.current_price if self.market_data else 0,
            "atm_strike": self.market_data.atm_strike if self.market_data else 0,
            "logs": self.latest_log,
            "positions": all_positions,
            "risk_stats": self.risk_manager.get_stats() if self.risk_manager else {},
            "trade_history": unified_trade_history,
            "paper_balance": paper_mgr.get_balance() if paper_mgr else 0,
            "paper_pnl": unrealized_pnl,
            "paper_daily_pnl": paper_mgr.get_daily_realized_pnl() if paper_mgr else 0.0,
            "portfolio_stats": paper_mgr.get_portfolio_stats() if paper_mgr else {},
            "market_state": market_state,
            "strategy_data": complete_strategy_data,
            "reasoning": self.strategy_runner.latest_reasoning if self.strategy_runner else {},
            "decision_reason": strategy_data.get("decision_reason", "Analyzing..."),
            "target_contract": self.strategy_runner.target_contract if self.strategy_runner else None,
            "trading_mode": self.order_manager.trading_mode if self.order_manager else "PAPER",
            "sentiment": market_state.get("sentiment", {}),
            "pcr": market_state.get("pcr"),
            "pcr_analysis": market_state.get("pcr_analysis"),
            "vix": market_state.get("vix"),
            "intelligence": intelligence_snapshot,   # New: full intelligence context
            "token_valid": getattr(self.data_fetcher, "token_valid", True) if self.data_fetcher else True,
            "config": {
                "timeframe": self.timeframe,
                "symbol": self.nifty_key,
                "access_token_present": bool(self.access_token)
            }
        }
        return status

    # ... (Keep other methods like update_config, set_trading_mode, etc. proxying to components)
    def update_config(self, timeframe=None):
        if timeframe:
            self.timeframe = timeframe
            if self.strategy_runner:
                self.strategy_runner.timeframe = timeframe
            self.log(f"Timeframe updated to {timeframe}")
        return self.get_status()

    def set_trading_mode(self, mode):
        if self.order_manager:
            self.order_manager.set_mode(mode)
            self.log(f"Trading mode switched to {mode}")
        return self.get_status()

    def add_paper_funds(self, amount):
        if self.order_manager:
            self.order_manager.paper_manager.add_funds(float(amount))
        return self.get_status()

    def set_access_token(self, token):
        """
        Set access token and persist it to .env file.
        This ensures the token is available even after server restart.
        """
        if not token:
            self.log(f"❌ Attempted to set empty access token")
            return
        
        self.access_token = token
        self.log(f"🔐 Setting access token (first 20 chars: {token[:20]}...)")
        
        # Save to .env file for persistence
        try:
            import os
            from pathlib import Path
            
            env_path = Path(__file__).parent / '.env'
            self.log(f"📝 Saving token to {env_path}")
            
            # Read existing .env
            env_content = {}
            if env_path.exists():
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            env_content[key] = value
            
            # Update token
            env_content['UPSTOX_ACCESS_TOKEN'] = token
            
            # Write back to .env
            with open(env_path, 'w') as f:
                for key, value in env_content.items():
                    f.write(f"{key}={value}\n")
            
            self.log(f"✅ Token written to .env file")
            
            # Reload config
            Config.reload()
            self.log(f"✅ Config reloaded with new token")
        except Exception as e:
            self.log(f"❌ Error saving token to .env: {e}")
            import traceback
            self.log(f"   Traceback: {traceback.format_exc()}")
        
        # Update all components with new token
        try:
            if self.market_data:
                self.market_data.access_token = token
                self.log(f"✅ Token updated in market_data")
            if self.order_manager:
                self.order_manager.set_access_token(token)
                self.log(f"✅ Token updated in order_manager")
            if self.data_fetcher:
                self.data_fetcher.set_access_token(token)
                self.log(f"✅ Token updated in data_fetcher")
        except Exception as e:
            self.log(f"⚠️ Error updating token in components: {e}")
        
        self.log(f"🟢 Access token set successfully")

bot = TradingBot()
