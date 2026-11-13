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
    """Return the accepted keys from a raw secret string."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        return [raw]
    if isinstance(parsed, dict):
        keys = [parsed.get("current"), parsed.get("previous")]
        return [k for k in keys if isinstance(k, str) and k]
    if isinstance(parsed, str) and parsed:
        return [parsed]
    return []


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


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    secret_arn = os.environ.get("ORDER_RESULT_SECRET_ARN")
    if not secret_arn:
        logger.error("result consumer rejected all messages: "
                     "ORDER_RESULT_SECRET_ARN is not configured")
        return {"statusCode": 200,
                "body": json.dumps({"processed": 0,
                                    "rejected": len(event.get("Records", [])),
                                    "reason": "secret_reference_missing"})}
    try:
        secrets = _secrets(secret_arn)
    except SecretUnavailable:
        logger.error("result consumer rejected all messages: "
                     "secret unavailable")
        return {"statusCode": 200,
                "body": json.dumps({"processed": 0,
                                    "rejected": len(event.get("Records", [])),
                                    "reason": "secret_unavailable"})}

    import result_handler

    return result_handler.process_records(event.get("Records", []), secrets)
