"""
Sandbox Order Executor.
Uses Upstox Sandbox API to place, modify, and cancel orders
with a sandbox token — no real money involved.

The sandbox environment emulates the actual API integration experience,
allowing full testing of order flow before going live.
"""

import logging
import requests
from typing import Optional, Dict, List
from app.core.config import Config
from app.core.models import OrderStatus

logger = logging.getLogger(__name__)


# Upstox API endpoints
BASE_URL = "https://api-hft.upstox.com/v2"
ORDER_PLACE_URL = f"{BASE_URL}/order/place"
ORDER_MODIFY_URL = f"{BASE_URL}/order/modify"
ORDER_CANCEL_URL = f"{BASE_URL}/order/cancel"
MULTI_ORDER_URL = f"{BASE_URL}/order/multi"
ORDER_HISTORY_URL = "https://api.upstox.com/v2/order/retrieve-all"


class SandboxExecutor:
    """
    Executes orders via Upstox Sandbox API.
    
    The sandbox token (valid 30 days) is obtained from:
    https://account.upstox.com/developer/apps#sandbox
    
    Supported operations:
    - Place single order
    - Modify existing order  
    - Cancel order
    - Retrieve order history
    
    Usage:
        executor = SandboxExecutor()
        result = executor.place_order(
            instrument_token="NSE_FO|NIFTY25FEB23500CE",
            quantity=25,
            transaction_type="BUY",
            order_type="MARKET",
        )
    """
    
    def __init__(self):
        self._order_history: List[dict] = []
    
    @property
    def _token(self) -> str:
        """Get the sandbox token from config."""
        # Prefer sandbox token, fall back to regular access token
        token = Config.SANDBOX_TOKEN or Config.ACCESS_TOKEN
        if not token:
            logger.error("No sandbox or access token configured")
        return token or ""
    
    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def place_order(
        self,
        instrument_token: str,
        quantity: int,
        transaction_type: str,
        order_type: str = "MARKET",
        product: str = "D",
        price: float = 0.0,
        trigger_price: float = 0.0,
        validity: str = "DAY",
        tag: str = "nifty_algo",
        is_amo: bool = False,
        disclosed_quantity: int = 0,
    ) -> Optional[Dict]:
        """
        Place a single order on Upstox Sandbox.
        
        Args:
            instrument_token: e.g., "NSE_FO|NIFTY25FEB23500CE"
            quantity: Number of units (must be multiple of lot size)
            transaction_type: "BUY" or "SELL"
            order_type: "MARKET", "LIMIT", "SL", "SL-M"
            product: "D" (delivery/intraday), "I" (intraday), "CO", "OCO"
            price: Limit price (required for LIMIT/SL orders)
            trigger_price: Trigger price (required for SL/SL-M orders)
            validity: "DAY" or "IOC"
            tag: Custom tag for tracking
            is_amo: After Market Order
            disclosed_quantity: Disclosed quantity
        
        Returns:
            {"order_id": "...", "status": "placed"} or None on failure
        """
        payload = {
            "quantity": quantity,
            "product": product,
            "validity": validity,
            "price": price,
            "tag": tag,
            "instrument_token": instrument_token,
            "order_type": order_type,
            "transaction_type": transaction_type,
            "disclosed_quantity": disclosed_quantity,
            "trigger_price": trigger_price,
            "is_amo": is_amo,
        }
        
        try:
            response = requests.post(
                ORDER_PLACE_URL,
                headers=self._headers,
                json=payload,
                timeout=10,
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get("status") == "success":
                order_id = result.get("data", {}).get("order_id", "")
                
                order_record = {
                    "order_id": order_id,
                    "instrument_token": instrument_token,
                    "quantity": quantity,
                    "transaction_type": transaction_type,
                    "order_type": order_type,
                    "price": price,
                    "status": OrderStatus.PLACED.value,
                }
                self._order_history.append(order_record)
                
                logger.info(f"✅ Sandbox order placed: {order_id} | "
                           f"{transaction_type} {quantity} {instrument_token}")
                return order_record
            else:
                error_msg = result.get("errors", [{}])
                logger.error(f"❌ Sandbox order failed: {error_msg}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("Sandbox order timeout")
            return None
        except Exception as e:
            logger.error(f"Sandbox order error: {e}")
            return None
    
    def place_multi_order(self, orders: List[Dict], slice_orders: bool = True) -> Dict:
        """
        Place multiple orders atomically via Upstox multi-order endpoint.

        Args:
            orders: List of order dicts with keys matching place_order params
            slice_orders: Auto-split orders exceeding exchange freeze limits

        Returns:
            {"order_ids": [...], "errors": [...], "partial": bool}
        """
        if len(orders) > 25:
            logger.error("Max 25 orders per multi-order request")
            return {"order_ids": [], "errors": ["Max 25 orders exceeded"], "partial": False}

        payload = []
        for i, order in enumerate(orders):
            payload.append({
                "quantity": order.get("quantity"),
                "product": order.get("product", "D"),
                "validity": order.get("validity", "DAY"),
                "price": order.get("price", 0.0),
                "tag": order.get("tag", "sandbox_spread"),
                "slice": slice_orders,
                "instrument_token": order.get("instrument_token", order.get("instrument_key")),
                "order_type": order.get("order_type", "MARKET"),
                "transaction_type": order.get("transaction_type"),
                "disclosed_quantity": order.get("disclosed_quantity", 0),
                "trigger_price": order.get("trigger_price", 0.0),
                "is_amo": order.get("is_amo", False),
                "correlation_id": order.get("correlation_id", f"leg_{i}_{order.get('tag', 'nifty')}"),
            })

        try:
            response = requests.post(
                MULTI_ORDER_URL,
                headers=self._headers,
                json=payload,
                timeout=10,
            )
            result = response.json()

            order_ids = []
            errors = []

            if response.status_code == 200 and result.get("status") == "success":
                for item in result.get("data", []):
                    oid = item.get("order_id", "")
                    order_ids.append(oid)
                    self._order_history.append({
                        "order_id": oid,
                        "correlation_id": item.get("correlation_id", ""),
                        "status": OrderStatus.PLACED.value,
                    })
            elif response.status_code == 207:
                # Partial success
                for item in result.get("data", []):
                    order_ids.append(item.get("order_id", ""))
                for err in result.get("errors", []):
                    errors.append(str(err))
            else:
                errors.append(str(result.get("errors", result.get("message", "Unknown error"))))

            partial = len(errors) > 0 and len(order_ids) > 0
            logger.info(f"Sandbox multi-order: {len(order_ids)} placed, {len(errors)} errors")
            return {"order_ids": order_ids, "errors": errors, "partial": partial}

        except requests.exceptions.Timeout:
            logger.error("Sandbox multi-order timeout")
            return {"order_ids": [], "errors": ["Timeout"], "partial": False}
        except Exception as e:
            logger.error(f"Sandbox multi-order error: {e}")
            return {"order_ids": [], "errors": [str(e)], "partial": False}
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        trigger_price: Optional[float] = None,
        validity: str = "DAY",
    ) -> Optional[Dict]:
        """
        Modify an existing sandbox order.
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity (optional)
            price: New price (optional)
            order_type: New order type (optional)
            trigger_price: New trigger price (optional)
            validity: Order validity
        
        Returns:
            Modified order details or None
        """
        payload = {"order_id": order_id, "validity": validity}
        
        if quantity is not None:
            payload["quantity"] = quantity
        if price is not None:
            payload["price"] = price
        if order_type is not None:
            payload["order_type"] = order_type
        if trigger_price is not None:
            payload["trigger_price"] = trigger_price
        
        try:
            response = requests.put(
                ORDER_MODIFY_URL,
                headers=self._headers,
                json=payload,
                timeout=10,
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get("status") == "success":
                logger.info(f"✅ Sandbox order modified: {order_id}")
                return {"order_id": order_id, "status": "modified"}
            else:
                logger.error(f"❌ Order modify failed: {result.get('errors', [])}")
                return None
                
        except Exception as e:
            logger.error(f"Order modify error: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a sandbox order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancelled successfully
        """
        try:
            response = requests.delete(
                ORDER_CANCEL_URL,
                headers=self._headers,
                params={"order_id": order_id},
                timeout=10,
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get("status") == "success":
                logger.info(f"✅ Sandbox order cancelled: {order_id}")
                # Update local history
                for record in self._order_history:
                    if record["order_id"] == order_id:
                        record["status"] = OrderStatus.CANCELLED.value
                return True
            else:
                logger.error(f"❌ Order cancel failed: {result.get('errors', [])}")
                return False
                
        except Exception as e:
            logger.error(f"Order cancel error: {e}")
            return False
    
    def get_order_history(self) -> List[Dict]:
        """Get all orders placed in this session."""
        return self._order_history
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """Get status of a specific order."""
        for record in self._order_history:
            if record["order_id"] == order_id:
                return record["status"]
        return None
    
    def fetch_live_orders(self) -> Optional[List[Dict]]:
        """
        Fetch order history from Upstox API.
        Useful for verifying sandbox order execution.
        """
        try:
            response = requests.get(
                ORDER_HISTORY_URL,
                headers=self._headers,
                timeout=10,
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                logger.warning(f"Failed to fetch orders: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return None
