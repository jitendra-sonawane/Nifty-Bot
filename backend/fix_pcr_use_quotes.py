#!/usr/bin/env python3
"""Fix PCR to use /market-quote/quotes instead of /market-quote/option-greek"""
import re

file_path = '/Users/jitendrasonawane/Workpace/backend/app/data/data_fetcher.py'

with open(file_path, 'r') as f:
    content = f.read()

# Replace get_nifty_pcr to use get_quotes instead of get_option_greeks_batch
old_pcr = '''    def get_nifty_pcr(self, spot_price):
        """Calculates Put-Call Ratio using /market-quote/option-greek API."""
        if self.instruments_df is None:
            self.load_instruments()
        if self.instruments_df is None or self.instruments_df.empty:
            self.logger.error("❌ [PCR] Instruments not loaded")
            return None
        try:
            self.logger.info(f"📊 [PCR] Starting: spot={spot_price}")
            nifty_opts = self.instruments_df[(self.instruments_df['name'] == 'NIFTY') & (self.instruments_df['instrument_type'] == 'OPTIDX')].copy()
            if nifty_opts.empty:
                self.logger.error("❌ [PCR] No Nifty options")
                return None
            if nifty_opts['expiry'].dtype == 'object':
                nifty_opts['expiry'] = pd.to_datetime(nifty_opts['expiry'])
            today = datetime.now()
            future_opts = nifty_opts[nifty_opts['expiry'] >= today]
            if future_opts.empty:
                self.logger.error("❌ [PCR] No future expiries")
                return None
            nearest_expiry = future_opts['expiry'].min()
            self.logger.info(f"📅 [PCR] Expiry: {nearest_expiry}")
            strike_range = 500
            relevant_opts = future_opts[(future_opts['expiry'] == nearest_expiry) & (future_opts['strike'] >= spot_price - strike_range) & (future_opts['strike'] <= spot_price + strike_range)]
            if relevant_opts.empty:
                self.logger.error(f"❌ [PCR] No options in range")
                return None
            self.logger.info(f"✅ [PCR] Found {len(relevant_opts)} options")
            instrument_keys = relevant_opts['instrument_key'].tolist()
            greeks_data = self.get_option_greeks_batch(instrument_keys)
            if not greeks_data:
                self.logger.error(f"❌ [PCR] No greeks data")
                return None
            self.logger.info(f"✅ [PCR] Got {len(greeks_data)} greeks")
            total_ce_oi = 0
            total_pe_oi = 0
            for key, greek_info in greeks_data.items():
                opt_info = relevant_opts[relevant_opts['instrument_key'] == key]
                if not opt_info.empty:
                    opt_type = opt_info.iloc[0]['option_type']
                    oi = greek_info.get('oi', 0)
                    if opt_type == 'CE':
                        total_ce_oi += oi
                    elif opt_type == 'PE':
                        total_pe_oi += oi
            self.logger.info(f"📊 [PCR] OI: CE={total_ce_oi}, PE={total_pe_oi}")
            if total_ce_oi > 0:
                pcr = total_pe_oi / total_ce_oi
                self.logger.info(f"✅ [PCR] Result: {pcr:.4f}")
                return round(pcr, 4)
            else:
                self.logger.error(f"❌ [PCR] No CE OI")
                return None
        except Exception as e:
            self.logger.error(f"❌ [PCR] Error: {e}")
            return None'''

new_pcr = '''    def get_nifty_pcr(self, spot_price):
        """Calculates Put-Call Ratio using /market-quote/quotes API."""
        if self.instruments_df is None:
            self.load_instruments()
        if self.instruments_df is None or self.instruments_df.empty:
            self.logger.error("❌ [PCR] Instruments not loaded")
            return None
        try:
            self.logger.info(f"📊 [PCR] Starting: spot={spot_price}")
            nifty_opts = self.instruments_df[(self.instruments_df['name'] == 'NIFTY') & (self.instruments_df['instrument_type'] == 'OPTIDX')].copy()
            if nifty_opts.empty:
                self.logger.error("❌ [PCR] No Nifty options")
                return None
            if nifty_opts['expiry'].dtype == 'object':
                nifty_opts['expiry'] = pd.to_datetime(nifty_opts['expiry'])
            today = datetime.now()
            future_opts = nifty_opts[nifty_opts['expiry'] >= today]
            if future_opts.empty:
                self.logger.error("❌ [PCR] No future expiries")
                return None
            nearest_expiry = future_opts['expiry'].min()
            self.logger.info(f"📅 [PCR] Expiry: {nearest_expiry}")
            strike_range = 500
            relevant_opts = future_opts[(future_opts['expiry'] == nearest_expiry) & (future_opts['strike'] >= spot_price - strike_range) & (future_opts['strike'] <= spot_price + strike_range)]
            if relevant_opts.empty:
                self.logger.error(f"❌ [PCR] No options in range")
                return None
            self.logger.info(f"✅ [PCR] Found {len(relevant_opts)} options")
            instrument_keys = relevant_opts['instrument_key'].tolist()
            quotes_data = self.get_quotes(instrument_keys)
            if not quotes_data:
                self.logger.error(f"❌ [PCR] No quotes data")
                return None
            self.logger.info(f"✅ [PCR] Got {len(quotes_data)} quotes")
            total_ce_oi = 0
            total_pe_oi = 0
            for key, quote_info in quotes_data.items():
                opt_info = relevant_opts[relevant_opts['instrument_key'] == key]
                if not opt_info.empty:
                    opt_type = opt_info.iloc[0]['option_type']
                    oi = quote_info.get('oi', 0)
                    if opt_type == 'CE':
                        total_ce_oi += oi
                    elif opt_type == 'PE':
                        total_pe_oi += oi
            self.logger.info(f"📊 [PCR] OI: CE={total_ce_oi}, PE={total_pe_oi}")
            if total_ce_oi > 0:
                pcr = total_pe_oi / total_ce_oi
                self.logger.info(f"✅ [PCR] Result: {pcr:.4f}")
                return round(pcr, 4)
            else:
                self.logger.error(f"❌ [PCR] No CE OI")
                return None
        except Exception as e:
            self.logger.error(f"❌ [PCR] Error: {e}")
            return None'''

content = content.replace(old_pcr, new_pcr)

with open(file_path, 'w') as f:
    f.write(content)

print("✅ Fixed PCR to use /market-quote/quotes API")
