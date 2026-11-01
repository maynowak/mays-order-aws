import base64
import json
import os
import unittest
from decimal import Decimal

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

from errors import OrderError, json_default
from identity import OrderIdentity
from order_service import create_order_service, decode_next_token
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
    """Client-Stub mit automatischem Item-Store.

    Privacy-Funktionen laden nach der GSI2-Query das vollstaendige Item per
    get_item. Damit bestehende Tests nur `query` stubben muessen, merkt sich
    der Stub die Query-Items und beantwortet get_item daraus (sofern der Test
    keinen eigenen get_item-Handler vorgibt).
    """
    handlers = dict(handlers)
    store = {}

    original_query = handlers.get("query")

    def query(**kwargs):
        result = original_query(**kwargs) if original_query else {"Items": []}
        for item in result.get("Items", []):
            pk = item.get("pk")
            if pk:
                store[pk] = item
        return result

    if original_query is not None:
        handlers["query"] = query

    if "get_item" not in handlers:
        def get_item(**kwargs):
            pk = (kwargs.get("Key") or {}).get("pk")
            item = store.get(pk)
            return {"Item": item} if item else {}

        handlers["get_item"] = get_item

    return FakeTable(handlers)


ORDER_ID = "ord_2f4b1c9e0000000000000000"

TEST_IDENTITY = OrderIdentity(
    consumer_id="cognito:test#client",
    owner_type="user",
    owner_id="user-123",
    actor_type="user",
    actor_id="user-123",
)


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
        "subjectId": "user-123",
        "consumerId": "cognito:test#client",
    }
    item.update(overrides)
    # pk haengt fachlich an der orderId (wichtig fuer get_item-Lookups).
    item["pk"] = f"{ORDER_ID_PREFIX}{item['orderId']}"
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
            },
            subject_id="user-123",
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
            },
            subject_id="user-123",
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

        order = service.get_order(ORDER_ID, identity=TEST_IDENTITY)
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

        order = service.get_order(ORDER_ID, identity=TEST_IDENTITY)
        self.assertNotIn("isTestData", order)

    def test_raises_order_not_found(self):
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"get_item": lambda **kw: {}}),
        )

        with self.assertRaises(OrderError) as ctx:
            service.get_order(ORDER_ID, identity=TEST_IDENTITY)
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

        result = service.list_orders(20, identity=TEST_IDENTITY)
        self.assertEqual(query_input["IndexName"], "gsi2")
        self.assertIn("gsi2pk = :pk", query_input["KeyConditionExpression"])
        self.assertEqual(query_input["ExpressionAttributeValues"][":pk"],
                         f"SUBJECT#{TEST_IDENTITY.owner_id}")
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

        result = service.list_orders(5, identity=TEST_IDENTITY)
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

        service.list_orders(20, token, identity=TEST_IDENTITY)
        self.assertEqual(query_input["ExclusiveStartKey"], lek)

    def test_rejects_invalid_next_token(self):
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"query": lambda **kw: {"Items": []}}),
        )

        with self.assertRaises(OrderError) as ctx:
            service.list_orders(20, "!!!not-base64-json!!!", identity=TEST_IDENTITY)
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

        order = service.update_order_status(ORDER_ID, "CONFIRMED", identity=TEST_IDENTITY)
        self.assertEqual(order["status"], "CONFIRMED")
        self.assertIn("#status = :currentStatus", update_input["ConditionExpression"])
        self.assertEqual(update_input["ExpressionAttributeValues"][":currentStatus"], "PENDING")
        self.assertEqual(update_input["ExpressionAttributeValues"][":newStatus"], "CONFIRMED")
        self.assertIn("#version = if_not_exists(#version, :zero) + :one",
                      update_input["UpdateExpression"])
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
            service.update_order_status(ORDER_ID, "CANCELLED", identity=TEST_IDENTITY)
        error = ctx.exception
        self.assertEqual(error.code, "INVALID_TRANSITION")
        self.assertEqual(error.details, {"currentStatus": "PROCESSING", "requestedStatus": "CANCELLED"})

    def test_raises_order_not_found(self):
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"get_item": lambda **kw: {}}),
        )

        with self.assertRaises(OrderError) as ctx:
            service.update_order_status(ORDER_ID, "CONFIRMED", identity=TEST_IDENTITY)
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
            service.update_order_status(ORDER_ID, "CONFIRMED", identity=TEST_IDENTITY)
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

    def test_privacy_requires_internal_secret(self):
        # Missing secret must block
        original = os.environ.pop("PRIVACY_INTERNAL_SECRET", None)
        try:
            service = create_order_service(table_name="mays-orders", client=make_client({}))
            with self.assertRaises(OrderError):
                service.inspect_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_inspect": True, "internal_token": "test-secret"})
        finally:
            if original is not None:
                os.environ["PRIVACY_INTERNAL_SECRET"] = original

    def test_privacy_requires_internal_token(self):
        service = create_order_service(table_name="mays-orders", client=make_client({}))
        with self.assertRaises(OrderError):
            service.inspect_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_inspect": True, "internal_token": "wrong-secret"})


if __name__ == "__main__":
    unittest.main()

class TestRuntimeFixRegression(unittest.TestCase):
    """MAYS-ORDERS-PRIVACY-RUNTIME-FIX-01: Decimal + reserviertes Wort 'status'."""

    def test_get_order_with_decimal_serializes(self):
        item = make_order(totalAmount=Decimal("39.98"))
        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"get_item": lambda **kw: {"Item": item}}),
        )
        order = service.get_order(ORDER_ID, identity=TEST_IDENTITY)
        body = json.loads(json.dumps(order, default=json_default))
        self.assertEqual(body["totalAmount"], 39.98)

    def test_list_orders_with_decimal_and_token(self):
        lek = {"pk": f"{ORDER_ID_PREFIX}abc", "sk": "#ORDER", "totalAmount": Decimal("10")}

        def on_query(**kwargs):
            return {"Items": [make_order()], "LastEvaluatedKey": lek}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"query": on_query}),
        )
        result = service.list_orders(20, identity=TEST_IDENTITY)
        self.assertIn("nextToken", result)
        # Token muss dekodierbar sein (Decimal im LEK darf nicht scheitern)
        decoded = decode_next_token(result["nextToken"])
        self.assertEqual(decoded["pk"], lek["pk"])

    def test_inspect_aliases_reserved_status(self):
        captured = {}

        def on_query(**kwargs):
            captured.update(kwargs)
            return {"Items": [make_order(orderId="ord_1", customer={"name": "A", "email": "a@example.com"})]}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"query": on_query}),
        )
        result = service.inspect_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_inspect": True, "internal_token": "test-secret"})
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["affectedRecords"], 1)
        # MO-RC4-P02G-A: Die GSI2-Query projiziert nur projizierte Attribute
        # (kein nicht-projiziertes Feld, kein Alias noetig); Details kommen
        # per get_item.
        self.assertEqual(captured.get("ProjectionExpression"), "orderId")
        self.assertNotIn("ExpressionAttributeNames", captured)

    def test_export_aliases_reserved_status(self):
        captured = {}

        def on_query(**kwargs):
            captured.update(kwargs)
            return {"Items": [make_order(orderId="ord_1")]}

        service = create_order_service(
            table_name="mays-orders",
            client=make_client({"query": on_query}),
        )
        result = service.export_subject("user-123", context={"project": "mays-orders", "authorized": True, "privacy_export": True, "internal_token": "test-secret"})
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(captured.get("ProjectionExpression"), "orderId")
        self.assertNotIn("ExpressionAttributeNames", captured)


class TestOrderOwnershipPersistence(unittest.TestCase):
    """MO-RC4-P02: subjectId wird Pflicht, persistiert und bleibt unveraendert."""

    BODY = {
        "customer": {"name": "Max Mustermann", "email": "max@example.com"},
        "items": [{"sku": "SKU-1001", "quantity": 1, "unitPrice": 1999}],
        "currency": "EUR",
    }

    def test_create_order_persists_subject_and_gsi2(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service("mays-orders", make_client({"put_item": on_put}))
        order = service.create_order(self.BODY, subject_id="user-123")

        self.assertEqual(stored["subjectId"], "user-123")
        self.assertEqual(stored["gsi2pk"], "SUBJECT#user-123")
        self.assertTrue(stored["gsi2sk"].startswith(f"{ORDER_ID_PREFIX}{order['orderId']}#"))
        # interne Felder bleiben aus der API-Antwort heraus
        self.assertNotIn("subjectId", order)
        self.assertNotIn("gsi2pk", order)

    def test_create_order_requires_owner(self):
        cases = (None, "", "   ", "user\x00id", "x" * 257)
        for bad in cases:
            with self.subTest(subject=repr(bad)):
                called = []
                service = create_order_service(
                    "mays-orders",
                    make_client({"put_item": lambda **kw: called.append(kw) or {}}),
                )
                with self.assertRaises(OrderError) as ctx:
                    service.create_order(self.BODY, subject_id=bad)
                self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")
                self.assertEqual(called, [])

    def test_status_update_keeps_original_owner(self):
        update_args = {}

        def on_get(**kwargs):
            return {"Item": make_order(version=1, subjectId="user-123",
                                       gsi2pk="SUBJECT#user-123",
                                       gsi2sk=f"{ORDER_ID_PREFIX}{ORDER_ID}#x")}

        def on_update(**kwargs):
            update_args.update(kwargs)
            updated = make_order(status="CONFIRMED", version=2, subjectId="user-123",
                                 gsi2pk="SUBJECT#user-123",
                                 gsi2sk=f"{ORDER_ID_PREFIX}{ORDER_ID}#x")
            return {"Attributes": updated}

        service = create_order_service(
            "mays-orders", make_client({"get_item": on_get, "update_item": on_update})
        )
        result = service.update_order_status(ORDER_ID, "CONFIRMED", identity=TEST_IDENTITY)

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertNotIn("subjectId", result)
        self.assertNotIn("subjectId", update_args["UpdateExpression"])
        self.assertNotIn("gsi2pk", update_args["UpdateExpression"])

    def test_body_cannot_smuggle_subject_id(self):
        called = []
        body = dict(self.BODY)
        body["subjectId"] = "attacker"
        service = create_order_service(
            "mays-orders", make_client({"put_item": lambda **kw: called.append(kw) or {}})
        )
        with self.assertRaises(OrderError) as ctx:
            service.create_order(body, subject_id="user-123")
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")
        self.assertEqual(called, [])

    def test_two_users_get_distinct_gsi2_partitions(self):
        stored = []

        def on_put(**kwargs):
            stored.append(kwargs["Item"]["gsi2pk"])
            return {}

        service = create_order_service("mays-orders", make_client({"put_item": on_put}))
        service.create_order(self.BODY, subject_id="user-a")
        service.create_order(self.BODY, subject_id="user-b")
        self.assertEqual(stored, ["SUBJECT#user-a", "SUBJECT#user-b"])


class TestPrivacyConsistency(unittest.TestCase):
    """MO-RC4-P02: Privacy-Funktionen nutzen die Zuordnung vollstaendig und sicher."""

    CONTEXT = {"project": "mays-orders", "authorized": True,
               "privacy_inspect": True, "privacy_export": True, "privacy_erase": True,
               "internal_token": "test-secret"}

    def test_inspect_paginates_all_pages(self):
        pages = [
            {"Items": [make_order(orderId="ord_1")], "LastEvaluatedKey": {"k": "1"}},
            {"Items": [make_order(orderId="ord_2")], "LastEvaluatedKey": {"k": "2"}},
            {"Items": [make_order(orderId="ord_3")]},
        ]
        calls = []

        def on_query(**kwargs):
            calls.append(kwargs)
            return pages[len(calls) - 1]

        service = create_order_service("mays-orders", make_client({"query": on_query}))
        result = service.inspect_subject("user-123", context=self.CONTEXT)

        self.assertEqual(len(calls), 3)
        self.assertIn("ExclusiveStartKey", calls[1])
        self.assertEqual(result["affectedRecords"], 3)
        self.assertCountEqual(result["orderReferences"], ["ord_1", "ord_2", "ord_3"])

    def test_erase_is_idempotent_when_item_already_gone(self):
        items = [make_order(subjectId="user-123", version=1)]

        def on_query(**kwargs):
            return {"Items": items}

        def on_delete(**kwargs):
            raise FakeClientError("ConditionalCheckFailedException")

        service = create_order_service(
            "mays-orders", make_client({"query": on_query, "delete_item": on_delete})
        )
        result = service.erase_subject(
            "user-123", context=self.CONTEXT, options={"mode": "EXECUTE", "policy": "ERASE"}
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["deletedRecords"], 0)
        self.assertEqual(result["skippedRecords"], 1)
        self.assertEqual(result["failedRecords"], 0)

    def test_erase_guard_binds_subject_in_condition(self):
        items = [make_order(subjectId="user-123", version=2)]
        captured = {}

        def on_delete(**kwargs):
            captured.update(kwargs)
            return {}

        service = create_order_service(
            "mays-orders", make_client({"query": lambda **kw: {"Items": items},
                                        "delete_item": on_delete})
        )
        service.erase_subject(
            "user-123", context=self.CONTEXT, options={"mode": "EXECUTE", "policy": "ERASE"}
        )

        self.assertIn("subjectId = :sid", captured["ConditionExpression"])
        self.assertIn("version = :ver", captured["ConditionExpression"])
        self.assertEqual(captured["ExpressionAttributeValues"][":sid"], "user-123")

    def test_erase_only_deletes_own_records(self):
        """Fremde Bestellungen tauchen in der GSI2-Query gar nicht erst auf."""
        deleted_keys = []

        def on_query(**kwargs):
            self.assertEqual(kwargs["ExpressionAttributeValues"][":pk"], "SUBJECT#user-123")
            return {"Items": [make_order(subjectId="user-123", version=1)]}

        def on_delete(**kwargs):
            deleted_keys.append(kwargs["Key"])
            return {}

        service = create_order_service(
            "mays-orders", make_client({"query": on_query, "delete_item": on_delete})
        )
        result = service.erase_subject(
            "user-123", context=self.CONTEXT, options={"mode": "EXECUTE", "policy": "ERASE"}
        )
        self.assertEqual(result["deletedRecords"], 1)
        self.assertEqual(deleted_keys, [{"pk": f"{ORDER_ID_PREFIX}{ORDER_ID}", "sk": "#ORDER"}])

    def test_anonymize_removes_owner_link(self):
        items = [make_order(subjectId="user-123", version=1)]
        captured = {}

        def on_update(**kwargs):
            captured.update(kwargs)
            return {}

        service = create_order_service(
            "mays-orders", make_client({"query": lambda **kw: {"Items": items},
                                        "update_item": on_update})
        )
        result = service.erase_subject(
            "user-123", context=self.CONTEXT, options={"mode": "EXECUTE", "policy": "ANONYMIZE"}
        )

        self.assertEqual(result["anonymizedRecords"], 1)
        self.assertIn("REMOVE subjectId, gsi2pk, gsi2sk", captured["UpdateExpression"])
        self.assertEqual(captured["ExpressionAttributeValues"][":sid"], "user-123")

    def test_erase_requires_explicit_policy(self):
        service = create_order_service(
            "mays-orders", make_client({"query": lambda **kw: {"Items": [make_order()]}})
        )
        result = service.erase_subject(
            "user-123", context=self.CONTEXT, options={"mode": "EXECUTE"}
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("Missing explicit retention policy", result["limitations"])


class TestIdentityPersistenceP02A(unittest.TestCase):
    """MO-RC4-P02A: Identity-Felder additiv, subjectId/GSI2 unveraendert."""

    BODY = TestOrderOwnershipPersistence.BODY

    def _identity(self, owner="user-123", consumer="cognito:iss#client",
                  owner_type="user", actor_type="user", actor=None):
        from identity import OrderIdentity
        return OrderIdentity(
            consumer_id=consumer,
            owner_type=owner_type,
            owner_id=owner,
            actor_type=actor_type,
            actor_id=actor or owner,
        )

    def test_identity_fields_are_persisted_and_hidden(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service("mays-orders", make_client({"put_item": on_put}))
        identity = self._identity()
        order = service.create_order(self.BODY, subject_id="user-123", identity=identity)

        self.assertEqual(stored["consumerId"], "cognito:iss#client")
        self.assertEqual(stored["ownerType"], "user")
        self.assertEqual(stored["ownerId"], "user-123")
        self.assertEqual(stored["actorType"], "user")
        self.assertEqual(stored["actorId"], "user-123")
        self.assertEqual(stored["identityVersion"], 1)
        # Privacy-Vertrag unveraendert:
        self.assertEqual(stored["subjectId"], "user-123")
        self.assertEqual(stored["gsi2pk"], "SUBJECT#user-123")
        # Keine internen Felder in der Antwort:
        for field in ("consumerId", "ownerType", "ownerId", "actorType", "actorId",
                      "identityVersion", "subjectId"):
            self.assertNotIn(field, order)

    def test_actor_may_differ_from_owner(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service("mays-orders", make_client({"put_item": on_put}))
        identity = self._identity(owner="user-123", actor_type="agent", actor="agent-7")
        service.create_order(self.BODY, identity=identity)

        self.assertEqual(stored["ownerId"], "user-123")
        self.assertEqual(stored["actorId"], "agent-7")
        self.assertEqual(stored["gsi2pk"], "SUBJECT#user-123")

    def test_owner_mismatch_is_rejected(self):
        service = create_order_service(
            "mays-orders", make_client({"put_item": lambda **kw: {}})
        )
        with self.assertRaises(OrderError) as ctx:
            service.create_order(self.BODY, subject_id="other",
                                 identity=self._identity(owner="user-123"))
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")

    def test_non_user_owner_type_is_rejected(self):
        service = create_order_service(
            "mays-orders", make_client({"put_item": lambda **kw: {}})
        )
        with self.assertRaises(OrderError) as ctx:
            service.create_order(self.BODY, identity=self._identity(owner_type="service"))
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")

    def test_identity_without_subject_argument_derives_owner(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service("mays-orders", make_client({"put_item": on_put}))
        service.create_order(self.BODY, identity=self._identity(owner="user-xyz"))
        self.assertEqual(stored["subjectId"], "user-xyz")
        self.assertEqual(stored["gsi2pk"], "SUBJECT#user-xyz")

    def test_legacy_subject_only_call_remains_supported(self):
        """P02-Vertrag bleibt gueltig: Aufruf ohne Identity schreibt keine
        Identity-Felder, subjectId/GSI2 unveraendert (keine erfundene Identitaet)."""
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service("mays-orders", make_client({"put_item": on_put}))
        service.create_order(self.BODY, subject_id="user-123")

        self.assertEqual(stored["subjectId"], "user-123")
        self.assertEqual(stored["gsi2pk"], "SUBJECT#user-123")
        for field in ("consumerId", "ownerType", "ownerId", "actorType", "actorId",
                      "identityVersion"):
            self.assertNotIn(field, stored)

        from identity import SOURCE_LEGACY_SUBJECT, classify_ownership
        self.assertEqual(classify_ownership(stored)["ownerSource"], SOURCE_LEGACY_SUBJECT)


class TestPrivacyConsumerScopeP02B(unittest.TestCase):
    """MO-RC4-P02B: Consumer-Scope filtert Privacy-Ergebnisse (nur einschränkend)."""

    def _ctx(self, consumer=None):
        context = {"project": "mays-orders", "authorized": True,
                   "privacy_inspect": True, "privacy_export": True,
                   "privacy_erase": True, "internal_token": "test-secret"}
        if consumer is not None:
            context["consumerId"] = consumer
        return context

    def _items(self):
        return [
            make_order(orderId="ord_a", subjectId="user-123",
                       consumerId="consumer-a", identityVersion=1,
                       identityVerification="verified_jwt"),
            make_order(orderId="ord_b", subjectId="user-123",
                       consumerId="consumer-b", identityVersion=1,
                       identityVerification="verified_jwt"),
            make_order(orderId="ord_legacy", subjectId="user-123"),
        ]

    def test_inspect_without_scope_returns_all(self):
        service = create_order_service(
            "mays-orders",
            make_client({"query": lambda **kw: {"Items": self._items()}}),
        )
        result = service.inspect_subject("user-123", context=self._ctx())
        self.assertEqual(result["affectedRecords"], 3)

    def test_inspect_with_scope_returns_only_matching_consumer(self):
        service = create_order_service(
            "mays-orders",
            make_client({"query": lambda **kw: {"Items": self._items()}}),
        )
        result = service.inspect_subject("user-123", context=self._ctx("consumer-a"))
        self.assertEqual(result["orderReferences"], ["ord_a"])

    def test_export_with_scope_hides_other_consumer_and_legacy(self):
        service = create_order_service(
            "mays-orders",
            make_client({"query": lambda **kw: {"Items": self._items()}}),
        )
        result = service.export_subject("user-123", context=self._ctx("consumer-b"))
        self.assertEqual(result["recordCount"], 1)
        self.assertEqual(result["orders"][0]["orderId"], "ord_b")
        # consumerId ist kein Exportfeld
        self.assertNotIn("consumerId", result["orders"][0])

    def test_erase_with_scope_does_not_touch_foreign_consumer(self):
        deleted = []

        def on_delete(**kwargs):
            deleted.append(kwargs["Key"])
            return {}

        service = create_order_service(
            "mays-orders",
            make_client({"query": lambda **kw: {"Items": self._items()},
                         "delete_item": on_delete}),
        )
        result = service.erase_subject(
            "user-123", context=self._ctx("consumer-a"),
            options={"mode": "EXECUTE", "policy": "ERASE"},
        )

        self.assertEqual(result["deletedRecords"], 1)
        expected_pk = self._items()[0]["pk"]
        self.assertEqual(deleted, [{"pk": expected_pk, "sk": "#ORDER"}])
        self.assertTrue(any("outside consumer scope" in note for note in result["limitations"]))

    def test_erase_without_scope_keeps_previous_behavior(self):
        deleted = []

        service = create_order_service(
            "mays-orders",
            make_client({"query": lambda **kw: {"Items": self._items()},
                         "delete_item": lambda **kw: deleted.append(kw["Key"]) or {}}),
        )
        result = service.erase_subject(
            "user-123", context=self._ctx(),
            options={"mode": "EXECUTE", "policy": "ERASE"},
        )
        self.assertEqual(result["deletedRecords"], 3)
        self.assertEqual(result["limitations"], [])

    def test_status_update_does_not_touch_identity_fields(self):
        captured = {}

        def on_get(**kwargs):
            return {"Item": make_order(subjectId="user-123", version=1,
                                       consumerId=TEST_IDENTITY.consumer_id,
                                       identityVersion=1,
                                       identityVerification="verified_jwt")}

        def on_update(**kwargs):
            captured.update(kwargs)
            return {"Attributes": make_order(status="CONFIRMED", version=2,
                                             subjectId="user-123")}

        service = create_order_service(
            "mays-orders", make_client({"get_item": on_get, "update_item": on_update})
        )
        service.update_order_status(ORDER_ID, "CONFIRMED", identity=TEST_IDENTITY)

        expression = captured["UpdateExpression"]
        for field in ("subjectId", "consumerId", "ownerId", "actorId",
                      "identityVersion", "identityVerification"):
            self.assertNotIn(field, expression)


class TestOrderTypeP02E(unittest.TestCase):
    """MO-RC4-P02E: orderType ist optional, Default generic, additiv."""

    BODY = TestOrderOwnershipPersistence.BODY

    def _stored(self, body):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service("mays-orders", make_client({"put_item": on_put}))
        order = service.create_order(body, subject_id="user-123")
        return stored, order

    def test_default_type_is_generic(self):
        stored, order = self._stored(self.BODY)
        self.assertEqual(stored["orderType"], "generic")
        self.assertEqual(order["orderType"], "generic")

    def test_explicit_generic_and_namespaced_type(self):
        stored, order = self._stored(dict(self.BODY, orderType="generic"))
        self.assertEqual(stored["orderType"], "generic")

        stored, order = self._stored(dict(self.BODY, orderType="ris.document.analyze"))
        self.assertEqual(stored["orderType"], "ris.document.analyze")
        self.assertEqual(order["orderType"], "ris.document.analyze")

    def test_invalid_type_is_rejected_before_write(self):
        called = []
        service = create_order_service(
            "mays-orders", make_client({"put_item": lambda **kw: called.append(kw) or {}})
        )
        for bad in ("", "   ", "Bad/Type", 42, "x" * 200):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(OrderError) as ctx:
                    service.create_order(dict(self.BODY, orderType=bad), subject_id="user-123")
                self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")
        self.assertEqual(called, [])

    def test_ownership_attributes_unaffected_by_type(self):
        stored, _ = self._stored(dict(self.BODY, orderType="jobsearch.match"))
        self.assertEqual(stored["subjectId"], "user-123")
        self.assertEqual(stored["gsi2pk"], "SUBJECT#user-123")


class TestDeliveryStateP02F(unittest.TestCase):
    """MO-RC4-P02F: Zustellzustand getrennt vom fachlichen Status."""

    BODY = TestOrderOwnershipPersistence.BODY

    def test_create_order_starts_with_delivery_pending(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service("mays-orders", make_client({"put_item": on_put}))
        service.create_order(self.BODY, subject_id="user-123")
        self.assertEqual(stored["deliveryState"], "pending")
        self.assertEqual(stored["status"], "PENDING")

    def test_mark_delivery_state_sets_state_and_increments_attempts(self):
        updates = []

        def on_update(**kwargs):
            updates.append(kwargs)
            return {}

        service = create_order_service("mays-orders", make_client({"update_item": on_update}))
        service.mark_delivery_state(ORDER_ID, "sent")
        service.mark_delivery_state(ORDER_ID, "failed")

        self.assertEqual(len(updates), 2)
        first = updates[0]
        self.assertIn("deliveryState = :state", first["UpdateExpression"])
        self.assertIn("deliveryAttempts = if_not_exists(deliveryAttempts, :zero) + :one",
                      first["UpdateExpression"])
        self.assertEqual(first["ExpressionAttributeValues"][":state"], "sent")
        self.assertNotIn("subjectId", first["UpdateExpression"])

    def test_invalid_delivery_state_is_rejected(self):
        service = create_order_service("mays-orders", make_client({"update_item": lambda **kw: {}}))
        with self.assertRaises(OrderError):
            service.mark_delivery_state(ORDER_ID, "processed")


class TestProcessingResultPrivacyP02GA(unittest.TestCase):
    """MO-RC4-P02G-A: Ergebnisse in Inspect/Export/Anonymize, nie oeffentlich."""

    CONTEXT = {"project": "mays-orders", "authorized": True,
               "privacy_inspect": True, "privacy_export": True,
               "privacy_erase": True, "internal_token": "test-secret"}

    def _item(self, **extra):
        return make_order(subjectId="user-123", consumerId="consumer-a",
                          identityVersion=1, identityVerification="verified_jwt", **extra)

    # ---------- Inspect ----------
    def test_inspect_reports_result_presence_without_content(self):
        item = self._item(result={"secretValue": "PII"}, processingState="succeeded",
                          processingError={"code": "X"})
        service = create_order_service("mays-orders",
                                       make_client({"query": lambda **kw: {"Items": [item]}}))
        result = service.inspect_subject("user-123", context=self.CONTEXT)

        self.assertTrue(result["hasProcessingResult"])
        self.assertTrue(result["hasProcessingError"])
        self.assertEqual(result["processingStates"], ["succeeded"])
        self.assertIn("processing.result", result["dataCategories"])
        self.assertIn("processing.error", result["dataCategories"])
        self.assertNotIn("PII", str(result))
        self.assertNotIn("secretValue", str(result))

    def test_inspect_without_result_fields(self):
        service = create_order_service("mays-orders",
                                       make_client({"query": lambda **kw: {"Items": [self._item()]}}))
        result = service.inspect_subject("user-123", context=self.CONTEXT)
        self.assertFalse(result["hasProcessingResult"])
        self.assertFalse(result["hasProcessingError"])
        self.assertEqual(result["processingStates"], [])

    def test_inspect_scope_isolation_still_applies(self):
        foreign = make_order(orderId="ord_other", subjectId="user-123",
                             consumerId="consumer-b", result={"x": 1})
        service = create_order_service("mays-orders",
                                       make_client({"query": lambda **kw: {"Items": [foreign]}}))
        result = service.inspect_subject(
            "user-123", context=dict(self.CONTEXT, consumerId="consumer-a")
        )
        self.assertFalse(result["hasProcessingResult"])
        self.assertEqual(result["orderReferences"], [])

    # ---------- Export ----------
    def test_export_includes_result_fields(self):
        item = self._item(result={"ok": True}, processingState="succeeded",
                          processingAttemptId="attempt-1",
                          completedAt="2026-11-01T12:00:00.000Z",
                          processingError={"code": "WARN", "message": "m"})
        service = create_order_service("mays-orders",
                                       make_client({"query": lambda **kw: {"Items": [item]}}))
        result = service.export_subject("user-123", context=self.CONTEXT)

        export = result["orders"][0]
        self.assertEqual(export["result"], {"ok": True})
        self.assertEqual(export["processingState"], "succeeded")
        self.assertEqual(export["processingAttemptId"], "attempt-1")
        self.assertEqual(export["completedAt"], "2026-11-01T12:00:00.000Z")
        self.assertEqual(export["processingError"], {"code": "WARN", "message": "m"})

    def test_export_legacy_order_omits_absent_fields(self):
        service = create_order_service("mays-orders",
                                       make_client({"query": lambda **kw: {"Items": [self._item()]}}))
        result = service.export_subject("user-123", context=self.CONTEXT)
        export = result["orders"][0]
        for field in ("result", "processingState", "processingAttemptId",
                      "completedAt", "processingError"):
            self.assertNotIn(field, export)

    # ---------- Anonymize ----------
    def test_anonymize_removes_result_and_error_fields(self):
        captured = {}

        def on_update(**kwargs):
            captured.update(kwargs)
            return {}

        service = create_order_service(
            "mays-orders",
            make_client({"query": lambda **kw: {"Items": [self._item(version=1)]},
                         "update_item": on_update}),
        )
        result = service.erase_subject(
            "user-123", context=self.CONTEXT,
            options={"mode": "EXECUTE", "policy": "ANONYMIZE"},
        )

        self.assertEqual(result["anonymizedRecords"], 1)
        expression = captured["UpdateExpression"]
        self.assertIn("REMOVE subjectId, gsi2pk, gsi2sk, #result, #perr, #patt", expression)
        names = captured["ExpressionAttributeNames"]
        self.assertEqual(names["#result"], "result")
        self.assertEqual(names["#perr"], "processingError")
        self.assertEqual(names["#patt"], "processingAttemptId")
        # Technische, nicht personenbezogene Felder bleiben erhalten
        self.assertNotIn("processingState", expression)
        self.assertNotIn("completedAt", expression)
        # Bedingung unveraendert (Ownership + Version)
        self.assertIn("subjectId = :sid", captured["ConditionExpression"])
        self.assertIn("version = :ver", captured["ConditionExpression"])

    def test_repeated_anonymize_is_safe(self):
        calls = []

        def on_delete(**kwargs):
            calls.append(kwargs)
            raise FakeClientError("ConditionalCheckFailedException")

        service = create_order_service(
            "mays-orders",
            make_client({"query": lambda **kw: {"Items": []}, "delete_item": on_delete}),
        )
        result = service.erase_subject(
            "user-123", context=self.CONTEXT,
            options={"mode": "EXECUTE", "policy": "ANONYMIZE"},
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["deletedRecords"], 0)

    # ---------- Oeffentliche API ----------
    def test_public_projection_hides_processing_fields(self):
        item = make_order(result={"secret": 1}, processingState="succeeded",
                          processingAttemptId="attempt-1",
                          completedAt="2026-11-01T12:00:00.000Z",
                          processingError={"code": "X"})

        def on_get(**kwargs):
            return {"Item": item}

        service = create_order_service("mays-orders", make_client({"get_item": on_get}))
        order = service.get_order(ORDER_ID, identity=TEST_IDENTITY)

        for field in ("result", "processingState", "processingAttemptId",
                      "completedAt", "processingError"):
            self.assertNotIn(field, order)

    def test_patch_response_hides_processing_fields(self):
        item = make_order(result={"secret": 1})

        def on_update(**kwargs):
            return {"Attributes": make_order(status="CONFIRMED", result={"secret": 1})}

        service = create_order_service(
            "mays-orders",
            make_client({"get_item": lambda **kw: {"Item": item}, "update_item": on_update}),
        )
        order = service.update_order_status(ORDER_ID, "CONFIRMED", identity=TEST_IDENTITY)
        self.assertNotIn("result", order)
