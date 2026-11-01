"""MO-RC4-P02C — Worker-Kollisionsschutz und Batch-Fehlerbehandlung."""

import json
import os
import unittest
from unittest import mock

import sqs_handler

os.environ.setdefault("ORDERS_TABLE", "mays-orders")

ORDER_ID = "ord_2f4b1c9e0000000000000000"


class FakeClientError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def make_item(status="PENDING", version=None, **extra):
    item = {
        "pk": {"S": f"ord_{ORDER_ID}"},
        "sk": {"S": "#ORDER"},
        "status": {"S": status},
    }
    if version is not None:
        item["version"] = {"N": str(version)}
    item.update(extra)
    return item


class FakeDynamo:
    """Minimaler DynamoDB-Client: get_item/update_item mit Condition-Semantik."""

    def __init__(self, item, *, conflict=False, conflict_item=None, error=None):
        self.item = item
        self.conflict = conflict
        self.conflict_item = conflict_item  # Zustand beim erneuten Lesen
        self.error = error
        self.updates = []
        self.reads = 0

    def get_item(self, **kwargs):
        self.reads += 1
        if self.reads > 1 and self.conflict_item is not None:
            return {"Item": self.conflict_item} if self.conflict_item else {}
        return {"Item": self.item} if self.item else {}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.conflict:
            raise FakeClientError("ConditionalCheckFailedException")
        # Erfolgreiches Update simulieren
        new_status = kwargs["ExpressionAttributeValues"][":newStatus"]["S"]
        self.item = dict(self.item, status={"S": new_status},
                         version={"N": str(int(self.item.get("version", {"N": "0"})["N"]) + 1)})
        return {}


def run_process(client, status="CONFIRMED"):
    with mock.patch.object(sqs_handler, "_get_dynamodb_client", return_value=client), \
         mock.patch.dict("sqs_handler.os.environ", {"ORDERS_TABLE": "mays-orders"}):
        return sqs_handler._process_order(ORDER_ID, status, {})


class TestProcessOrderCollisionSafety(unittest.TestCase):
    def test_successful_transition_uses_condition_and_version(self):
        client = FakeDynamo(make_item("PENDING", version=1))
        outcome = run_process(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSED)
        self.assertEqual(len(client.updates), 1)
        update = client.updates[0]
        self.assertIn("attribute_exists(pk)", update["ConditionExpression"])
        self.assertIn("#status = :currentStatus", update["ConditionExpression"])
        self.assertEqual(update["ExpressionAttributeValues"][":currentStatus"]["S"], "PENDING")
        self.assertIn("if_not_exists(#version, :zero) + :one", update["UpdateExpression"])
        self.assertEqual(client.item["status"]["S"], "CONFIRMED")
        self.assertEqual(client.item["version"]["N"], "2")

    def test_two_concurrent_workers_only_one_writes(self):
        client = FakeDynamo(make_item("PENDING", version=1), conflict=True,
                            conflict_item=make_item("CONFIRMED", version=2))
        outcome = run_process(client)
        # Der Verlierer schreibt nicht und gilt als idempotent abgeschlossen
        self.assertEqual(outcome, sqs_handler.OUTCOME_NOOP)
        self.assertEqual(len(client.updates), 1)

    def test_storno_between_read_and_write_is_not_overwritten(self):
        client = FakeDynamo(make_item("PENDING", version=1), conflict=True,
                            conflict_item=make_item("CANCELLED", version=2))
        outcome = run_process(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_REJECTED)
        self.assertEqual(client.item["status"]["S"], "PENDING")  # unverändert

    def test_duplicate_message_is_idempotent(self):
        client = FakeDynamo(make_item("CONFIRMED", version=2))
        outcome = run_process(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_NOOP)
        self.assertEqual(client.updates, [])

    def test_stale_message_does_not_downgrade(self):
        client = FakeDynamo(make_item("PROCESSING", version=3))
        outcome = run_process(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_STALE)
        self.assertEqual(client.updates, [])

    def test_cancelled_order_is_rejected_without_write(self):
        client = FakeDynamo(make_item("CANCELLED", version=2))
        outcome = run_process(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_REJECTED)
        self.assertEqual(client.updates, [])

    def test_missing_order_is_reported(self):
        client = FakeDynamo(None)
        outcome = run_process(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_MISSING)
        self.assertEqual(client.updates, [])

    def test_legacy_order_without_version_is_supported(self):
        client = FakeDynamo(make_item("PENDING"))  # kein version-Attribut
        outcome = run_process(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSED)
        update = client.updates[0]
        self.assertIn("if_not_exists(#version, :zero)", update["UpdateExpression"])
        self.assertEqual(client.item["version"]["N"], "1")

    def test_owner_attributes_are_never_touched(self):
        client = FakeDynamo(make_item("PENDING", version=1, subjectId={"S": "user-1"},
                                      consumerId={"S": "cognito:iss#client"}))
        run_process(client)
        update = client.updates[0]
        for field in ("subjectId", "consumerId", "ownerId", "actorId",
                      "identityVersion", "identityVerification"):
            self.assertNotIn(field, update["UpdateExpression"])
            self.assertNotIn(field, update.get("ExpressionAttributeNames", {}).values())

    def test_technical_error_propagates(self):
        client = FakeDynamo(make_item("PENDING"), error=RuntimeError("ddb down"))
        with self.assertRaises(RuntimeError):
            run_process(client)


class TestHandlerBatchFailures(unittest.TestCase):
    def _record(self, message_id, order_id="ord_1", status="CONFIRMED", body=None):
        payload = body if body is not None else json.dumps({"orderId": order_id, "status": status})
        return {"messageId": message_id, "body": payload}

    def test_success_reports_no_failures(self):
        with mock.patch.object(sqs_handler, "_process_order",
                               return_value=sqs_handler.OUTCOME_PROCESSED):
            response = sqs_handler.handler({"Records": [self._record("m1")]}, None)
        self.assertEqual(response["batchItemFailures"], [])

    def test_idempotent_and_stale_count_as_success(self):
        with mock.patch.object(sqs_handler, "_process_order",
                               side_effect=[sqs_handler.OUTCOME_NOOP, sqs_handler.OUTCOME_STALE]):
            response = sqs_handler.handler(
                {"Records": [self._record("m1"), self._record("m2")]}, None
            )
        self.assertEqual(response["batchItemFailures"], [])

    def test_permanent_failure_is_reported_for_that_message_only(self):
        with mock.patch.object(sqs_handler, "_process_order",
                               side_effect=[sqs_handler.OUTCOME_PROCESSED,
                                            sqs_handler.OUTCOME_REJECTED,
                                            sqs_handler.OUTCOME_PROCESSED]):
            response = sqs_handler.handler(
                {"Records": [self._record("m1"), self._record("m2"), self._record("m3")]}, None
            )
        self.assertEqual(response["batchItemFailures"], [{"itemIdentifier": "m2"}])

    def test_malformed_message_is_reported(self):
        response = sqs_handler.handler(
            {"Records": [self._record("bad", body="not-json")]}, None
        )
        # parse failure -> kein _process_order-Aufruf nötig
        self.assertEqual(response["batchItemFailures"], [{"itemIdentifier": "bad"}])

    def test_incomplete_message_is_reported(self):
        response = sqs_handler.handler(
            {"Records": [self._record("m1", body=json.dumps({"status": "CONFIRMED"}))]}, None
        )
        self.assertEqual(response["batchItemFailures"], [{"itemIdentifier": "m1"}])

    def test_technical_exception_is_reported_for_retry(self):
        with mock.patch.object(sqs_handler, "_process_order", side_effect=RuntimeError("boom")):
            response = sqs_handler.handler({"Records": [self._record("m1")]}, None)
        self.assertEqual(response["batchItemFailures"], [{"itemIdentifier": "m1"}])

    def test_empty_batch(self):
        response = sqs_handler.handler({"Records": []}, None)
        self.assertEqual(response["batchItemFailures"], [])

    def test_missing_message_id_with_failure_raises_to_retry_batch(self):
        record = {"body": "not-json"}  # kein messageId
        with self.assertRaises(RuntimeError):
            sqs_handler.handler({"Records": [record]}, None)


if __name__ == "__main__":
    unittest.main()
