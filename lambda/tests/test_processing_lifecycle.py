"""MO-RC4-P02G-B — Processing-Lifecycle: Claim, Ergebnisübernahme, Fehler, Privacy-Race."""

import os
import unittest
from unittest import mock

import sqs_handler
from order_handlers import ProcessingFailure, register

os.environ.setdefault("ORDERS_TABLE", "mays-orders")

ORDER_ID = "ord_2f4b1c9e0000000000000000"
PK = f"ord_{ORDER_ID}"


class FakeClientError(Exception):
    def __init__(self, code="ConditionalCheckFailedException"):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def item(status="PENDING", *, version=1, subject=True, **extra):
    value = {
        "pk": {"S": PK},
        "sk": {"S": "#ORDER"},
        "status": {"S": status},
        "version": {"N": str(version)},
        "orderType": {"S": "test.processing"},
    }
    if subject:
        value["subjectId"] = {"S": "user-1"}
    value.update(extra)
    return value


class FakeDynamo:
    """Stub mit den Bedingungen des Processing-Lifecycles."""

    def __init__(self, order):
        self.item = order
        self.updates = []

    # -- intern --
    @staticmethod
    def _s(value):
        if not isinstance(value, dict):
            return value
        if "S" in value:
            return value["S"]
        if "N" in value:
            return value["N"]
        if "BOOL" in value:
            return value["BOOL"]
        return None

    def _condition_ok(self, condition, values):
        order = self.item
        if order is None:
            return False
        status = self._s(order.get("status"))

        if "attribute_exists(subjectId)" in condition and "subjectId" not in order:
            return False
        if "#status = :currentStatus" in condition:
            if status != values[":currentStatus"]["S"]:
                return False
        if "#status <> :cancelled" in condition and status == "CANCELLED":
            return False
        is_claim = "attribute_not_exists(processingState)" in condition
        if not is_claim and "processingState = :running" in condition:
            if self._s(order.get("processingState")) != "running":
                return False
        if not is_claim and "processingAttemptId = :attempt" in condition:
            if self._s(order.get("processingAttemptId")) != values[":attempt"]["S"]:
                return False
        if is_claim:
            state = self._s(order.get("processingState"))
            claimed = self._s(order.get("processingClaimedAt"))
            lease_ok = state == "running" and (
                claimed is None or claimed < values[":leaseExpiry"]["S"]
            )
            if not (state is None or state == "pending" or lease_ok):
                return False
        if "processingAttempts < :maxAttempts" in condition:
            attempts = int(self._s(order.get("processingAttempts")) or 0)
            if attempts >= int(values[":maxAttempts"]["N"]):
                return False
        if ":version" in values:
            current = self._s(order.get("version"))
            if current is not None and int(current) != int(values[":version"]["N"]):
                return False
        return True

    def _apply(self, expression, values):
        order = self.item
        if order is None:
            return
        if expression.startswith("SET processingState = :running"):
            order["processingState"] = {"S": "running"}
            order["processingAttemptId"] = {"S": values[":attempt"]["S"]}
            order["processingClaimedAt"] = {"S": values[":now"]["S"]}
            attempts = int(self._s(order.get("processingAttempts")) or 0)
            order["processingAttempts"] = {"N": str(attempts + 1)}
            return
        if expression.startswith("SET processingState = :succeeded"):
            order["processingState"] = {"S": "succeeded"}
            order["result"] = values[":result"]
            order["completedAt"] = {"S": values[":now"]["S"]}
            order["updatedAt"] = {"S": values[":now"]["S"]}
            order["version"] = {"N": str(int(self._s(order.get("version")) or 0) + 1)}
            order.pop("processingError", None)
            order.pop("processingClaimedAt", None)
            return
        if expression.startswith("SET processingState = :failed"):
            order["processingState"] = {"S": "failed"}
            order["processingError"] = values[":error"]
            order["completedAt"] = {"S": values[":now"]["S"]}
            order["updatedAt"] = {"S": values[":now"]["S"]}
            order["version"] = {"N": str(int(self._s(order.get("version")) or 0) + 1)}
            order.pop("result", None)
            order.pop("processingClaimedAt", None)
            return
        if expression.startswith("SET processingState = :pending"):
            order["processingState"] = {"S": "pending"}
            order.pop("processingClaimedAt", None)
            return
        if expression.startswith("SET #status = :newStatus"):
            order["status"] = {"S": values[":newStatus"]["S"]}
            order["version"] = {"N": str(int(self._s(order.get("version")) or 0) + 1)}
            return
        raise AssertionError(f"unexpected update: {expression}")

    # -- client API --
    def get_item(self, **kwargs):
        return {"Item": dict(self.item)} if self.item else {}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        if not self._condition_ok(kwargs["ConditionExpression"], kwargs["ExpressionAttributeValues"]):
            raise FakeClientError()
        self._apply(kwargs["UpdateExpression"], kwargs["ExpressionAttributeValues"])
        return {}


def run(client, status="CONFIRMED", payload=None):
    with mock.patch.object(sqs_handler, "_get_dynamodb_client", return_value=client), \
         mock.patch.dict("sqs_handler.os.environ", {"ORDERS_TABLE": "mays-orders"}):
        return sqs_handler._process_order(ORDER_ID, status, payload or {})


def processing_handler(behaviour=None):
    """Registriert einen frischen Processing-Handler (einmal pro Test)."""
    import uuid

    order_type = f"test.processing.t{uuid.uuid4().hex[:8]}"

    @register(order_type, processing=True)
    def _handler(order, payload, context):
        if behaviour is not None:
            return behaviour(order, payload, context)
        return {"result": {"processed": True}}

    return order_type


class TestProcessingClaim(unittest.TestCase):
    def test_successful_processing_sets_result_atomically(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SUCCEEDED)
        self.assertEqual(client.item["processingState"]["S"], "succeeded")
        self.assertEqual(client.item["result"], {"M": {"processed": {"BOOL": True}}})
        self.assertIn("completedAt", client.item)
        # Statuswechsel (1 -> 2) + Abschluss (+1) = 3
        self.assertEqual(client.item["version"]["N"], "3")
        self.assertNotIn("processingClaimedAt", client.item)

    def test_duplicate_message_after_success_is_idempotent(self):
        calls = []
        handler_type = processing_handler(lambda o, p, c: calls.append(1) or {"result": {"ok": True}})
        client = FakeDynamo(item(orderType={"S": handler_type}))

        run(client)
        second = run(client)

        self.assertEqual(second, sqs_handler.OUTCOME_NOOP)
        self.assertEqual(len(calls), 1)

    def test_active_claim_blocks_second_worker(self):
        calls = []
        handler_type = processing_handler(lambda o, p, c: calls.append(1) or {"result": {"ok": True}})
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "running"},
                                 processingAttemptId={"S": "other"},
                                 processingAttempts={"N": "1"},
                                 processingClaimedAt={"S": "9999-12-31T23:59:59.000Z"}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SKIPPED)
        self.assertEqual(calls, [])

    def test_expired_claim_can_be_retried(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "running"},
                                 processingAttemptId={"S": "old"},
                                 processingAttempts={"N": "1"},
                                 processingClaimedAt={"S": "2000-01-01T00:00:00.000Z"}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SUCCEEDED)
        self.assertEqual(client.item["processingAttempts"]["N"], "2")

    def test_cancelled_order_is_not_claimed(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome = run(client, status="CONFIRMED")  # Zielstatus
        # Order im Zustand CANCELLED: Statusuebergang wird abgelehnt
        cancelled = FakeDynamo(item(status="CANCELLED", orderType={"S": handler_type}))
        outcome = run(cancelled)
        self.assertEqual(outcome, sqs_handler.OUTCOME_REJECTED)
        self.assertEqual(cancelled.updates, [])

    def test_anonymized_order_is_rejected(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type}, subject=False))
        outcome = run(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_REJECTED)

    def test_terminal_failed_state_is_not_retried(self):
        calls = []
        handler_type = processing_handler(lambda o, p, c: calls.append(1) or {"result": {}})
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "failed"},
                                 processingAttempts={"N": "1"}))
        outcome = run(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SKIPPED)
        self.assertEqual(calls, [])

    def test_attempt_budget_limits_retries(self):
        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type},
                                 processingState={"S": "running"},
                                 processingAttemptId={"S": "old"},
                                 processingAttempts={"N": str(sqs_handler.MAX_PROCESSING_ATTEMPTS)},
                                 processingClaimedAt={"S": "2000-01-01T00:00:00.000Z"}))
        outcome = run(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SKIPPED)

    def test_legacy_item_without_version_can_be_claimed(self):
        handler_type = processing_handler()
        order = item(orderType={"S": handler_type})
        order.pop("version")
        client = FakeDynamo(order)
        outcome = run(client)
        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SUCCEEDED)
        # Statuswechsel (fehlend -> 1) + Abschluss (+1) = 2
        self.assertEqual(client.item["version"]["N"], "2")


class TestProcessingHandlerContract(unittest.TestCase):
    def test_business_failure_is_persisted_controlled(self):
        def fail(order, payload, context):
            raise ProcessingFailure("UPSTREAM_REJECTED", "upstream said no")

        handler_type = processing_handler(fail)
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_FAILED)
        self.assertEqual(client.item["processingState"]["S"], "failed")
        self.assertEqual(client.item["processingError"]["M"]["code"], {"S": "UPSTREAM_REJECTED"})
        self.assertEqual(client.item["processingError"]["M"]["message"], {"S": "upstream said no"})
        self.assertNotIn("result", client.item)
        self.assertIn("completedAt", client.item)

    def test_technical_error_releases_claim_and_retries(self):
        def boom(order, payload, context):
            raise RuntimeError("database flake")

        handler_type = processing_handler(boom)
        client = FakeDynamo(item(orderType={"S": handler_type}))
        with self.assertRaises(RuntimeError):
            run(client)

        self.assertEqual(client.item["processingState"]["S"], "pending")
        self.assertNotIn("processingClaimedAt", client.item)
        self.assertNotIn("result", client.item)

    def test_invalid_result_is_rejected_without_completion(self):
        handler_type = processing_handler(lambda o, p, c: {"blob": "x" * 20000})
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_HANDLER_FAILED)
        self.assertNotIn("result", client.item)
        self.assertEqual(client.item["processingState"]["S"], "pending")

    def test_generic_handler_keeps_status_only_behaviour(self):
        client = FakeDynamo(item(orderType={"S": "generic"}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSED)
        self.assertEqual(client.item["status"]["S"], "CONFIRMED")
        for field in ("processingState", "processingAttemptId", "result",
                      "completedAt", "processingError"):
            self.assertNotIn(field, client.item)


class TestProcessingPrivacyRace(unittest.TestCase):
    def _handler_that(self, action):
        def handler(order, payload, context):
            action()
            return {"result": {"processed": True}}
        return processing_handler(handler)

    def test_anonymize_during_processing_rejects_result(self):
        client = None

        def anonymize():
            client.item.pop("subjectId", None)
            client.item.pop("gsi2pk", None)

        handler_type = processing_handler(lambda o, p, c: (anonymize(), {"result": {"x": 1}})[1])
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_REJECTED)
        self.assertNotIn("result", client.item)
        self.assertEqual(client.item["processingState"]["S"], "running")

    def test_erase_during_processing_rejects_result(self):
        client = None

        def erase():
            client.item = None

        handler_type = processing_handler(lambda o, p, c: (erase(), {"result": {"x": 1}})[1])
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_MISSING)

    def test_cancellation_during_processing_rejects_result(self):
        client = None

        def cancel():
            client.item["status"] = {"S": "CANCELLED"}

        handler_type = processing_handler(lambda o, p, c: (cancel(), {"result": {"x": 1}})[1])
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_REJECTED)
        self.assertNotIn("result", client.item)
        self.assertEqual(client.item["status"]["S"], "CANCELLED")

    def test_conflicting_attempt_cannot_complete(self):
        client = None

        def steal():
            client.item["processingAttemptId"] = {"S": "other-attempt"}

        handler_type = processing_handler(lambda o, p, c: (steal(), {"result": {"x": 1}})[1])
        client = FakeDynamo(item(orderType={"S": handler_type}))
        outcome = run(client)

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSING_SKIPPED)
        self.assertNotIn("result", client.item)

    def test_completion_error_after_handler_is_not_a_success(self):
        """Absturz zwischen Handler und Abschluss -> Claim bleibt (Lease), kein Ergebnis."""
        client = None

        handler_type = processing_handler()
        client = FakeDynamo(item(orderType={"S": handler_type}))
        original_update = client.update_item

        def flaky_complete(**kwargs):
            if kwargs["UpdateExpression"].startswith("SET processingState = :succeeded"):
                raise RuntimeError("dynamodb unavailable")
            return original_update(**kwargs)

        client.update_item = flaky_complete

        with self.assertRaises(RuntimeError):
            run(client)
        self.assertNotIn("result", client.item)


if __name__ == "__main__":
    unittest.main()
