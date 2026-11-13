"""S1–S6 — verified owner enforcement for Mays-Orders.

Local only: no AWS, no deployment. Covers the 14 required evidence points.
"""

import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

import index  # noqa: E402
from errors import OrderError  # noqa: E402
from identity import IdentityError, OwnerIdentity, extract_identity, owner_key  # noqa: E402
from order_service import OrderService, create_order_service  # noqa: E402

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_POOL"
CLIENT = "client-abc"

ALICE = OwnerIdentity(issuer=ISSUER, subject="alice", client_id=CLIENT)
BOB = OwnerIdentity(issuer=ISSUER, subject="bob", client_id=CLIENT)
ALICE_OTHER_ISSUER = OwnerIdentity(
    issuer="https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_OTHER",
    subject="alice", client_id=CLIENT)

RETAIL = {
    "customer": {"name": "Max Mustermann", "email": "max@example.com"},
    "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
    "currency": "EUR",
}

AGENT_BODY = {
    "orderType": "agent.execution",
    "agentOrder": {
        "schemaVersion": "1.0",
        "target": {"agentId": "addition_agent", "capability": "math.add"},
        "input": {"data": {"left": 17, "right": 25}},
    },
}


def event_for(identity, *, claims_override=None, path_params=None,
              route="GET /orders/{orderId}", body=None, qs=None):
    claims = {
        "iss": identity.issuer,
        "sub": identity.subject,
        "client_id": identity.client_id,
        "token_use": "access",
    }
    claims.update(claims_override or {})
    return {
        "routeKey": route,
        "pathParameters": path_params,
        "queryStringParameters": qs,
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {"authorizer": {"jwt": {"claims": claims}}},
    }


class FakeTable:
    """In-memory table with the query/update/put surface the service uses."""

    class ValidationFailed(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "ValidationException"}}

    def __init__(self):
        self.items = {}
        self.queries = []

    def put_item(self, **kwargs):
        self.items[kwargs["Item"]["orderId"]] = dict(kwargs["Item"])
        return {}

    def get_item(self, Key):
        order_id = Key["pk"][len("ord_"):]
        item = self.items.get(order_id)
        return {"Item": dict(item)} if item else {}

    def query(self, **kwargs):
        self.queries.append(kwargs)
        if getattr(self, "reject_query", False):
            raise FakeTable.ValidationFailed()
        owner = kwargs["ExpressionAttributeValues"][":owner"]
        return {"Items": [dict(i) for i in self.items.values()
                          if i.get("gsi3pk") == owner]}

    def update_item(self, Key, UpdateExpression, **kwargs):
        order_id = Key["pk"][len("ord_"):]
        item = self.items[order_id]
        if "#status" in UpdateExpression and ":newStatus" in kwargs.get(
                "ExpressionAttributeValues", {}):
            item["status"] = kwargs["ExpressionAttributeValues"][":newStatus"]
        return {"Attributes": dict(item)}


# ---------------------------------------------------------------------------
# S1 — identity extraction
# ---------------------------------------------------------------------------
class TestIdentityExtraction(unittest.TestCase):
    def test_valid_claims_yield_owner(self):
        identity = extract_identity(event_for(ALICE),
                                    expected_issuer=ISSUER,
                                    expected_client_id=CLIENT)
        self.assertEqual("alice", identity.subject)
        self.assertEqual(ISSUER, identity.issuer)

    def test_missing_authorizer_context_is_rejected(self):
        with self.assertRaises(IdentityError) as ctx:
            extract_identity({"routeKey": "GET /orders"})
        self.assertEqual("missing_identity_context", ctx.exception.code)

    def test_missing_subject_is_rejected(self):
        with self.assertRaises(IdentityError) as ctx:
            extract_identity(event_for(ALICE, claims_override={"sub": ""}))
        self.assertEqual("missing_subject", ctx.exception.code)

    def test_missing_issuer_is_rejected(self):
        with self.assertRaises(IdentityError) as ctx:
            extract_identity(event_for(ALICE, claims_override={"iss": None}))
        self.assertEqual("missing_issuer", ctx.exception.code)

    def test_wrong_issuer_is_rejected(self):
        with self.assertRaises(IdentityError) as ctx:
            extract_identity(event_for(ALICE), expected_issuer="https://evil")
        self.assertEqual("issuer_mismatch", ctx.exception.code)

    def test_wrong_audience_is_rejected(self):
        with self.assertRaises(IdentityError) as ctx:
            extract_identity(event_for(ALICE), expected_client_id="other-client")
        self.assertEqual("audience_mismatch", ctx.exception.code)

    def test_invalid_token_use_is_rejected(self):
        with self.assertRaises(IdentityError) as ctx:
            extract_identity(event_for(ALICE, claims_override={"token_use": "refresh"}))
        self.assertEqual("invalid_token_use", ctx.exception.code)

    def test_same_subject_different_issuer_is_a_different_owner(self):
        self.assertNotEqual(ALICE.owner_key, ALICE_OTHER_ISSUER.owner_key)
        self.assertEqual(ALICE.owner_key, owner_key(ISSUER, "alice"))

    def test_staff_group_grants_no_implicit_access(self):
        staff = OwnerIdentity(issuer=ISSUER, subject="support", client_id=CLIENT,
                              groups=("staff", "admins"))
        self.assertFalse(staff.can_read({"ownerKey": ALICE.owner_key}))


# ---------------------------------------------------------------------------
# S2 — create
# ---------------------------------------------------------------------------
class TestCreateOwnership(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.service = OrderService("t", client=self.table)

    def test_retail_order_records_owner_and_index(self):
        self.service.create_order(RETAIL, ALICE)
        item = list(self.table.items.values())[0]
        self.assertEqual(ALICE.owner_key, item["ownerKey"])
        self.assertEqual(ISSUER, item["ownerIssuer"])
        self.assertEqual("alice", item["ownerSubject"])
        self.assertEqual("user", item["actorType"])
        self.assertEqual(ALICE.owner_key, item["gsi3pk"])

    def test_agent_order_records_the_same_owner_fields(self):
        self.service.create_order(AGENT_BODY, ALICE)
        item = list(self.table.items.values())[0]
        self.assertEqual(ALICE.owner_key, item["ownerKey"])
        self.assertEqual(ALICE.owner_key, item["gsi3pk"])
        self.assertIn("agentOrder", item)

    def test_identity_is_required(self):
        with self.assertRaises(OrderError):
            self.service.create_order(RETAIL, None)

    def test_body_cannot_inject_owner_fields(self):
        body = dict(RETAIL)
        body["ownerKey"] = "forged"
        with self.assertRaises(OrderError) as ctx:
            self.service.create_order(body, ALICE)
        self.assertEqual("VALIDATION_ERROR", ctx.exception.code)


# ---------------------------------------------------------------------------
# S3 — get / patch
# ---------------------------------------------------------------------------
class TestOwnerEnforcement(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.service = OrderService("t", client=self.table)
        self.order_id = self.service.create_order(RETAIL, ALICE)["orderId"]

    def test_owner_can_read(self):
        order = self.service.get_order(self.order_id, ALICE)
        self.assertEqual(self.order_id, order["orderId"])

    def test_foreign_reader_gets_404(self):
        with self.assertRaises(OrderError) as ctx:
            self.service.get_order(self.order_id, BOB)
        self.assertEqual(404, ctx.exception.http_status)
        self.assertEqual("ORDER_NOT_FOUND", ctx.exception.code)

    def test_same_subject_other_issuer_gets_404(self):
        with self.assertRaises(OrderError) as ctx:
            self.service.get_order(self.order_id, ALICE_OTHER_ISSUER)
        self.assertEqual(404, ctx.exception.http_status)

    def test_foreign_patch_is_rejected_and_changes_nothing(self):
        with self.assertRaises(OrderError) as ctx:
            self.service.update_order_status(self.order_id, "CONFIRMED", BOB)
        self.assertEqual(404, ctx.exception.http_status)
        self.assertEqual("PENDING", self.table.items[self.order_id]["status"])

    def test_owner_patch_succeeds(self):
        order = self.service.update_order_status(self.order_id, "CONFIRMED", ALICE)
        self.assertEqual("CONFIRMED", order["status"])

    def test_legacy_order_without_owner_is_inaccessible(self):
        self.table.items[self.order_id].pop("ownerKey")
        with self.assertRaises(OrderError) as ctx:
            self.service.get_order(self.order_id, ALICE)
        self.assertEqual(404, ctx.exception.http_status)

    def test_nonexistent_and_foreign_are_indistinguishable(self):
        foreign = self.service.get_order
        with self.assertRaises(OrderError) as foreign_ctx:
            foreign(self.order_id, BOB)
        with self.assertRaises(OrderError) as missing_ctx:
            foreign("ord_doesnotexist", BOB)
        self.assertEqual(foreign_ctx.exception.code, missing_ctx.exception.code)
        self.assertEqual(foreign_ctx.exception.http_status,
                         missing_ctx.exception.http_status)


# ---------------------------------------------------------------------------
# S4 — list
# ---------------------------------------------------------------------------
class TestOwnerList(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.service = OrderService("t", client=self.table)
        self.service.create_order(RETAIL, ALICE)
        self.service.create_order(RETAIL, BOB)

    def test_list_queries_the_owner_index(self):
        result = self.service.list_orders(ALICE, 20)
        query = self.table.queries[-1]
        self.assertEqual("gsi3", query["IndexName"])
        self.assertEqual(ALICE.owner_key,
                         query["ExpressionAttributeValues"][":owner"])
        self.assertEqual(1, result["count"])

    def test_foreign_orders_are_not_listed(self):
        alice_ids = {o["orderId"] for o in self.service.list_orders(ALICE, 20)["orders"]}
        bob_ids = {o["orderId"] for o in self.service.list_orders(BOB, 20)["orders"]}
        self.assertEqual(1, len(alice_ids))
        self.assertEqual(1, len(bob_ids))
        self.assertTrue(alice_ids.isdisjoint(bob_ids))

    def test_missing_index_fails_closed_without_global_fallback(self):
        self.table.reject_query = True
        with self.assertRaises(OrderError) as ctx:
            self.service.list_orders(ALICE, 20)
        self.assertEqual(503, ctx.exception.http_status)
        self.assertEqual("SERVICE_UNAVAILABLE", ctx.exception.code)
        # the only query attempted was the owner index, never gsi1
        self.assertTrue(all(q["IndexName"] == "gsi3" for q in self.table.queries))


# ---------------------------------------------------------------------------
# S5/S6 — route level, privacy untouched, agent body protected
# ---------------------------------------------------------------------------
class TestRouteLevelEnforcement(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.service = OrderService("t", client=self.table)
        self.order_id = self.service.create_order(RETAIL, ALICE)["orderId"]
        self.env = patch.dict(os.environ, {
            "ORDERS_TABLE": "t",
            "ORDERS_COGNITO_ISSUER": ISSUER,
            "ORDERS_COGNITO_CLIENT_ID": CLIENT,
        })
        self.env.start()
        self.patches = [patch.object(index, "create_order_service",
                                     return_value=self.service)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()

    def _call(self, event):
        response = index.handler(event, None)
        return response["statusCode"], json.loads(response["body"])

    def test_owner_gets_200(self):
        code, body = self._call(event_for(
            ALICE, path_params={"orderId": self.order_id}))
        self.assertEqual(200, code)
        self.assertEqual(self.order_id, body["orderId"])

    def test_foreign_user_gets_404(self):
        code, body = self._call(event_for(
            BOB, path_params={"orderId": self.order_id}))
        self.assertEqual(404, code)
        self.assertEqual("ORDER_NOT_FOUND", body["error"]["code"])

    def test_missing_claims_get_401(self):
        code, body = self._call({"routeKey": "GET /orders/{orderId}",
                                 "pathParameters": {"orderId": self.order_id}})
        self.assertEqual(401, code)
        self.assertEqual("UNAUTHORIZED", body["error"]["code"])

    def test_manipulated_sub_in_body_is_ignored(self):
        # The body cannot carry identity; a forged field is a validation error,
        # and the owner still comes from the verified claims.
        code, body = self._call(event_for(
            ALICE, route="POST /orders", body={**RETAIL, "sub": "bob"}))
        self.assertEqual(400, code)
        self.assertEqual("VALIDATION_ERROR", body["error"]["code"])

    def test_agent_order_body_is_not_exposed(self):
        agent_id = self.service.create_order(AGENT_BODY, ALICE)["orderId"]
        code, body = self._call(event_for(
            ALICE, path_params={"orderId": agent_id}))
        self.assertEqual(200, code)
        self.assertNotIn("agentOrder", body)
        self.assertNotIn("agentOrderFingerprint", body)

    def test_foreign_user_cannot_see_agent_order(self):
        agent_id = self.service.create_order(AGENT_BODY, ALICE)["orderId"]
        code, _body = self._call(event_for(
            BOB, path_params={"orderId": agent_id}))
        self.assertEqual(404, code)

    def test_missing_identity_configuration_fails_closed(self):
        with patch.dict(os.environ, {"ORDERS_COGNITO_ISSUER": ""}):
            code, body = self._call(event_for(
                ALICE, path_params={"orderId": self.order_id}))
        self.assertEqual(503, code)
        self.assertEqual("SERVICE_UNAVAILABLE", body["error"]["code"])

    def test_no_secret_in_error_bodies(self):
        code, body = self._call(event_for(
            BOB, path_params={"orderId": self.order_id}))
        text = json.dumps(body)
        self.assertNotIn("ris_", text)
        self.assertNotIn("Bearer", text)
        self.assertNotIn("test-secret", text)

    def test_privacy_path_still_uses_its_own_index(self):
        """S5: privacy stays on gsi2 and keeps its own auth boundary."""
        import inspect
        source = inspect.getsource(OrderService.inspect_subject)
        self.assertIn("GSI2_NAME", source)
        self.assertIn("_require_privacy_auth", source)


if __name__ == "__main__":
    unittest.main()
