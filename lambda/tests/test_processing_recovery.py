"""MO-RC4-P02I-B2 — automatische Processing-Recovery + GSI3-Pflege."""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest import mock

import index
import recovery
import sqs_handler
from order_service import create_order_service

sys.path.insert(0, os.path.dirname(__file__))

from test_processing_lifecycle import (  # noqa: E402
    FakeDynamo,
    item as lifecycle_item,
    processing_handler,
    run as run_worker,
)

os.environ.setdefault("ORDERS_TABLE", "mays-orders")
os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
ORDER_ID = "ord_2f4b1c9e0000000000000000"


def iso(moment):
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"


def claimed(seconds_ago, **extra):
    return iso(NOW - timedelta(seconds=seconds_ago))


def make_item(order_id=ORDER_ID, *, state="running", claimed_ago=400,
              attempts=1, status="CONFIRMED", subject="user-1", indexed=True,
              **extra):
    item = {
        "pk": f"ord_{order_id}",
        "sk": "#ORDER",
        "orderId": order_id,
        "status": status,
        "processingState": state,
        "processingAttempts": attempts,
        "processingClaimedAt": claimed(claimed_ago) if claimed_ago is not None else None,
    }
    if subject:
        item["subjectId"] = subject
    if indexed and state == "running" and claimed_ago is not None:
        item["gsi3pk"] = "PROCESSING#RUNNING"
        item["gsi3sk"] = item["processingClaimedAt"]
    item.update(extra)
    return item


class FakeTable:
    def __init__(self, items):
        self.items = {item["pk"]: dict(item) for item in items}
        self.queries = []
        self.sent_reads = 0

    def query(self, **kwargs):
        self.queries.append(kwargs)
        values = kwargs["ExpressionAttributeValues"]
        cutoff = values[":cutoff"]
        matches = [
            dict(item) for item in self.items.values()
            if item.get("gsi3pk") == values[":pk"] and item.get("gsi3sk", "") <= cutoff
        ]
        matches.sort(key=lambda entry: entry.get("gsi3sk", ""))
        start = kwargs.get("ExclusiveStartKey")
        offset = start.get("offset", 0) if start else 0
        limit = kwargs.get("Limit", 100)
        page = matches[offset:offset + limit]
        response = {"Items": page}
        if offset + limit < len(matches):
            response["LastEvaluatedKey"] = {"offset": offset + limit}
        return response

    def get_item(self, **kwargs):
        self.sent_reads += 1
        item = self.items.get(kwargs["Key"]["pk"])
        return {"Item": dict(item)} if item else {}


def sender(fail_for=(), calls=None):
    def _send(order_id):
        if calls is not None:
            calls.append(order_id)
        if order_id in fail_for:
            raise RuntimeError("SQS down")
    return _send


class TestProcessingRecoverySelection(unittest.TestCase):
    def test_expired_claim_is_redelivered(self):
        table = FakeTable([make_item()])
        calls = []
        report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW)

        self.assertEqual(report["candidates"], 1)
        self.assertEqual(report["sent"], 1)
        self.assertEqual(calls, [ORDER_ID])
        self.assertEqual(report["kind"], "processing")

    def test_leas_not_expired_is_skipped(self):
        # Lease 300 + Margin 60 => cutoff = now-360; 200 s alt = noch aktiv
        table = FakeTable([make_item(claimed_ago=200)])
        calls = []
        report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW)
        # vom Index nicht geliefert (gsi3sk > cutoff)
        self.assertEqual(report["candidates"], 0)
        self.assertEqual(calls, [])

    def test_safety_margin_boundary(self):
        # 350 s alt: Lease abgelaufen, aber innerhalb des 60-s-Puffers
        table = FakeTable([make_item(claimed_ago=350)])
        report = recovery.run_processing_recovery(table, sender(), now=NOW)
        self.assertEqual(report["candidates"], 0)

    def test_cutoff_uses_lease_plus_margin(self):
        table = FakeTable([])
        recovery.run_processing_recovery(table, sender(), now=NOW, safety_margin_seconds=120)
        values = table.queries[0]["ExpressionAttributeValues"]
        self.assertEqual(
            values[":cutoff"],
            iso(NOW - timedelta(seconds=sqs_handler.PROCESSING_LEASE_SECONDS + 120)),
        )

    def test_non_running_states_are_skipped(self):
        for state in ("pending", "succeeded", "failed"):
            with self.subTest(state=state):
                table = FakeTable([make_item(state=state, indexed=True)])
                calls = []
                report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW)
                self.assertEqual(calls, [])

    def test_budget_exhausted_is_skipped_and_counted(self):
        table = FakeTable([make_item(attempts=sqs_handler.MAX_PROCESSING_ATTEMPTS)])
        calls = []
        report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW)
        self.assertEqual(calls, [])
        self.assertEqual(report["budgetExhausted"], 1)
        self.assertEqual(report["skipped"].get("budget_exhausted"), 1)

    def test_cancelled_is_skipped(self):
        table = FakeTable([make_item(status="CANCELLED")])
        calls = []
        report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW)
        self.assertEqual(calls, [])
        self.assertEqual(report["skipped"].get("cancelled"), 1)

    def test_anonymized_is_skipped(self):
        table = FakeTable([make_item(subject=None)])
        calls = []
        report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW)
        self.assertEqual(calls, [])
        self.assertEqual(report["skipped"].get("anonymized"), 1)

    def test_deleted_order_is_skipped(self):
        entry = make_item()
        table = FakeTable([entry])
        table.items.clear()  # Index-Treffer, Item inzwischen gelöscht
        report = recovery.run_processing_recovery(table, sender(), now=NOW)
        # Query liefert nichts mehr -> keine Kandidaten
        self.assertEqual(report["sent"], 0)

    def test_legacy_running_without_index_attrs_is_not_found(self):
        table = FakeTable([make_item(indexed=False)])
        calls = []
        report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW)
        self.assertEqual(report["candidates"], 0)
        self.assertEqual(calls, [])


class TestProcessingRecoveryLimits(unittest.TestCase):
    def test_limit_bounds_run(self):
        items = [make_item(f"ord_{i}", claimed_ago=400 + i) for i in range(5)]
        table = FakeTable(items)
        calls = []
        report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW, limit=2)
        self.assertEqual(report["candidates"], 2)
        self.assertEqual(len(calls), 2)

    def test_pagination_across_pages(self):
        items = [make_item(f"ord_{i}", claimed_ago=400 + i) for i in range(5)]
        table = FakeTable(items)
        calls = []

        def query_once(**kwargs):
            kwargs["Limit"] = 2
            return FakeTable.query(table, **kwargs)

        table.query = query_once
        report = recovery.run_processing_recovery(table, sender(calls=calls), now=NOW, limit=5)
        self.assertEqual(len(calls), 5)
        self.assertEqual(len(table.queries), 3)

    def test_send_failure_is_counted_not_raised(self):
        table = FakeTable([make_item()])
        report = recovery.run_processing_recovery(table, sender(fail_for={ORDER_ID}), now=NOW)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["sent"], 0)
        self.assertEqual(report["skipped"].get("send_failed"), 1)

    def test_recovery_performs_no_writes(self):
        table = FakeTable([make_item()])
        # FakeTable hat bewusst kein update_item; jeder Schreibversuch waere ein AttributeError
        report = recovery.run_processing_recovery(table, sender(), now=NOW)
        self.assertEqual(report["sent"], 1)

    def test_repeated_runs_resend_at_least_once(self):
        table = FakeTable([make_item()])
        calls = []
        recovery.run_processing_recovery(table, sender(calls=calls), now=NOW)
        recovery.run_processing_recovery(table, sender(calls=calls), now=NOW + timedelta(minutes=5))
        self.assertEqual(calls, [ORDER_ID, ORDER_ID])  # Dokumentierte At-least-once-Semantik


class TestInternalAction(unittest.TestCase):
    def _call(self, event):
        with mock.patch("boto3.resource"), \
             mock.patch.dict("index.os.environ", {"ORDERS_TABLE": "mays-orders"}), \
             mock.patch("index.create_order_service"):
            return index.handler(event, None)

    def test_processing_scan_returns_report(self):
        with mock.patch("recovery.run_processing_recovery",
                        return_value={"status": "COMPLETED", "sent": 2}) as runner:
            response = self._call({"internalAction": "processing/scan",
                                   "options": {"limit": 5, "safetyMarginSeconds": 90}})
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["sent"], 2)
        self.assertEqual(runner.call_args.kwargs["limit"], 5)
        self.assertEqual(runner.call_args.kwargs["safety_margin_seconds"], 90)

    def test_delivery_action_still_works(self):
        with mock.patch("recovery.run_recovery", return_value={"status": "COMPLETED"}) as runner:
            response = self._call({"internalAction": "recovery/scan"})
        self.assertEqual(response["statusCode"], 200)
        runner.assert_called_once()

    def test_unknown_action_is_rejected(self):
        response = self._call({"internalAction": "processing/other"})
        self.assertEqual(response["statusCode"], 400)


class TestGsi3Maintenance(unittest.TestCase):
    def test_claim_writes_index_attributes(self):
        handler_type = processing_handler()
        client = FakeDynamo(lifecycle_item(orderType={"S": handler_type}))
        run_worker(client)

        claim = next(
            update for update in client.updates
            if "gsi3pk = :gsi3pk" in update["UpdateExpression"]
        )
        self.assertIn("gsi3pk = :gsi3pk", claim["UpdateExpression"])
        self.assertIn("gsi3sk = :now", claim["UpdateExpression"])
        self.assertEqual(claim["ExpressionAttributeValues"][":gsi3pk"]["S"],
                         sqs_handler.PROCESSING_INDEX_PK)

    def test_success_removes_index_attributes(self):
        handler_type = processing_handler()
        client = FakeDynamo(lifecycle_item(orderType={"S": handler_type}))
        run_worker(client)
        completion = client.updates[-1]
        self.assertIn("REMOVE", completion["UpdateExpression"])
        self.assertIn("gsi3pk", completion["UpdateExpression"])
        self.assertIn("gsi3sk", completion["UpdateExpression"])

    def test_failure_removes_index_attributes(self):
        from order_handlers import ProcessingFailure

        def fail(order, payload, context):
            raise ProcessingFailure("UPSTREAM", "nope")

        handler_type = processing_handler(fail)
        client = FakeDynamo(lifecycle_item(orderType={"S": handler_type}))
        run_worker(client)
        completion = client.updates[-1]
        self.assertIn("gsi3pk, gsi3sk", completion["UpdateExpression"])

    def test_release_removes_index_attributes(self):
        def boom(order, payload, context):
            raise RuntimeError("technical")

        handler_type = processing_handler(boom)
        client = FakeDynamo(lifecycle_item(orderType={"S": handler_type}))
        with self.assertRaises(RuntimeError):
            run_worker(client)
        release = client.updates[-1]
        self.assertIn("REMOVE processingClaimedAt, gsi3pk, gsi3sk",
                      release["UpdateExpression"])


class TestAnonymizeIndexRemoval(unittest.TestCase):
    def test_anonymize_removes_gsi3_attributes(self):
        from order_service import OrderService

        captured = {}
        item = {
            "pk": f"ord_{ORDER_ID}", "sk": "#ORDER", "orderId": ORDER_ID,
            "status": "CONFIRMED", "subjectId": "user-1",
            "consumerId": "cognito:test#client", "version": 1,
            "processingState": "running", "gsi3pk": "PROCESSING#RUNNING",
            "gsi3sk": "2026-11-01T10:00:00.000Z",
        }

        class StubTable:
            def query(self, **kwargs):
                return {"Items": [dict(item)]}

            def update_item(self, **kwargs):
                captured.update(kwargs)
                return {}

        service = OrderService("mays-orders", client=StubTable())
        service.erase_subject(
            "user-1",
            context={"project": "mays-orders", "authorized": True,
                     "privacy_erase": True, "internal_token": "test-secret"},
            options={"mode": "EXECUTE", "policy": "ANONYMIZE"},
        )

        expression = captured["UpdateExpression"]
        self.assertIn("gsi3pk, gsi3sk", expression)


if __name__ == "__main__":
    unittest.main()
