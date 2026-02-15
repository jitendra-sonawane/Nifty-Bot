import pandas as pd
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Feature columns logged at entry + outcome columns added at exit
FEATURE_COLS = [
    "trade_id", "timestamp", "symbol", "signal",
    # Price
    "open", "high", "low", "close", "volume",
    # Technical indicators
    "rsi", "supertrend", "ema_5", "ema_20", "ema_diff_pct", "atr_pct",
    # Options data
    "pcr", "pcr_trend",
    "ce_delta", "pe_delta", "ce_theta", "pe_theta", "ce_iv", "pe_iv",
    # Intelligence context
    "vix", "regime", "adx", "iv_rank", "breadth_bias",
    # Time features
    "hour", "minute", "day_of_week",
    # Labels (filled at exit)
    "pnl", "pnl_pct", "outcome",
]


class AIDataCollector:
    def __init__(self):
        self.data_buffer = []  # In-memory buffer of trade records

    def log_entry(
        self,
        trade_id,
        timestamp,
        market_data: dict,
        indicators: dict,
        signal: str,
        intelligence_context: dict = None,
    ):
        """
        Log market state and indicator values at trade entry.

        Args:
            trade_id         : Unique position ID from PositionManager
            timestamp        : Entry datetime
            market_data      : Dict with OHLCV fields
            indicators       : Dict with rsi, supertrend, ema_5, ema_20, pcr, vix, greeks, etc.
            signal           : 'BUY_CE' or 'BUY_PE'
            intelligence_context : Optional IntelligenceEngine.get_context() snapshot
        """
        ts = timestamp if isinstance(timestamp, datetime) else datetime.now()
        greeks = indicators.get("greeks") or {}
        ce_g = greeks.get("ce") or {}
        pe_g = greeks.get("pe") or {}

        # Derive EMA diff %
        ema_5 = indicators.get("ema_5")
        ema_20 = indicators.get("ema_20")
        ema_diff_pct = None
        if ema_5 and ema_20 and ema_20 != 0:
            ema_diff_pct = round((ema_5 - ema_20) / ema_20 * 100, 4)

        # Pull from intelligence context if provided
        ic = intelligence_context or {}
        regime_ctx = ic.get("market_regime") or {}
        iv_ctx = ic.get("iv_rank") or {}
        breadth_ctx = ic.get("market_breadth") or {}

        record = {
            "trade_id": trade_id,
            "timestamp": ts.isoformat(),
            "symbol": market_data.get("symbol", "NSE_INDEX|Nifty 50"),
            "signal": signal,
            # Price
            "open":   market_data.get("open"),
            "high":   market_data.get("high"),
            "low":    market_data.get("low"),
            "close":  market_data.get("close"),
            "volume": market_data.get("volume"),
            # Technical
            "rsi":           indicators.get("rsi"),
            "supertrend":    1 if indicators.get("supertrend") == "BULLISH" else -1,
            "ema_5":         ema_5,
            "ema_20":        ema_20,
            "ema_diff_pct":  ema_diff_pct,
            "atr_pct":       indicators.get("atr_pct"),
            # Options
            "pcr":           indicators.get("pcr"),
            "pcr_trend":     indicators.get("pcr_trend"),
            "ce_delta":      ce_g.get("delta"),
            "pe_delta":      pe_g.get("delta"),
            "ce_theta":      ce_g.get("theta"),
            "pe_theta":      pe_g.get("theta"),
            "ce_iv":         ce_g.get("iv"),
            "pe_iv":         pe_g.get("iv"),
            # Intelligence
            "vix":           indicators.get("vix"),
            "regime":        regime_ctx.get("regime"),
            "adx":           regime_ctx.get("adx"),
            "iv_rank":       iv_ctx.get("iv_rank"),
            "breadth_bias":  breadth_ctx.get("breadth_bias"),
            # Time features
            "hour":        ts.hour,
            "minute":      ts.minute,
            "day_of_week": ts.weekday(),  # 0=Mon, 4=Fri
            # Labels — filled at exit
            "pnl":     None,
            "pnl_pct": None,
            "outcome": None,
        }

        self.data_buffer.append(record)
        logger.debug(f"AI entry logged: {trade_id} | {signal}")

    def update_exit(self, trade_id, pnl: float, pnl_pct: float, outcome: int):
        """
        Attach exit labels to the buffered entry record.

        Args:
            trade_id : Must match the trade_id used in log_entry()
            pnl      : Realized P&L in ₹
            pnl_pct  : P&L as % of premium
            outcome  : 1 = win, 0 = loss
        """
        for record in self.data_buffer:
            if record["trade_id"] == trade_id:
                record["pnl"]     = round(pnl, 2)
                record["pnl_pct"] = round(pnl_pct, 2)
                record["outcome"] = outcome
                logger.debug(f"AI exit labeled: {trade_id} | pnl={pnl:.2f} | outcome={outcome}")
                return

        logger.warning(f"AIDataCollector: trade_id '{trade_id}' not found in buffer for exit update.")

    def save_to_csv(self, filename="ai_training_data.csv"):
        """
        Append buffered records that have exit labels to the CSV file.
        Unlabeled records (still open) remain in buffer.
        """
        complete = [r for r in self.data_buffer if r.get("outcome") is not None]
        if not complete:
            logger.debug("No complete (labeled) records to save.")
            return

        df = pd.DataFrame(complete, columns=FEATURE_COLS)
        file_exists = os.path.isfile(filename)

        try:
            if file_exists:
                df.to_csv(filename, mode="a", header=False, index=False)
                logger.info(f"Appended {len(df)} labeled records to {filename}")
            else:
                df.to_csv(filename, index=False)
                logger.info(f"Created {filename} with {len(df)} records")

            # Keep only unlabeled records in buffer (open positions)
            self.data_buffer = [r for r in self.data_buffer if r.get("outcome") is None]

        except Exception as e:
            logger.error(f"Failed to save AI data: {e}")
