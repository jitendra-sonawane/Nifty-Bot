"""
Nifty 50 Heatmap API
Fetches live market quotes for all Nifty 50 stocks using Upstox Full Market Quotes API.
Endpoint: GET /v2/market-quote/quotes with NSE_EQ|{ISIN} keys.
"""

import time
import requests
import logging

try:
    from app.core.logger_config import logger
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# NIFTY 50 CONSTITUENT DATA (symbol → ISIN)
# ═══════════════════════════════════════════

NIFTY50_STOCKS = {
    "HDFCBANK":    "INE040A01034",
    "ICICIBANK":   "INE090A01021",
    "SBIN":        "INE062A01020",
    "KOTAKBANK":   "INE237A01028",
    "AXISBANK":    "INE238A01034",
    "BAJFINANCE":  "INE296A01024",
    "BAJAJFINSV":  "INE918I01018",
    "HDFCLIFE":    "INE795G01014",
    "SBILIFE":     "INE123W01016",
    "SHRIRAMFIN":  "INE721A01013",
    "INFY":        "INE009A01021",
    "TCS":         "INE467B01029",
    "HCLTECH":     "INE860A01027",
    "WIPRO":       "INE075A01022",
    "TECHM":       "INE669C01036",
    "RELIANCE":    "INE002A01018",
    "ONGC":        "INE213A01029",
    "NTPC":        "INE733E01010",
    "POWERGRID":   "INE752E01010",
    "BPCL":        "INE029A01011",
    "COALINDIA":   "INE522F01014",
    "ADANIENT":    "INE423A01024",
    "ADANIPORTS":  "INE742F01042",
    "HINDUNILVR":  "INE030A01027",
    "ITC":         "INE154A01025",
    "NESTLEIND":   "INE239A01016",
    "TATACONSUM":  "INE192A01025",
    "BRITANNIA":   "INE216A01030",
    "M&M":         "INE101A01026",
    "MARUTI":      "INE585B01010",
    "TATAMOTORS":  "INE155A01022",
    "BAJAJ-AUTO":  "INE917I01010",
    "EICHERMOT":   "INE066A01021",
    "HEROMOTOCO":  "INE158A01026",
    "TATASTEEL":   "INE081A01020",
    "JSWSTEEL":    "INE019A01038",
    "HINDALCO":    "INE038A01020",
    "SUNPHARMA":   "INE044A01036",
    "DRREDDY":     "INE089A01023",
    "CIPLA":       "INE059A01026",
    "APOLLOHOSP":  "INE437A01024",
    "BHARTIARTL":  "INE397D01024",
    "ULTRACEMCO":  "INE481G01011",
    "GRASIM":      "INE047A01021",
    "LT":          "INE018A01030",
    "TITAN":       "INE280A01028",
    "ASIANPAINT":  "INE021A01026",
    "INDUSINDBK":  "INE095A01012",
    "DIVISLAB":    "INE361B01024",
    "TRENT":       "INE849A01020",
    "BEL":         "INE263A01024",
}

# Reverse lookup: ISIN → symbol
ISIN_TO_SYMBOL = {isin: sym for sym, isin in NIFTY50_STOCKS.items()}


# ═══════════════════════════════════════════
# CACHE
# ═══════════════════════════════════════════

_cache = {
    "data": None,
    "timestamp": 0,
}
CACHE_TTL = 60  # seconds


def get_nifty50_heatmap_data(access_token: str) -> dict:
    """
    Fetch Nifty 50 market quotes from Upstox Full Market Quotes API.
    Returns { stocks: [ { symbol, price, change, changePercent } ] }
    Cached for 60 seconds.
    """
    now = time.time()

    # Return cached data if fresh
    if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
        logger.debug("📊 [HEATMAP] Returning cached data")
        return _cache["data"]

    # Build instrument keys: NSE_EQ|ISIN
    instrument_keys = [f"NSE_EQ|{isin}" for isin in NIFTY50_STOCKS.values()]

    url = "https://api.upstox.com/v2/market-quote/quotes"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    params = {"instrument_key": ",".join(instrument_keys)}

    stocks = []

    try:
        logger.info(f"📊 [HEATMAP] Fetching quotes for {len(instrument_keys)} Nifty 50 stocks")
        response = requests.get(url, headers=headers, params=params, timeout=15)

        if response.status_code == 200:
            data = response.json()
            quotes = data.get("data", {})

            for key, quote in quotes.items():
                # Key format from Upstox: "NSE_EQ:SYMBOL" or "NSE_EQ|ISIN"
                # Extract ISIN from the original key or use symbol from response
                symbol = quote.get("symbol", "")
                last_price = quote.get("last_price", 0)
                net_change = quote.get("net_change", 0)
                ohlc = quote.get("ohlc", {})
                prev_close = ohlc.get("close", 0)

                # Calculate % change
                if prev_close and prev_close > 0:
                    change_pct = (net_change / prev_close) * 100
                else:
                    change_pct = 0

                stocks.append({
                    "symbol": symbol,
                    "price": round(last_price, 2),
                    "change": round(net_change, 2),
                    "changePercent": round(change_pct, 2),
                    "open": ohlc.get("open", 0),
                    "high": ohlc.get("high", 0),
                    "low": ohlc.get("low", 0),
                    "close": prev_close,
                    "volume": quote.get("volume", 0),
                })

            logger.info(f"✅ [HEATMAP] Got {len(stocks)} stock quotes")
        elif response.status_code == 401:
            logger.error("❌ [HEATMAP] Unauthorized - access token may be expired")
            return {"stocks": [], "error": "Unauthorized"}
        elif response.status_code == 429:
            logger.warning("⚠️ [HEATMAP] Rate limited by Upstox API")
            # Return cached data if available
            if _cache["data"]:
                return _cache["data"]
            return {"stocks": [], "error": "Rate limited"}
        else:
            logger.error(f"❌ [HEATMAP] Error {response.status_code}: {response.text[:200]}")
            return {"stocks": [], "error": f"API error {response.status_code}"}

    except requests.Timeout:
        logger.error("⏱️ [HEATMAP] Request timed out")
        if _cache["data"]:
            return _cache["data"]
        return {"stocks": [], "error": "Timeout"}
    except Exception as e:
        logger.error(f"❌ [HEATMAP] Exception: {e}")
        if _cache["data"]:
            return _cache["data"]
        return {"stocks": [], "error": str(e)}

    result = {"stocks": stocks}
    _cache["data"] = result
    _cache["timestamp"] = now
    return result
