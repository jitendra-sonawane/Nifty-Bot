import json
import os
import datetime
import uuid
from typing import Optional, Dict, List

class Position:
    """Represents a single open position with entry/exit parameters."""
    
    def __init__(self, instrument_key: str, entry_price: float, quantity: int, 
                 position_type: str, strike: Optional[float] = None, stop_loss_pct: float = 0.30, target_multiplier: float = 1.5,
                 trailing_activation_pct: float = 1.0, trailing_pct: float = 0.5):
        self.id = str(uuid.uuid4())
        self.instrument_key = instrument_key
        self.entry_price = entry_price
        self.quantity = quantity
        self.position_type = position_type  # "CE" or "PE"
        self.strike = strike
        self.current_price = entry_price  # Tracks live option price
        self.entry_time = datetime.datetime.now()
        
        # Calculate stop loss and target
        self.stop_loss = entry_price * (1 - stop_loss_pct)
        self.target = entry_price * target_multiplier
        
        # Trailing Stop Configuration
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_pct = trailing_pct
        self.trailing_sl = None
        self.trailing_sl_activated = False
        
    def to_dict(self):
        pnl = (self.current_price - self.entry_price) * self.quantity
        pnl_pct = ((self.current_price - self.entry_price) / self.entry_price * 100) if self.entry_price else 0
        return {
            "id": self.id,
            "instrument_key": self.instrument_key,
            "entry_price": self.entry_price,
            "current_price": round(self.current_price, 2),
            "quantity": self.quantity,
            "position_type": self.position_type,
            "strike": self.strike,
            "stop_loss": round(self.stop_loss, 2),
            "target": round(self.target, 2),
            "trailing_sl": round(self.trailing_sl, 2) if self.trailing_sl else None,
            "trailing_sl_activated": bool(self.trailing_sl_activated),
            "entry_time": self.entry_time.isoformat(),
            "unrealized_pnl": round(pnl, 2),
            "unrealized_pnl_pct": round(pnl_pct, 2),
        }
    
    def update_trailing_stop(self, current_price: float):
        """Update trailing stop loss to lock in profits."""
        # Calculate percentage gain
        gain_pct = ((current_price - self.entry_price) / self.entry_price) * 100
        
        # Activate trailing SL if gain exceeds activation percentage
        if gain_pct >= self.trailing_activation_pct and not self.trailing_sl_activated:
            self.trailing_sl_activated = True
            # Initial trailing SL at breakeven or specified trail distance
            self.trailing_sl = max(self.entry_price, current_price * (1 - (self.trailing_pct / 100)))
        
        # Update trailing SL if price continues to rise
        if self.trailing_sl_activated and current_price > self.entry_price:
            # Calculate potential new SL based on trailing percentage
            new_trailing_sl = current_price * (1 - (self.trailing_pct / 100))
            
            # Only move SL up
            if self.trailing_sl is None or new_trailing_sl > self.trailing_sl:
                self.trailing_sl = new_trailing_sl
    
    def should_exit(self, current_price: float, current_time: datetime.datetime) -> tuple[bool, str]:
        """
        Check if position should be exited.
        Returns: (should_exit, reason)
        """
        # 1. Check stop loss
        if current_price <= self.stop_loss:
            return True, f"STOP_LOSS (Entry: {self.entry_price}, Exit: {current_price})"
        
        # 2. Check target
        if current_price >= self.target:
            return True, f"TARGET_HIT (Entry: {self.entry_price}, Exit: {current_price})"
        
        # 3. Check trailing stop loss
        if self.trailing_sl and current_price <= self.trailing_sl:
            return True, f"TRAILING_SL (Entry: {self.entry_price}, Exit: {current_price})"
        
        # 4. Check time-based exit (close at 3:15 PM)
        if current_time.hour == 15 and current_time.minute >= 15:
            return True, f"TIME_BASED_EXIT (Market Close)"
        
        return False, ""


class PositionManager:
    """Manages all open positions with persistence."""
    
    def __init__(self, data_file="positions_data.json"):
        self.data_file = data_file
        self.positions: Dict[str, Position] = {}
        self._load_positions()
    
    def _load_positions(self):
        """Load positions from file."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    # Reconstruct Position objects
                    for pos_data in data.get("positions", []):
                        pos = Position(
                            instrument_key=pos_data["instrument_key"],
                            entry_price=pos_data["entry_price"],
                            quantity=pos_data["quantity"],
                            position_type=pos_data["position_type"],
                            strike=pos_data.get("strike")
                        )
                        pos.id = pos_data["id"]
                        pos.stop_loss = pos_data["stop_loss"]
                        pos.target = pos_data["target"]
                        pos.trailing_sl = pos_data.get("trailing_sl")
                        pos.trailing_sl_activated = pos_data.get("trailing_sl_activated", False)
                        pos.trailing_activation_pct = pos_data.get("trailing_activation_pct", 1.0)
                        pos.trailing_pct = pos_data.get("trailing_pct", 0.5)
                        pos.current_price = pos_data.get("current_price", pos_data["entry_price"])
                        pos.entry_time = datetime.datetime.fromisoformat(pos_data["entry_time"])
                        self.positions[pos.id] = pos
            except Exception as e:
                print(f"Error loading positions: {e}")
    
    def _save_positions(self):
        """Save positions to file."""
        try:
            data = {
                "positions": [pos.to_dict() for pos in self.positions.values()]
            }
            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving positions: {e}")
    
    def open_position(self, instrument_key: str, entry_price: float,
                     quantity: int, position_type: str, strike: Optional[float] = None,
                     is_expiry_day: bool = False) -> Position:
        """Open a new position. On expiry day, SL is tightened automatically."""
        from app.core.config import Config

        # Validate instrument_key format
        if not self._is_valid_instrument_key(instrument_key):
            raise ValueError(f"❌ Invalid instrument_key format: {instrument_key}. Expected format: NSE_FO|xxxxx")

        # Tighten SL on expiry day (0DTE gamma risk)
        sl_pct = 0.30  # default
        if is_expiry_day:
            sl_pct *= Config.EXPIRY_DAY.get("sl_tightening_factor", 0.6)  # 30% * 0.6 = 18%

        position = Position(instrument_key, entry_price, quantity, position_type, strike=strike, stop_loss_pct=sl_pct)
        self.positions[position.id] = position
        self._save_positions()
        expiry_tag = " [0DTE: tightened SL]" if is_expiry_day else ""
        print(f"📈 Position Opened{expiry_tag}: {position_type} @ {entry_price} (SL: {position.stop_loss:.2f}, Target: {position.target:.2f})")
        return position
    
    def _is_valid_instrument_key(self, instrument_key: str) -> bool:
        """Validate instrument_key format - should be NSE_FO|xxxxx or NSE_INDEX|xxxxx."""
        if not instrument_key or not isinstance(instrument_key, str):
            return False
        # Valid format: NSE_FO|NIFTY25NOV26050CE or NSE_FO|52910 or NSE_INDEX|Nifty 50
        parts = instrument_key.split('|')
        if len(parts) != 2:
            return False
        exchange, key = parts
        if exchange not in ['NSE_FO', 'NSE_INDEX', 'NSE_EQ']:
            return False
        if not key or len(key.strip()) == 0:
            return False
        return True
    
    def close_position(self, position_id: str, exit_price: float, reason: str) -> Optional[Dict]:
        """Close a position and return P&L details."""
        if position_id not in self.positions:
            return None
        
        position = self.positions[position_id]
        pnl = (exit_price - position.entry_price) * position.quantity
        pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
        
        trade_summary = {
            "position_id": position_id,
            "instrument": position.instrument_key,
            "type": position.position_type,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "quantity": position.quantity,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "entry_time": position.entry_time.isoformat(),
            "exit_time": datetime.datetime.now().isoformat()
        }
        
        del self.positions[position_id]
        self._save_positions()
        
        print(f"📊 Position Closed: {reason} | P&L: ₹{pnl:.2f} ({pnl_pct:.2f}%)")
        return trade_summary
    
    def check_exits(self, current_prices: Dict[str, float]) -> List[Dict]:
        """
        Check all positions for exit conditions.
        Returns list of trade summaries for closed positions.
        """
        current_time = datetime.datetime.now()
        closed_trades = []
        positions_to_close = []
        
        for pos_id, position in self.positions.items():
            current_price = current_prices.get(position.instrument_key)
            if not current_price:
                continue
            
            # Update live option price on the position
            position.current_price = current_price
            
            # Update trailing stop
            position.update_trailing_stop(current_price)
            
            # Check if should exit
            should_exit, reason = position.should_exit(current_price, current_time)
            if should_exit:
                positions_to_close.append((pos_id, current_price, reason))
        
        # Close positions that triggered exit
        for pos_id, exit_price, reason in positions_to_close:
            trade = self.close_position(pos_id, exit_price, reason)
            if trade:
                closed_trades.append(trade)
        
        return closed_trades
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        return [pos.to_dict() for pos in self.positions.values()]
    
    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len(self.positions)
    
    def calculate_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate total unrealized P&L for all positions."""
        total_pnl = 0.0
        for position in self.positions.values():
            current_price = current_prices.get(position.instrument_key)
            if current_price:
                pnl = (current_price - position.entry_price) * position.quantity
                total_pnl += pnl
        return total_pnl
