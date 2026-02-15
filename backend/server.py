from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from main import bot
import uvicorn
import asyncio
import os
import time
from typing import Optional, List
from app.core.authentication import Authenticator
from app.core.config import Config
from app.core.logger_config import logger
from app.utils.json_utils import convert_numpy_types
from app.data.option_data_handler import OptionDataHandler
from pathlib import Path

app = FastAPI(title="Upstox Trading Bot API")

logger.info("🚀 Initializing FastAPI Server...")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("✅ CORS Middleware configured")

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients, remove dead connections"""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.debug(f"Error sending to WebSocket: {e}")
                dead_connections.append(connection)
        
        # Remove dead connections
        for conn in dead_connections:
            await self.disconnect(conn)

manager = ConnectionManager()

# Option Data Handler
option_data_handler: Optional[OptionDataHandler] = None

@app.on_event("startup")
async def startup_event():
    global option_data_handler
    try:
        bot.initialize()
        
        # Set callback for bot status updates
        # Since bot is now async, it calls this callback. 
        # We need to make sure the callback can run async broadcast.
        # The bot calls status_callback(status).
        # We can define a wrapper.
        
        async def status_callback_handler(status):
            """Async wrapper for status broadcasts"""
            try:
                # Ensure all numpy types are converted to native Python types before serialization
                clean_status = convert_numpy_types(status)
                await manager.broadcast(clean_status)
            except Exception as e:
                logger.error(f"Error broadcasting status: {e}")
        
        bot.status_callback = status_callback_handler
        
        logger.info("🟢 Bot initialized and status callback configured")
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    await bot.stop()
    logger.info("🔴 Server shutdown complete")

@app.get("/")
def read_root():
    return {"message": "Upstox Trading Bot API is running (Async)"}

@app.get("/auth/status")
def get_auth_status():
    """Check if Upstox access token is valid"""
    token_status = Config.is_token_valid()
    return {
        "authenticated": token_status["is_valid"],
        "token_status": token_status
    }

@app.get("/status")
def get_status():
    """Get current bot status with fresh token validation"""
    status = convert_numpy_types(bot.get_status())
    
    # Always validate token fresh from environment (not from cache)
    # This ensures we get the latest token validity after auth callback
    import os
    from dotenv import load_dotenv
    import json
    import base64
    import time
    
    # Reload .env to get the latest token
    load_dotenv(override=True)
    fresh_token = os.getenv("UPSTOX_ACCESS_TOKEN")
    
    # Validate the fresh token directly (don't use cached Config value)
    if fresh_token:
        try:
            # Decode JWT (without verification, just for diagnostics)
            parts = fresh_token.split('.')
            if len(parts) == 3:
                payload = parts[1]
                padding = 4 - len(payload) % 4
                if padding != 4:
                    payload += '=' * padding
                
                decoded = json.loads(base64.urlsafe_b64decode(payload))
                
                current_time = time.time()
                exp_time = decoded.get('exp', 0)
                remaining = exp_time - current_time
                
                logger.info(f"🔍 DEBUG: Token Validation - Current Time: {current_time}, Exp Time: {exp_time}, Remaining: {remaining}")
                logger.info(f"🔍 DEBUG: Token Snippet: {fresh_token[:20]}...{fresh_token[-20:]}")
                
                if remaining > 0:
                    token_status = {
                        "is_valid": True,
                        "expires_at": exp_time,
                        "remaining_seconds": int(remaining),
                        "error_message": None
                    }
                else:
                    token_status = {
                        "is_valid": False,
                        "expires_at": exp_time,
                        "remaining_seconds": int(remaining),
                        "error_message": f"Access token expired {int(abs(remaining))} seconds ago"
                    }
            else:
                token_status = {
                    "is_valid": False,
                    "expires_at": None,
                    "remaining_seconds": 0,
                    "error_message": "Invalid token format (not JWT)"
                }
        except Exception as e:
            token_status = {
                "is_valid": False,
                "expires_at": None,
                "remaining_seconds": 0,
                "error_message": f"Error validating token: {str(e)}"
            }
    else:
        token_status = {
            "is_valid": False,
            "expires_at": None,
            "remaining_seconds": 0,
            "error_message": "No access token found"
        }
    
    # Combined authentication status
    data_fetcher_valid = getattr(bot.data_fetcher, "token_valid", "N/A") if bot.data_fetcher else "NoFetcher"
    
    # We are authenticated ONLY if the token is valid (time-wise) AND the API accepts it
    is_authenticated = token_status["is_valid"] and (data_fetcher_valid is True)
    
    status["auth"] = {
        "authenticated": is_authenticated,
        "token_status": token_status,
        "api_status": data_fetcher_valid
    }
    
    logger.debug(f"📊 Status endpoint: authenticated={is_authenticated} (Token: {token_status['is_valid']}, API: {data_fetcher_valid})")
    return status

@app.post("/start")
async def start_bot():
    try:
        logger.info("🟢 POST /start - Starting bot")
        await bot.start()
        return {"message": "Bot started successfully", "status": convert_numpy_types(bot.get_status())}
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop")
async def stop_bot():
    try:
        logger.info("🔴 POST /stop - Stopping bot")
        await bot.stop()
        return {"message": "Bot stopped successfully", "status": convert_numpy_types(bot.get_status())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
def get_logs():
    return {"logs": bot.latest_log}

class ConfigRequest(BaseModel):
    timeframe: str

@app.get("/config")
def get_config():
    status = convert_numpy_types(bot.get_status())
    return status.get("config", {})

@app.post("/config")
def update_config(request: ConfigRequest):
    result = bot.update_config(timeframe=request.timeframe)
    return convert_numpy_types(result)

class ModeRequest(BaseModel):
    mode: str

@app.post("/mode")
def set_mode(request: ModeRequest):
    result = bot.set_trading_mode(request.mode)
    return convert_numpy_types(result)

class FundsRequest(BaseModel):
    amount: float

@app.post("/paper/funds")
def add_funds(request: FundsRequest):
    result = bot.add_paper_funds(request.amount)
    return convert_numpy_types(result)

class ClosePositionRequest(BaseModel):
    position_id: str
    exit_price: float

@app.post("/positions/close")
def close_position(request: ClosePositionRequest):
    paper_mgr = bot.order_manager.paper_manager if (bot.order_manager and bot.order_manager.paper_manager) else None

    # Try multi-leg position first (PaperTradingManager)
    if paper_mgr and request.position_id in paper_mgr.positions:
        pos = paper_mgr.positions[request.position_id]
        # Update each leg's current price to the provided exit price
        for leg in pos.legs:
            leg.current_price = request.exit_price
        trade = paper_mgr.close_position(request.position_id, exit_reason="MANUAL_CLOSE")
        if trade:
            return {"message": "Closed", "trade": convert_numpy_types(trade.to_dict())}

    # Fallback: single-leg position (PositionManager)
    if not bot.position_manager:
        raise HTTPException(status_code=400, detail="Manager not initialized")

    trade = bot.position_manager.close_position(
        position_id=request.position_id,
        exit_price=request.exit_price,
        reason="MANUAL_CLOSE"
    )
    if trade:
        # Record into unified paper trading journal
        if paper_mgr:
            paper_mgr.record_single_leg_trade(trade)
        return {"message": "Closed", "trade": convert_numpy_types(trade)}

    raise HTTPException(status_code=404, detail="Position not found")

# Backtesting
class BacktestRequest(BaseModel):
    from_date: str
    to_date: str
    initial_capital: float = 100000
    strategy: str = "iron_condor"

@app.post("/backtest")
def run_backtest(request: BacktestRequest):
    """Run backtest for a specific strategy."""
    try:
        from app.strategies.backtester import StrategyBacktester
        from app.strategies.iron_condor import IronCondorStrategy
        from app.strategies.short_straddle import ShortStraddleStrategy
        from app.strategies.bull_bear_spread import BullCallSpreadStrategy, BearPutSpreadStrategy
        from app.strategies.breakout_strategy import BreakoutStrategy

        # Strategy registry
        strategies = {
            "iron_condor": IronCondorStrategy,
            "short_straddle": ShortStraddleStrategy,
            "bull_call_spread": BullCallSpreadStrategy,
            "bear_put_spread": BearPutSpreadStrategy,
            "breakout": BreakoutStrategy,
        }

        strategy_cls = strategies.get(request.strategy)
        if not strategy_cls:
            return {"error": f"Unknown strategy: {request.strategy}. Available: {list(strategies.keys())}"}

        backtester = StrategyBacktester(bot.data_fetcher if bot.data_fetcher else None)
        result = backtester.run(
            strategy=strategy_cls(),
            from_date=request.from_date,
            to_date=request.to_date,
            initial_capital=request.initial_capital,
        )
        return convert_numpy_types(result.to_dict())
    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        return {"error": str(e)}


# ─── Strategy Endpoints ────────────────────────────────────────────────────

@app.get("/strategies")
def list_strategies():
    """List all available strategies and their configurations."""
    from app.strategies.iron_condor import IronCondorStrategy
    from app.strategies.short_straddle import ShortStraddleStrategy
    from app.strategies.bull_bear_spread import BullCallSpreadStrategy, BearPutSpreadStrategy
    from app.strategies.breakout_strategy import BreakoutStrategy

    strategies = [
        IronCondorStrategy(),
        ShortStraddleStrategy(),
        BullCallSpreadStrategy(),
        BearPutSpreadStrategy(),
        BreakoutStrategy(),
    ]
    return {
        "active_strategy": Config.ACTIVE_STRATEGY,
        "trading_mode": Config.TRADING_MODE,
        "strategies": [s.get_info() for s in strategies],
    }

class SetStrategyRequest(BaseModel):
    strategy: str

# ─── Intelligence Engine Endpoints ─────────────────────────────────────────

class IntelligenceToggleRequest(BaseModel):
    module: str
    enabled: bool

@app.post("/intelligence/toggle")
def toggle_intelligence_module(request: IntelligenceToggleRequest):
    """Enable or disable an intelligence module by name."""
    engine = getattr(bot, "intelligence_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Intelligence engine not initialized")
    if request.module not in engine._modules:
        valid = list(engine._modules.keys())
        raise HTTPException(status_code=400, detail=f"Unknown module '{request.module}'. Valid: {valid}")
    if request.enabled:
        engine.enable(request.module)
    else:
        engine.disable(request.module)
    return {
        "module": request.module,
        "enabled": request.enabled,
        "modules": {name: mod.enabled for name, mod in engine._modules.items()},
    }

@app.get("/intelligence/status")
def get_intelligence_status():
    """Get current status of all intelligence modules."""
    engine = getattr(bot, "intelligence_engine", None)
    if engine is None:
        return {"modules": {}, "context": {}}
    return {
        "modules": {name: mod.enabled for name, mod in engine._modules.items()},
        "context": engine.get_context(),
    }

@app.post("/strategies/active")
def set_active_strategy(request: SetStrategyRequest):
    """Set the active trading strategy."""
    valid = ["iron_condor", "short_straddle", "bull_call_spread", "bear_put_spread", "breakout"]
    if request.strategy not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid strategy. Choose from: {valid}")
    Config.ACTIVE_STRATEGY = request.strategy
    return {"message": f"Active strategy set to {request.strategy}", "active_strategy": Config.ACTIVE_STRATEGY}


# ─── Option Chain Endpoints ────────────────────────────────────────────────

@app.get("/option-chain")
def get_option_chain(spot_price: float = 0):
    """Get current option chain data."""
    from app.core.option_chain import OptionChainManager

    chain = OptionChainManager()
    price = spot_price if spot_price > 0 else 23500  # Default to approximate Nifty
    chain.update(price, force=True)
    return convert_numpy_types(chain.get_chain_summary())


# ─── Paper Trading / Portfolio Endpoints ───────────────────────────────────

def _get_paper_mgr():
    """Return the live PaperTradingManager from the bot (single source of truth)."""
    if bot.order_manager and bot.order_manager.paper_manager:
        return bot.order_manager.paper_manager
    # Fallback: load from file if bot not yet initialized
    from app.managers.paper_trading import PaperTradingManager
    return PaperTradingManager()


@app.get("/portfolio")
def get_portfolio():
    """Get paper trading portfolio stats."""
    return convert_numpy_types(_get_paper_mgr().get_portfolio_stats())


@app.get("/portfolio/positions")
def get_open_positions_portfolio():
    """Get all open multi-leg positions from PaperTradingManager."""
    ptm = _get_paper_mgr()
    # Also include single-leg positions from PositionManager
    multi_leg = ptm.get_open_positions()
    single_leg = bot.position_manager.get_positions() if bot.position_manager else []
    return convert_numpy_types({"positions": multi_leg, "single_leg_positions": single_leg})


@app.get("/portfolio/history")
def get_trade_history(strategy: str = None, limit: int = 100):
    """Get unified trade history from PaperTradingManager, optionally filtered."""
    return convert_numpy_types({"trades": _get_paper_mgr().get_trade_history(strategy, limit)})


@app.get("/portfolio/stats")
def get_portfolio_stats():
    """Get detailed portfolio stats including win rate, P&L breakdown, strategy analytics."""
    return convert_numpy_types(_get_paper_mgr().get_portfolio_stats())


@app.post("/portfolio/reset")
def reset_portfolio():
    """Reset paper trading portfolio to initial capital."""
    ptm = _get_paper_mgr()
    ptm.reset()
    return {"message": "Portfolio reset", "stats": convert_numpy_types(ptm.get_portfolio_stats())}


# ─── Risk Management Endpoints ────────────────────────────────────────────

@app.get("/risk")
def get_risk_stats():
    """Get current risk management stats."""
    from app.managers.risk_manager import RiskManager
    rm = RiskManager()
    return convert_numpy_types(rm.get_stats())


# ─── Sandbox Endpoints ────────────────────────────────────────────────────

class SandboxOrderRequest(BaseModel):
    instrument_token: str
    quantity: int
    transaction_type: str  # BUY or SELL
    order_type: str = "MARKET"
    price: float = 0.0

@app.post("/sandbox/order")
def place_sandbox_order(request: SandboxOrderRequest):
    """Place an order via Upstox Sandbox API."""
    from app.core.sandbox_executor import SandboxExecutor
    executor = SandboxExecutor()
    result = executor.place_order(
        instrument_token=request.instrument_token,
        quantity=request.quantity,
        transaction_type=request.transaction_type,
        order_type=request.order_type,
        price=request.price,
    )
    if result:
        return {"status": "success", "order": result}
    raise HTTPException(status_code=400, detail="Order placement failed")

@app.get("/sandbox/orders")
def get_sandbox_orders():
    """Get sandbox order history."""
    from app.core.sandbox_executor import SandboxExecutor
    executor = SandboxExecutor()
    orders = executor.fetch_live_orders()
    return {"orders": orders or []}


# ─── Nifty 50 Heatmap ─────────────────────────────────────────────────────

@app.get("/api/nifty50/heatmap")
def get_nifty50_heatmap():
    """Get live Nifty 50 heatmap data from Upstox Full Market Quotes API."""
    from app.data.nifty50_api import get_nifty50_heatmap_data

    # Use the bot's access token (refreshed via auth flow)
    access_token = Config.ACCESS_TOKEN
    if not access_token:
        # Try fresh from env
        from dotenv import load_dotenv
        load_dotenv(override=True)
        access_token = os.getenv("UPSTOX_ACCESS_TOKEN")

    if not access_token:
        raise HTTPException(status_code=401, detail="No access token available")

    result = get_nifty50_heatmap_data(access_token)
    return result


# Greeks Data Endpoint
@app.get("/greeks")
def get_greeks():
    """Get latest Greeks data for CE and PE options"""
    if bot.market_data and bot.market_data.latest_greeks:
        return {
            "type": "greeks_update",
            "data": convert_numpy_types(bot.market_data.latest_greeks)
        }
    return {
        "type": "greeks_update",
        "data": None
    }

# WebSocket
@app.websocket("/ws/status")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive - receive any messages from client
            # Timeout after 30 seconds of inactivity to detect dropped connections
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                # Connection is still alive, just no data - that's ok
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            manager.disconnect(websocket)
        except:
            pass

# Greeks WebSocket
@app.websocket("/ws/greeks")
async def greeks_websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        logger.info("Greeks WebSocket client connected")
        
        while True:
            try:
                # Send latest Greeks data at regular intervals
                if bot.market_data and bot.market_data.latest_greeks:
                    greeks_data = {
                        "type": "greeks_update",
                        "data": convert_numpy_types(bot.market_data.latest_greeks)
                    }
                    await websocket.send_json(greeks_data)
                else:
                    # Send placeholder to keep connection alive
                    await websocket.send_json({
                        "type": "greeks_update",
                        "data": None
                    })
                
                # Send every second
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending Greeks update: {e}")
                break
    except WebSocketDisconnect:
        logger.info("Greeks WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Greeks WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass

# Heatmap WebSocket
@app.websocket("/ws/heatmap")
async def heatmap_websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        logger.info("Heatmap WebSocket client connected")
        
        while True:
            try:
                # Send latest Nifty 50 quotes
                if bot.market_data and bot.market_data.nifty50_quotes:
                    # Convert dict to list for frontend
                    stocks_list = list(bot.market_data.nifty50_quotes.values())
                    
                    heatmap_data = {
                        "type": "heatmap_update",
                        "stocks": convert_numpy_types(stocks_list)
                    }
                    await websocket.send_json(heatmap_data)
                
                # Send every second (or faster if needed, but 1s is good for heatmap)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending Heatmap update: {e}")
                break
    except WebSocketDisconnect:
        logger.info("Heatmap WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Heatmap WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass


# Auth
@app.get("/auth/login")
def get_login_url():
    auth = Authenticator()
    login_url = auth.get_login_url()
    logger.info(f"🔗 Generated login URL for client")
    logger.debug(f"   API_KEY: {Config.API_KEY[:10] if Config.API_KEY else 'NOT SET'}...")
    logger.debug(f"   REDIRECT_URI: {Config.REDIRECT_URI}")
    return {"login_url": login_url}

@app.get("/auth/debug")
def auth_debug():
    """Debug endpoint to check auth configuration"""
    return {
        "api_key_set": bool(Config.API_KEY),
        "api_secret_set": bool(Config.API_SECRET),
        "redirect_uri": Config.REDIRECT_URI,
        "access_token_set": bool(Config.ACCESS_TOKEN),
        "token_status": Config.is_token_valid()
    }

@app.get("/user/profile")
def get_user_profile():
    """Get user profile information from Upstox"""
    try:
        # Check if token is valid
        token_status = Config.is_token_valid()
        if not token_status["is_valid"]:
            raise HTTPException(status_code=401, detail="Access token is invalid or expired")
        
        # Import upstox_client
        import upstox_client
        from upstox_client.rest import ApiException
        
        # Configure API client
        configuration = upstox_client.Configuration()
        configuration.access_token = Config.ACCESS_TOKEN
        api_client = upstox_client.ApiClient(configuration)
        user_api = upstox_client.UserApi(api_client)
        
        # Fetch user profile
        api_version = '2.0'
        api_response = user_api.get_profile(api_version)
        
        # Extract user data
        if api_response and api_response.data:
            user_data = {
                "user_id": api_response.data.user_id if hasattr(api_response.data, 'user_id') else None,
                "user_name": api_response.data.user_name if hasattr(api_response.data, 'user_name') else None,
                "email": api_response.data.email if hasattr(api_response.data, 'email') else None,
            }
            logger.info(f"✅ User profile fetched: {user_data.get('user_name', 'N/A')}")
            return user_data
        else:
            raise HTTPException(status_code=500, detail="Failed to fetch user profile")
            
    except ApiException as e:
        logger.error(f"❌ Upstox API error fetching profile: {e}")
        raise HTTPException(status_code=e.status, detail=f"Upstox API error: {e.reason}")
    except Exception as e:
        logger.error(f"❌ Error fetching user profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/callback", response_class=HTMLResponse)
def auth_callback(code: str = None):
    if not code:
        error_html = """
        <html>
            <head>
                <title>Authentication Failed</title>
                <style>
                    body { font-family: Arial, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
                    .container { text-align: center; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
                    h1 { color: #d32f2f; margin: 0; }
                    p { color: #666; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>❌ Authentication Failed</h1>
                    <p>Error: Missing authorization code</p>
                    <p>Closing in 3 seconds...</p>
                </div>
                <script>
                    setTimeout(() => {
                        window.close();
                    }, 3000);
                </script>
            </body>
        </html>
        """
        return error_html
    
    auth = Authenticator()
    try:
        token = auth.generate_access_token(code)
        logger.info(f"✅ Access token received from Upstox")
        
        # Save token logic
        bot.set_access_token(token)
        logger.info(f"✅ Token saved to bot and .env file")
        
        # Verify token was saved and is valid
        token_status = Config.is_token_valid()
        logger.info(f"🔐 Token validation after save: is_valid={token_status['is_valid']}, remaining_seconds={token_status.get('remaining_seconds', 0)}")
        
        if not token_status['is_valid']:
            logger.error(f"❌ Token validation failed after save: {token_status.get('error_message')}")
        
        # Give backend time to fully persist and propagate the token
        import time
        time.sleep(1)  # Wait 1 second to ensure .env file is written and flushed
        
        # Return HTML that signals the opener window and closes itself
        success_html = """
        <html>
            <head>
                <title>Authentication Successful</title>
                <style>
                    body { font-family: Arial, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
                    .container { text-align: center; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
                    h1 { color: #4caf50; margin: 0; }
                    p { color: #666; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✅ Authentication Successful!</h1>
                    <p>Token received. Redirecting to dashboard...</p>
                </div>
                <script>
                    // Signal the opener window that auth was successful
                    if (window.opener) {
                        window.opener.postMessage('auth_success', '*');
                        console.log('📨 Sent auth_success message to opener');
                    } else {
                        console.warn('⚠️ No opener window found');
                    }
                    // Close this popup after a short delay
                    setTimeout(() => {
                        window.close();
                    }, 1500);
                </script>
            </body>
        </html>
        """
        return success_html
    except Exception as e:
        logger.error(f"❌ Auth callback error: {e}")
        error_html = f"""
        <html>
            <head>
                <title>Authentication Failed</title>
                <style>
                    body {{ font-family: Arial, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
                    .container {{ text-align: center; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }}
                    h1 {{ color: #d32f2f; margin: 0; }}
                    p {{ color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>❌ Authentication Failed</h1>
                    <p>Error: {str(e)}</p>
                    <p>Closing in 3 seconds...</p>
                </div>
                <script>
                    setTimeout(() => {{
                        window.close();
                    }}, 3000);
                </script>
            </body>
        </html>
        """
        return error_html

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
