"""
Fixed version of get_nifty_pcr with comprehensive logging and rate limit handling
"""

def get_nifty_pcr(self, spot_price):
    """
    Calculates Put-Call Ratio using /market-quote/option-greek API.
    Includes comprehensive logging for debugging.
    """
    if self.instruments_df is None:
        self.load_instruments()
        
    if self.instruments_df is None or self.instruments_df.empty:
        self.logger.error("❌ Instruments not loaded, cannot calculate PCR.")
        return None

    try:
        self.logger.info(f"📊 [PCR] Starting calculation for spot price: {spot_price}")
        
        # 1. Filter for Nifty Options
        nifty_opts = self.instruments_df[
            (self.instruments_df['name'] == 'NIFTY') & 
            (self.instruments_df['instrument_type'] == 'OPTIDX')
        ].copy()
        
        if nifty_opts.empty:
            self.logger.error("❌ [PCR] No Nifty options found in instruments master")
            return None
        
        self.logger.info(f"✅ [PCR] Found {len(nifty_opts)} Nifty options")

        # 2. Find Nearest Expiry
        if nifty_opts['expiry'].dtype == 'object':
            nifty_opts['expiry'] = pd.to_datetime(nifty_opts['expiry'])
            
        today = datetime.now()
        future_opts = nifty_opts[nifty_opts['expiry'] >= today]
        
        if future_opts.empty:
            self.logger.error("❌ [PCR] No future expiries found")
            return None
            
        nearest_expiry = future_opts['expiry'].min()
        self.logger.info(f"📅 [PCR] Nearest expiry: {nearest_expiry}")
        
        # 3. Filter for Strikes around Spot (+/- 500 points)
        strike_range = 500
        relevant_opts = future_opts[
            (future_opts['expiry'] == nearest_expiry) &
            (future_opts['strike'] >= spot_price - strike_range) &
            (future_opts['strike'] <= spot_price + strike_range)
        ]
        
        if relevant_opts.empty:
            self.logger.error(f"❌ [PCR] No options found for expiry {nearest_expiry} around {spot_price}")
            return None
        
        self.logger.info(f"✅ [PCR] Found {len(relevant_opts)} relevant options in strike range")
            
        # 4. Get Instrument Keys
        instrument_keys = relevant_opts['instrument_key'].tolist()
        self.logger.info(f"🔑 [PCR] Fetching data for {len(instrument_keys)} instrument keys")
        
        # 5. Fetch Greeks (includes OI)
        greeks_data = self.get_option_greeks_batch(instrument_keys)
        
        if not greeks_data:
            self.logger.error(f"❌ [PCR] Failed to fetch greeks for {len(instrument_keys)} instruments")
            return None
        
        self.logger.info(f"✅ [PCR] Received greeks data for {len(greeks_data)} instruments")
        
        total_ce_oi = 0
        total_pe_oi = 0
        ce_count = 0
        pe_count = 0
        
        # 6. Extract OI from Greeks response
        for key, greek_info in greeks_data.items():
            opt_info = relevant_opts[relevant_opts['instrument_key'] == key]
            if not opt_info.empty:
                opt_type = opt_info.iloc[0]['option_type']
                oi = greek_info.get('oi', 0)
                
                if opt_type == 'CE':
                    total_ce_oi += oi
                    ce_count += 1
                elif opt_type == 'PE':
                    total_pe_oi += oi
                    pe_count += 1
        
        self.logger.info(f"📊 [PCR] OI Aggregation: CE={ce_count} contracts (OI={total_ce_oi}), PE={pe_count} contracts (OI={total_pe_oi})")
        
        # 7. Calculate PCR
        if total_ce_oi > 0:
            pcr = total_pe_oi / total_ce_oi
            self.logger.info(f"✅ [PCR] Calculated: {pcr:.4f} (Put OI: {total_pe_oi}, Call OI: {total_ce_oi})")
            return round(pcr, 4)
        else:
            self.logger.error(f"❌ [PCR] No Call OI found for PCR calculation")
            return None
            
    except Exception as e:
        self.logger.error(f"❌ [PCR] Error calculating PCR: {e}")
        import traceback
        self.logger.error(traceback.format_exc())
        return None


def get_option_greeks_batch(self, instrument_keys):
    """
    Fetch Greeks data for multiple instruments (includes OI).
    Includes logging for debugging API calls.
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
                self.logger.info(f"✅ [GREEKS] Successfully received data for {len(data['data'])} instruments")
                return data['data']
            else:
                self.logger.error(f"❌ [GREEKS] No 'data' key in response: {data.keys()}")
        elif response.status_code == 429:
            self.logger.warning(f"⚠️ [GREEKS] Rate limited (429): {response.text[:200]}")
        else:
            self.logger.error(f"❌ [GREEKS] Error: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        self.logger.error(f"❌ [GREEKS] Exception: {e}")
    
    return {}
