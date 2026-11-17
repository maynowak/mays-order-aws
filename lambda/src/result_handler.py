"""Internal SQS consumer for RIS agent results.

Entry point: ``result_consumer.handler`` (separate Lambda, no HTTP route).

Trust boundary (A06.2):

1. The message must carry an SQS attribute ``serviceSignature`` containing
   HMAC-SHA256(secret, ``messageId`` + "\\n" + body), where ``messageId`` is the
   **envelope** id inside the JSON body (the SQS record id is a UUID assigned
   at send time and is not part of the signed material).
2. ``ORDER_RESULT_SERVICE_SECRET`` must be configured; otherwise every message
   is reported as a batch failure (retry/DLQ), never acknowledged as processed.
3. The stored order is authoritative: order id, correlation reference and work
   id must match before anything is written.

Permanent rejections (invalid envelope, wrong order, duplicate conflict,
cancelled order) are consumed, not retried. Infrastructure errors are returned
as ``batchItemFailures`` so SQS retries exactly those records.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

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
    records = event.get("Records", [])
    secret = os.environ.get("ORDER_RESULT_SERVICE_SECRET")
    if not secret:
        # Fail closed, but never acknowledge as processed: report every record
        # as a batch failure so SQS retries and the DLQ can engage.
        logger.error("result consumer rejected all messages: "
                     "ORDER_RESULT_SERVICE_SECRET is not configured")
        return {"batchItemFailures": [
            {"itemIdentifier": record.get("messageId", "")}
            for record in records]}
    return process_records(records, [secret])


def process_records(records: List[Dict[str, Any]],
                    secrets: List[str],
                    service: Any = None) -> Dict[str, Any]:
    """Verify and apply a batch with one or more accepted HMAC keys.

    Multiple keys support rotation: the consumer accepts ``current`` and
    ``previous`` until the producer rollout is complete.

    Signature basis is the **envelope** ``messageId`` from the JSON body, not
    the SQS-assigned ``record["messageId"]``. SQS assigns a UUID at send time
    that the producer cannot know, so verifying against it rejects every
    correctly signed message. The HMAC still covers the message id, therefore
    a tampered id invalidates the signature.

    Infrastructure failures are reported as ``batchItemFailures`` (keyed by the
    SQS record id) so SQS retries exactly those records and the DLQ works.
    """
    table_name = os.environ.get("ORDERS_TABLE")
    if not table_name:
        raise RuntimeError("ORDERS_TABLE is not configured")
    service = service or create_order_service(table_name=table_name)

    processed = 0
    rejected = 0
    failures: List[Dict[str, str]] = []

    for record in records:
        sqs_message_id = record.get("messageId", "")
        body = record.get("body") or ""
        signature = _signature(record)

        try:
            raw = json.loads(body)
        except (TypeError, ValueError):
            logger.warning("result rejected: invalid_json")
            rejected += 1
            continue
        message_id = raw.get("messageId") if isinstance(raw, dict) else None
        if not isinstance(message_id, str) or not message_id:
            logger.warning("result rejected: missing_message_id")
            rejected += 1
            continue

        if not any(verify_signature(secret, message_id, body, signature)
                   for secret in secrets if secret):
            logger.warning("result rejected: invalid service signature")
            rejected += 1
            continue
        try:
            envelope = validate_result_envelope(raw)
            service.apply_result(envelope)
            processed += 1
        except (ValueError, OrderError, ResultEnvelopeError,
                ResultRejected) as exc:
            # Permanent: consume the message instead of looping forever.
            logger.warning("result rejected: %s",
                           getattr(exc, "code", type(exc).__name__))
            rejected += 1
        except Exception:
            # Infrastructure failure: retry only this record.
            logger.exception("result processing failed; returning batch failure")
            failures.append({"itemIdentifier": sqs_message_id})

    response: Dict[str, Any] = {
        "statusCode": 200,
        "body": json.dumps({"processed": processed, "rejected": rejected}),
    }
    if failures:
        response["batchItemFailures"] = failures
    return response
