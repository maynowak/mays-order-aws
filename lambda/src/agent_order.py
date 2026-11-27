"""Agent Order Body V1 — validator for the nested order component.

This is the Mays-Orders side of the contract defined in RIS
(``agents/orders/agent_order.py``, MO-RIS-AGENT-ORDER-BODY-01 A01).

Duplication is deliberate and bounded: the two repositories are separate
deployables and must not import each other's code. The schema version and the
rejection codes are therefore pinned here and covered by the same fixtures on
both sides. Changing one side without the other is a contract break.

Scope: validation only. No persistence, no dispatch, no authorization.
``metadata`` references are informational — they never grant access.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, Optional

AGENT_ORDER_SCHEMA_VERSION = "1.0"
ACCEPTED_AGENT_ORDER_VERSIONS = frozenset({"1.0", "1"})

ORDER_TYPE_AGENT = "agent.execution"
SUPPORTED_AGENT_ORDER_TYPES = frozenset({ORDER_TYPE_AGENT})

AGENT_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
CAPABILITY_RE = re.compile(r"^[a-z0-9]+\.[a-z0-9_.\-]{1,64}$")
ORDER_TYPE_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$")
MAX_ORDER_TYPE_LENGTH = 64

BODY_KEYS = frozenset({
    "schemaVersion", "target", "input", "metadata", "processing",
    "resultContract",
})
TARGET_KEYS = frozenset({"agentId", "capability", "agentVersion"})
INPUT_KEYS = frozenset({"schemaVersion", "data"})
METADATA_KEYS = frozenset({
    "source", "partnerApplicationRef", "apiProfileRef", "requestId",
    "idempotencyKey",
})
PROCESSING_KEYS = frozenset({
    "trigger", "parentOrderId", "parentWorkId", "executionProfile",
})
RESULT_CONTRACT_KEYS = frozenset({
    "schemaVersion", "format", "expectedCapability", "delivery",
})

SUPPORTED_RESULT_FORMATS = frozenset({"json"})
SUPPORTED_DELIVERIES = frozenset({"order-result"})

DEFAULT_SOURCE = "ris-agent-ecosystem"
DEFAULT_TRIGGER = "ORDER_CREATED"
DEFAULT_EXECUTION_PROFILE = "default"

MAX_AGENT_ORDER_BYTES = 16 * 1024

FORBIDDEN_KEY_PARTS = (
    "secret", "apikey", "api_key", "password", "passwd", "credential",
    "authorization", "bearer", "token", "jwt", "privatekey", "private_key",
)
FORBIDDEN_VALUE_PREFIXES = ("ris_", "Bearer ", "bearer ")


class AgentOrderValidationError(ValueError):
    """Invalid agent order with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AgentOrderValidationError(code, message)


def _reject_unknown(mapping: Dict[str, Any], allowed: Iterable[str],
                    path: str) -> None:
    unknown = [k for k in mapping if k not in allowed]
    if unknown:
        raise AgentOrderValidationError(
            "unknown_field", f"unknown field '{unknown[0]}' at {path}")


def _assert_str(value: Any, path: str) -> str:
    _require(isinstance(value, str) and value.strip() != "", "invalid_field",
             f"'{path}' must be a non-empty string")
    return value


def _scan(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                raise AgentOrderValidationError(
                    "secret_in_agent_order",
                    f"forbidden credential-shaped field at {path}.{key}")
            _scan(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if value.startswith(FORBIDDEN_VALUE_PREFIXES):
            raise AgentOrderValidationError(
                "secret_in_agent_order",
                f"credential-shaped value at {path}")


def validate_order_type(value: Any) -> str:
    _require(isinstance(value, str) and value != "", "invalid_field",
             "Field 'orderType' must be a non-empty string")
    _require(len(value) <= MAX_ORDER_TYPE_LENGTH, "invalid_field",
             f"Field 'orderType' must be at most {MAX_ORDER_TYPE_LENGTH} characters")
    _require(bool(ORDER_TYPE_RE.match(value)), "invalid_field",
             "Field 'orderType' must match '<segment>[.<segment>...]'")
    return value


def validate_agent_order(body: Any, *,
                         expected_capability: Optional[str] = None) -> Dict[str, Any]:
    """Validate and normalise one agentOrder document."""
    _require(isinstance(body, dict), "invalid_agent_order",
             "Field 'agentOrder' must be an object")
    _reject_unknown(body, BODY_KEYS, "agentOrder")

    version = body.get("schemaVersion")
    _require(version in ACCEPTED_AGENT_ORDER_VERSIONS,
             "unsupported_agent_order_version",
             f"agentOrder.schemaVersion {version!r} is not supported "
             f"(expected {AGENT_ORDER_SCHEMA_VERSION})")

    target = body.get("target")
    _require(isinstance(target, dict), "invalid_target",
             "Field 'agentOrder.target' must be an object")
    _reject_unknown(target, TARGET_KEYS, "agentOrder.target")
    agent_id = _assert_str(target.get("agentId"), "agentOrder.target.agentId")
    _require(bool(AGENT_ID_RE.match(agent_id)), "invalid_target",
             "Field 'agentOrder.target.agentId' has unsupported characters")
    capability = _assert_str(target.get("capability"),
                             "agentOrder.target.capability")
    _require(bool(CAPABILITY_RE.match(capability)), "invalid_capability",
             "Field 'agentOrder.target.capability' must look like 'domain.action'")
    agent_version = target.get("agentVersion")
    if agent_version is not None:
        _assert_str(agent_version, "agentOrder.target.agentVersion")

    if expected_capability is not None:
        _require(capability == expected_capability, "capability_mismatch",
                 f"agentOrder capability is {capability!r}, "
                 f"expected {expected_capability!r}")

    raw_input = body.get("input")
    _require(isinstance(raw_input, dict), "invalid_input",
             "Field 'agentOrder.input' must be an object")
    _reject_unknown(raw_input, INPUT_KEYS, "agentOrder.input")
    input_version = raw_input.get("schemaVersion", "1.0")
    _require(input_version in ACCEPTED_AGENT_ORDER_VERSIONS,
             "unsupported_input_version",
             f"agentOrder.input.schemaVersion {input_version!r} is not supported")
    data = raw_input.get("data")
    _require(isinstance(data, dict), "invalid_input",
             "Field 'agentOrder.input.data' must be an object")

    metadata = body.get("metadata") or {}
    _require(isinstance(metadata, dict), "invalid_metadata",
             "Field 'agentOrder.metadata' must be an object")
    _reject_unknown(metadata, METADATA_KEYS, "agentOrder.metadata")
    for key, value in metadata.items():
        if value is not None:
            _assert_str(value, f"agentOrder.metadata.{key}")

    processing = body.get("processing") or {}
    _require(isinstance(processing, dict), "invalid_processing",
             "Field 'agentOrder.processing' must be an object")
    _reject_unknown(processing, PROCESSING_KEYS, "agentOrder.processing")

    result_contract = body.get("resultContract") or {
        "schemaVersion": "1.0",
        "format": "json",
        "expectedCapability": capability,
        "delivery": "order-result",
    }
    _require(isinstance(result_contract, dict), "invalid_result_contract",
             "Field 'agentOrder.resultContract' must be an object")
    _reject_unknown(result_contract, RESULT_CONTRACT_KEYS,
                    "agentOrder.resultContract")
    fmt = result_contract.get("format", "json")
    _require(fmt in SUPPORTED_RESULT_FORMATS, "unsupported_result_format",
             f"agentOrder.resultContract.format {fmt!r} is not supported")
    delivery = result_contract.get("delivery", "order-result")
    _require(delivery in SUPPORTED_DELIVERIES, "unsupported_delivery",
             f"agentOrder.resultContract.delivery {delivery!r} is not supported")
    expected = result_contract.get("expectedCapability", capability)
    _require(expected == capability, "result_contract_mismatch",
             "agentOrder.resultContract.expectedCapability must equal "
             "target.capability")

    _scan(data, "agentOrder.input.data")
    _scan(metadata, "agentOrder.metadata")

    try:
        encoded = json.dumps(body, default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AgentOrderValidationError(
            "invalid_agent_order", "agentOrder must be JSON-serializable") from exc
    _require(len(encoded) <= MAX_AGENT_ORDER_BYTES, "agent_order_too_large",
             f"agentOrder exceeds {MAX_AGENT_ORDER_BYTES} bytes")

    return {
        "schemaVersion": AGENT_ORDER_SCHEMA_VERSION,
        "target": {
            "agentId": agent_id,
            "capability": capability,
            "agentVersion": agent_version,
        },
        "input": {"schemaVersion": "1.0", "data": data},
        "metadata": {
            "source": metadata.get("source", DEFAULT_SOURCE),
            "partnerApplicationRef": metadata.get("partnerApplicationRef"),
            "apiProfileRef": metadata.get("apiProfileRef"),
            "requestId": metadata.get("requestId"),
            "idempotencyKey": metadata.get("idempotencyKey"),
        },
        "processing": {
            "trigger": processing.get("trigger", DEFAULT_TRIGGER),
            "parentOrderId": processing.get("parentOrderId"),
            "parentWorkId": processing.get("parentWorkId"),
            "executionProfile": processing.get(
                "executionProfile", DEFAULT_EXECUTION_PROFILE),
        },
        "resultContract": {
            "schemaVersion": "1.0",
            "format": fmt,
            "expectedCapability": expected,
            "delivery": delivery,
        },
    }


def fingerprint(agent_order: Dict[str, Any]) -> str:
    """Immutability marker for the accepted execution parameters.

    Same semantics as RIS: schema version + target + input only, so a retry
    with a new requestId is not a different execution.
    """
    canonical = json.dumps(
        {
            "schemaVersion": agent_order["schemaVersion"],
            "target": agent_order["target"],
            "input": agent_order["input"],
        },
        sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "AGENT_ORDER_SCHEMA_VERSION",
    "ACCEPTED_AGENT_ORDER_VERSIONS",
    "ORDER_TYPE_AGENT",
    "SUPPORTED_AGENT_ORDER_TYPES",
    "AgentOrderValidationError",
    "validate_order_type",
    "validate_agent_order",
    "fingerprint",
]
