import asyncio
import json
import os
from typing import Dict, Any, Set
from dotenv import load_dotenv

load_dotenv()

import httpx
import websockets
from google.protobuf.json_format import MessageToDict
from upstox_client.feeder.proto import MarketDataFeedV3_pb2

# Import our dynamic option selector
from instrument_keys import get_instrument_keys
from event_bus import event_bus, MarketEvent

UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
WS_AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

# Global state for tracking
current_nifty_price = None
last_atm_strike = None
subscribed_instruments: Set[str] = set()
instrument_metadata: Dict[str, Dict] = {} # Key -> {strike, type}
PRICE_CHANGE_THRESHOLD = 50  # Re-subscribe if price moves 50 points

async def get_authorized_ws_url() -> str:
    print(f"DEBUG: Token available? {'Yes' if UPSTOX_ACCESS_TOKEN else 'No'}")
    if UPSTOX_ACCESS_TOKEN:
        print(f"DEBUG: Token length: {len(UPSTOX_ACCESS_TOKEN)}")
        print(f"DEBUG: Token prefix: {UPSTOX_ACCESS_TOKEN[:5]}...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(WS_AUTHORIZE_URL, headers={
                "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
                "Accept": "application/json"
            })
            if response.status_code != 200:
                print(f"Error Response: {response.text}")
            response.raise_for_status()
            data = response.json()
            print(f"DEBUG: Full API Response: {data}")
            
            # Try both keys just in case
            ws_url = data.get("data",{}).get("authorizedRedirectUri")
            if not ws_url:
                 ws_url = data.get("data",{}).get("authorize_redirect_url")
            
            print(f"DEBUG: Extracted ws_url: {ws_url}")
            return ws_url
        except Exception as e:
            print(f"Request failed: {e}")
            raise


def get_option_instruments(nifty_price: float, expiry_date: str = "2025-12-16") -> dict:
    """Get instrument keys and metadata for options based on current Nifty price"""
    try:
        result = get_instrument_keys(nifty_price, expiry_date, num_strikes=5)
        if result:
            # Combine CE and PE keys
            all_keys = result['ce_options'] + result['pe_options']
            print(f"📊 Generated {len(all_keys)} option keys for price {nifty_price}")
            return {
                'keys': all_keys,
                'metadata': result.get('metadata', {})
            }
        return {'keys': [], 'metadata': {}}
    except Exception as e:
        print(f"❌ Error getting option instruments: {e}")
        return {'keys': [], 'metadata': {}}


def should_update_subscriptions(new_price: float) -> bool:
    """Check if we should update subscriptions based on price change"""
    global current_nifty_price, last_atm_strike
    
    if current_nifty_price is None:
        return True  # First time
    
    price_diff = abs(new_price - current_nifty_price)
    
    # Update if price moved significantly
    if price_diff >= PRICE_CHANGE_THRESHOLD:
        print(f"🔄 Price moved {price_diff:.2f} points (threshold: {PRICE_CHANGE_THRESHOLD})")
        return True
    
    return False


async def update_subscriptions(websocket, new_instruments: list):
    """Update WebSocket subscriptions with new instrument keys"""
    global subscribed_instruments
    
    new_set = set(new_instruments)
    
    # Find instruments to unsubscribe
    to_unsubscribe = subscribed_instruments - new_set
    
    # Find instruments to subscribe
    to_subscribe = new_set - subscribed_instruments
    
    # Unsubscribe from old instruments
    if to_unsubscribe:
        unsub_payload = {
            "guid": "nifty-bot",
            "method": "unsub",
            "data": {
                "mode": "full",
                "instrumentKeys": list(to_unsubscribe)
            }
        }
        await websocket.send(json.dumps(unsub_payload).encode("utf-8"))
        print(f"📤 Unsubscribed from {len(to_unsubscribe)} instruments")
    
    # Subscribe to new instruments
    if to_subscribe:
        sub_payload = {
            "guid": "nifty-bot",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": list(to_subscribe)
            }
        }
        print(f"📡 Sending update subscription payload: {json.dumps(sub_payload, indent=2)}")
        await websocket.send(json.dumps(sub_payload).encode("utf-8"))
        print(f"📥 Subscribed to {len(to_subscribe)} new instruments")
    
    # Update tracking
    subscribed_instruments = new_set
    print(f"✅ Total subscribed instruments: {len(subscribed_instruments)}")

async def market_streamer_loop():
    global current_nifty_price, last_atm_strike, instrument_metadata
    
    while True:
        try:
            ws_url = await get_authorized_ws_url()
            print("authorized ws url", ws_url)
            async with websockets.connect(ws_url, max_size=None) as websocket:
                print("connected to v3 websocket")
                
                # Initial subscription: Start with Nifty 50 index only
                initial_instruments = ["NSE_INDEX|Nifty 50"]
                
                sub_payload = {
                    "guid": "nifty-bot",
                    "method": "sub",
                    "data": {
                        "mode": "full",
                        "instrumentKeys": initial_instruments
                    }
                }

                print(f"📡 Sending subscription payload: {json.dumps(sub_payload, indent=2)}")
                await websocket.send(json.dumps(sub_payload).encode("utf-8"))
                print("✅ Initial subscription: Nifty 50 Index")
                subscribed_instruments.update(initial_instruments)

                async for raw_msg in websocket:
                    try:
                        if isinstance(raw_msg, bytes):
                            feed_response = MarketDataFeedV3_pb2.FeedResponse()
                            # print("feed_response", feed_response)
                            feed_response.ParseFromString(raw_msg)
                            data_dict = MessageToDict(feed_response)
                            # print("data_dict", data_dict)
                            response_type = data_dict.get("type")
                            
                            if response_type == "market_info":
                                print(f"\n[Market Status] Ts: {data_dict.get('currentTs')}")
                                print(json.dumps(data_dict.get("marketInfo"), indent=2))
                                
                            elif response_type in ["initial_feed", "live_feed"] or "feeds" in data_dict:
                                feeds = data_dict.get("feeds", {})
                                
                                for key, feed_data in feeds.items():
                                    # Extract LTP
                                    # Extract LTP
                                    ltp = None
                                    volume = None
                                    # print("extract feed data", feed_data)
                                    # Handle fullFeed structure
                                    if "fullFeed" in feed_data:
                                        full_feed = feed_data["fullFeed"]
                                        # Check for Index Full Feed
                                        if "indexFF" in full_feed:
                                            ltp = full_feed["indexFF"].get("ltpc", {}).get("ltp")
                                        # Check for Market Full Feed (for options/stocks)
                                        elif "marketFF" in full_feed:
                                            market_ff = full_feed["marketFF"]
                                            ltp = market_ff.get("ltpc", {}).get("ltp")
                                            volume= market_ff.get("vtt")
                                            open_interest = market_ff.get("oi")
                                    
                                    # Handle legacy/simple structure matching existing logic if needed
                                    elif "ltpc" in feed_data:
                                        ltp = feed_data["ltpc"].get("ltp")
                                    elif "ff" in feed_data:
                                        ltp = feed_data["ff"].get("ltp")
                                    # elif "marketFF" in feed_data:
                                    #     volume = feed_data["marketFF"].get("vtt")
                                    # DEBUG: Print all received keys
                                    print(f"🔍 Received: {key} | LTP: {ltp}")
                                    
                                    if ltp is None:
                                        print(f"⚠️ LTP is None for {key}. Feed Data keys: {feed_data.keys()}")
                                        print(f"⚠️ Full Feed Data: {json.dumps(feed_data, indent=2)}")
                                    
                                    # Check if this is Nifty 50 index
                                    if key == "NSE_INDEX|Nifty 50" and ltp:
                                        # ... (keep existing Nifty logic for subscriptions) ...
                                        new_price = float(ltp)
                                        currency_price = current_nifty_price
                                        
                                        # Publish Nifty Tick
                                        await event_bus.publish(MarketEvent(
                                            event_type="MARKET_TICK",
                                            data={
                                                'token': key,
                                                'ltp': new_price,
                                                'timestamp': data_dict.get('currentTs'),
                                                'type': 'INDEX'
                                            }
                                        ))

                                        # ... (rest of subscription update logic) ...
                                        if should_update_subscriptions(new_price):
                                            # ...
                                            current_nifty_price = new_price
                                            print(f"   Calling get_option_instruments({new_price}, '2025-12-16')...")
                                            result = get_option_instruments(new_price, "2025-12-16")
                                            option_keys = result.get('keys', [])
                                            new_meta = result.get('metadata', {})
                                            
                                            print(f"   Received {len(option_keys) if option_keys else 0} option keys")
                                            
                                            if option_keys:
                                                # Update global metadata
                                                instrument_metadata.update(new_meta)
                                                
                                                # Combine with Nifty index
                                                all_instruments = ["NSE_INDEX|Nifty 50"] + option_keys
                                                
                                                print(f"   Total instruments to subscribe: {len(all_instruments)}")
                                                print(f"   First 3 option keys: {option_keys[:3]}")
                                                
                                                # Update subscriptions
                                                await update_subscriptions(websocket, all_instruments)
                                                
                                                last_atm_strike = new_price
                                    # Publish Option Data
                                    elif key in subscribed_instruments and key != "NSE_INDEX|Nifty 50" and ltp:
                                        # print(f"📊 OPTION DATA: {key}: LTP={ltp} Volume={volume}")
                                        
                                        # LOOKUP METADATA
                                        meta = instrument_metadata.get(key, {})
                                        # if key == 'NSE_FO|48229':
                                        #     print(f"Open Interest from here:{open_interest} ltp:{ltp} for {key}")
                                        #     print(f"market ff {market_ff}")
                                        # open_interest = 
                                        await event_bus.publish(MarketEvent(
                                            event_type="MARKET_TICK",
                                            data={
                                                'token': key,
                                                'ltp': float(ltp),
                                                'volume': int(volume) if volume else 0,
                                                'timestamp': data_dict.get('currentTs'),
                                                'type': 'OPTION',
                                                'strike': meta.get('strike', 0),    # <--- PASSED HERE
                                                'option_type': meta.get('type', 'UNK'), # <--- PASSED HERE
                                                'open_interest':int(open_interest) if open_interest else 0
                                            }
                                        ))
                                        
                            else:
                                print(f"\n[Unknown Type: {response_type}]")
                                print(json.dumps(data_dict, indent=2))
                            
                            continue

                        # Text message handling (rare for V3)
                        msg_text = raw_msg
                        print(f"Received Text Message: {msg_text}")
                        
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}")
                    except Exception as e:
                         print(f"Error processing message: {e}")
                         import traceback
                         traceback.print_exc()
                

        except Exception as e:
            print(f"Error in market streamer loop: {e}")
            await asyncio.sleep(5)


# Import the volume service setup
from volume_tracker import setup_volume_service

async def start_market_streamer():
    # Initialize services
    await setup_volume_service()
    
    # Start loop
    await market_streamer_loop()