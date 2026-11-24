"""MO-RIS-COMPAT-01: optional generic orderDescription (additive).

The field is stored verbatim and never parsed by Mays-Orders. Legacy agent
orders (root ``agentOrder``) remain unchanged.
"""

import os
import unittest

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

from errors import OrderError  # noqa: E402
from identity import OwnerIdentity  # noqa: E402
from order_service import create_order_service  # noqa: E402
from validation import validate_create_order  # noqa: E402

IDENTITY = OwnerIdentity(
    issuer="https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST",
    subject="user-1", client_id="client-test")

RETAIL = {
    "customer": {"name": "Max Mustermann", "email": "max@example.com"},
    "items": [{"sku": "SKU-1001", "quantity": 2, "unitPrice": 1999}],
    "currency": "EUR",
}


def agent_body(**overrides):
    body = {
        "orderType": "agent.execution",
        "agentOrder": {
            "schemaVersion": "1.0",
            "target": {"agentId": "ats-agent", "capability": "analyze.job"},
            "input": {"schemaVersion": "1.0", "data": {"job": {"title": "X"}}},
            "metadata": {"source": "ris", "requestId": "corr-1"},
        },
    }
    body.update(overrides)
    return body


class FakeTable:
    def __init__(self, handlers=None):
        self._handlers = handlers or {}

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
        return {}


class TestOrderDescriptionValidation(unittest.TestCase):
    def test_retail_accepts_and_returns_description(self):
        out = validate_create_order(dict(RETAIL, orderDescription="Bitte prüfen"))
        self.assertEqual("Bitte prüfen", out["orderDescription"])

    def test_agent_accepts_description_next_to_agent_order(self):
        out = validate_create_order(agent_body(orderDescription="Lauf 1"))
        self.assertEqual("Lauf 1", out["orderDescription"])
        self.assertEqual("ats-agent", out["agentOrder"]["target"]["agentId"])

    def test_agent_without_description_is_unchanged(self):
        out = validate_create_order(agent_body())
        self.assertNotIn("orderDescription", out)

    def test_limit_is_1024(self):
        validate_create_order(dict(RETAIL, orderDescription="x" * 1024))
        with self.assertRaises(OrderError):
            validate_create_order(dict(RETAIL, orderDescription="x" * 1025))

    def test_control_characters_are_rejected(self):
        with self.assertRaises(OrderError):
            validate_create_order(dict(RETAIL, orderDescription="a\x01b"))

    def test_empty_description_is_rejected(self):
        with self.assertRaises(OrderError):
            validate_create_order(dict(RETAIL, orderDescription="   "))

    def test_unknown_root_field_still_rejected(self):
        with self.assertRaises(OrderError):
            validate_create_order(dict(RETAIL, extra="x"))


class TestGenericOrderType(unittest.TestCase):
    """orderType without agentOrder is a generic order (opaque metadata)."""

    def test_agent_execution_type_without_agent_order_is_generic(self):
        body = dict(RETAIL, orderType="agent.execution",
                    orderDescription='{"any":"payload"}')
        out = validate_create_order(body)
        self.assertEqual("agent.execution", out["orderType"])
        self.assertNotIn("agentOrder", out)
        self.assertEqual('{"any":"payload"}', out["orderDescription"])

    def test_generic_order_type_is_persisted(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service(
            table_name="mays-orders", client=FakeTable({"put_item": on_put}))
        order = service.create_order(
            dict(RETAIL, orderType="agent.execution",
                 orderDescription='{"x":1}'), IDENTITY)
        self.assertEqual("agent.execution", stored["orderType"])
        self.assertEqual('{"x":1}', stored["orderDescription"])
        self.assertNotIn("agentOrder", stored)
        self.assertNotIn("agentOrderFingerprint", stored)
        self.assertEqual("agent.execution", order["orderType"])

    def test_agent_order_still_routes_to_agent_branch(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service(
            table_name="mays-orders", client=FakeTable({"put_item": on_put}))
        service.create_order(agent_body(), IDENTITY)
        self.assertIn("agentOrder", stored)
        self.assertIn("agentOrderFingerprint", stored)

    def test_invalid_order_type_still_rejected(self):
        with self.assertRaises(OrderError):
            validate_create_order(dict(RETAIL, orderType="Bad/Type"))


class TestOrderDescriptionPersistence(unittest.TestCase):
    def test_retail_persists_description(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service(
            table_name="mays-orders", client=FakeTable({"put_item": on_put}))
        order = service.create_order(
            dict(RETAIL, orderDescription="Retail-Text"), IDENTITY)
        self.assertEqual("Retail-Text", order["orderDescription"])
        self.assertEqual("Retail-Text", stored["orderDescription"])

    def test_agent_persists_description_and_keeps_agent_order(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service(
            table_name="mays-orders", client=FakeTable({"put_item": on_put}))
        order = service.create_order(
            agent_body(orderDescription="Agent-Text"), IDENTITY)
        self.assertEqual("Agent-Text", stored["orderDescription"])
        self.assertEqual("ats-agent",
                         stored["agentOrder"]["target"]["agentId"])
        # agentOrder stays internal; description is public
        self.assertNotIn("agentOrder", order)
        self.assertEqual("Agent-Text", order["orderDescription"])

    def test_legacy_agent_order_without_description(self):
        stored = {}

        def on_put(**kwargs):
            stored.update(kwargs["Item"])
            return {}

        service = create_order_service(
            table_name="mays-orders", client=FakeTable({"put_item": on_put}))
        service.create_order(agent_body(), IDENTITY)
        self.assertNotIn("orderDescription", stored)
        self.assertIn("agentOrder", stored)
        self.assertIn("agentOrderFingerprint", stored)

    def test_privacy_inspect_reports_description_category(self):
        item = dict(agent_body(orderDescription="X"))
        item.update({"orderId": "ord_1", "status": "PENDING"})
        service = create_order_service(
            table_name="mays-orders",
            client=FakeTable({"query": lambda **kw: {"Items": [item]}}))
        result = service.inspect_subject(
            "user-1",
            {"project": "mays-orders", "authorized": True,
             "privacy_inspect": True, "internal_token": "test-secret"})
        self.assertIn("orderDescription", result["dataCategories"])


if __name__ == "__main__":
    unittest.main()
