import asyncio
import logging
import datetime
import uuid
from typing import Dict, List, Optional
from app.managers.order_manager import OrderManager
from app.managers.position_manager import PositionManager
from app.managers.risk_manager import RiskManager
from app.utils.ai_data_collector import AIDataCollector
from app.core.config import Config

logger = logging.getLogger(__name__)

# Policy for handling partial failures in multi-leg orders
PARTIAL_FAIL_CANCEL = "CANCEL_FILLED"   # Cancel all filled legs (conservative)
PARTIAL_FAIL_KEEP = "KEEP_FILLED"       # Keep filled legs (aggressive)


class TradeExecutor:
    def __init__(self, order_manager: OrderManager, position_manager: PositionManager, risk_manager: RiskManager):
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.risk_manager = risk_manager
        self.ai_collector = AIDataCollector()
        self.nifty_key = Config.SYMBOL_NIFTY_50
        self.trade_history = []
        self.partial_fail_policy = PARTIAL_FAIL_CANCEL

    async def execute_trade(self, signal_data: Dict):
        """Executes a trade based on signal data."""
        signal = signal_data['signal']
        greeks = signal_data.get('greeks')
        if not greeks:
            logger.warning("Cannot execute trade without Greeks data")
            return

        # Require instrument keys for order placement
        instrument_key = greeks.get('ce_instrument_key') if signal == "BUY_CE" else greeks.get('pe_instrument_key')
        if not instrument_key:
            logger.warning(
                "Cannot execute trade: Greeks missing ce_instrument_key/pe_instrument_key. "
                "Ensure MarketDataManager includes option instrument keys in greeks."
            )
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

        # RiskManager.can_trade(strategy_name, current_balance, current_positions, max_risk=0)
        strategy_name = "main"
        can_trade, reason = self.risk_manager.can_trade(
            strategy_name, current_balance, current_positions, max_risk=0
        )
        if can_trade:
            entry_price = greeks['ce']['price'] if signal == "BUY_CE" else greeks['pe']['price']
            logger.info(f"✅ Risk check passed. Placing {signal} order @ ₹{entry_price:.2f}")
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
                strike = signal_data.get('strike')
                position = self.position_manager.open_position(
                    instrument_key=instrument_key,
                    entry_price=entry_price,
                    quantity=quantity,
                    position_type=option_type,
                    strike=strike
                )
                logger.info(f"✅ Position opened: {position.id}")

                # Log for AI (include intelligence context for richer features)
                self.ai_collector.log_entry(
                    trade_id=position.id,
                    timestamp=datetime.datetime.now(),
                    market_data=signal_data['market_data'],
                    indicators=signal_data['indicators'],
                    signal=signal,
                    intelligence_context=signal_data.get('intelligence_context'),
                )
            else:
                logger.warning(
                    f"🚫 TRADE BLOCKED: Order placement returned None for {signal} "
                    f"| instrument={instrument_key} qty={quantity} price=₹{entry_price:.2f} "
                    f"(check paper balance or instrument key validity)"
                )
        else:
            logger.warning(f"❌ Trade blocked by risk manager: {reason}")

    async def execute_spread_trade(self, signal_data: Dict):
        """
        Execute a multi-leg spread trade (e.g., Bull Call Spread, Bear Put Spread, Iron Condor).

        signal_data must contain:
            - strategy_name: str (e.g., "bear_put_spread")
            - legs: List[Dict], each with:
                - instrument_key: str
                - quantity: int
                - transaction_type: "BUY" or "SELL"
                - price: float (current market price for the leg)
                - option_type: "CE" or "PE"
                - strike: int
            - market_data: dict (for AI logging)
            - indicators: dict (for AI logging)
        """
        legs = signal_data.get("legs", [])
        strategy_name = signal_data.get("strategy_name", "spread")

        if not legs or len(legs) < 2:
            logger.warning("Spread trade requires at least 2 legs")
            return

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self._place_spread_sync, strategy_name, legs, signal_data
            )
        except Exception as e:
            logger.error(f"Error executing spread trade: {e}", exc_info=True)

    def _place_spread_sync(self, strategy_name: str, legs: List[Dict], signal_data: Dict):
        """Place a multi-leg spread order synchronously."""
        current_balance = self.order_manager.paper_manager.get_balance()
        current_positions = self.position_manager.get_position_count()

        can_trade, reason = self.risk_manager.can_trade(
            strategy_name, current_balance, current_positions, max_risk=0
        )
        if not can_trade:
            logger.warning(f"Spread blocked by risk manager: {reason}")
            return

        # Build multi-order legs with IOC validity and correlation IDs
        spread_id = str(uuid.uuid4())[:8]
        order_legs = []
        for i, leg in enumerate(legs):
            order_legs.append({
                "instrument_key": leg["instrument_key"],
                "quantity": leg["quantity"],
                "transaction_type": leg["transaction_type"],
                "order_type": "MARKET",
                "product": "D",
                "price": leg.get("price", 0.0),
                "validity": "IOC",
                "correlation_id": f"{strategy_name}_{i}_{spread_id}",
                "tag": f"algo_{strategy_name}",
            })

        logger.info(f"Placing {strategy_name} spread: {len(order_legs)} legs | spread_id={spread_id}")
        result = self.order_manager.place_multi_order(order_legs)

        if result["partial"]:
            logger.warning(f"Spread partial fill! {len(result['order_ids'])} filled, {len(result['errors'])} failed")
            if self.partial_fail_policy == PARTIAL_FAIL_CANCEL:
                for oid in result["order_ids"]:
                    self.order_manager.cancel_order(oid)
                logger.info("Cancelled filled legs due to partial failure")
                return

        if not result["order_ids"]:
            logger.error(f"Spread order failed completely: {result['errors']}")
            return

        # Open positions for each successfully placed leg
        for i, (leg, oid) in enumerate(zip(legs, result["order_ids"])):
            if oid:
                position = self.position_manager.open_position(
                    instrument_key=leg["instrument_key"],
                    entry_price=leg.get("price", 0.0),
                    quantity=leg["quantity"],
                    position_type=leg.get("option_type", "CE"),
                    strike=leg.get("strike"),
                    order_id=oid,
                )
                logger.info(f"Spread leg {i} opened: {position.id} | {leg['transaction_type']} {leg.get('option_type')} @ {leg.get('strike')}")

        # AI logging
        self.ai_collector.log_entry(
            trade_id=f"spread_{spread_id}",
            timestamp=datetime.datetime.now(),
            market_data=signal_data.get("market_data", {}),
            indicators=signal_data.get("indicators", {}),
            signal=strategy_name,
            intelligence_context=signal_data.get("intelligence_context"),
        )

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
                        trade_id=trade.get('position_id', trade.get('id', 'UNKNOWN')),
                        pnl=trade['pnl'],
                        pnl_pct=trade['pnl_pct'],
                        outcome=1 if trade['pnl'] > 0 else 0
                    )
                    self.ai_collector.save_to_csv("ai_training_data.csv")
                    
                    logger.info(f"💼 Trade Closed: {trade['reason']} | P&L: ₹{trade['pnl']:.2f}")
            except Exception as e:
                logger.error(f"Error checking exits: {e}")
                
            # Sync closed trades to PaperTradingManager for unified history
            if closed_trades and self.order_manager.paper_manager:
                for trade in closed_trades:
                    # Check if already recorded (idempotency)
                    exists = any(t.trade_id == trade.get('position_id') for t in self.order_manager.paper_manager.trade_history)
                    if not exists:
                        self.order_manager.paper_manager.record_single_leg_trade(trade)
                        logger.info(f"✅ Synced closed trade {trade.get('position_id')} to PaperTradingManager")
