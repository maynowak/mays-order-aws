"""Local tests for the B2 privacy live harness (no AWS/HTTP access)."""

from __future__ import annotations

import json
import unittest

from tests.e2e_harness import (
    BLOCKED,
    PASS,
    CleanupOwnershipError,
    ExactKeyCleanupBackend,
    OwnedOrder,
    redact,
)
from tests.privacy_e2e_harness import (
    PrivacyInvokeClient,
    PrivacyLiveConfig,
    PrivacyResponse,
    decode_jwt_subject,
    make_privacy_context,
    resolve_privacy_config,
    run_marker,
)

BASE_ENV = {
    "MO_PRIVACY_LIVE": "1",
    "MO_E2E_LIVE_CLEANUP": "1",
    "PRIVACY_E2E_INVOKER_APPROVED": "1",
    "AWS_PROFILE": "mayaws",
    "AWS_REGION": "eu-central-1",
    "PRIVACY_E2E_ACCOUNT_ID": "240571105849",
    "PRIVACY_E2E_TABLE": "mays-orders-rc4-test",
    "PRIVACY_E2E_HANDLER": "mays-orders-rc4-test-handler",
    "PRIVACY_E2E_CODE_SHA256": "expected-sha",
    "PRIVACY_E2E_PROJECT": "mays-orders-rc4-test",
    "PRIVACY_E2E_CONSUMER_ID": "cognito:issuer#client",
    "API_BASE_URL": "https://api.example.invalid",
    "PRIVACY_E2E_QUEUE_URL": "https://sqs.example.invalid/queue",
    "PRIVACY_E2E_DLQ_URL": "https://sqs.example.invalid/dlq",
    "PRIVACY_E2E_SUBJECT_A": "subject-a",
    "PRIVACY_E2E_SUBJECT_B": "subject-b",
    "PRIVACY_E2E_ACCESS_TOKEN_A": "token-a-secret",
    "PRIVACY_E2E_ACCESS_TOKEN_B": "token-b-secret",
    "PRIVACY_E2E_INTERNAL_TOKEN": "internal-secret",
}


class TestPrivacyGates(unittest.TestCase):
    def test_all_gates_ready(self):
        config = resolve_privacy_config(BASE_ENV)
        self.assertEqual(config.status, PASS)
        self.assertTrue(config.ready)
        self.assertNotIn("token-a-secret", repr(config))
        self.assertNotIn("token-b-secret", repr(config))
        self.assertNotIn("internal-secret", repr(config))

    def test_no_explicit_live_approval_is_blocked(self):
        env = dict(BASE_ENV)
        env.pop("MO_PRIVACY_LIVE")
        config = resolve_privacy_config(env)
        self.assertEqual(config.status, BLOCKED)
        self.assertIn("MO_PRIVACY_LIVE", config.blocked_reason)

    def test_no_cleanup_approval_is_blocked(self):
        env = dict(BASE_ENV)
        env.pop("MO_E2E_LIVE_CLEANUP")
        config = resolve_privacy_config(env)
        self.assertEqual(config.status, BLOCKED)
        self.assertIn("MO_E2E_LIVE_CLEANUP", config.blocked_reason)

    def test_no_invoker_approval_is_blocked(self):
        env = dict(BASE_ENV)
        env.pop("PRIVACY_E2E_INVOKER_APPROVED")
        config = resolve_privacy_config(env)
        self.assertEqual(config.status, BLOCKED)
        self.assertIn("PRIVACY_E2E_INVOKER_APPROVED", config.blocked_reason)

    def test_missing_internal_token_is_blocked_without_leaking_value(self):
        env = dict(BASE_ENV)
        env.pop("PRIVACY_E2E_INTERNAL_TOKEN")
        config = resolve_privacy_config(env)
        self.assertEqual(config.status, BLOCKED)
        self.assertIn("PRIVACY_E2E_INTERNAL_TOKEN", config.blocked_reason)
        self.assertNotIn("internal-secret", config.blocked_reason)

    def test_missing_account_or_region_is_blocked(self):
        env = dict(BASE_ENV)
        env["AWS_REGION"] = ""
        config = resolve_privacy_config(env)
        self.assertEqual(config.status, BLOCKED)
        self.assertIn("AWS_REGION", config.blocked_reason)


class TestPrivacyInvokeAdapter(unittest.TestCase):
    def test_builds_internal_event_and_parses_response(self):
        seen = {}

        def fake_invoke(event):
            seen.update(event)
            return {"statusCode": 200, "body": json.dumps({"status": "COMPLETED"})}

        client = PrivacyInvokeClient(fake_invoke)
        config = resolve_privacy_config(BASE_ENV)
        context = make_privacy_context(config, "privacy_inspect")
        response = client.invoke("privacy/inspect", "subject-a", context)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body["status"], "COMPLETED")
        self.assertEqual(seen["internalAction"], "privacy/inspect")
        self.assertEqual(seen["payload"]["subjectId"], "subject-a")
        self.assertEqual(seen["authContext"]["project"], "mays-orders-rc4-test")
        self.assertEqual(seen["authContext"]["consumerId"], "cognito:issuer#client")
        self.assertNotIn("internal-secret", repr(response))

    def test_unsupported_action_is_rejected_before_invoke(self):
        calls = []
        client = PrivacyInvokeClient(lambda event: calls.append(event) or {"statusCode": 200, "body": "{}"})
        with self.assertRaises(ValueError):
            client.invoke("privacy/drop-all", "subject-a", {})
        self.assertEqual(calls, [])

    def test_redacted_diagnostic_hides_internal_token(self):
        client = PrivacyInvokeClient(lambda event: {"statusCode": 200, "body": "{}"})
        response = PrivacyResponse(
            status_code=200,
            body={"status": "COMPLETED", "internal_token": "secret-value"},
        )
        rendered = json.dumps(client.redacted_diagnostic(response))
        self.assertNotIn("secret-value", rendered)
        self.assertIn("COMPLETED", rendered)

        diagnostic = client.diagnostic(
            test_id="G3X-PRV-X01",
            run_id="run-a",
            action="privacy/inspect",
            response=response,
        )
        self.assertEqual(diagnostic["test_id"], "G3X-PRV-X01")
        self.assertEqual(diagnostic["actual_status"], 200)

    def test_redact_handles_internal_token_key(self):
        rendered = json.dumps(redact({"internal_token": "secret-value"}))
        self.assertNotIn("secret-value", rendered)


class FakeDynamoClient:
    def __init__(self, items):
        self.items = dict(items)
        self.deleted = []

    def get_item(self, **kwargs):
        key = (kwargs["Key"]["pk"]["S"], kwargs["Key"]["sk"]["S"])
        item = self.items.get(key)
        return {"Item": item} if item else {}

    def delete_item(self, **kwargs):
        key = (kwargs["Key"]["pk"]["S"], kwargs["Key"]["sk"]["S"])
        self.deleted.append(key)
        self.items.pop(key, None)
        return {}


def _item(order_id, marker, subject="subject-a"):
    item = {
        "pk": f"ord_{order_id}",
        "sk": "#ORDER",
        "orderId": order_id,
        "status": "CONFIRMED",
        "version": 1,
        "items": [{"sku": marker, "quantity": 1, "unitPrice": 100}],
    }
    if subject is not None:
        item["subjectId"] = subject
    return item


class TestExactKeyCleanup(unittest.TestCase):
    def test_deletes_exact_key_even_after_subject_removed(self):
        order = OwnedOrder("run-a", "run-a", "ord_a", "E2E-run-a-1")
        client = FakeDynamoClient({("ord_ord_a", "#ORDER"): _item("ord_a", order.marker, subject=None)})
        cleanup = ExactKeyCleanupBackend(
            table_name="mays-orders-rc4-test",
            region="eu-central-1",
            run_id="run-a",
            client=client,
        )

        cleanup(order)

        self.assertEqual(client.deleted, [("ord_ord_a", "#ORDER")])

    def test_refuses_marker_mismatch(self):
        order = OwnedOrder("run-a", "run-a", "ord_a", "E2E-run-a-1")
        client = FakeDynamoClient({("ord_ord_a", "#ORDER"): _item("ord_a", "E2E-run-b-1")})
        cleanup = ExactKeyCleanupBackend(
            table_name="mays-orders-rc4-test",
            region="eu-central-1",
            run_id="run-a",
            client=client,
        )

        with self.assertRaises(CleanupOwnershipError):
            cleanup(order)
        self.assertEqual(client.deleted, [])

    def test_refuses_foreign_run_ownership(self):
        order = OwnedOrder("run-b", "run-b", "ord_a", "E2E-run-b-1")
        client = FakeDynamoClient({("ord_ord_a", "#ORDER"): _item("ord_a", order.marker)})
        cleanup = ExactKeyCleanupBackend(
            table_name="mays-orders-rc4-test",
            region="eu-central-1",
            run_id="run-a",
            client=client,
        )

        with self.assertRaises(CleanupOwnershipError):
            cleanup(order)
        self.assertEqual(client.deleted, [])

    def test_missing_item_is_noop(self):
        order = OwnedOrder("run-a", "run-a", "ord_missing", "E2E-run-a-1")
        client = FakeDynamoClient({})
        cleanup = ExactKeyCleanupBackend(
            table_name="mays-orders-rc4-test",
            region="eu-central-1",
            run_id="run-a",
            client=client,
        )

        cleanup(order)
        self.assertEqual(client.deleted, [])


class TestTokenHelper(unittest.TestCase):
    def test_decode_subject_and_run_marker(self):
        token = "header." + "eyJzdWIiOiJzdWJqZWN0LWEifQ" + ".signature"
        self.assertEqual(decode_jwt_subject(token), "subject-a")
        self.assertEqual(run_marker("run-a", "1"), "E2E-run-a-1")


if __name__ == "__main__":
    unittest.main()
