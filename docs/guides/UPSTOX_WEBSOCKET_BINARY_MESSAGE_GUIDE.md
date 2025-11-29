# Upstox WebSocket Binary Message Decoding Guide

## Overview

The Upstox Python SDK uses **Protocol Buffers (Protobuf)** to encode and decode binary WebSocket messages from the Upstox market data feed. The SDK provides a complete implementation with built-in WebSocket streamer classes.

---

## 1. Built-in WebSocket Streamer Class

### `MarketDataStreamerV3` Class

Located in: `upstox_client.feeder.market_data_streamer_v3`

This is the main high-level class for handling market data streaming:

```python
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3

# Initialize the streamer with an API client
streamer = MarketDataStreamerV3(
    api_client=api_client,
    instrumentKeys=['NSE_FO|NIFTY23NOV16800PE'],
    mode="ltpc"  # or "full", "option_greeks", "full_d30"
)

# Connect to WebSocket
streamer.connect()

# Subscribe to events
streamer.on(streamer.Event["OPEN"], on_open_callback)
streamer.on(streamer.Event["MESSAGE"], on_message_callback)
streamer.on(streamer.Event["ERROR"], on_error_callback)
streamer.on(streamer.Event["CLOSE"], on_close_callback)
```

### Streaming Modes

The SDK supports 4 different modes:

| Mode | Value | Description |
|------|-------|-------------|
| **LTPC** | "ltpc" | Last Traded Price & Close price only (lightweight) |
| **FULL** | "full" | Complete market data with OHLC, Greeks, etc. |
| **OPTION** | "option_greeks" | Option Greeks data only |
| **D30** | "full_d30" | Full data with 30-minute candles |

---

## 2. Message Format and Protobuf Structure

### Binary Message Format

**WebSocket Communication Protocol:**

1. **Client Requests:** Sent as JSON encoded in UTF-8, then transmitted as BINARY opcode
2. **Server Responses:** Sent as binary protobuf-encoded data

### Protobuf Message Structure

The main message classes are:

```
FeedResponse (Root message)
├── type: Type (enum: initial_feed, live_feed, market_info)
├── feeds: map<string, Feed> (instrument key -> feed data)
├── currentTs: int64 (current timestamp in milliseconds)
└── marketInfo: MarketInfo (market status for each segment)

Feed (Polymorphic message with union type)
├── ltpc: LTPC
├── fullFeed: FullFeed
├── firstLevelWithGreeks: FirstLevelWithGreeks
└── requestMode: RequestMode (enum)

LTPC (Last Traded Price & Close)
├── ltp: double (Last Traded Price)
├── ltt: int64 (Last Traded Time)
├── ltq: int64 (Last Traded Quantity)
└── cp: double (Close Price)

FullFeed (Complete Market Data)
├── marketFF: MarketFullFeed
├── indexFF: IndexFullFeed
└── (union type)

MarketFullFeed
├── ltpc: LTPC
├── marketLevel: MarketLevel (bid-ask quotes)
├── optionGreeks: OptionGreeks
├── marketOHLC: MarketOHLC (OHLC data)
├── atp: double (Average Traded Price)
├── vtt: int64 (Volume Traded Today)
├── oi: double (Open Interest)
├── iv: double (Implied Volatility)
├── tbq: double (Total Buy Quantity)
└── tsq: double (Total Sell Quantity)

OptionGreeks
├── delta: double
├── theta: double
├── gamma: double
├── vega: double
└── rho: double

MarketLevel
└── bidAskQuote: repeated Quote (bid-ask levels)

Quote (Bid/Ask Level)
├── bidQ: int64 (Bid Quantity)
├── bidP: double (Bid Price)
├── askQ: int64 (Ask Quantity)
└── askP: double (Ask Price)

MarketOHLC
└── ohlc: repeated OHLC

OHLC (Candle Data)
├── interval: string (e.g., "1min", "5min", "1day")
├── open: double
├── high: double
├── low: double
├── close: double
├── vol: int64 (volume)
└── ts: int64 (timestamp)

MarketInfo
└── segmentStatus: map<string, MarketStatus>

MarketStatus (enum)
├── PRE_OPEN_START (0)
├── PRE_OPEN_END (1)
├── NORMAL_OPEN (2)
├── NORMAL_CLOSE (3)
├── CLOSING_START (4)
└── CLOSING_END (5)
```

---

## 3. How the SDK Decodes Binary Messages

### Internal Decoding Process

The `MarketDataStreamerV3` class uses the following approach:

```python
def decode_protobuf(self, buffer):
    """Decode binary protobuf buffer to FeedResponse object"""
    FeedResponse = self.protobufRoot.FeedResponse
    return FeedResponse.FromString(buffer)

def handle_message(self, ws, message):
    """Handle incoming binary message from WebSocket"""
    # Decode binary protobuf message
    decoded_data = self.decode_protobuf(message)
    
    # Convert protobuf to dictionary (JSON-compatible format)
    from google.protobuf import json_format
    data_dict = json_format.MessageToDict(decoded_data)
    
    # Emit the decoded data to listeners
    self.emit(self.Event["MESSAGE"], data_dict)
```

### Key Components:

1. **Protobuf Module:** `upstox_client.feeder.proto.MarketDataFeedV3_pb2`
   - Contains all message class definitions
   - Auto-generated from `.proto` file by protocol buffer compiler

2. **Decoding Method:** `FeedResponse.FromString(binary_data)`
   - Takes raw binary buffer
   - Returns deserialized FeedResponse object with all fields populated

3. **Conversion to JSON:** `json_format.MessageToDict(protobuf_object)`
   - Converts protobuf object to Python dictionary
   - Makes it compatible with JSON serialization
   - Useful for logging, storage, and API responses

---

## 4. WebSocket Connection Details

### Connection Setup

Located in: `upstox_client.feeder.market_data_feeder_v3.py`

```python
class MarketDataFeederV3:
    def connect(self):
        """Establish WebSocket connection to Upstox"""
        sslopt = {
            "cert_reqs": ssl.CERT_NONE,
            "check_hostname": False,
        }
        
        # WebSocket endpoint
        ws_url = "wss://api.upstox.com/v3/feed/market-data-feed"
        
        # Authorization header with OAuth2 token
        headers = {
            'Authorization': self.api_client.configuration.auth_settings()
                             .get("OAUTH2")["value"]
        }
        
        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            ws_url,
            header=headers,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Run in separate thread
        threading.Thread(
            target=self.ws.run_forever,
            kwargs={"sslopt": sslopt}
        ).start()
```

### Request Format (JSON)

Client sends subscription requests as JSON, encoded as UTF-8 binary:

```python
{
    "guid": "unique-uuid",
    "method": "sub",  # or "unsub", "change_mode"
    "data": {
        "instrumentKeys": [
            "NSE_FO|NIFTY23NOV16800PE",
            "NSE_EQ|SBIN-EQ"
        ],
        "mode": "ltpc"  # Optional, only for subscribe/change_mode
    }
}
```

### Binary Transmission

```python
# Sending binary messages
request_json = json.dumps(request_obj).encode('utf-8')
self.ws.send(request_json, opcode=websocket.ABNF.OPCODE_BINARY)
```

---

## 5. Code Example: Complete Usage Pattern

```python
from upstox_client import ApiClient, MarketDataStreamerV3
from upstox_client.configuration import Configuration

# Setup API client
config = Configuration()
config.api_key['OAUTH2'] = 'your_oauth_token'
api_client = ApiClient(config)

# Initialize streamer with initial subscriptions
streamer = MarketDataStreamerV3(
    api_client=api_client,
    instrumentKeys=['NSE_FO|NIFTY23NOV16800PE'],
    mode="ltpc"
)

# Define event handlers
def on_open():
    print("WebSocket connection opened")

def on_message(data):
    """
    data is already converted to dictionary:
    {
        'type': 'live_feed',  # or 'initial_feed', 'market_info'
        'feeds': {
            'NSE_FO|NIFTY23NOV16800PE': {
                'ltpc': {
                    'ltp': 125.50,
                    'ltt': 1700000000000,
                    'ltq': 100,
                    'cp': 124.75
                }
            }
        },
        'currentTs': 1700000000123,
        'marketInfo': {...}
    }
    """
    print(f"Received update: {data}")
    
    # Access specific fields
    for instrument_key, feed in data.get('feeds', {}).items():
        if 'ltpc' in feed:
            ltpc = feed['ltpc']
            print(f"{instrument_key}: LTP={ltpc['ltp']}, "
                  f"Volume={ltpc['ltq']}")

def on_error(error):
    print(f"Error: {error}")

def on_close(status_code, message):
    print(f"Connection closed: {status_code} - {message}")

# Register event listeners
streamer.on(streamer.Event["OPEN"], on_open)
streamer.on(streamer.Event["MESSAGE"], on_message)
streamer.on(streamer.Event["ERROR"], on_error)
streamer.on(streamer.Event["CLOSE"], on_close)

# Connect
streamer.connect()

# Subscribe to additional instruments
streamer.subscribe(
    ["NSE_EQ|SBIN-EQ", "NSE_EQ|RELIANCE-EQ"],
    mode="ltpc"
)

# Change mode for specific instruments
streamer.change_mode(
    ["NSE_FO|NIFTY23NOV16800PE"],
    newMode="full"
)

# Unsubscribe from instruments
streamer.unsubscribe(["NSE_EQ|SBIN-EQ"])

# Disconnect
streamer.disconnect()
```

---

## 6. Manual Binary Decoding (Advanced)

If you need to decode protobuf messages manually without the streamer:

```python
from upstox_client.feeder.proto import MarketDataFeedV3_pb2
from google.protobuf import json_format

def decode_upstox_feed(binary_message):
    """Manually decode binary WebSocket message"""
    
    # Create empty FeedResponse message
    feed_response = MarketDataFeedV3_pb2.FeedResponse()
    
    # Parse binary data
    feed_response.ParseFromString(binary_message)
    
    # Access fields directly
    print(f"Message Type: {feed_response.type}")
    print(f"Current Timestamp: {feed_response.currentTs}")
    
    # Iterate through feeds
    for instrument_key, feed in feed_response.feeds.items():
        print(f"\nInstrument: {instrument_key}")
        
        # Check which feed type is present (union)
        feed_type = feed.WhichOneof('FeedUnion')
        
        if feed_type == 'ltpc':
            ltpc = feed.ltpc
            print(f"  LTP: {ltpc.ltp}")
            print(f"  LTT: {ltpc.ltt}")
            print(f"  LTQ: {ltpc.ltq}")
            print(f"  Close Price: {ltpc.cp}")
            
        elif feed_type == 'fullFeed':
            full_feed = feed.fullFeed
            if full_feed.HasField('marketFF'):
                market_ff = full_feed.marketFF
                print(f"  LTPC: {market_ff.ltpc.ltp}")
                print(f"  ATP: {market_ff.atp}")
                print(f"  Volume: {market_ff.vtt}")
                print(f"  OI: {market_ff.oi}")
                print(f"  IV: {market_ff.iv}")
                
                # Option Greeks
                if market_ff.HasField('optionGreeks'):
                    greeks = market_ff.optionGreeks
                    print(f"  Delta: {greeks.delta}")
                    print(f"  Theta: {greeks.theta}")
                    print(f"  Gamma: {greeks.gamma}")
                    
    # Convert to dictionary format
    data_dict = json_format.MessageToDict(feed_response)
    return data_dict
```

---

## 7. Key Implementation Notes

### Protocol Buffer Definitions

The protobuf definitions are compiled into Python classes. The key file is:
- `upstox_client/feeder/proto/MarketDataFeedV3_pb2.py`

This file is auto-generated from `MarketDataFeedV3.proto` and contains:
- Message class definitions (LTPC, Feed, FeedResponse, etc.)
- Enum definitions (Type, RequestMode, MarketStatus)
- Helper methods for serialization/deserialization

### Automatic Data Type Conversion

Protobuf automatically handles:
- `double` → Python `float`
- `int64` → Python `int`
- `string` → Python `str`
- Nested messages → Python objects with attributes
- Repeated fields → Python `list`
- Maps → Python `dict`

### Event Listener Pattern

The SDK uses an observer pattern for handling messages:

```python
# Built-in events
streamer.Event = {
    "OPEN": "open",
    "CLOSE": "close", 
    "MESSAGE": "message",
    "ERROR": "error",
    "RECONNECTING": "reconnecting",
    "AUTO_RECONNECT_STOPPED": "autoReconnectStopped"
}
```

### Auto-Reconnect Feature

```python
# Configure auto-reconnect
streamer.auto_reconnect(
    enable=True,
    interval=1,        # seconds between attempts
    retry_count=5      # maximum retry attempts
)
```

---

## 8. Important Field Types Reference

### Numeric Precision

| Field Type | Python Type | Precision | Range |
|-----------|-----------|-----------|--------|
| `double` | `float` | 64-bit IEEE 754 | ±1.7E±308 |
| `int64` | `int` | 64-bit signed | -2^63 to 2^63-1 |
| `string` | `str` | UTF-8 encoded | Unlimited |

### Timestamp Handling

- All timestamps (`ltt`, `ts`) are in **milliseconds since epoch**
- Convert to datetime:
  ```python
  from datetime import datetime
  dt = datetime.fromtimestamp(timestamp_ms / 1000)
  ```

### Union Types (Oneof)

Some messages use protobuf `oneof` for union types. Check which field is set:

```python
feed_type = feed.WhichOneof('FeedUnion')
if feed_type == 'ltpc':
    # ltpc field is set
    data = feed.ltpc
elif feed_type == 'fullFeed':
    # fullFeed field is set
    data = feed.fullFeed
```

---

## 9. Troubleshooting

### Common Issues

1. **ParseFromString fails**: Binary data might be corrupted or incomplete
2. **Field not found**: Check message type using `WhichOneof()` for union types
3. **Timestamp issues**: Remember timestamps are in milliseconds, not seconds
4. **Authorization errors (401)**: OAuth token might be expired
5. **Connection drops**: Enable auto-reconnect to handle network issues

### Debugging

```python
# Print raw protobuf message structure
print(feed_response)

# Convert to JSON string for inspection
import json
json_str = json_format.MessageToJson(feed_response)
print(json.dumps(json.loads(json_str), indent=2))

# Check which fields are populated
print(feed.ListFields())
```

---

## Summary

The Upstox Python SDK provides:
- ✅ **Built-in WebSocket Streamer**: `MarketDataStreamerV3` for easy market data streaming
- ✅ **Automatic Protobuf Decoding**: Binary messages automatically decoded to Python objects
- ✅ **Multiple Data Modes**: LTPC (light), FULL (complete), OPTION (Greeks), D30 (30-min candles)
- ✅ **Event-Driven Architecture**: Observer pattern for handling connections and messages
- ✅ **Auto-Reconnect**: Built-in reconnection logic for network resilience
- ✅ **JSON Compatibility**: Automatic conversion to dict/JSON for easy integration

The SDK handles all the complexity of protobuf decoding internally, allowing you to focus on business logic.
