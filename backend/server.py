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
                await manager.broadcast(status)
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
    
    status["auth"] = {
        "authenticated": token_status["is_valid"],
        "token_status": token_status
    }
    
    logger.debug(f"📊 Status endpoint: authenticated={token_status['is_valid']}, token_present={bool(fresh_token)}")
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
    # This needs to be handled by TradeExecutor or PositionManager directly
    # Bot exposes position_manager for legacy compat
    if not bot.position_manager:
        raise HTTPException(status_code=400, detail="Manager not initialized")
    
    trade = bot.position_manager.close_position(
        position_id=request.position_id,
        exit_price=request.exit_price,
        reason="MANUAL_CLOSE"
    )
    if trade:
        # We should also update TradeExecutor history
        if bot.trade_executor:
            bot.trade_executor.trade_history.append(trade)
        return {"message": "Closed", "trade": convert_numpy_types(trade)}
    raise HTTPException(status_code=404, detail="Position not found")

# Backtesting
class BacktestRequest(BaseModel):
    from_date: str
    to_date: str
    initial_capital: float = 100000

@app.post("/backtest")
def run_backtest(request: BacktestRequest):
    # Backtester is synchronous, run in threadpool if needed
    # For now, keep it sync as it might be CPU intensive
    try:
        from backtester import Backtester
        if not bot.data_fetcher:
             return {"error": "Bot not initialized"}
        
        # We need a StrategyEngine instance. 
        # Bot has strategy_runner which has strategy_engine
        strategy_engine = bot.strategy_runner.strategy_engine if bot.strategy_runner else None
        
        if not strategy_engine:
             return {"error": "Strategy Engine not ready"}

        backtester = Backtester(bot.data_fetcher, strategy_engine)
        result = backtester.run_backtest(
            symbol='NSE_INDEX|Nifty 50',
            from_date=request.from_date,
            to_date=request.to_date,
            initial_capital=request.initial_capital,
            interval='1minute'
        )
        return result
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return {"error": str(e)}

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
