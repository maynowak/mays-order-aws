"""Local E2E test harness for RC4.

This module deliberately contains no AWS client construction and no network
access at import time. The live test module injects either a fake transport
(for local tests) or a real HTTP transport only after an explicit live opt-in.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
NOT_EXECUTED = "NOT EXECUTED"

LIVE_OPT_IN_ENV = "MO_E2E_LIVE"
REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = {
    "access_token",
    "refresh_token",
    "id_token",
    "password",
    "authorization",
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "secret",
    "token",
}


class AuthUnavailable(RuntimeError):
    """Raised when an authenticated operation has no pre-provisioned token."""


class CleanupOwnershipError(RuntimeError):
    """Raised when cleanup is attempted for data outside the current run."""


class CleanupUnavailable(RuntimeError):
    """Raised when no safe product cleanup operation exists."""


class CleanupError(RuntimeError):
    """Raised when cleanup of an owned test order fails."""


@dataclass(frozen=True)
class AuthContext:
    access_token: Optional[str] = field(repr=False)
    api_base_url: Optional[str]
    status: str
    blocked_reason: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.status == PASS


def resolve_auth(env: Optional[Mapping[str, str]] = None) -> AuthContext:
    """Resolve live E2E configuration without contacting Cognito.

    Live execution requires an explicit opt-in plus a pre-provisioned token.
    Password-based Cognito authentication is intentionally not performed here.
    """
    values = dict(os.environ if env is None else env)
    if values.get(LIVE_OPT_IN_ENV) != "1":
        return AuthContext(
            access_token=None,
            api_base_url=values.get("API_BASE_URL") or None,
            status=BLOCKED,
            blocked_reason=f"live E2E not enabled ({LIVE_OPT_IN_ENV} != 1)",
        )

    token = (values.get("ACCESS_TOKEN") or "").strip()
    api_base_url = (values.get("API_BASE_URL") or "").strip()
    if not api_base_url:
        return AuthContext(
            access_token=None,
            api_base_url=None,
            status=BLOCKED,
            blocked_reason="API_BASE_URL missing for live E2E",
        )
    if not token:
        return AuthContext(
            access_token=None,
            api_base_url=api_base_url,
            status=BLOCKED,
            blocked_reason="pre-provisioned ACCESS_TOKEN missing for live E2E",
        )
    return AuthContext(
        access_token=token,
        api_base_url=api_base_url,
        status=PASS,
        blocked_reason=None,
    )


def classify_outcome(
    *, executed: bool, passed: bool, blocked_reason: Optional[str] = None
) -> str:
    if blocked_reason:
        return BLOCKED
    if not executed:
        return NOT_EXECUTED
    return PASS if passed else FAIL


def redact(value: Any, key: str = "") -> Any:
    """Redact credentials recursively without touching business identifiers."""
    if key.lower() in _SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(entry) for entry in value]
    if isinstance(value, str):
        return re.sub(
            r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1" + REDACTED, value
        )
    return value


@dataclass
class Diagnostic:
    test_id: str
    run_id: str
    operation: str
    expected_status: Optional[int] = None
    actual_status: Optional[int] = None
    error_type: Optional[str] = None
    cleanup_status: str = NOT_EXECUTED
    blocked_reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return redact(
            {
                "test_id": self.test_id,
                "run_id": self.run_id,
                "operation": self.operation,
                "expected_status": self.expected_status,
                "actual_status": self.actual_status,
                "error_type": self.error_type,
                "cleanup_status": self.cleanup_status,
                "blocked_reason": self.blocked_reason,
            }
        )


@dataclass(frozen=True)
class SyntheticOrder:
    run_id: str
    sequence: int
    payload: Dict[str, Any]

    @property
    def marker(self) -> str:
        return f"E2E-{self.run_id}-{self.sequence}"


def build_synthetic_order(run_id: str, sequence: int = 1) -> SyntheticOrder:
    """Build deterministic, non-personal order data scoped to one run."""
    marker = f"E2E-{run_id}-{sequence}"
    return SyntheticOrder(
        run_id=run_id,
        sequence=sequence,
        payload={
            "customer": {
                "name": f"E2E Test {run_id} {sequence}",
                "email": f"e2e+{run_id}-{sequence}@example.invalid",
            },
            "items": [{"sku": marker, "quantity": 1, "unitPrice": 100}],
            "currency": "EUR",
        },
    )


@dataclass
class OwnedOrder:
    run_id: str
    owner_run_id: str
    order_id: str
    marker: str
    cleanup_status: str = NOT_EXECUTED


@dataclass
class CleanupResult:
    order_id: str
    status: str
    error_type: Optional[str] = None


class CleanupLedger:
    """Tracks cleanup only for records created by the current test run."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.results: List[CleanupResult] = []

    def owns(self, order: OwnedOrder) -> bool:
        return (
            bool(order.order_id)
            and order.run_id == self.run_id
            and order.owner_run_id == self.run_id
        )

    def cleanup(self, order: OwnedOrder, delete: Callable[[OwnedOrder], None]) -> CleanupResult:
        if not self.owns(order):
            order.cleanup_status = BLOCKED
            self.results.append(
                CleanupResult(order.order_id, BLOCKED, "CleanupOwnershipError")
            )
            raise CleanupOwnershipError(
                "refusing cleanup: order is not owned by the current test run"
            )
        try:
            delete(order)
        except Exception as exc:
            order.cleanup_status = FAIL
            self.results.append(
                CleanupResult(order.order_id, FAIL, type(exc).__name__)
            )
            raise CleanupError(
                f"cleanup failed for order {order.order_id}: {type(exc).__name__}"
            ) from exc
        order.cleanup_status = PASS
        result = CleanupResult(order.order_id, PASS)
        self.results.append(result)
        return result


@dataclass
class E2ERun:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    orders: List[OwnedOrder] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)
    cleanup: CleanupLedger = field(init=False)

    def __post_init__(self) -> None:
        self.cleanup = CleanupLedger(self.run_id)

    def synthetic_order(self, sequence: int = 1) -> SyntheticOrder:
        return build_synthetic_order(self.run_id, sequence)

    def register_created(self, order_id: str, marker: str) -> OwnedOrder:
        order = OwnedOrder(
            run_id=self.run_id,
            owner_run_id=self.run_id,
            order_id=order_id,
            marker=marker,
        )
        self.orders.append(order)
        return order

    def record_diagnostic(self, diagnostic: Diagnostic) -> Diagnostic:
        self.diagnostics.append(diagnostic)
        return diagnostic

    def cleanup_all(self, delete: Callable[[OwnedOrder], None]) -> List[CleanupResult]:
        errors = []
        for order in self.orders:
            try:
                self.cleanup.cleanup(order, delete)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise CleanupError(
                f"{len(errors)} cleanup operation(s) failed; see cleanup ledger"
            ) from errors[0]
        return self.cleanup.results

    def run_with_cleanup(
        self,
        action: Callable[[], Any],
        delete: Callable[[OwnedOrder], None],
    ) -> Any:
        """Run an action and always attempt cleanup, including on exceptions."""
        try:
            return action()
        finally:
            self.cleanup_all(delete)


@dataclass
class HttpResponse:
    status: int
    data: bytes = b""
    headers: Dict[str, str] = field(default_factory=dict)


class FakeTransport:
    """Deterministic HTTP transport for local validation."""

    def __init__(self, responses: Iterable[HttpResponse]):
        self.responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def request(self, method, url, headers=None, body=None, timeout=15):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "body": body,
            }
        )
        if not self.responses:
            raise AssertionError("FakeTransport has no queued response")
        return self.responses.pop(0)


class Urllib3Transport:
    """Real HTTP transport, only constructed by an explicitly enabled live run."""

    def __init__(self):
        import urllib3

        self.pool = urllib3.PoolManager()

    def request(self, method, url, headers=None, body=None, timeout=15):
        response = self.pool.request(
            method,
            url,
            body=body,
            headers=headers,
            timeout=timeout,
        )
        return HttpResponse(
            status=response.status,
            data=response.data,
            headers={str(k): str(v) for k, v in response.headers.items()},
        )


class ApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        access_token: Optional[str] = None,
        transport: Optional[Any] = None,
        timeout: int = 15,
    ):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.transport = transport or Urllib3Transport()
        self.timeout = timeout

    def __repr__(self) -> str:
        return (
            f"ApiClient(base_url={self.base_url!r}, "
            f"authenticated={bool(self.access_token)})"
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Mapping[str, Any]] = None,
        authenticated: bool = True,
    ) -> HttpResponse:
        if authenticated and not self.access_token:
            raise AuthUnavailable(
                "authenticated request requires a pre-provisioned ACCESS_TOKEN"
            )
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.access_token}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        return self.transport.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            body=body,
            timeout=self.timeout,
        )

    def get(self, path: str, *, authenticated: bool = True) -> HttpResponse:
        return self.request("GET", path, authenticated=authenticated)

    def post(
        self, path: str, payload: Mapping[str, Any], *, authenticated: bool = True
    ) -> HttpResponse:
        return self.request(
            "POST", path, payload=payload, authenticated=authenticated
        )


def response_json(response: HttpResponse) -> Dict[str, Any]:
    try:
        value = json.loads(response.data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AssertionError("response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise AssertionError("response JSON is not an object")
    return value
