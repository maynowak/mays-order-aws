from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from errors import validation_error
from order_types import ORDER_STATUSES

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ORDER_ID_RE = re.compile(r"^ord_[A-Za-z0-9]+$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
STATUS_SET = set(ORDER_STATUSES)


def is_plain_object(value: Any) -> bool:
    return isinstance(value, dict)


def reject_unknown_keys(value: Dict[str, Any], allowed: List[str], path: str) -> None:
    unknown = [key for key in value if key not in allowed]
    if unknown:
        raise validation_error(
            f"Unknown field '{unknown[0]}' at {path}",
            {"path": f"{path}.{unknown[0]}"},
        )


def assert_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value.strip()) == 0:
        raise validation_error(f"Field '{path}' must be a non-empty string", {"path": path})
    return value


def assert_integer(value: Any, path: str, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise validation_error(f"Field '{path}' must be an integer >= {minimum}", {"path": path})
    return value


def validate_create_order(body: Any) -> Dict[str, Any]:
    if not is_plain_object(body):
        raise validation_error("Request body must be a JSON object")

    reject_unknown_keys(body, ["customer", "items", "currency"], "body")

    customer = body.get("customer")
    if not is_plain_object(customer):
        raise validation_error("Field 'customer' must be an object", {"path": "customer"})
    reject_unknown_keys(customer, ["name", "email"], "customer")
    name = assert_string(customer.get("name"), "customer.name")
    email = assert_string(customer.get("email"), "customer.email")
    if not EMAIL_RE.match(email):
        raise validation_error(
            "Field 'customer.email' must be a valid email address",
            {"path": "customer.email"},
        )

    items = body.get("items")
    if not isinstance(items, list) or len(items) < 1:
        raise validation_error("Field 'items' must be a non-empty array", {"path": "items"})
    validated_items: List[Dict[str, Any]] = []
    for index, raw in enumerate(items):
        if not is_plain_object(raw):
            raise validation_error(
                f"Field 'items[{index}]' must be an object",
                {"path": f"items[{index}]"},
            )
        reject_unknown_keys(raw, ["sku", "quantity", "unitPrice"], f"items[{index}]")
        sku = assert_string(raw.get("sku"), f"items[{index}].sku")
        quantity = assert_integer(raw.get("quantity"), f"items[{index}].quantity", 1)
        unit_price = assert_integer(raw.get("unitPrice"), f"items[{index}].unitPrice", 1)
        validated_items.append({"sku": sku, "quantity": quantity, "unitPrice": unit_price})

    currency = assert_string(body.get("currency"), "currency")
    if not CURRENCY_RE.match(currency):
        raise validation_error(
            "Field 'currency' must be a 3-letter ISO-4217 code (uppercase)",
            {"path": "currency"},
        )

    return {"customer": {"name": name, "email": email}, "items": validated_items, "currency": currency}


def validate_order_id(order_id: Any) -> str:
    if not isinstance(order_id, str) or not ORDER_ID_RE.match(order_id):
        raise validation_error(
            "Path parameter 'orderId' must match format 'ord_<alphanumeric>'",
            {"path": "orderId"},
        )
    return order_id


def validate_status(status: Any) -> str:
    if not isinstance(status, str) or status not in STATUS_SET:
        raise validation_error(
            f"Field 'status' must be one of: {', '.join(ORDER_STATUSES)}",
            {"path": "status"},
        )
    return status


def validate_status_update_body(body: Any) -> str:
    if not is_plain_object(body):
        raise validation_error("Request body must be a JSON object")
    reject_unknown_keys(body, ["status"], "body")
    return validate_status(body.get("status"))


def validate_list_params(query: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(query, dict):
        query = {}
    raw_limit = query.get("limit")
    raw_next_token = query.get("nextToken")

    limit = 20
    if raw_limit is not None:
        if not isinstance(raw_limit, str) or not re.match(r"^\d+$", raw_limit):
            raise validation_error("Query parameter 'limit' must be an integer", {"path": "limit"})
        limit = int(raw_limit, 10)
        if limit < 1 or limit > 100:
            raise validation_error(
                "Query parameter 'limit' must be between 1 and 100",
                {"path": "limit"},
            )

    next_token: Optional[str] = None
    if raw_next_token is not None:
        next_token = assert_string(raw_next_token, "nextToken")

    result: Dict[str, Any] = {"limit": limit}
    if next_token is not None:
        result["nextToken"] = next_token
    return result
