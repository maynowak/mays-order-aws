"""Privacy-specific helpers for the opt-in B2 live tests.

This module is deliberately network-free at import time. It only describes
gates, builds Lambda-invoke events, and parses responses. A real boto3 client
is constructed by the live test module after every gate passed.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional

from tests.e2e_harness import BLOCKED, PASS, redact

PRIVACY_LIVE_ENV = "MO_PRIVACY_LIVE"
PRIVACY_INVOKER_ENV = "PRIVACY_E2E_INVOKER_APPROVED"
PRIVACY_CLEANUP_ENV = "MO_E2E_LIVE_CLEANUP"

PRIVACY_ACTIONS = (
    "privacy/inspect",
    "privacy/export",
    "privacy/erase",
)


@dataclass(frozen=True)
class PrivacyLiveConfig:
    account_id: str
    region: str
    table_name: str
    function_name: str
    project: str
    consumer_id: str
    code_sha256: str
    api_base_url: str
    queue_url: str
    dlq_url: str
    subject_a: str
    subject_b: str
    access_token_a: str = field(repr=False)
    access_token_b: str = field(repr=False)
    internal_token: str = field(repr=False)
    status: str = PASS
    blocked_reason: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.status == PASS


def resolve_privacy_config(env: Optional[Mapping[str, str]] = None) -> PrivacyLiveConfig:
    """Resolve B2 gates without contacting AWS.

    All missing prerequisites are returned as an explicit BLOCKED reason. The
    values themselves (tokens/secret) never appear in repr or reason strings.
    """
    values = dict(env or {})
    missing = []

    if values.get(PRIVACY_LIVE_ENV) != "1":
        missing.append(f"{PRIVACY_LIVE_ENV}=1")
    if values.get(PRIVACY_CLEANUP_ENV) != "1":
        missing.append(f"{PRIVACY_CLEANUP_ENV}=1")
    if values.get(PRIVACY_INVOKER_ENV) != "1":
        missing.append(f"{PRIVACY_INVOKER_ENV}=1")

    required = {
        "AWS_PROFILE": "AWS_PROFILE",
        "AWS_REGION": "AWS_REGION",
        "PRIVACY_E2E_ACCOUNT_ID": "account_id",
        "PRIVACY_E2E_TABLE": "table_name",
        "PRIVACY_E2E_HANDLER": "function_name",
        "PRIVACY_E2E_CODE_SHA256": "code_sha256",
        "PRIVACY_E2E_PROJECT": "project",
        "PRIVACY_E2E_CONSUMER_ID": "consumer_id",
        "API_BASE_URL": "api_base_url",
        "PRIVACY_E2E_QUEUE_URL": "queue_url",
        "PRIVACY_E2E_DLQ_URL": "dlq_url",
        "PRIVACY_E2E_SUBJECT_A": "subject_a",
        "PRIVACY_E2E_SUBJECT_B": "subject_b",
        "PRIVACY_E2E_ACCESS_TOKEN_A": "access_token_a",
        "PRIVACY_E2E_ACCESS_TOKEN_B": "access_token_b",
        "PRIVACY_E2E_INTERNAL_TOKEN": "internal_token",
    }
    for env_name in required:
        if not str(values.get(env_name) or "").strip():
            missing.append(env_name)

    reason = None
    if missing:
        reason = "BLOCKED: missing privacy live prerequisite(s): " + ", ".join(missing)

    return PrivacyLiveConfig(
        account_id=str(values.get("PRIVACY_E2E_ACCOUNT_ID") or ""),
        region=str(values.get("AWS_REGION") or ""),
        table_name=str(values.get("PRIVACY_E2E_TABLE") or ""),
        function_name=str(values.get("PRIVACY_E2E_HANDLER") or ""),
        project=str(values.get("PRIVACY_E2E_PROJECT") or ""),
        consumer_id=str(values.get("PRIVACY_E2E_CONSUMER_ID") or ""),
        code_sha256=str(values.get("PRIVACY_E2E_CODE_SHA256") or ""),
        api_base_url=str(values.get("API_BASE_URL") or ""),
        queue_url=str(values.get("PRIVACY_E2E_QUEUE_URL") or ""),
        dlq_url=str(values.get("PRIVACY_E2E_DLQ_URL") or ""),
        subject_a=str(values.get("PRIVACY_E2E_SUBJECT_A") or ""),
        subject_b=str(values.get("PRIVACY_E2E_SUBJECT_B") or ""),
        access_token_a=str(values.get("PRIVACY_E2E_ACCESS_TOKEN_A") or ""),
        access_token_b=str(values.get("PRIVACY_E2E_ACCESS_TOKEN_B") or ""),
        internal_token=str(values.get("PRIVACY_E2E_INTERNAL_TOKEN") or ""),
        status=BLOCKED if reason else PASS,
        blocked_reason=reason,
    )


def make_privacy_context(
    config: PrivacyLiveConfig,
    permission: str,
    *,
    project: Optional[str] = None,
    consumer_id: Optional[str] = None,
    token: Optional[str] = None,
    authorized: bool = True,
    include_consumer: bool = True,
) -> Dict[str, Any]:
    """Build the internal authContext for one privacy action.

    The token is included only in the in-memory invoke payload. Callers must
    not render this mapping or put it into reports.
    """
    context: Dict[str, Any] = {
        "project": project if project is not None else config.project,
        "authorized": authorized,
        "internal_token": token if token is not None else config.internal_token,
        permission: True,
    }
    if include_consumer:
        context["consumerId"] = (
            consumer_id if consumer_id is not None else config.consumer_id
        )
    return context


def run_marker(run_id: str, suffix: str) -> str:
    return f"E2E-{run_id}-{suffix}"


def decode_jwt_subject(token: str) -> str:
    """Read the `sub` claim from an access token without logging the token."""
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    claims = json.loads(base64.urlsafe_b64decode(part))
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise ValueError("access token has no subject")
    return subject


@dataclass(frozen=True)
class PrivacyResponse:
    status_code: int
    body: Dict[str, Any]

    def __repr__(self) -> str:
        return f"PrivacyResponse(status_code={self.status_code}, body_keys={sorted(self.body)})"


class PrivacyInvokeClient:
    """Thin Lambda-invoke adapter; no HTTP and no AWS client construction."""

    def __init__(self, invoke: Callable[[Mapping[str, Any]], Mapping[str, Any]]):
        self._invoke = invoke

    def invoke(
        self,
        action: str,
        subject_id: str,
        context: Mapping[str, Any],
        *,
        options: Optional[Mapping[str, Any]] = None,
    ) -> PrivacyResponse:
        if action not in PRIVACY_ACTIONS:
            raise ValueError(f"unsupported privacy action: {action}")
        payload: Dict[str, Any] = {"subjectId": subject_id}
        if options is not None:
            payload["options"] = dict(options)
        event = {
            "internalAction": action,
            "payload": payload,
            "authContext": dict(context),
        }
        raw = self._invoke(event)
        status = raw.get("statusCode")
        body = raw.get("body")
        if not isinstance(status, int):
            raise ValueError("privacy invoke response has no integer statusCode")
        if isinstance(body, str):
            body = json.loads(body)
        if not isinstance(body, dict):
            raise ValueError("privacy invoke response body is not an object")
        return PrivacyResponse(status_code=status, body=body)

    def redacted_diagnostic(self, response: PrivacyResponse) -> Dict[str, Any]:
        return redact(response.body)


def boto3_invoker(function_name: str, lambda_client: Any = None):
    """Return an invoker callable for the live test, constructing boto3 lazily."""
    if lambda_client is None:
        import boto3

        lambda_client = boto3.client("lambda")

    def invoke(event: Mapping[str, Any]) -> Mapping[str, Any]:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event).encode("utf-8"),
        )
        raw = response["Payload"].read()
        return json.loads(raw)

    return invoke
