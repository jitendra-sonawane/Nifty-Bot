import requests
import pandas as pd
from datetime import datetime, timedelta
from app.core.config import Config
import pandas as pd
from datetime import datetime, timedelta
import os
import gzip
import shutil
from app.core.config import Config
import upstox_client
from upstox_client.rest import ApiException
import urllib.parse
import logging

from app.core.greeks import GreeksCalculator

# Get logger instance
try:
    from app.core.logger_config import logger
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token
        self.logger = logger
        self.base_url = "https://api.upstox.com/v2"
        
        # Configure SDK client
        configuration = upstox_client.Configuration()
        configuration.access_token = access_token
        self.api_instance = upstox_client.HistoryApi(upstox_client.ApiClient(configuration))
        self.api_instance = upstox_client.HistoryApi(upstox_client.ApiClient(configuration))
        self.instruments_df = None
        self.greeks_calculator = GreeksCalculator()

    def set_access_token(self, token):
        self.access_token = token
        configuration = upstox_client.Configuration()
        configuration.access_token = token
        self.api_instance = upstox_client.HistoryApi(upstox_client.ApiClient(configuration))
        print("DataFetcher: Access Token updated.")

    def load_instruments(self):
        """Downloads and loads the instrument master list."""
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"
        file_path = "NSE.csv.gz"
        csv_path = "NSE.csv"
        
        try:
            # Check if file exists and is recent (e.g., < 24 hours)
            should_download = True
            if os.path.exists(csv_path):
                file_time = datetime.fromtimestamp(os.path.getmtime(csv_path))
                if datetime.now() - file_time < timedelta(hours=24):
                    should_download = False
                    print("Using cached instruments file.")
            
            if should_download:
                print("Downloading instruments...")
                # Download
                response = requests.get(url, stream=True)
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                # Extract
                with gzip.open(file_path, 'rb') as f_in:
                    with open(csv_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            
            # Load
            self.instruments_df = pd.read_csv(csv_path)
            # Standardize expiry to datetime
            if 'expiry' in self.instruments_df.columns:
                self.instruments_df['expiry'] = pd.to_datetime(self.instruments_df['expiry'], errors='coerce')
                # Keep as YYYY-MM-DD string for easier filtering if needed, or keep as datetime
                # Let's keep as datetime for robust comparison, but we need to ensure we compare with datetime
            print("Instruments loaded successfully.")
        except Exception as e:
            print(f"Error loading instruments: {e}")

        def get_next_weekly_expiry(self):
            """
            Returns the next Thursday expiry date for NIFTY options.
            """
            today = datetime.now()
            days_ahead = (3 - today.weekday()) % 7
            expiry = today + timedelta(days=days_ahead)
            # If today is Thursday and after market close, pick next Thursday
            if today.weekday() == 3 and today.hour >= 15:
                expiry += timedelta(days=7)
            return expiry.strftime('%Y-%m-%d')

        def get_weekly_option_key(self, symbol, strike, option_type):
            """
            Returns the correct instrument key for the current week's NIFTY option.
            """
            expiry = self.get_next_weekly_expiry()
            if self.instruments_df is None:
                self.load_instruments()
            expiry_dt = pd.to_datetime(expiry)
            filtered = self.instruments_df[
                (self.instruments_df['name'] == symbol) &
                (self.instruments_df['instrument_type'] == 'OPTIDX') &
                (self.instruments_df['strike'] == float(strike)) &
                (self.instruments_df['option_type'] == option_type) &
                (self.instruments_df['expiry'] == expiry_dt)
            ]
            if not filtered.empty:
                tradingsymbol = filtered.iloc[0]['tradingsymbol']
                return f"NSE_FO|{tradingsymbol}"
            else:
                print(f"No instrument found for {symbol} {expiry} {strike} {option_type}")
                return None
    def get_option_instrument_key(self, symbol, expiry, strike, option_type):
        """
        Finds the instrument key for a specific option contract.
        symbol: 'NIFTY'
        expiry: '2023-11-23' (Format needs to match CSV)
        strike: 19500.0
        option_type: 'CE' or 'PE'
        """
        if self.instruments_df is None:
            self.load_instruments()
            
        # Filter logic (This depends on the exact CSV format, assuming standard columns)
        # Columns usually: instrument_key, exchange_token, tradingsymbol, name, last_price, expiry, strike, tick_size, lot_size, instrument_type, option_type, exchange
        
        # Note: This is a simplified filter and might need adjustment based on actual CSV columns
        # Let's assume 'tradingsymbol' or structured query
        try:
            # Ensure expiry is in the same format (datetime or string)
            # The CSV expiry is likely YYYY-MM-DD
            if isinstance(expiry, str):
                expiry = pd.to_datetime(expiry)
            
            
            filtered = self.instruments_df[
                (self.instruments_df['name'] == symbol) & 
                (self.instruments_df['instrument_type'] == 'OPTIDX') &
                (self.instruments_df['strike'] == float(strike)) &
                (self.instruments_df['option_type'] == option_type) &
                (self.instruments_df['expiry'] == expiry)
            ]
            
            # Debug logging
            print(f"🔍 Searching for option: {symbol} {expiry} {strike} {option_type}")
            print(f"   Found {len(filtered)} matching instruments")
            
            # Sort by expiry and pick the closest one if expiry is not exact or just pick the requested one
            # For now, let's just return the first match's instrument_key
            if not filtered.empty:
                # Return the correct instrument_key format: NSE_FO|token (e.g., NSE_FO|65628)
                key = filtered.iloc[0]['instrument_key']
                
                # Ensure it's a string and has pipe separator
                if isinstance(key, str) and '|' in key:
                    print(f"   ✅ Found key: {key}")  
                    return key
                else:
                    print(f"   ❌ Invalid key format: {key} (type: {type(key)})")
                    return None
            else:
                print(f"   ❌ Instrument not found for {symbol} {expiry} {strike} {option_type}")
                # Show what's available for this expiry
                available = self.instruments_df[
                    (self.instruments_df['name'] == symbol) & 
                    (self.instruments_df['instrument_type'] == 'OPTIDX') &
                    (self.instruments_df['expiry'] == expiry)
                ]
                if not available.empty:
                    print(f"   Available strikes for {expiry}: {sorted(available['strike'].unique()[:10])}")
                return None
        except Exception as e:
            print(f"Error finding instrument: {e}")
            return None


    def get_historical_data(self, instrument_key, interval, from_date, to_date):
        """
        Fetches historical candle data.
        interval: '1minute', '5minute', '30minute', 'day', etc.
        """
        try:
            print(f"📊 Fetching historical data for {instrument_key} from {from_date} to {to_date}...")
            
            # Build URL with proper URL encoding for instrument key
            encoded_key = urllib.parse.quote(instrument_key)
            url = f"{self.base_url}/historical-candle/{encoded_key}/{interval}/{to_date}/{from_date}"
            print(f"🔗 API URL: {url}")
            print(f"🔐 Access Token present: {bool(self.access_token)}")
            
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            print(f"📤 Sending request...")
            response = requests.get(url, headers=headers, timeout=30)
            
            print(f"📥 Response status: {response.status_code}")
            print(f"📋 Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Response JSON received: {str(data)[:500]}")
                
                if 'data' in data and 'candles' in data['data']:
                    candles = data['data']['candles']
                    print(f"✅ Found {len(candles)} candles in response")
                    # Candles are usually [timestamp, open, high, low, close, volume, oi]
                    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df.set_index('timestamp')  # Set timestamp as index
                    df = df.sort_index()  # Sort by index
                    print(f"✅ Loaded {len(df)} candles into DataFrame")
                    print(f"   First timestamp: {df.index[0]}, Last timestamp: {df.index[-1]}")
                    return df
                else:
                    print(f"⚠️  Response format unexpected. Keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
                    print(f"📄 Full response: {str(data)[:1000]}")
                    return None
            else:
                print(f"❌ Error fetching data: {response.status_code}")
                print(f"📄 Response body: {response.text[:500]}")
                return None
        except requests.Timeout:
            print(f"⏱️  Request timeout: Historical data fetch took too long (30s)")
            return None
        except requests.ConnectionError as e:
            print(f"🔌 Connection error: {e}")
            return None
        except Exception as e:
            print(f"❌ Exception in get_historical_data: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_option_chain(self, instrument_key, expiry_date):
        # This would require a specific endpoint or logic to parse option chain
        # For now, we might just fetch specific option contracts if we know the symbol
        pass

    def get_nifty_pcr(self, spot_price):
        """
        Calculates Put-Call Ratio (PCR) for Nifty 50 based on nearest expiry and strikes around spot.
        """
        if self.instruments_df is None:
            self.load_instruments()
            
        if self.instruments_df is None or self.instruments_df.empty:
            print("Instruments not loaded, cannot calculate PCR.")
            return None

        try:
            # 1. Filter for Nifty Options
            nifty_opts = self.instruments_df[
                (self.instruments_df['name'] == 'NIFTY') & 
                (self.instruments_df['instrument_type'] == 'OPTIDX')
            ].copy()
            
            if nifty_opts.empty:
                print("No Nifty options found in instruments master.")
                return None

            # 2. Find Nearest Expiry
            # Convert expiry column to datetime if not already
            if nifty_opts['expiry'].dtype == 'object':
                nifty_opts['expiry'] = pd.to_datetime(nifty_opts['expiry'])
                
            today = datetime.now()
            # Filter for future expiries
            future_opts = nifty_opts[nifty_opts['expiry'] >= today]
            
            if future_opts.empty:
                print("No future expiries found.")
                return None
                
            # Get the nearest expiry date
            nearest_expiry = future_opts['expiry'].min()
            
            # 3. Filter for Strikes around Spot (+/- 500 points)
            strike_range = 500
            relevant_opts = future_opts[
                (future_opts['expiry'] == nearest_expiry) &
                (future_opts['strike'] >= spot_price - strike_range) &
                (future_opts['strike'] <= spot_price + strike_range)
            ]
            
            if relevant_opts.empty:
                print(f"No options found for expiry {nearest_expiry} around {spot_price}")
                return None
                
            # 4. Get Instrument Keys - use the correct format from CSV (NSE_FO|token)
            instrument_keys = relevant_opts['instrument_key'].tolist()
            
            # 5. Fetch Quotes (OI)
            # Upstox allows fetching multiple quotes. Max limit usually exists (e.g., 100).
            # We might have ~20 strikes * 2 types = 40 keys. Should be fine.
            
            # 5. Fetch Quotes (OI)
            quotes = self.get_quotes(instrument_keys)
            
            total_ce_oi = 0
            total_pe_oi = 0
            
            for key, quote in quotes.items():
                    
                    for key, quote in quotes.items():
                        # Find option type from our dataframe
                        opt_info = relevant_opts[relevant_opts['instrument_key'] == key]
                        if not opt_info.empty:
                            opt_type = opt_info.iloc[0]['option_type']
                            oi = quote.get('oi', 0)
                            
                            if opt_type == 'CE':
                                total_ce_oi += oi
                            elif opt_type == 'PE':
                                total_pe_oi += oi
                                
                    if total_ce_oi > 0:
                        pcr = total_pe_oi / total_ce_oi
                        return round(pcr, 2)
                    else:
                        return 0
                
        except Exception as e:
            print(f"Error calculating PCR: {e}")
            return None

    def get_current_price(self, instrument_key):
        url = f"{self.base_url}/market-quote/ltp"
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        params = {'instrument_key': instrument_key}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            # Parse LTP
            try:
                # Upstox sometimes returns keys with ':' instead of '|'
                # Let's try the requested key first
                if instrument_key in data['data']:
                    return data['data'][instrument_key]['last_price']
                
                # Try replacing | with :
                alt_key = instrument_key.replace('|', ':')
                if alt_key in data['data']:
                    return data['data'][alt_key]['last_price']
                    
                # Fallback: if data has only one key, use it
                if len(data['data']) == 1:
                    first_key = list(data['data'].keys())[0]
                    return data['data'][first_key]['last_price']
                    
                print(f"Key {instrument_key} not found in response: {data['data'].keys()}")
                return None
            except KeyError:
                print(f"KeyError parsing response: {data}")
                return None
        else:
            print(f"Error fetching price: {response.status_code} - {response.text}")
        return None
        return None

    def get_india_vix(self):
        """Fetches the current value of India VIX."""
        # Instrument key for India VIX from NSE.csv check: "NSE_INDEX|India VIX"
        vix_key = "NSE_INDEX|India VIX"
        return self.get_current_price(vix_key)

    def _get_symbol_info(self, instrument_keys):
        """Helper method to get symbol info from instrument keys for better logging."""
        if self.instruments_df is None:
            return {}
        
        symbol_info = {}
        for key in instrument_keys:
            try:
                # Try to match the key in the dataframe
                matches = self.instruments_df[self.instruments_df['instrument_key'] == key]
                if not matches.empty:
                    match = matches.iloc[0]
                    symbol_info[key] = f"{match.get('name', 'N/A')} ({match.get('trading_symbol', 'N/A')})"
                else:
                    symbol_info[key] = "Unknown"
            except Exception as e:
                symbol_info[key] = f"Error mapping: {str(e)}"
        return symbol_info

    def get_quotes(self, instrument_keys):
        if not instrument_keys:
            return {}
            
        # Validate all instrument keys before making API call
        invalid_keys = [key for key in instrument_keys if not self._is_valid_instrument_key(key)]
        if invalid_keys:
            self.logger.error(f"❌ Invalid instrument keys found: {invalid_keys}. Expected format: NSE_FO|xxxxx")
            self.logger.error(f"Please ensure instrument_keys are in Upstox format (e.g., NSE_FO|52910)")
            return {}
        
        # Split keys into chunks of 100 if needed (Upstox limit)
        # For now assuming < 100 keys
        
        url = f"{self.base_url}/market-quote/quotes"
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        params = {'instrument_key': ','.join(instrument_keys)}
        
        # Get symbol info for better logging
        symbol_info = self._get_symbol_info(instrument_keys)
        symbol_info_str = " | ".join([f"{key}: {symbol_info.get(key, 'N/A')}" for key in instrument_keys])
        
        try:
            self.logger.info(f"🔍 Fetching quotes for {len(instrument_keys)} keys: {symbol_info_str}")
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    return data['data']
                else:
                    self.logger.error(f"❌ Error fetching quotes (no data): {data} | Keys: {symbol_info_str}")
            else:
                self.logger.error(f"❌ Error fetching quotes: {response.status_code} - {response.text} | Keys: {symbol_info_str}")
        except Exception as e:
            self.logger.error(f"❌ Exception fetching quotes: {e} | Keys: {symbol_info_str}")
            
        return {}
    
    def _is_valid_instrument_key(self, instrument_key: str) -> bool:
        """Validate instrument_key format - should be NSE_FO|xxxxx or NSE_INDEX|xxxxx."""
        if not instrument_key or not isinstance(instrument_key, str):
            return False
        # Valid format: NSE_FO|NIFTY25NOV26050CE or NSE_FO|52910 or NSE_INDEX|Nifty 50
        parts = instrument_key.split('|')
        if len(parts) != 2:
            return False
        exchange, key = parts
        if exchange not in ['NSE_FO', 'NSE_INDEX', 'NSE_EQ']:
            return False
        if not key or len(key.strip()) == 0:
            return False
        return True

    def get_nearest_expiry(self):
        if self.instruments_df is None:
            self.load_instruments()
            
        today = datetime.now().date()
        
        # Filter for Nifty Options
        nifty_opts = self.instruments_df[
            (self.instruments_df['name'] == 'NIFTY') & 
            (self.instruments_df['instrument_type'] == 'OPTIDX')
        ].copy()
        
        # Convert expiry to date
        nifty_opts['expiry'] = pd.to_datetime(nifty_opts['expiry']).dt.date
        
        # Filter future expiries
        future_opts = nifty_opts[nifty_opts['expiry'] >= today]
        
        if future_opts.empty:
            return None
            
        return future_opts['expiry'].min().strftime("%Y-%m-%d")

    def get_atm_strike(self, spot_price, step=50):
        return round(spot_price / step) * step

    def get_option_greeks(self, spot_price, expiry_date=None):
        """
        Fetch ATM option prices and calculate Greeks.
        """
        if expiry_date is None:
            expiry_date = self.get_nearest_expiry()
            
        if not expiry_date:
            return None

        atm_strike = self.get_atm_strike(spot_price)
        T = self.greeks_calculator.time_to_expiry(expiry_date)
        
        # Get Instrument Keys for ATM CE and PE
        self.logger.info(f"🔍 Finding option instruments for expiry={expiry_date}, strike={atm_strike}")
        
        ce_key = self.get_option_instrument_key("NIFTY", expiry_date, atm_strike, "CE")
        pe_key = self.get_option_instrument_key("NIFTY", expiry_date, atm_strike, "PE")
        
        if not ce_key or not pe_key:
            self.logger.error(f"❌ Could not find instrument keys")
            self.logger.error(f"   CE Key: {ce_key}")
            self.logger.error(f"   PE Key: {pe_key}")
            self.logger.error(f"   Expiry: {expiry_date}, Strike: {atm_strike}")
            return None
        
        # Validate keys
        if not self._is_valid_instrument_key(ce_key) or not self._is_valid_instrument_key(pe_key):
            self.logger.error(f"❌ Invalid instrument key format!")
            self.logger.error(f"   CE Key: {ce_key} (valid={self._is_valid_instrument_key(ce_key)})")
            self.logger.error(f"   PE Key: {pe_key} (valid={self._is_valid_instrument_key(pe_key)})")
            return None
        
        self.logger.info(f"✅ Found valid instrument keys:")
        self.logger.info(f"   CE: {ce_key}")
        self.logger.info(f"   PE: {pe_key}")

        # Fetch Market Prices
        quotes = self.get_quotes([ce_key, pe_key])
        
        # If quotes fail, log error and return None (no mock data)
        if not quotes:
            self.logger.error(f"❌ Failed to fetch option quotes for strike {atm_strike}")
            self.logger.error(f"   CE Key: {ce_key}")
            self.logger.error(f"   PE Key: {pe_key}")
            self.logger.error(f"   Check instrument key format and API authentication")
            return None

        ce_price = quotes.get(ce_key, {}).get('last_price', 0)
        pe_price = quotes.get(pe_key, {}).get('last_price', 0)

        # If prices are 0, return None (don't use mock data)
        if ce_price == 0 or pe_price == 0:
            self.logger.error(f"❌ Option prices are zero: CE={ce_price}, PE={pe_price}")
            self.logger.error(f"   API returned quotes but prices are invalid")
            return None

        # Calculate IV
        ce_iv = self.greeks_calculator.implied_volatility(ce_price, spot_price, atm_strike, T, 'CE')
        pe_iv = self.greeks_calculator.implied_volatility(pe_price, spot_price, atm_strike, T, 'PE')

        # Calculate Greeks
        ce_greeks = self.greeks_calculator.calculate_greeks(spot_price, atm_strike, T, ce_iv, 'CE')
        pe_greeks = self.greeks_calculator.calculate_greeks(spot_price, atm_strike, T, pe_iv, 'PE')

        return {
            'atm_strike': atm_strike,
            'expiry_date': expiry_date,
            'ce_instrument_key': ce_key,
            'pe_instrument_key': pe_key,
            'ce': {**ce_greeks, 'iv': ce_iv, 'price': ce_price},
            'pe': {**pe_greeks, 'iv': pe_iv, 'price': pe_price}
        }
