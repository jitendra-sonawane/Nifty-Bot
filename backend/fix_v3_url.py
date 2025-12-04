#!/usr/bin/env python3
file_path = '/Users/jitendrasonawane/Workpace/backend/app/data/data_fetcher.py'
with open(file_path, 'r') as f:
    content = f.read()

old = '''    def get_option_greeks_batch(self, instrument_keys):
        """Fetch Greeks data for multiple instruments (includes OI)."""
        if not instrument_keys:
            return {}
        url = f"{self.base_url}/market-quote/option-greek"'''

new = '''    def get_option_greeks_batch(self, instrument_keys):
        """Fetch Greeks data for multiple instruments (includes OI)."""
        if not instrument_keys:
            return {}
        url = "https://api.upstox.com/v3/market-quote/option-greek"'''

content = content.replace(old, new)
with open(file_path, 'w') as f:
    f.write(content)
print("✅ Updated get_option_greeks_batch to use v3 API")
