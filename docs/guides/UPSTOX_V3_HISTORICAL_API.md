# Upstox v3 Historical API Migration

## Overview
Upstox v3 Historical API provides extended interval support compared to v2, allowing for more granular time-series data analysis.

## API Versions Comparison

### v2 Historical API (Legacy)
- **Base URL**: `https://api.upstox.com/v2`
- **Endpoint**: `/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}`
- **Supported Intervals**: `1minute`, `30minute`, `day`, `week`, `month`
- **Status**: Still functional but limited

### v3 Historical API (Current)
- **Base URL**: `https://api.upstox.com/v3`
- **Endpoint**: `/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}`
- **Supported Intervals**: 
  - `1minute`
  - `5minute` ✨ NEW
  - `10minute` ✨ NEW
  - `15minute` ✨ NEW
  - `30minute`
  - `60minute` ✨ NEW
  - `day`
  - `week`
  - `month`
- **Status**: Recommended for new implementations

## Migration Changes

### Updated Code
The `DataFetcher` class now uses v3 API:

```python
# Before (v2)
self.base_url = "https://api.upstox.com/v2"
SUPPORTED_INTERVALS = ['1minute', '30minute', 'day', 'week', 'month']

# After (v3)
self.base_url_v3 = "https://api.upstox.com/v3"
SUPPORTED_INTERVALS = ['1minute', '5minute', '10minute', '15minute', '30minute', '60minute', 'day', 'week', 'month']
```

### Method Signature
```python
def get_historical_data(self, instrument_key, interval, from_date, to_date):
    """
    Fetches historical candle data using Upstox v3 API.
    interval: '1minute', '5minute', '10minute', '15minute', '30minute', '60minute', 'day', 'week', 'month'
    from_date: 'YYYY-MM-DD' format
    to_date: 'YYYY-MM-DD' format
    """
```

## Usage Examples

### 5-Minute Candles
```python
df = data_fetcher.get_historical_data(
    'NSE_INDEX|Nifty 50',
    '5minute',
    '2024-01-01',
    '2024-01-31'
)
```

### 15-Minute Candles
```python
df = data_fetcher.get_historical_data(
    'NSE_FO|52910',  # NIFTY option
    '15minute',
    '2024-01-01',
    '2024-01-31'
)
```

### Hourly Candles
```python
df = data_fetcher.get_historical_data(
    'NSE_INDEX|Nifty 50',
    '60minute',
    '2024-01-01',
    '2024-01-31'
)
```

## Response Format
Both v2 and v3 return the same candle structure:
```json
{
  "data": {
    "candles": [
      [timestamp, open, high, low, close, volume, oi],
      ...
    ]
  }
}
```

## DataFrame Output
```python
df = data_fetcher.get_historical_data(...)
# Returns DataFrame with columns:
# - timestamp (index)
# - open
# - high
# - low
# - close
# - volume
# - oi (open interest)
```

## Benefits of v3

| Feature | v2 | v3 |
|---------|----|----|
| 1-minute candles | ✅ | ✅ |
| 5-minute candles | ❌ | ✅ |
| 10-minute candles | ❌ | ✅ |
| 15-minute candles | ❌ | ✅ |
| 30-minute candles | ✅ | ✅ |
| 60-minute candles | ❌ | ✅ |
| Daily candles | ✅ | ✅ |
| Weekly candles | ✅ | ✅ |
| Monthly candles | ✅ | ✅ |

## Other v3 APIs Used

Your bot already uses v3 for:
- **Option Greeks**: `https://api.upstox.com/v3/market-quote/option-greek`

## Backward Compatibility

The v2 API is still available for:
- Market quotes: `/market-quote/quotes`
- LTP (Last Traded Price): `/market-quote/ltp`
- Other market data endpoints

Your code maintains v2 for these endpoints while using v3 for historical data.

## Error Handling

The updated code includes:
- Interval validation against supported list
- Date format parsing (handles both DD-MM-YYYY and YYYY-MM-DD)
- Proper error logging with emoji indicators
- Timeout handling (30 seconds)
- Connection error handling

## Testing

To verify v3 API is working:

```python
from app.data.data_fetcher import DataFetcher

fetcher = DataFetcher(api_key, access_token)

# Test 5-minute interval
df = fetcher.get_historical_data(
    'NSE_INDEX|Nifty 50',
    '5minute',
    '2024-01-01',
    '2024-01-02'
)

if df is not None:
    print(f"✅ v3 API working! Got {len(df)} candles")
    print(df.head())
else:
    print("❌ v3 API failed")
```

## References

- Upstox API Documentation: https://upstox.com/developer/api-documentation
- Historical Data Endpoint: `/v3/historical-candle`
- Supported Intervals: Check official Upstox docs for latest updates
