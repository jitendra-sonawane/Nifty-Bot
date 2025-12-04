#!/usr/bin/env python3
"""
Script to apply PCR fixes: add logging and increase interval
"""
import re

# Fix 1: Update market_data.py to increase PCR interval from 60 to 120 seconds
market_data_file = '/Users/jitendrasonawane/Workpace/backend/app/core/market_data.py'

with open(market_data_file, 'r') as f:
    content = f.read()

# Replace 60 second interval with 120
content = content.replace('await asyncio.sleep(60)  # Every minute', 'await asyncio.sleep(120)  # Every 2 minutes to avoid rate limits')

with open(market_data_file, 'w') as f:
    f.write(content)

print("✅ Fixed market_data.py: Increased PCR interval to 120 seconds")

# Fix 2: Update data_fetcher.py get_option_greeks_batch with logging
data_fetcher_file = '/Users/jitendrasonawane/Workpace/backend/app/data/data_fetcher.py'

with open(data_fetcher_file, 'r') as f:
    content = f.read()

# Replace get_option_greeks_batch method
old_method = '''    def get_option_greeks_batch(self, instrument_keys):
        """
        Fetch Greeks data for multiple instruments (includes OI).
        """
        if not instrument_keys:
            return {}
        
        url = f"{self.base_url}/market-quote/option-greek"
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        params = {'instrument_key': ','.join(instrument_keys)}
        
        try:
            self.logger.info(f"🔍 Fetching greeks for {len(instrument_keys)} instruments")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    return data['data']
            else:
                self.logger.error(f"Error fetching greeks: {response.status_code} - {response.text}")
        except Exception as e:
            self.logger.error(f"Exception fetching greeks: {e}")
        
        return {}'''

new_method = '''    def get_option_greeks_batch(self, instrument_keys):
        """
        Fetch Greeks data for multiple instruments (includes OI).
        """
        if not instrument_keys:
            return {}
        
        url = f"{self.base_url}/market-quote/option-greek"
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        params = {'instrument_key': ','.join(instrument_keys)}
        
        try:
            self.logger.info(f"🔍 [GREEKS] Calling /market-quote/option-greek for {len(instrument_keys)} instruments")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            self.logger.info(f"📥 [GREEKS] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    self.logger.info(f"✅ [GREEKS] Received data for {len(data['data'])} instruments")
                    return data['data']
                else:
                    self.logger.error(f"❌ [GREEKS] No 'data' key in response")
            elif response.status_code == 429:
                self.logger.warning(f"⚠️ [GREEKS] Rate limited (429)")
            else:
                self.logger.error(f"❌ [GREEKS] Error: {response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ [GREEKS] Exception: {e}")
        
        return {}'''

content = content.replace(old_method, new_method)

with open(data_fetcher_file, 'w') as f:
    f.write(content)

print("✅ Fixed data_fetcher.py: Added logging to get_option_greeks_batch")

print("\n✅ All fixes applied successfully!")
print("\nChanges made:")
print("1. Increased PCR fetch interval from 60s to 120s (reduces API rate limiting)")
print("2. Added detailed logging to Greeks API calls")
print("\nNext steps:")
print("- Restart the bot to apply changes")
print("- Check logs for [PCR] and [GREEKS] tags to debug")
