from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any, Dict, Optional

from errors import OrderError, error_body, internal_error, validation_error
from order_service import create_order_service
from validation import validate_list_params, validate_order_id, validate_status_update_body

JSON_HEADERS = {"Content-Type": "application/json"}


def parse_body(event: Dict[str, Any]) -> Any:
    body = event.get("body")
    if body is None:
        return None
    raw = body
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(body).decode("utf-8")
        except Exception as exc:
            raise validation_error("Request body must be valid JSON") from exc
    try:
        return json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise validation_error("Request body must be valid JSON") from exc


def ok(status_code: int, payload: Any) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": json.dumps(payload, separators=(",", ":")),
    }


def fail(error: Any) -> Dict[str, Any]:
    if isinstance(error, OrderError):
        return {
            "statusCode": error.http_status,
            "headers": JSON_HEADERS,
            "body": json.dumps(error_body(error), separators=(",", ":")),
        }
    print(f"Unexpected error: {error}", file=sys.stderr)
    err = internal_error()
    return {
        "statusCode": err.http_status,
        "headers": JSON_HEADERS,
        "body": json.dumps(error_body(err), separators=(",", ":")),
    }


def route_key(event: Dict[str, Any]) -> str:
    route = event.get("routeKey")
    if route:
        return route
    method = event.get("httpMethod", "GET")
    path = event.get("rawPath", "/")
    return f"{method} {path}"


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    table_name = os.environ.get("ORDERS_TABLE")
    if not table_name:
        return fail(internal_error("Lambda is not configured (ORDERS_TABLE missing)"))

    service = create_order_service(table_name=table_name)

    try:
        route = route_key(event)

        if route == "POST /orders":
            order = service.create_order(parse_body(event))
            return ok(201, order)

        if route == "GET /orders":
            params = validate_list_params(event.get("queryStringParameters"))
            result = service.list_orders(params["limit"], params.get("nextToken"))
            return ok(200, result)

        if route == "GET /orders/{orderId}":
            path_params = event.get("pathParameters") or {}
            order_id = validate_order_id(path_params.get("orderId"))
            order = service.get_order(order_id)
            return ok(200, order)

        if route == "PATCH /orders/{orderId}/status":
            path_params = event.get("pathParameters") or {}
            order_id = validate_order_id(path_params.get("orderId"))
            status = validate_status_update_body(parse_body(event))
            order = service.update_order_status(order_id, status)
            return ok(200, order)

        return fail(validation_error(f"Unsupported route: {route}"))
    except Exception as err:
        return fail(err)
