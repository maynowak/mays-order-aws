"""MO-RC4-TESTSUITE-HARDENING-10B — lokaler End-to-End-Komponentenpfad.

Der Test verwendet die produktiven Einstiegspunkte:

    index.handler  -> OrderService -> FakeDynamoDB
                                 -> FakeSQS
    sqs_handler.handler -> FakeDynamoDB

API- und Worker-Pfad teilen denselben In-Memory-Zustand. Es gibt keinen
boto3-Aufruf, keine Queue und keine echte Tabelle.
"""

from __future__ import annotations

import copy
import json
import os
import re
import unittest
from contextlib import ExitStack
from unittest import mock

import index
import order_service
import sqs_handler
from order_handlers import register

TABLE_NAME = "mays-orders-component-test"
SQS_URL = "https://sqs.local/000000000000/mays-orders-component-test"
SUBJECT_A = "user-a"
SUBJECT_B = "user-b"
ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_COMPONENT"
CLIENT_ID = "component-client"
FAIL_ORDER_TYPE = "test.component.handler-failure"

PAYLOAD = {
    "customer": {"name": "Ada Lovelace", "email": "ada@example.test"},
    "items": [{"sku": "SKU-1", "quantity": 2, "unitPrice": 100}],
    "currency": "EUR",
}


class FakeClientError(Exception):
    def __init__(self, code="ConditionalCheckFailedException"):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def _native(value):
    """Convert DynamoDB attribute values (client API) to Python values."""
    if not isinstance(value, dict):
        return value
    if "S" in value:
        return value["S"]
    if "N" in value:
        return int(value["N"]) if "." not in value["N"] else float(value["N"])
    if "BOOL" in value:
        return value["BOOL"]
    if "NULL" in value:
        return None
    if "M" in value:
        return {key: _native(entry) for key, entry in value["M"].items()}
    if "L" in value:
        return [_native(entry) for entry in value["L"]]
    raise AssertionError(f"unsupported DynamoDB value: {value}")


def _typed(value):
    """Convert one Python value to a DynamoDB attribute value (client API)."""
    if isinstance(value, dict):
        return {"M": {key: _typed(entry) for key, entry in value.items()}}
    if isinstance(value, list):
        return {"L": [_typed(entry) for entry in value]}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, (int, float)):
        return {"N": str(value)}
    if value is None:
        return {"NULL": True}
    if isinstance(value, str):
        return {"S": value}
    raise AssertionError(f"unsupported Python value: {type(value).__name__}")


def _typed_item(item):
    """Convert a canonical item to the low-level client's item shape."""
    return {key: _typed(value) for key, value in item.items()}


def _field(token, names):
    key = token.strip()
    return names.get(key, key)


def _condition_ok(item, expression, names, values):
    """Evaluate the small ConditionExpression subset used by RC4.

    Unsupported expressions fail loudly instead of silently succeeding.
    """
    if item is None:
        return False
    resolved = expression
    for alias, field in (names or {}).items():
        resolved = resolved.replace(alias, field)

    for raw_clause in resolved.split(" AND "):
        clause = raw_clause.strip()
        while clause.startswith("(") and clause.endswith(")"):
            clause = clause[1:-1].strip()

        match = re.fullmatch(r"attribute_exists\(([^)]+)\)", clause)
        if match:
            if match.group(1).strip() not in item:
                return False
            continue
        match = re.fullmatch(r"attribute_not_exists\(([^)]+)\)", clause)
        if match:
            if match.group(1).strip() in item:
                return False
            continue

        for operator in ("<>", ">=", "<=", "=", ">", "<"):
            marker = f" {operator} "
            if marker not in clause:
                continue
            field, token = clause.split(marker, 1)
            field = _field(field, names)
            actual = item.get(field)
            expected = values[token.strip()]
            if operator == "=":
                ok = actual == expected
            elif operator == "<>":
                ok = actual != expected
            elif operator == ">":
                ok = actual is not None and actual > expected
            elif operator == "<":
                ok = actual is not None and actual < expected
            elif operator == ">=":
                ok = actual is not None and actual >= expected
            else:
                ok = actual is not None and actual <= expected
            if not ok:
                return False
            break
        else:
            raise AssertionError(f"unsupported ConditionExpression clause: {clause}")
    return True


def _split_top_level(expression):
    parts = []
    depth = 0
    start = 0
    for position, character in enumerate(expression):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(expression[start:position].strip())
            start = position + 1
    parts.append(expression[start:].strip())
    return [part for part in parts if part]


def _rhs_value(rhs, item, names, values):
    rhs = rhs.strip()
    match = re.fullmatch(
        r"if_not_exists\(([^,]+),\s*(:[A-Za-z0-9_]+)\)(?:\s*\+\s*(:[A-Za-z0-9_]+))?",
        rhs,
    )
    if match:
        field = _field(match.group(1), names)
        current = item.get(field)
        if current is None:
            current = values[match.group(2)]
        if match.group(3):
            current += values[match.group(3)]
        return current
    if rhs in values:
        return values[rhs]
    raise AssertionError(f"unsupported update value: {rhs}")


def _apply_update(item, expression, names, values):
    set_part, _, remove_part = expression.partition(" REMOVE ")
    if set_part.startswith("SET "):
        set_part = set_part[4:]

    if set_part.strip():
        for assignment in _split_top_level(set_part):
            field_token, separator, rhs = assignment.partition(" = ")
            if not separator:
                raise AssertionError(f"unsupported SET assignment: {assignment}")
            item[_field(field_token, names)] = _rhs_value(rhs, item, names, values)

    if remove_part.strip():
        for field_token in remove_part.split(","):
            item.pop(_field(field_token, names), None)


class FakeDynamoStore:
    """Shared canonical item store for the table and client adapters."""

    def __init__(self):
        self.items = {}
        self.fail_get = None
        self.force_conditional_failure = False

    @staticmethod
    def key(pk, sk):
        return (pk, sk)

    def put(self, item):
        stored = copy.deepcopy(item)
        self.items[self.key(stored["pk"], stored["sk"])] = stored

    def get(self, pk, sk):
        if self.fail_get is not None:
            error, self.fail_get = self.fail_get, None
            raise error
        item = self.items.get(self.key(pk, sk))
        return copy.deepcopy(item) if item is not None else None

    def update(
        self,
        pk,
        sk,
        *,
        update_expression,
        condition_expression=None,
        names=None,
        values=None,
        return_values=None,
    ):
        item = self.items.get(self.key(pk, sk))
        if self.force_conditional_failure:
            self.force_conditional_failure = False
            raise FakeClientError()
        if condition_expression and not _condition_ok(
            item, condition_expression, names or {}, values or {}
        ):
            raise FakeClientError()
        if item is None:
            raise FakeClientError()
        _apply_update(item, update_expression, names or {}, values or {})
        copied = copy.deepcopy(item)
        if return_values == "ALL_NEW":
            return {"Attributes": copied}
        return {}


class FakeTable:
    """boto3 resource Table-compatible adapter (native values)."""

    def __init__(self, store):
        self.store = store

    def put_item(self, Item):
        self.store.put(Item)
        return {}

    def get_item(self, Key, ConsistentRead=True):
        item = self.store.get(Key["pk"], Key["sk"])
        return {"Item": item} if item is not None else {}

    def update_item(
        self,
        Key,
        UpdateExpression,
        ConditionExpression=None,
        ExpressionAttributeNames=None,
        ExpressionAttributeValues=None,
        ReturnValues=None,
    ):
        values = {
            key: _native(value) for key, value in (ExpressionAttributeValues or {}).items()
        }
        return self.store.update(
            Key["pk"],
            Key["sk"],
            update_expression=UpdateExpression,
            condition_expression=ConditionExpression,
            names=ExpressionAttributeNames,
            values=values,
            return_values=ReturnValues,
        )


class FakeClient:
    """boto3 low-level DynamoDB-client-compatible adapter (typed values)."""

    def __init__(self, store):
        self.store = store

    def get_item(self, TableName, Key, ConsistentRead=True):
        pk = Key["pk"]["S"]
        sk = Key["sk"]["S"]
        item = self.store.get(pk, sk)
        return {"Item": _typed_item(item)} if item is not None else {}

    def update_item(
        self,
        TableName,
        Key,
        UpdateExpression,
        ConditionExpression=None,
        ExpressionAttributeNames=None,
        ExpressionAttributeValues=None,
        ReturnValues=None,
    ):
        values = {
            key: _native(value) for key, value in (ExpressionAttributeValues or {}).items()
        }
        return self.store.update(
            Key["pk"]["S"],
            Key["sk"]["S"],
            update_expression=UpdateExpression,
            condition_expression=ConditionExpression,
            names=ExpressionAttributeNames,
            values=values,
            return_values=ReturnValues,
        )


class FakeResource:
    def __init__(self, store):
        self.table_names = []
        self.table = FakeTable(store)

    def Table(self, name):
        self.table_names.append(name)
        return self.table


class FakeSQS:
    def __init__(self):
        self.messages = []

    def send_message(self, QueueUrl, MessageBody, MessageAttributes=None):
        message_id = f"message-{len(self.messages) + 1}"
        self.messages.append(
            {
                "messageId": message_id,
                "body": MessageBody,
                "attributes": MessageAttributes or {},
                "queue_url": QueueUrl,
            }
        )
        return {"MessageId": message_id}

    def records(self):
        return [
            {"messageId": message["messageId"], "body": message["body"]}
            for message in self.messages
        ]


def _event(method, *, payload=None, order_id=None, sub=SUBJECT_A):
    route = method
    event = {
        "routeKey": route,
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": sub,
                        "iss": ISSUER,
                        "client_id": CLIENT_ID,
                    }
                }
            }
        },
    }
    if payload is not None:
        event["body"] = json.dumps(payload)
    if order_id is not None:
        event["pathParameters"] = {"orderId": order_id}
    return event


def call_api(
    store,
    sqs,
    *,
    method="POST /orders",
    payload=None,
    order_id=None,
    sub=SUBJECT_A,
):
    resource = FakeResource(store)
    with ExitStack() as stack:
        stack.enter_context(
            mock.patch.object(order_service, "_get_dynamodb_resource", return_value=resource)
        )
        stack.enter_context(mock.patch.object(index, "_get_sqs_client", return_value=sqs))
        stack.enter_context(mock.patch.object(index, "SQS_QUEUE_URL", SQS_URL))
        stack.enter_context(
            mock.patch.dict(
                os.environ,
                {"ORDERS_TABLE": TABLE_NAME, "SQS_QUEUE_URL": SQS_URL},
                clear=False,
            )
        )
        return index.handler(
            _event(method, payload=payload, order_id=order_id, sub=sub), None
        )


def call_worker(store, record):
    with ExitStack() as stack:
        stack.enter_context(
            mock.patch.object(sqs_handler, "_get_dynamodb_client", return_value=FakeClient(store))
        )
        stack.enter_context(
            mock.patch.dict(os.environ, {"ORDERS_TABLE": TABLE_NAME}, clear=False)
        )
        return sqs_handler.handler({"Records": [record]}, None)


def _json_body(response):
    return json.loads(response["body"])


def _record(order_id, status="CONFIRMED", message_id="worker-message"):
    return {
        "messageId": message_id,
        "body": json.dumps({"orderId": order_id, "status": status}),
    }


class TestOrderProcessingComponent(unittest.TestCase):
    def setUp(self):
        self.store = FakeDynamoStore()
        self.sqs = FakeSQS()

    def _create(self, *, sub=SUBJECT_A, payload=None):
        response = call_api(
            self.store,
            self.sqs,
            payload=payload or dict(PAYLOAD),
            sub=sub,
        )
        self.assertEqual(response["statusCode"], 201, response)
        return _json_body(response)

    def _stored(self, order_id):
        return self.store.get(f"ord_{order_id}", "#ORDER")

    # T10B-01 ---------------------------------------------------------------
    def test_t10b_01_creation_persists_and_publishes(self):
        order = self._create()

        self.assertTrue(order["orderId"].startswith("ord_"))
        self.assertEqual(order["status"], "PENDING")
        self.assertEqual(order["totalAmount"], 200)
        self.assertNotIn("subjectId", order)

        item = self._stored(order["orderId"])
        self.assertIsNotNone(item)
        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(item["version"], 1)
        self.assertEqual(item["subjectId"], SUBJECT_A)
        self.assertEqual(item["gsi2pk"], f"SUBJECT#{SUBJECT_A}")
        self.assertEqual(item["deliveryState"], "sent")
        self.assertEqual(item["deliveryAttempts"], 1)
        self.assertEqual(len(self.sqs.messages), 1)

        message = json.loads(self.sqs.messages[0]["body"])
        self.assertEqual(message["orderId"], order["orderId"])
        self.assertEqual(message["status"], "CONFIRMED")
        self.assertEqual(
            self.sqs.messages[0]["attributes"]["orderId"]["StringValue"],
            order["orderId"],
        )

    def test_rc3_legacy_payload_without_order_type_keeps_contract(self):
        """RC3 body without orderType remains valid and maps to generic."""
        order = self._create(payload=dict(PAYLOAD))
        item = self._stored(order["orderId"])

        self.assertEqual(item["orderType"], "generic")
        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(item["subjectId"], SUBJECT_A)
        self.assertEqual(order["currency"], "EUR")
        self.assertEqual(order["totalAmount"], 200)
        for internal in ("subjectId", "consumerId", "version", "pk", "sk"):
            self.assertNotIn(internal, order)
        self.assertEqual(len(self.sqs.messages), 1)

    def test_rc4_namespaced_unknown_type_fails_closed_without_status_write(self):
        """A valid namespaced orderType without a registered handler stays pending."""
        order = self._create(
            payload={**PAYLOAD, "orderType": "ris.document.analyze"}
        )
        self.assertEqual(
            self._stored(order["orderId"])["orderType"], "ris.document.analyze"
        )

        result = call_worker(self.store, _record(order["orderId"]))

        self.assertEqual(
            result, {"batchItemFailures": [{"itemIdentifier": "worker-message"}]}
        )
        item = self._stored(order["orderId"])
        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(item["version"], 1)

    # T10B-02 ---------------------------------------------------------------
    def test_t10b_02_worker_transitions_shared_state(self):
        order = self._create()
        record = self.sqs.records()[0]

        result = call_worker(self.store, record)

        self.assertEqual(result, {"batchItemFailures": []})
        item = self._stored(order["orderId"])
        self.assertEqual(item["status"], "CONFIRMED")
        self.assertEqual(item["version"], 2)
        self.assertEqual(item["deliveryState"], "sent")

        response = call_api(
            self.store,
            self.sqs,
            method="GET /orders/{orderId}",
            order_id=order["orderId"],
        )
        self.assertEqual(response["statusCode"], 200, response)
        self.assertEqual(_json_body(response)["status"], "CONFIRMED")

    # T10B-03 ---------------------------------------------------------------
    def test_t10b_03_repeated_api_requests_are_distinct_orders(self):
        # RC4 hat keinen vom Client gelieferten Idempotency-Key. Gleiche
        # Payloads sind daher zwei gueltige, getrennte Bestellungen; eine
        # automatische API-Deduplizierung darf nicht vorgetaeuscht werden.
        first = self._create()
        second = self._create()

        self.assertNotEqual(first["orderId"], second["orderId"])
        self.assertEqual(len(self.store.items), 2)
        self.assertEqual(len(self.sqs.messages), 2)
        self.assertEqual(self._stored(first["orderId"])["version"], 1)
        self.assertEqual(self._stored(second["orderId"])["version"], 1)

    def test_t10b_03_duplicate_worker_delivery_is_idempotent(self):
        order = self._create()
        record = _record(order["orderId"])

        first = call_worker(self.store, record)
        second = call_worker(self.store, record)

        self.assertEqual(first, {"batchItemFailures": []})
        self.assertEqual(second, {"batchItemFailures": []})
        item = self._stored(order["orderId"])
        self.assertEqual(item["status"], "CONFIRMED")
        self.assertEqual(item["version"], 2)

    def test_t10b_03_conditional_conflict_does_not_write_or_increment(self):
        order = self._create()
        self.store.force_conditional_failure = True

        result = call_worker(self.store, _record(order["orderId"]))

        self.assertEqual(
            result, {"batchItemFailures": [{"itemIdentifier": "worker-message"}]}
        )
        item = self._stored(order["orderId"])
        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(item["version"], 1)

    # T10B-04 ---------------------------------------------------------------
    def test_t10b_04_invalid_messages_return_retry_signal_without_mutation(self):
        malformed = call_worker(
            self.store, {"messageId": "bad-json", "body": "not-json"}
        )
        missing_fields = call_worker(
            self.store,
            {"messageId": "missing", "body": json.dumps({"orderId": "ord_x"})},
        )

        self.assertEqual(
            malformed, {"batchItemFailures": [{"itemIdentifier": "bad-json"}]}
        )
        self.assertEqual(
            missing_fields, {"batchItemFailures": [{"itemIdentifier": "missing"}]}
        )
        self.assertEqual(self.store.items, {})

    def test_t10b_04_repository_failure_returns_retry_signal(self):
        order = self._create()
        self.store.fail_get = RuntimeError("temporary repository failure")

        result = call_worker(self.store, _record(order["orderId"]))

        self.assertEqual(
            result, {"batchItemFailures": [{"itemIdentifier": "worker-message"}]}
        )
        item = self._stored(order["orderId"])
        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(item["version"], 1)

    def test_t10b_04_handler_failure_returns_retry_signal_without_status_write(self):
        @register(FAIL_ORDER_TYPE)
        def failing_handler(order, payload):
            raise RuntimeError("controlled handler failure")

        order = self._create(payload={**PAYLOAD, "orderType": FAIL_ORDER_TYPE})

        result = call_worker(self.store, _record(order["orderId"]))

        self.assertEqual(
            result, {"batchItemFailures": [{"itemIdentifier": "worker-message"}]}
        )
        item = self._stored(order["orderId"])
        self.assertEqual(item["status"], "PENDING")
        self.assertEqual(item["version"], 1)

    # T10B-05 ---------------------------------------------------------------
    def test_t10b_05_body_subject_override_is_rejected(self):
        response = call_api(
            self.store,
            self.sqs,
            payload={**PAYLOAD, "subjectId": SUBJECT_B},
        )

        self.assertEqual(response["statusCode"], 400, response)
        self.assertEqual(self.store.items, {})
        self.assertEqual(self.sqs.messages, [])

    def test_t10b_05_foreign_identity_gets_404_but_owner_gets_order(self):
        order = self._create(sub=SUBJECT_A)
        item = self._stored(order["orderId"])
        self.assertEqual(item["subjectId"], SUBJECT_A)
        self.assertEqual(item["ownerId"], SUBJECT_A)
        self.assertEqual(item["actorId"], SUBJECT_A)
        self.assertEqual(
            item["consumerId"],
            "cognito:cognito-idp.eu-central-1.amazonaws.com/"
            f"eu-central-1_COMPONENT#{CLIENT_ID}",
        )

        foreign = call_api(
            self.store,
            self.sqs,
            method="GET /orders/{orderId}",
            order_id=order["orderId"],
            sub=SUBJECT_B,
        )
        owner = call_api(
            self.store,
            self.sqs,
            method="GET /orders/{orderId}",
            order_id=order["orderId"],
            sub=SUBJECT_A,
        )

        self.assertEqual(foreign["statusCode"], 404, foreign)
        self.assertEqual(owner["statusCode"], 200, owner)
        self.assertEqual(_json_body(owner)["orderId"], order["orderId"])
        self.assertEqual(_json_body(owner)["status"], "PENDING")

    # T10B-06 ---------------------------------------------------------------
    def test_t10b_06_invalid_transition_is_rejected_and_valid_transition_is_versioned(self):
        order = self._create()

        invalid = call_worker(
            self.store, _record(order["orderId"], status="SHIPPED", message_id="invalid")
        )
        self.assertEqual(
            invalid, {"batchItemFailures": [{"itemIdentifier": "invalid"}]}
        )
        self.assertEqual(self._stored(order["orderId"])["status"], "PENDING")
        self.assertEqual(self._stored(order["orderId"])["version"], 1)

        valid = call_worker(
            self.store, _record(order["orderId"], status="CONFIRMED", message_id="valid")
        )
        self.assertEqual(valid, {"batchItemFailures": []})
        self.assertEqual(self._stored(order["orderId"])["status"], "CONFIRMED")
        self.assertEqual(self._stored(order["orderId"])["version"], 2)

        # A repeat is idempotent: no second status change and no version bump.
        repeated = call_worker(
            self.store, _record(order["orderId"], status="CONFIRMED", message_id="repeat")
        )
        self.assertEqual(repeated, {"batchItemFailures": []})
        self.assertEqual(self._stored(order["orderId"])["version"], 2)

        response = call_api(
            self.store,
            self.sqs,
            method="GET /orders/{orderId}",
            order_id=order["orderId"],
        )
        self.assertEqual(response["statusCode"], 200, response)
        self.assertEqual(_json_body(response)["status"], "CONFIRMED")


if __name__ == "__main__":
    unittest.main()
