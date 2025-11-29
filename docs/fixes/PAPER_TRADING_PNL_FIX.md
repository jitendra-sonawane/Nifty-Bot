# Paper Trading Daily P&L Fix

## Issue
Daily profit and loss was not updating in paper trading mode. The system was only showing unrealized P&L from open positions, not the realized P&L from closed trades.

## Root Cause
The paper trading system used `PaperTradingManager` to manage positions and orders, but closed trades were not being tracked for P&L calculation. The `daily_pnl` in `RiskManager` was only updated when positions were closed through `position_manager.check_exits()`, which wasn't used for paper trading mode.

## Solution

### 1. **Enhanced PaperTradingManager** (`backend/paper_trading.py`)
- Added `daily_realized_pnl` tracking for realized P&L from closed trades
- Added `last_reset_date` to auto-reset daily P&L at start of each trading day
- Added `_reset_daily_pnl()` method to handle daily resets
- Modified `_update_positions()` to:
  - Calculate realized P&L when positions are closed (SELL orders)
  - Track closed trades in `data["closed_trades"]` with full P&L details
  - Update `daily_realized_pnl` when trades close
  - Log each closed trade with P&L information
- Added new methods:
  - `get_daily_realized_pnl()` - Returns realized P&L from closed trades for the day
  - `get_closed_trades()` - Returns all closed trades from current session
  - `get_total_pnl()` - Returns combined realized + unrealized P&L

### 2. **Updated Backend Status** (`backend/main.py`)
- Added `paper_daily_pnl` field in `get_status()` method
- Retrieves realized P&L using `self.order_manager.paper_manager.get_daily_realized_pnl()`
- Returns both `paper_pnl` (unrealized) and `paper_daily_pnl` (realized) to frontend

### 3. **Updated Frontend Type Definition** (`frontend/src/apiSlice.ts`)
- Added optional `paper_daily_pnl?: number` field to `StatusResponse` interface
- Allows frontend to receive and display realized daily P&L data

### 4. **Enhanced Dashboard Display** (`frontend/src/Dashboard.tsx`)
- Updated Daily P&L card to show:
  - **Realized P&L**: P&L from closed trades
  - **Unrealized P&L**: P&L from open positions
- Fallback to unrealized P&L if realized P&L is not available
- Color-coded green for profit, red for loss

## How It Works

### When a position is SOLD (closed):
1. P&L is calculated: `(exit_price - entry_price) × quantity`
2. `daily_realized_pnl` is updated with the realized P&L
3. Trade details are stored in `data["closed_trades"]`
4. Console logs: "💰 Paper Trade Closed: P&L ₹X.XX (Y%) | Daily Total: ₹Z.ZZ"

### Daily Reset:
- At start of each new day, `daily_realized_pnl` automatically resets to 0
- Called via `_reset_daily_pnl()` whenever P&L is queried
- Compares current date with `last_reset_date`

## Data Structure

### Closed Trade Object:
```json
{
  "instrument_key": "NSE_FO|NIFTY25NOV26050CE",
  "entry_price": 150.50,
  "exit_price": 175.25,
  "quantity": 10,
  "pnl": 247.50,
  "pnl_pct": 16.35,
  "entry_time": "2025-11-24T10:30:45.123456",
  "exit_time": "2025-11-24T11:15:30.654321",
  "reason": "PAPER_TRADE_CLOSE"
}
```

## Testing
To test the fix:
1. Start paper trading
2. Place a BUY order
3. Place a SELL order to close the position
4. Check the Daily P&L on the Dashboard
5. Should display realized P&L from the closed trade
6. Verify it resets at the start of next trading day

## Benefits
- ✅ Accurate daily P&L tracking for paper trading
- ✅ Realized vs Unrealized P&L visibility
- ✅ Automatic daily reset at market open
- ✅ Complete trade history with P&L details
- ✅ Consistent with real trading mode tracking
