# Backend Architecture Flowchart - Detailed Guide

## 1. System Overview Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Server (server.py)                        │
│                         Runs on http://0.0.0.0:8000                        │
└────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
         ┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐
         │ HTTP Endpoints   │  │ WebSocket      │  │ Trading Bot      │
         │ (REST API)       │  │ Real-time Data │  │ Core (main.py)   │
         │                  │  │ Streaming      │  │                  │
         └──────────────────┘  └────────────────┘  └──────────────────┘
                    │                 │                     │
                    │                 │                     │
                    └─────────────────┼─────────────────────┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                │                     │                     │
                ▼                     ▼                     ▼
        ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐
        │ Config & Auth   │  │ Data Pipeline    │  │ Trading Managers  │
        │ (core/)         │  │ (data/)          │  │ (managers/)       │
        │                 │  │                  │  │                   │
        │ • Config        │  │ • DataFetcher    │  │ • OrderManager    │
        │ • Authenticator │  │ • OptionHandler  │  │ • PositionMgr     │
        │ • Logger        │  │                  │  │ • RiskManager     │
        │ • GreeksCalc    │  │                  │  │ • PaperTrading    │
        └─────────────────┘  └──────────────────┘  └───────────────────┘
                │                     │                     │
                │                     │                     │
                └─────────────────────┼─────────────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      │                               │
                      ▼                               ▼
              ┌──────────────────┐          ┌──────────────────┐
              │ Strategy Engine  │          │ Upstox API       │
              │ (strategies/)    │          │ Real-time Data   │
              │                  │          │                  │
              │ • Indicators     │          │ • OHLC Data      │
              │ • Signals        │          │ • Market Feed    │
              │ • Backtesting    │          │ • Order Management
              └──────────────────┘          └──────────────────┘
```

---

## 2. Bot Initialization & Startup Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                          Server Startup                          │
│                      server.py main block                        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Create FastAPI App   │
                  │ Configure CORS       │
                  │ Setup Logger         │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ POST /start Endpoint │
                  │ Called from Frontend │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ bot.start()          │
                  │ (main.py)            │
                  └──────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
        ┌───────────────┐ ┌───────────────┐ ┌──────────────┐
        │ Set is_running│ │ Start Thread  │ │ Start WS     │
        │ = True        │ │ _run_loop()   │ │ MarketData   │
        └───────────────┘ └───────────────┘ └──────────────┘
                │             │             │
                └─────────────┼─────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Return Status to     │
                  │ Frontend             │
                  └──────────────────────┘
```

---

## 3. Bot Initialization Process (bot.initialize())

```
┌──────────────────────────────────────────────────────────────────┐
│              TradingBot.initialize() (main.py:63)                │
└──────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
    ┌──────────────────┐  ┌──────────┐  ┌──────────────────┐
    │ Load Config      │  │ Load Auth│  │ Initialize       │
    │ (env vars)       │  │ Token    │  │ Components       │
    │                  │  │          │  │                  │
    │ • API KEY        │  │ • Check  │  │ • DataFetcher    │
    │ • API SECRET     │  │   if     │  │ • StrategyEngine │
    │ • ACCESS TOKEN   │  │   valid  │  │ • OrderManager   │
    │ • TIMEFRAME      │  │ • Log    │  │ • Position Mgr   │
    └──────────────────┘  └──────────┘  └──────────────────┘
            │                 │                 │
            └─────────────────┼─────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Load Instruments     │
                  │ (NSE.csv)            │
                  │                      │
                  │ • Download if needed │
                  │ • Cache locally      │
                  │ • Load to DataFrame  │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Initialize WebSocket │
                  │ MarketDataSocket     │
                  │                      │
                  │ • Set tokens         │
                  │ • Set instruments    │
                  │ • Setup event sync   │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Initialize Risk      │
                  │ Manager              │
                  │                      │
                  │ • Get paper balance  │
                  │ • Set initial capital│
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Initialization Done  │
                  │ Ready to Start       │
                  └──────────────────────┘
```

---

## 4. Main Trading Loop (_run_loop)

```
┌────────────────────────────────────────────────────────────────────────┐
│                      _run_loop() - Main Loop                           │
│                    (Runs every iteration)                              │
└────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ While is_running:    │
                  └──────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
    ┌─────────────┐  ┌──────────────────┐  ┌─────────────┐
    │ Fetch Real  │  │ Fetch Historical │  │ WebSocket   │
    │ Time Price  │  │ OHLC Data        │  │ Price       │
    │             │  │ (last 100 bars)  │  │ (if avail)  │
    │ API/WS      │  │                  │  │             │
    └─────────────┘  └──────────────────┘  └─────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Update Current Price │
                  │ ATM Strike Level     │
                  │ Last Updated Time    │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Calculate Indicators │
                  │ (Strategy Engine)    │
                  │                      │
                  │ • EMA (5, 20)        │
                  │ • RSI (14)           │
                  │ • MACD               │
                  │ • Bollinger Bands    │
                  │ • Supertrend         │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Generate Signal      │
                  │ Based on Indicators  │
                  │                      │
                  │ BUY / SELL /         │
                  │ HOLD / CLOSE         │
                  └──────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
        ┌─────────────────┐        ┌───────────────────┐
        │ Signal = BUY    │        │ Other Signals or  │
        │ (After Cooldown)│        │ HOLD              │
        └─────────────────┘        └───────────────────┘
                │                           │
                ▼                           ▼
        ┌─────────────────┐        ┌───────────────────┐
        │ Fetch Option    │        │ Continue Loop     │
        │ Chain for ATM   │        │ No Action         │
        │ Strike          │        └───────────────────┘
        └─────────────────┘
                │
                ▼
        ┌─────────────────┐
        │ Calculate Greeks│
        │ (Volatility)    │
        │ IV Rank         │
        └─────────────────┘
                │
                ▼
        ┌─────────────────────────────────────┐
        │ Strategy Decision:                  │
        │ Which contract to trade?            │
        │ • CE or PE?                         │
        │ • What quantity?                    │
        │ • What exit rules?                  │
        └─────────────────────────────────────┘
                │
                ▼
        ┌─────────────────────────────────────┐
        │ Check Risk Manager                  │
        │ • Can take this trade?              │
        │ • Position limits?                  │
        │ • Capital available?                │
        └─────────────────────────────────────┘
                │
        ┌───────┴───────┐
        │               │
        ▼ YES           ▼ NO
    ┌──────────┐   ┌──────────┐
    │Place     │   │Wait &    │
    │Order     │   │Retry     │
    └──────────┘   └──────────┘
        │
        ▼
    ┌──────────────────────┐
    │ Order Placement      │
    │ (Paper/Real Mode)    │
    │                      │
    │ • Create order       │
    │ • Update position    │
    │ • Set exit rules     │
    └──────────────────────┘
        │
        ▼
    ┌──────────────────────┐
    │ Monitor Position     │
    │ • Check P&L          │
    │ • Monitor Exit rules │
    │ • Manage stop loss   │
    └──────────────────────┘
        │
        ▼
    ┌──────────────────────┐
    │ Calculate PnL        │
    │ Update Dashboard     │
    │ Collect AI Data      │
    └──────────────────────┘
        │
        ▼
    ┌──────────────────────┐
    │ Sleep (1s) / Wait    │
    │ for next iteration   │
    └──────────────────────┘
        │
        └──────────────────────► [Loop back to top]
```

---

## 5. Order Placement Flow

```
┌────────────────────────────────────────────────────────────────┐
│                   Order Placement Flow                         │
│              (When Signal Generated)                           │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Generate Trade Order │
                  │ • Instrument Key     │
                  │ • Quantity           │
                  │ • Transaction Type   │
                  │ • Current Price      │
                  └──────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
        ┌──────────────────┐      ┌──────────────────┐
        │ Trading Mode     │      │ Trading Mode     │
        │ = "PAPER"        │      │ = "REAL"         │
        └──────────────────┘      └──────────────────┘
                │                           │
                ▼                           ▼
        ┌──────────────────┐      ┌──────────────────┐
        │ PaperTradingMgr  │      │ Upstox API       │
        │ .place_order()   │      │ .place_order()   │
        │                  │      │                  │
        │ • Simulate trade │      │ • Real broker    │
        │ • Update balance │      │ • Live execution │
        │ • Record P&L     │      │                  │
        └──────────────────┘      └──────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Return Order ID      │
                  │ & Order Details      │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Update Position      │
                  │ Manager              │
                  │                      │
                  │ • Add position       │
                  │ • Set entry price    │
                  │ • Set exit rules     │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Create Trading       │
                  │ Reasoning Record     │
                  │                      │
                  │ • Why this trade?    │
                  │ • Entry conditions   │
                  │ • Exit conditions    │
                  │ • Risk-Reward        │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Log & Store Data     │
                  │ • Bot logs           │
                  │ • AI training data   │
                  │ • Position data      │
                  └──────────────────────┘
```

---

## 6. Position Management & Exit Flow

```
┌────────────────────────────────────────────────────────────────┐
│             Position Management & Exit Logic                   │
└────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │Check     │    │Monitor   │    │Monitor   │
        │P&L Goals │    │Stop Loss │    │Trailing  │
        │          │    │          │    │Stop      │
        │ • Profit │    │ • SL Hit?│    │ • Adjust?│
        │   Target │    │ • Exit   │    │ • Exit   │
        │ • Time   │    │   order  │    │   order  │
        │   Exits  │    │          │    │          │
        └──────────┘    └──────────┘    └──────────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │ Exit Signal  │    │ No Exit      │
            │ Generated    │    │ Continue     │
            │              │    │ Holding      │
            └──────────────┘    └──────────────┘
                    │                   │
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │ Place Exit   │    │ Loop Back    │
            │ Order at     │    │ Next Iter    │
            │ Current Price│    │              │
            └──────────────┘    └──────────────┘
                    │
                    ▼
            ┌──────────────┐
            │ Calculate    │
            │ Position P&L │
            │ • Entry Price│
            │ • Exit Price │
            │ • Qty        │
            │ • Net P&L    │
            └──────────────┘
                    │
                    ▼
            ┌──────────────┐
            │ Update Risk  │
            │ Manager      │
            │ • Daily P&L  │
            │ • Total P&L  │
            │ • Max Drawdown
            └──────────────┘
                    │
                    ▼
            ┌──────────────┐
            │ Close        │
            │ Position in  │
            │ Position Mgr │
            └──────────────┘
                    │
                    ▼
            ┌──────────────┐
            │ Add to Trade │
            │ History      │
            │ Archive      │
            └──────────────┘
```

---

## 7. API Endpoints Flow

```
┌──────────────────────────────────────────────────────────────┐
│                FastAPI Endpoints (server.py)                 │
└──────────────────────────────────────────────────────────────┘
        │                                                   │
        ├─── GET / (Health Check)                          │
        │     └─► {"message": "API is running"}            │
        │                                                  │
        ├─── GET /status                                   │
        │     └─► Returns bot.get_status()                 │
        │         • is_running, signals, prices            │
        │         • Positions, P&L, risk stats             │
        │                                                  │
        ├─── POST /start                                   │
        │     └─► bot.start()                              │
        │         Starts trading loop                      │
        │                                                  │
        ├─── POST /stop                                    │
        │     └─► bot.stop()                               │
        │         Stops trading loop                       │
        │                                                  │
        ├─── GET /logs                                     │
        │     └─► Returns latest_log (last 50 lines)       │
        │                                                  │
        ├─── GET /config                                   │
        │     └─► Returns config settings                  │
        │         • Timeframe, symbol, token status        │
        │                                                  │
        ├─── POST /config                                  │
        │     │ Request: { "timeframe": "string" }         │
        │     └─► Updates bot configuration                │
        │                                                  │
        ├─── POST /mode                                    │
        │     │ Request: { "mode": "PAPER" | "REAL" }      │
        │     └─► Switches trading mode                    │
        │                                                  │
        ├─── POST /paper/funds                             │
        │     │ Request: { "amount": float }               │
        │     └─► Adds funds to paper trading              │
        │                                                  │
        ├─── POST /positions/close                         │
        │     │ Request: {                                 │
        │     │   "position_id": string,                   │
        │     │   "exit_price": float                      │
        │     │ }                                          │
        │     └─► Manually close position                  │
        │                                                  │
        ├─── POST /backtest                                │
        │     │ Request: {                                 │
        │     │   "from_date": string,                     │
        │     │   "to_date": string,                       │
        │     │   "initial_capital": float                 │
        │     │ }                                          │
        │     └─► Run backtest simulation                  │
        │                                                  │
        └─── WebSocket /ws                                 │
              └─► Real-time market data streaming
```

---

## 8. Data Flow - Real-Time Updates

```
┌─────────────────────────────────────────────────────────────┐
│           Real-Time Data Flow (WebSocket)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
        ┌─────────────┐ ┌──────────┐ ┌──────────────┐
        │ Upstox API  │ │ WebSocket│ │ DataFetcher  │
        │ Server      │ │ Feed     │ │ REST API     │
        │             │ │          │ │              │
        │ Market Data │ │ Real-    │ │ Historical   │
        └─────────────┘ │ time     │ │ OHLC         │
                │       │ prices   │ └──────────────┘
                │       └──────────┘      │
                │             │           │
                └─────────────┼───────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ MarketDataSocket     │
                  │ ._on_message()       │
                  │                      │
                  │ • Parse JSON         │
                  │ • Extract price      │
                  │ • Update latest_data │
                  │ • Signal event       │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ _run_loop() Waits    │
                  │ on data_event        │
                  │                      │
                  │ • Processes price    │
                  │ • Updates indicators │
                  │ • Generates signal   │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Broadcasting Update  │
                  │ to Frontend (if WS)  │
                  │                      │
                  │ Status every ~10 sec │
                  │ Price every tick     │
                  └──────────────────────┘
```

---

## 9. Component Interactions

```
┌────────────────────────────────────────────────────────────────┐
│ Component Dependencies (How modules communicate)               │
└────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │ Config       │ ◄─────────────────────┐
  │ (core/)      │                       │
  └──────────────┘                       │
       ▲  ▲  ▲                          │
       │  │  └──────────────┐           │
       │  │                 │           │
       │  ▼                 ▼ ▼         │
  ┌──────────────┐    ┌─────────────┐  │
  │ Server.py    │───►│ TradingBot  │──┤
  │ (FastAPI)    │    │ (main.py)   │  │
  └──────────────┘    └─────────────┘  │
                            │ │ │ │     │
           ┌────────────────┼┼┼┘│     │
           │                │ │  │     │
           ▼                ▼ ▼  ▼ ▼   │
       ┌─────────┐     ┌──────────────┐│
       │Position │     │OrderManager  ││
       │Manager  │     │              ││
       │         │     │ Paper        ││
       └─────────┘     │ Trading Mgr  ││
           ▲           └──────────────┘│
           │                │          │
       ┌─────────┐          │         │
       │Risk Mgr │◄─────────┤         │
       │         │          │         │
       └─────────┘          ▼         │
                   ┌──────────────────┘
                   │
           ┌───────┼─────────┐
           │       │         │
           ▼       ▼         ▼
      ┌──────┐ ┌──────┐ ┌──────────────┐
      │Data  │ │Strat │ │WebSocket     │
      │Fetch │ │Engine│ │Client        │
      └──────┘ └──────┘ └──────────────┘
           │       │         │
           └───────┼─────────┘
                   │
                   ▼
          ┌──────────────────┐
          │ Upstox API       │
          │ (Broker)         │
          └──────────────────┘
```

---

## 10. Data Storage & Persistence

```
┌────────────────────────────────────────────────────────────────┐
│ Data Storage Architecture                                      │
└────────────────────────────────────────────────────────────────┘
        │
        ├─────────────────────────────────────────┐
        │                                         │
        ▼                                         ▼
    ┌─────────────────────┐          ┌─────────────────────┐
    │ CSV Files           │          │ JSON Files          │
    │ (data/)             │          │ (data/)             │
    │                     │          │                     │
    │ • NSE.csv           │          │ • positions_data    │
    │   (instrument list) │          │   (open positions)  │
    │                     │          │                     │
    │ • ai_training_      │          │ • paper_trading_    │
    │   data.csv          │          │   data.json         │
    │   (ML features)     │          │   (trade history)   │
    │                     │          │                     │
    └─────────────────────┘          └─────────────────────┘
           ▲                                  ▲
           │                                  │
           └──────────────┬───────────────────┘
                          │
            ┌─────────────┼─────────────┐
            │             │             │
            ▼             ▼             ▼
      ┌──────────┐ ┌──────────┐ ┌───────────┐
      │Position  │ │Paper     │ │AI Data    │
      │Manager   │ │Trading   │ │Collector  │
      │          │ │Manager   │ │           │
      │Save:     │ │Save:     │ │Save:      │
      │• Entries │ │• Trades  │ │• Features │
      │• Exits   │ │• Balance │ │• Labels   │
      │• Greeks  │ │• PnL     │ │• Outcomes │
      └──────────┘ └──────────┘ └───────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ Logs Directory   │
            │ (logs/)          │
            │                  │
            │ • Trading logs   │
            │ • Error logs     │
            │ • Access logs    │
            └──────────────────┘
```

---

## 11. Signal Generation Decision Tree

```
┌────────────────────────────────────────────────────────────────┐
│ How Trading Signals Are Generated                              │
└────────────────────────────────────────────────────────────────┘
                              │
                    Latest OHLC Data
                         (100 bars)
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
        ┌───────────────┐        ┌──────────────────┐
        │ Calculate     │        │ Calculate        │
        │ Technical     │        │ Support &        │
        │ Indicators    │        │ Resistance       │
        │               │        │                  │
        │ • EMA(5,20)   │        │ • Pivot points   │
        │ • RSI(14)     │        │ • Pivot support  │
        │ • MACD        │        │ • Pivot resistance
        │ • Bollinger   │        │                  │
        │ • Supertrend  │        │                  │
        └───────────────┘        └──────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Check Signal Rules   │
                  │ (Configured in       │
                  │  strategy.py)        │
                  └──────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
            ┌────────┐  ┌────────┐  ┌────────┐
            │ BUY    │  │ SELL   │  │ HOLD/  │
            │Signal? │  │Signal? │  │CLOSE?  │
            │        │  │        │  │        │
            │EMA5>20 │  │EMA5<20 │  │Else    │
            │RSI<45  │  │RSI>55  │  │        │
            │Price   │  │Price   │  │        │
            │>ST     │  │<ST     │  │        │
            └────────┘  └────────┘  └────────┘
                │             │             │
                └─────────────┼─────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Check Cooldown       │
                  │ (2 min between same  │
                  │  signal type)        │
                  └──────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼ YES                       ▼ NO
            ┌────────┐              ┌────────┐
            │ Signal │              │ Skip   │
            │Approved│              │Signal  │
            └────────┘              └────────┘
                │                       │
                └───────────┬───────────┘
                            │
                            ▼
                ┌──────────────────────┐
                │ Store Latest Signal  │
                │ Send to Frontend     │
                │ Log with Timestamp   │
                └──────────────────────┘
```

---

## 12. Risk Management Flow

```
┌────────────────────────────────────────────────────────────────┐
│ Risk Management & Position Control                             │
└────────────────────────────────────────────────────────────────┘
                              │
                    Signal Generated
                              │
                              ▼
                  ┌──────────────────────┐
                  │ RiskManager          │
                  │ can_take_trade()     │
                  │                      │
                  │ Checks:              │
                  └──────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
    ┌──────────────┐   ┌──────────────┐  ┌──────────────┐
    │ Capital      │   │ Position     │  │ Daily Loss   │
    │ Available?   │   │ Limits       │  │ Limit        │
    │              │   │              │  │              │
    │ • Balance >  │   │ • Max open   │  │ • Daily PnL  │
    │   margin req │   │   positions  │  │   > -limit?  │
    │ • Account    │   │ • Per trade  │  │ • Stop loss  │
    │   not locked │   │   size limit │  │   triggered? │
    └──────────────┘   └──────────────┘  └──────────────┘
            │                 │                 │
            └─────────────────┼─────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼ ALL PASS          ▼ ANY FAIL
            ┌──────────────┐    ┌──────────────┐
            │ APPROVE      │    │ REJECT       │
            │ TRADE        │    │ TRADE        │
            │              │    │              │
            │ Proceed to   │    │ Log reason   │
            │ Order Mgr    │    │ Skip signal  │
            └──────────────┘    └──────────────┘
                    │                   │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │ Place Order  │    │ Continue to  │
            │ Update Stats │    │ Next Loop    │
            │ Set Limits   │    │              │
            └──────────────┘    └──────────────┘
```

---

## 13. Key Data Structures

```
┌────────────────────────────────────────────────────────────────┐
│ Important Data Structures Used                                 │
└────────────────────────────────────────────────────────────────┘

TradingBot Class (main.py)
├── Configuration
│   ├── is_running: bool
│   ├── access_token: str
│   ├── nifty_key: str
│   └── timeframe: str
│
├── Market State
│   ├── current_price: float
│   ├── atm_strike: int
│   ├── last_updated: datetime
│   ├── latest_strategy_data: dict {
│   │   ├── ema_5: float
│   │   ├── ema_20: float
│   │   ├── rsi: float
│   │   ├── signal: str
│   │   └── reason: str
│   │}
│   └── latest_sentiment: dict
│
├── Components
│   ├── data_fetcher: DataFetcher
│   ├── strategy_engine: StrategyEngine
│   ├── order_manager: OrderManager
│   ├── position_manager: PositionManager
│   ├── risk_manager: RiskManager
│   ├── ws_client: MarketDataSocket
│   └── reasoning_engine: TradingReasoning
│
├── Trading State
│   ├── trade_history: list[dict] {
│   │   ├── entry_price: float
│   │   ├── exit_price: float
│   │   ├── quantity: int
│   │   ├── pnl: float
│   │   ├── entry_time: datetime
│   │   └── exit_time: datetime
│   │}
│   └── latest_log: list[str]
│
└── Monitoring
    ├── last_signal_time: dict
    └── signal_cooldown_seconds: int (120)


Position (position_manager.py)
├── position_id: str (unique)
├── instrument_key: str
├── entry_price: float
├── entry_time: datetime
├── quantity: int
├── current_price: float
├── greeks: dict {
│   ├── delta: float
│   ├── gamma: float
│   ├── theta: float
│   ├── vega: float
│   ├── iv: float
│   └── iv_rank: float
│}
├── pnl_current: float
├── exit_rules: dict {
│   ├── profit_target: float
│   ├── stop_loss: float
│   ├── trailing_stop: float
│   └── time_exit_min: int
│}
└── status: str (OPEN | CLOSED | HOLD)


Order (paper_trading.py)
├── order_id: str
├── instrument_key: str
├── transaction_type: str (BUY | SELL)
├── quantity: int
├── price: float
├── order_time: datetime
└── status: str (PENDING | EXECUTED | REJECTED)
```

---

## 14. State Transitions Diagram

```
┌────────────────────────────────────────────────────────────────┐
│ Bot State Machine                                              │
└────────────────────────────────────────────────────────────────┘

  ┌─────────────────────┐
  │  NOT INITIALIZED    │
  │                     │
  │ bot = TradingBot()  │
  └──────────┬──────────┘
             │
             │ bot.initialize()
             │
             ▼
  ┌─────────────────────┐
  │ INITIALIZED         │
  │                     │
  │ Components ready    │
  │ is_running = False  │
  └──────────┬──────────┘
             │
             │ bot.start()
             │
             ▼
  ┌──────────────────────────┐
  │ RUNNING                  │
  │                          │
  │ • Loop thread active     │
  │ • WebSocket connected    │
  │ • Monitoring signals     │
  │ • Placing trades         │
  └──────────┬───────────────┘
             │
       ┌─────┼─────┐
       │             │
       │ bot.stop()  │ ERROR / EXCEPTION
       │             │
       ▼             ▼
  ┌─────────────┐  ┌──────────────┐
  │ STOPPED     │  │ ERROR STATE  │
  │             │  │              │
  │ is_running  │  │ Log error    │
  │ = False     │  │ Attempt fix  │
  └────────┬────┘  └──────┬───────┘
           │               │
           └───────┬───────┘
                   │
                   │ bot.start()
                   │ (restart)
                   ▼
          ┌─────────────────┐
          │ RUNNING (again) │
          └─────────────────┘
```

---

## 15. Execution Timeline Example

```
┌────────────────────────────────────────────────────────────────┐
│ Sample Execution Timeline (1 Minute)                           │
└────────────────────────────────────────────────────────────────┘

08:30:00 ─ Server starts, awaits API calls
08:30:05 ─ Frontend calls POST /start
08:30:06 ─ bot.initialize() runs
08:30:10 ─ Components initialized
08:30:15 ─ bot.start() called
08:30:16 ─ Threading starts, _run_loop() begins
08:30:17 ─ WS connection established

[Loop starts iterating every 1-5 seconds]

08:30:20 ─ Fetch current price: 18,450.25
08:30:21 ─ Fetch 100-bar OHLC data
08:30:22 ─ Calculate EMA(5), EMA(20), RSI, MACD
08:30:23 ─ Analysis: EMA5(18450) > EMA20(18420) ✓
08:30:23 ─           RSI(42) < 45 ✓
08:30:23 ─           Supertrend = BULLISH ✓
08:30:24 ─ → Signal: BUY (cooldown OK)
08:30:25 ─ Fetch CE options for ATM strike 18450
08:30:26 ─ Get option prices: 18450 CE = 102.50
08:30:27 ─ Calculate Greeks (Delta=0.60, Vega=0.15)
08:30:28 ─ Risk Manager Check:
08:30:28 ─   • Balance: 95,000 ✓
08:30:28 ─   • Can trade 1 lot (100 qty) ✓
08:30:28 ─   • Daily loss limit: OK ✓
08:30:29 ─ → APPROVE TRADE
08:30:30 ─ Place BUY order: 100 qty @ 102.50 (MARKET)
08:30:31 ─ Order ID: ORD-123456 (Paper executed)
08:30:32 ─ Position #1 created: Entry=102.50, Qty=100
08:30:33 ─ Set Exit Rules:
08:30:33 ─   • Profit Target: 110.00 (+7.50/lot)
08:30:33 ─   • Stop Loss: 95.00 (-7.50/lot)
08:30:34 ─ Store Reasoning: "EMA bullish crossover + RSI oversold"
08:30:35 ─ Update Dashboard Status
08:30:36 ─ [Loop continues...]

08:30:50 ─ CE price = 105.00
08:30:50 ─ Position P&L: +250 (unrealized)
08:30:51 ─ Update Dashboard

08:31:10 ─ CE price = 108.50
08:31:10 ─ Position P&L: +600 (unrealized)
08:31:11 ─ Update Dashboard

08:32:00 ─ CE price = 112.00
08:32:00 ─ Position P&L: +950 (exceeds target 110)
08:32:01 ─ Exit Signal: Profit target hit
08:32:02 ─ Place SELL order: 100 qty @ MARKET
08:32:03 ─ Exit filled @ 111.50
08:32:04 ─ Position closed: P&L = +900 (realized)
08:32:05 ─ Update Trade History
08:32:06 ─ Reset for next signal
08:32:07 ─ Dashboard shows: Daily P&L: +900

[Loop continues...]
```

---

## Summary of Key Components

| Component | File | Responsibility |
|-----------|------|-----------------|
| **TradingBot** | main.py | Main orchestrator, manages all components |
| **FastAPI Server** | server.py | REST API endpoints, HTTP interface |
| **DataFetcher** | data/data_fetcher.py | Fetch OHLC, options data from Upstox |
| **StrategyEngine** | strategies/strategy.py | Calculate indicators, generate signals |
| **OrderManager** | managers/order_manager.py | Place/manage orders (Paper + Real) |
| **PositionManager** | managers/position_manager.py | Track open positions, P&L |
| **RiskManager** | managers/risk_manager.py | Check risk limits, manage capital |
| **PaperTradingManager** | managers/paper_trading.py | Simulate paper trading |
| **MarketDataSocket** | core/websocket_client.py | Real-time WebSocket connection |
| **GreeksCalculator** | core/greeks.py | Calculate option Greeks |
| **Authenticator** | core/authentication.py | Handle OAuth, token management |
| **TradingReasoning** | strategies/reasoning.py | Generate reasoning for decisions |
| **AIDataCollector** | utils/ai_data_collector.py | Collect data for ML training |
| **Config** | core/config.py | Configuration & environment variables |

