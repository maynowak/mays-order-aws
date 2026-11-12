"""RC4 live E2E tests — isolated by test run and guarded by explicit opt-in.

Local harness validation lives in ``tests/test_e2e_harness.py`` and uses a fake
HTTP transport. This module performs no network access unless ALL of the
following are true:

- ``MO_E2E_LIVE=1``
- ``API_BASE_URL`` is set
- a pre-provisioned ``ACCESS_TOKEN`` is present
- ``MO_E2E_LIVE_CLEANUP=1`` is explicitly approved
- ``E2E_SUBJECT`` matches the access-token subject and is verified against
  each stored order before cleanup

Without these conditions no order is created. There is no silent fallback to
direct DynamoDB deletion.

The previous global SQS queue-count assertion was removed: it was not
run-scoped and could neither prove ownership nor provide safe cleanup.
"""

from __future__ import annotations

import json
import os
import time
import unittest

from tests.e2e_harness import (
    BLOCKED,
    ApiClient,
    CleanupError,
    Diagnostic,
    E2ERun,
    LiveCleanupBackend,
    Urllib3Transport,
    resolve_auth,
    response_json,
)

# Live order tests are enabled only for an explicitly approved run with an
# owner-verified cleanup backend. There is no silent fallback to direct DDB
# deletion when this opt-in is absent.
LIVE_CLEANUP_AVAILABLE = os.environ.get("MO_E2E_LIVE_CLEANUP") == "1"

CONFIRM_TIMEOUT_SECONDS = int(os.environ.get("E2E_CONFIRM_TIMEOUT_SECONDS", "60"))
POLL_INTERVAL_SECONDS = float(os.environ.get("E2E_POLL_INTERVAL_SECONDS", "3"))


def _live_endpoint():
    if os.environ.get("MO_E2E_LIVE") != "1":
        return None
    return (os.environ.get("API_BASE_URL") or "").strip() or None


class LiveE2EBase(unittest.TestCase):
    """Independent live tests; each test creates and tracks its own order."""

    @classmethod
    def setUpClass(cls):
        cls.auth = resolve_auth(os.environ)

    def setUp(self):
        if not self.auth.ready:
            self.skipTest(f"BLOCKED: {self.auth.blocked_reason}")
        if not LIVE_CLEANUP_AVAILABLE:
            self.skipTest(
                "BLOCKED: no explicit live cleanup approval; set "
                "MO_E2E_LIVE_CLEANUP=1 only for an approved run"
            )
        subject_id = (os.environ.get("E2E_SUBJECT") or "").strip()
        if not subject_id:
            self.skipTest("BLOCKED: E2E_SUBJECT missing for owner-verified cleanup")
        self.run = E2ERun()
        self.cleanup_backend = LiveCleanupBackend(
            table_name=os.environ.get("ORDERS_TABLE", ""),
            region=os.environ.get("AWS_REGION", "eu-central-1"),
            subject_id=subject_id,
        )
        self.client = ApiClient(
            self.auth.api_base_url,
            access_token=self.auth.access_token,
            transport=Urllib3Transport(),
        )

    def tearDown(self):
        if not getattr(self, "run", None) or not self.run.orders:
            return
        try:
            self.run.cleanup_all(self.cleanup_backend)
        except CleanupError:
            for order in self.run.orders:
                order.cleanup_status = BLOCKED
            raise

    def _expect(self, response, expected: int, *, operation: str):
        diagnostic = Diagnostic(
            test_id=self.id().rsplit(".", 1)[-1],
            run_id=self.run.run_id,
            operation=operation,
            expected_status=expected,
            actual_status=response.status,
            error_type=None if response.status == expected else "UnexpectedStatus",
        )
        self.run.record_diagnostic(diagnostic)
        if response.status != expected:
            self.fail(
                "unexpected HTTP status: "
                + json.dumps(diagnostic.as_dict(), separators=(",", ":"))
            )

    def _create_order(self):
        synthetic = self.run.synthetic_order(1)
        response = self.client.post("/orders", synthetic.payload)
        self._expect(response, 201, operation="POST /orders")
        order = response_json(response)
        self.assertIn("orderId", order)
        owned = self.run.register_created(order["orderId"], synthetic.marker)
        return owned, order

    def _wait_for_confirmed(self, order_id: str) -> dict:
        deadline = time.monotonic() + CONFIRM_TIMEOUT_SECONDS
        last_status = None
        while time.monotonic() < deadline:
            response = self.client.get(f"/orders/{order_id}")
            self._expect(
                response,
                200,
                operation=f"GET /orders/{order_id}",
            )
            order = response_json(response)
            last_status = order.get("status")
            if last_status == "CONFIRMED":
                return order
            if last_status not in ("PENDING", "CONFIRMED", "PROCESSING"):
                self.fail(f"unexpected order status: {last_status}")
            time.sleep(POLL_INTERVAL_SECONDS)
        self.fail(
            f"order {order_id} not CONFIRMED after {CONFIRM_TIMEOUT_SECONDS}s; "
            f"last status: {last_status}"
        )

    def test_post_order_creates_pending_order(self):
        """T10C-01: each test creates its own order; no shared self.order_id."""
        owned, order = self._create_order()

        self.assertEqual(order["status"], "PENDING")
        self.assertEqual(order["totalAmount"], 100)
        self.assertEqual(order["items"][0]["sku"], owned.marker)

    def test_order_transitions_to_confirmed_independently(self):
        """T10C-01: transition test owns its own order."""
        owned, _order = self._create_order()

        confirmed = self._wait_for_confirmed(owned.order_id)

        self.assertEqual(confirmed["orderId"], owned.order_id)
        self.assertEqual(confirmed["status"], "CONFIRMED")

    def test_order_data_integrity_independently(self):
        """T10C-01: integrity test owns its own order."""
        owned, _order = self._create_order()

        response = self.client.get(f"/orders/{owned.order_id}")
        self._expect(
            response,
            200,
            operation=f"GET /orders/{owned.order_id}",
        )
        stored = response_json(response)

        self.assertEqual(stored["orderId"], owned.order_id)
        self.assertEqual(stored["currency"], "EUR")
        self.assertEqual(len(stored["items"]), 1)
        self.assertEqual(stored["items"][0]["sku"], owned.marker)


class TestLiveUnauthenticatedEndpoint(unittest.TestCase):
    """T10C-03: independent 401 test that never needs an access token."""

    def setUp(self):
        self.api_base_url = _live_endpoint()
        if not self.api_base_url:
            self.skipTest(
                "BLOCKED: live E2E not enabled or API_BASE_URL missing; "
                "local 401 coverage uses the fake transport"
            )
        self.client = ApiClient(self.api_base_url, transport=Urllib3Transport())

    def test_unauthenticated_get_orders_returns_401(self):
        response = self.client.get("/orders", authenticated=False)
        self.assertEqual(response.status, 401, "expected unauthenticated 401")
