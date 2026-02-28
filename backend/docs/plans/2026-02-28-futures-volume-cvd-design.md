# Nifty 50 Futures Volume + Cumulative Volume Delta (CVD)

**Date**: 2026-02-28
**Status**: Approved

## Goal

Add a real-time Nifty 50 futures-based volume strip with cumulative volume delta (CVD) to the main dashboard, positioned below the chart area and always visible.

## Architecture: Dedicated FuturesVolumeTracker

A new `FuturesVolumeTracker` class handles futures volume ingestion, 1-minute candle building, buy/sell delta classification, and CVD accumulation. It piggybacks on the existing Upstox V3 WebSocket (no new connection).

## Backend

### Futures Instrument Discovery

At startup, `MarketDataManager` looks up the near-month Nifty futures contract from the instruments CSV:
- Filter: `instrument_type == 'FUTIDX'`, `name == 'NIFTY'`, nearest expiry
- Result: instrument key like `NSE_FO|<token>`
- Added to the existing `instrument_keys` subscription list in `_start_streamer_logic()`

### FuturesVolumeTracker (`app/core/futures_volume.py`)

**Responsibilities**:
- Receives tick updates from `_on_streamer_message` when key matches futures instrument
- Builds 1-minute volume candles with buy/sell classification using the uptick/downtick rule:
  - LTP > previous LTP: tick volume classified as "buy"
  - LTP < previous LTP: tick volume classified as "sell"
  - LTP == previous LTP: use previous direction
- Computes delta per candle: `buy_volume - sell_volume`
- Accumulates CVD: running sum of all deltas since market open (9:15 AM IST)
- Stores rolling window of candle data (max ~375 candles for full trading day)
- Resets at 9:15 AM IST each day

**Data structure**:
```python
{
    "futures_volume": {
        "instrument_key": "NSE_FO|...",
        "futures_ltp": 24150.5,
        "candles": [
            {
                "time": "09:15",
                "timestamp": 1709096100,
                "total_volume": 12500,
                "buy_volume": 7200,
                "sell_volume": 5300,
                "delta": 1900,
                "cvd": 1900
            }
        ],
        "current_cvd": 15200,
        "current_delta": 800,
        "total_volume": 450000
    }
}
```

### Integration Points

1. **MarketDataManager**: Add futures key to subscription, route futures ticks to `FuturesVolumeTracker.on_tick()`
2. **DataFetcher**: New method `get_futures_instrument_key()` to find nearest futures contract
3. **TradingBot.get_status()**: Add `futures_volume` to status dict from tracker's `get_snapshot()`
4. **main.py**: Initialize `FuturesVolumeTracker` and wire it into `MarketDataManager`

## Frontend

### FuturesVolumeStrip Component

**Location**: `src/features/market/FuturesVolumeStrip.tsx`

**Placement**: Below chart panel in the left column (between chart and IndicatorStrip), always visible.

**Layout** (~160px tall, `surface-elevated` card):
- Header: "NIFTY FUTURES VOLUME" + current CVD value + total session volume + futures LTP
- Chart area: Dual-layer SVG:
  - Layer 1: Volume bars per 1-min candle, colored green (delta > 0) or red (delta < 0)
  - Layer 2: CVD polyline overlay showing cumulative delta trend
- X-axis: Time labels (09:15, 09:30, etc.)

**Rendering**: Pure SVG (same approach as existing PriceChart.tsx), no new charting library.

**Data flow**: `useGetStatusQuery()` -> `status.futures_volume` -> prop to `<FuturesVolumeStrip>`

### Dashboard Integration

Add `<FuturesVolumeStrip>` in `Dashboard.tsx` within the left column, after the chart card and before IndicatorStrip.

## Files to Create/Modify

### New Files
- `backend/app/core/futures_volume.py` - FuturesVolumeTracker class
- `frontend/src/features/market/FuturesVolumeStrip.tsx` - Volume + CVD component

### Modified Files
- `backend/app/data/data_fetcher.py` - Add `get_futures_instrument_key()`
- `backend/app/core/market_data.py` - Subscribe to futures, route ticks
- `backend/main.py` - Initialize tracker, add to status
- `frontend/src/Dashboard.tsx` - Add FuturesVolumeStrip to layout
- `frontend/src/types/api.ts` - Add FuturesVolume TypeScript types

## Non-Goals

- No VWAP or volume profile (keep focused)
- No intelligence module integration (can be added later)
- No historical data backfill (starts fresh each session)
