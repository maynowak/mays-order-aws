"""MO-RC4-P02H-A — Owner-/Consumer-Autorisierung der öffentlichen Order-API."""

import json
import os
import unittest
from unittest import mock

import index
import sqs_handler
from errors import OrderError
from identity import OrderIdentity, authorize_order_access
from order_service import create_order_service

os.environ.setdefault("ORDERS_TABLE", "mays-orders")

ORDER_ID = "ord_2f4b1c9e0000000000000000"
OWNER = "user-owner"
CONSUMER = "cognito:test#client"

IDENTITY = OrderIdentity(
    consumer_id=CONSUMER, owner_type="user", owner_id=OWNER,
    actor_type="user", actor_id=OWNER,
)
FOREIGN = OrderIdentity(
    consumer_id=CONSUMER, owner_type="user", owner_id="user-foreign",
    actor_type="user", actor_id="user-foreign",
)
OTHER_CONSUMER = OrderIdentity(
    consumer_id="cognito:test#other", owner_type="user", owner_id=OWNER,
    actor_type="user", actor_id=OWNER,
)

BODY = {
    "customer": {"name": "Max", "email": "max@example.com"},
    "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
    "currency": "EUR",
}


def make_item(order_id=ORDER_ID, *, subject=OWNER, consumer=CONSUMER,
              status="PENDING", created="2026-11-01T12:00:00.000Z", **extra):
    item = {
        "pk": f"ord_{order_id}",
        "sk": "#ORDER",
        "orderId": order_id,
        "status": status,
        "customer": BODY["customer"],
        "items": BODY["items"],
        "currency": "EUR",
        "totalAmount": 100,
        "createdAt": created,
        "updatedAt": created,
        "version": 1,
        "gsi1pk": "LIST",
        "gsi1sk": created,
        "gsi2pk": f"SUBJECT#{subject}" if subject else None,
        "gsi2sk": f"ord_{order_id}#{created}" if subject else None,
    }
    if subject is None:
        item.pop("subjectId", None)
    else:
        item["subjectId"] = subject
    if consumer is None:
        item.pop("consumerId", None)
    else:
        item["consumerId"] = consumer
    if subject is None:
        item.pop("gsi2pk", None)
        item.pop("gsi2sk", None)
    item.update(extra)
    return item


class FakeClientError(Exception):
    def __init__(self, code="ConditionalCheckFailedException"):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeTable:
    """Minimaler DynamoDB-Stub für GSI2-Query, GetItem und bedingte Updates."""

    def __init__(self, items, *, conflict=False):
        self.items = {item["pk"]: dict(item) for item in items}
        self.conflict = conflict
        self.updates = []

    def query(self, **kwargs):
        values = kwargs["ExpressionAttributeValues"]
        partition = values[":pk"]
        matches = [dict(item) for item in self.items.values()
                   if item.get("gsi2pk") == partition]
        start = kwargs.get("ExclusiveStartKey")
        offset = start.get("offset", 0) if start else 0
        limit = kwargs.get("Limit", 100)
        page = matches[offset:offset + limit]
        response = {"Items": page}
        if offset + limit < len(matches):
            response["LastEvaluatedKey"] = {"offset": offset + limit}
        return response

    def get_item(self, **kwargs):
        item = self.items.get(kwargs["Key"]["pk"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        if self.conflict:
            raise FakeClientError()
        item = self.items[kwargs["Key"]["pk"]]
        values = kwargs.get("ExpressionAttributeValues", {})
        condition = kwargs.get("ConditionExpression", "")
        if "#subjectId = :owner" in condition and item.get("subjectId") != values[":owner"]:
            raise FakeClientError()
        if "#consumerId = :consumer" in condition and item.get("consumerId") != values[":consumer"]:
            raise FakeClientError()
        if "#status = :currentStatus" in condition and item.get("status") != values[":currentStatus"]:
            raise FakeClientError()
        if ":newStatus" in values:
            item["status"] = values[":newStatus"]
            item["updatedAt"] = values[":now"]
            item["version"] = item.get("version", 0) + 1
        return {"Attributes": dict(item)}


def service_with(items, **kwargs):
    return create_order_service("mays-orders", FakeTable(items, **kwargs))


class TestAccessHelper(unittest.TestCase):
    def test_both_conditions_required(self):
        item = make_item()
        self.assertTrue(authorize_order_access(item, IDENTITY))
        self.assertFalse(authorize_order_access(item, FOREIGN))
        self.assertFalse(authorize_order_access(item, OTHER_CONSUMER))

    def test_missing_fields_fail_closed(self):
        self.assertFalse(authorize_order_access(make_item(subject=None), IDENTITY))
        self.assertFalse(authorize_order_access(make_item(consumer=None), IDENTITY))
        self.assertFalse(authorize_order_access({}, IDENTITY))
        self.assertFalse(authorize_order_access(make_item(), None))


class TestGetAuthorization(unittest.TestCase):
    def test_owner_can_read(self):
        service = service_with([make_item()])
        order = service.get_order(ORDER_ID, identity=IDENTITY)
        self.assertEqual(order["orderId"], ORDER_ID)
        for field in ("subjectId", "consumerId", "version"):
            self.assertNotIn(field, order)

    def test_foreign_order_is_404(self):
        service = service_with([make_item()])
        with self.assertRaises(OrderError) as ctx:
            service.get_order(ORDER_ID, identity=FOREIGN)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_same_subject_other_consumer_is_404(self):
        service = service_with([make_item()])
        with self.assertRaises(OrderError) as ctx:
            service.get_order(ORDER_ID, identity=OTHER_CONSUMER)
        self.assertEqual(ctx.exception.http_status, 404)

    def test_legacy_without_subject_or_consumer_is_404(self):
        for legacy in (make_item(subject=None), make_item(consumer=None)):
            with self.subTest(item=legacy.get("orderId")):
                service = service_with([legacy])
                with self.assertRaises(OrderError) as ctx:
                    service.get_order(ORDER_ID, identity=IDENTITY)
                self.assertEqual(ctx.exception.http_status, 404)

    def test_missing_order_is_404(self):
        service = service_with([])
        with self.assertRaises(OrderError) as ctx:
            service.get_order(ORDER_ID, identity=IDENTITY)
        self.assertEqual(ctx.exception.http_status, 404)


class TestListAuthorization(unittest.TestCase):
    def test_only_own_orders_are_listed(self):
        service = service_with([
            make_item("ord_mine"),
            make_item("ord_foreign", subject="user-foreign"),
            make_item("ord_other_consumer", consumer="cognito:test#other"),
            make_item("ord_legacy", subject=None),
            make_item("ord_no_consumer", consumer=None),
        ])
        result = service.list_orders(20, identity=IDENTITY)

        ids = [order["orderId"] for order in result["orders"]]
        self.assertEqual(ids, ["ord_mine"])
        self.assertEqual(result["count"], 1)

    def test_uses_gsi2_not_gsi1(self):
        table = FakeTable([make_item()])
        service = create_order_service("mays-orders", table)
        with mock.patch.object(table, "query", wraps=table.query) as spy:
            service.list_orders(20, identity=IDENTITY)
        kwargs = spy.call_args.kwargs
        self.assertEqual(kwargs["IndexName"], "gsi2")
        self.assertIn("gsi2pk = :pk", kwargs["KeyConditionExpression"])
        self.assertEqual(kwargs["ExpressionAttributeValues"][":pk"], f"SUBJECT#{OWNER}")
        self.assertNotIn("gsi1pk", json.dumps(kwargs))

    def test_pagination_across_pages_with_filtering(self):
        items = [make_item(f"ord_{i}", created=f"2026-11-01T12:00:{i:02d}.000Z",
                           consumer=CONSUMER if i % 2 == 0 else "cognito:test#other")
                 for i in range(6)]
        service = service_with(items)
        first = service.list_orders(2, identity=IDENTITY)
        self.assertEqual(len(first["orders"]), 2)
        self.assertIn("nextToken", first)

        second = service.list_orders(2, first["nextToken"], identity=IDENTITY)
        self.assertEqual(len(second["orders"]), 1)  # nur 3 eigene insgesamt
        self.assertNotIn("nextToken", second)

        combined = [o["orderId"] for o in first["orders"] + second["orders"]]
        self.assertEqual(len(combined), 3)
        self.assertEqual(len(set(combined)), 3)

    def test_no_internal_fields_in_list(self):
        service = service_with([make_item(result={"x": 1}, processingState="succeeded")])
        order = service.list_orders(20, identity=IDENTITY)["orders"][0]
        for field in ("subjectId", "consumerId", "result", "processingState",
                      "processingAttemptId", "completedAt", "processingError"):
            self.assertNotIn(field, order)

    def test_invalid_cursor_is_400(self):
        service = service_with([make_item()])
        with self.assertRaises(OrderError) as ctx:
            service.list_orders(20, "!!!not-base64!!!", identity=IDENTITY)
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")


class TestPatchAuthorization(unittest.TestCase):
    def test_owner_can_update_with_atomic_condition(self):
        table = FakeTable([make_item()])
        service = create_order_service("mays-orders", table)
        order = service.update_order_status(ORDER_ID, "CONFIRMED", identity=IDENTITY)

        self.assertEqual(order["status"], "CONFIRMED")
        condition = table.updates[0]["ConditionExpression"]
        self.assertIn("#subjectId = :owner", condition)
        self.assertIn("#consumerId = :consumer", condition)
        self.assertIn("#status = :currentStatus", condition)
        values = table.updates[0]["ExpressionAttributeValues"]
        self.assertEqual(values[":owner"], OWNER)
        self.assertEqual(values[":consumer"], CONSUMER)

    def test_foreign_update_is_404_and_writes_nothing(self):
        table = FakeTable([make_item()])
        service = create_order_service("mays-orders", table)
        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CONFIRMED", identity=FOREIGN)
        self.assertEqual(ctx.exception.http_status, 404)
        self.assertEqual(table.updates, [])
        self.assertEqual(table.items[f"ord_{ORDER_ID}"]["status"], "PENDING")

    def test_foreign_cancellation_is_rejected(self):
        table = FakeTable([make_item()])
        service = create_order_service("mays-orders", table)
        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CANCELLED", identity=FOREIGN)
        self.assertEqual(ctx.exception.http_status, 404)
        self.assertEqual(table.items[f"ord_{ORDER_ID}"]["status"], "PENDING")

    def test_same_subject_other_consumer_is_404(self):
        table = FakeTable([make_item()])
        service = create_order_service("mays-orders", table)
        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CONFIRMED", identity=OTHER_CONSUMER)
        self.assertEqual(ctx.exception.http_status, 404)
        self.assertEqual(table.updates, [])

    def test_legacy_without_identity_is_404(self):
        for legacy in (make_item(subject=None), make_item(consumer=None)):
            with self.subTest():
                table = FakeTable([legacy])
                service = create_order_service("mays-orders", table)
                with self.assertRaises(OrderError) as ctx:
                    service.update_order_status(ORDER_ID, "CONFIRMED", identity=IDENTITY)
                self.assertEqual(ctx.exception.http_status, 404)
                self.assertEqual(table.updates, [])

    def test_concurrent_update_is_409_without_fallback_write(self):
        table = FakeTable([make_item()], conflict=True)
        service = create_order_service("mays-orders", table)
        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CONFIRMED", identity=IDENTITY)
        self.assertEqual(ctx.exception.code, "CONFLICTED_UPDATE")
        self.assertEqual(len(table.updates), 1)  # kein ungeschuetzter Zweit-Write

    def test_conflict_with_unreadable_order_is_404(self):
        """Nach Konflikt: Order fremd geworden -> 404 statt 409."""
        table = FakeTable([make_item()], conflict=True)
        original_update = table.update_item

        def update_then_change_owner(**kwargs):
            try:
                return original_update(**kwargs)
            except FakeClientError:
                table.items[f"ord_{ORDER_ID}"]["subjectId"] = "user-someone-else"
                raise

        table.update_item = update_then_change_owner
        service = create_order_service("mays-orders", table)
        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CONFIRMED", identity=IDENTITY)
        self.assertEqual(ctx.exception.http_status, 404)
        self.assertEqual(len(table.updates), 1)


class FakeHandlerService:
    def __init__(self):
        self.create_order = lambda body, subject_id=None, identity=None: {
            "orderId": "ord_1", "status": "PENDING"
        }
        self.mark_delivery_state = lambda order_id, state: None
        self.get_order = lambda order_id, identity=None: {
            "orderId": order_id, "status": "PENDING"
        }
        self.list_orders = lambda limit, next_token=None, identity=None: {
            "orders": [], "count": 0
        }
        self.update_order_status = lambda order_id, status, identity=None: {
            "orderId": order_id, "status": status
        }


def auth_event(route_key, sub=OWNER, iss="https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_T",
               client="test-client", **extra):
    event = {
        "routeKey": route_key,
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "sub": sub, "iss": iss, "client_id": client,
        }}}},
    }
    event.update(extra)
    return event


class TestHandlerAuthorization(unittest.TestCase):
    def _call(self, event):
        with mock.patch("index.create_order_service", return_value=FakeHandlerService()), \
             mock.patch.dict("index.os.environ", {"ORDERS_TABLE": "mays-orders"}):
            return index.handler(event, None)

    def test_get_without_identity_is_401(self):
        response = self._call({"routeKey": "GET /orders/{orderId}",
                               "pathParameters": {"orderId": "ord_1"},
                               "requestContext": {}})
        self.assertEqual(response["statusCode"], 401)

    def test_patch_without_identity_is_401(self):
        response = self._call({"routeKey": "PATCH /orders/{orderId}/status",
                               "pathParameters": {"orderId": "ord_1"},
                               "body": json.dumps({"status": "CONFIRMED"}),
                               "requestContext": {}})
        self.assertEqual(response["statusCode"], 401)

    def test_list_without_identity_is_401(self):
        response = self._call({"routeKey": "GET /orders", "requestContext": {}})
        self.assertEqual(response["statusCode"], 401)

    def test_get_with_identity_is_200(self):
        response = self._call(auth_event("GET /orders/{orderId}",
                                         pathParameters={"orderId": "ord_1"}))
        self.assertEqual(response["statusCode"], 200)

    def test_patch_with_identity_is_200(self):
        response = self._call(auth_event("PATCH /orders/{orderId}/status",
                                         pathParameters={"orderId": "ord_1"},
                                         body=json.dumps({"status": "CONFIRMED"})))
        self.assertEqual(response["statusCode"], 200)

    def test_body_cannot_override_identity(self):
        response = self._call(auth_event("PATCH /orders/{orderId}/status",
                                         pathParameters={"orderId": "ord_1"},
                                         body=json.dumps({"status": "CONFIRMED",
                                                          "subjectId": "attacker"})))
        self.assertEqual(response["statusCode"], 400)


class TestWorkerUnaffected(unittest.TestCase):
    def test_worker_runs_without_identity_context(self):
        """Der Worker braucht keine Cognito-Identitaet (IAM-Pfad)."""
        item = make_item(status="PENDING")
        item["status"] = {"S": "PENDING"}
        item["orderType"] = {"S": "generic"}

        class WorkerClient:
            def __init__(self):
                self.item = item

            def get_item(self, **kwargs):
                return {"Item": dict(self.item)}

            def update_item(self, **kwargs):
                self.item["status"] = kwargs["ExpressionAttributeValues"][":newStatus"]
                return {}

        client = WorkerClient()
        with mock.patch.object(sqs_handler, "_get_dynamodb_client", return_value=client), \
             mock.patch.dict("sqs_handler.os.environ", {"ORDERS_TABLE": "mays-orders"}):
            outcome = sqs_handler._process_order(ORDER_ID, "CONFIRMED", {})

        self.assertEqual(outcome, sqs_handler.OUTCOME_PROCESSED)
        self.assertEqual(client.item["status"]["S"], "CONFIRMED")


if __name__ == "__main__":
    unittest.main()
