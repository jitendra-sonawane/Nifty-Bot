"""
Data models for the Nifty 50 Algo Trading Platform.
Clean dataclass-based models used across strategies, execution, and backtesting.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import datetime


# ─── Enums ──────────────────────────────────────────────────────────────────

class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"

class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class TradingMode(str, Enum):
    SANDBOX = "sandbox"
    PAPER = "paper"
    LIVE = "live"

class SignalAction(str, Enum):
    ENTER = "ENTER"
    EXIT = "EXIT"
    ADJUST = "ADJUST"
    HOLD = "HOLD"

class OrderStatus(str, Enum):
    PENDING = "pending"
    PLACED = "placed"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class StrategyType(str, Enum):
    IRON_CONDOR = "iron_condor"
    SHORT_STRADDLE = "short_straddle"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    BREAKOUT = "breakout"


# ─── Core Data Models ───────────────────────────────────────────────────────

@dataclass
class Greeks:
    """Option Greeks for a single instrument."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    iv: float = 0.0  # Implied volatility (%)

    def to_dict(self) -> dict:
        return {
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 6),
            "theta": round(self.theta, 4),
            "vega": round(self.vega, 4),
            "iv": round(self.iv, 2),
        }


@dataclass
class OrderLeg:
    """Single leg of a multi-leg option order."""
    instrument_key: str
    strike: float
    option_type: OptionType
    transaction_type: TransactionType
    quantity: int
    price: float = 0.0
    greeks: Optional[Greeks] = None

    @property
    def is_buy(self) -> bool:
        return self.transaction_type == TransactionType.BUY

    @property
    def is_sell(self) -> bool:
        return self.transaction_type == TransactionType.SELL

    @property
    def premium_flow(self) -> float:
        """Positive = credit received, negative = debit paid."""
        sign = -1 if self.is_buy else 1
        return sign * self.price * self.quantity

    def to_dict(self) -> dict:
        return {
            "instrument_key": self.instrument_key,
            "strike": self.strike,
            "option_type": self.option_type.value,
            "transaction_type": self.transaction_type.value,
            "quantity": self.quantity,
            "price": round(self.price, 2),
            "greeks": self.greeks.to_dict() if self.greeks else None,
        }


@dataclass
class StrategySignal:
    """Output from a strategy's signal generation."""
    strategy_name: str
    action: SignalAction
    legs: List[OrderLeg] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0  # 0.0 to 1.0
    max_risk: float = 0.0
    max_reward: float = 0.0
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)

    @property
    def net_premium(self) -> float:
        """Net premium collected (+ve) or paid (-ve)."""
        return sum(leg.premium_flow for leg in self.legs)

    @property
    def risk_reward_ratio(self) -> float:
        if self.max_risk == 0:
            return 0.0
        return round(self.max_reward / self.max_risk, 2)

    def to_dict(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "action": self.action.value,
            "legs": [leg.to_dict() for leg in self.legs],
            "reasoning": self.reasoning,
            "confidence": round(self.confidence, 2),
            "max_risk": round(self.max_risk, 2),
            "max_reward": round(self.max_reward, 2),
            "net_premium": round(self.net_premium, 2),
            "risk_reward_ratio": self.risk_reward_ratio,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PositionLeg:
    """A tracked leg within an active multi-leg position."""
    leg_id: str
    instrument_key: str
    strike: float
    option_type: OptionType
    transaction_type: TransactionType
    quantity: int
    entry_price: float
    current_price: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        """P&L for this leg based on current vs entry price."""
        multiplier = 1 if self.transaction_type == TransactionType.BUY else -1
        return multiplier * (self.current_price - self.entry_price) * self.quantity

    def to_dict(self) -> dict:
        return {
            "leg_id": self.leg_id,
            "instrument_key": self.instrument_key,
            "strike": self.strike,
            "option_type": self.option_type.value,
            "transaction_type": self.transaction_type.value,
            "quantity": self.quantity,
            "entry_price": round(self.entry_price, 2),
            "current_price": round(self.current_price, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
        }


@dataclass
class MultiLegPosition:
    """A complete multi-leg option position (e.g., Iron Condor = 4 legs)."""
    position_id: str
    strategy_name: str
    legs: List[PositionLeg] = field(default_factory=list)
    entry_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    exit_time: Optional[datetime.datetime] = None
    is_open: bool = True
    max_risk: float = 0.0
    max_reward: float = 0.0
    exit_reason: str = ""

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(leg.unrealized_pnl for leg in self.legs)

    @property
    def market_value(self) -> float:
        """Net cash flow to close this position (NLV component).
        Positive = we'd receive cash, Negative = we'd pay cash."""
        total = 0.0
        for leg in self.legs:
            sign = 1 if leg.transaction_type == TransactionType.BUY else -1
            total += sign * leg.current_price * leg.quantity
        return total

    @property
    def net_entry_premium(self) -> float:
        """Net premium at entry. Positive = credit strategy."""
        total = 0.0
        for leg in self.legs:
            sign = -1 if leg.transaction_type == TransactionType.BUY else 1
            total += sign * leg.entry_price * leg.quantity
        return total

    @property
    def portfolio_greeks(self) -> Dict[str, float]:
        """Aggregate Greeks across all legs."""
        totals = {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}
        # This would be populated by the risk manager with live Greeks
        return totals

    def to_dict(self) -> dict:
        net_entry = self.net_entry_premium
        return {
            "position_id": self.position_id,
            "strategy_name": self.strategy_name,
            "legs": [leg.to_dict() for leg in self.legs],
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "is_open": self.is_open,
            "total_unrealized_pnl": round(self.total_unrealized_pnl, 2),
            "net_entry_premium": round(net_entry, 2),
            "trade_type": "CREDIT" if net_entry >= 0 else "DEBIT",
            "market_value": round(self.market_value, 2),
            "max_risk": round(self.max_risk, 2),
            "max_reward": round(self.max_reward, 2),
            "exit_reason": self.exit_reason,
        }


@dataclass
class TradeRecord:
    """Completed trade record for analytics."""
    trade_id: str
    strategy_name: str
    entry_time: datetime.datetime
    exit_time: datetime.datetime
    legs: List[dict]   # Serialized leg data at entry
    entry_premium: float
    exit_premium: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    market_conditions: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        duration = (self.exit_time - self.entry_time).total_seconds() / 60 if self.exit_time and self.entry_time else 0
        # Persist market_conditions so it survives save/load round-trips
        mc = dict(self.market_conditions) if self.market_conditions else {}
        mc["duration_minutes"] = round(duration, 1)
        trade_type = mc.get("trade_type", "DEBIT")
        return {
            "trade_id": self.trade_id,
            "strategy_name": self.strategy_name,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "legs": self.legs,
            "entry_premium": round(self.entry_premium, 2),
            "exit_premium": round(self.exit_premium, 2),
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 2),
            "exit_reason": self.exit_reason,
            "trade_type": trade_type,
            "market_conditions": mc,
            "duration_minutes": round(duration, 1),
        }


@dataclass
class PerformanceMetrics:
    """Performance analytics for backtesting and live trading."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_trade_duration: float = 0.0  # minutes
    expectancy: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "best_trade": round(self.best_trade, 2),
            "worst_trade": round(self.worst_trade, 2),
            "avg_trade_duration": round(self.avg_trade_duration, 1),
            "expectancy": round(self.expectancy, 2),
        }


@dataclass
class BacktestResult:
    """Complete backtest output."""
    strategy_name: str
    from_date: str
    to_date: str
    initial_capital: float
    final_capital: float
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    equity_timestamps: List[str] = field(default_factory=list)
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)

    def to_dict(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [round(e, 2) for e in self.equity_curve],
            "equity_timestamps": self.equity_timestamps,
            "metrics": self.metrics.to_dict(),
        }


@dataclass
class OptionChainEntry:
    """Single row in the option chain (one strike, CE + PE)."""
    strike: float
    ce_price: float = 0.0
    pe_price: float = 0.0
    ce_oi: int = 0
    pe_oi: int = 0
    ce_volume: int = 0
    pe_volume: int = 0
    ce_iv: float = 0.0
    pe_iv: float = 0.0
    ce_greeks: Optional[Greeks] = None
    pe_greeks: Optional[Greeks] = None
    ce_instrument_key: str = ""
    pe_instrument_key: str = ""
    ce_pop: float = 0.0  # Probability of Profit (from Upstox API)
    pe_pop: float = 0.0

    def to_dict(self) -> dict:
        return {
            "strike": self.strike,
            "ce_price": round(self.ce_price, 2),
            "pe_price": round(self.pe_price, 2),
            "ce_oi": self.ce_oi,
            "pe_oi": self.pe_oi,
            "ce_volume": self.ce_volume,
            "pe_volume": self.pe_volume,
            "ce_iv": round(self.ce_iv, 2),
            "pe_iv": round(self.pe_iv, 2),
            "ce_instrument_key": self.ce_instrument_key,
            "pe_instrument_key": self.pe_instrument_key,
            "ce_pop": round(self.ce_pop, 1),
            "pe_pop": round(self.pe_pop, 1),
        }
