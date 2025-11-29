# Backend Structure Quick Reference

## 📁 Where to Find What

### Configuration & Authentication
```
app/core/config.py          → API keys, timeframes, parameters
app/core/authentication.py  → OAuth, access token management
app/core/logger_config.py   → Logging setup
```

### Market Data
```
app/data/data_fetcher.py        → Fetch OHLCV, quotes, instruments
app/data/option_data_handler.py → Real-time option Greeks
app/core/websocket_client.py    → WebSocket streaming
```

### Trading Logic
```
app/managers/order_manager.py      → Place/cancel orders
app/managers/position_manager.py   → Manage open positions
app/managers/risk_manager.py       → Risk analysis & limits
app/managers/paper_trading.py      → Simulated trading
```

### Strategies
```
app/strategies/strategy.py    → Technical indicators (RSI, EMA, MACD, BB, etc)
app/strategies/backtester.py  → Backtest on historical data
app/strategies/reasoning.py   → Trade reasoning & decision making
```

### Utilities
```
app/utils/json_utils.py         → JSON serialization
app/utils/ai_data_collector.py  → Collect ML training data
```

### Options Greeks
```
app/core/greeks.py → Black-Scholes Greeks calculation
```

### Tests
```
tests/test_*.py → All unit tests
```

### Data Files
```
data/NSE.csv                   → Instrument master (7000+ contracts)
data/ai_training_data.csv      → ML training data
data/paper_trading_data.json    → Paper account state
data/positions_data.json        → Positions state
```

---

## 🔄 Common Imports

### Config & Auth
```python
from app.core.config import Config
from app.core.authentication import Authenticator
from app.core.logger_config import logger
```

### Data
```python
from app.data.data_fetcher import DataFetcher
from app.data.option_data_handler import OptionDataHandler
from app.core.websocket_client import MarketDataSocket
```

### Strategies
```python
from app.strategies.strategy import StrategyEngine
from app.strategies.backtester import Backtester
from app.strategies.reasoning import TradingReasoning
```

### Managers
```python
from app.managers.order_manager import OrderManager
from app.managers.position_manager import PositionManager
from app.managers.risk_manager import RiskManager
from app.managers.paper_trading import PaperTradingManager
```

### Greeks
```python
from app.core.greeks import GreeksCalculator
```

---

## 🚀 Quick Commands

### Run Bot
```bash
cd backend
python3 main.py
```

### Run API Server
```bash
python3 server.py
```

### Run Tests
```bash
python3 -m pytest tests/
python3 tests/test_option_data_handler.py
```

### Check Imports
```bash
python3 -c "from app.core.config import Config; print('✅ OK')"
python3 -c "from app.data.data_fetcher import DataFetcher; print('✅ OK')"
```

---

## 📊 Module Dependencies

```
No dependencies
├─ app/core/

app/core/ dependencies
├─ app/data/
├─ app/managers/
└─ app/strategies/

app/data/ dependencies
└─ app/core/

app/managers/ dependencies
├─ app/core/
└─ app/data/

app/strategies/ dependencies
├─ app/core/
├─ app/data/
└─ app/managers/
```

---

## 📋 File Locations

| File | New Location |
|------|-------------|
| config.py | app/core/config.py |
| authentication.py | app/core/authentication.py |
| logger_config.py | app/core/logger_config.py |
| websocket_client.py | app/core/websocket_client.py |
| greeks.py | app/core/greeks.py |
| data_fetcher.py | app/data/data_fetcher.py |
| option_data_handler.py | app/data/option_data_handler.py |
| order_manager.py | app/managers/order_manager.py |
| position_manager.py | app/managers/position_manager.py |
| risk_manager.py | app/managers/risk_manager.py |
| paper_trading.py | app/managers/paper_trading.py |
| strategy.py | app/strategies/strategy.py |
| backtester.py | app/strategies/backtester.py |
| reasoning.py | app/strategies/reasoning.py |
| json_utils.py | app/utils/json_utils.py |
| ai_data_collector.py | app/utils/ai_data_collector.py |
| test_*.py | tests/test_*.py |

---

## ✅ Status

- ✅ Folders created
- ✅ Files moved & copied
- ✅ Imports updated
- ✅ __init__.py files created
- ✅ Tests verified
- ✅ Documentation complete
- ✅ Ready for production

---

**Last Updated**: Nov 24, 2025
