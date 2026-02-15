# Nifty Trading Bot - End-to-End Backend Workflow

This document details the complete flow of data and logic within the backend of the trading bot, from initialization to trade execution.

## 1. High-Level Architecture
The system follows an **Event-Driven Architecture**. The core driver is the real-time market data stream (WebSocket), which triggers the strategy logic upon every price update.

```mermaid
graph TD
    subgraph "Initialization Phase"
        Entry[main.py] --> BotInit[TradingBot.initialize]
        BotInit --> LoadEnv[Load .env & Config]
        BotInit --> InitComponents[Init Managers]
        InitComponents --> DF[DataFetcher (HTTP)]
        InitComponents --> MDM[MarketDataManager (WS)]
        InitComponents --> SR[StrategyRunner]
        InitComponents --> TE[TradeExecutor]
    end

    subgraph "Data Ingestion (Real-Time)"
        Upstox((Upstox WebSocket)) -->|Feed Broadcast| MDM
        MDM -->|Parse 'fullFeed'| Parsers
        
        subgraph "Parsers"
            P1[Nifty 50 Index Price]
            P2[ATM Option Prices]
            P3[Option Chain OI]
        end
        
        P1 -->|Update| CurrentPrice[Current Price]
        P3 -->|Aggregated| PCR[PCR Calc (Values & Logic)]
        P2 -->|Algorithm| Greeks[Greeks Calc (IV, Delta)]
    end

    subgraph "Strategy Processing (Event Loop)"
        CurrentPrice -->|Trigger Event| SR_Update[StrategyRunner.on_price_update]
        SR_Update --> Candle[CandleManager.update]
        Candle -->|Price Tick| Incomplete[Update Incomplete Candle]
        Candle -->|Time Limit| Complete[Finalize 5-min Candle]
        
        CurrentPrice -->|Tick| EMA[StreamingEMA.update]
        
        Incomplete --> StrategyData[Prepare DataFrame + State]
        EMA --> StrategyData
        PCR --> StrategyData
        Greeks --> StrategyData
    end

    subgraph "Signal & Filter Logic"
        StrategyData --> Engine[StrategyEngine.check_signal]
        
        subgraph "Filter Generation Pipeline"
            Engine --> Ind[Calc Indicators: RSI, Supertrend, ATR]
            Ind --> Filters{Filter Check Gate}
            
            Filters -- Check 1 --> F_ST[Supertrend Logic]
            Filters -- Check 2 --> F_EMA[EMA Crossover]
            Filters -- Check 3 --> F_RSI[RSI Threshold 50+/-]
            Filters -- Check 4 --> F_ATR[Volatility 0.01-2.5%]
            Filters -- Check 5 --> F_PCR[PCR <1 Bull / >1 Bear]
            Filters -- Check 6 --> F_Greeks[Quality Score > 50]
        end
        
        Filters -->|ALL PASS| Signal[Signal: BUY_CE / BUY_PE]
        Filters -->|ANY FAIL| Hold[Signal: HOLD]
    end

    subgraph "Execution Phase"
        Signal -->|If BUY| Executor[TradeExecutor]
        Executor --> Risk[RiskManager Check]
        Risk -- Approved --> Order[OrderManager.place_order]
        Risk -- Rejected --> Log[Log Rejection]
        Order --> API[Upstox API]
    end
```

## 2. Detailed Data Flow Steps

### Phase 1: Ingestion (`MarketDataManager`)
The `MarketDataManager` is the heart of the system.
- **WebSocket Connection**: Connects to Upstox V3 WebSocket.
- **Subscriptions**:
    - `Nifty 50`: For the underlying index price.
    - `Option Chain`: Subscribes to strikes ±500 points from ATM to calculate PCR.
- **Processing**:
    - **Price**: Updates instantly.
    - **PCR**: Aggregates Open Interest (OI) from all subscribed strikes every 5 seconds.
    - **Greeks**: Calculates IV and Delta for ATM options based on real-time prices.

### Phase 2: Orchestration (`StrategyRunner`)
This component acts as the bridge between raw data and pure logic.
- **Candle Formation**: It doesn't wait for candles to close. It uses `CandleManager` to maintain a live, "incomplete" candle that updates with every tick. This allows the bot to react *intra-candle*.
- **Streaming Indicators**: Uses `StreamingEMA` classes to calculate EMA 5 and 20 recursively without needing to re-process the entire history array every second.

### Phase 3: Metric Generation (`StrategyEngine`)
This is where the decision is made (`app/strategies/strategy.py`).

The `check_signal` function builds the **Filter Metrics**:

1.  **Supertrend**:
    - Uses ATR (Average True Range) to calculate bands.
    - **Metric**: Boolean (Bullish/Bearish).
2.  **RSI**:
    - 14-period standard RSI.
    - **Metric**: Value (0-100). Bullish > 50, Bearish < 50.
3.  **EMA Crossover**:
    - Compares current vs previous candle EMAs.
    - **Metric**: `True` if a crossover occurred in the desired direction.
4.  **PCR (Sentiment)**:
    - **Metric**: Ratio of Put OI / Call OI.
    - Logic: < 1.0 implies Bullish, > 1.0 implies Bearish.
5.  **Volatility (ATR)**:
    - **Metric**: `(ATR / Price) * 100`.
    - Filter: Must be between 0.01% and 2.5% to ensure the market is moving but not dangerous.

### Phase 4: Validated Signal
A trade is ONLY triggered if **every single filter** returns `True` for a specific direction.

- **BUY_CE Trigger**:
    - Supertrend: Bullish
    - EMA: 5 > 20 (or crossover)
    - RSI: > 50
    - PCR: < 1.0
    - Greeks: Quality > 50

- **BUY_PE Trigger**:
    - Supertrend: Bearish
    - EMA: 5 < 20 (or crossover)
    - RSI: < 50
    - PCR: > 1.0
    - Greeks: Quality > 50
