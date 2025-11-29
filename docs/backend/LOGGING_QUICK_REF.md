# Quick Reference - Backend Logging

## TL;DR

**Logs are automatically created and stored in:**
```
backend/logs/niftybot_YYYY-MM-DD_HH-MM-SS.log
```

## Viewing Logs

### Terminal
```bash
# Watch logs in real-time
tail -f backend/logs/niftybot_*.log

# View last 50 lines
tail -50 backend/logs/niftybot_*.log

# Search for errors
grep ERROR backend/logs/*.log
```

### API (from frontend or curl)
```bash
# Get current (latest) log
curl http://localhost:8000/logs/current

# Get all log files
curl http://localhost:8000/logs/files

# Get specific log file
curl "http://localhost:8000/logs/file/niftybot_2025-11-23_14-30-45.log"
```

## What's Logged

| Event | Example |
|-------|---------|
| Server Start | `🚀 NiftyBot Backend Started - Log File: logs/niftybot_2025-11-23_14-30-45.log` |
| API Call | `🟢 POST /start - Starting bot` |
| Backtest | `📊 POST /backtest - Backtest request: 2025-06-05 to 2025-11-23` |
| Success | `✅ Backtest complete: 22 trades, Return: 0.65%` |
| Error | `❌ Error starting bot: Connection refused` |

## Log Levels

- **DEBUG** (file only): Detailed info for troubleshooting
- **INFO** (console + file): Important events
- **WARNING** (console + file): Warning messages
- **ERROR** (console + file): Errors with tracebacks

## Files Modified

1. `backend/logger_config.py` - NEW: Logger setup
2. `backend/server.py` - MODIFIED: Added logging to endpoints
3. `backend/data_fetcher.py` - MODIFIED: Ready for logging
4. `backend/backtester.py` - MODIFIED: Uses logger for backtest logs
5. `backend/.gitignore` - NEW: Excludes logs from git
6. `backend/LOGGING.md` - NEW: Full documentation

## Key Features

✅ Automatic timestamped log files
✅ One file per server restart
✅ API endpoints to view logs
✅ Full error tracebacks
✅ Minimal performance impact
✅ Git safe (excluded from commits)

## Common Commands

```bash
# View current server logs
curl -s http://localhost:8000/logs/current | jq -r '.log'

# List all log files
curl -s http://localhost:8000/logs/files | jq '.files'

# Search for backtest logs
grep "📊" backend/logs/*.log

# Monitor logs in real-time
watch -n 1 'tail -20 backend/logs/niftybot_*.log'

# Count total log entries
wc -l backend/logs/*.log
```

## Troubleshooting

**No logs appearing?**
- Check if `backend/logs/` directory exists
- Verify server is running: `curl http://localhost:8000/status`
- Check write permissions: `ls -l backend/logs/`

**Logs too large?**
- Delete old files: `find backend/logs -name "*.log" -mtime +7 -delete`
- Archive to backup location

**Need more details?**
- Read `backend/LOGGING.md` for comprehensive guide
