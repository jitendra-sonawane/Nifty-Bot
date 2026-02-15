import os
from dotenv import load_dotenv
import json
import base64
import time

# Load environment variables
from pathlib import Path

# Load environment variables from backend directory
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Config:
    API_KEY = os.getenv("UPSTOX_API_KEY")
    API_SECRET = os.getenv("UPSTOX_API_SECRET")
    REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")
    ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
    SANDBOX_TOKEN = os.getenv("UPSTOX_SANDBOX_TOKEN", "")
    
    # ── Trading Mode ──────────────────────────────────────────────────
    # "sandbox" = Upstox sandbox API (real API structure, dummy execution)
    # "paper"   = Local paper trading (virtual wallet, no API calls)
    # "live"    = Real money trading (use with extreme caution)
    TRADING_MODE = os.getenv("TRADING_MODE", "paper")
    
    # ── Nifty 50 Constants ────────────────────────────────────────────
    SYMBOL_NIFTY_50 = "NSE_INDEX|Nifty 50"
    NIFTY_LOT_SIZE = 25       # Nifty 50 lot size (as of 2024)
    NIFTY_STRIKE_STEP = 50    # Strike price interval
    INITIAL_CAPITAL = 1000000  # ₹10,00,000 default paper capital
    
    # ── Timeframe ─────────────────────────────────────────────────────
    TIMEFRAME = "5minute"
    
    # ── Indicator Parameters (used by StrategyEngine) ─────────────────
    EMA_SHORT_PERIOD = 5
    EMA_LONG_PERIOD = 20
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 55
    RSI_OVERSOLD = 45
    
    # ── Risk Management ───────────────────────────────────────────────
    TARGET_RATIO = 2.0
    STOP_LOSS_PERCENT = 0.10
    RISK_PER_TRADE_PCT = 0.02      # 2% of capital per trade
    DAILY_LOSS_LIMIT_PCT = 0.05    # 5% max daily loss
    MAX_CONCURRENT_POSITIONS = 3
    
    # ── Active Strategy ───────────────────────────────────────────────
    ACTIVE_STRATEGY = os.getenv("ACTIVE_STRATEGY", "iron_condor")
    
    # ── Iron Condor Strategy Parameters ───────────────────────────────
    IRON_CONDOR = {
        "short_offset": 100,       # Short strikes: ATM ± 100 pts
        "wing_width": 200,         # Long strikes: short ± 200 pts (hedge)
        "entry_time": "09:30",     # Enter after market settles
        "exit_time": "15:15",      # Square off before close
        "max_loss_pct": 0.50,      # Exit if loss > 50% of max risk
        "target_pct": 0.60,        # Exit at 60% of collected premium
        "iv_percentile_min": 30,   # Min IV percentile to enter
        "max_lots": 4,             # Max lots per leg
        "vix_max": 20,             # Block entry if VIX exceeds this
        "rsi_lower": 35,           # RSI floor for range-bound filter
        "rsi_upper": 65,           # RSI ceiling for range-bound filter
        "min_dte": 1,              # Min days to expiry (block on expiry day)
        "trailing_sl": True,       # Enable trailing stop loss
        "trailing_sl_pct": 0.40,   # Trail at 40% drawdown from peak profit
    }
    
    # ── Short Straddle Strategy Parameters ────────────────────────────
    SHORT_STRADDLE = {
        "strike_offset": 0,        # ATM by default
        "sl_points": 100,          # Stop loss in Nifty points movement
        "target_pct": 0.30,        # Target 30% of collected premium
        "entry_time": "09:20",     # Early entry for max theta
        "exit_time": "15:15",      # Square off before close
        "adjustment_threshold": 150,  # Shift strikes if Nifty moves 150+ pts
        "max_lots": 2,             # Max lots per leg
    }
    
    # ── Bull Call / Bear Put Spread Parameters ────────────────────────
    DIRECTIONAL_SPREAD = {
        "spread_width": 100,       # Distance between buy/sell strikes
        "entry_time": "09:30",
        "exit_time": "15:15",
        "target_pct": 0.50,        # Target 50% of max profit
        "sl_pct": 0.40,            # Stop at 40% of max loss
        "min_signal_confidence": 0.6,  # Min confidence from indicator engine
        "max_lots": 4,
    }
    
    # ── Breakout Strategy Parameters ──────────────────────────────────
    BREAKOUT = {
        "lookback_candles": 20,    # Candles for S/R calculation
        "volume_multiplier": 1.5,  # Volume spike threshold
        "entry_time": "09:45",     # Wait for initial volatility
        "exit_time": "15:15",
        "trailing_sl_atr_mult": 1.5,  # Trailing SL = 1.5 × ATR
        "target_rr_ratio": 2.0,    # Risk:Reward = 1:2
        "max_lots": 2,
    }

    # ── Intelligence Engine ────────────────────────────────────────────────
    INTELLIGENCE = {
        # MarketRegimeModule
        "adx_trending_threshold":  25,    # ADX >= 25 → trending regime
        "adx_ranging_threshold":   20,    # ADX < 20 → ranging regime
        "bb_squeeze_pct":           1.5,  # BB width < 1.5% → squeeze / ranging
        "bb_expansion_pct":         3.0,  # BB width > 3.0% → trending / volatile
        "atr_high_vol_pct":         1.2,  # ATR% > 1.2% → high-volatility regime

        # IVRankModule
        "iv_sell_premium_rank":    60,    # IV Rank >= 60 → premium selling ok
        "iv_buy_debit_rank":       30,    # IV Rank <= 30 → buy debit spreads
        "iv_block_below_rank":     20,    # IV Rank < 20 → block all entries (IV too cheap)

        # MarketBreadthModule
        "breadth_strong_bullish":  35,    # >= 35/50 stocks advancing → strong bull
        "breadth_bullish":         28,    # >= 28/50 → bullish
        "breadth_bearish":         22,    # <= 22/50 → bearish
        "breadth_strong_bearish":  15,    # <= 15/50 → strong bear

        # OrderBookModule
        "spread_excellent_pct":    0.3,   # Bid-ask spread < 0.3% → excellent
        "spread_good_pct":         1.0,   # Bid-ask spread < 1.0% → good, else POOR

        # PortfolioGreeksModule
        "delta_hedge_threshold":   0.30,  # |net_delta| > 0.30 → hedge needed
    }

    # ── Expiry Day (0DTE) Special Handling ────────────────────────────────
    EXPIRY_DAY = {
        "block_breakout": True,              # No breakout entries on expiry day
        "sl_tightening_factor": 0.6,         # Tighten SL to 60% of normal
        "position_size_factor": 0.5,         # Half position size on 0DTE
        "block_new_entries_after": "14:00",  # No new entries after 2 PM on expiry
        "gamma_warning_threshold": 0.05,     # Warn if gamma > 0.05
    }

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
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parent.parent.parent / '.env'
        load_dotenv(dotenv_path=env_path, override=True)  # Force override existing variables
        
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
