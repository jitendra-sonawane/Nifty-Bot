# EMA Calculation Analysis Report

## Summary
The EMA calculation in your trading bot is **working correctly**. Both the pandas `ewm()` method and manual calculation produce identical results.

## Key Findings

### 1. API Data Verification ✅
- **Data Source**: Upstox API (NSE_INDEX|Nifty 50)
- **Interval**: 1-minute candles
- **Data Points**: 750 candles fetched successfully
- **Date Range**: 2025-11-27 to 2025-11-28
- **Data Quality**: No NaN values, all OHLCV data valid

### 2. EMA Calculation Verification ✅
**Current Values (Last Candle):**
- Close Price: 26204.55
- EMA 5: 26205.4091
- EMA 20: 26203.8759

**Calculation Method:**
```python
ema_5 = close.ewm(span=5, adjust=False).mean()
ema_20 = close.ewm(span=20, adjust=False).mean()
```

**Verification Results:**
- Pandas ewm() vs Manual calculation difference: < 0.0001 (negligible)
- Both methods produce identical results
- No NaN values in EMA calculations

### 3. Crossover Detection ✅
**Current Status:**
- Previous candle: EMA5 (26205.84) > EMA20 (26203.80) ✓
- Current candle: EMA5 (26205.41) > EMA20 (26203.88) ✓
- **Status**: Bullish trend maintained, no crossover detected

**Crossover Logic:**
```python
bullish_crossover = (prev_ema_5 <= prev_ema_20) and (curr_ema_5 > curr_ema_20)
bearish_crossover = (prev_ema_5 >= prev_ema_20) and (curr_ema_5 < curr_ema_20)
```

## Potential Issues to Check

### 1. **API Interval Mismatch** ⚠️
**Issue Found**: Your code uses `"5minute"` interval, but Upstox API only supports:
- `1minute`
- `30minute`
- `day`
- `week`
- `month`

**Location**: `backend/app/strategies/strategy.py` and `backend/app/core/strategy_runner.py`

**Fix Required**: Change from `"5minute"` to `"1minute"` or `"30minute"`

### 2. **Date Format Issue** ⚠️
**Issue Found**: The API expects `yyyy-mm-dd` format, but code uses `dd-mm-yyyy`

**Location**: `backend/app/data/data_fetcher.py` - `get_historical_data()` method

**Current Code**:
```python
to_date = datetime.now().strftime("%d-%m-%Y")  # Wrong format
from_date = (datetime.now() - timedelta(days=5)).strftime("%d-%m-%Y")
```

**Should Be**:
```python
to_date = datetime.now().strftime("%Y-%m-%d")  # Correct format
from_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
```

### 3. **Data Consistency** ✅
- Volume data is 0 (expected for index instruments)
- OI data is 0 (expected for index instruments)
- Close prices are valid and consistent

## Recommendations

### Priority 1: Fix API Interval
Update all references to use supported intervals:
```python
# Instead of:
df = fetcher.get_historical_data(nifty_key, "5minute", from_date, to_date)

# Use:
df = fetcher.get_historical_data(nifty_key, "1minute", from_date, to_date)
# or
df = fetcher.get_historical_data(nifty_key, "30minute", from_date, to_date)
```

### Priority 2: Fix Date Format
Update date formatting in `data_fetcher.py`:
```python
def get_historical_data(self, instrument_key, interval, from_date, to_date):
    # Ensure dates are in yyyy-mm-dd format
    if isinstance(from_date, str):
        from_date = datetime.strptime(from_date, "%d-%m-%Y").strftime("%Y-%m-%d")
    if isinstance(to_date, str):
        to_date = datetime.strptime(to_date, "%d-%m-%Y").strftime("%Y-%m-%d")
```

### Priority 3: Add Validation
Add validation for supported intervals:
```python
SUPPORTED_INTERVALS = ["1minute", "30minute", "day", "week", "month"]
if interval not in SUPPORTED_INTERVALS:
    raise ValueError(f"Interval {interval} not supported. Use: {SUPPORTED_INTERVALS}")
```

## EMA Calculation Details

### Formula Used (Exponential Moving Average)
```
Multiplier = 2 / (Period + 1)
EMA = (Current Price × Multiplier) + (Previous EMA × (1 - Multiplier))
```

### For EMA 5:
- Multiplier = 2 / (5 + 1) = 0.3333
- First EMA = SMA of first 5 values
- Subsequent EMAs use the formula above

### For EMA 20:
- Multiplier = 2 / (20 + 1) = 0.0952
- First EMA = SMA of first 20 values
- Subsequent EMAs use the formula above

## Test Results

| Metric | Result |
|--------|--------|
| Data Fetched | ✅ 750 candles |
| EMA 5 Calculation | ✅ Correct |
| EMA 20 Calculation | ✅ Correct |
| Crossover Detection | ✅ Working |
| NaN Values | ✅ None |
| Pandas vs Manual Diff | ✅ < 0.0001 |

## Conclusion

Your EMA calculation logic is **mathematically correct**. The issue is likely:
1. **API interval not supported** - "5minute" doesn't exist
2. **Date format mismatch** - API expects yyyy-mm-dd, code sends dd-mm-yyyy

Once these are fixed, the strategy should work correctly with real market data.

## Files to Update

1. **backend/app/data/data_fetcher.py**
   - Fix date format in `get_historical_data()`
   - Add interval validation

2. **backend/app/core/strategy_runner.py**
   - Update interval from "5minute" to "1minute" or "30minute"

3. **backend/app/strategies/strategy.py**
   - No changes needed (calculation is correct)

4. **backend/app/core/market_data.py**
   - Update any hardcoded intervals
