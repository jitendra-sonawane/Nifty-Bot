# Order Flow & Microstructure Analytics — Design

**Date:** 2026-03-02
**Status:** Approved
**Scope:** Backend analytics engine + Intelligence module filter + Frontend dashboard tab

---

## Goal

Add order flow and market microstructure analytics to QuantNifty. This provides:
1. **Signal confirmation** — an intelligence module filter that confirms/rejects strategy signals using order flow data.
2. **Visual analysis** — a dedicated "Order Flow" tab in the dashboard for discretionary decision-making.

## Metrics

| Metric | What It Shows | Source |
|--------|---------------|--------|
| **VWAP + Deviation Bands** | Institutional reference price. Price above VWAP = bullish bias. ±1σ bands for mean-reversion zones. | Futures tick data (LTP + LTQ) |
| **Delta Divergence Alerts** | CVD vs price divergence. Rising price + falling CVD = bearish reversal signal. | FuturesVolumeTracker candles + CVD |
| **Volume Profile (POC + Value Area)** | Where volume concentrates at each price level. POC = highest volume price. Value Area = 70% of volume range. | Futures tick data binned by price |
| **Order Book Imbalance** | Real-time bid/ask volume ratio from 5-level depth data. Detects directional pressure. | MarketDataManager.bid_ask_cache |

---

## Architecture

### Approach: Dedicated OrderFlowAnalyzer (Approach 2)

Clean separation between tick collection and analytics:

```
Tick Data ──> FuturesVolumeTracker ──> candles, CVD, delta
                    │
                    v
              OrderFlowAnalyzer ──> VWAP, volume profile, divergence, book imbalance
                    │
          ┌─────────┴──────────┐
          v                    v
  OrderFlowModule         OrderFlowTab
  (intelligence filter)   (frontend panel)
```

FuturesVolumeTracker stays focused on candle building + CVD.
OrderFlowAnalyzer owns all derived analytics.

---

## Backend Design

### New Files

| File | Purpose |
|------|---------|
| `backend/app/core/order_flow.py` | OrderFlowAnalyzer class — computes VWAP, volume profile, divergence, book imbalance |
| `backend/app/intelligence/order_flow_module.py` | Intelligence engine plugin — wraps analyzer for signal filtering |
| `backend/tests/test_order_flow.py` | Unit tests for OrderFlowAnalyzer |
| `backend/tests/test_order_flow_module.py` | Unit tests for OrderFlowModule |

### Modified Files

| File | Change |
|------|--------|
| `backend/main.py` | Create OrderFlowAnalyzer, register module, add to status |
| `backend/app/core/market_data.py` | Feed ticks + order book to OrderFlowAnalyzer |
| `backend/app/strategies/strategy.py` | Add `order_flow` filter to signal evaluation |

### OrderFlowAnalyzer Class

```python
class OrderFlowAnalyzer:
    """
    Computes order flow metrics from futures tick data and order book depth.
    Thread-safe — called from WebSocket background thread.
    Resets at market open (09:15 IST) each day.
    """

    def __init__(self, bin_size: float = 50.0, max_bins: int = 40):
        self._lock = threading.Lock()
        self._bin_size = bin_size          # Price bin width for volume profile
        self._max_bins = max_bins          # Max bins to retain

        # VWAP state
        self._cum_pv: float = 0.0         # Cumulative (price * volume)
        self._cum_vol: float = 0.0        # Cumulative volume
        self._cum_pv2: float = 0.0        # For deviation bands: Σ(vol * price²)

        # Volume profile: {price_bin: {"buy": float, "sell": float}}
        self._profile: Dict[float, Dict[str, float]] = {}

        # Order book
        self._book_bids: float = 0.0
        self._book_asks: float = 0.0

        # Delta divergence tracking
        self._recent_prices: List[float] = []   # Last N candle closes
        self._recent_cvds: List[float] = []     # Last N CVD values
        self._divergence_lookback: int = 8

        # Reset tracking
        self._last_reset_date: Optional[date] = None

    def on_tick(self, price: float, volume: float, direction: str, timestamp: float):
        """Process each tick. Called from FuturesVolumeTracker.on_tick()."""
        with self._lock:
            self._maybe_reset(timestamp)
            if volume <= 0:
                return

            # VWAP accumulation
            self._cum_pv += price * volume
            self._cum_vol += volume
            self._cum_pv2 += volume * price * price

            # Volume profile
            bin_key = round(price / self._bin_size) * self._bin_size
            if bin_key not in self._profile:
                self._profile[bin_key] = {"buy": 0.0, "sell": 0.0}
            self._profile[bin_key][direction] += volume

    def on_candle_close(self, candle_close: float, cvd: float):
        """Track candle closes for divergence detection."""
        with self._lock:
            self._recent_prices.append(candle_close)
            self._recent_cvds.append(cvd)
            if len(self._recent_prices) > self._divergence_lookback:
                self._recent_prices.pop(0)
                self._recent_cvds.pop(0)

    def update_order_book(self, bids: List[Dict], asks: List[Dict]):
        """Update order book state from 5-level depth data."""
        with self._lock:
            self._book_bids = sum(b.get("qty", 0) for b in bids)
            self._book_asks = sum(a.get("qty", 0) for a in asks)

    def get_snapshot(self) -> Dict:
        """Returns complete order flow state for API/frontend."""
        with self._lock:
            vwap = self._cum_pv / self._cum_vol if self._cum_vol > 0 else 0.0
            # Deviation: σ = sqrt(Σ(vol * price²) / Σ(vol) - vwap²)
            variance = (self._cum_pv2 / self._cum_vol - vwap * vwap) if self._cum_vol > 0 else 0.0
            std_dev = variance ** 0.5 if variance > 0 else 0.0

            # Volume profile sorted by price
            profile = sorted(
                [
                    {
                        "price": p,
                        "buy_vol": v["buy"],
                        "sell_vol": v["sell"],
                        "total": v["buy"] + v["sell"],
                    }
                    for p, v in self._profile.items()
                ],
                key=lambda x: x["price"],
            )

            # POC = bin with max total volume
            poc = max(profile, key=lambda x: x["total"])["price"] if profile else 0.0

            # Value Area = contiguous bins around POC containing 70% of total volume
            va_high, va_low = self._compute_value_area(profile, poc)

            # Book imbalance (0-1 scale, 0.5 = balanced)
            total_book = self._book_bids + self._book_asks
            imbalance = self._book_bids / total_book if total_book > 0 else 0.5

            # Delta divergence
            divergence = self._detect_divergence()

            return {
                "vwap": round(vwap, 2),
                "vwap_upper": round(vwap + std_dev, 2),
                "vwap_lower": round(vwap - std_dev, 2),
                "std_dev": round(std_dev, 2),
                "volume_profile": profile,
                "poc": poc,
                "value_area_high": va_high,
                "value_area_low": va_low,
                "book_imbalance": round(imbalance, 3),
                "bid_total": self._book_bids,
                "ask_total": self._book_asks,
                "delta_divergence": divergence,
                "total_volume": self._cum_vol,
            }
```

### VWAP Calculation

```
VWAP = Σ(Price × Volume) / Σ(Volume)
Upper Band = VWAP + σ   where σ = sqrt(Σ(Vol × Price²) / Σ(Vol) - VWAP²)
Lower Band = VWAP - σ
```

Resets at 09:15 IST each trading day.

### Volume Profile

- Nifty price range divided into 50-point bins (e.g., 24950, 25000, 25050)
- Each tick: volume added to the appropriate bin as buy or sell
- POC = bin with highest total volume
- Value Area: start from POC, expand outward (add next-highest bin) until 70% of total volume is enclosed

### Delta Divergence Detection

Compare last N candle closes vs CVD values:
- **Bearish**: price higher highs + CVD lower highs (strength = magnitude of CVD decline)
- **Bullish**: price lower lows + CVD higher lows (strength = magnitude of CVD rise)
- Lookback: 8 candles (configurable)
- Strength: 0.0 to 1.0 scale

### Order Book Imbalance

```
imbalance = Σ(bid_qty across 5 levels) / (Σ(bid_qty) + Σ(ask_qty))
```

- 0.5 = balanced
- > 0.6 = bid-heavy (bullish pressure)
- < 0.4 = ask-heavy (bearish pressure)

---

## Intelligence Module Design

### OrderFlowModule

```python
class OrderFlowModule:
    name = "order_flow"

    def analyze(self, context: dict) -> dict:
        snapshot = self.analyzer.get_snapshot()
        signal_direction = context.get("signal_direction")  # "CE" or "PE"

        scores = {
            "vwap_alignment": self._score_vwap(snapshot, signal_direction),
            "delta_momentum": self._score_delta(snapshot, signal_direction),
            "book_support": self._score_book(snapshot, signal_direction),
            "volume_profile": self._score_profile(snapshot, signal_direction),
        }

        composite = sum(scores.values()) / len(scores)

        return {
            "pass": composite >= 40,
            "score": composite,
            "components": scores,
            "alerts": self._build_alerts(snapshot),
        }
```

### Filter Rules

| Metric | Bullish (BUY_CE) | Bearish (BUY_PE) |
|--------|-------------------|-------------------|
| VWAP | Price > VWAP → 80pts, within bands → 50pts, below → 20pts | Inverse |
| Delta/CVD | CVD trending up + no bearish divergence → 80pts | CVD trending down + no bullish divergence → 80pts |
| Book Imbalance | > 0.55 → 80pts, 0.45-0.55 → 50pts, < 0.45 → 20pts | Inverse |
| Volume Profile | Price above POC + in value area → 80pts | Price below POC + in value area → 80pts |

Composite >= 40 → filter passes. Below 40 → signal suppressed.

### Wiring in main.py

```python
# In TradingBot.initialize():
self.order_flow_analyzer = OrderFlowAnalyzer()
self.intelligence_engine.register("order_flow", OrderFlowModule(self.order_flow_analyzer))

# In MarketDataManager._on_streamer_message() (futures tick block):
# After futures_volume_tracker.on_tick():
if self.order_flow_analyzer:
    self.order_flow_analyzer.on_tick(price, volume, direction, timestamp)
    if bids_and_asks_available:
        self.order_flow_analyzer.update_order_book(bids, asks)

# In get_status():
"order_flow": self.order_flow_analyzer.get_snapshot() if self.order_flow_analyzer else None
```

---

## Frontend Design

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/features/order-flow/OrderFlowTab.tsx` | Main tab component (3-column grid) |
| `frontend/src/features/order-flow/VolumeProfileChart.tsx` | Horizontal bar chart — buy/sell volume per price bin |
| `frontend/src/features/order-flow/VWAPChart.tsx` | Price line with VWAP overlay + CVD divergence markers |
| `frontend/src/features/order-flow/OrderBookPanel.tsx` | Live 5-level bid/ask visualization + imbalance gauge |
| `frontend/src/features/order-flow/OrderFlowHeader.tsx` | Summary strip — VWAP position, POC, imbalance, divergence alert |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/layout/BottomTabs.tsx` | Add "Order Flow" tab |
| `frontend/src/types/api.ts` | Add OrderFlow TypeScript types |

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  OrderFlowHeader: VWAP | POC | Book Imbalance | Divergence Alert │
├────────────────┬──────────────────┬──────────────────────────────┤
│ VolumeProfile  │   VWAPChart      │     OrderBookPanel           │
│ (horizontal    │   (price + VWAP  │     (5-level bid/ask bars    │
│  bars per      │    + bands +     │      + imbalance gauge)      │
│  price bin)    │    CVD overlay)  │                              │
└────────────────┴──────────────────┴──────────────────────────────┘
```

### TypeScript Types

```typescript
interface OrderFlowData {
    vwap: number;
    vwap_upper: number;
    vwap_lower: number;
    std_dev: number;
    volume_profile: VolumeProfileBin[];
    poc: number;
    value_area_high: number;
    value_area_low: number;
    book_imbalance: number;
    bid_total: number;
    ask_total: number;
    delta_divergence: DeltaDivergence;
    total_volume: number;
}

interface VolumeProfileBin {
    price: number;
    buy_vol: number;
    sell_vol: number;
    total: number;
}

interface DeltaDivergence {
    active: boolean;
    type: "bullish" | "bearish" | null;
    strength: number;
    bars: number;
}
```

### Rendering Approach

- Pure SVG — same approach as PriceChart.tsx and FuturesVolumeStrip.tsx
- No additional charting libraries
- Tailwind CSS for layout
- `useMemo` for performance optimization
- Data via Redux store from `/ws/status` broadcast

---

## Data Flow Summary

```
Upstox WebSocket
    │
    v
MarketDataManager._on_streamer_message()
    │
    ├── FuturesVolumeTracker.on_tick(price, ltq, timestamp)
    │       │
    │       └── OrderFlowAnalyzer.on_tick(price, ltq, direction, timestamp)
    │
    ├── OrderFlowAnalyzer.update_order_book(bids, asks)
    │
    └── (on candle close from FuturesVolumeTracker)
            └── OrderFlowAnalyzer.on_candle_close(close, cvd)

TradingBot.get_status()
    │
    └── "order_flow": order_flow_analyzer.get_snapshot()
            │
            v
        Frontend Redux Store → OrderFlowTab renders
```

---

## Testing Strategy

- **OrderFlowAnalyzer**: Unit tests for VWAP math, volume profile binning, POC/value area calculation, divergence detection, book imbalance, daily reset
- **OrderFlowModule**: Tests for filter scoring logic per direction (CE vs PE)
- **Integration**: Verify wiring from FuturesVolumeTracker → OrderFlowAnalyzer → get_status()

---

## Estimated Effort

| Component | Effort |
|-----------|--------|
| OrderFlowAnalyzer + tests | 4-6 hours |
| OrderFlowModule + tests | 2-3 hours |
| Wiring (main.py, market_data.py) | 1-2 hours |
| Frontend types + OrderFlowTab | 4-6 hours |
| Frontend sub-components (4) | 6-8 hours |
| BottomTabs integration | 1 hour |
| **Total** | **18-26 hours** |
