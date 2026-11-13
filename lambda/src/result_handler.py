"""Internal SQS consumer for RIS agent results.

Entry point: ``result_handler.handler`` (separate Lambda, no HTTP route).

Trust boundary (A06.2):

1. The message must carry an SQS attribute ``serviceSignature`` containing
   HMAC-SHA256(secret, ``messageId`` + "\\n" + body). A sender name inside the
   JSON is informational only and never sufficient.
2. ``ORDER_RESULT_SERVICE_SECRET`` must be configured; otherwise every message
   is dropped (fail-closed).
3. The stored order is authoritative: order id, correlation reference and work
   id must match before anything is written.

Permanent rejections (invalid envelope, wrong order, duplicate conflict,
cancelled order) are consumed, not retried. Infrastructure errors propagate so
SQS redelivers.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from errors import OrderError
from order_service import create_order_service
from result_envelope import (
    ResultEnvelopeError,
    ResultRejected,
    validate_result_envelope,
    verify_signature,
)

logger = logging.getLogger(__name__)


def _signature(record: Dict[str, Any]) -> str:
    attributes = record.get("messageAttributes") or {}
    entry = attributes.get("serviceSignature") or {}
    return entry.get("stringValue") or ""


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    table_name = os.environ.get("ORDERS_TABLE")
    if not table_name:
        raise RuntimeError("ORDERS_TABLE is not configured")

    secret = os.environ.get("ORDER_RESULT_SERVICE_SECRET")
    if not secret:
        # Fail closed: no verification material means nothing is trusted.
        logger.error("result consumer rejected all messages: "
                     "ORDER_RESULT_SERVICE_SECRET is not configured")
        return {"statusCode": 200,
                "body": json.dumps({"processed": 0,
                                    "rejected": len(event.get("Records", [])),
                                    "reason": "service_secret_missing"})}

    service = create_order_service(table_name=table_name)
    processed = 0
    rejected = 0

    for record in event.get("Records", []):
        message_id = record.get("messageId", "")
        body = record.get("body") or ""
        if not verify_signature(secret, message_id, body, _signature(record)):
            logger.warning("result rejected: invalid service signature")
            rejected += 1
            continue
        try:
            envelope = validate_result_envelope(json.loads(body))
            service.apply_result(envelope)
            processed += 1
        except (ValueError, OrderError, ResultEnvelopeError,
                ResultRejected) as exc:
            # Permanent: consume the message instead of looping forever.
            logger.warning("result rejected: %s",
                           getattr(exc, "code", type(exc).__name__))
            rejected += 1
        except Exception:
            # Infrastructure failure: let SQS redeliver.
            logger.exception("result processing failed; raising for retry")
            raise

    return {"statusCode": 200,
            "body": json.dumps({"processed": processed,
                                "rejected": rejected})}
