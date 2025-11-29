# Backend Logging System Documentation

## Overview
The NiftyBot backend now has a comprehensive logging system that automatically creates timestamped log files whenever the server starts or restarts.

## Log File Location
- **Directory**: `backend/logs/`
- **File Format**: `niftybot_YYYY-MM-DD_HH-MM-SS.log`
- **Example**: `niftybot_2025-11-23_14-30-45.log`

## How It Works

### Automatic Log Creation
When the server starts, a new log file is automatically created with:
1. Current date and time in the filename
2. Server startup message with timestamp
3. All subsequent operations logged in real-time

### Log Levels
- **DEBUG**: Detailed information for debugging (written to file only)
- **INFO**: General informational messages (console + file)
- **WARNING**: Warning messages (console + file)
- **ERROR**: Error messages with full traceback (console + file)

### Log Format
```
2025-11-23 14:30:45 - niftybot - INFO - [server.py:150] - Message content
```

## Features Logged

### Server Operations
- Server startup/shutdown
- API endpoint access (GET/POST requests)
- Configuration changes
- Trading mode changes
- Fund additions

### Trading Operations
- Bot start/stop
- Position opens/closes with P&L
- Trade execution
- Signal generation
- Error handling

### Data Operations
- API requests to Upstox
- Data fetch operations
- Historical data loading
- Backtest execution with results

### Strategy Operations
- Signal calculations
- Indicator values
- Entry/exit conditions
- Risk management checks

## API Endpoints for Log Viewing

### 1. Get List of Log Files
```
GET /logs/files
```
Returns list of all available log files with metadata.

**Response:**
```json
{
  "files": [
    {
      "name": "niftybot_2025-11-23_14-30-45.log",
      "size": 15234,
      "modified": 1700735445
    }
  ]
}
```

### 2. Get Current Log (Latest)
```
GET /logs/current
```
Returns the most recent log file (last 500 lines).

**Response:**
```json
{
  "log": "2025-11-23 14:30:45 - niftybot - INFO - Server started...",
  "filename": "niftybot_2025-11-23_14-30-45.log",
  "total_lines": 1000,
  "returned_lines": 500
}
```

### 3. Get Specific Log File
```
GET /logs/file/{filename}
```
Returns a specific log file (last 1000 lines).

**Example:**
```
GET /logs/file/niftybot_2025-11-23_14-30-45.log
```

## Typical Log Flow

### Server Startup
```
2025-11-23 14:30:45 - niftybot - INFO - ================================================================================
2025-11-23 14:30:45 - niftybot - INFO - 🚀 NiftyBot Backend Started - Log File: logs/niftybot_2025-11-23_14-30-45.log
2025-11-23 14:30:45 - niftybot - INFO - 📅 Timestamp: 2025-11-23 14:30:45
2025-11-23 14:30:45 - niftybot - INFO - ================================================================================
2025-11-23 14:30:45 - niftybot - INFO - 🚀 Initializing FastAPI Server...
2025-11-23 14:30:45 - niftybot - INFO - ✅ CORS Middleware configured
```

### Bot Start Request
```
2025-11-23 14:31:00 - niftybot - INFO - 🟢 POST /start - Starting bot
2025-11-23 14:31:00 - niftybot - INFO - ✅ Bot started successfully. Status: {...}
```

### Backtest Execution
```
2025-11-23 14:31:15 - niftybot - INFO - 📊 POST /backtest - Backtest request: 2025-06-05 to 2025-11-23, Capital: ₹100,000.00
2025-11-23 14:31:15 - niftybot - INFO - 📥 Fetching data for NSE_INDEX|Nifty 50...
2025-11-23 14:31:16 - niftybot - INFO - ✅ Data loaded: 7500 candles
2025-11-23 14:31:20 - niftybot - INFO - ✅ Backtest complete: 22 trades, Return: 0.65%, Final Capital: ₹100,649.66
```

### Error Handling
```
2025-11-23 14:31:45 - niftybot - ERROR - ❌ Error starting bot: Connection refused
Traceback (most recent call last):
  File "server.py", line 55, in start_bot
    bot.start()
  ...
```

## Log Viewing

### Via API (Recommended)
Use the logging endpoints from the Dashboard or frontend:
- Latest logs: `GET /logs/current`
- All log files: `GET /logs/files`

### Via Command Line
```bash
# View latest log file
tail -f backend/logs/niftybot_*.log

# Search for errors
grep "ERROR" backend/logs/niftybot_*.log

# Count log entries
wc -l backend/logs/niftybot_*.log
```

### Via File System
```bash
cd backend/logs
ls -lh
# View specific file
cat niftybot_2025-11-23_14-30-45.log
```

## Log Cleanup

### Disk Space Management
Old log files can be safely deleted:
```bash
# Remove logs older than 30 days
find backend/logs -name "*.log" -mtime +30 -delete

# Remove all logs except last 5
ls -t backend/logs/*.log | tail -n +6 | xargs rm -f
```

### Suggested Policy
- Keep logs for last 30 days
- Archive older logs separately
- Monitor disk usage

## Troubleshooting

### No Logs Directory
If the `logs/` directory doesn't exist:
1. It will be created automatically on first server start
2. Check write permissions in `backend/` directory

### Log File Not Found
1. Check that the server is running: `GET /status`
2. Verify logs directory exists: `backend/logs/`
3. Check file permissions: `ls -l backend/logs/`

### Missing Log Entries
1. Check log level settings in `logger_config.py`
2. Ensure logger is properly imported in modules
3. Verify write permissions to log file

## Integration with Frontend

The logs can be displayed in the Dashboard sidebar by integrating with the `/logs/current` endpoint.

Example integration:
```typescript
const response = await fetch('http://localhost:8000/logs/current');
const data = await response.json();
setLogs(data.log);
```

## Security Considerations

1. **Log File Access**: Protected via `/logs/` endpoints with directory traversal prevention
2. **Sensitive Data**: Avoid logging passwords, API keys, or tokens
3. **File Permissions**: Logs are readable by the application user only
4. **Disk Space**: Monitor to prevent disk full errors

## Performance Impact

- **File I/O**: Minimal impact (async writes)
- **Memory**: Logger uses standard Python logging (low overhead)
- **Disk Usage**: ~1-5 MB per day depending on activity

## Best Practices

1. **Regular Review**: Check logs daily for errors
2. **Archive Old Logs**: Remove logs older than 30 days
3. **Monitor Errors**: Set up alerts for ERROR level logs
4. **Performance Analysis**: Use logs to identify slow operations
5. **Debugging**: Enable DEBUG logs when troubleshooting

---

**Created**: 2025-11-23  
**Last Updated**: 2025-11-23  
**Version**: 1.0
