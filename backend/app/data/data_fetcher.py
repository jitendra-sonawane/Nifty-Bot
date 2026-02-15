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
    # Upstox v3 API supports extended intervals
    SUPPORTED_INTERVALS = [
        '1minute', '5minute', '10minute', '15minute', '30minute', '60minute',
        '1hour', '2hour', '3hour', '4hour', '5hour',
        'day', 'week', 'month'
    ]
    
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token
        self.logger = logger
        self.base_url_v2 = "https://api.upstox.com/v2"
        self.base_url_v3 = "https://api.upstox.com/v3"
        
        # Configure SDK client
        configuration = upstox_client.Configuration()
        configuration.access_token = access_token
        self.api_instance = upstox_client.HistoryApi(upstox_client.ApiClient(configuration))
        self.api_instance = upstox_client.HistoryApi(upstox_client.ApiClient(configuration))
        self.instruments_df = None
        self.greeks_calculator = GreeksCalculator()
        self.token_valid = True  # Flips to False on 401 / UDAPI100050
        


    def set_access_token(self, token):
        self.access_token = token
        self.token_valid = True  # Reset on new token
        configuration = upstox_client.Configuration()
        configuration.access_token = token
        self.api_instance = upstox_client.HistoryApi(upstox_client.ApiClient(configuration))
        print("DataFetcher: Access Token updated.")

    def _is_token_error(self, response) -> bool:
        """
        Check if an API response indicates a token error (expired / invalid).
        Logs a clear, actionable message and sets self.token_valid = False.
        Returns True if a token error was detected.
        """
        if response.status_code == 401:
            self.token_valid = False
            self.logger.error(
                "🔑 TOKEN EXPIRED (401) — re-authenticate via the dashboard Login button"
            )
            return True
        # Upstox sometimes returns 200 with an error body
        if response.status_code == 200:
            try:
                body = response.json()
                if isinstance(body, dict) and body.get("status") == "error":
                    codes = [e.get("errorCode", "") for e in body.get("errors", [])]
                    if "UDAPI100050" in codes or any("token" in c.lower() for c in codes):
                        self.token_valid = False
                        self.logger.error(
                            "🔑 TOKEN INVALID (UDAPI100050) — re-authenticate via the dashboard Login button"
                        )
                        return True
            except Exception:
                pass
        return False

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
        Fetches historical candle data using Upstox v3 API.
        interval: '1minute', '5minute', '10minute', '15minute', '30minute', '60minute',
                  '1hour', '2hour', '3hour', '4hour', '5hour',
                  'day', 'week', 'month'
        from_date: 'YYYY-MM-DD' format
        to_date: 'YYYY-MM-DD' format
        """
        try:
            if interval not in self.SUPPORTED_INTERVALS:
                self.logger.error(f"❌ Unsupported interval: {interval}")
                self.logger.error(f"   Supported intervals: {self.SUPPORTED_INTERVALS}")
                return None
            
            try:
                if isinstance(from_date, str):
                    from_date_obj = datetime.strptime(from_date, "%d-%m-%Y") if "-" in from_date and len(from_date.split("-")[0]) == 2 else datetime.strptime(from_date, "%Y-%m-%d")
                    from_date = from_date_obj.strftime("%Y-%m-%d")
                if isinstance(to_date, str):
                    to_date_obj = datetime.strptime(to_date, "%d-%m-%Y") if "-" in to_date and len(to_date.split("-")[0]) == 2 else datetime.strptime(to_date, "%Y-%m-%d")
                    to_date = to_date_obj.strftime("%Y-%m-%d")
            except Exception as e:
                self.logger.error(f"❌ Invalid date format: {e}")
                return None
            
            self.logger.info(f"📊 Fetching v3 historical data: {instrument_key} | {interval} | {from_date} to {to_date}")
            
            # Parse interval to extract unit and interval value
            # Format: '5minute' -> unit='minutes', interval_value='5'
            # Format: 'day' -> unit='days', interval_value='1'
            # Note: Upstox v3 API expects PLURAL units: minutes, hours, days, weeks, months
            if interval in ['day', 'week', 'month']:
                unit = interval + 's'  # Convert to plural: day -> days
                interval_value = '1'
            elif interval.endswith('minute'):
                unit = 'minutes'
                interval_value = interval.replace('minute', '')
            elif interval.endswith('hour'):
                unit = 'hours'
                interval_value = interval.replace('hour', '')
            else:
                self.logger.error(f"❌ Unable to parse interval format: {interval}")
                return None
            
            encoded_key = urllib.parse.quote(instrument_key)
            url = f"{self.base_url_v3}/historical-candle/{encoded_key}/{unit}/{interval_value}/{to_date}/{from_date}"
            
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            response = requests.get(url, headers=headers, timeout=30)

            if self._is_token_error(response):
                return None

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'candles' in data['data']:
                    candles = data['data']['candles']
                    self.logger.info(f"✅ Found {len(candles)} candles")
                    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df.set_index('timestamp')
                    df = df.sort_index()
                    return df
                else:
                    self.logger.error(f"⚠️ Unexpected response format: {data.keys() if isinstance(data, dict) else 'N/A'}")
                    return None
            else:
                self.logger.error(f"❌ Error {response.status_code}: {response.text[:500]}")
                return None
        except requests.Timeout:
            self.logger.error(f"⏱️ Request timeout (30s)")
            return None
        except requests.ConnectionError as e:
            self.logger.error(f"🔌 Connection error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"❌ Exception: {type(e).__name__}: {e}")
            return None

    def get_intraday_data(self, instrument_key, interval):
        """
        Fetches intraday candle data for the current day using Upstox v3 API.
        This closes the gap between historical data (which ends yesterday) and live stream.
        """
        try:
            # Parse interval to V3 format: 'minutes/1', 'minutes/5', 'minutes/15', 'minutes/30'
            interval_map = {
                '1minute': 'minutes/1',
                '5minute': 'minutes/5',
                '10minute': 'minutes/10', # Note: Verify 10min support, otherwise fallback or resample
                '15minute': 'minutes/15',
                '30minute': 'minutes/30',
                '60minute': 'minutes/60',
            }
            
            v3_interval = interval_map.get(interval)
            
            if not v3_interval:
                # Fallback logic or default
                if interval == '10minute':
                    # Upstox V3 might not support 10min directly in intraday, use 5min and resample later?
                    # For now let's try strict mapping or error.
                    # Actually, V3 intraday supports specific intervals. Let's assume standard ones.
                    v3_interval = 'minutes/10' # Try blindly
                else:
                    self.logger.warning(f"⚠️ Interval {interval} might not be supported for Intraday API. Defaulting to 1minute.")
                    v3_interval = 'minutes/1'

            encoded_key = urllib.parse.quote(instrument_key)
            url = f"{self.base_url_v3}/historical-candle/intraday/{encoded_key}/{v3_interval}"
            
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.access_token}'
            }
            
            self.logger.info(f"📊 Fetching Intraday data: {instrument_key} | {v3_interval}")
            response = requests.get(url, headers=headers, timeout=10)

            if self._is_token_error(response):
                return None

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'candles' in data['data']:
                    candles = data['data']['candles']
                    if candles:
                        self.logger.info(f"✅ Found {len(candles)} Intraday candles")
                        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df = df.set_index('timestamp')
                        df = df.sort_index()
                        return df
                    else:
                        self.logger.info(f"ℹ️ Intraday data empty (Market might be closed or just opened)")
                        return None
                else:
                    self.logger.error(f"⚠️ Unexpected Intraday response format")
                    return None
            else:
                self.logger.warning(f"⚠️ Intraday fetch failed: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Exception fetching Intraday data: {e}")
            return None

    def get_option_chain(self, instrument_key, expiry_date):
        # This would require a specific endpoint or logic to parse option chain
        # For now, we might just fetch specific option contracts if we know the symbol
        pass

    def get_nifty_pcr(self, spot_price):
        """
        Calculates Nifty PCR (Put-Call Ratio) using Option Chain.
        
        DEPRECATED: This method uses HTTP polling. Use MarketDataManager's WebSocket-based
        PCR calculation for real-time data instead.
        """
        self.logger.info(f"📊 [PCR] Starting: spot={spot_price}")
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
            self.logger.info(f" instrument_keys: {instrument_keys[:5]}... (total {len(instrument_keys)})")
            if not greeks_data:
                self.logger.error(f"❌ [PCR] No greeks data")
                return None
            self.logger.info(f"✅ [PCR] Got {len(greeks_data)} greeks")
            
            total_ce_oi = 0
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
            return None

    def get_current_price(self, instrument_key):
        url = f"{self.base_url_v2}/market-quote/ltp"
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        params = {'instrument_key': instrument_key}
        response = requests.get(url, headers=headers, params=params)
        if self._is_token_error(response):
            return None
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
            
        invalid_keys = [key for key in instrument_keys if not self._is_valid_instrument_key(key)]
        if invalid_keys:
            self.logger.error(f"❌ Invalid instrument keys found: {invalid_keys}. Expected format: NSE_FO|xxxxx")
            self.logger.error(f"Please ensure instrument_keys are in Upstox format (e.g., NSE_FO|52910)")
            return {}
        
        url = f"{self.base_url_v2}/market-quote/quotes"
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
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if self._is_token_error(response):
                return {}
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
    
    def get_available_strikes(self, symbol, expiry_date):
        """Get all available strikes for a symbol and expiry."""
        if self.instruments_df is None:
            self.load_instruments()
            
        if isinstance(expiry_date, str):
            expiry_date = pd.to_datetime(expiry_date)
            
        filtered = self.instruments_df[
            (self.instruments_df['name'] == symbol) & 
            (self.instruments_df['instrument_type'] == 'OPTIDX') &
            (self.instruments_df['expiry'] == expiry_date)
        ]
        
        if not filtered.empty:
            return sorted(filtered['strike'].unique())
        return []

    def get_option_greeks_batch(self, instrument_keys):
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
        return {}

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
