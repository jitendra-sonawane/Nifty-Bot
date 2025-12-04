#!/usr/bin/env python3
"""Fix PCR key matching issue - match by trading symbol instead of instrument_key"""

file_path = '/Users/jitendrasonawane/Workpace/backend/app/data/data_fetcher.py'

with open(file_path, 'r') as f:
    content = f.read()

old_pcr_loop = '''            total_ce_oi = 0
            total_pe_oi = 0
            matched_count = 0
            for key, greek_info in greeks_data.items():
                # Normalize key format: API returns 'NSE_FO:SYMBOL' but DataFrame has 'NSE_FO|SYMBOL'
                normalized_key = key.replace(':', '|')
                opt_info = relevant_opts[relevant_opts['instrument_key'] == normalized_key]
                if not opt_info.empty:
                    matched_count += 1
                    opt_type = opt_info.iloc[0]['option_type']
                    # Extract OI from response - check multiple possible field names
                    oi = greek_info.get('oi', 0) or greek_info.get('open_interest', 0)
                    if oi == 0 and 'ohlc' in greek_info:
                        oi = greek_info['ohlc'].get('oi', 0) or greek_info['ohlc'].get('open_interest', 0)
                    if opt_type == 'CE':
                        total_ce_oi += oi
                    elif opt_type == 'PE':
                        total_pe_oi += oi'''

new_pcr_loop = '''            total_ce_oi = 0
            total_pe_oi = 0
            for key, greek_info in greeks_data.items():
                # Extract trading symbol from API key: NSE_FO:NIFTY25D0926050CE -> NIFTY25D0926050CE
                parts = key.split(':')
                if len(parts) == 2:
                    trading_symbol = parts[1]
                    opt_info = relevant_opts[relevant_opts['tradingsymbol'] == trading_symbol]
                    if not opt_info.empty:
                        opt_type = opt_info.iloc[0]['option_type']
                        oi = greek_info.get('oi', 0) or greek_info.get('open_interest', 0)
                        if oi == 0 and 'ohlc' in greek_info:
                            oi = greek_info['ohlc'].get('oi', 0) or greek_info['ohlc'].get('open_interest', 0)
                        if opt_type == 'CE':
                            total_ce_oi += oi
                        elif opt_type == 'PE':
                            total_pe_oi += oi'''

content = content.replace(old_pcr_loop, new_pcr_loop)

with open(file_path, 'w') as f:
    f.write(content)

print("✅ Fixed PCR key matching to use tradingsymbol")
