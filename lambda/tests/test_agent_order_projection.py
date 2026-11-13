"""P01–P04 — owner-only agent order detail projection.

Local only, no AWS. Verifies that exactly one route releases the fachliche
agentOrder, and only to the verified owner.
"""

import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

import index  # noqa: E402
from errors import OrderError  # noqa: E402
from identity import OwnerIdentity  # noqa: E402
from order_service import OrderService, to_public_agent_order  # noqa: E402

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_POOL"
CLIENT = "client-abc"
ALICE = OwnerIdentity(issuer=ISSUER, subject="alice", client_id=CLIENT)
BOB = OwnerIdentity(issuer=ISSUER, subject="bob", client_id=CLIENT)

RETAIL = {
    "customer": {"name": "Max Mustermann", "email": "max@example.com"},
    "items": [{"sku": "SKU-1", "quantity": 2, "unitPrice": 1999}],
    "currency": "EUR",
}

AGENT = {
    "orderType": "agent.execution",
    "agentOrder": {
        "schemaVersion": "1.0",
        "target": {"agentId": "addition_agent", "capability": "math.add",
                   "agentVersion": "1.0.0"},
        "input": {"schemaVersion": "1.0", "data": {"left": 17, "right": 25}},
        "metadata": {
            "source": "ris-agent-ecosystem",
            "partnerApplicationRef": "partner-a",
            "apiProfileRef": "profile-a",
            "requestId": "req-001",
            "idempotencyKey": "addition-001",
        },
        "processing": {
            "trigger": "ORDER_CREATED",
            "parentOrderId": None,
            "parentWorkId": "work-secret-123",
            "executionProfile": "default",
        },
        "resultContract": {
            "schemaVersion": "1.0",
            "format": "json",
            "expectedCapability": "math.add",
            "delivery": "order-result",
        },
    },
}


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
        owner = kwargs["ExpressionAttributeValues"][":owner"]
        return {"Items": [dict(i) for i in self.items.values()
                          if i.get("gsi3pk") == owner]}

    def update_item(self, Key, UpdateExpression, **kwargs):
        order_id = Key["pk"][len("ord_"):]
        item = self.items[order_id]
        item["status"] = kwargs["ExpressionAttributeValues"][":newStatus"]
        return {"Attributes": dict(item)}


class TestOwnerDetailProjection(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.service = OrderService("t", client=self.table)
        self.agent_id = self.service.create_order(AGENT, ALICE)["orderId"]

    def test_owner_sees_the_fachliche_agent_order(self):
        order = self.service.get_order(self.agent_id, ALICE)
        self.assertIn("agentOrder", order)
        agent_order = order["agentOrder"]
        self.assertEqual("addition_agent", agent_order["target"]["agentId"])
        self.assertEqual("math.add", agent_order["target"]["capability"])
        self.assertEqual({"left": 17, "right": 25},
                         agent_order["input"]["data"])
        self.assertEqual("json", agent_order["resultContract"]["format"])

    def test_identity_references_are_withheld(self):
        agent_order = self.service.get_order(self.agent_id, ALICE)["agentOrder"]
        metadata = agent_order["metadata"]
        self.assertEqual("ris-agent-ecosystem", metadata["source"])
        self.assertEqual("req-001", metadata["requestId"])
        self.assertNotIn("partnerApplicationRef", metadata)
        self.assertNotIn("apiProfileRef", metadata)
        self.assertNotIn("idempotencyKey", metadata)

    def test_processing_state_is_withheld(self):
        agent_order = self.service.get_order(self.agent_id, ALICE)["agentOrder"]
        self.assertNotIn("processing", agent_order)
        self.assertNotIn("work-secret-123", json.dumps(agent_order))

    def test_fingerprint_is_withheld(self):
        order = self.service.get_order(self.agent_id, ALICE)
        self.assertNotIn("agentOrderFingerprint", order)

    def test_foreign_owner_gets_404(self):
        with self.assertRaises(OrderError) as ctx:
            self.service.get_order(self.agent_id, BOB)
        self.assertEqual(404, ctx.exception.http_status)
        self.assertEqual("ORDER_NOT_FOUND", ctx.exception.code)

    def test_legacy_agent_order_without_owner_gets_404(self):
        self.table.items[self.agent_id].pop("ownerKey")
        with self.assertRaises(OrderError) as ctx:
            self.service.get_order(self.agent_id, ALICE)
        self.assertEqual(404, ctx.exception.http_status)

    def test_list_never_contains_agent_order(self):
        result = self.service.list_orders(ALICE, 20)
        serialized = json.dumps(result)
        self.assertNotIn("agentOrder", serialized)
        self.assertNotIn("math.add", serialized)

    def test_create_response_stays_without_agent_order(self):
        created = self.service.create_order(AGENT, ALICE)
        self.assertNotIn("agentOrder", created)

    def test_retail_detail_is_unchanged(self):
        retail_id = self.service.create_order(RETAIL, ALICE)["orderId"]
        order = self.service.get_order(retail_id, ALICE)
        self.assertNotIn("agentOrder", order)
        self.assertEqual("EUR", order["currency"])
        self.assertEqual(3998, order["totalAmount"])
        self.assertEqual("Max Mustermann", order["customer"]["name"])
        self.assertEqual(
            ["createdAt", "currency", "customer", "items", "orderId",
             "status", "totalAmount", "updatedAt"],
            sorted(order),
        )

    def test_foreign_patch_cannot_touch_an_agent_order(self):
        with self.assertRaises(OrderError) as ctx:
            self.service.update_order_status(self.agent_id, "CONFIRMED", BOB)
        self.assertEqual(404, ctx.exception.http_status)
        self.assertEqual("PENDING", self.table.items[self.agent_id]["status"])

    def test_patch_response_does_not_release_agent_order(self):
        order = self.service.update_order_status(self.agent_id, "CONFIRMED", ALICE)
        self.assertNotIn("agentOrder", order)


class TestProjectionHardening(unittest.TestCase):
    def test_unknown_stored_fields_are_not_projected(self):
        tampered = json.loads(json.dumps(AGENT["agentOrder"]))
        tampered["target"]["internalNote"] = "leak"
        tampered["metadata"]["apiProfileRef"] = "profile-a"
        tampered["input"]["data"]["api_key"] = "ris_" + "A" * 47
        projected = to_public_agent_order(tampered)
        serialized = json.dumps(projected)
        self.assertNotIn("internalNote", serialized)
        self.assertNotIn("profile-a", serialized)
        self.assertNotIn("ris_", serialized)

    def test_malformed_stored_body_is_withheld(self):
        self.assertEqual({}, to_public_agent_order(None))
        self.assertEqual({}, to_public_agent_order("not-an-object"))
        # A body that no longer satisfies V1 is not projected at all.
        self.assertEqual({}, to_public_agent_order({"target": "x", "input": 5}))


class TestRouteLevelProjection(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.service = OrderService("t", client=self.table)
        self.agent_id = self.service.create_order(AGENT, ALICE)["orderId"]
        self.env = patch.dict(os.environ, {
            "ORDERS_TABLE": "t",
            "ORDERS_COGNITO_ISSUER": ISSUER,
            "ORDERS_COGNITO_CLIENT_ID": CLIENT,
        })
        self.env.start()
        self.patch = patch.object(index, "create_order_service",
                                  return_value=self.service)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.env.stop()

    def _get(self, identity, order_id):
        event = {
            "routeKey": "GET /orders/{orderId}",
            "pathParameters": {"orderId": order_id},
            "requestContext": {"authorizer": {"jwt": {"claims": {
                "iss": identity.issuer, "sub": identity.subject,
                "client_id": identity.client_id, "token_use": "access"}}}},
        }
        response = index.handler(event, None)
        return response["statusCode"], json.loads(response["body"])

    def test_owner_gets_agent_order_over_http(self):
        code, body = self._get(ALICE, self.agent_id)
        self.assertEqual(200, code)
        self.assertEqual("math.add", body["agentOrder"]["target"]["capability"])

    def test_foreign_owner_gets_404_over_http(self):
        code, body = self._get(BOB, self.agent_id)
        self.assertEqual(404, code)
        self.assertEqual("ORDER_NOT_FOUND", body["error"]["code"])

    def test_no_internal_fields_in_the_response(self):
        _code, body = self._get(ALICE, self.agent_id)
        for internal in ("agentOrderFingerprint", "ownerKey", "ownerIssuer",
                         "ownerSubject", "gsi3pk", "gsi3sk", "pk", "sk"):
            self.assertNotIn(internal, body)


if __name__ == "__main__":
    unittest.main()
