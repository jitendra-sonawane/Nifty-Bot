import urllib.parse
import requests
from app.core.config import Config
from app.core.logger_config import logger

class Authenticator:
    def __init__(self):
        self.api_key = Config.API_KEY
        self.api_secret = Config.API_SECRET
        self.redirect_uri = Config.REDIRECT_URI
        self.base_url = "https://api.upstox.com/v2"
        
        # Validate configuration
        if not self.api_key:
            logger.warning("⚠️ UPSTOX_API_KEY not set in environment")
        if not self.api_secret:
            logger.warning("⚠️ UPSTOX_API_SECRET not set in environment")
        if not self.redirect_uri:
            logger.warning("⚠️ UPSTOX_REDIRECT_URI not set in environment")

    def get_login_url(self):
        """Generates the login URL for the user to authenticate."""
        if not self.api_key or not self.redirect_uri:
            logger.error("❌ Cannot generate login URL: API_KEY or REDIRECT_URI not configured")
            raise ValueError("API_KEY and REDIRECT_URI must be configured in .env")
        
        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "state": "random_state_string" 
        }
        login_url = f"{self.base_url}/login/authorization/dialog?{urllib.parse.urlencode(params)}"
        logger.debug(f"🔗 Login URL generated: {login_url[:80]}...")
        return login_url

    def generate_access_token(self, auth_code):
        """Exchanges the auth code for an access token."""
        if not self.api_key or not self.api_secret or not self.redirect_uri:
            logger.error("❌ Cannot generate token: credentials not configured")
            raise ValueError("API credentials must be configured in .env")
        
        logger.info(f"🔄 Exchanging auth code for access token...")
        url = f"{self.base_url}/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "code": auth_code,
            "client_id": self.api_key,
            "client_secret": self.api_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            if response.status_code == 200:
                token = response.json().get("access_token")
                logger.info(f"✅ Access token received from Upstox")
                return token
            else:
                error_msg = f"Upstox API error: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout exchanging auth code for token")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error: {e}")
            raise



if __name__ == "__main__":
    auth = Authenticator()
    print(f"Login URL: {auth.get_login_url()}")
    # In a real scenario, you'd start a local server to catch the redirect code
    # or ask the user to paste it.
