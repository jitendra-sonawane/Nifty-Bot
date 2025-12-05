#!/usr/bin/env python3
"""
Diagnostic script to check available expiries in NSE.csv
"""
import pandas as pd
from datetime import datetime
import os

def check_expiries():
    try:
        csv_path = "backend/NSE.csv"
        if not os.path.exists(csv_path):
            print(f"File not found: {csv_path}")
            # Try to find it in current dir
            csv_path = "NSE.csv"
            if not os.path.exists(csv_path):
                print(f"File not found: {csv_path}")
                return

        print(f"Loading {csv_path}...")
        df = pd.read_csv(csv_path)
        print("Loaded.")
        
        print(f"Unique names: {df['name'].unique()[:10]}")

        nifty_opts = df[
            (df['name'] == 'NIFTY') & 
            (df['instrument_type'] == 'OPTIDX')
        ].copy()
        
        if nifty_opts.empty:
            print("No NIFTY options found.")
            return

        nifty_opts['expiry'] = pd.to_datetime(nifty_opts['expiry'])
        
        dec_opts = nifty_opts[
            (nifty_opts['expiry'] >= '2025-12-01') &
            (nifty_opts['expiry'] <= '2025-12-31')
        ]
        
        print("All NIFTY Expiries in Dec 2025:")
        print(sorted(dec_opts['expiry'].unique()))
        today = datetime.now()
        
        future_opts = nifty_opts[nifty_opts['expiry'] >= today]
        
        print(f"Today: {today}")
        print("Available Expiries:")
        expiries = sorted(future_opts['expiry'].unique())
        for exp in expiries[:10]:
            print(f"  - {exp}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_expiries()
