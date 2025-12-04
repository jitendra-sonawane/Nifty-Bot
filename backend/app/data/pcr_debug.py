"""
Debug script to test PCR calculation and API data flow
"""
import sys
sys.path.insert(0, '/Users/jitendrasonawane/Workpace/backend')

from app.data.data_fetcher import DataFetcher
from app.core.config import Config
from app.core.logger_config import logger

def test_pcr_calculation():
    """Test PCR calculation with detailed logging"""
    
    logger.info("=" * 80)
    logger.info("🧪 PCR CALCULATION DEBUG TEST")
    logger.info("=" * 80)
    
    # Initialize
    api_key = Config.API_KEY
    access_token = Config.ACCESS_TOKEN
    
    logger.info(f"API Key present: {bool(api_key)}")
    logger.info(f"Access Token present: {bool(access_token)}")
    
    if not access_token:
        logger.error("❌ No access token found. Cannot proceed.")
        return
    
    # Create fetcher
    fetcher = DataFetcher(api_key, access_token)
    
    # Load instruments
    logger.info("\n📥 Loading instruments...")
    fetcher.load_instruments()
    
    if fetcher.instruments_df is None:
        logger.error("❌ Failed to load instruments")
        return
    
    logger.info(f"✅ Instruments loaded: {len(fetcher.instruments_df)} total")
    
    # Get current price
    logger.info("\n💰 Fetching current Nifty price...")
    nifty_key = "NSE_INDEX|Nifty 50"
    current_price = fetcher.get_current_price(nifty_key)
    
    if not current_price:
        logger.error("❌ Failed to fetch current price")
        return
    
    logger.info(f"✅ Current Nifty price: {current_price}")
    
    # Calculate PCR
    logger.info("\n📊 Calculating PCR...")
    pcr = fetcher.get_nifty_pcr(current_price)
    
    if pcr is None:
        logger.error("❌ PCR calculation returned None")
    else:
        logger.info(f"✅ PCR: {pcr}")
    
    logger.info("\n" + "=" * 80)

if __name__ == "__main__":
    test_pcr_calculation()
