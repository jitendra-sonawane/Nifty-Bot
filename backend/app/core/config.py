import os
from dotenv import load_dotenv
import json
import base64
import time

# Load environment variables
load_dotenv()

class Config:
    API_KEY = os.getenv("UPSTOX_API_KEY")
    API_SECRET = os.getenv("UPSTOX_API_SECRET")
    REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")
    ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
    
    # Trading Configuration
    TIMEFRAME = "1minute"  # Upstox API format (1minute, 30minute, day, week, month)
    SYMBOL_NIFTY_50 = "NSE_INDEX|Nifty 50"
    
    # Strategy Parameters
    EMA_SHORT_PERIOD = 5
    EMA_LONG_PERIOD = 20
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 55
    RSI_OVERSOLD = 45
    
    # Risk Management
    TARGET_RATIO = 2.0  # 1:2 Risk Reward
    STOP_LOSS_PERCENT = 0.10 # 10% SL on premium

    @classmethod
    def reload(cls):
        """Reload environment variables from .env file.
        Useful after saving a new access token at runtime.
        """
        # Force reload of environment
        import sys
        if 'dotenv' in sys.modules:
            # Clear any cached environment variables
            del sys.modules['dotenv']
        
        from dotenv import load_dotenv
        load_dotenv(override=True)  # Force override existing variables
        
        cls.API_KEY = os.getenv("UPSTOX_API_KEY")
        cls.API_SECRET = os.getenv("UPSTOX_API_SECRET")
        cls.REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")
        cls.ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
        
        # Debug logging
        import logging
        logger = logging.getLogger("config_reload")
        logger.info(f"✅ Config reloaded: Token={'SET' if cls.ACCESS_TOKEN else 'NOT SET'}")
    
    @classmethod
    def is_token_valid(cls) -> dict:
        """Check if the access token is valid (not expired).
        Returns a dict with 'is_valid', 'expires_at', 'remaining_seconds', 'error_message'
        """
        token = cls.ACCESS_TOKEN
        
        if not token:
            return {
                "is_valid": False,
                "expires_at": None,
                "remaining_seconds": 0,
                "error_message": "No access token found. Please authenticate with Upstox."
            }
        
        try:
            # Decode JWT (without verification, just for diagnostics)
            parts = token.split('.')
            if len(parts) != 3:
                return {
                    "is_valid": False,
                    "expires_at": None,
                    "remaining_seconds": 0,
                    "error_message": "Invalid token format (not JWT)"
                }
            
            # Add padding if needed
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            
            current_time = time.time()
            exp_time = decoded.get('exp', 0)
            remaining = exp_time - current_time
            
            if remaining <= 0:
                return {
                    "is_valid": False,
                    "expires_at": exp_time,
                    "remaining_seconds": int(remaining),
                    "error_message": f"Access token expired {int(abs(remaining))} seconds ago. Please re-authenticate."
                }
            
            return {
                "is_valid": True,
                "expires_at": exp_time,
                "remaining_seconds": int(remaining),
                "error_message": None
            }
        except Exception as e:
            return {
                "is_valid": False,
                "expires_at": None,
                "remaining_seconds": 0,
                "error_message": f"Error validating token: {str(e)}"
            }
