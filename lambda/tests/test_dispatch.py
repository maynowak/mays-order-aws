"""A05 — dispatch binding, send state and recovery (Orders side)."""

import json
import os
import unittest

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

from dispatch import DispatchRejected, build_dispatch_envelope  # noqa: E402
from errors import OrderError  # noqa: E402
from identity import OwnerIdentity  # noqa: E402
from order_service import OrderService  # noqa: E402

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_P"
ALICE = OwnerIdentity(issuer=ISSUER, subject="alice", client_id="client-a")
BOB = OwnerIdentity(issuer=ISSUER, subject="bob", client_id="client-a")

AGENT = {
    "orderType": "agent.execution",
    "agentOrder": {
        "schemaVersion": "1.0",
        "target": {"agentId": "addition_agent", "capability": "math.add"},
        "input": {"data": {"left": 17, "right": 25}},
        "metadata": {"source": "ris-agent-ecosystem", "requestId": "req-001",
                     "apiProfileRef": "ctx-a", "idempotencyKey": "idem-1"},
    },
}


class ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class Table:
    def __init__(self):
        self.items = {}

    def put_item(self, **kwargs):
        self.items[kwargs["Item"]["orderId"]] = dict(kwargs["Item"])

    def get_item(self, Key):
        order_id = Key["pk"][len("ord_"):]
        item = self.items.get(order_id)
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, **kwargs):
        order_id = Key["pk"][len("ord_"):]
        item = self.items[order_id]
        values = ExpressionAttributeValues or {}
        if ConditionExpression:
            if ("attribute_not_exists(expectedWorkId)" in ConditionExpression
                    and "expectedWorkId" in item):
                raise ConditionalFailed()
            if ("expectedWorkId = :w" in ConditionExpression
                    and item.get("expectedWorkId") != values.get(":w")):
                raise ConditionalFailed()
        if ":w" in values:
            item["expectedWorkId"] = values[":w"]
        if ":d" in values:
            item["dispatch"] = values[":d"]
        return {"Attributes": dict(item)}


class TestDispatchBinding(unittest.TestCase):
    def setUp(self):
        self.table = Table()
        self.service = OrderService("t", client=self.table)
        self.order_id = self.service.create_order(AGENT, ALICE)["orderId"]

    def test_dispatch_binds_exactly_one_work_id(self):
        first = self.service.prepare_dispatch(self.order_id, ALICE)
        second = self.service.prepare_dispatch(self.order_id, ALICE)
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["workId"], second["workId"])
        self.assertEqual(first["workId"],
                         self.table.items[self.order_id]["expectedWorkId"])

    def test_crash_before_send_keeps_the_bound_id(self):
        bound = self.service.prepare_dispatch(self.order_id, ALICE)
        # no mark_dispatch_sent: simulates a crash between bind and send
        self.assertEqual("PENDING",
                         self.table.items[self.order_id]["dispatch"]["status"])
        retry = self.service.prepare_dispatch(self.order_id, ALICE)
        self.assertEqual(bound["workId"], retry["workId"])
        self.assertEqual("PENDING", retry["dispatchStatus"])

    def test_retry_after_send_reuses_the_id(self):
        bound = self.service.prepare_dispatch(self.order_id, ALICE)
        self.service.mark_dispatch_sent(self.order_id, bound["workId"], "m-1")
        retry = self.service.prepare_dispatch(self.order_id, ALICE)
        self.assertEqual(bound["workId"], retry["workId"])
        self.assertEqual("SENT", retry["dispatchStatus"])

    def test_completed_order_is_not_rebound(self):
        bound = self.service.prepare_dispatch(self.order_id, ALICE)
        self.table.items[self.order_id]["processing"] = {
            "schemaVersion": "1.0", "status": "COMPLETED", "attempt": 1}
        retry = self.service.prepare_dispatch(self.order_id, ALICE)
        self.assertEqual(bound["workId"], retry["workId"])

    def test_cancelled_order_is_rejected(self):
        self.table.items[self.order_id]["status"] = "CANCELLED"
        with self.assertRaises(DispatchRejected) as ctx:
            self.service.prepare_dispatch(self.order_id, ALICE)
        self.assertEqual("order_cancelled", ctx.exception.code)

    def test_foreign_owner_is_rejected_like_missing(self):
        with self.assertRaises(OrderError) as ctx:
            self.service.prepare_dispatch(self.order_id, BOB)
        self.assertEqual(404, ctx.exception.http_status)

    def test_tampered_definition_is_rejected(self):
        self.table.items[self.order_id]["agentOrder"]["target"]["capability"] = "math.divide"
        with self.assertRaises(DispatchRejected) as ctx:
            self.service.prepare_dispatch(self.order_id, ALICE)
        self.assertEqual("fingerprint_mismatch", ctx.exception.code)

    def test_missing_fingerprint_is_rejected(self):
        self.table.items[self.order_id].pop("agentOrderFingerprint")
        with self.assertRaises(DispatchRejected) as ctx:
            self.service.prepare_dispatch(self.order_id, ALICE)
        self.assertEqual("fingerprint_missing", ctx.exception.code)

    def test_retail_order_is_not_dispatchable(self):
        retail = self.service.create_order({
            "customer": {"name": "Max", "email": "max@example.com"},
            "items": [{"sku": "S", "quantity": 1, "unitPrice": 100}],
            "currency": "EUR"}, ALICE)["orderId"]
        with self.assertRaises(DispatchRejected) as ctx:
            self.service.prepare_dispatch(retail, ALICE)
        self.assertEqual("not_agent_order", ctx.exception.code)


class TestDispatchEnvelope(unittest.TestCase):
    def setUp(self):
        self.table = Table()
        self.service = OrderService("t", client=self.table)
        self.order_id = self.service.create_order(AGENT, ALICE)["orderId"]
        self.bound = self.service.prepare_dispatch(self.order_id, ALICE)
        self.envelope = self.service.dispatch_envelope(
            self.order_id, self.bound["workId"])

    def test_envelope_carries_the_bound_work_id(self):
        self.assertEqual("ORDER_DISPATCH", self.envelope["messageType"])
        self.assertEqual(self.bound["workId"],
                         self.envelope["execution"]["workId"])

    def test_envelope_is_built_from_the_stored_order(self):
        self.assertEqual(self.order_id, self.envelope["orderId"])
        self.assertEqual("req-001", self.envelope["correlationId"])
        self.assertEqual({"left": 17, "right": 25}, self.envelope["payload"])
        self.assertEqual("math.add",
                         self.envelope["recipient"]["capability"])

    def test_envelope_contains_no_secrets(self):
        serialized = json.dumps(self.envelope)
        self.assertNotIn("ris_", serialized)
        self.assertNotIn("Bearer", serialized)
        self.assertNotIn("ownerKey", serialized)

    def test_wrong_work_id_cannot_build_an_envelope(self):
        with self.assertRaises(DispatchRejected) as ctx:
            self.service.dispatch_envelope(self.order_id, "work-other")
        self.assertEqual("work_mismatch", ctx.exception.code)

    def test_missing_identity_reference_blocks_dispatch(self):
        item = self.table.items[self.order_id]
        item["agentOrder"]["metadata"].pop("apiProfileRef")
        # fingerprint is recomputed over target+input only, so it stays valid
        with self.assertRaises(DispatchRejected) as ctx:
            build_dispatch_envelope(item, self.bound["workId"])
        self.assertEqual("missing_identity_reference", ctx.exception.code)

    def test_missing_correlation_blocks_dispatch(self):
        item = self.table.items[self.order_id]
        item["agentOrder"]["metadata"].pop("requestId")
        with self.assertRaises(DispatchRejected) as ctx:
            build_dispatch_envelope(item, self.bound["workId"])
        self.assertEqual("missing_correlation", ctx.exception.code)


class TestSendState(unittest.TestCase):
    def setUp(self):
        self.table = Table()
        self.service = OrderService("t", client=self.table)
        self.order_id = self.service.create_order(AGENT, ALICE)["orderId"]
        self.bound = self.service.prepare_dispatch(self.order_id, ALICE)

    def test_mark_sent_is_idempotent_for_the_same_message(self):
        first = self.service.mark_dispatch_sent(
            self.order_id, self.bound["workId"], "m-1")
        second = self.service.mark_dispatch_sent(
            self.order_id, self.bound["workId"], "m-1")
        self.assertEqual(first["messageId"], second["messageId"])
        self.assertEqual("SENT", self.table.items[self.order_id]["dispatch"]["status"])

    def test_different_message_after_send_is_a_conflict(self):
        self.service.mark_dispatch_sent(self.order_id, self.bound["workId"], "m-1")
        with self.assertRaises(DispatchRejected) as ctx:
            self.service.mark_dispatch_sent(
                self.order_id, self.bound["workId"], "m-2")
        self.assertEqual("dispatch_conflict", ctx.exception.code)

    def test_send_state_is_not_public(self):
        self.service.mark_dispatch_sent(self.order_id, self.bound["workId"], "m-1")
        order = self.service.get_order(self.order_id, ALICE)
        self.assertNotIn("dispatch", order)
        self.assertNotIn("expectedWorkId", order)


if __name__ == "__main__":
    unittest.main()
