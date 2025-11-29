# Backend Folder Structure Guide

## 📁 Organized Structure

```
backend/
├── app/                          # Main application package
│   ├── __init__.py
│   ├── core/                     # Core functionality & configuration
│   │   ├── __init__.py
│   │   ├── authentication.py     # OAuth & Upstox authentication
│   │   ├── config.py             # Configuration & environment variables
│   │   ├── greeks.py             # Greeks calculation (Black-Scholes)
│   │   ├── logger_config.py      # Logging configuration
│   │   └── websocket_client.py   # Upstox WebSocket client
│   │
│   ├── data/                     # Data access & management
│   │   ├── __init__.py
│   │   ├── data_fetcher.py       # Fetch market data from Upstox API
│   │   └── option_data_handler.py # Real-time option Greeks streaming
│   │
│   ├── managers/                 # Business logic managers
│   │   ├── __init__.py
│   │   ├── order_manager.py      # Place & manage orders
│   │   ├── paper_trading.py      # Simulated trading (paper account)
│   │   ├── position_manager.py   # Track open positions
│   │   └── risk_manager.py       # Risk analysis & control
│   │
│   ├── strategies/               # Trading strategies
│   │   ├── __init__.py
│   │   ├── backtester.py         # Backtest strategies on historical data
│   │   ├── reasoning.py          # Generate reasoning for trades
│   │   └── strategy.py           # Technical indicators & signals
│   │
│   └── utils/                    # Utility functions
│       ├── __init__.py
│       ├── ai_data_collector.py  # Collect AI training data
│       └── json_utils.py         # JSON serialization helpers
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_backtester.py
│   ├── test_greeks.py
│   ├── test_option_data_handler.py
│   ├── test_trailing_stop.py
│   └── test_upstox.py
│
├── data/                         # Data files
│   ├── NSE.csv                   # NSE instrument master
│   ├── NSE.csv.gz
│   ├── ai_training_data.csv      # AI training data
│   ├── paper_trading_data.json    # Paper trading state
│   └── positions_data.json        # Positions state
│
├── logs/                         # Application logs
│   └── niftybot_*.log
│
├── main.py                       # Bot entry point (uses new imports)
├── server.py                     # FastAPI server (uses new imports)
├── requirements.txt              # Python dependencies
├── .env                          # Environment variables
├── .env.example                  # Example environment
├── .gitignore                    # Git ignore rules
├── move_files.sh                 # Migration script (cleanup later)
└── README.md                     # Backend documentation
```

## 🎯 Module Organization

### `app/core/`
**Purpose**: Core functionality, configuration, and utilities
- **config.py**: API keys, trading parameters, timeframes
- **authentication.py**: OAuth flow, access token management
- **websocket_client.py**: Real-time market data streaming
- **greeks.py**: Options pricing & Greeks calculation
- **logger_config.py**: Centralized logging setup

### `app/data/`
**Purpose**: Data fetching and real-time data streaming
- **data_fetcher.py**: REST API calls to Upstox
- **option_data_handler.py**: WebSocket Greeks streaming

### `app/managers/`
**Purpose**: Business logic & state management
- **order_manager.py**: Place/cancel orders (real + paper)
- **paper_trading.py**: Simulated trading environment
- **position_manager.py**: Track active positions
- **risk_manager.py**: Risk metrics & position limits

### `app/strategies/`
**Purpose**: Trading signal generation & backtesting
- **strategy.py**: Technical indicators (RSI, EMA, MACD, Bollinger, etc)
- **reasoning.py**: Trade reasoning & decision logic
- **backtester.py**: Historical testing framework

### `app/utils/`
**Purpose**: Helper functions
- **json_utils.py**: JSON serialization (numpy types, etc)
- **ai_data_collector.py**: Collect training data for ML models

### `tests/`
**Purpose**: Test suite
- All test files moved here (separated from source)

### `data/`
**Purpose**: Data files & state persistence
- CSVs: NSE instruments, AI training data
- JSONs: Paper trading state, positions

## 🔄 Import Changes

### Before (Old Root Level)
```python
from config import Config
from data_fetcher import DataFetcher
from strategy import StrategyEngine
from order_manager import OrderManager
```

### After (New Organized Structure)
```python
from app.core.config import Config
from app.data.data_fetcher import DataFetcher
from app.strategies.strategy import StrategyEngine
from app.managers.order_manager import OrderManager
```

## 📋 Files Updated with New Imports

- ✅ `main.py` - Entry point
- ✅ `server.py` - FastAPI server
- ✅ `app/core/authentication.py`
- ✅ `app/data/data_fetcher.py`
- ✅ `app/data/option_data_handler.py`
- ✅ `app/managers/order_manager.py`
- ✅ `app/strategies/backtester.py`

## 🚀 How to Use

### Running the Bot
```bash
cd /Users/jitendrasonawane/Workpace/backend
python3 main.py
```

### Running the API Server
```bash
python3 server.py
```

### Running Tests
```bash
python3 -m pytest tests/
```

## 🧹 Cleanup

After verifying everything works, you can delete the old root-level files:
```bash
# Remove old files (after confirming new structure works)
rm config.py authentication.py data_fetcher.py strategy.py \
   order_manager.py position_manager.py risk_manager.py \
   backtester.py reasoning.py websocket_client.py \
   greeks.py json_utils.py ai_data_collector.py \
   test_*.py
```

## ✅ Benefits of This Structure

1. **Clear Organization**: Easy to find related code
2. **Scalability**: Easy to add new modules
3. **Testability**: Separated `tests/` folder
4. **Maintainability**: Logical grouping of functionality
5. **Modularity**: Each package is self-contained
6. **Professional**: Follows Python best practices

## 📖 Module Dependencies

```
app/core/ (No dependencies on other app modules)
  ↑
app/data/ (Depends on core/)
  ↑
app/managers/ (Depends on core/, data/)
  ↑
app/strategies/ (Depends on core/, data/, managers/)
  ↑
main.py & server.py (Use all modules)
```

---

**Structure organized on**: Nov 24, 2025  
**Total modules**: 15 Python files  
**Status**: ✅ Ready for development
