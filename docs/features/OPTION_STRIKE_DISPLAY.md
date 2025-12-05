# Option Strike Display on Dashboard

**Date**: 2025-12-01  
**Feature**: Display recommended option strike on dashboard cards

## Changes Made

### 1. **Enhanced Greeks Panel** ([GreeksPanel.tsx](file:///Users/jitendrasonawane/Workpace/frontend/src/GreeksPanel.tsx))

Made the ATM strike and expiry more prominent:
- **Larger font size** - Strike now displays at 2xl (₹23500)
- **Better visual hierarchy** - Bordered boxes with labels
- **Clear labeling** - "At-The-Money" and "Next Expiry" subtitles
- **Improved contrast** - Purple/blue borders for quick identification

**Before**: Small text in header  
**After**: Large, prominent display with 2xl font size

### 2. **Signal Card Enhancement** ([MetricsGrid.tsx](file:///Users/jitendrasonawane/Workpace/frontend/src/components/dashboard/MetricsGrid.tsx))

Added target strike display when showing BUY signals:
- **Automatic display** - Shows when signal is `BUY_CE` or `BUY_PE`
- **Strike + Type** - Shows both strike price (₹23500) and option type (CE/PE
)
- **Visual badge** - Purple-themed badge with border
- **Compact design** - Fits cleanly in signal card

## User Experience

### **When BUY_CE Signal**
```
Signal Card shows:
┌─────────────────┐
│ BUY_CE         │  ← Green text
│ Target Strike: │  ← Purple badge
│ ₹23500 CE      │  ← Strike + Type
│ ST↑ RSI70...   │  ← Reason
└─────────────────┘
```

### **Greeks Panel Display**
```
┌───────────────────────┐
│ Option Analysis       │
├──────────┬────────────┤
│ ATM STRIKE│  EXPIRY   │
│  ₹23500  │ 2025-12-05│  ← Large text
│At-The-Money│Next Expiry│
├──────────────────────┤
│ Call Options (CE)     │
│ Greeks...             │
└────────────────────────┘
```

## Benefits

✅ **Clear Recommendation** - Users immediately see which strike to trade  
✅ **No Confusion** - Strike displayed at multiple locations  
✅ **Better Decisions** - Quick identification of ATM options  
✅ **Visual Hierarchy** - Large text catches attention  

## Technical Details

### Data Source
- Backend sends `atm_strike` in `strategy_data.greeks`
- Calculated as: `round(spot_price / 50) * 50`
- Updates every 5 seconds with market data

### Display Logic
```tsx
{(signal === 'BUY_CE' || signal === 'BUY_PE') && status?.strategy_data?.greeks?.atm_strike && (
    <div className="...">
        Target Strike: ₹{status.strategy_data.greeks.atm_strike} {signal === 'BUY_CE' ? 'CE' : 'PE'}
    </div>
)}
```

## Future Enhancements

Could add:
- OTM strike options (±1, ±2 strikes)
- Premium prices for each strike
- Strike selection dropdown
- Multiple expiry comparison
