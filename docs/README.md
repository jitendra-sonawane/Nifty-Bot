# Documentation Index

This directory contains all project documentation organized by category.

## 📁 Directory Structure

### `/features`
Feature implementation documentation and plans:
- [`SIGNAL_IMPROVEMENTS.md`](features/SIGNAL_IMPROVEMENTS.md) - Signal generation enhancements
- [`SUPPORT_RESISTANCE_FEATURE.md`](features/SUPPORT_RESISTANCE_FEATURE.md) - Support/resistance level detection
- [`REALTIME_GREEKS_STREAMING.md`](features/REALTIME_GREEKS_STREAMING.md) - Real-time Greeks data streaming
- [`TIMESCALEDB_IMPLEMENTATION_PLAN.md`](features/TIMESCALEDB_IMPLEMENTATION_PLAN.md) - TimescaleDB integration plan

### `/fixes`
Bug fixes and troubleshooting documentation:
- **Authentication Fixes**: `AUTH_*.md` files documenting authentication flow fixes
- **Dashboard Fixes**: `DASHBOARD_*.md` files for UI/data display issues
- **Greeks Fixes**: `GREEKS_*.md` files for option Greeks calculation fixes
- [`PAPER_TRADING_PNL_FIX.md`](fixes/PAPER_TRADING_PNL_FIX.md) - Paper trading P&L fix
- [`QUICK_FIX_REFERENCE.md`](fixes/QUICK_FIX_REFERENCE.md) - Quick reference for common fixes

### `/guides`
Setup and usage guides:
- [`SETUP.md`](guides/SETUP.md) - Project setup instructions
- **Token Validation**: `TOKEN_VALIDATION_*.md` files for auth token handling
- [`UPSTOX_WEBSOCKET_BINARY_MESSAGE_GUIDE.md`](guides/UPSTOX_WEBSOCKET_BINARY_MESSAGE_GUIDE.md) - WebSocket integration guide

### `/architecture`
System architecture and design documentation:
- [`BACKEND_FLOWCHART.md`](architecture/BACKEND_FLOWCHART.md) - Backend architecture flowchart
- [`ARCHITECTURE_FIXES_SUMMARY.md`](architecture/ARCHITECTURE_FIXES_SUMMARY.md) - Architecture improvements
- [`BEFORE_AFTER_COMPARISON.md`](architecture/BEFORE_AFTER_COMPARISON.md) - Refactoring comparisons
- [`CODE_CHANGES_DETAIL.md`](architecture/CODE_CHANGES_DETAIL.md) - Detailed code change documentation
- [`DATA_FLOW_TEST.md`](architecture/DATA_FLOW_TEST.md) - Data flow testing documentation

### `/backend`
Backend-specific documentation:
- [`LOGGING.md`](backend/LOGGING.md) - Logging system documentation
- [`LOGGING_QUICK_REF.md`](backend/LOGGING_QUICK_REF.md) - Quick logging reference
- [`QUICK_REFERENCE.md`](backend/QUICK_REFERENCE.md) - Backend quick reference
- [`REORGANIZATION.md`](backend/REORGANIZATION.md) - Backend reorganization notes
- [`STRUCTURE.md`](backend/STRUCTURE.md) - Backend project structure

### `/walkthroughs`
Implementation walkthroughs and verification:
- `IMPLEMENTATION_*.md` - Various implementation walkthroughs
- [`VERIFICATION_CHECKLIST.md`](walkthroughs/VERIFICATION_CHECKLIST.md) - Feature verification checklist
- [`WALKTHROUGH.md`](walkthroughs/WALKTHROUGH.md) - General project walkthrough

## 🚀 Quick Start

1. **New to the project?** Start with [`guides/SETUP.md`](guides/SETUP.md)
2. **Understanding the architecture?** Check [`architecture/BACKEND_FLOWCHART.md`](architecture/BACKEND_FLOWCHART.md)
3. **Running into issues?** See [`fixes/QUICK_FIX_REFERENCE.md`](fixes/QUICK_FIX_REFERENCE.md)
4. **Implementing features?** Browse the [`features/`](features/) directory

## 📝 Contributing

When adding new documentation:
- Place feature docs in `/features`
- Place bug fix documentation in `/fixes`
- Place setup/usage guides in `/guides`
- Place architecture docs in `/architecture`
- Update this README index accordingly
