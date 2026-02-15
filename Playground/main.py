from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from streamer import start_market_streamer
import asyncio
from typing import List
from event_bus import event_bus, ExceptionMode, MarketEvent

app = FastAPI(title="Simple data fetcher ")

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle dropped connections gracefully
                pass

manager = ConnectionManager()

# --- Event Bus Bridge ---
async def broadcast_volume_update(event: MarketEvent):
    """Bridge: Event Bus -> WebSocket"""
    await manager.broadcast(event.data)

@app.on_event("startup")
async def startup_event():
    # Start the streamer
    asyncio.create_task(start_market_streamer())
    
    # Subscribe WebSocket bridge to VOLUME_UPDATE events
    event_bus.subscribe(
        event_type="VOLUME_UPDATE",
        callback=broadcast_volume_update,
        mode=ExceptionMode.PARALLEL
    )
    
    # Subscribe WebSocket bridge to VOLUME_SPIKE events
    event_bus.subscribe(
        event_type="VOLUME_SPIKE",
        callback=broadcast_volume_update,
        mode=ExceptionMode.PARALLEL
    )

@app.websocket("/ws/volume")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def read_root():
    # Serve the HTML file directly (for simplicity)
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/get_pcr")
def get_pcr():
    return {"PCR": "1.2"}