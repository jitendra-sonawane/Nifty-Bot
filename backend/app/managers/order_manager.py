import logging
from typing import List, Dict, Optional
import upstox_client
from upstox_client.rest import ApiException
from app.core.config import Config
from app.managers.paper_trading import PaperTradingManager

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, access_token):
        self.access_token = access_token
        configuration = upstox_client.Configuration()
        configuration.access_token = access_token
        self.api_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
        self.paper_manager = PaperTradingManager()
        self.trading_mode = "PAPER"  # Default to PAPER

    def set_access_token(self, token):
        self.access_token = token
        configuration = upstox_client.Configuration()
        configuration.access_token = token
        self.api_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
        logger.info("OrderManager: Access Token updated.")

    def set_mode(self, mode):
        self.trading_mode = mode
        logger.info(f"Trading Mode set to: {self.trading_mode}")

    def place_order(self, instrument_key, quantity, transaction_type,
                    order_type='MARKET', product='D', price=0.0, validity='DAY'):
        if self.trading_mode == "PAPER":
            return self.paper_manager.place_order(instrument_key, quantity, transaction_type, price, product)

        body = upstox_client.PlaceOrderRequest(
            quantity=quantity,
            product=product,
            validity=validity,
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
            logger.info(f"Order placed: {api_response.data.order_id} | {transaction_type} {quantity} {instrument_key} | validity={validity}")
            return api_response.data.order_id
        except ApiException as e:
            logger.error(f"Order placement failed: {e}")
            return None

    def place_multi_order(self, legs: List[Dict], slice_orders: bool = True) -> Dict:
        """
        Place multiple orders atomically via Upstox multi-order API.

        Args:
            legs: List of dicts with keys: instrument_key, quantity, transaction_type,
                  order_type, product, price, validity, correlation_id
            slice_orders: Auto-split orders exceeding exchange freeze limits

        Returns:
            {"order_ids": [...], "errors": [...], "partial": bool}
        """
        if len(legs) > 25:
            logger.error("Multi-order: max 25 orders per request")
            return {"order_ids": [], "errors": ["Max 25 orders exceeded"], "partial": False}

        if self.trading_mode == "PAPER":
            order_ids = []
            for leg in legs:
                oid = self.paper_manager.place_order(
                    instrument_key=leg["instrument_key"],
                    quantity=leg["quantity"],
                    transaction_type=leg["transaction_type"],
                    price=leg.get("price", 0.0),
                    product=leg.get("product", "D"),
                )
                order_ids.append(oid)
            logger.info(f"Paper multi-order: {len(order_ids)} legs placed")
            return {"order_ids": order_ids, "errors": [], "partial": False}

        # LIVE mode: use Upstox multi-order API
        multi_requests = []
        for i, leg in enumerate(legs):
            req = upstox_client.MultiOrderRequest(
                quantity=leg["quantity"],
                product=leg.get("product", "D"),
                validity=leg.get("validity", "DAY"),
                price=leg.get("price", 0.0),
                tag=leg.get("tag", "algo_spread"),
                slice=slice_orders,
                instrument_token=leg["instrument_key"],
                order_type=leg.get("order_type", "MARKET"),
                transaction_type=leg["transaction_type"],
                disclosed_quantity=leg.get("disclosed_quantity", 0),
                trigger_price=leg.get("trigger_price", 0.0),
                is_amo=False,
                correlation_id=leg.get("correlation_id", f"leg_{i}"),
            )
            multi_requests.append(req)

        try:
            response = self.api_instance.place_multi_order(body=multi_requests, api_version='2.0')

            order_ids = []
            errors = []

            if response.data:
                for item in response.data:
                    order_ids.append(item.order_id if hasattr(item, 'order_id') else str(item))

            if response.errors:
                for err in response.errors:
                    err_msg = str(err)
                    errors.append(err_msg)
                    logger.error(f"Multi-order leg error: {err_msg}")

            partial = len(errors) > 0 and len(order_ids) > 0
            logger.info(f"Multi-order result: {len(order_ids)} filled, {len(errors)} errors, partial={partial}")
            return {"order_ids": order_ids, "errors": errors, "partial": partial}

        except ApiException as e:
            logger.error(f"Multi-order API failed: {e}")
            return {"order_ids": [], "errors": [str(e)], "partial": False}

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order by order_id."""
        if self.trading_mode == "PAPER":
            logger.info(f"Paper cancel: {order_id}")
            return True

        try:
            self.api_instance.cancel_order(order_id, api_version='2.0')
            logger.info(f"Order cancelled: {order_id}")
            return True
        except ApiException as e:
            logger.error(f"Cancel failed for {order_id}: {e}")
            return False

    def modify_order(self):
        pass
