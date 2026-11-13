"""Internal result handoff contract (Mays-Orders side).

Receives the RIS ``ORDER_RESULT`` / ``ORDER_FAILED`` envelope from the internal
result queue. This is a *subset* of the frozen RIS transport V1; the two
repositories are separate deployables, so the schema is pinned here and covered
by the same fixtures.

Trust boundary
--------------
A sender name inside the JSON is **not** proof. The consumer requires an SQS
message attribute carrying an HMAC-SHA256 over ``messageId`` + body, computed
with ``ORDER_RESULT_SERVICE_SECRET``. A forged or modified message fails the
signature check and is dropped before any order is touched. Queue/IAM
restriction (only the RIS result producer may send) remains an infrastructure
requirement, documented in the gate report.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, Dict, Iterable, Optional

SCHEMA_VERSION = "1"
ACCEPTED_SCHEMA_VERSIONS = frozenset({"1", "1.0"})

ORDER_RESULT = "ORDER_RESULT"
ORDER_FAILED = "ORDER_FAILED"
SUPPORTED_TYPES = frozenset({ORDER_RESULT, ORDER_FAILED})

SYSTEM_ORDERS = "mays-orders"
SYSTEM_RIS = "ris"

ORDER_ID_RE = re.compile(r"^ord_[A-Za-z0-9]+$")

MAX_PAYLOAD_BYTES = 16 * 1024

FORBIDDEN_KEY_PARTS = (
    "secret", "apikey", "api_key", "password", "passwd", "credential",
    "authorization", "bearer", "token", "jwt", "privatekey", "private_key",
)
FORBIDDEN_VALUE_PREFIXES = ("ris_", "Bearer ", "bearer ")

TOP_LEVEL_KEYS = frozenset({
    "schemaVersion", "messageId", "messageType", "orderId", "correlationId",
    "idempotencyKey", "sender", "recipient", "identity", "payload", "payloadRef",
    "createdAt", "execution", "parentOrderId", "parentWorkId",
})
REQUIRED_KEYS = frozenset({
    "schemaVersion", "messageId", "messageType", "orderId", "correlationId",
    "idempotencyKey", "sender", "recipient", "execution", "payload",
    "createdAt",
})


class ResultEnvelopeError(ValueError):
    """Rejected result envelope with a stable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ResultRejected(Exception):
    """Permanent rejection of an otherwise well-formed result (no retry)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ResultEnvelopeError(code, message)


def _reject_unknown(mapping: Dict[str, Any], allowed: Iterable[str],
                    path: str) -> None:
    unknown = [k for k in mapping if k not in allowed]
    if unknown:
        raise ResultEnvelopeError(
            "unknown_field", f"unknown field '{unknown[0]}' at {path}")


def _scan(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                raise ResultEnvelopeError(
                    "secret_in_result",
                    f"forbidden credential-shaped field at {path}.{key}")
            _scan(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if value.startswith(FORBIDDEN_VALUE_PREFIXES):
            raise ResultEnvelopeError(
                "secret_in_result", f"credential-shaped value at {path}")


def canonical_body(message_id: str, body: str) -> bytes:
    return f"{message_id}\n{body}".encode("utf-8")


def sign(secret: str, message_id: str, body: str) -> str:
    return hmac.new(secret.encode("utf-8"),
                    canonical_body(message_id, body),
                    hashlib.sha256).hexdigest()


def verify_signature(secret: str, message_id: str, body: str,
                     signature: Optional[str]) -> bool:
    """Constant-time check of the internal service signature."""
    if not secret or not signature:
        return False
    expected = sign(secret, message_id, body)
    return hmac.compare_digest(expected, str(signature))


def validate_result_envelope(raw: Any) -> Dict[str, Any]:
    """Validate one result envelope (already signature-verified)."""
    _require(isinstance(raw, dict), "invalid_envelope",
             "result envelope must be an object")
    _reject_unknown(raw, TOP_LEVEL_KEYS, "envelope")

    missing = [key for key in REQUIRED_KEYS if key not in raw]
    if missing:
        raise ResultEnvelopeError(
            "missing_field", f"missing required field '{missing[0]}'")

    _require(raw["schemaVersion"] in ACCEPTED_SCHEMA_VERSIONS,
             "unsupported_schema_version",
             f"schemaVersion {raw['schemaVersion']!r} is not supported")
    _require(raw["messageType"] in SUPPORTED_TYPES, "unknown_message_type",
             f"messageType {raw['messageType']!r} is not a result type")

    _require(isinstance(raw["orderId"], str)
             and bool(ORDER_ID_RE.match(raw["orderId"])),
             "invalid_order_id", "'orderId' must match 'ord_<alphanumeric>'")
    for field in ("messageId", "correlationId", "idempotencyKey", "createdAt"):
        _require(isinstance(raw[field], str) and raw[field].strip() != "",
                 "invalid_field", f"'{field}' must be a non-empty string")

    sender = raw["sender"]
    _require(isinstance(sender, dict) and sender.get("system") == SYSTEM_RIS,
             "wrong_sender_system", "result must originate from ris")
    recipient = raw["recipient"]
    _require(isinstance(recipient, dict)
             and recipient.get("system") == SYSTEM_ORDERS,
             "wrong_recipient_system", "result must be addressed to mays-orders")

    execution = raw["execution"]
    _require(isinstance(execution, dict), "missing_execution",
             "'execution' must be an object")
    _reject_unknown(execution, {"workId", "attempt", "executionId"}, "execution")
    _require(isinstance(execution.get("workId"), str)
             and execution["workId"].strip() != "",
             "missing_work_id", "'execution.workId' is required")
    attempt = execution.get("attempt")
    _require(isinstance(attempt, int) and not isinstance(attempt, bool)
             and attempt >= 1, "invalid_attempt",
             "'execution.attempt' must be an integer >= 1")

    payload = raw["payload"]
    _require(isinstance(payload, dict), "invalid_payload",
             "'payload' must be an object")
    encoded = json.dumps(payload, default=str).encode("utf-8")
    _require(len(encoded) <= MAX_PAYLOAD_BYTES, "payload_too_large",
             f"'payload' exceeds {MAX_PAYLOAD_BYTES} bytes")
    _scan(payload, "payload")

    return {key: raw[key] for key in TOP_LEVEL_KEYS if key in raw}


__all__ = [
    "SCHEMA_VERSION",
    "ACCEPTED_SCHEMA_VERSIONS",
    "ORDER_RESULT",
    "ORDER_FAILED",
    "SUPPORTED_TYPES",
    "ResultEnvelopeError",
    "sign",
    "verify_signature",
    "validate_result_envelope",
]
