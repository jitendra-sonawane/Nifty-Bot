# Setup Guide - Upstox Trading Bot

A comprehensive guide to set up and run the Upstox Trading Bot with both backend and frontend components.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Overview](#project-overview)
3. [Backend Setup](#backend-setup)
4. [Frontend Setup](#frontend-setup)
5. [Running the Application](#running-the-application)
6. [Initial Configuration](#initial-configuration)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **macOS** (or Linux/Windows with appropriate command adjustments)
- **Python 3.8+** (for backend)
- **Node.js 16+** (for frontend)
- **npm 8+** (for frontend)
- **Git** (for version control)

### Required Accounts
- **Upstox Account** - Sign up at [upstox.com](https://upstox.com)
  - Generate API credentials (API Key, Secret)
  - Set a Redirect URI for OAuth flow

### Install Required Tools

#### Python Installation
```bash
# Check if Python is installed
python3 --version

# If not installed, use Homebrew on macOS
brew install python3
```

#### Node.js Installation
```bash
# Check if Node is installed
node --version
npm --version

# If not installed, use Homebrew on macOS
brew install node
```

---

## Project Overview

This project is a full-stack trading bot application:

### **Backend** (`/backend`)
- FastAPI server for REST API endpoints
- Upstox WebSocket integration for real-time market data
- Trading strategies with technical indicators (RSI, EMA, MACD, Bollinger Bands)
- Paper trading simulation
- Position and risk management
- Historical backtesting

### **Frontend** (`/frontend`)
- React + TypeScript UI dashboard
- Real-time trading data visualization
- Strategy backtesting interface
- Position management view
- Live Greeks and market data display

---

## Backend Setup

### Step 1: Navigate to Backend Directory
```bash
cd /Users/jitendrasonawane/Workpace/backend
```

### Step 2: Create Python Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# You should see (venv) at the start of your terminal prompt
```

### Step 3: Install Python Dependencies
```bash
# Ensure pip is up to date
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt
```

**Dependencies Overview:**
- `upstox-python-sdk` - Upstox API client
- `pandas` - Data manipulation
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `scipy` - Scientific computing
- `websocket-client` - WebSocket connection
- `python-dotenv` - Environment variable management

### Step 4: Configure Environment Variables
```bash
# Copy example environment file
cp .env.example .env

# Edit the .env file with your credentials
nano .env
```

**Required Environment Variables:**
```
UPSTOX_API_KEY=your_api_key_here
UPSTOX_API_SECRET=your_api_secret_here
UPSTOX_REDIRECT_URI=http://localhost:5000/callback
ACCESS_TOKEN=your_access_token_here  # Optional - will be generated on first run
```

### Step 5: Verify Backend Installation
```bash
# Test Python environment
python -c "import upstox; import fastapi; print('✓ Backend dependencies installed')"
```

---

## Frontend Setup

### Step 1: Navigate to Frontend Directory
```bash
cd /Users/jitendrasonawane/Workpace/frontend
```

### Step 2: Install Node Dependencies
```bash
# Install packages
npm install
```

**Key Dependencies:**
- `react` - UI library
- `react-redux` - State management
- `axios` - HTTP client
- `tailwindcss` - CSS framework
- `vite` - Build tool
- `typescript` - Type safety
- `lucide-react` - Icon library

### Step 3: Verify Frontend Installation
```bash
# Check if build works
npm run build

# If successful, you'll see a "dist/" folder created
```

---

## Running the Application

### Option A: Run Separately (Development)

#### Terminal 1: Start Backend Server
```bash
cd /Users/jitendrasonawane/Workpace/backend

# Activate virtual environment
source venv/bin/activate

# Start FastAPI server
python server.py

# Or use Uvicorn directly
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`

#### Terminal 2: Start Frontend Development Server
```bash
cd /Users/jitendrasonawane/Workpace/frontend

# Start Vite dev server
npm run dev
```

Frontend will be available at: `http://localhost:5173` (or as shown in terminal)

### Option B: Run Backend Only (Production)

```bash
cd /Users/jitendrasonawane/Workpace/backend

source venv/bin/activate

# Production server
uvicorn server:app --host 0.0.0.0 --port 8000
```

---

## Initial Configuration

### First-Time Login (Upstox OAuth)

1. **Start the application** following the steps above
2. **Access the frontend** at `http://localhost:5173`
3. **Click "Login with Upstox"** button
4. **You'll be redirected** to Upstox login page
5. **Login** with your Upstox credentials
6. **Authorize** the application to access your account
7. **You'll be redirected back** to the app with an access token
8. **Token will be saved** for future sessions

### Save Access Token

The access token is automatically saved in your browser's local storage. To manually save it to `.env`:

```bash
# Edit .env file
nano .env

# Add your token
ACCESS_TOKEN=your_token_here
```

### Configure Trading Parameters

Edit `backend/app/core/config.py` to customize:
- Trading timeframes (default: 5-minute)
- RSI parameters (thresholds)
- EMA periods (fast & slow)
- Position sizing
- Risk limits

---

## Running Tests

### Backend Tests
```bash
cd /Users/jitendrasonawane/Workpace/backend

source venv/bin/activate

# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_backtester.py -v

# Run with coverage
python -m pytest tests/ --cov=app
```

**Available Tests:**
- `test_backtester.py` - Strategy backtesting
- `test_greeks.py` - Greeks calculation
- `test_option_data_handler.py` - Real-time data handling
- `test_upstox.py` - API integration
- `test_trailing_stop.py` - Stop loss logic

### Frontend Tests
```bash
cd /Users/jitendrasonawane/Workpace/frontend

# Run linter
npm run lint

# Build for production
npm run build
```

---

## Project Structure

### Backend (`/backend/app/`)
```
app/
├── core/              # Configuration, auth, WebSocket
├── data/              # Data fetching & streaming
├── managers/          # Order, position, risk management
├── strategies/        # Trading logic & backtesting
├── utils/             # Helper functions
└── tests/             # Test suite
```

### Frontend (`/frontend/src/`)
```
src/
├── App.tsx            # Main application component
├── Dashboard.tsx      # Main dashboard view
├── apiSlice.ts        # Redux API slice
├── store.ts           # Redux store configuration
├── components/        # Reusable UI components
└── assets/            # Static files
```

---

## Environment Variables Reference

### Backend (.env)
| Variable | Description | Example |
|----------|-------------|---------|
| `UPSTOX_API_KEY` | Your Upstox API key | `abc123xyz...` |
| `UPSTOX_API_SECRET` | Your Upstox API secret | `secret123...` |
| `UPSTOX_REDIRECT_URI` | OAuth redirect URL | `http://localhost:5000/callback` |
| `ACCESS_TOKEN` | Upstox access token | `token123...` |

---

## Common Issues & Troubleshooting

### Python Virtual Environment Issues
```bash
# Virtual environment not activating?
# Make sure you're in the backend directory
cd /Users/jitendrasonawane/Workpace/backend

# Try explicit path to activate
source ./venv/bin/activate

# Deactivate and reactivate
deactivate
source venv/bin/activate
```

### Dependencies Installation Fails
```bash
# Update pip, setuptools, wheel
pip install --upgrade pip setuptools wheel

# Try installing requirements again
pip install -r requirements.txt

# If specific package fails, install individually
pip install upstox-python-sdk
```

### API Authentication Errors
- Verify Upstox API key & secret in `.env`
- Ensure Redirect URI matches Upstox console settings
- Check if access token has expired (requires re-login)
- Verify API credentials have correct permissions

### Port Already in Use
```bash
# If port 8000 is in use, use different port
uvicorn server:app --port 8001

# For frontend, Vite will suggest different port
npm run dev
```

### WebSocket Connection Issues
- Ensure backend is running on correct port
- Check network connectivity
- Verify WebSocket URL in frontend configuration
- Check browser console for errors

### Build Failures
```bash
# Clear node modules and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install

# Clear build cache
rm -rf dist
npm run build
```

---

## Development Workflow

### 1. Feature Development
```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes to backend or frontend
# Test changes locally
npm run dev  # Frontend
python server.py  # Backend

# Run tests
npm run lint  # Frontend
python -m pytest tests/  # Backend
```

### 2. Testing Before Deployment
```bash
# Backend tests
cd backend
python -m pytest tests/ -v

# Frontend build
cd frontend
npm run build

# Check for TypeScript errors
npx tsc --noEmit
```

### 3. Deployment
```bash
# Production build
npm run build

# Start production server
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Next Steps

1. ✅ Complete setup using this guide
2. 📖 Read `backend/README.md` for backend-specific details
3. 📖 Read `frontend/README.md` for frontend-specific details
4. 🧪 Run tests to verify installation
5. 🔧 Configure trading parameters in `backend/app/core/config.py`
6. 📊 Start paper trading to test strategies
7. 📚 Review strategy code in `backend/app/strategies/`

---

## Support & Additional Resources

- **Upstox API Docs**: https://upstox.com/developers/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **React Docs**: https://react.dev/
- **Vite Docs**: https://vitejs.dev/

---

## Version History

- **v1.0** - Initial setup guide
- Last Updated: November 27, 2025

