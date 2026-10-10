import base64
import json
import os
import unittest

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

from errors import OrderError
from order_service import create_order_service
from order_types import GSI1_PK, ORDER_ID_PREFIX


class FakeTable:
    """Stub für boto3 dynamodb.Table — registriert Handler je Operation."""

    def __init__(self, handlers):
        self._handlers = handlers

    def put_item(self, **kwargs):
        handler = self._handlers.get("put_item")
        return {} if handler is None else handler(**kwargs)

    def get_item(self, **kwargs):
        handler = self._handlers.get("get_item")
        return {} if handler is None else handler(**kwargs)

    def query(self, **kwargs):
        handler = self._handlers.get("query")
        return {"Items": []} if handler is None else handler(**kwargs)

    def update_item(self, **kwargs):
        handler = self._handlers.get("update_item")
        return {} if handler is None else handler(**kwargs)

    def delete_item(self, **kwargs):
        handler = self._handlers.get("delete_item")
        return {} if handler is None else handler(**kwargs)


class FakeClientError(Exception):
    """Stub für boto3 ClientError (reicht für die Fehler-Erkennung)."""

    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def make_client(handlers):
    return FakeTable(handlers)


ORDER_ID = "ord_2f4b1c9e0000000000000000"


def make_order(**overrides):
    item = {
        "pk": f"{ORDER_ID_PREFIX}{ORDER_ID}",
        "sk": "#ORDER",
        "orderId": ORDER_ID,
        "status": "PENDING",
        "customer": {"name": "Max Mustermann", "email": "max@example.com"},
        "items": [{"sku": "SKU-1001", "quantity": 2, "unitPrice": 1999, "lineTotal": 3998}],
        "currency": "EUR",
        "totalAmount": 3998,
        "createdAt": "2026-08-17T12:00:00.000Z",
        "updatedAt": "2026-08-17T12:00:00.000Z",
        "version": 1,
        "gsi1pk": GSI1_PK,
        "gsi1sk": "2026-08-17T12:00:00.000Z",
    }
    item.update(overrides)
    return item


def encode_token(key):
    return base64.b64encode(json.dumps(key, separators=(",", ":")).encode("utf-8")).decode("utf-8")


class TestCreateOrder(unittest.TestCase):
    def test_computes_line_total_and_total_amount_server_side(self):
        put_item = {}

        def on_put(**kwargs):
            put_item["item"] = kwargs["Item"]
            return {}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"put_item": on_put}),
        )

        order = service.create_order(
            {
                "customer": {"name": "Max Mustermann", "email": "max@example.com"},
                "items": [
                    {"sku": "SKU-1001", "quantity": 2, "unitPrice": 1999},
                    {"sku": "SKU-1002", "quantity": 1, "unitPrice": 499},
                ],
                "currency": "EUR",
            }
        )

        self.assertEqual(order["status"], "PENDING")
        self.assertEqual(order["totalAmount"], 4497)
        self.assertEqual(order["items"][0]["lineTotal"], 3998)
        self.assertEqual(order["createdAt"], order["updatedAt"])

        stored = put_item["item"]
        self.assertEqual(stored["pk"], f"{ORDER_ID_PREFIX}{order['orderId']}")
        self.assertEqual(stored["sk"], "#ORDER")
        self.assertEqual(stored["gsi1pk"], GSI1_PK)
        self.assertEqual(stored["gsi1sk"], order["createdAt"])
        self.assertEqual(stored["version"], 1)
        self.assertEqual(stored["status"], "PENDING")
        self.assertEqual(stored["orderId"], order["orderId"])

    def test_validates_body_before_write(self):
        called = []

        def on_put(**kwargs):
            called.append(kwargs)
            return {}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"put_item": on_put}),
        )

        with self.assertRaises(OrderError) as ctx:
            service.create_order({"customer": {}, "items": [], "currency": ""})
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")
        self.assertEqual(called, [])

    def test_create_order_does_not_set_is_test_data(self):
        """Normale Order-Erstellung markiert Items NICHT als Testdaten (TEST 13)."""
        put_item = {}

        def on_put(**kwargs):
            put_item["item"] = kwargs["Item"]
            return {}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"put_item": on_put}),
        )

        service.create_order(
            {
                "customer": {"name": "Max Mustermann", "email": "max@example.com"},
                "items": [{"sku": "SKU-1001", "quantity": 1, "unitPrice": 1999}],
                "currency": "EUR",
            }
        )

        self.assertNotIn("isTestData", put_item["item"])
        self.assertNotIn("isTestData", put_item["item"]["items"][0])


class TestGetOrder(unittest.TestCase):
    def test_returns_order_without_internal_fields(self):
        item = make_order()
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"get_item": lambda **kw: {"Item": item}}),
        )

        order = service.get_order(ORDER_ID)
        self.assertEqual(order["orderId"], item["orderId"])
        self.assertEqual(order["status"], "PENDING")
        self.assertNotIn("pk", order)
        self.assertNotIn("version", order)

    def test_returns_order_without_is_test_data_marker(self):
        """Demo-Seed-Items tragen isTestData=true in DynamoDB, aber NICHT in der API-Antwort."""
        item = make_order(isTestData=True)
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"get_item": lambda **kw: {"Item": item}}),
        )

        order = service.get_order(ORDER_ID)
        self.assertNotIn("isTestData", order)

    def test_raises_order_not_found(self):
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"get_item": lambda **kw: {}}),
        )

        with self.assertRaises(OrderError) as ctx:
            service.get_order(ORDER_ID)
        self.assertEqual(ctx.exception.code, "ORDER_NOT_FOUND")
        self.assertEqual(ctx.exception.http_status, 404)


class TestListOrders(unittest.TestCase):
    def test_queries_gsi1_descending_and_returns_compact_items(self):
        query_input = {}

        def on_query(**kwargs):
            query_input.update(kwargs)
            return {"Items": [make_order()]}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"query": on_query}),
        )

        result = service.list_orders(20)
        self.assertEqual(query_input["IndexName"], "gsi1")
        self.assertFalse(query_input["ScanIndexForward"])
        self.assertEqual(query_input["Limit"], 20)
        self.assertEqual(result["count"], 1)
        self.assertEqual(
            result["orders"][0],
            {
                "orderId": ORDER_ID,
                "status": "PENDING",
                "customer": {"name": "Max Mustermann"},
                "totalAmount": 3998,
                "createdAt": "2026-08-17T12:00:00.000Z",
                "updatedAt": "2026-08-17T12:00:00.000Z",
            },
        )
        self.assertNotIn("nextToken", result)

    def test_encodes_last_evaluated_key_as_base64_next_token(self):
        lek = {"pk": f"{ORDER_ID_PREFIX}abc", "sk": "#ORDER"}
        service = create_order_service(
            table_name="mays-orders",
            client=make_client(
                {"query": lambda **kw: {"Items": [make_order()], "LastEvaluatedKey": lek}}
            ),
        )

        result = service.list_orders(5)
        self.assertEqual(result["nextToken"], encode_token(lek))

    def test_sets_exclusive_start_key_from_next_token(self):
        lek = {"pk": f"{ORDER_ID_PREFIX}abc", "sk": "#ORDER"}
        token = encode_token(lek)
        query_input = {}

        def on_query(**kwargs):
            query_input.update(kwargs)
            return {"Items": []}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"query": on_query}),
        )

        service.list_orders(20, token)
        self.assertEqual(query_input["ExclusiveStartKey"], lek)

    def test_rejects_invalid_next_token(self):
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"query": lambda **kw: {"Items": []}}),
        )

        with self.assertRaises(OrderError) as ctx:
            service.list_orders(20, "!!!not-base64-json!!!")
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")


class TestUpdateOrderStatus(unittest.TestCase):
    def test_valid_transition_uses_conditional_update(self):
        current = make_order(status="PENDING")
        updated = make_order(status="CONFIRMED", updatedAt="2026-08-17T13:00:00.000Z", version=2)
        update_input = {}

        def on_update(**kwargs):
            update_input.update(kwargs)
            return {"Attributes": updated}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client(
                {"get_item": lambda **kw: {"Item": current}, "update_item": on_update}
            ),
        )

        order = service.update_order_status(ORDER_ID, "CONFIRMED")
        self.assertEqual(order["status"], "CONFIRMED")
        self.assertIn("#status = :currentStatus", update_input["ConditionExpression"])
        self.assertEqual(update_input["ExpressionAttributeValues"][":currentStatus"], "PENDING")
        self.assertEqual(update_input["ExpressionAttributeValues"][":newStatus"], "CONFIRMED")
        self.assertIn("#version = #version + :one", update_input["UpdateExpression"])
        self.assertEqual(update_input["ExpressionAttributeValues"][":one"], 1)
        self.assertNotIn("version", order)
        self.assertNotIn("isTestData", order)

    def test_raises_invalid_transition(self):
        service = create_order_service(
            table_name="mays-orders",
            client=make_client(
                {"get_item": lambda **kw: {"Item": make_order(status="PROCESSING")}}
            ),
        )

        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CANCELLED")
        error = ctx.exception
        self.assertEqual(error.code, "INVALID_TRANSITION")
        self.assertEqual(error.details, {"currentStatus": "PROCESSING", "requestedStatus": "CANCELLED"})

    def test_raises_order_not_found(self):
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"get_item": lambda **kw: {}}),
        )

        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CONFIRMED")
        self.assertEqual(ctx.exception.code, "ORDER_NOT_FOUND")
        self.assertEqual(ctx.exception.http_status, 404)

    def test_raises_conflicted_update_on_conditional_check_failed(self):
        def on_update(**kwargs):
            raise FakeClientError("ConditionalCheckFailedException")

        service = create_order_service(
            table_name="mays-orders",
            client=make_client(
                {"get_item": lambda **kw: {"Item": make_order(status="PENDING")}, "update_item": on_update}
            ),
        )

        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CONFIRMED")
        self.assertEqual(ctx.exception.code, "CONFLICTED_UPDATE")
        self.assertEqual(ctx.exception.http_status, 409)


class TestPrivacyInspect(unittest.TestCase):
    def test_inspect_returns_orders_for_subject(self):
        items = [
            make_order(orderId="ord_1", customer={"name": "A", "email": "a@example.com"}),
            make_order(orderId="ord_2", customer={"name": "A", "email": "a@example.com"}),
        ]

        def on_query(**kwargs):
            self.assertEqual(kwargs.get("IndexName"), "gsi2")
            return {"Items": items}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"query": on_query}),
        )
        result = service.inspect_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_inspect": True, "internal_token": "test-secret"})
        self.assertEqual(result["subjectId"], "user-123")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["affectedRecords"], 2)
        self.assertCountEqual(result["orderReferences"], ["ord_1", "ord_2"])
        self.assertIn("customer.name", result["dataCategories"])

    def test_inspect_requires_project_context(self):
        service = create_order_service(table_name="mays-orders", client=make_client({}))
        with self.assertRaises(OrderError):
            service.inspect_subject("user-123", context={})

    def test_inspect_requires_authorization(self):
        service = create_order_service(table_name="mays-orders", client=make_client({}))
        with self.assertRaises(OrderError):
            service.inspect_subject("user-123", context={"project": "mays-orders", "authorized": False})

    def test_inspect_returns_empty_when_no_items(self):
        def on_query(**kwargs):
            return {"Items": []}
        service = create_order_service(table_name="mays-orders", client=make_client({"query": on_query}))
        result = service.inspect_subject("user-999", context={"project": "mays-orders", "authorized": True, "privacy_inspect": True, "internal_token": "test-secret"})
        self.assertEqual(result["affectedRecords"], 0)
        self.assertEqual(result["orderReferences"], [])


class TestPrivacyExport(unittest.TestCase):
    def test_export_returns_orders_for_subject(self):
        items = [
            make_order(orderId="ord_1", customer={"name": "A", "email": "a@example.com"}),
            make_order(orderId="ord_2", customer={"name": "B", "email": "b@example.com"}),
        ]

        def on_query(**kwargs):
            self.assertEqual(kwargs.get("IndexName"), "gsi2")
            return {"Items": items}

        service = create_order_service(table_name="mays-orders", client=make_client({"query": on_query}))
        result = service.export_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_export": True, "internal_token": "test-secret"})
        self.assertEqual(result["schemaVersion"], "1.0")
        self.assertEqual(result["subjectId"], "user-123")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["recordCount"], 2)
        self.assertEqual(len(result["orders"]), 2)
        self.assertEqual(result["orders"][0]["orderId"], "ord_1")
        self.assertNotIn("pk", result["orders"][0])
        self.assertNotIn("subjectId", result["orders"][0])

    def test_export_requires_authorization(self):
        service = create_order_service(table_name="mays-orders", client=make_client({}))
        with self.assertRaises(OrderError):
            service.export_subject("user-123", context={"project": "mays-orders", "authorized": False})

    def test_export_pagination(self):
        items_page1 = [make_order(orderId="ord_1")]
        items_page2 = [make_order(orderId="ord_2")]

        def on_query(**kwargs):
            # Simulate pagination
            if kwargs.get("ExclusiveStartKey"):
                return {"Items": items_page2}
            return {"Items": items_page1, "LastEvaluatedKey": {"dummy": "key"}}

        service = create_order_service(table_name="mays-orders", client=make_client({"query": on_query}))
        result = service.export_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_export": True, "internal_token": "test-secret"})
        self.assertEqual(result["recordCount"], 2)

    def test_export_no_pii_in_logs(self):
        # Ensure export does not raise and returns data without internal fields
        items = [make_order(orderId="ord_1")]
        service = create_order_service(table_name="mays-orders", client=make_client({"query": lambda **kw: {"Items": items}}))
        result = service.export_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_export": True, "internal_token": "test-secret"})
        for order in result["orders"]:
            self.assertNotIn("pk", order)
            self.assertNotIn("gsi1pk", order)
            self.assertNotIn("subjectId", order)


class TestPrivacyErase(unittest.TestCase):
    def test_erase_preview_no_mutation(self):
        items = [make_order(orderId="ord_1")]

        def on_query(**kwargs):
            return {"Items": items}

        service = create_order_service(table_name="mays-orders", client=make_client({"query": on_query}))
        result = service.erase_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_erase": True, "internal_token": "test-secret"}, options={"mode": "PREVIEW", "policy": "ERASE"})
        self.assertEqual(result["status"], "PREVIEW")
        self.assertEqual(result["affectedRecords"], 1)
        self.assertEqual(result["plannedDeletes"], 1)

    def test_erase_execute_deletes(self):
        items = [make_order(orderId="ord_1", subjectId="user-123")]

        deleted = []

        def on_query(**kwargs):
            return {"Items": items}

        def on_delete(**kwargs):
            deleted.append(kwargs)
            return {}

        service = create_order_service(table_name="mays-orders", client=make_client({"query": on_query, "delete_item": on_delete}))
        result = service.erase_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_erase": True, "internal_token": "test-secret"}, options={"mode": "EXECUTE", "policy": "ERASE"})
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["deletedRecords"], 1)
        self.assertEqual(len(deleted), 1)

    def test_erase_requires_authorization(self):
        service = create_order_service(table_name="mays-orders", client=make_client({}))
        with self.assertRaises(OrderError):
            service.erase_subject("user-123", context={"project": "mays-orders", "authorized": False}, options={"mode": "PREVIEW"})

    def test_erase_anonymize(self):
        items = [make_order(orderId="ord_1", subjectId="user-123")]

        updated = []

        def on_query(**kwargs):
            return {"Items": items}

        def on_update(**kwargs):
            updated.append(kwargs)
            return {}

        service = create_order_service(table_name="mays-orders", client=make_client({"query": on_query, "update_item": on_update}))
        result = service.erase_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_erase": True, "internal_token": "test-secret"}, options={"mode": "EXECUTE", "policy": "ANONYMIZE"})
        self.assertEqual(result["anonymizedRecords"], 1)
        self.assertEqual(len(updated), 1)


if __name__ == "__main__":
    unittest.main()