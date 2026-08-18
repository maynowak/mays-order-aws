from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from errors import conflicted_update, invalid_transition, order_not_found, validation_error
from state_machine import can_transition
from order_types import GSI1_PK, ORDER_ID_PREFIX, ORDER_SK, TABLE_INDEX_NAME
from validation import validate_create_order

INTERNAL_FIELDS = {"pk", "sk", "gsi1pk", "gsi1sk", "version"}

_dynamodb_resource = None


def _get_dynamodb_resource():
    """Boto3-Ressource lazy erzeugen und über Warm-Starts hinweg wiederverwenden.

    Der Import von boto3 erfolgt bewusst erst hier (Lambda-Runtime stellt boto3
    bereit; die Unit-Tests injizieren einen Fake-Client und brauchen boto3 nicht).
    """
    global _dynamodb_resource
    if _dynamodb_resource is None:
        import boto3

        _dynamodb_resource = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")
        )
    return _dynamodb_resource


def generate_order_id() -> str:
    return f"{ORDER_ID_PREFIX}{secrets.token_hex(12)}"


def now_iso() -> str:
    now = datetime.now(timezone.utc)
    return f"{now:%Y-%m-%dT%H:%M:%S}.{now.microsecond // 1000:03d}Z"


def to_public_order(item: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in item.items() if key not in INTERNAL_FIELDS}


def to_list_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "orderId": item["orderId"],
        "status": item["status"],
        "customer": {"name": item["customer"]["name"]},
        "totalAmount": item["totalAmount"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }


def encode_next_token(last_evaluated_key: Optional[Dict[str, Any]]) -> Optional[str]:
    if not last_evaluated_key:
        return None
    raw = json.dumps(last_evaluated_key, separators=(",", ":"))
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def decode_next_token(next_token: str) -> Dict[str, Any]:
    try:
        raw = base64.b64decode(next_token.encode("utf-8")).decode("utf-8")
        parsed: Any = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("not an object")
        return parsed
    except Exception as exc:
        raise validation_error(
            "Query parameter 'nextToken' is not a valid pagination token",
            {"path": "nextToken"},
        ) from exc


def is_client_error(err: Any, code: str) -> bool:
    return hasattr(err, "response") and err.response.get("Error", {}).get("Code") == code


def is_conditional_check_failed(err: Any) -> bool:
    return is_client_error(err, "ConditionalCheckFailedException")


def is_validation_exception(err: Any) -> bool:
    return is_client_error(err, "ValidationException")


class OrderService:
    def __init__(self, table_name: str, client: Any = None) -> None:
        self._table_name = table_name
        self._table = client if client is not None else _get_dynamodb_resource().Table(table_name)

    def create_order(self, raw_body: Any) -> Dict[str, Any]:
        input_data = validate_create_order(raw_body)
        now = now_iso()
        order_id = generate_order_id()

        items = [
            {**item, "lineTotal": item["quantity"] * item["unitPrice"]}
            for item in input_data["items"]
        ]
        total_amount = sum(item["lineTotal"] for item in items)

        item: Dict[str, Any] = {
            "pk": f"{ORDER_ID_PREFIX}{order_id}",
            "sk": ORDER_SK,
            "orderId": order_id,
            "status": "PENDING",
            "customer": input_data["customer"],
            "items": items,
            "currency": input_data["currency"],
            "totalAmount": total_amount,
            "createdAt": now,
            "updatedAt": now,
            "version": 1,
            "gsi1pk": GSI1_PK,
            "gsi1sk": now,
        }

        self._table.put_item(Item=item)

        return to_public_order(item)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        result = self._table.get_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK}
        )
        item = result.get("Item")
        if item is None:
            raise order_not_found(order_id)
        return to_public_order(item)

    def list_orders(self, limit: int, next_token: Optional[str] = None) -> Dict[str, Any]:
        query_kwargs: Dict[str, Any] = {
            "IndexName": TABLE_INDEX_NAME,
            "KeyConditionExpression": "gsi1pk = :pk",
            "ExpressionAttributeValues": {":pk": GSI1_PK},
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if next_token:
            query_kwargs["ExclusiveStartKey"] = decode_next_token(next_token)

        try:
            result = self._table.query(**query_kwargs)
        except Exception as err:
            if is_validation_exception(err):
                raise validation_error(
                    "Invalid pagination token or query",
                    {"path": "nextToken"},
                ) from err
            raise

        orders = [to_list_item(item) for item in result.get("Items", [])]

        response: Dict[str, Any] = {"orders": orders, "count": len(orders)}
        encoded = encode_next_token(result.get("LastEvaluatedKey"))
        if encoded:
            response["nextToken"] = encoded
        return response

    def update_order_status(self, order_id: str, status: str) -> Dict[str, Any]:
        current = self.get_order(order_id)

        if not can_transition(current["status"], status):
            raise invalid_transition(current["status"], status)

        try:
            result = self._table.update_item(
                Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
                UpdateExpression="SET #status = :newStatus, updatedAt = :now, #version = #version + :one",
                ConditionExpression="attribute_exists(pk) AND #status = :currentStatus",
                ExpressionAttributeNames={"#status": "status", "#version": "version"},
                ExpressionAttributeValues={
                    ":newStatus": status,
                    ":currentStatus": current["status"],
                    ":now": now_iso(),
                    ":one": 1,
                },
                ReturnValues="ALL_NEW",
            )
            return to_public_order(result["Attributes"])
        except Exception as err:
            if is_conditional_check_failed(err):
                raise conflicted_update() from err
            raise


def create_order_service(table_name: str, client: Any = None) -> OrderService:
    return OrderService(table_name, client)
