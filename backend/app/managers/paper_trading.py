"""
Enhanced Paper Trading Manager.
Supports multi-leg positions, per-strategy analytics,
transaction history with reasoning, and wallet tracking.

Usage:
    ptm = PaperTradingManager(initial_capital=1000000)
    pos = ptm.open_position(signal)       # From strategy signal
    ptm.update_position_prices(pos_id, prices)
    ptm.close_position(pos_id, reason)
    stats = ptm.get_portfolio_stats()
"""

import uuid
import datetime
import logging
import json
import csv
import os
from typing import Dict, List, Optional

from app.core.config import Config
from app.core.models import (
    StrategySignal,
    MultiLegPosition,
    PositionLeg,
    TradeRecord,
    PerformanceMetrics,
    TransactionType,
    OptionType,
)

logger = logging.getLogger(__name__)


class PaperTradingManager:
    """
    Enhanced paper trading manager for multi-leg option positions.

    Features:
    - Virtual wallet with configurable initial capital
    - Multi-leg position tracking (Iron Condor = 4 legs as one position)
    - Real-time P&L updates per position
    - Transaction history with trade reasoning
    - Per-strategy performance analytics
    - Persistence to JSON file (survives server restarts)
    - CSV trade journal for ML training
    """

    SAVE_FILE = "paper_trading_state.json"
    CSV_FILE  = "trade_journal.csv"

    def __init__(self, initial_capital: float = None):
        self.initial_capital = initial_capital or Config.INITIAL_CAPITAL
        self.balance = self.initial_capital

        # Active positions
        self.positions: Dict[str, MultiLegPosition] = {}  # position_id -> position

        # Completed trades
        self.trade_history: List[TradeRecord] = []

        # Session tracking
        self.session_pnl: float = 0.0
        self.session_start = datetime.datetime.now()

        # Load saved state
        self._load_state()
        self._ensure_csv_header()

    # ─── Position Lifecycle ──────────────────────────────────────────────────

    def open_position(self, signal: StrategySignal) -> Optional[MultiLegPosition]:
        """
        Open a new multi-leg position from a strategy signal.

        Args:
            signal: StrategySignal with ENTER action and defined legs

        Returns:
            MultiLegPosition if opened, None if rejected
        """
        if not signal.legs:
            logger.warning(f"Cannot open position — no legs in signal")
            return None

        # Calculate margin/debit required
        net_premium = signal.net_premium
        margin_required = signal.max_risk if net_premium >= 0 else abs(net_premium)

        if margin_required > self.balance:
            logger.warning(
                f"Insufficient balance: ₹{self.balance:,.0f} < ₹{margin_required:,.0f}"
            )
            return None

        # Create position
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

        position = MultiLegPosition(
            position_id=position_id,
            strategy_name=signal.strategy_name,
            legs=position_legs,
            entry_time=datetime.datetime.now(),
            is_open=True,
            max_risk=signal.max_risk,
            max_reward=signal.max_reward,
        )

        self.positions[position_id] = position

        # Deduct debit premium from balance (credit strategies don't touch balance until close)
        if net_premium < 0:
            self.balance += net_premium  # net_premium is negative for debit

        logger.info(
            f"📂 Position Opened: {signal.strategy_name} | "
            f"ID: {position_id} | Legs: {len(signal.legs)} | "
            f"Net Premium: ₹{net_premium:,.0f} | "
            f"Remaining Balance: ₹{self.balance:,.0f}"
        )

        self._save_state()
        return position

    def update_position_prices(
        self,
        position_id: str,
        current_prices: Dict[str, float],
    ) -> Optional[float]:
        """
        Update current prices for a position's legs.

        Args:
            position_id: Position to update
            current_prices: Dict of leg_id -> current_price OR instrument_key -> current_price

        Returns:
            Total unrealized P&L, or None if position not found
        """
        position = self.positions.get(position_id)
        if not position or not position.is_open:
            return None

        for leg in position.legs:
            if leg.leg_id in current_prices:
                leg.current_price = current_prices[leg.leg_id]
            elif leg.instrument_key in current_prices:
                leg.current_price = current_prices[leg.instrument_key]

        return position.total_unrealized_pnl

    def close_position(
        self,
        position_id: str,
        exit_reason: str = "manual",
    ) -> Optional[TradeRecord]:
        """
        Close an open position and record the trade.

        Args:
            position_id: Position to close
            exit_reason: Reason for closing

        Returns:
            TradeRecord of the completed trade
        """
        position = self.positions.get(position_id)
        if not position or not position.is_open:
            logger.warning(f"Position {position_id} not found or already closed")
            return None

        # Close position
        position.is_open = False
        position.exit_time = datetime.datetime.now()
        position.exit_reason = exit_reason

        # Calculate final P&L
        pnl = position.total_unrealized_pnl
        entry_premium = abs(position.net_entry_premium)

        # Exit premium: what we receive/pay to close each leg
        exit_premium = 0
        for leg in position.legs:
            # To close: reverse the original transaction
            # If originally SOLD, we BUY back (cost) → negative flow
            # If originally BOUGHT, we SELL (receive) → positive flow
            sign = 1 if leg.transaction_type == TransactionType.BUY else -1
            exit_premium += sign * leg.current_price * leg.quantity

        pnl_pct = (pnl / max(entry_premium, 1)) * 100

        # Duration
        duration = (position.exit_time - position.entry_time).total_seconds() / 60

        # Legs snapshot at exit
        legs_snapshot = []
        for leg in position.legs:
            d = leg.to_dict()
            d["exit_price"] = round(leg.current_price, 2)
            legs_snapshot.append(d)

        # Create trade record
        trade = TradeRecord(
            trade_id=position_id,
            strategy_name=position.strategy_name,
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            legs=legs_snapshot,
            entry_premium=entry_premium,
            exit_premium=abs(exit_premium),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            exit_reason=exit_reason,
            market_conditions={"duration_minutes": round(duration, 1)},
        )

        self.trade_history.append(trade)
        self._append_trade_to_csv(trade)

        # Update balance (realise P&L)
        self.balance += pnl
        self.session_pnl += pnl

        # Remove from active positions
        del self.positions[position_id]

        logger.info(
            f"📕 Position Closed: {position.strategy_name} | "
            f"ID: {position_id} | P&L: ₹{pnl:,.0f} ({pnl_pct:.1f}%) | "
            f"Reason: {exit_reason} | Balance: ₹{self.balance:,.0f}"
        )

        self._save_state()
        return trade

    def record_single_leg_trade(self, trade_dict: dict):
        """
        Record a completed single-leg trade (from PositionManager) into the unified journal.

        Args:
            trade_dict: Trade summary from PositionManager.close_position()
                Expected keys: position_id, instrument, type, entry_price, exit_price,
                               quantity, pnl, pnl_pct, reason, entry_time, exit_time
        """
        try:
            pnl = float(trade_dict.get("pnl", 0))

            entry_dt = datetime.datetime.fromisoformat(trade_dict["entry_time"]) \
                if isinstance(trade_dict["entry_time"], str) else trade_dict["entry_time"]
            exit_dt = datetime.datetime.fromisoformat(trade_dict["exit_time"]) \
                if isinstance(trade_dict["exit_time"], str) else trade_dict["exit_time"]

            entry_price = float(trade_dict.get("entry_price", 0))
            exit_price = float(trade_dict.get("exit_price", 0))
            quantity = int(trade_dict.get("quantity", 0))
            option_type = trade_dict.get("type", "CE")

            leg_snapshot = {
                "instrument_key": trade_dict.get("instrument", ""),
                "option_type": option_type,
                "transaction_type": "BUY",
                "quantity": quantity,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "unrealized_pnl": pnl,
            }

            trade = TradeRecord(
                trade_id=trade_dict.get("position_id", str(uuid.uuid4())[:8]),
                strategy_name=f"single_leg_{option_type.lower()}",
                entry_time=entry_dt,
                exit_time=exit_dt,
                legs=[leg_snapshot],
                entry_premium=entry_price * quantity,
                exit_premium=exit_price * quantity,
                pnl=round(pnl, 2),
                pnl_pct=round(float(trade_dict.get("pnl_pct", 0)), 2),
                exit_reason=trade_dict.get("reason", "manual"),
                market_conditions={
                    "duration_minutes": round(
                        (exit_dt - entry_dt).total_seconds() / 60, 1
                    )
                },
            )

            self.trade_history.append(trade)
            self._append_trade_to_csv(trade)

            # Reflect realized P&L in balance & session P&L
            self.balance += pnl
            self.session_pnl += pnl

            self._save_state()

            logger.info(
                f"📋 Single-leg trade recorded: {option_type} | "
                f"P&L: ₹{pnl:,.0f} | Balance: ₹{self.balance:,.0f}"
            )
        except Exception as e:
            logger.error(f"Failed to record single-leg trade: {e}", exc_info=True)

    # ─── Query Methods ───────────────────────────────────────────────────────

    def get_open_positions(self) -> List[dict]:
        """Get all open positions as dicts."""
        return [p.to_dict() for p in self.positions.values() if p.is_open]

    def get_position(self, position_id: str) -> Optional[MultiLegPosition]:
        """Get a specific position."""
        return self.positions.get(position_id)

    def get_trade_history(self, strategy: str = None, limit: int = 50) -> List[dict]:
        """Get completed trade history, optionally filtered by strategy."""
        trades = self.trade_history
        if strategy:
            trades = [t for t in trades if t.strategy_name == strategy]

        # Most recent first
        trades = sorted(trades, key=lambda t: t.exit_time, reverse=True)
        return [t.to_dict() for t in trades[:limit]]

    def get_strategy_analytics(self) -> Dict[str, dict]:
        """Get per-strategy performance breakdown."""
        analytics = {}

        by_strategy: Dict[str, List[TradeRecord]] = {}
        for trade in self.trade_history:
            by_strategy.setdefault(trade.strategy_name, []).append(trade)

        for strategy_name, trades in by_strategy.items():
            pnls = [t.pnl for t in trades]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]

            analytics[strategy_name] = {
                "total_trades": len(trades),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": round(len(wins) / max(len(trades), 1) * 100, 1),
                "total_pnl": round(sum(pnls), 2),
                "avg_pnl": round(sum(pnls) / max(len(trades), 1), 2),
                "best_trade": round(max(pnls), 2) if pnls else 0,
                "worst_trade": round(min(pnls), 2) if pnls else 0,
                "profit_factor": round(
                    sum(wins) / max(abs(sum(losses)), 1), 2
                ) if losses else float("inf"),
            }

        return analytics

    def get_portfolio_stats(self) -> dict:
        """Get overall portfolio statistics."""
        open_pnl = sum(p.total_unrealized_pnl for p in self.positions.values() if p.is_open)
        realized_pnl = sum(t.pnl for t in self.trade_history)

        total_trades = len(self.trade_history)
        winning_trades = len([t for t in self.trade_history if t.pnl > 0])
        win_rate = round(winning_trades / max(total_trades, 1) * 100, 1)

        all_pnls = [t.pnl for t in self.trade_history]
        wins_pnl = [p for p in all_pnls if p > 0]
        loss_pnl = [p for p in all_pnls if p < 0]

        return {
            "initial_capital": self.initial_capital,
            "current_balance": round(self.balance, 2),
            "total_equity": round(self.balance + open_pnl, 2),
            "unrealized_pnl": round(open_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "session_pnl": round(self.session_pnl, 2),
            "total_return_pct": round(
                (self.balance + open_pnl - self.initial_capital) / self.initial_capital * 100, 2
            ),
            "open_positions": len([p for p in self.positions.values() if p.is_open]),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": len([t for t in self.trade_history if t.pnl <= 0]),
            "win_rate": win_rate,
            "avg_win": round(sum(wins_pnl) / max(len(wins_pnl), 1), 2),
            "avg_loss": round(sum(loss_pnl) / max(len(loss_pnl), 1), 2),
            "best_trade": round(max(all_pnls), 2) if all_pnls else 0,
            "worst_trade": round(min(all_pnls), 2) if all_pnls else 0,
            "profit_factor": round(
                sum(wins_pnl) / max(abs(sum(loss_pnl)), 1), 2
            ) if loss_pnl else (float("inf") if wins_pnl else 0),
            "strategy_analytics": self.get_strategy_analytics(),
        }

    def reset(self):
        """Reset to initial state."""
        self.balance = self.initial_capital
        self.positions.clear()
        self.trade_history.clear()
        self.session_pnl = 0.0
        self.session_start = datetime.datetime.now()
        self._save_state()
        logger.info(f"🔄 Paper trading reset to ₹{self.initial_capital:,.0f}")

    # ─── Legacy Compatibility Methods ────────────────────────────────────────

    def get_balance(self) -> float:
        """Legacy: Return current cash balance."""
        return self.balance

    def place_order(
        self,
        instrument_key: str,
        quantity: int,
        transaction_type: str,
        price: float,
        product: str = "D",
    ) -> Optional[str]:
        """
        Legacy: Simulate order placement for paper trading.
        Used by OrderManager when trading_mode is PAPER.
        Deducts cost from balance for BUY and returns a fake order id.
        """
        if transaction_type.upper() != "BUY":
            logger.warning("Paper place_order: only BUY supported")
            return None
        cost = quantity * (price or 0)
        if cost <= 0:
            return None
        if cost > self.balance:
            logger.warning(
                f"Paper order rejected: cost ₹{cost:,.0f} > balance ₹{self.balance:,.0f}"
            )
            return None
        self.balance -= cost
        order_id = f"paper_{uuid.uuid4().hex[:12]}"
        self._save_state()
        logger.info(f"📄 Paper order placed: {order_id} | -₹{cost:,.0f} | Balance: ₹{self.balance:,.0f}")
        return order_id

    def get_positions(self) -> List[dict]:
        """Legacy: Return open positions as list of dicts."""
        return self.get_open_positions()

    def get_pnl(self, current_prices: Dict[str, float] = None) -> float:
        """Legacy: Return total unrealized P&L across open positions."""
        return sum(p.total_unrealized_pnl for p in self.positions.values() if p.is_open)

    def get_daily_realized_pnl(self) -> float:
        """Legacy: Return session/daily realized P&L."""
        return self.session_pnl

    def add_funds(self, amount: float):
        """Legacy: Add funds to paper trading balance."""
        self.balance += amount
        logger.info(f"💰 Added ₹{amount:,.0f} | New balance: ₹{self.balance:,.0f}")
        self._save_state()

    # ─── Persistence ─────────────────────────────────────────────────────────

    def _save_state(self):
        """Save full state to JSON for persistence across restarts."""
        try:
            # Serialize open positions (positions dict includes only open ones after close_position removes them)
            open_positions_data = []
            for pos in self.positions.values():
                if pos.is_open:
                    open_positions_data.append(pos.to_dict())

            state = {
                "initial_capital": self.initial_capital,
                "balance": self.balance,
                "session_pnl": self.session_pnl,
                "trade_history": [t.to_dict() for t in self.trade_history],
                "open_positions": open_positions_data,
                "saved_at": datetime.datetime.now().isoformat(),
            }
            with open(self.SAVE_FILE, "w") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save paper trading state: {e}", exc_info=True)

    def _load_state(self):
        """Load saved state including open positions."""
        try:
            if not os.path.exists(self.SAVE_FILE):
                logger.info("No saved paper trading state found — starting fresh")
                return

            with open(self.SAVE_FILE, "r") as f:
                state = json.load(f)

            self.balance = state.get("balance", self.initial_capital)
            self.session_pnl = state.get("session_pnl", 0)

            # ── Restore trade history ──────────────────────────────────────
            for t in state.get("trade_history", []):
                try:
                    trade = TradeRecord(
                        trade_id=t["trade_id"],
                        strategy_name=t["strategy_name"],
                        entry_time=datetime.datetime.fromisoformat(t["entry_time"]),
                        exit_time=datetime.datetime.fromisoformat(t["exit_time"]),
                        legs=t.get("legs", []),
                        entry_premium=t.get("entry_premium", 0),
                        exit_premium=t.get("exit_premium", 0),
                        pnl=t.get("pnl", 0),
                        pnl_pct=t.get("pnl_pct", 0),
                        exit_reason=t.get("exit_reason", ""),
                        market_conditions=t.get("market_conditions", {}),
                    )
                    self.trade_history.append(trade)
                except Exception as e:
                    logger.warning(f"Skipping corrupt trade record: {e}")

            # ── Restore open positions ─────────────────────────────────────
            restored = 0
            for pos_data in state.get("open_positions", []):
                try:
                    legs = []
                    for leg_data in pos_data.get("legs", []):
                        legs.append(PositionLeg(
                            leg_id=leg_data["leg_id"],
                            instrument_key=leg_data["instrument_key"],
                            strike=float(leg_data.get("strike", 0)),
                            option_type=OptionType(leg_data["option_type"]),
                            transaction_type=TransactionType(leg_data["transaction_type"]),
                            quantity=int(leg_data["quantity"]),
                            entry_price=float(leg_data["entry_price"]),
                            current_price=float(leg_data.get("current_price", leg_data["entry_price"])),
                        ))

                    position = MultiLegPosition(
                        position_id=pos_data["position_id"],
                        strategy_name=pos_data["strategy_name"],
                        legs=legs,
                        entry_time=datetime.datetime.fromisoformat(pos_data["entry_time"]),
                        exit_time=None,
                        is_open=True,
                        max_risk=float(pos_data.get("max_risk", 0)),
                        max_reward=float(pos_data.get("max_reward", 0)),
                    )
                    self.positions[position.position_id] = position
                    restored += 1
                except Exception as e:
                    logger.warning(f"Skipping corrupt position: {e}")

            logger.info(
                f"📥 Loaded paper trading state: balance=₹{self.balance:,.0f} | "
                f"trades={len(self.trade_history)} | open_positions={restored}"
            )
        except Exception as e:
            logger.error(f"Could not load paper trading state: {e}", exc_info=True)

    # ─── CSV Journal ─────────────────────────────────────────────────────────

    CSV_HEADERS = [
        "trade_id", "strategy", "entry_time", "exit_time", "duration_min",
        "legs_count", "entry_premium", "exit_premium", "pnl", "pnl_pct",
        "exit_reason", "balance_after",
    ]

    def _ensure_csv_header(self):
        """Create CSV with header if it doesn't exist."""
        if not os.path.exists(self.CSV_FILE):
            try:
                with open(self.CSV_FILE, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADERS)
            except Exception as e:
                logger.debug(f"Could not create CSV journal: {e}")

    def _append_trade_to_csv(self, trade: TradeRecord):
        """Append a completed trade to the CSV journal."""
        try:
            duration = trade.market_conditions.get("duration_minutes", 0)
            row = [
                trade.trade_id,
                trade.strategy_name,
                trade.entry_time.isoformat(),
                trade.exit_time.isoformat(),
                duration,
                len(trade.legs),
                round(trade.entry_premium, 2),
                round(trade.exit_premium, 2),
                round(trade.pnl, 2),
                round(trade.pnl_pct, 2),
                trade.exit_reason,
                round(self.balance, 2),
            ]
            with open(self.CSV_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            logger.debug(f"Could not write to CSV journal: {e}")
