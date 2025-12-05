#!/usr/bin/env python3
file_path = '/Users/jitendrasonawane/Workpace/backend/app/data/data_fetcher.py'
with open(file_path, 'r') as f:
    content = f.read()
content = content.replace('https://api.upstox.com/v2/market-quote/option-greek', 'https://api.upstox.com/v3/market-quote/option-greek')
with open(file_path, 'w') as f:
    f.write(content)
print("✅ Updated to v3 API")
