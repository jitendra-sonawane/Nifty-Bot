# TimescaleDB Integration for Trading Bot

This plan implements TimescaleDB to replace in-memory/JSON storage with a high-performance time-series database optimized for tick data, historical backtesting, and analytics.

## User Review Required

> [!IMPORTANT]
> **Data Migration**: Existing positions and paper trading data in JSON files will be migrated to the database. Original JSON files will be retained as backup.

> [!IMPORTANT]
> **Docker Dependency**: TimescaleDB will run as a Docker container. The bot will depend on this service being available.

> [!WARNING]
> **Breaking Change**: Database connection configuration will be required. A new `.env` variable `DATABASE_URL` must be set (default will be provided for Docker setup).

---

## Proposed Changes

### Infrastructure

#### [NEW] [docker-compose.yml](file:///Users/jitendrasonawane/Workpace/docker-compose.yml)

Add TimescaleDB service to existing docker-compose configuration:
- TimescaleDB 2.13-pg16 container
- Persistent volume for data storage (`timescaledb_data`)
- Network connectivity with backend service
- Health checks for service availability
- Credentials via environment variables

#### [NEW] [backend/.env.example](file:///Users/jitendrasonawane/Workpace/backend/.env.example)

Update example environment file with database configuration:
```
DATABASE_URL=postgresql://niftybot:password@timescaledb:5432/trading_bot
```

---

### Database Layer

#### [NEW] [backend/app/database/connection.py](file:///Users/jitendrasonawane/Workpace/backend/app/database/connection.py)

Database connection manager with async support:
- SQLAlchemy async engine creation
- Connection pooling (pool_size=20, max_overflow=10)
- Session factory with context manager
- Health check utilities

#### [NEW] [backend/app/database/models.py](file:///Users/jitendrasonawane/Workpace/backend/app/database/models.py)

SQLAlchemy ORM models for all time-series data:
- `TickData`: Tick-level market data (OHLCV, timestamp, instrument_key)
- `GreeksData`: Option Greeks history (delta, gamma, theta, vega, iv, strike, expiry)
- `TradeHistory`: Complete trade records (entry/exit, P&L, signal type)
- `Position`: Open positions (current state, stop loss, target)
- `MarketIndicators`: PCR, VIX, sentiment snapshots
- `BacktestResult`: Backtest run metadata and performance metrics

#### [NEW] [backend/app/database/schema.sql](file:///Users/jitendrasonawane/Workpace/backend/app/database/schema.sql)

TimescaleDB-specific schema setup:
- Hypertable creation for `tick_data` (partitioned by time, 1-day chunks)
- Hypertable creation for `greeks_data` (partitioned by time, 1-day chunks)
- Composite indexes on (timestamp, instrument_key) for fast lookups
- Retention policies: keep tick data for 30 days, aggregates forever
- Continuous aggregates for 1-min, 5-min, 1-hour OHLC candles
- Compression policies for data older than 7 days

#### [NEW] [backend/app/database/repository.py](file:///Users/jitendrasonawane/Workpace/backend/app/database/repository.py)

Data access layer with async methods:
- `insert_tick_data(tick)`: Bulk insert tick data
- `insert_greeks_data(greeks)`: Persist Greeks snapshots
- `get_historical_ticks(symbol, from_date, to_date)`: Query tick history
- `get_ohlc_candles(symbol, interval, from_date, to_date)`: Fetch OHLC from continuous aggregates
- `save_position(position)`: Persist position state
- `close_position(position_id, exit_price)`: Update position on close
- `save_trade(trade)`: Record completed trade
- `get_trades(from_date, to_date)`: Query trade history
- All methods use async/await for non-blocking I/O

---

### Core Integration

#### [MODIFY] [backend/app/core/market_data.py](file:///Users/jitendrasonawane/Workpace/backend/app/core/market_data.py)

Integrate database persistence in `MarketDataManager`:
- Add `repository` dependency injection in `__init__`
- Update `_on_streamer_message()` to persist tick data asynchronously
- Batch tick inserts every 5 seconds or 100 ticks (whichever comes first)
- Error handling: log failures but don't crash on DB errors
- Metrics: track tick ingestion rate and DB latency

#### [MODIFY] [backend/app/data/option_data_handler.py](file:///Users/jitendrasonawane/Workpace/backend/app/data/option_data_handler.py)

Persist Greeks calculations in `OptionDataHandler`:
- Add `repository` dependency in `__init__`
- Update `_emit_greeks_update()` to save Greeks to database
- Store: timestamp, instrument_key, strike, expiry, option_type, delta, gamma, theta, vega, iv, underlying_price
- Asynchronous inserts to avoid blocking WebSocket callbacks

#### [MODIFY] [backend/app/managers/position_manager.py](file:///Users/jitendrasonawane/Workpace/backend/app/managers/position_manager.py)

Replace JSON file persistence with database:
- Remove `_load_positions()` and `_save_positions()` JSON methods
- Add `repository` dependency
- Update `open_position()` to insert into database
- Update `close_position()` to update position status and create trade record
- Load open positions from database on startup
- Migration helper: load existing JSON data and seed database on first run

---

### Backtesting Enhancement

#### [MODIFY] [backend/app/strategies/backtester.py](file:///Users/jitendrasonawane/Workpace/backend/app/strategies/backtester.py)

Use real historical data from TimescaleDB:
- Add `repository` dependency
- Update `run_backtest()` to query historical OHLC from database
- Fall back to mock data only if database has no data for date range
- Store backtest results in database (run_id, parameters, metrics, trade list)
- Log data source (DB vs. mock) in results

---

### Server Configuration

#### [MODIFY] [backend/server.py](file:///Users/jitendrasonawane/Workpace/backend/server.py)

Initialize database on FastAPI startup:
- Add database connection initialization in `startup_event()`
- Run schema migrations automatically (create tables, hypertables, policies)
- Pass `repository` to `MarketDataManager`, `OptionDataHandler`, `PositionManager`
- Add `/health/db` endpoint to check database connectivity
- Graceful shutdown: close database connections in `shutdown_event()`

#### [MODIFY] [backend/requirements.txt](file:///Users/jitendrasonawane/Workpace/backend/requirements.txt)

Add required dependencies:
```
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
```

---

### Migration Utility

#### [NEW] [backend/app/database/migrate_json.py](file:///Users/jitendrasonawane/Workpace/backend/app/database/migrate_json.py)

One-time migration script:
- Read `positions_data.json` and `paper_trading_data.json`
- Insert existing positions and trades into database
- Validate migration success
- Create backup of JSON files (`.json.bak`)
- Can be run manually or auto-triggered on first startup if tables are empty

---

## Verification Plan

### Automated Tests

#### 1. Database Connection Test
```bash
cd /Users/jitendrasonawane/Workpace/backend
python -m pytest tests/test_database_connection.py -v
```
Create `tests/test_database_connection.py` to verify:
- Database connection establishment
- Schema creation (tables, hypertables)
- Basic insert/query operations
- Connection pooling

#### 2. Data Persistence Test
```bash
cd /Users/jitendrasonawane/Workpace/backend
python -m pytest tests/test_data_persistence.py -v
```
Create `tests/test_data_persistence.py` to verify:
- Tick data insertion and retrieval
- Greeks data persistence
- Position lifecycle (open/update/close)
- Trade history recording
- Bulk insert performance (1000 ticks in <1s)

#### 3. Integration Test
```bash
cd /Users/jitendrasonawane/Workpace/backend
python -m pytest tests/test_timescaledb_integration.py -v
```
Create `tests/test_timescaledb_integration.py` to verify:
- MarketDataManager persists ticks during WebSocket streaming
- OptionDataHandler saves Greeks calculations
- PositionManager uses database instead of JSON
- Backtester retrieves historical data from database

### Manual Verification

#### 1. Start TimescaleDB Container
```bash
cd /Users/jitendrasonawane/Workpace
docker-compose up timescaledb -d
docker-compose logs -f timescaledb  # Verify successful startup
```

#### 2. Run Migration Script
```bash
cd /Users/jitendrasonawane/Workpace/backend
python -m app.database.migrate_json
# Verify: Check that positions from JSON are now in database
```

#### 3. Start Bot and Monitor Data Ingestion
```bash
cd /Users/jitendrasonawane/Workpace
docker-compose up backend -d
docker-compose logs -f backend

# Look for log messages:
# - "✅ Connected to TimescaleDB"
# - "💾 Persisted 100 ticks to database"
# - "📊 Greeks data saved to TimescaleDB"
```

#### 4. Query Database Directly
```bash
docker exec -it timescaledb psql -U niftybot -d trading_bot

# Run queries:
SELECT COUNT(*) FROM tick_data;
SELECT * FROM tick_data ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM greeks_data ORDER BY timestamp DESC LIMIT 5;
SELECT * FROM positions WHERE status = 'OPEN';
```

#### 5. Run Backtest with Historical Data
- Use frontend dashboard to trigger backtest
- Verify that backtest uses database data (check logs for "Using historical data from TimescaleDB")
- Compare results with previous mock data runs

#### 6. Verify Continuous Aggregates
```bash
docker exec -it timescaledb psql -U niftybot -d trading_bot

# Query 1-minute OHLC aggregate:
SELECT * FROM tick_data_1min ORDER BY bucket DESC LIMIT 10;

# Verify compression is working:
SELECT * FROM timescaledb_information.chunks WHERE is_compressed = true;
```

---

## Success Criteria

✅ TimescaleDB container runs alongside backend  
✅ All tick data from WebSocket persisted to database  
✅ Greeks calculations saved with timestamps  
✅ Positions migrated from JSON to database  
✅ Backtests use real historical data from database  
✅ OHLC continuous aggregates working (1min, 5min, 1hour)  
✅ Data retention policy automatically manages old data  
✅ No performance degradation (tick ingestion < 10ms latency)  
