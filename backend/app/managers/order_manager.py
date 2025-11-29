import upstox_client
from upstox_client.rest import ApiException
from app.core.config import Config
from app.managers.paper_trading import PaperTradingManager

class OrderManager:
    def __init__(self, access_token):
        self.access_token = access_token
        configuration = upstox_client.Configuration()
        configuration.access_token = access_token
        self.api_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
        self.paper_manager = PaperTradingManager()
        self.trading_mode = "PAPER" # Default to PAPER

    def set_access_token(self, token):
        self.access_token = token
        configuration = upstox_client.Configuration()
        configuration.access_token = token
        self.api_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
        print("OrderManager: Access Token updated.")

    def set_mode(self, mode):
        self.trading_mode = mode
        print(f"Trading Mode set to: {self.trading_mode}")

    def place_order(self, instrument_key, quantity, transaction_type, order_type='MARKET', product='D', price=0.0):
        if self.trading_mode == "PAPER":
            # For paper trading, we use the provided price. If 0 (MARKET), we might need to handle it.
            # Ideally main.py passes the current market price even for MARKET orders for simulation.
            return self.paper_manager.place_order(instrument_key, quantity, transaction_type, price, product)

        body = upstox_client.PlaceOrderRequest(
            quantity=quantity,
            product=product,
            validity="DAY",
            price=price,
            tag="algo_bot",
            instrument_token=instrument_key,
            order_type=order_type,
            transaction_type=transaction_type,
            disclosed_quantity=0,
            trigger_price=0.0,
            is_amo=False
        )

        try:
            api_response = self.api_instance.place_order(body, api_version='2.0')
            print(f"Order placed successfully. Order ID: {api_response.data.order_id}")
            return api_response.data.order_id
        except ApiException as e:
            print(f"Exception when calling OrderApi->place_order: {e}")
            return None

    def modify_order(self):
        # Implement if needed
        pass

    def cancel_order(self):
        # Implement if needed
        pass
