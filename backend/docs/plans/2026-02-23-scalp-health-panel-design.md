# Scalp Health Panel — Design Document

**Date:** 2026-02-23
**Status:** Approved
**Approach:** Backend-Computed Intelligence Module (Approach 1)

## Overview

A new "Scalp Health" tab in the dashboard's BottomTabs that provides real-time health indicators for intraday options scalping. Supports both 0 DTE and weekly expiries with DTE-adaptive thresholds. Focused on gamma scalping and momentum/directional scalping styles.

The backend computes all metrics via a new `ScalpHealthModule` plugged into the existing `IntelligenceEngine`. Data flows through the existing `/ws/status` WebSocket. The frontend adds a new BottomTab to display the metrics.

---

## Architecture

```
ScalpHealthModule (app/intelligence/scalp_health.py)
    ├── Reads from: MarketDataManager (prices, Greeks, OI)
    ├── Reads from: GreeksCalculator (Black-Scholes computations)
    ├── Reads from: OIAnalysisModule (buildup signals, max pain)
    ├── Reads from: OrderBookModule (bid-ask spread)
    ├── Reads from: OptionChainManager (ATM strike, chain data)
    └── Outputs: ScalpHealthContext → intelligence["scalp_health"]
                                    → streamed via /ws/status
```

Registered in `IntelligenceEngine` alongside existing modules. Togglable via `/intelligence/toggle`.

---

## 1. Composite Scalp Health Score (0-100)

Single headline metric. Weighted sum of sub-scores, with weights that adapt based on DTE.

### Weights

| Component         | Base Weight | 0 DTE Weight | 3-5 DTE Weight |
|-------------------|-------------|--------------|-----------------|
| Greeks Quality    | 30%         | 35%          | 25%             |
| OI Confirmation   | 25%         | 20%          | 30%             |
| Time/Decay        | 20%         | 25%          | 15%             |
| Liquidity         | 15%         | 15%          | 15%             |
| Market Context    | 10%         | 5%           | 15%             |

### Score Bands

| Range  | Label   | Meaning                                                    |
|--------|---------|------------------------------------------------------------|
| 80-100 | Prime   | High gamma, confirmed OI, tight spreads — ideal scalp      |
| 60-79  | Good    | Most sub-scores healthy, minor concerns                    |
| 40-59  | Caution | Some metrics unfavorable (wide spreads, conflicting OI)    |
| 0-39   | Avoid   | Poor conditions (low gamma, no liquidity, adverse theta)   |

---

## 2. Greeks Metrics (10 indicators)

### Gamma Cluster (Primary)

1. **Gamma Exposure (GEX) in ₹**
   - Formula: `gamma × spot² × 0.01 × lot_size`
   - Rupee P&L change per 1% spot move
   - Thresholds: >₹3,000 (High/Green), ₹1,000-3,000 (Medium/Amber), <₹1,000 (Low/Red)

2. **ATM Proximity Score (0-100)**
   - Formula: `100 - (abs(spot - atm_strike) / strike_step × 100)`
   - Clamped to [0, 100]
   - >80 = Green (peak gamma zone), 50-80 = Amber, <50 = Red

3. **Gamma/Theta Ratio**
   - Formula: `gamma / abs(theta)`
   - Efficiency metric: delta-move earnings vs time-decay cost
   - >2.0 = Green (gamma dominates), 1.0-2.0 = Amber, <1.0 = Red (theta eating your edge)

4. **Delta Flip Zone**
   - Price level where CE delta = 0.50 (or PE delta = -0.50)
   - Computed from ATM strike ± interpolation from Greeks
   - Display: price level + distance from spot in points

### Delta & Direction

5. **CE Delta / PE Delta**
   - ATM option deltas, streamed from existing Greeks data
   - Display: side-by-side with directional arrow

6. **Delta per ₹**
   - Formula: `delta / option_premium`
   - Capital efficiency: directional leverage per rupee spent
   - Higher = better for momentum scalps

### Volatility

7. **IV vs Realized Vol Spread**
   - Formula: `ATM_IV - HV_5d` (5-day historical volatility from ATR)
   - Positive = premiums rich (overpriced options)
   - Negative = premiums cheap (underpriced options)
   - For option buyers: negative spread is favorable

8. **Vega Risk**
   - ATM vega value
   - High vega near events = vol sensitivity risk/opportunity
   - Display: value + "Low/Medium/High" risk label

### DTE-Adaptive

9. **Theta per Minute**
   - Formula: `daily_theta / trading_minutes_remaining`
   - Real-time holding cost clock
   - On 0 DTE this is extreme; on 3+ DTE it's negligible
   - Red if cost > 0.5% of premium per minute

10. **Gamma Peak Indicator**
    - Boolean: `DTE ≤ 1 AND abs(spot - ATM) ≤ 1 × strike_step`
    - When true: you're in maximum-gamma territory
    - Display: YES (highlighted) or NO

---

## 3. OI & Volume Metrics (9 indicators)

### OI Buildup & Direction

1. **OI Buildup Signal**
   - Reuses existing `oi_analysis.buildup_signal`
   - Values: LONG_BUILDUP, SHORT_BUILDUP, SHORT_COVERING, LONG_UNWINDING, NEUTRAL
   - Color-coded: green (bullish), red (bearish), amber (ambiguous)

2. **Real-time OI Change (CE & PE)**
   - Absolute OI change since market open for ATM ± 1 strike
   - Positive = fresh positions. Negative = unwinding.
   - Display: +5,200 CE / -1,800 PE with arrows

3. **OI Change Rate**
   - Formula: `OI_change / minutes_since_open`
   - Spike detection: rate > 2× average triggers "aggressive positioning" flag
   - Display: lots/minute with trend arrow

### Support/Resistance Walls

4. **Max OI Strikes (CE & PE)**
   - Reuses existing `oi_analysis` data
   - Display: strike price + OI value + distance from spot

5. **Max Pain Strike**
   - Reuses existing computation
   - Display: strike + distance from spot + "magnetic pull" strength indicator

6. **OI Concentration Index (0-100)**
   - Formula: `(OI at top 3 strikes / total_OI) × 100`
   - >70 = strong walls (range-bound likely), <30 = no clear walls (breakout likely)
   - Informs gamma vs directional scalp choice

### Volume & Flow

7. **Volume/OI Ratio (CE & PE)**
   - Today's volume / total OI
   - >1.0 = heavy fresh activity (momentum signal)
   - <0.3 = stale positions, less conviction

8. **PCR Trend Direction**
   - Computed from PCR snapshots over last 15 minutes
   - Values: RISING (more puts), FALLING (more calls), STABLE
   - Augments existing PCR value with directionality

9. **Unwinding Alert**
   - Triggers when OI drops >10% at a key support/resistance strike within 5 minutes
   - Signals a wall breaking — potential breakout catalyst
   - Display: strike + "UNWINDING" badge (red alert) or "—" when inactive

---

## 4. Liquidity & Execution Quality (3 indicators)

1. **Bid-Ask Spread (CE & PE)**
   - Reuses existing `order_book` module data
   - Display: percentage + Excellent/Good/Poor label
   - Thresholds: <0.3% (Excellent), <1.0% (Good), >1.0% (Poor)

2. **Effective Spread**
   - Formula: `(bid_ask_spread × 0.5) + slippage_estimate`
   - Slippage estimate: `(order_size / avg_5min_volume) × spread`
   - Estimated real execution cost per lot

3. **Lot Liquidity Score (0-100)**
   - Based on lots traded in last 5 minutes at ATM strike
   - >50 lots/5min = 100, <5 lots/5min = 0 (linear interpolation)
   - Tells you if you can enter/exit at desired size

---

## 5. Market Context (4 indicators)

1. **Market Regime**
   - Reuses existing `market_regime` module
   - Adds scalp recommendation: Trending → directional scalps, Ranging → gamma scalps

2. **VIX Level + Trend**
   - Current India VIX with direction (↑/↓/→)
   - >18 = high vol (good for scalps), <12 = low vol (harder to scalp)

3. **Intraday Momentum Score**
   - Formula: `(current_price - day_open) / ATR × 100`
   - >80% = most of daily range consumed, <30% = room to run
   - Helps decide if a directional move has more legs

4. **Time-of-Day Factor**
   - 9:15-10:00 → "Peak" (opening volatility)
   - 10:00-14:00 → "Low" (mid-day consolidation)
   - 14:00-15:30 → "Moderate" (closing activity)
   - Display: zone name + minutes until next zone transition

---

## 6. Frontend Layout

New **"Scalp Health"** tab in BottomTabs (lazy-loaded, same pattern as Intelligence tab).

```
┌───────────────────────────────────────────────────────────────┐
│  SCALP HEALTH SCORE: 78/100  ████████████░░░░  [GOOD]        │
│  DTE: 0d 3h 22m  │  Gamma Peak: YES  │  Regime: TRENDING     │
├───────────────────┬───────────────────┬───────────────────────┤
│  GREEKS           │  OI & FLOW        │  LIQUIDITY + CONTEXT  │
│                   │                   │                       │
│  GEX: ₹2,340     │  Signal:          │  Spread CE: 0.2% ✓   │
│  ATM Prox: 92     │   LONG_BUILDUP    │  Spread PE: 0.4% ✓   │
│  γ/θ Ratio: 3.2  │  OI Chg CE: +5.2K │  Lot Liq: 85/100     │
│  Delta Flip:      │  OI Chg PE: -1.8K │                       │
│   24,850 (12pts)  │  OI Rate: 42/min  │  VIX: 14.2 ↑         │
│  CE δ: 0.52      │  Max Pain: 24,800 │  Momentum: 45%        │
│  PE δ: -0.48     │  Max OI CE: 25,000│  Time: Peak (42m)     │
│  δ/₹: 0.008      │  Max OI PE: 24,500│  Regime: TRENDING     │
│  IV-HV: +2.1%    │  Conc: 65/100     │   → Directional scalps│
│  Vega: 4.2       │  Vol/OI: 1.3      │                       │
│  θ/min: -₹0.12   │  PCR Trend: ↑     │                       │
│  Peak: YES        │  Unwinding: —     │                       │
└───────────────────┴───────────────────┴───────────────────────┘
```

### Color Coding
- Each metric has green/amber/red indicator based on thresholds defined above
- Composite score bar uses gradient: red → amber → green
- Gamma Peak "YES" gets a highlight/glow effect

### Responsive
- Desktop: 3-column layout
- Mobile: stacked cards (Score → Greeks → OI → Liquidity/Context)

---

## 7. Data Model

### Backend: ScalpHealthContext

```python
@dataclass
class ScalpHealthContext:
    # Composite
    score: int                      # 0-100
    score_band: str                 # "PRIME" | "GOOD" | "CAUTION" | "AVOID"
    sub_scores: Dict[str, int]      # {"greeks": 85, "oi": 72, ...}

    # DTE
    dte_days: int
    dte_hours: int
    dte_minutes: int
    expiry_date: str

    # Greeks
    gex_rupees: float
    atm_proximity: int              # 0-100
    gamma_theta_ratio: float
    delta_flip_price: float
    delta_flip_distance: float      # points from spot
    ce_delta: float
    pe_delta: float
    delta_per_rupee_ce: float
    delta_per_rupee_pe: float
    iv_hv_spread: float             # percentage points
    vega_risk: float
    vega_risk_label: str            # "LOW" | "MEDIUM" | "HIGH"
    theta_per_minute: float
    gamma_peak: bool

    # OI
    oi_buildup_signal: str
    oi_change_ce: int
    oi_change_pe: int
    oi_change_rate: float           # lots/minute
    oi_rate_alert: bool             # spike detected
    max_oi_ce_strike: int
    max_oi_pe_strike: int
    max_pain_strike: int
    max_pain_distance: float
    oi_concentration: int           # 0-100
    volume_oi_ratio_ce: float
    volume_oi_ratio_pe: float
    pcr_trend: str                  # "RISING" | "FALLING" | "STABLE"
    unwinding_alert: Optional[Dict] # {strike, oi_drop_pct} or None

    # Liquidity
    spread_ce_pct: float
    spread_pe_pct: float
    spread_ce_label: str            # "EXCELLENT" | "GOOD" | "POOR"
    spread_pe_label: str
    effective_spread: float
    lot_liquidity_score: int        # 0-100

    # Market Context
    regime: str
    regime_scalp_recommendation: str
    vix_level: float
    vix_trend: str                  # "UP" | "DOWN" | "FLAT"
    intraday_momentum: float        # percentage of ATR consumed
    time_of_day_zone: str           # "PEAK" | "MODERATE" | "LOW"
    minutes_to_next_zone: int
```

### Frontend: TypeScript Interface

```typescript
interface ScalpHealthContext {
  score: number;
  score_band: 'PRIME' | 'GOOD' | 'CAUTION' | 'AVOID';
  sub_scores: Record<string, number>;

  dte_days: number;
  dte_hours: number;
  dte_minutes: number;
  expiry_date: string;

  // Greeks (10 metrics)
  gex_rupees: number;
  atm_proximity: number;
  gamma_theta_ratio: number;
  delta_flip_price: number;
  delta_flip_distance: number;
  ce_delta: number;
  pe_delta: number;
  delta_per_rupee_ce: number;
  delta_per_rupee_pe: number;
  iv_hv_spread: number;
  vega_risk: number;
  vega_risk_label: 'LOW' | 'MEDIUM' | 'HIGH';
  theta_per_minute: number;
  gamma_peak: boolean;

  // OI (9 metrics)
  oi_buildup_signal: string;
  oi_change_ce: number;
  oi_change_pe: number;
  oi_change_rate: number;
  oi_rate_alert: boolean;
  max_oi_ce_strike: number;
  max_oi_pe_strike: number;
  max_pain_strike: number;
  max_pain_distance: number;
  oi_concentration: number;
  volume_oi_ratio_ce: number;
  volume_oi_ratio_pe: number;
  pcr_trend: 'RISING' | 'FALLING' | 'STABLE';
  unwinding_alert: { strike: number; oi_drop_pct: number } | null;

  // Liquidity (3 metrics)
  spread_ce_pct: number;
  spread_pe_pct: number;
  spread_ce_label: 'EXCELLENT' | 'GOOD' | 'POOR';
  spread_pe_label: 'EXCELLENT' | 'GOOD' | 'POOR';
  effective_spread: number;
  lot_liquidity_score: number;

  // Market Context (4 metrics)
  regime: string;
  regime_scalp_recommendation: string;
  vix_level: number;
  vix_trend: 'UP' | 'DOWN' | 'FLAT';
  intraday_momentum: number;
  time_of_day_zone: 'PEAK' | 'MODERATE' | 'LOW';
  minutes_to_next_zone: number;
}
```

---

## 8. Files to Create/Modify

### Backend (New)
- `app/intelligence/scalp_health.py` — ScalpHealthModule class

### Backend (Modify)
- `app/intelligence/__init__.py` — Register ScalpHealthModule
- `app/core/models.py` — Add ScalpHealthContext dataclass
- `app/core/config.py` — Add scalp health thresholds/weights

### Frontend (New)
- `src/features/scalp-health/ScalpHealthTab.tsx` — Main tab component
- `src/features/scalp-health/ScalpHealthScore.tsx` — Composite score header
- `src/features/scalp-health/GreeksMetrics.tsx` — Greeks column
- `src/features/scalp-health/OIMetrics.tsx` — OI column
- `src/features/scalp-health/LiquidityContext.tsx` — Liquidity + context column

### Frontend (Modify)
- `src/types/api.ts` — Add ScalpHealthContext interface
- `src/Dashboard.tsx` — Add "Scalp Health" to BottomTabs
- `src/hooks/useDashboard.ts` — Extract scalp_health from intelligence context
