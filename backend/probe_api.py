import requests
import urllib.parse
from app.core.config import Config

def probe_intraday():
    api_key = Config.API_KEY
    access_token = Config.ACCESS_TOKEN
    base_url = "https://api.upstox.com/v3"
    
    instrument_key = Config.SYMBOL_NIFTY_50
    encoded_key = urllib.parse.quote(instrument_key)
    interval = "1minute"
    
    # Try V3 with split interval format?
    base_url = "https://api.upstox.com/v3"
    # url = f"{base_url}/historical-candle/intraday/{encoded_key}/{interval}" 
    # Try: /historical-candle/intraday/{key}/minutes/5
    url = f"{base_url}/historical-candle/intraday/{encoded_key}/minutes/5"
    
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    
    print(f"Probing Intraday URL: {url}")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and 'candles' in data['data']:
            candles = data['data']['candles']
            print(f"✅ Success! Received {len(candles)} candles.")
            if candles:
                print(f"Last Candle: {candles[0]}") # Upstox usually returns reverse chronological? or chronological?
                # Check first and last
                print(f"First in list: {candles[0]}")
                print(f"Last in list: {candles[-1]}")
        else:
            print(f"⚠️ Response OK but unexpected format: {data.keys()}")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    probe_intraday()
