#!/usr/bin/env python3
"""Fix PCR OI extraction from /market-quote/option-greek endpoint"""

file_path = '/Users/jitendrasonawane/Workpace/backend/app/data/data_fetcher.py'

with open(file_path, 'r') as f:
    content = f.read()

# Update get_option_greeks_batch with better logging
old_greeks = '''    def get_option_greeks_batch(self, instrument_keys):
        """Fetch Greeks data for multiple instruments (includes OI)."""
        if not instrument_keys:
            return {}
        url = "https://api.upstox.com/v3/market-quote/option-greek"
        headers = {'Accept': 'application/json', 'Authorization': f'Bearer {self.access_token}'}
        params = {'instrument_key': ','.join(instrument_keys)}
        try:
            self.logger.info(f"🔍 [GREEKS] Fetching {len(instrument_keys)}")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            self.logger.info(f"📥 [GREEKS] Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    self.logger.info(f"✅ [GREEKS] Got {len(data['data'])}")
                    # Log first item to check structure
                    if data['data']:
                        first_key = list(data['data'].keys())[0]
                        self.logger.info(f"🔍 [GREEKS] Sample data for {first_key}: {data['data'][first_key]}")
                    return data['data']
            elif response.status_code == 429:
                self.logger.warning(f"⚠️ [GREEKS] Rate limited")
            else:
                self.logger.error(f"❌ [GREEKS] Error {response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ [GREEKS] Exception: {e}")
        return {}'''

new_greeks = '''    def get_option_greeks_batch(self, instrument_keys):
        """Fetch Greeks data for multiple instruments (includes OI)."""
        if not instrument_keys:
            return {}
        url = "https://api.upstox.com/v3/market-quote/option-greek"
        headers = {'Accept': 'application/json', 'Authorization': f'Bearer {self.access_token}'}
        params = {'instrument_key': ','.join(instrument_keys)}
        try:
            self.logger.info(f"🔍 [GREEKS] Fetching {len(instrument_keys)}")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            self.logger.info(f"📥 [GREEKS] Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    self.logger.info(f"✅ [GREEKS] Got {len(data['data'])}")
                    if data['data']:
                        first_key = list(data['data'].keys())[0]
                        first_item = data['data'][first_key]
                        self.logger.info(f"🔍 [GREEKS] Response keys: {list(first_item.keys())}")
                        if 'oi' in first_item:
                            self.logger.info(f"🔍 [GREEKS] OI at top: {first_item.get('oi')}")
                        if 'ohlc' in first_item:
                            self.logger.info(f"🔍 [GREEKS] OHLC keys: {list(first_item['ohlc'].keys())}")
                    return data['data']
            elif response.status_code == 429:
                self.logger.warning(f"⚠️ [GREEKS] Rate limited")
            else:
                self.logger.error(f"❌ [GREEKS] Error {response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ [GREEKS] Exception: {e}")
        return {}'''

content = content.replace(old_greeks, new_greeks)

with open(file_path, 'w') as f:
    f.write(content)

print("✅ Updated get_option_greeks_batch with detailed OI logging")
