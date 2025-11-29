import pandas as pd
import os
import logging
from datetime import datetime

class AIDataCollector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.data_buffer = [] # List to store trade records
        
    def log_entry(self, trade_id, timestamp, market_data, indicators, signal):
        """
        Log the state of the market and indicators at the time of trade entry.
        """
        entry_record = {
            "trade_id": trade_id,
            "timestamp": timestamp,
            "symbol": market_data.get("symbol", "UNKNOWN"),
            "signal": signal,
            
            # Market Data
            "open": market_data.get("open"),
            "high": market_data.get("high"),
            "low": market_data.get("low"),
            "close": market_data.get("close"),
            "volume": market_data.get("volume"),
            
            # Indicators
            "rsi": indicators.get("rsi"),
            "supertrend": 1 if indicators.get("supertrend") == "BULLISH" else -1,
            "vwap": indicators.get("vwap"),
            "pcr": indicators.get("pcr"),
            
            # Derived Features
            "price_vs_vwap": market_data.get("close") - indicators.get("vwap") if indicators.get("vwap") else None,
        }
        
        # Add Greeks if available
        greeks = indicators.get("greeks")
        if greeks:
            entry_record["ce_delta"] = greeks.get("ce", {}).get("delta")
            entry_record["pe_delta"] = greeks.get("pe", {}).get("delta")
            entry_record["ce_theta"] = greeks.get("ce", {}).get("theta")
            entry_record["pe_theta"] = greeks.get("pe", {}).get("theta")
        else:
            entry_record["ce_delta"] = None
            entry_record["pe_delta"] = None
            entry_record["ce_theta"] = None
            entry_record["pe_theta"] = None
            
        self.data_buffer.append(entry_record)
        
    def update_exit(self, trade_id, pnl, pnl_pct, outcome):
        """
        Update the existing record with exit details (Label).
        """
        for record in self.data_buffer:
            if record["trade_id"] == trade_id:
                record["pnl"] = pnl
                record["pnl_pct"] = pnl_pct
                record["outcome"] = outcome # 1 for Win, 0 for Loss
                return
                
        self.logger.warning(f"Trade ID {trade_id} not found in buffer for exit update.")

    def save_to_csv(self, filename="ai_training_data.csv"):
        """
        Save the buffered data to a CSV file.
        """
        if not self.data_buffer:
            self.logger.warning("No data to save.")
            return
            
        df = pd.DataFrame(self.data_buffer)
        
        # Check if file exists to append or create new
        file_exists = os.path.isfile(filename)
        
        try:
            if file_exists:
                df.to_csv(filename, mode='a', header=False, index=False)
                self.logger.info(f"Appended {len(df)} records to {filename}")
            else:
                df.to_csv(filename, index=False)
                self.logger.info(f"Created {filename} with {len(df)} records")
                
            # Clear buffer after saving
            self.data_buffer = []
            
        except Exception as e:
            self.logger.error(f"Failed to save AI data: {e}")
