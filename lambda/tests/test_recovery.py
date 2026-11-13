"""MO-RC4-P02F — PENDING-Recovery (GSI1-Fenster, Claim/Lease, Zustellung)."""

import unittest
from datetime import datetime, timedelta, timezone

from errors import OrderError
from recovery import run_recovery

NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


def iso(moment):
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"


class FakeClientError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeTable:
    """Minimales DynamoDB-Table-Stub mit GSI1-Query und Claim-Semantik."""

    def __init__(self, items, *, sent_mark_fails=False):
        self.items = {item["pk"]: dict(item) for item in items}
        self.sent_mark_fails = sent_mark_fails
        self.updates = []
        self.sent = []

    def _item(self, key):
        return self.items.get(key["pk"])

    def query(self, **kwargs):
        values = kwargs["ExpressionAttributeValues"]
        since = values[":since"]
        matches = [
            dict(item) for item in self.items.values()
            if item.get("gsi1pk") == values[":list"] and item.get("gsi1sk", "") >= since
        ]
        matches.sort(key=lambda item: item.get("gsi1sk", ""))
        limit = kwargs.get("Limit", 100)
        start = kwargs.get("ExclusiveStartKey")
        offset = start.get("offset", 0) if start else 0
        page = matches[offset:offset + limit]
        response = {"Items": page}
        if offset + limit < len(matches):
            response["LastEvaluatedKey"] = {"offset": offset + limit}
        return response

    def get_item(self, **kwargs):
        item = self._item(kwargs["Key"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        item = self._item(kwargs["Key"])
        if item is None:
            raise FakeClientError("ConditionalCheckFailedException")

        expression = kwargs["UpdateExpression"]
        values = kwargs.get("ExpressionAttributeValues", {})
        condition = kwargs.get("ConditionExpression")

        if condition and "deliveryClaimedAt = :now" in condition:
            if item.get("deliveryClaimedAt") != values.get(":now"):
                raise FakeClientError("ConditionalCheckFailedException")
        if condition and "#status = :pending" in condition:
            if item.get("status") != "PENDING":
                raise FakeClientError("ConditionalCheckFailedException")
            if item.get("deliveryState") == "sent":
                raise FakeClientError("ConditionalCheckFailedException")
            claimed = item.get("deliveryClaimedAt")
            if claimed is not None and claimed >= values.get(":leaseExpiry", ""):
                raise FakeClientError("ConditionalCheckFailedException")

        if expression.startswith("SET deliveryState = :sending"):
            item["deliveryState"] = values[":sending"]
            item["deliveryClaimedAt"] = values[":now"]
            item["lastDeliveryAt"] = values[":now"]
            item["deliveryAttempts"] = item.get("deliveryAttempts", 0) + 1
        elif expression.startswith("SET deliveryState = :sent"):
            if self.sent_mark_fails:
                raise RuntimeError("mark sent failed")
            item["deliveryState"] = values[":sent"]
            item["lastDeliveryAt"] = values[":now"]
            item.pop("deliveryClaimedAt", None)
        elif expression.startswith("SET deliveryState = :failed"):
            item["deliveryState"] = values[":failed"]
            item["lastDeliveryAt"] = values[":now"]
            item.pop("deliveryClaimedAt", None)
        else:
            raise AssertionError(f"unexpected update expression: {expression}")
        return {}


def order(order_id, *, created=None, status="PENDING", **extra):
    created = created or iso(NOW - timedelta(minutes=5))
    item = {
        "pk": f"ord_{order_id}",
        "sk": "#ORDER",
        "orderId": order_id,
        "status": status,
        "createdAt": created,
        "gsi1pk": "LIST",
        "gsi1sk": created,
        "version": 1,
    }
    item.update(extra)
    return item


def sender(fail_for=(), calls=None):
    def _send(order_id):
        if calls is not None:
            calls.append(order_id)
        if order_id in fail_for:
            raise RuntimeError("SQS down")
    return _send


class TestRecoveryHappyPath(unittest.TestCase):
    def test_stuck_pending_order_is_redelivered(self):
        table = FakeTable([order("ord_1")])
        calls = []
        report = run_recovery(table, sender(calls=calls), now=NOW)

        self.assertEqual(report["candidates"], 1)
        self.assertEqual(report["claimed"], 1)
        self.assertEqual(report["sent"], 1)
        self.assertEqual(calls, ["ord_1"])
        self.assertEqual(table.items["ord_ord_1"]["deliveryState"], "sent")
        self.assertEqual(table.items["ord_ord_1"]["deliveryAttempts"], 1)
        self.assertNotIn("deliveryClaimedAt", table.items["ord_ord_1"])

    def test_legacy_order_without_delivery_attributes_is_recovered(self):
        table = FakeTable([order("ord_legacy")])
        report = run_recovery(table, sender(), now=NOW)
        self.assertEqual(report["sent"], 1)
        self.assertEqual(table.items["ord_ord_legacy"]["deliveryState"], "sent")

    def test_failed_delivery_is_retried_on_next_run(self):
        table = FakeTable([order("ord_1")])
        first = run_recovery(table, sender(fail_for={"ord_1"}), now=NOW)
        self.assertEqual(first["failed"], 1)
        self.assertEqual(table.items["ord_ord_1"]["deliveryState"], "failed")

        second = run_recovery(table, sender(), now=NOW + timedelta(minutes=6))
        self.assertEqual(second["sent"], 1)
        self.assertEqual(table.items["ord_ord_1"]["deliveryState"], "sent")

    def test_already_delivered_order_is_not_requeued(self):
        table = FakeTable([order("ord_1", deliveryState="sent")])
        calls = []
        report = run_recovery(table, sender(calls=calls), now=NOW)
        self.assertEqual(calls, [])
        self.assertEqual(report["skipped"].get("already_sent"), 1)

    def test_non_pending_orders_are_skipped(self):
        table = FakeTable([order("ord_confirmed", status="CONFIRMED"),
                           order("ord_cancelled", status="CANCELLED")])
        calls = []
        report = run_recovery(table, sender(calls=calls), now=NOW)
        self.assertEqual(calls, [])
        self.assertEqual(report["skipped"].get("not_pending"), 2)

    def test_ownership_attributes_are_untouched(self):
        table = FakeTable([order("ord_1", subjectId="user-1", consumerId="c1",
                                 ownerType="user", ownerId="user-1",
                                 actorType="user", actorId="user-1",
                                 identityVersion=1, identityVerification="verified_jwt")])
        run_recovery(table, sender(), now=NOW)
        item = table.items["ord_ord_1"]
        self.assertEqual(item["subjectId"], "user-1")
        self.assertEqual(item["consumerId"], "c1")
        self.assertEqual(item["identityVerification"], "verified_jwt")
        self.assertEqual(item["version"], 1)


class TestRecoveryConcurrency(unittest.TestCase):
    def test_active_lease_blocks_second_runner(self):
        table = FakeTable([order("ord_1", deliveryState="sending",
                                 deliveryClaimedAt=iso(NOW - timedelta(seconds=10)))])
        calls = []
        report = run_recovery(table, sender(calls=calls), now=NOW, lease_seconds=300)
        self.assertEqual(calls, [])
        self.assertEqual(report["skipped"].get("claimed_or_changed"), 1)

    def test_expired_lease_allows_retry(self):
        table = FakeTable([order("ord_1", deliveryState="sending",
                                 deliveryClaimedAt=iso(NOW - timedelta(seconds=600)))])
        report = run_recovery(table, sender(), now=NOW, lease_seconds=300)
        self.assertEqual(report["sent"], 1)

    def test_two_sequential_runs_send_only_once(self):
        table = FakeTable([order("ord_1")])
        calls = []
        run_recovery(table, sender(calls=calls), now=NOW)
        second = run_recovery(table, sender(calls=calls), now=NOW + timedelta(minutes=5))
        self.assertEqual(calls, ["ord_1"])
        self.assertEqual(second["sent"], 0)
        self.assertEqual(second["skipped"].get("already_sent"), 1)

    def test_crash_after_send_leaves_uncertain_state(self):
        """Send ok, aber Bestaetigung nicht schreibbar -> uncertain, kein Doppel-Send im selben Lauf."""
        table = FakeTable([order("ord_1")], sent_mark_fails=True)
        calls = []
        report = run_recovery(table, sender(calls=calls), now=NOW)
        self.assertEqual(report["sent"], 1)
        self.assertEqual(report["uncertain"], 1)
        self.assertEqual(calls, ["ord_1"])
        # Lease bleibt stehen -> naechster Lauf darf erst nach Ablauf erneut senden
        self.assertEqual(table.items["ord_ord_1"]["deliveryState"], "sending")
        second = run_recovery(table, sender(calls=calls), now=NOW + timedelta(minutes=6))
        self.assertEqual(second["sent"], 1)
        self.assertEqual(calls, ["ord_1", "ord_1"])


class TestRecoveryScopeAndLimits(unittest.TestCase):
    def test_young_orders_are_skipped(self):
        table = FakeTable([order("ord_young", created=iso(NOW - timedelta(seconds=5)))])
        calls = []
        report = run_recovery(table, sender(calls=calls), now=NOW, min_age_seconds=60)
        self.assertEqual(calls, [])
        self.assertEqual(report["skipped"].get("too_young"), 1)

    def test_pagination_across_pages(self):
        items = [order(f"ord_{i}", created=iso(NOW - timedelta(minutes=10 - i)))
                 for i in range(5)]
        table = FakeTable(items)
        calls = []
        report = run_recovery(table, sender(calls=calls), now=NOW, limit=50)
        self.assertEqual(report["scanned"], 5)
        self.assertEqual(len(calls), 5)

    def test_limit_bounds_the_run(self):
        items = [order(f"ord_{i}", created=iso(NOW - timedelta(minutes=10 - i)))
                 for i in range(5)]
        table = FakeTable(items)
        calls = []
        report = run_recovery(table, sender(calls=calls), now=NOW, limit=2)
        self.assertEqual(report["candidates"], 2)
        self.assertEqual(len(calls), 2)

    def test_window_excludes_old_orders(self):
        table = FakeTable([order("ord_old", created=iso(NOW - timedelta(hours=3)))])
        report = run_recovery(table, sender(), now=NOW, window_minutes=60)
        self.assertEqual(report["scanned"], 0)

    def test_invalid_options_fall_back_to_defaults(self):
        table = FakeTable([])
        report = run_recovery(table, sender(), now=NOW, window_minutes="abc", limit=None)
        self.assertEqual(report["windowMinutes"], 60)
        self.assertEqual(report["limit"], 50)


if __name__ == "__main__":
    unittest.main()
