"""A04 tests — nested agentOrder: create, validate, persist, keep private.

Local only: no AWS, no deployment. The retail contract is asserted unchanged.
"""

import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("ORDERS_PROJECT_NAME", "mays-orders")
os.environ.setdefault("PRIVACY_INTERNAL_SECRET", "test-secret")

from agent_order import (  # noqa: E402
    AgentOrderValidationError,
    fingerprint,
    validate_agent_order,
)
from errors import OrderError  # noqa: E402
from order_service import OrderService, to_list_item, to_public_order  # noqa: E402
from validation import validate_create_order  # noqa: E402

from identity import OrderIdentity

IDENTITY = OrderIdentity(
    consumer_id="cognito:cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST#client-test",
    owner_type="user", owner_id="user-1", actor_type="user", actor_id="user-1")




class FakeTable:
    def __init__(self):
        self.items = []

    def put_item(self, **kwargs):
        self.items.append(kwargs["Item"])
        return {}

    def get_item(self, **kwargs):
        return {}


AGENT_ORDER = {
    "schemaVersion": "1.0",
    "target": {
        "agentId": "addition_agent",
        "capability": "math.add",
        "agentVersion": "1.0.0",
    },
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
        "parentWorkId": None,
        "executionProfile": "default",
    },
    "resultContract": {
        "schemaVersion": "1.0",
        "format": "json",
        "expectedCapability": "math.add",
        "delivery": "order-result",
    },
}

RETAIL = {
    "customer": {"name": "Max Mustermann", "email": "max@example.com"},
    "items": [{"sku": "SKU-1001", "quantity": 2, "unitPrice": 19}],
    "currency": "EUR",
}


def agent_body(**overrides):
    body = {"orderType": "agent.execution", "agentOrder": json.loads(
        json.dumps(AGENT_ORDER))}
    body.update(overrides)
    return body


class TestAgentOrderValidation(unittest.TestCase):
    def test_valid_agent_order_is_accepted(self):
        out = validate_create_order(agent_body())
        self.assertEqual("agent.execution", out["orderType"])
        self.assertEqual("math.add", out["agentOrder"]["target"]["capability"])

    def test_minimal_agent_order_receives_defaults(self):
        minimal = {
            "orderType": "agent.execution",
            "agentOrder": {
                "schemaVersion": "1.0",
                "target": {"agentId": "addition_agent",
                           "capability": "math.add"},
                "input": {"data": {"left": 17, "right": 25}},
            },
        }
        out = validate_create_order(minimal)
        self.assertEqual("ORDER_CREATED", out["agentOrder"]["processing"]["trigger"])
        self.assertEqual("json", out["agentOrder"]["resultContract"]["format"])

    def test_version_one_is_accepted(self):
        body = agent_body()
        body["agentOrder"]["schemaVersion"] = "1"
        self.assertTrue(validate_create_order(body))

    def test_unknown_version_is_rejected(self):
        body = agent_body()
        body["agentOrder"]["schemaVersion"] = "2.0"
        with self.assertRaises(OrderError):
            validate_create_order(body)

    def test_unknown_field_is_rejected(self):
        body = agent_body()
        body["agentOrder"]["target"]["priority"] = 1
        with self.assertRaises(OrderError):
            validate_create_order(body)

    def test_agent_order_without_order_type_is_rejected(self):
        with self.assertRaises(OrderError):
            validate_create_order({"agentOrder": AGENT_ORDER})

    def test_order_type_without_agent_order_is_rejected(self):
        with self.assertRaises(OrderError):
            validate_create_order({"orderType": "agent.execution"})

    def test_ris_order_v1_description_is_parsed_as_agent_order(self):
        body = {
            "orderType": "agent.execution",
            "orderDescription": json.dumps(AGENT_ORDER),
            "customer": {"name": "Mays", "email": "ops@example.com"},
            "items": [{"sku": "ATS", "quantity": 1, "unitPrice": 100}],
            "currency": "EUR",
        }
        normalized = validate_create_order(body)
        self.assertEqual("addition_agent", normalized["agentOrder"]["target"]["agentId"])
        self.assertEqual(1, len(normalized["items"]))
        self.assertEqual(body["orderDescription"], normalized["orderDescription"])

    def test_order_identity_compatibility_value_is_owner_scoped(self):
        from identity import OwnerIdentity
        alice = OwnerIdentity(
            issuer="https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST",
            subject="alice", client_id="client-a")
        bob = OwnerIdentity(
            issuer=alice.issuer, subject="bob", client_id="client-a")
        self.assertEqual("alice", alice.owner_id)
        self.assertEqual(alice.consumer_id, bob.consumer_id)
        self.assertNotEqual(alice.owner_id, bob.owner_id)

    def test_retail_fields_cannot_be_combined(self):
        body = agent_body()
        body["customer"] = {"name": "x", "email": "x@example.com"}
        with self.assertRaises(OrderError):
            validate_create_order(body)

    def test_unsupported_order_type_is_rejected(self):
        with self.assertRaises(OrderError):
            validate_create_order({"orderType": "retail.order",
                                   "agentOrder": AGENT_ORDER})

    def test_retail_order_stays_valid(self):
        out = validate_create_order(RETAIL)
        self.assertEqual("generic", out["orderType"])
        self.assertNotIn("agentOrder", out)
        self.assertEqual("EUR", out["currency"])

    def test_secret_in_agent_order_is_rejected(self):
        body = agent_body()
        body["agentOrder"]["input"]["data"] = {"api_key": "ris_" + "A" * 47}
        with self.assertRaises(OrderError) as ctx:
            validate_create_order(body)
        self.assertNotIn("ris_", str(ctx.exception))

    def test_oversized_agent_order_is_rejected(self):
        body = agent_body()
        body["agentOrder"]["input"]["data"] = {"blob": "x" * (17 * 1024)}
        with self.assertRaises(OrderError):
            validate_create_order(body)

    def test_fingerprint_is_stable_and_input_sensitive(self):
        first = validate_agent_order(AGENT_ORDER)
        second = validate_agent_order(json.loads(json.dumps(AGENT_ORDER)))
        self.assertEqual(fingerprint(first), fingerprint(second))
        changed = json.loads(json.dumps(AGENT_ORDER))
        changed["input"]["data"]["right"] = 26
        self.assertNotEqual(fingerprint(first),
                            fingerprint(validate_agent_order(changed)))


class TestAgentOrderPersistence(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.service = OrderService("orders-table", client=self.table)

    def test_agent_order_is_persisted_as_own_component(self):
        order = self.service.create_order(agent_body(), subject_id=IDENTITY.owner_id, identity=IDENTITY)
        item = self.table.items[0]
        self.assertEqual("agent.execution", item["orderType"])
        self.assertEqual("math.add", item["agentOrder"]["target"]["capability"])
        self.assertEqual(fingerprint(item["agentOrder"]),
                         item["agentOrderFingerprint"])
        self.assertTrue(item["orderId"].startswith("ord_"))

    def test_no_retail_fields_are_invented(self):
        self.service.create_order(agent_body(), subject_id=IDENTITY.owner_id, identity=IDENTITY)
        item = self.table.items[0]
        for forbidden in ("customer", "items", "currency", "totalAmount"):
            self.assertNotIn(forbidden, item)

    def test_agent_order_is_not_in_the_public_projection(self):
        order = self.service.create_order(agent_body(), subject_id=IDENTITY.owner_id, identity=IDENTITY)
        self.assertNotIn("agentOrder", order)
        self.assertNotIn("agentOrderFingerprint", order)
        self.assertEqual("PENDING", order["status"])

    def test_list_projection_is_minimal_for_agent_orders(self):
        self.service.create_order(agent_body(), subject_id=IDENTITY.owner_id, identity=IDENTITY)
        listed = to_list_item(self.table.items[0])
        self.assertEqual("agent.execution", listed["orderType"])
        self.assertNotIn("customer", listed)
        self.assertNotIn("totalAmount", listed)
        self.assertNotIn("agentOrder", listed)

    def test_retail_order_persistence_is_unchanged(self):
        order = self.service.create_order(RETAIL, subject_id=IDENTITY.owner_id, identity=IDENTITY)
        item = self.table.items[0]
        self.assertEqual("generic", item["orderType"])
        self.assertNotIn("agentOrder", item)
        self.assertEqual(38, item["totalAmount"])
        self.assertEqual("EUR", order["currency"])
        self.assertNotIn("agentOrder", to_public_order(item))


class TestCreateRouteDispatch(unittest.TestCase):
    def setUp(self):
        import index
        self.index = index
        os.environ["ORDERS_TABLE"] = "orders-table"
        self._queue = index.SQS_QUEUE_URL
        self._dispatch_queue = index.ORDER_DISPATCH_QUEUE_URL
        index.SQS_QUEUE_URL = "https://sqs.local/queue"

    def tearDown(self):
        self.index.SQS_QUEUE_URL = self._queue
        self.index.ORDER_DISPATCH_QUEUE_URL = self._dispatch_queue

    def _post(self, order, service_order):
        service = type("S", (), {"create_order": lambda self, body,
                                 subject_id=None, identity=None: service_order})()
        event = {"routeKey": "POST /orders", "body": json.dumps(order)}
        with patch.object(self.index, "create_order_service",
                          return_value=service), \
             patch.object(self.index, "resolve_order_identity_from_event",
                           return_value=IDENTITY), \
             patch.object(self.index, "_send_to_sqs") as send:
            response = self.index.handler(event, None)
        return response, send

    def test_agent_order_is_not_sent_to_the_retail_worker(self):
        response, send = self._post(
            agent_body(),
            {"orderId": "ord_abc123", "orderType": "agent.execution",
             "status": "PENDING"})
        self.assertEqual(201, response["statusCode"])
        send.assert_not_called()

    def test_agent_order_uses_the_bound_dispatch_transport(self):
        service_order = {"orderId": "ord_abc123", "orderType": "agent.execution",
                         "status": "PENDING"}

        class Service:
            def create_order(self, body, *, subject_id, identity):
                return service_order

            def prepare_dispatch(self, order_id, identity):
                return {"orderId": order_id, "workId": "work-bound"}

            def dispatch_envelope(self, order_id, work_id):
                self.envelope = {"orderId": order_id, "execution": {"workId": work_id}}
                return self.envelope

            def mark_dispatch_sent(self, order_id, work_id, message_id):
                self.sent = (order_id, work_id, message_id)

        service = Service()
        sqs = type("SQS", (), {"send_message": lambda self, **kwargs: {
            "MessageId": "sqs-message"}})()
        event = {"routeKey": "POST /orders", "body": json.dumps(agent_body())}
        self.index.ORDER_DISPATCH_QUEUE_URL = "https://sqs.local/ris-dispatch"
        with patch.object(self.index, "create_order_service", return_value=service), \
             patch.object(self.index, "resolve_order_identity_from_event", return_value=IDENTITY), \
             patch.object(self.index, "_get_sqs_client", return_value=sqs), \
             patch.object(self.index, "_send_to_sqs") as retail_send:
            response = self.index.handler(event, None)

        self.assertEqual(201, response["statusCode"])
        retail_send.assert_not_called()
        self.assertEqual(("ord_abc123", "work-bound", "sqs-message"), service.sent)

    def test_retail_order_still_dispatches(self):
        response, send = self._post(
            RETAIL, {"orderId": "ord_abc123", "status": "PENDING"})
        self.assertEqual(201, response["statusCode"])
        send.assert_called_once_with("ord_abc123")


if __name__ == "__main__":
    unittest.main()
