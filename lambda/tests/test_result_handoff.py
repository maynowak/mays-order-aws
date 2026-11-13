"""A06 — internal result handoff: contract, boundary, ingestion, projection.

Local only: SQS is simulated by plain dicts, no AWS call.
"""

import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

from errors import OrderError  # noqa: E402
from identity import OwnerIdentity  # noqa: E402
from order_service import OrderService, to_public_processing  # noqa: E402
from result_envelope import (  # noqa: E402
    ResultEnvelopeError,
    ResultRejected,
    sign,
    validate_result_envelope,
)
import result_handler  # noqa: E402

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_POOL"
CLIENT = "client-abc"
ALICE = OwnerIdentity(issuer=ISSUER, subject="alice", client_id=CLIENT)
BOB = OwnerIdentity(issuer=ISSUER, subject="bob", client_id=CLIENT)
SERVICE_SECRET = "result-service-secret"

AGENT = {
    "orderType": "agent.execution",
    "agentOrder": {
        "schemaVersion": "1.0",
        "target": {"agentId": "addition_agent", "capability": "math.add"},
        "input": {"data": {"left": 17, "right": 25}},
        "metadata": {"source": "ris-agent-ecosystem", "requestId": "req-001"},
    },
}


class ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, **kwargs):
        self.items[kwargs["Item"]["orderId"]] = dict(kwargs["Item"])
        return {}

    def get_item(self, Key):
        order_id = Key["pk"][len("ord_"):]
        item = self.items.get(order_id)
        return {"Item": dict(item)} if item else {}

    def query(self, **kwargs):
        return {"Items": []}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None, ExpressionAttributeValues=None,
                    **kwargs):
        order_id = Key["pk"][len("ord_"):]
        item = self.items[order_id]
        if ConditionExpression and "attribute_not_exists(#p)" in ConditionExpression:
            if "processing" in item:
                raise ConditionalFailed()
        values = ExpressionAttributeValues or {}
        if ":p" in values:
            item["processing"] = values[":p"]
        if ":newStatus" in values:
            item["status"] = values[":newStatus"]
        return {"Attributes": dict(item)}


def result_envelope(order_id="ord_test", **overrides):
    envelope = {
        "schemaVersion": "1",
        "messageId": "msg_result_1",
        "messageType": "ORDER_RESULT",
        "orderId": order_id,
        "correlationId": "req-001",
        "idempotencyKey": f"{order_id}:work-1:ORDER_RESULT",
        "sender": {"system": "ris", "reference": "ris-runtime"},
        "recipient": {"system": "mays-orders"},
        "payload": {"left": 17, "right": 25, "sum": 42},
        "createdAt": "2026-11-13T13:00:00+00:00",
        "execution": {"workId": "work-1", "attempt": 1,
                      "executionId": "exec-1"},
    }
    envelope.update(overrides)
    return envelope


class Harness(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.service = OrderService("t", client=self.table)
        self.order_id = self.service.create_order(AGENT, ALICE)["orderId"]

    def env(self, **overrides):
        return result_envelope(self.order_id, **overrides)


class TestResultContract(unittest.TestCase):
    def test_valid_result_envelope_is_accepted(self):
        parsed = validate_result_envelope(result_envelope())
        self.assertEqual("ORDER_RESULT", parsed["messageType"])

    def test_valid_failed_envelope_is_accepted(self):
        parsed = validate_result_envelope(result_envelope(
            messageType="ORDER_FAILED",
            payload={"error": {"message": "agent failed"}}))
        self.assertEqual("ORDER_FAILED", parsed["messageType"])

    def test_unknown_version_is_rejected(self):
        with self.assertRaises(ResultEnvelopeError) as ctx:
            validate_result_envelope(result_envelope(schemaVersion="2"))
        self.assertEqual("unsupported_schema_version", ctx.exception.code)

    def test_dispatch_type_is_not_a_result(self):
        with self.assertRaises(ResultEnvelopeError) as ctx:
            validate_result_envelope(result_envelope(messageType="ORDER_DISPATCH"))
        self.assertEqual("unknown_message_type", ctx.exception.code)

    def test_wrong_sender_system_is_rejected(self):
        with self.assertRaises(ResultEnvelopeError) as ctx:
            validate_result_envelope(result_envelope(
                sender={"system": "mays-orders"}))
        self.assertEqual("wrong_sender_system", ctx.exception.code)

    def test_manipulated_payload_with_secret_is_rejected(self):
        with self.assertRaises(ResultEnvelopeError) as ctx:
            validate_result_envelope(result_envelope(
                payload={"sum": 42, "api_key": "ris_" + "A" * 47}))
        self.assertEqual("secret_in_result", ctx.exception.code)

    def test_invalid_payload_type_is_rejected(self):
        with self.assertRaises(ResultEnvelopeError):
            validate_result_envelope(result_envelope(payload="42"))

    def test_oversized_payload_is_rejected(self):
        with self.assertRaises(ResultEnvelopeError) as ctx:
            validate_result_envelope(result_envelope(
                payload={"blob": "x" * (17 * 1024)}))
        self.assertEqual("payload_too_large", ctx.exception.code)

    def test_missing_order_id_is_rejected(self):
        envelope = result_envelope()
        envelope.pop("orderId")
        with self.assertRaises(ResultEnvelopeError) as ctx:
            validate_result_envelope(envelope)
        self.assertEqual("missing_field", ctx.exception.code)


class TestResultIngestion(Harness):
    def test_valid_result_is_stored_once(self):
        record = self.service.apply_result(validate_result_envelope(self.env()))
        self.assertEqual("COMPLETED", record["status"])
        self.assertEqual(42, record["result"]["sum"])
        self.assertEqual("COMPLETED", self.table.items[self.order_id]["processing"]["status"])

    def test_failed_result_is_stored_as_failure(self):
        record = self.service.apply_result(validate_result_envelope(self.env(
            messageType="ORDER_FAILED",
            payload={"error": {"message": "agent failed"}})))
        self.assertEqual("FAILED", record["status"])
        self.assertEqual("agent failed", record["error"]["message"])
        self.assertNotIn("result", record)

    def test_duplicate_delivery_is_idempotent(self):
        first = self.service.apply_result(validate_result_envelope(self.env()))
        second = self.service.apply_result(validate_result_envelope(self.env()))
        self.assertEqual(first["idempotencyKey"], second["idempotencyKey"])
        self.assertEqual(1, len(self.table.items))

    def test_different_result_after_completion_is_rejected(self):
        self.service.apply_result(validate_result_envelope(self.env()))
        with self.assertRaises(ResultRejected) as ctx:
            self.service.apply_result(validate_result_envelope(self.env(
                idempotencyKey="other")))
        self.assertEqual("already_finalised", ctx.exception.code)

    def test_unknown_order_is_rejected(self):
        with self.assertRaises(OrderError) as ctx:
            self.service.apply_result(validate_result_envelope(
                result_envelope("ord_unknown")))
        self.assertEqual(404, ctx.exception.http_status)

    def test_retail_order_rejects_a_result(self):
        retail = {"customer": {"name": "Max", "email": "max@example.com"},
                  "items": [{"sku": "S", "quantity": 1, "unitPrice": 100}],
                  "currency": "EUR"}
        retail_id = self.service.create_order(retail, ALICE)["orderId"]
        with self.assertRaises(ResultRejected) as ctx:
            self.service.apply_result(validate_result_envelope(
                result_envelope(retail_id, correlationId="req-001")))
        self.assertEqual("not_agent_order", ctx.exception.code)

    def test_false_correlation_is_rejected(self):
        with self.assertRaises(ResultRejected) as ctx:
            self.service.apply_result(validate_result_envelope(self.env(
                correlationId="req-other")))
        self.assertEqual("correlation_mismatch", ctx.exception.code)

    def test_false_work_id_is_rejected_when_dispatch_recorded_one(self):
        self.table.items[self.order_id]["expectedWorkId"] = "work-1"
        with self.assertRaises(ResultRejected) as ctx:
            self.service.apply_result(validate_result_envelope(self.env(
                execution={"workId": "work-OTHER", "attempt": 1})))
        self.assertEqual("work_mismatch", ctx.exception.code)

    def test_execution_mismatch_on_duplicate_is_rejected(self):
        self.service.apply_result(validate_result_envelope(self.env()))
        with self.assertRaises(ResultRejected) as ctx:
            self.service.apply_result(validate_result_envelope(self.env(
                execution={"workId": "work-1", "attempt": 1,
                           "executionId": "exec-OTHER"})))
        self.assertEqual("execution_mismatch", ctx.exception.code)

    def test_stale_attempt_is_rejected(self):
        self.table.items[self.order_id]["processing"] = {
            "schemaVersion": "1.0", "status": "RUNNING", "attempt": 5}
        with self.assertRaises(ResultRejected) as ctx:
            self.service.apply_result(validate_result_envelope(self.env(
                execution={"workId": "work-1", "attempt": 3})))
        self.assertEqual("stale_attempt", ctx.exception.code)

    def test_cancelled_order_is_rejected(self):
        self.table.items[self.order_id]["status"] = "CANCELLED"
        with self.assertRaises(ResultRejected) as ctx:
            self.service.apply_result(validate_result_envelope(self.env()))
        self.assertEqual("order_cancelled", ctx.exception.code)

    def test_order_without_correlation_is_rejected(self):
        self.table.items[self.order_id]["agentOrder"]["metadata"].pop("requestId")
        with self.assertRaises(ResultRejected) as ctx:
            self.service.apply_result(validate_result_envelope(self.env()))
        self.assertEqual("missing_correlation", ctx.exception.code)


class TestConsumerBoundary(Harness):
    def setUp(self):
        super().setUp()
        self.env_vars = patch.dict(os.environ, {
            "ORDERS_TABLE": "t",
            "ORDER_RESULT_SERVICE_SECRET": SERVICE_SECRET,
        })
        self.env_vars.start()
        self.patch = patch.object(
            result_handler, "create_order_service", return_value=self.service)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.env_vars.stop()

    def _record(self, envelope, *, signature=None, message_id="msg-1"):
        body = json.dumps(envelope)
        return {
            "messageId": message_id,
            "body": body,
            "messageAttributes": {
                "serviceSignature": {
                    "stringValue": signature if signature is not None
                    else sign(SERVICE_SECRET, message_id, body)}},
        }

    def test_valid_signed_message_is_processed(self):
        response = result_handler.handler(
            {"Records": [self._record(self.env())]}, None)
        self.assertEqual({"processed": 1, "rejected": 0},
                         json.loads(response["body"]))
        self.assertEqual("COMPLETED",
                         self.table.items[self.order_id]["processing"]["status"])

    def test_missing_signature_is_rejected_without_write(self):
        response = result_handler.handler(
            {"Records": [self._record(self.env(), signature="")]}, None)
        self.assertEqual(1, json.loads(response["body"])["rejected"])
        self.assertNotIn("processing", self.table.items[self.order_id])

    def test_tampered_body_invalidates_the_signature(self):
        record = self._record(self.env())
        record["body"] = json.dumps(self.env(payload={"sum": 999}))
        response = result_handler.handler({"Records": [record]}, None)
        self.assertEqual(1, json.loads(response["body"])["rejected"])
        self.assertNotIn("processing", self.table.items[self.order_id])

    def test_missing_service_secret_rejects_everything(self):
        with patch.dict(os.environ, {"ORDER_RESULT_SERVICE_SECRET": ""}):
            response = result_handler.handler(
                {"Records": [self._record(self.env())]}, None)
        self.assertEqual(0, json.loads(response["body"])["processed"])
        self.assertNotIn("processing", self.table.items[self.order_id])

    def test_rejected_message_does_not_leak_secrets(self):
        response = result_handler.handler(
            {"Records": [self._record(self.env(), signature="forged")]}, None)
        self.assertNotIn(SERVICE_SECRET, response["body"])


class TestResultProjection(Harness):
    def test_owner_reads_the_result(self):
        self.service.apply_result(validate_result_envelope(self.env()))
        order = self.service.get_order(self.order_id, ALICE)
        self.assertEqual("COMPLETED", order["processing"]["status"])
        self.assertEqual(42, order["processing"]["result"]["sum"])

    def test_foreign_owner_gets_404(self):
        self.service.apply_result(validate_result_envelope(self.env()))
        with self.assertRaises(OrderError) as ctx:
            self.service.get_order(self.order_id, BOB)
        self.assertEqual(404, ctx.exception.http_status)

    def test_projection_withholds_internal_correlation(self):
        self.service.apply_result(validate_result_envelope(self.env()))
        processing = self.service.get_order(self.order_id, ALICE)["processing"]
        for internal in ("workId", "messageId", "idempotencyKey",
                         "executionId"):
            self.assertNotIn(internal, processing)
        self.assertEqual({"status", "attempt", "completedAt", "result"},
                         set(processing))

    def test_failed_projection_exposes_a_sanitised_error(self):
        self.service.apply_result(validate_result_envelope(self.env(
            messageType="ORDER_FAILED",
            payload={"error": {"message": "agent failed", "stack": "x"}})))
        error = self.service.get_order(self.order_id, ALICE)["processing"]["error"]
        self.assertEqual({"message": "agent failed"}, error)

    def test_projection_ignores_malformed_processing(self):
        self.assertEqual({}, to_public_processing("nope"))
        self.assertEqual({}, to_public_processing({}))


if __name__ == "__main__":
    unittest.main()
