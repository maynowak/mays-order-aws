"""Local validation of the RC4 E2E harness (no HTTP/AWS access)."""

from __future__ import annotations

import json
import unittest

from tests.e2e_harness import (
    BLOCKED,
    FAIL,
    NOT_EXECUTED,
    PASS,
    ApiClient,
    AuthUnavailable,
    CleanupError,
    CleanupOwnershipError,
    CleanupUnavailable,
    Diagnostic,
    E2ERun,
    FakeTransport,
    HttpResponse,
    OwnedOrder,
    build_synthetic_order,
    classify_outcome,
    redact,
    resolve_auth,
    response_json,
)


class TestUnauthenticatedBoundary(unittest.TestCase):
    def test_unauthenticated_get_orders_is_independent_401(self):
        """T10C-03: no token, no credentials, deterministic 401."""
        transport = FakeTransport(
            [HttpResponse(status=401, data=b'{"message":"Unauthorized"}')]
        )
        client = ApiClient("https://api.example.invalid", transport=transport)

        response = client.get("/orders", authenticated=False)

        self.assertEqual(response.status, 401)
        self.assertEqual(response_json(response)["message"], "Unauthorized")
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertNotIn("Authorization", call["headers"])
        self.assertNotIn("access_token", call)

    def test_authenticated_request_without_token_is_rejected(self):
        """T10C-02: authenticated and unauthenticated paths stay separate."""
        transport = FakeTransport([])
        client = ApiClient("https://api.example.invalid", transport=transport)

        with self.assertRaises(AuthUnavailable):
            client.get("/orders", authenticated=True)
        self.assertEqual(transport.calls, [])


class TestAuthClassification(unittest.TestCase):
    def test_live_mode_requires_explicit_opt_in(self):
        auth = resolve_auth({"ACCESS_TOKEN": "should-not-be-used"})
        self.assertEqual(auth.status, BLOCKED)
        self.assertIn("not enabled", auth.blocked_reason)

    def test_live_mode_without_token_is_blocked(self):
        auth = resolve_auth(
            {"MO_E2E_LIVE": "1", "API_BASE_URL": "https://api.example.invalid"}
        )
        self.assertEqual(auth.status, BLOCKED)
        self.assertFalse(auth.ready)
        self.assertIn("ACCESS_TOKEN", auth.blocked_reason)

    def test_live_mode_with_preprovided_token_is_ready(self):
        auth = resolve_auth(
            {
                "MO_E2E_LIVE": "1",
                "API_BASE_URL": "https://api.example.invalid",
                "ACCESS_TOKEN": "token-value",
            }
        )
        self.assertEqual(auth.status, PASS)
        self.assertTrue(auth.ready)
        self.assertNotIn("token-value", repr(auth))

    def test_outcome_classification_distinguishes_all_states(self):
        self.assertEqual(
            classify_outcome(executed=True, passed=True), PASS
        )
        self.assertEqual(
            classify_outcome(executed=True, passed=False), FAIL
        )
        self.assertEqual(
            classify_outcome(
                executed=False, passed=False, blocked_reason="missing token"
            ),
            BLOCKED,
        )
        self.assertEqual(
            classify_outcome(executed=False, passed=False), NOT_EXECUTED
        )


class TestSyntheticData(unittest.TestCase):
    def test_fixture_is_run_scoped_unique_and_non_personal(self):
        run_a_1 = build_synthetic_order("run-a", 1)
        run_a_2 = build_synthetic_order("run-a", 2)
        run_b_1 = build_synthetic_order("run-b", 1)

        self.assertNotEqual(run_a_1.marker, run_a_2.marker)
        self.assertNotEqual(run_a_1.marker, run_b_1.marker)
        self.assertEqual(run_a_1.payload["items"][0]["sku"], run_a_1.marker)
        self.assertTrue(
            run_a_1.payload["customer"]["email"].endswith("@example.invalid")
        )
        self.assertIn("run-a", run_a_1.payload["customer"]["name"])
        self.assertNotIn("test-user@example.com", json.dumps(run_a_1.payload))

    def test_each_run_has_its_own_ledger(self):
        first = E2ERun(run_id="run-a")
        second = E2ERun(run_id="run-b")
        first.register_created("ord_a", "run-a-1")

        self.assertEqual(first.cleanup.run_id, "run-a")
        self.assertEqual(second.cleanup.run_id, "run-b")
        self.assertEqual(second.orders, [])


class TestCleanupSafety(unittest.TestCase):
    def test_owned_order_cleanup_records_success(self):
        run = E2ERun(run_id="run-a")
        order = run.register_created("ord_owned", "run-a-1")
        deleted = []

        results = run.cleanup_all(deleted.append)

        self.assertEqual(deleted, [order])
        self.assertEqual(order.cleanup_status, PASS)
        self.assertEqual(results[0].status, PASS)

    def test_cleanup_runs_when_test_action_raises(self):
        run = E2ERun(run_id="run-a")
        order = run.register_created("ord_after_error", "run-a-1")
        deleted = []

        def failing_action():
            raise RuntimeError("test body failed")

        with self.assertRaises(RuntimeError):
            run.run_with_cleanup(failing_action, deleted.append)

        self.assertEqual(deleted, [order])
        self.assertEqual(order.cleanup_status, PASS)

    def test_cleanup_failure_is_reported_not_suppressed(self):
        run = E2ERun(run_id="run-a")
        order = run.register_created("ord_failure", "run-a-1")

        def failing_delete(_order):
            raise OSError("cleanup transport failed")

        with self.assertRaises(CleanupError):
            run.cleanup_all(failing_delete)

        self.assertEqual(order.cleanup_status, FAIL)
        self.assertEqual(run.cleanup.results[0].status, FAIL)
        self.assertEqual(run.cleanup.results[0].error_type, "OSError")

    def test_foreign_order_is_never_deleted(self):
        """T10C-05 / Mutation A target: ownership guard must fail closed."""
        run = E2ERun(run_id="run-a")
        foreign = OwnedOrder(
            run_id="run-b",
            owner_run_id="run-b",
            order_id="ord_foreign",
            marker="foreign",
        )
        deleted = []

        with self.assertRaises(CleanupOwnershipError):
            run.cleanup.cleanup(foreign, deleted.append)

        self.assertEqual(deleted, [])
        self.assertEqual(foreign.cleanup_status, BLOCKED)
        self.assertEqual(run.cleanup.results[0].status, BLOCKED)

    def test_unavailable_cleanup_is_an_explicit_blocker(self):
        run = E2ERun(run_id="run-a")
        order = run.register_created("ord_no_api", "run-a-1")

        def unavailable(_order):
            raise CleanupUnavailable("no safe order delete endpoint")

        with self.assertRaises(CleanupError):
            run.cleanup_all(unavailable)

        self.assertEqual(order.cleanup_status, FAIL)
        self.assertEqual(run.cleanup.results[0].error_type, "CleanupUnavailable")


class TestDiagnostics(unittest.TestCase):
    def test_secret_redaction_covers_nested_and_bearer_values(self):
        payload = {
            "access_token": "access-secret",
            "nested": {"refresh_token": "refresh-secret"},
            "authorization": "Bearer bearer-secret",
            "message": "Bearer inline-secret",
            "orderId": "ord_visible",
        }

        safe = redact(payload)
        rendered = json.dumps(safe)

        for secret in (
            "access-secret",
            "refresh-secret",
            "bearer-secret",
            "inline-secret",
        ):
            self.assertNotIn(secret, rendered)
        self.assertIn("ord_visible", rendered)
        self.assertEqual(safe["authorization"], "[REDACTED]")

    def test_failure_diagnostic_contains_required_context(self):
        diagnostic = Diagnostic(
            test_id="T10C-01",
            run_id="run-a",
            operation="GET /orders/{orderId}",
            expected_status=200,
            actual_status=500,
            error_type="AssertionError",
            cleanup_status=FAIL,
            blocked_reason=None,
        )

        payload = diagnostic.as_dict()

        self.assertEqual(payload["test_id"], "T10C-01")
        self.assertEqual(payload["run_id"], "run-a")
        self.assertEqual(payload["operation"], "GET /orders/{orderId}")
        self.assertEqual(payload["expected_status"], 200)
        self.assertEqual(payload["actual_status"], 500)
        self.assertEqual(payload["error_type"], "AssertionError")
        self.assertEqual(payload["cleanup_status"], FAIL)

    def test_blocked_diagnostic_reports_reason_without_credentials(self):
        diagnostic = Diagnostic(
            test_id="T10C-02",
            run_id="run-a",
            operation="POST /orders",
            expected_status=201,
            actual_status=None,
            error_type=None,
            cleanup_status=NOT_EXECUTED,
            blocked_reason="pre-provisioned ACCESS_TOKEN missing for live E2E",
        )

        payload = diagnostic.as_dict()
        rendered = json.dumps(payload)

        self.assertEqual(payload["blocked_reason"], diagnostic.blocked_reason)
        self.assertNotIn("Bearer ", rendered)
        self.assertNotIn("password", rendered.lower())


if __name__ == "__main__":
    unittest.main()
