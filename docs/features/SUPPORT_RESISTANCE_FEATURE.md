# Support & Resistance + Breakout Detection Feature

## Overview
Added intelligent support/resistance level detection and breakout analysis to the NiftyBot trading system. These features are now calculated in real-time and displayed on the dashboard.

## Backend Implementation

### Strategy Engine (`strategy.py`)

#### 1. `calculate_support_resistance(df, window=20)`
Identifies key price levels where price has historically reversed:

**What it does:**
- Analyzes the last 100 candles to find local highs and lows
- Identifies pivot points (local extremes with higher/lower bars on both sides)
- Calculates nearest support (highest level below current price)
- Calculates nearest resistance (lowest level above current price)
- Returns distance percentages from current price

**Returns:**
```python
{
    'support_levels': [list of 5 key support levels],
    'resistance_levels': [list of 5 key resistance levels],
    'nearest_support': 26100.50,  # Closest support below price
    'nearest_resistance': 26400.75,  # Closest resistance above price
    'support_distance_pct': 0.85,  # % away from current price
    'resistance_distance_pct': 1.20,  # % away from current price
    'current_price': 26250.00
}
```

**Key Features:**
- Uses local pivot identification (not just highs/lows of period)
- Includes highest high and lowest low in recent history
- Automatically sorted and deduplicated
- Distance percentages show how far price needs to move to reach levels

#### 2. `detect_breakout(df, sensitivity=0.015)`
Identifies when price breaks out above resistance or below support:

**What it does:**
- Monitors price against the highest high and lowest low from last 50 candles
- Detects breakouts with configurable sensitivity threshold (default 1.5%)
- Calculates the strength of the breakout as a percentage

**Returns:**
```python
{
    'is_breakout': True,
    'breakout_type': 'UPSIDE',  # or 'DOWNSIDE' or None
    'breakout_level': 26400.00,  # Price level being broken
    'strength': 2.45  # Percentage move beyond the level
}
```

**Key Features:**
- UPSIDE: Price breaks above highest high of last 50 candles + sensitivity
- DOWNSIDE: Price breaks below lowest low of last 50 candles - sensitivity
- Strength shows aggressive/weak breakouts
- Useful for identifying momentum trades

#### 3. Strategy Signal Integration
Both calculations are now included in the `check_signal()` response:
- Passed with every strategy analysis
- Accessible in the main signal decision reason
- Real-time updates as new candle data arrives

## Frontend Implementation

### New Component: `SupportResistance.tsx`

**Visual Display Features:**

1. **Current Price Header**
   - Shows latest price prominently
   - Located at top of component

2. **Breakout Alert** (Conditional)
   - Shows when price is breaking out
   - Color-coded: Green for UPSIDE, Red for DOWNSIDE
   - Displays breakout level and strength percentage
   - Alert icon for visual prominence

3. **Resistance Section** (Red theme)
   - Nearest resistance with distance percentage
   - Top 2 other resistance levels
   - Downtrend icon for visual identification

4. **Support Section** (Green theme)
   - Nearest support with distance percentage
   - Top 2 other support levels
   - Uptrend icon for visual identification

5. **Target Zone Card** (Blue theme)
   - Shows both nearest support and resistance
   - Displays the range between them
   - Helps identify safe trading zones

**Component Props:**
```typescript
interface SupportResistanceProps {
    supportResistance?: SupportResistanceData;
    breakout?: BreakoutData;
}
```

**Styling:**
- Responsive design with dark theme
- Color-coded sections (Red/Green/Blue)
- Icons from lucide-react
- Compact layout for sidebar placement

### Dashboard Integration

**Location:** Right sidebar, between System Control and Market Sentiment

**Data Flow:**
```
Backend (check_signal) 
  → API Response (strategy_data)
  → Redux (StatusResponse) 
  → Dashboard (strategyData prop)
  → SupportResistance Component
```

**Updates:**
- API interface updated (`apiSlice.ts`)
- New TypeScript interfaces for support_resistance and breakout data
- Dashboard component passes data to SupportResistance

## Usage in Trading

### Support/Resistance Levels
- **Entry Points:** Price tends to reverse at these levels
- **Stop Loss:** Place below support or above resistance
- **Take Profit:** Target the next resistance/support level
- **Risk/Reward:** Calculate from distance percentages

### Breakout Detection
- **Strong Breakouts (>2%):** Price breaking with momentum
- **Weak Breakouts (<1%):** Price barely breaking through
- **Trade Confirmation:** Can confirm trend continuation trades
- **False Breakout Alert:** Watch for price returning within range

## Technical Details

### Calculation Method
- **Support/Resistance:** Pivot point identification + historical high/low analysis
- **Lookback Period:** 100 candles for levels, 50 candles for breakout detection
- **Sensitivity:** 1.5% default (configurable) for breakout confirmation
- **Real-time Updates:** Recalculated with each new candle

### Performance
- Minimal computational overhead
- Uses existing pandas operations
- Runs alongside other indicators
- No additional API calls required

### Accuracy
- Based on local pivot highs/lows (not just period extremes)
- Includes highest high and lowest low for completeness
- Distance percentages help identify major vs minor levels
- Breakout detection accounts for noise with sensitivity threshold

## Future Enhancements

1. **Dynamic Levels:** Update support/resistance based on market structure
2. **Level Strength:** Track how many times each level was tested
3. **Clustering:** Group levels that are very close together
4. **Alerts:** Notify user when price approaches key levels
5. **Strategy Rules:** Add support/resistance conditions to BUY_CE/BUY_PE logic
6. **Historical Analysis:** Store level breaks for pattern analysis
7. **Multi-timeframe:** Show levels from different timeframes
8. **Volume Analysis:** Incorporate volume at support/resistance levels

## Files Modified

**Backend:**
- `/backend/strategy.py` - Added 2 new methods + integration in check_signal()

**Frontend:**
- `/frontend/src/SupportResistance.tsx` - New component (created)
- `/frontend/src/Dashboard.tsx` - Imported and integrated component
- `/frontend/src/apiSlice.ts` - Updated TypeScript interfaces
