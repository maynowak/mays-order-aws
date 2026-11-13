"""ORDER_DISPATCH construction for Mays-Orders (A05).

The envelope is built from the **stored, validated order**, never from the
original HTTP request. The work id is bound server-side before sending, so the
result that later arrives can be matched to exactly this execution.

Transport shape: the frozen RIS Generic Order Transport V1. The pre-bound
workId travels in ``execution.workId`` — a field the V1 validator already
accepts; the RIS mapping was extended to honour it (A05-1, documented, no schema
change, no version bump).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

DISPATCH_MESSAGE_TYPE = "ORDER_DISPATCH"
TRANSPORT_SCHEMA_VERSION = "1"
MAX_DISPATCH_PAYLOAD_BYTES = 16 * 1024


class DispatchRejected(Exception):
    """Permanent, non-retryable dispatch rejection."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def new_work_id() -> str:
    """Server-generated work id, bound to the order before dispatch."""
    return "work-" + uuid.uuid4().hex


def build_dispatch_envelope(order: Dict[str, Any], work_id: str, *,
                            now: Optional[datetime] = None,
                            message_id: Optional[str] = None) -> Dict[str, Any]:
    """Build ORDER_DISPATCH from a stored agent order.

    Raises DispatchRejected when the stored order cannot produce a valid
    dispatch (no identity reference, no correlation, oversized payload).
    """
    agent_order = order.get("agentOrder") or {}
    target = agent_order.get("target") or {}
    metadata = agent_order.get("metadata") or {}
    raw_input = agent_order.get("input") or {}
    payload = raw_input.get("data")

    if not isinstance(payload, dict):
        raise DispatchRejected("invalid_payload",
                               "Stored agent order has no object payload")

    encoded = json.dumps(payload, default=str).encode("utf-8")
    if len(encoded) > MAX_DISPATCH_PAYLOAD_BYTES:
        raise DispatchRejected("payload_too_large",
                               "Payload exceeds the dispatch limit")

    correlation_id = metadata.get("requestId")
    if not correlation_id:
        raise DispatchRejected("missing_correlation",
                               "Agent order has no correlation reference")

    # The receiver resolves this reference against its own trusted store; the
    # value itself is not proof (A05/D03, T03).
    context_ref = metadata.get("apiProfileRef")
    if not context_ref:
        raise DispatchRejected("missing_identity_reference",
                               "Agent order has no identity context reference")

    agent_id = target.get("agentId")
    capability = target.get("capability")
    if not agent_id or not capability:
        raise DispatchRejected("invalid_target",
                               "Agent order has no target or capability")

    stamp = (now or datetime.now(timezone.utc)).isoformat()
    return {
        "schemaVersion": TRANSPORT_SCHEMA_VERSION,
        "messageId": message_id or f"msg_{work_id}_dispatch",
        "messageType": DISPATCH_MESSAGE_TYPE,
        "orderId": order["orderId"],
        "correlationId": correlation_id,
        "idempotencyKey": (metadata.get("idempotencyKey")
                           or f"{order['orderId']}:dispatch"),
        "sender": {"system": "mays-orders", "reference": "orders-api"},
        "recipient": {
            "system": "ris",
            "agentId": agent_id,
            "capability": capability,
        },
        "identity": {"contextRef": context_ref},
        "payload": payload,
        "createdAt": stamp,
        # A05-1: pre-bound execution identity. Optional in V1; the RIS mapping
        # reuses it instead of generating a second work id.
        "execution": {"workId": work_id},
    }


__all__ = [
    "DISPATCH_MESSAGE_TYPE",
    "MAX_DISPATCH_PAYLOAD_BYTES",
    "DispatchRejected",
    "new_work_id",
    "build_dispatch_envelope",
]
