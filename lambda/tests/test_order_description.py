"""MO-ORDER-DESCRIPTION-01: additive description and privacy contract tests."""
import os
import unittest

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

from errors import OrderError
from identity import OrderIdentity
from order_service import create_order_service, to_list_item, to_public_order
from validation import MAX_ORDER_DESCRIPTION_LENGTH, validate_create_order

BASE_BODY = {
    "customer": {"name": "Max Mustermann", "email": "max@example.com"},
    "items": [{"sku": "RIS-ATS-MATCHING", "quantity": 1, "unitPrice": 199}],
    "currency": "EUR",
}
DESCRIPTION = "ATS-Matching einer Stellenausschreibung"
PRIVACY_CONTEXT = {
    "project": "mays-orders",
    "authorized": True,
    "privacy_inspect": True,
    "privacy_export": True,
    "privacy_erase": True,
    "internal_token": "test-secret",
}
IDENTITY = OrderIdentity(
    consumer_id="cognito:test#client",
    owner_type="user",
    owner_id="user-123",
    actor_type="user",
    actor_id="user-123",
)


class InMemoryOrders:
    """Minimales DynamoDB-Table-Double inkl. UpdateExpression-Auswertung.

    Die Anonymisierung ist der einzige Vertragspunkt, bei dem das Verhalten
    von DynamoDB selbst relevant ist: REMOVE eines nicht vorhandenen
    Attributs ist ein No-op (kein Fehler). Genau das bildet diese Klasse ab.
    """

    def __init__(self):
        self.order = None
        self.updates = []

    def put_item(self, **kwargs):
        self.order = kwargs["Item"].copy()
        return {}

    def get_item(self, **kwargs):
        if self.order and kwargs.get("Key", {}).get("pk") == self.order["pk"]:
            return {"Item": self.order}
        return {}

    def query(self, **kwargs):
        if not self.order:
            return {"Items": []}
        # GSI2-Semantik: ohne gsi2pk ist das Item im Index nicht auffindbar.
        partition = (kwargs.get("ExpressionAttributeValues") or {}).get(":pk")
        if partition != self.order.get("gsi2pk"):
            return {"Items": []}
        return {"Items": [{"orderId": self.order["orderId"]}]}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        key_matches = (
            self.order is not None
            and kwargs.get("Key", {}).get("pk") == self.order["pk"]
        )
        if key_matches:
            self._apply_update(
                kwargs.get("UpdateExpression", ""),
                kwargs.get("ExpressionAttributeNames", {}),
                kwargs.get("ExpressionAttributeValues", {}),
            )
        return {}

    def delete_item(self, **kwargs):
        if self.order and kwargs.get("Key", {}).get("pk") == self.order["pk"]:
            self.order = None
        return {}

    def _apply_update(self, expression, names, values):
        set_part, _, remove_part = expression.partition(" REMOVE ")
        if set_part.startswith("SET "):
            for assignment in set_part[len("SET "):].split(","):
                target, _, placeholder = assignment.strip().partition(" = ")
                if not target or not placeholder:
                    continue
                path = [names.get(part, part) for part in target.split(".")]
                cursor = self.order
                for key in path[:-1]:
                    cursor = cursor.setdefault(key, {})
                cursor[path[-1]] = values[placeholder]
        for token in remove_part.split(","):
            name = names.get(token.strip(), token.strip())
            if name:
                # DynamoDB REMOVE eines fehlenden Attributs ist ein No-op.
                self.order.pop(name, None)


class TestOrderDescriptionValidation(unittest.TestCase):
    def test_absent_is_backward_compatible(self):
        validated = validate_create_order(BASE_BODY)
        self.assertNotIn("orderDescription", validated)

    def test_accepts_and_trims_optional_description(self):
        parsed = validate_create_order({**BASE_BODY, "orderDescription": "  " + DESCRIPTION + "  "})
        self.assertEqual(parsed["orderDescription"], DESCRIPTION)

    def test_allows_multiline_tabs_and_carriage_return(self):
        for value in ("A\nB", "A\tB", "A\r\nB"):
            with self.subTest(value=repr(value)):
                parsed = validate_create_order({**BASE_BODY, "orderDescription": value})
                self.assertEqual(parsed["orderDescription"], value)

    def test_max_length_boundary_is_inclusive(self):
        maximum = "a" * MAX_ORDER_DESCRIPTION_LENGTH
        trimmed = validate_create_order(
            {**BASE_BODY, "orderDescription": "  " + maximum + "  "}
        )
        self.assertEqual(len(trimmed["orderDescription"]), MAX_ORDER_DESCRIPTION_LENGTH)
        # Nicht-ASCII-Zeichen zaehlen als Zeichen, nicht als Bytes.
        unicode_max = validate_create_order(
            {**BASE_BODY, "orderDescription": "ä" * MAX_ORDER_DESCRIPTION_LENGTH}
        )
        self.assertEqual(len(unicode_max["orderDescription"]), MAX_ORDER_DESCRIPTION_LENGTH)

    def test_rejects_invalid_descriptions(self):
        invalid_values = (
            None,
            123,
            12.5,
            True,
            {},
            [],
            "",
            "  ",
            "a" * (MAX_ORDER_DESCRIPTION_LENGTH + 1),
            "one\x00two",
            "a\x7fb",
            # C1-Steuerzeichen und Unicode-Zeilentrenner sind kein Bestelltext.
            "a\x85b",
            "a\x9bb",
            "a\u2028b",
            "a\u2029b",
            # Lone Surrogate ist kein gültiger Unicode-Skalarwert.
            "a\ud800b",
        )
        for invalid in invalid_values:
            with self.subTest(value=repr(invalid)):
                with self.assertRaises(OrderError) as error:
                    validate_create_order({**BASE_BODY, "orderDescription": invalid})
                self.assertEqual(error.exception.http_status, 400)
                self.assertEqual(error.exception.details, {"path": "orderDescription"})

    def test_unknown_fields_still_rejected(self):
        with self.assertRaises(OrderError):
            validate_create_order({**BASE_BODY, "unknown": "no"})

    def test_does_not_change_items_or_order_type(self):
        parsed = validate_create_order(
            {**BASE_BODY, "orderType": "jobsearch.match", "orderDescription": DESCRIPTION}
        )
        self.assertEqual(parsed["orderType"], "jobsearch.match")
        self.assertEqual(parsed["items"], BASE_BODY["items"])
        self.assertEqual(parsed["currency"], "EUR")


class TestOrderDescriptionPersistence(unittest.TestCase):
    def test_create_persists_and_exposes_description(self):
        table = InMemoryOrders()
        service = create_order_service("mays-orders", client=table)
        order = service.create_order(
            {**BASE_BODY, "orderDescription": DESCRIPTION},
            subject_id="user-123",
            identity=IDENTITY,
        )
        self.assertEqual(table.order["orderDescription"], DESCRIPTION)
        self.assertEqual(order["orderDescription"], DESCRIPTION)
        self.assertEqual(to_public_order(table.order)["orderDescription"], DESCRIPTION)
        # Kompaktes Listing bleibt bewusst ohne Freitext.
        self.assertNotIn("orderDescription", to_list_item(table.order))

    def test_create_without_description_omits_attribute(self):
        table = InMemoryOrders()
        service = create_order_service("mays-orders", client=table)
        order = service.create_order(BASE_BODY, subject_id="user-123", identity=IDENTITY)
        self.assertNotIn("orderDescription", table.order)
        self.assertNotIn("orderDescription", order)

    def test_post_persist_get_roundtrip(self):
        table = InMemoryOrders()
        service = create_order_service("mays-orders", client=table)
        created = service.create_order(
            {**BASE_BODY, "orderDescription": DESCRIPTION},
            subject_id="user-123",
            identity=IDENTITY,
        )
        fetched = service.get_order(created["orderId"], identity=IDENTITY)
        self.assertEqual(fetched["orderDescription"], DESCRIPTION)
        self.assertEqual(fetched["orderId"], created["orderId"])

    def test_existing_order_without_description_keeps_legacy_shape(self):
        table = InMemoryOrders()
        service = create_order_service("mays-orders", client=table)
        created = service.create_order(BASE_BODY, subject_id="user-123", identity=IDENTITY)
        fetched = service.get_order(created["orderId"], identity=IDENTITY)
        self.assertNotIn("orderDescription", fetched)
        self.assertEqual(
            set(fetched),
            {
                "orderId", "status", "orderType", "customer", "items", "currency",
                "totalAmount", "createdAt", "updatedAt", "deliveryState",
            },
        )


class TestOrderDescriptionPrivacy(unittest.TestCase):
    def test_inspect_reports_category_only_when_present(self):
        with_description = InMemoryOrders()
        service = create_order_service("mays-orders", client=with_description)
        service.create_order(
            {**BASE_BODY, "orderDescription": DESCRIPTION},
            subject_id="user-123",
            identity=IDENTITY,
        )
        inspection = service.inspect_subject("user-123", context=PRIVACY_CONTEXT)
        self.assertEqual(inspection["status"], "COMPLETED")
        self.assertIn("orderDescription", inspection["dataCategories"])

        without_description = InMemoryOrders()
        service = create_order_service("mays-orders", client=without_description)
        service.create_order(BASE_BODY, subject_id="user-123", identity=IDENTITY)
        inspection = service.inspect_subject("user-123", context=PRIVACY_CONTEXT)
        self.assertEqual(inspection["status"], "COMPLETED")
        self.assertNotIn("orderDescription", inspection["dataCategories"])

    def test_export_includes_and_omits_description(self):
        with_description = InMemoryOrders()
        service = create_order_service("mays-orders", client=with_description)
        service.create_order(
            {**BASE_BODY, "orderDescription": DESCRIPTION},
            subject_id="user-123",
            identity=IDENTITY,
        )
        export = service.export_subject("user-123", context=PRIVACY_CONTEXT)
        self.assertEqual(export["status"], "COMPLETED")
        self.assertEqual(export["orders"][0]["orderDescription"], DESCRIPTION)

        without_description = InMemoryOrders()
        service = create_order_service("mays-orders", client=without_description)
        service.create_order(BASE_BODY, subject_id="user-123", identity=IDENTITY)
        export = service.export_subject("user-123", context=PRIVACY_CONTEXT)
        self.assertEqual(export["status"], "COMPLETED")
        self.assertNotIn("orderDescription", export["orders"][0])

    def test_anonymize_removes_description(self):
        table = InMemoryOrders()
        service = create_order_service("mays-orders", client=table)
        service.create_order(
            {**BASE_BODY, "orderDescription": DESCRIPTION},
            subject_id="user-123",
            identity=IDENTITY,
        )
        erased = service.erase_subject(
            "user-123",
            context=PRIVACY_CONTEXT,
            options={"mode": "EXECUTE", "policy": "ANONYMIZE"},
        )
        self.assertEqual(erased["status"], "COMPLETED")
        self.assertEqual(erased["anonymizedRecords"], 1)
        self.assertEqual(len(table.updates), 1)
        update = table.updates[0]
        self.assertIn("#desc", update["UpdateExpression"])
        self.assertEqual(update["ExpressionAttributeNames"]["#desc"], "orderDescription")
        # DynamoDB-Semantik: Attribut ist danach entfernt.
        self.assertNotIn("orderDescription", table.order)
        self.assertEqual(table.order["customer"]["name"], "ANONYMIZED")
        self.assertNotIn("subjectId", table.order)

        # Nach ANONYMIZE ist die Order weder über GSI2 noch über GET erreichbar
        # und taucht in Inspect/Export nicht mehr auf.
        inspection = service.inspect_subject("user-123", context=PRIVACY_CONTEXT)
        self.assertEqual(inspection["affectedRecords"], 0)
        self.assertNotIn("orderDescription", inspection["dataCategories"])
        export = service.export_subject("user-123", context=PRIVACY_CONTEXT)
        self.assertEqual(export["recordCount"], 0)
        with self.assertRaises(OrderError) as error:
            service.get_order(table.order["orderId"], identity=IDENTITY)
        self.assertEqual(error.exception.http_status, 404)

    def test_anonymize_without_description_is_noop_for_that_attribute(self):
        table = InMemoryOrders()
        service = create_order_service("mays-orders", client=table)
        service.create_order(BASE_BODY, subject_id="user-123", identity=IDENTITY)
        erased = service.erase_subject(
            "user-123",
            context=PRIVACY_CONTEXT,
            options={"mode": "EXECUTE", "policy": "ANONYMIZE"},
        )
        self.assertEqual(erased["status"], "COMPLETED")
        self.assertEqual(erased["anonymizedRecords"], 1)
        self.assertNotIn("orderDescription", table.order)
        self.assertEqual(table.order["customer"]["email"], "anonymized@example.com")

    def test_erase_still_deletes_the_item(self):
        table = InMemoryOrders()
        service = create_order_service("mays-orders", client=table)
        service.create_order(
            {**BASE_BODY, "orderDescription": DESCRIPTION},
            subject_id="user-123",
            identity=IDENTITY,
        )
        erased = service.erase_subject(
            "user-123",
            context=PRIVACY_CONTEXT,
            options={"mode": "EXECUTE", "policy": "ERASE"},
        )
        self.assertEqual(erased["status"], "COMPLETED")
        self.assertEqual(erased["deletedRecords"], 1)
        self.assertIsNone(table.order)


if __name__ == "__main__":
    unittest.main()
