from __future__ import annotations

import base64
import json
import os
import sys
import uuid
from typing import Any, Dict, Optional

from errors import (
    OrderError,
    error_body,
    internal_error,
    json_default,
    unauthorized_error,
    validation_error,
)
from identity import extract_verified_subject, resolve_order_identity_from_event
from order_service import DELIVERY_FAILED, DELIVERY_SENT, create_order_service
from validation import validate_list_params, validate_order_id, validate_status_update_body

JSON_HEADERS = {"Content-Type": "application/json"}

SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL")

# Eigentümer-Identität (MO-RC4-P02): ausschließlich aus dem verifizierten
# JWT-Autorisator-Kontext, nie aus dem Request-Body. Cognito-`sub` ist eine
# stabile, unveränderliche Benutzer-ID.
_MAX_SUBJECT_ID_LENGTH = 256


def extract_subject_id(event: Dict[str, Any]) -> str:
    """Verifizierte Benutzer-ID (JWT `sub`) oder 401.

    Duenne Kompatibilitaets-Huelle um `identity.extract_verified_subject`;
    die eigentliche Aufloesung (inkl. Consumer-Namensraum) liegt zentral in
    `identity.py` (MO-RC4-P02A).
    """
    return extract_verified_subject(event)

# Bestehenden Helper wiederverwenden (zentral in errors.json_default).
_json_default = json_default

def _get_sqs_client():
    import boto3
    return boto3.client('sqs', region_name=os.environ.get('AWS_REGION', 'eu-central-1'))

def _send_to_sqs(order_id: str) -> bool:
    if not SQS_QUEUE_URL:
        print("SQS_QUEUE_URL not configured")
        return False
    try:
        sqs = _get_sqs_client()
        message = {
            "orderId": order_id,
            "status": "CONFIRMED",
            "metadata": {"reason": "order_created"}
        }
        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageAttributes={
                "orderId": {
                    "StringValue": order_id,
                    "DataType": "String"
                }
            }
        )
        print(f"Sent order {order_id} to SQS")
        return True
    except Exception as e:
        print(f"Failed to send to SQS: {e}")
        return False

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
        "body": json.dumps(payload, separators=(",", ":"), default=_json_default),
    }


def fail(error: Any) -> Dict[str, Any]:
    if isinstance(error, OrderError):
        return {
            "statusCode": error.http_status,
            "headers": JSON_HEADERS,
            "body": json.dumps(error_body(error), separators=(",", ":"), default=_json_default),
        }
    print(f"Unexpected error: {error}", file=sys.stderr)
    err = internal_error()
    return {
        "statusCode": err.http_status,
        "headers": JSON_HEADERS,
        "body": json.dumps(error_body(err), separators=(",", ":"), default=_json_default),
    }


def route_key(event: Dict[str, Any]) -> str:
    route = event.get("routeKey")
    if route:
        return route
    method = event.get("httpMethod", "GET")
    path = event.get("rawPath", "/")
    return f"{method} {path}"


# Interne Privacy-Aktionen — ausschließlich per direktem Lambda-Invoke
# (IAM lambda:InvokeFunction) erreichbar. Es wird KEINE öffentliche
# API-Gateway-Route hinzugefügt. Jede Aktion läuft durch
# OrderService._require_privacy_auth (fail-closed).
_INTERNAL_PRIVACY_ACTIONS = ("privacy/inspect", "privacy/export", "privacy/erase")

# MO-RC4-P02F: Recovery wird ausschliesslich per direktem Lambda-Invoke
# (EventBridge Scheduler oder Operator) ausgeloest. Es gibt KEINE HTTP-Route.
# Die Autorisierung ist IAM-basiert (lambda:InvokeFunction nur fuer die
# Scheduler-Rolle); ein Secret im Scheduler-Payload waere ein Leak im State.
INTERNAL_RECOVERY_ACTION = "recovery/scan"

# MO-RC4-P02I-B2: Processing-Recovery (abgelaufene Verarbeitungs-Claims).
# Ebenfalls nur per direktem Lambda-Invoke (Scheduler/Operator), keine Route.
INTERNAL_PROCESSING_RECOVERY_ACTION = "processing/scan"


def _send_processing_recovery(order_id: str, status: str = "CONFIRMED") -> None:
    """Stellt eine Order erneut zu; wirft bei Fehlern (Recovery zaehlt das als Fehler)."""
    if not SQS_QUEUE_URL:
        raise RuntimeError("SQS_QUEUE_URL not configured")
    message = {
        "orderId": order_id,
        "status": status,
        "metadata": {"reason": "processing_recovery"},
    }
    _get_sqs_client().send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(message),
        MessageAttributes={"orderId": {"StringValue": order_id, "DataType": "String"}},
    )


def _handle_processing_recovery(event: Dict[str, Any]) -> Dict[str, Any]:
    from recovery import run_processing_recovery

    options = event.get("options") or {}

    import boto3

    table_name = os.environ.get("ORDERS_TABLE")
    if not table_name:
        return fail(internal_error("Lambda is not configured (ORDERS_TABLE missing)"))
    table = boto3.resource(
        "dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")
    ).Table(table_name)

    report = run_processing_recovery(
        table,
        _send_processing_recovery,
        limit=options.get("limit", 20),
        safety_margin_seconds=options.get("safetyMarginSeconds", 60),
    )
    return ok(200, report)


def _mark_delivery(service: Any, order_id: str, state: str) -> None:
    """Best-effort-Zustellvermerk; darf die API-Antwort nicht veraendern."""
    try:
        service.mark_delivery_state(order_id, state)
    except Exception as exc:
        print(f"Delivery state update failed for {order_id}: {exc}")


def _handle_recovery(event: Dict[str, Any]) -> Dict[str, Any]:
    from recovery import run_recovery

    options = event.get("options") or {}

    def send(order_id: str) -> None:
        if not _send_to_sqs(order_id):
            raise RuntimeError(f"SQS delivery failed for {order_id}")

    import boto3

    table_name = os.environ.get("ORDERS_TABLE")
    if not table_name:
        return fail(internal_error("Lambda is not configured (ORDERS_TABLE missing)"))
    table = boto3.resource(
        "dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")
    ).Table(table_name)

    report = run_recovery(
        table,
        send,
        window_minutes=options.get("windowMinutes", 60),
        limit=options.get("limit", 50),
        min_age_seconds=options.get("minAgeSeconds", 60),
        lease_seconds=options.get("leaseSeconds", 300),
    )
    return ok(200, report)


def _handle_internal(service: Any, event: Dict[str, Any]) -> Dict[str, Any]:
    action = event.get("internalAction")
    if action == INTERNAL_RECOVERY_ACTION:
        try:
            return _handle_recovery(event)
        except Exception as err:
            return fail(err)
    if action == INTERNAL_PROCESSING_RECOVERY_ACTION:
        try:
            return _handle_processing_recovery(event)
        except Exception as err:
            return fail(err)
    if action not in _INTERNAL_PRIVACY_ACTIONS:
        return fail(validation_error(f"Unsupported internal action: {action}"))
    payload = event.get("payload") or {}
    auth_context = event.get("authContext")
    subject_id = payload.get("subjectId")
    options = payload.get("options")
    try:
        if action == "privacy/inspect":
            result = service.inspect_subject(subject_id, context=auth_context)
        elif action == "privacy/export":
            result = service.export_subject(subject_id, context=auth_context)
        else:
            result = service.erase_subject(subject_id, context=auth_context, options=options)
        return ok(200, result)
    except Exception as err:
        return fail(err)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    table_name = os.environ.get("ORDERS_TABLE")
    if not table_name:
        return fail(internal_error("Lambda is not configured (ORDERS_TABLE missing)"))

    service = create_order_service(table_name=table_name)

    # Interner Aufrufweg (direkter Invoke, keine HTTP-Route).
    if isinstance(event, dict) and isinstance(event.get("internalAction"), str):
        return _handle_internal(service, event)

    try:
        route = route_key(event)

        if route == "POST /orders":
            # Identitaet zuerst aufloesen (fail-closed), dann Body validieren.
            identity = resolve_order_identity_from_event(event)
            order = service.create_order(
                parse_body(event), subject_id=identity.owner_id, identity=identity
            )
            order_id = order.get("orderId")
            if order_id:
                if SQS_QUEUE_URL and _send_to_sqs(order_id):
                    _mark_delivery(service, order_id, DELIVERY_SENT)
                else:
                    # Zustellung fehlgeschlagen/unmoeglich: Recovery uebernimmt.
                    _mark_delivery(service, order_id, DELIVERY_FAILED)
            return ok(201, order)

        if route == "GET /orders":
            # MO-RC4-P02H-A: auch lesende Routen brauchen die verifizierte
            # Identitaet; Liste wird auf Owner+Consumer eingeschraenkt.
            identity = resolve_order_identity_from_event(event)
            params = validate_list_params(event.get("queryStringParameters"))
            result = service.list_orders(
                params["limit"], params.get("nextToken"), identity=identity
            )
            return ok(200, result)

        if route == "GET /orders/{orderId}":
            identity = resolve_order_identity_from_event(event)
            path_params = event.get("pathParameters") or {}
            order_id = validate_order_id(path_params.get("orderId"))
            order = service.get_order(order_id, identity=identity)
            return ok(200, order)

        if route == "PATCH /orders/{orderId}/status":
            identity = resolve_order_identity_from_event(event)
            path_params = event.get("pathParameters") or {}
            order_id = validate_order_id(path_params.get("orderId"))
            status = validate_status_update_body(parse_body(event))
            order = service.update_order_status(order_id, status, identity=identity)
            return ok(200, order)

        return fail(validation_error(f"Unsupported route: {route}"))
    except Exception as err:
        return fail(err)
