import asyncio
import logging
import datetime
from typing import Dict, Optional
from app.managers.order_manager import OrderManager
from app.managers.position_manager import PositionManager
from app.managers.risk_manager import RiskManager
from app.utils.ai_data_collector import AIDataCollector
from app.core.config import Config

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, order_manager: OrderManager, position_manager: PositionManager, risk_manager: RiskManager):
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.risk_manager = risk_manager
        self.ai_collector = AIDataCollector()
        self.nifty_key = Config.SYMBOL_NIFTY_50
        self.trade_history = []

    async def execute_trade(self, signal_data: Dict):
        """Executes a trade based on signal data."""
        signal = signal_data['signal']
        greeks = signal_data.get('greeks')
        
        if not greeks:
            logger.warning("Cannot execute trade without Greeks data")
            return

        try:
            # Run risk checks and order placement in executor
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._place_order_sync, signal, greeks, signal_data)
        except Exception as e:
            logger.error(f"Error executing trade: {e}")

    def _place_order_sync(self, signal, greeks, signal_data):
        current_balance = self.order_manager.paper_manager.get_balance()
        current_positions = self.position_manager.get_position_count()
        
        can_trade, reason = self.risk_manager.can_trade(current_balance, current_positions)
        
        if can_trade:
            entry_price = greeks['ce']['price'] if signal == "BUY_CE" else greeks['pe']['price']
            quantity = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_loss_pct=0.30,
                current_balance=current_balance
            )
            
            option_type = "CE" if signal == "BUY_CE" else "PE"
            instrument_key = greeks.get('ce_instrument_key') if signal == "BUY_CE" else greeks.get('pe_instrument_key')
            
            order_id = self.order_manager.place_order(
                instrument_key=instrument_key,
                quantity=quantity,
                transaction_type="BUY",
                order_type='MARKET',
                product='D',
                price=entry_price
            )
            
            if order_id:
                position = self.position_manager.open_position(
                    instrument_key=instrument_key,
                    entry_price=entry_price,
                    quantity=quantity,
                    position_type=option_type
                )
                logger.info(f"✅ Position opened: {position.id}")
                
                # Log for AI
                self.ai_collector.log_entry(
                    trade_id=position.id,
                    timestamp=datetime.datetime.now(),
                    market_data=signal_data['market_data'],
                    indicators=signal_data['indicators'],
                    signal=signal
                )
        else:
            logger.warning(f"❌ Trade blocked: {reason}")

    async def check_exits(self, current_prices: Dict[str, float]):
        """Checks for position exits."""
        if self.position_manager.get_position_count() > 0:
            try:
                loop = asyncio.get_running_loop()
                closed_trades = await loop.run_in_executor(None, self.position_manager.check_exits, current_prices)
                
                for trade in closed_trades:
                    self.trade_history.append(trade)
                    self.risk_manager.update_daily_pnl(trade['pnl'])
                    
                    self.ai_collector.update_exit(
                        trade_id=trade.get('id', 'UNKNOWN'),
                        pnl=trade['pnl'],
                        pnl_pct=trade['pnl_pct'],
                        outcome=1 if trade['pnl'] > 0 else 0
                    )
                    self.ai_collector.save_to_csv("ai_training_data_live.csv")
                    
                    logger.info(f"💼 Trade Closed: {trade['reason']} | P&L: ₹{trade['pnl']:.2f}")
            except Exception as e:
                logger.error(f"Error checking exits: {e}")
