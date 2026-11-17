"""L02 — dedicated result-consumer Lambda entrypoint.

Separate function from the HTTP handler: same A06 boundary, but the HMAC key is
fetched from Secrets Manager instead of an environment variable.

Secret shape (rotation-friendly)::

    {"current": "<hex>", "previous": "<hex>"}

A bare string is accepted as a single key. The value is never logged, never
returned and never stored in Terraform state.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_cached_secrets: Optional[List[str]] = None


class SecretUnavailable(RuntimeError):
    """The HMAC secret could not be resolved (fail-closed)."""


def parse_secret(raw: str) -> List[str]:
    """Return the accepted keys from a raw secret string.

    Blank/whitespace-only values are rejected: an empty key would make every
    signature fail and must never be treated as a usable secret.
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        return [raw]
    if isinstance(parsed, dict):
        keys = [parsed.get("current"), parsed.get("previous")]
    elif isinstance(parsed, str):
        keys = [parsed]
    else:
        keys = []
    return [key.strip() for key in keys
            if isinstance(key, str) and key.strip()]


def _fetch_secret(secret_arn: str) -> List[str]:
    import boto3

    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    raw = response.get("SecretString") or ""
    keys = parse_secret(raw)
    if not keys:
        raise SecretUnavailable("result secret is empty or malformed")
    return keys


def _secrets(secret_arn: str) -> List[str]:
    global _cached_secrets
    if _cached_secrets is None:
        _cached_secrets = _fetch_secret(secret_arn)
    return _cached_secrets


def reset_cache() -> None:
    """Test hook: forget the cached secret."""
    global _cached_secrets
    _cached_secrets = None


def _batch_failures(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Report every record for retry (used when no verification key exists).

    An ``itemIdentifier`` is mandatory; a record without the SQS message id is
    an invocation failure, never a silent acknowledgement.
    """
    failures: List[Dict[str, str]] = []
    for record in records:
        message_id = record.get("messageId")
        if not message_id:
            raise RuntimeError("SQS record without messageId")
        failures.append({"itemIdentifier": message_id})
    return failures


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    records = event.get("Records", [])
    secret_arn = os.environ.get("ORDER_RESULT_SECRET_ARN")
    if not secret_arn:
        logger.error("result consumer cannot verify messages: "
                     "ORDER_RESULT_SECRET_ARN is not configured")
        return {"batchItemFailures": _batch_failures(records)}
    try:
        secrets = _secrets(secret_arn)
    except SecretUnavailable:
        logger.error("result consumer cannot verify messages: "
                     "secret unavailable")
        return {"batchItemFailures": _batch_failures(records)}
    except Exception as exc:  # noqa: BLE001 - never ack on an unreadable secret
        logger.error("result consumer cannot verify messages: "
                     "secret read failed (%s)", type(exc).__name__)
        return {"batchItemFailures": _batch_failures(records)}
    if not secrets:
        logger.error("result consumer cannot verify messages: "
                     "secret has no usable key")
        return {"batchItemFailures": _batch_failures(records)}

    import result_handler

    # The response carries statusCode/body for observability and
    # batchItemFailures for the ESM; Lambda ignores the extra keys.
    return result_handler.process_records(records, secrets)
