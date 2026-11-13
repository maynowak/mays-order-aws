"""L02/L03 — result consumer Lambda entrypoint tests (Secrets Manager path)."""

import json
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

from identity import OwnerIdentity  # noqa: E402
from order_service import OrderService  # noqa: E402
from result_envelope import sign  # noqa: E402
import result_consumer  # noqa: E402
import result_handler  # noqa: E402

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_P"
ALICE = OwnerIdentity(issuer=ISSUER, subject="alice", client_id="client-a")
CURRENT = "current-key"
PREVIOUS = "previous-key"

AGENT = {
    "orderType": "agent.execution",
    "agentOrder": {
        "schemaVersion": "1.0",
        "target": {"agentId": "addition_agent", "capability": "math.add"},
        "input": {"data": {"left": 17, "right": 25}},
        "metadata": {"source": "ris", "requestId": "req-001"},
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

    def query(self, **kwargs):
        return {"Items": []}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, **kwargs):
        order_id = Key["pk"][len("ord_"):]
        item = self.items[order_id]
        values = ExpressionAttributeValues or {}
        if ConditionExpression and "attribute_not_exists(#p)" in ConditionExpression:
            if "processing" in item:
                raise ConditionalFailed()
        if ":p" in values:
            item["processing"] = values[":p"]
        return {"Attributes": dict(item)}


def result_envelope(**overrides):
    envelope = {
        "schemaVersion": "1",
        "messageId": "msg-result-1",
        "messageType": "ORDER_RESULT",
        "orderId": "ord_placeholder",
        "correlationId": "req-001",
        "idempotencyKey": "ord_placeholder:work-1:ORDER_RESULT",
        "sender": {"system": "ris", "reference": "ris-runtime"},
        "recipient": {"system": "mays-orders"},
        "payload": {"left": 17, "right": 25, "sum": 42},
        "createdAt": "2026-11-13T00:00:00+00:00",
        "execution": {"workId": "work-1", "attempt": 1},
    }
    envelope.update(overrides)
    return envelope


class ConsumerHarness(unittest.TestCase):
    def setUp(self):
        self.table = Table()
        self.service = OrderService("orders", client=self.table)
        self.order_id = self.service.create_order(AGENT, ALICE)["orderId"]
        self.env = patch.dict(os.environ, {
            "ORDERS_TABLE": "orders",
            "ORDER_RESULT_SECRET_ARN": "arn:aws:secretsmanager:eu-central-1:1:secret:x",
        })
        self.env.start()
        result_consumer.reset_cache()
        self.patches = [
            patch.object(result_consumer, "_fetch_secret",
                         return_value=[CURRENT, PREVIOUS]),
            patch.object(result_handler, "create_order_service",
                         return_value=self.service),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()
        result_consumer.reset_cache()

    def record(self, envelope, secret=CURRENT, message_id="m1"):
        body = json.dumps(envelope)
        return {"messageId": message_id, "body": body,
                "messageAttributes": {"serviceSignature": {
                    "stringValue": sign(secret, message_id, body)}}}

    def run_handler(self, *records):
        return result_consumer.handler({"Records": list(records)}, None)


class TestSecretHandling(ConsumerHarness):
    def test_valid_result_is_applied(self):
        response = self.run_handler(self.record(result_envelope(
            orderId=self.order_id)))
        self.assertEqual({"processed": 1, "rejected": 0},
                         json.loads(response["body"]))
        self.assertEqual("COMPLETED",
                         self.table.items[self.order_id]["processing"]["status"])

    def test_previous_key_is_accepted_during_rotation(self):
        self.run_handler(self.record(result_envelope(orderId=self.order_id),
                                     secret=PREVIOUS))
        self.assertIn("processing", self.table.items[self.order_id])

    def test_missing_secret_reference_fails_closed(self):
        with patch.dict(os.environ, {"ORDER_RESULT_SECRET_ARN": ""}):
            response = self.run_handler(self.record(result_envelope(
                orderId=self.order_id)))
        body = json.loads(response["body"])
        self.assertEqual(0, body["processed"])
        self.assertEqual("secret_reference_missing", body["reason"])
        self.assertNotIn("processing", self.table.items[self.order_id])

    def test_unavailable_secret_fails_closed(self):
        result_consumer.reset_cache()
        with patch.object(result_consumer, "_fetch_secret",
                          side_effect=result_consumer.SecretUnavailable("x")):
            response = self.run_handler(self.record(result_envelope(
                orderId=self.order_id)))
        body = json.loads(response["body"])
        self.assertEqual(0, body["processed"])
        self.assertEqual("secret_unavailable", body["reason"])

    def test_secret_value_is_never_returned(self):
        response = self.run_handler(self.record(result_envelope(
            orderId=self.order_id)))
        serialized = json.dumps(response)
        self.assertNotIn(CURRENT, serialized)
        self.assertNotIn(PREVIOUS, serialized)

    def test_parse_secret_supports_rotation_json(self):
        self.assertEqual([CURRENT, PREVIOUS],
                         result_consumer.parse_secret(
                             json.dumps({"current": CURRENT,
                                         "previous": PREVIOUS})))
        self.assertEqual([CURRENT], result_consumer.parse_secret(CURRENT))
        self.assertEqual([], result_consumer.parse_secret(""))


class TestRejections(ConsumerHarness):
    def _rejected(self, envelope, **kwargs):
        response = self.run_handler(self.record(envelope, **kwargs))
        self.assertEqual(1, json.loads(response["body"])["rejected"])

    def test_wrong_signature(self):
        self._rejected(result_envelope(orderId=self.order_id),
                       secret="forged-key")
        self.assertNotIn("processing", self.table.items[self.order_id])

    def test_unknown_version(self):
        self._rejected(result_envelope(orderId=self.order_id, schemaVersion="2"))

    def test_unknown_message_type(self):
        self._rejected(result_envelope(orderId=self.order_id,
                                       messageType="ORDER_DISPATCH"))

    def test_wrong_order(self):
        self._rejected(result_envelope(orderId="ord_other"))

    def test_cancelled_order(self):
        self.table.items[self.order_id]["status"] = "CANCELLED"
        self._rejected(result_envelope(orderId=self.order_id))
        self.assertNotIn("processing", self.table.items[self.order_id])

    def test_partial_batch(self):
        good = self.record(result_envelope(orderId=self.order_id), message_id="a")
        bad = self.record(result_envelope(orderId=self.order_id,
                                          schemaVersion="2"), message_id="b")
        body = json.loads(self.run_handler(bad, good)["body"])
        self.assertEqual({"processed": 1, "rejected": 1}, body)


if __name__ == "__main__":
    unittest.main()
