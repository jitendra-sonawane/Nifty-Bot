# Upstox API Interval Format Fix

## Issue
The application was encountering a **400 Bad Request** error when fetching historical candle data from the Upstox v3 API:

```
ERROR - ❌ Error 400: {"status":"error","errors":[{"errorCode":"UDAPI100036","message":"Invalid input","propertyPath":"interval","invalidValue":"5minute",...}]}
```

## Root Cause
The Upstox v3 Historical Candle API expects the URL format:
```
/v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}
```

Where:
- `{unit}` should be one of: **`minutes`, `hours`, `days`, `weeks`, `months`** (PLURAL form)
- `{interval}` should be just the numeric value (e.g., `5`, not `5minute`)

The code was incorrectly constructing the URL as:
```python
url = f"{base_url_v3}/historical-candle/{encoded_key}/minute/{interval}/{to_date}/{from_date}"
```

With `interval = "5minute"`, this resulted in:
```
/v3/historical-candle/NSE_INDEX%7CNifty%2050/minute/5minute/2025-12-04/2025-11-29
```

Which had TWO errors:
1. Unit was singular (`minute`) instead of plural (`minutes`)
2. Interval value included the word "minute" (`5minute`) instead of just the number (`5`)

## Solution
Updated the `get_historical_data` method in `/backend/app/data/data_fetcher.py` to:

1. **Parse the interval string** to extract the unit and numeric value:
   ```python
   # Note: Upstox v3 API expects PLURAL units: minutes, hours, days, weeks, months
   if interval in ['day', 'week', 'month']:
       unit = interval + 's'  # Convert to plural: day -> days
       interval_value = '1'
   elif interval.endswith('minute'):
       unit = 'minutes'  # PLURAL
       interval_value = interval.replace('minute', '')
   elif interval.endswith('hour'):
       unit = 'hours'  # PLURAL
       interval_value = interval.replace('hour', '')
   ```

2. **Construct the URL correctly**:
   ```python
   url = f"{self.base_url_v3}/historical-candle/{encoded_key}/{unit}/{interval_value}/{to_date}/{from_date}"
   ```

3. **Updated SUPPORTED_INTERVALS** to include hour-based intervals:
   ```python
   SUPPORTED_INTERVALS = [
       '1minute', '5minute', '10minute', '15minute', '30minute', '60minute',
       '1hour', '2hour', '3hour', '4hour', '5hour',
       'day', 'week', 'month'
   ]
   ```

## Examples
| Input Interval | Parsed Unit | Parsed Value | Resulting URL Path |
|---------------|-------------|--------------|-------------------|
| `5minute` | `minutes` | `5` | `/minutes/5/` |
| `60minute` | `minutes` | `60` | `/minutes/60/` |
| `1hour` | `hours` | `1` | `/hours/1/` |
| `day` | `days` | `1` | `/days/1/` |
| `week` | `weeks` | `1` | `/weeks/1/` |

## Files Modified
- `/Users/jitendrasonawane/Workpace/backend/app/data/data_fetcher.py`
  - Updated `get_historical_data()` method (lines 192-265)
  - Updated `SUPPORTED_INTERVALS` constant (lines 26-31)

## Testing
The backend server has been restarted with the fix applied. The error should no longer occur when fetching historical data.

## Related Documentation
- [Upstox v3 Historical Candle API Documentation](https://upstox.com/developer/api-documentation/historical-candle-data)
- Supported intervals: 1-300 minutes, 1-5 hours, 1 day, 1 week, 1 month
