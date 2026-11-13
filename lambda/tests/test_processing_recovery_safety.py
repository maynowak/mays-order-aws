"""MO-RC4-P02I-A — Recovery-Safety: Klassifikation, ACK-Semantik, Logging."""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

import sqs_handler

# Erlaubt den Import der Fixtures sowohl via discover als auch direkt.
sys.path.insert(0, os.path.dirname(__file__))

from test_processing_lifecycle import (
    FakeClientError,
    FakeDynamo,
    item,
    processing_handler,
    run,
)

os.environ.setdefault("ORDERS_TABLE", "mays-orders")


def run_captured(client, status="CONFIRMED", payload=None):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        outcome = run(client, status=status, payload=payload)
    return outcome, buffer.getvalue()


class TestClaimFailureClassification(unittest.TestCase):
    """Getrennte Outcomes statt eines Sammel-Status (P02I-A)."""

    def test_already_succeeded_is_noop(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "succeeded"}))
        outcome, log = run_captured(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_NOOP)
        self.assertNotIn("PROCESSING_CLAIMED", log)

    def test_active_claim_is_already_running(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "running"},
                                 processingAttemptId={"S": "other"},
                                 processingAttempts={"N": "1"},
                                 processingClaimedAt={"S": "9999-12-31T23:59:59.000Z"}))
        outcome, log = run_captured(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_ALREADY_RUNNING)
        self.assertIn("PROCESSING_ALREADY_RUNNING", log)
        self.assertNotIn("PROCESSING_CLAIMED", log)

    def test_terminal_failed_is_distinct(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "failed"},
                                 processingAttempts={"N": "1"}))
        outcome, log = run_captured(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_TERMINAL_FAILED)
        self.assertIn("PROCESSING_TERMINAL_FAILED", log)

    def test_exhausted_budget_is_distinct(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "running"},
                                 processingAttemptId={"S": "old"},
                                 processingAttempts={"N": str(sqs_handler.MAX_PROCESSING_ATTEMPTS)},
                                 processingClaimedAt={"S": "2000-01-01T00:00:00.000Z"}))
        outcome, log = run_captured(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_ATTEMPT_EXHAUSTED)
        self.assertIn("PROCESSING_ATTEMPT_EXHAUSTED", log)


class TestAcknowledgementSemantics(unittest.TestCase):
    """Welche Outcomes werden quittiert (ACK) und welche nicht?"""

    def test_skipped_outcomes_are_acknowledged(self):
        for outcome in (
            sqs_handler.OUTCOME_PROCESSING_ALREADY_RUNNING,
            sqs_handler.OUTCOME_PROCESSING_TERMINAL_FAILED,
            sqs_handler.OUTCOME_PROCESSING_ATTEMPT_EXHAUSTED,
            sqs_handler.OUTCOME_PROCESSING_SKIPPED,
            sqs_handler.OUTCOME_PROCESSING_REJECTED,
            sqs_handler.OUTCOME_PROCESSING_SUCCEEDED,
            sqs_handler.OUTCOME_PROCESSING_FAILED,
        ):
            with self.subTest(outcome=outcome):
                self.assertIn(outcome, sqs_handler._SUCCESS_OUTCOMES)

    def test_technical_and_invalid_outcomes_are_not_acknowledged(self):
        for outcome in (
            sqs_handler.OUTCOME_HANDLER_FAILED,
            sqs_handler.OUTCOME_UNKNOWN_TYPE,
            sqs_handler.OUTCOME_MISSING,
        ):
            with self.subTest(outcome=outcome):
                self.assertNotIn(outcome, sqs_handler._SUCCESS_OUTCOMES)

    def test_batch_failure_only_contains_failing_message(self):
        records = [
            {"messageId": "ok", "body": json.dumps({"orderId": "ord_1", "status": "CONFIRMED"})},
            {"messageId": "busy", "body": json.dumps({"orderId": "ord_2", "status": "CONFIRMED"})},
        ]
        with mock.patch.object(
            sqs_handler, "_process_order",
            side_effect=[sqs_handler.OUTCOME_PROCESSING_ALREADY_RUNNING,
                         sqs_handler.OUTCOME_HANDLER_FAILED],
        ):
            response = sqs_handler.handler({"Records": records}, None)
        self.assertEqual(response["batchItemFailures"], [{"itemIdentifier": "busy"}])


class TestCrashSafety(unittest.TestCase):
    def test_rejected_status_transition_writes_no_processing_state(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(status="CANCELLED", orderType={"S": handler_type}))
        outcome, _ = run_captured(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_REJECTED)
        self.assertNotIn("processingState", client.item)
        self.assertEqual(client.updates, [])

    def test_crash_between_claim_and_completion_leaves_running(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type}))
        original_update = client.update_item

        def fail_completion(**kwargs):
            if kwargs["UpdateExpression"].startswith("SET processingState = :succeeded"):
                raise RuntimeError("crash")
            return original_update(**kwargs)

        client.update_item = fail_completion
        with self.assertRaises(RuntimeError):
            run(client)

        self.assertEqual(client.item["processingState"]["S"], "running")
        self.assertIn("processingAttemptId", client.item)
        self.assertIn("processingClaimedAt", client.item)
        self.assertNotIn("result", client.item)

    def test_side_effect_then_crash_leaves_no_result(self):
        effects = []

        def handler(order, payload, context):
            effects.append(context["attemptId"])
            raise RuntimeError("crash after side effect")

        handler_type = processing_handler(handler)
        client = FakeDynamo(item(orderType={"S": handler_type}))
        with self.assertRaises(RuntimeError):
            run(client)

        self.assertEqual(len(effects), 1)
        self.assertNotIn("result", client.item)
        self.assertEqual(client.item["processingState"]["S"], "pending")
        self.assertNotIn("processingClaimedAt", client.item)

    def test_technical_error_logs_release_without_payload(self):
        def handler(order, payload, context):
            raise RuntimeError("boom")

        handler_type = processing_handler(handler)
        client = FakeDynamo(item(orderType={"S": handler_type}))
        buffer = io.StringIO()
        with redirect_stdout(buffer), self.assertRaises(RuntimeError):
            run(client)
        log = buffer.getvalue()
        self.assertIn("PROCESSING_RETRY_RELEASED", log)
        self.assertNotIn("boom", log)  # keine Exception-Texte

    def test_duplicate_after_success_does_not_reclaim(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type}))
        run(client)
        outcome, log = run_captured(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_NOOP)
        self.assertNotIn("PROCESSING_CLAIMED", log)


class TestRecoveryObservability(unittest.TestCase):
    def test_claim_and_success_events_are_logged(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome, log = run_captured(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SUCCEEDED)
        self.assertIn("PROCESSING_CLAIMED", log)
        self.assertIn("PROCESSING_SUCCEEDED", log)
        self.assertIn("orderId=", log)
        self.assertIn("attemptId=", log)

    def test_expired_lease_is_logged(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "running"},
                                 processingAttemptId={"S": "old"},
                                 processingAttempts={"N": "1"},
                                 processingClaimedAt={"S": "2000-01-01T00:00:00.000Z"}))
        outcome, log = run_captured(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SUCCEEDED)
        self.assertIn("PROCESSING_LEASE_EXPIRED", log)
        self.assertIn("PROCESSING_CLAIMED", log)

    def test_recovery_required_logged_on_attempt_conflict(self):
        client = None

        def steal(order, payload, context):
            client.item["processingAttemptId"] = {"S": "other"}
            return {"result": {"x": 1}}

        handler_type = processing_handler(steal)
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome, log = run_captured(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SKIPPED)
        self.assertIn("PROCESSING_RECOVERY_REQUIRED", log)

    def test_logs_contain_no_result_content_or_pii(self):
        handler_type = processing_handler(
            lambda o, p, c: {"result": {"email": "max@example.com", "value": "SECRET"}}
        )
        client = FakeDynamo(item(orderType={"S": handler_type}))
        _, log = run_captured(client)

        self.assertNotIn("max@example.com", log)
        self.assertNotIn("SECRET", log)
        self.assertNotIn("customer", log)

    def test_business_failure_logs_event_without_message_text(self):
        from order_handlers import ProcessingFailure

        def fail(order, payload, context):
            raise ProcessingFailure("UPSTREAM", "internal detail")

        handler_type = processing_handler(fail)
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome, log = run_captured(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_FAILED)
        self.assertIn("PROCESSING_FAILED", log)
        self.assertNotIn("internal detail", log)


if __name__ == "__main__":
    unittest.main()
