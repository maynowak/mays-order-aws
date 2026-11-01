import base64
import json
import unittest
from contextlib import contextmanager
from decimal import Decimal
from unittest import mock

import index
from errors import order_not_found


class FakeService:
    def __init__(self, create=None, get=None, list_orders=None, update=None):
        self.create_order = create or (
            lambda raw, subject_id=None, identity=None: {"orderId": "ord_1", "status": "PENDING"}
        )
        self.mark_delivery_state = lambda order_id, state: None
        self.get_order = get or (lambda order_id: {"orderId": order_id, "status": "PENDING"})
        self.list_orders = list_orders or (
            lambda limit, next_token=None: {"orders": [], "count": 0}
        )
        self.update_order_status = update or (
            lambda order_id, status: {"orderId": order_id, "status": status}
        )


ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TESTPOOL"
CLIENT_ID = "test-client-id"


def auth_event(route_key, sub="user-123", iss=ISSUER, client_id=CLIENT_ID, **extra):
    """Event mit verifiziertem JWT-Kontext (HTTP API v2, Payload 2.0).

    `iss` + `client_id` bilden den Consumer-Namensraum (MO-RC4-P02A).
    """
    claims = {"sub": sub}
    if iss is not None:
        claims["iss"] = iss
    if client_id is not None:
        claims["client_id"] = client_id
    event = {
        "routeKey": route_key,
        "requestContext": {"authorizer": {"jwt": {"claims": claims}}},
    }
    event.update(extra)
    return event


@contextmanager
def patch_service(fake):
    with mock.patch("index.create_order_service", return_value=fake), mock.patch.dict(
        "index.os.environ", {"ORDERS_TABLE": "mays-orders"}
    ):
        yield


class TestHandlerConfig(unittest.TestCase):
    def test_missing_orders_table_returns_500(self):
        with mock.patch.dict("index.os.environ", {"ORDERS_TABLE": ""}):
            response = index.handler({"routeKey": "GET /orders"}, None)
        self.assertEqual(response["statusCode"], 500)
        body = json.loads(response["body"])
        self.assertEqual(body["error"]["code"], "INTERNAL_ERROR")


class TestHandlerRoutes(unittest.TestCase):
    def test_post_orders_returns_201_and_parses_body(self):
        captured = {}

        def create(raw, subject_id=None, identity=None):
            captured["raw"] = raw
            captured["subject_id"] = subject_id
            return {"orderId": "ord_1", "status": "PENDING", "totalAmount": 2000}

        fake = FakeService(create=create)
        with patch_service(fake):
            response = index.handler(
                auth_event(
                    "POST /orders",
                    sub="user-abc",
                    body=json.dumps(
                        {
                            "customer": {"name": "Max", "email": "max@example.com"},
                            "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 2000}],
                            "currency": "EUR",
                        }
                    ),
                ),
                None,
            )
        self.assertEqual(response["statusCode"], 201)
        self.assertEqual(captured["raw"]["customer"]["name"], "Max")
        # MO-RC4-P02: Eigentuemer stammt aus dem JWT-Kontext
        self.assertEqual(captured["subject_id"], "user-abc")

    def test_post_orders_decodes_base64_body(self):
        captured = {}

        def create(raw, subject_id=None, identity=None):
            captured["raw"] = raw
            return {"orderId": "ord_1", "status": "PENDING"}

        fake = FakeService(create=create)
        payload = json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                              "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 2000}],
                              "currency": "EUR"})
        with patch_service(fake):
            index.handler(
                auth_event(
                    "POST /orders",
                    body=base64.b64encode(payload.encode("utf-8")).decode("utf-8"),
                    isBase64Encoded=True,
                ),
                None,
            )
        self.assertEqual(captured["raw"]["customer"]["name"], "Max")

    def test_post_orders_invalid_json_returns_400(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler(auth_event("POST /orders", body="not json"), None)
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "VALIDATION_ERROR")

    def test_get_orders_returns_200_with_list(self):
        captured = {}

        def list_orders(limit, next_token=None):
            captured["limit"] = limit
            captured["next_token"] = next_token
            return {"orders": [], "count": 0}

        fake = FakeService(list_orders=list_orders)
        with patch_service(fake):
            response = index.handler(
                {"routeKey": "GET /orders", "queryStringParameters": {"limit": "10", "nextToken": "abc"}},
                None,
            )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(captured["limit"], 10)
        self.assertEqual(captured["next_token"], "abc")

    def test_get_orders_invalid_limit_returns_400(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler(
                {"routeKey": "GET /orders", "queryStringParameters": {"limit": "abc"}},
                None,
            )
        self.assertEqual(response["statusCode"], 400)

    def test_get_order_returns_200(self):
        fake = FakeService(get=lambda order_id: {"orderId": order_id, "status": "PENDING"})
        with patch_service(fake):
            response = index.handler(
                {"routeKey": "GET /orders/{orderId}", "pathParameters": {"orderId": "ord_abc"}},
                None,
            )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["orderId"], "ord_abc")

    def test_get_order_invalid_id_returns_400(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler(
                {"routeKey": "GET /orders/{orderId}", "pathParameters": {"orderId": "order-123"}},
                None,
            )
        self.assertEqual(response["statusCode"], 400)

    def test_patch_status_returns_200(self):
        captured = {}

        def update(order_id, status):
            captured["status"] = status
            return {"orderId": order_id, "status": status}

        fake = FakeService(update=update)
        with patch_service(fake):
            response = index.handler(
                {
                    "routeKey": "PATCH /orders/{orderId}/status",
                    "pathParameters": {"orderId": "ord_abc"},
                    "body": json.dumps({"status": "CONFIRMED"}),
                },
                None,
            )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(captured["status"], "CONFIRMED")

    def test_patch_status_invalid_body_returns_400(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler(
                {
                    "routeKey": "PATCH /orders/{orderId}/status",
                    "pathParameters": {"orderId": "ord_abc"},
                    "body": json.dumps({}),
                },
                None,
            )
        self.assertEqual(response["statusCode"], 400)

    def test_route_key_fallback_http_method_and_path(self):
        captured = {}

        def list_orders(limit, next_token=None):
            captured["called"] = True
            return {"orders": [], "count": 0}

        fake = FakeService(list_orders=list_orders)
        with patch_service(fake):
            response = index.handler({"httpMethod": "GET", "rawPath": "/orders"}, None)
        self.assertEqual(response["statusCode"], 200)
        self.assertTrue(captured["called"])

    def test_unsupported_route_returns_400(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler({"routeKey": "DELETE /orders/1"}, None)
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "VALIDATION_ERROR")


class TestDecimalSerialization(unittest.TestCase):
    def test_ok_serializes_decimal_as_float(self):
        payload = {"orderId": "ord_1", "totalAmount": Decimal("29.99"), "quantity": Decimal("2")}
        result = index.ok(200, payload)
        body = json.loads(result["body"])
        self.assertEqual(body["orderId"], "ord_1")
        self.assertEqual(body["totalAmount"], 29.99)
        self.assertEqual(body["quantity"], 2.0)

    def test_ok_serializes_nested_decimal(self):
        payload = {"order": {"amount": Decimal("10.5")}, "list": [Decimal("1"), Decimal("2")]}
        result = index.ok(200, payload)
        body = json.loads(result["body"])
        self.assertEqual(body["order"]["amount"], 10.5)
        self.assertEqual(body["list"], [1.0, 2.0])

class TestHandlerErrors(unittest.TestCase):
    def test_order_error_mapped_to_status_code(self):
        def get_missing(order_id):
            raise order_not_found(order_id)

        fake = FakeService(get=get_missing)
        with patch_service(fake):
            response = index.handler(
                {"routeKey": "GET /orders/{orderId}", "pathParameters": {"orderId": "ord_missing"}},
                None,
            )
        self.assertEqual(response["statusCode"], 404)
        body = json.loads(response["body"])
        self.assertEqual(body["error"]["code"], "ORDER_NOT_FOUND")

    def test_unexpected_error_maps_to_500(self):
        def create_boom(raw, subject_id=None, identity=None):
            raise RuntimeError("boom")

        fake = FakeService(create=create_boom)
        with patch_service(fake):
            response = index.handler(
                auth_event(
                    "POST /orders",
                    body=json.dumps({"customer": {}, "items": [], "currency": ""}),
                ),
                None,
            )
        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "INTERNAL_ERROR")


if __name__ == "__main__":
    unittest.main()

class TestHandlerDecimalRegression(unittest.TestCase):
    """MAYS-ORDERS-PRIVACY-RUNTIME-FIX-01: GET/LIST mit DynamoDB-Decimal."""

    def test_get_order_with_decimal_returns_200(self):
        fake = FakeService(get=lambda order_id: {"orderId": order_id, "status": "PENDING", "totalAmount": Decimal("39.98")})
        with patch_service(fake):
            response = index.handler(
                {"routeKey": "GET /orders/{orderId}", "pathParameters": {"orderId": "ord_1"}},
                None,
            )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["totalAmount"], 39.98)

    def test_list_orders_with_decimal_returns_200(self):
        fake = FakeService(list_orders=lambda limit, next_token=None: {"orders": [{"orderId": "ord_1", "totalAmount": Decimal("10")}], "count": 1})
        with patch_service(fake):
            response = index.handler({"routeKey": "GET /orders", "queryStringParameters": {}}, None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["orders"][0]["totalAmount"], 10.0)


class TestInternalPrivacyDispatch(unittest.TestCase):
    """Interner Aufrufweg: direkter Invoke, keine öffentliche Route."""

    def test_unknown_internal_action_rejected(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler({"internalAction": "privacy/drop-all"}, None)
        self.assertEqual(response["statusCode"], 400)

    def test_inspect_dispatches_with_auth_context(self):
        seen = {}

        class Svc(FakeService):
            def inspect_subject(self, subject_id, context=None):
                seen["subject"] = subject_id
                seen["context"] = context
                return {"subjectId": subject_id, "status": "COMPLETED", "affectedRecords": 0}

        with patch_service(Svc()):
            response = index.handler(
                {"internalAction": "privacy/inspect",
                 "payload": {"subjectId": "user-1"},
                 "authContext": {"project": "mays-orders", "authorized": True}},
                None,
            )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(seen["subject"], "user-1")
        self.assertEqual(json.loads(response["body"])["status"], "COMPLETED")

    def test_auth_failure_maps_to_error(self):
        def inspect_boom(subject_id, context=None):
            from errors import validation_error as ve
            raise ve("Unauthorized privacy operation")

        fake = FakeService()
        fake.inspect_subject = inspect_boom
        with patch_service(fake):
            response = index.handler(
                {"internalAction": "privacy/inspect",
                 "payload": {"subjectId": "user-1"},
                 "authContext": {}},
                None,
            )
        self.assertEqual(response["statusCode"], 400)


class TestOrderOwnership(unittest.TestCase):
    """MO-RC4-P02: Eigentuemer kommt ausschliesslich aus dem verifizierten JWT."""

    def test_post_without_authorizer_is_rejected(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler(
                {
                    "routeKey": "POST /orders",
                    "body": json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                                        "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
                                        "currency": "EUR"}),
                },
                None,
            )
        self.assertEqual(response["statusCode"], 401)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "UNAUTHORIZED")

    def test_post_with_blank_subject_is_rejected(self):
        for blank in ("", "   "):
            with self.subTest(sub=repr(blank)):
                fake = FakeService()
                with patch_service(fake):
                    response = index.handler(
                        auth_event("POST /orders", sub=blank,
                                   body=json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                                                    "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
                                                    "currency": "EUR"})),
                        None,
                    )
                self.assertEqual(response["statusCode"], 401)

    def test_post_with_malformed_subject_is_rejected(self):
        cases = ("x" * 257, "user\x00id", "user\nid")
        for bad in cases:
            with self.subTest(sub=repr(bad)):
                fake = FakeService()
                with patch_service(fake):
                    response = index.handler(
                        auth_event("POST /orders", sub=bad,
                                   body=json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                                                    "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
                                                    "currency": "EUR"})),
                        None,
                    )
                self.assertEqual(response["statusCode"], 401)

    def test_body_subject_id_cannot_override_jwt(self):
        captured_subject = {}

        def create(raw, subject_id=None, identity=None):
            captured_subject["value"] = subject_id
            return {"orderId": "ord_1", "status": "PENDING"}

        fake = FakeService(create=create)
        with patch_service(fake):
            response = index.handler(
                auth_event(
                    "POST /orders",
                    sub="real-user",
                    body=json.dumps({
                        "customer": {"name": "Max", "email": "max@example.com"},
                        "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
                        "currency": "EUR",
                        "subjectId": "attacker",
                    }),
                ),
                None,
            )
        # Der Handler uebernimmt ausschliesslich den JWT-Wert; das Body-Feld
        # wird nie als Eigentuemer verwendet (Ablehnung erfolgt im Service-
        # Validator, siehe test_order_service).
        self.assertEqual(response["statusCode"], 201)
        self.assertEqual(captured_subject["value"], "real-user")

    def test_flat_authorizer_claims_are_accepted(self):
        captured = {}

        def create(raw, subject_id=None, identity=None):
            captured["subject_id"] = subject_id
            return {"orderId": "ord_1", "status": "PENDING"}

        fake = FakeService(create=create)
        with patch_service(fake):
            response = index.handler(
                {
                    "routeKey": "POST /orders",
                    "requestContext": {"authorizer": {"sub": "flat-user", "iss": ISSUER,
                                                     "client_id": CLIENT_ID}},
                    "body": json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                                        "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
                                        "currency": "EUR"}),
                },
                None,
            )
        self.assertEqual(response["statusCode"], 201)
        self.assertEqual(captured["subject_id"], "flat-user")

    def test_get_orders_does_not_require_authorizer(self):
        """Lesende Routen bleiben unveraendert (keine Regressionswirkung)."""
        fake = FakeService()
        with patch_service(fake):
            response = index.handler({"routeKey": "GET /orders"}, None)
        self.assertEqual(response["statusCode"], 200)


class TestIdentityResolutionP02A(unittest.TestCase):
    """MO-RC4-P02A: Consumer-Namensraum + Owner/Actor-Trennung im Handler."""

    BODY = json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                       "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
                       "currency": "EUR"})

    def test_missing_consumer_identity_is_rejected(self):
        for kwargs in ({"iss": None}, {"client_id": None}):
            with self.subTest(kwargs=kwargs):
                fake = FakeService()
                with patch_service(fake):
                    response = index.handler(
                        auth_event("POST /orders", body=self.BODY, **kwargs), None
                    )
                self.assertEqual(response["statusCode"], 401)
                self.assertEqual(json.loads(response["body"])["error"]["code"], "UNAUTHORIZED")

    def test_identity_with_consumer_and_separated_actor_is_passed(self):
        captured = {}

        def create(raw, subject_id=None, identity=None):
            captured["subject_id"] = subject_id
            captured["identity"] = identity
            return {"orderId": "ord_1", "status": "PENDING"}

        fake = FakeService(create=create)
        with patch_service(fake):
            response = index.handler(
                auth_event("POST /orders", sub="user-42", body=self.BODY), None
            )

        self.assertEqual(response["statusCode"], 201)
        identity = captured["identity"]
        self.assertEqual(captured["subject_id"], "user-42")
        self.assertEqual(identity.consumer_id,
                         "cognito:cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TESTPOOL"
                         "#test-client-id")
        self.assertEqual(identity.owner_id, "user-42")
        self.assertEqual(identity.actor_id, "user-42")
        self.assertEqual(identity.owner_type, "user")

    def test_aud_claim_is_accepted_as_consumer_client(self):
        captured = {}

        def create(raw, subject_id=None, identity=None):
            captured["identity"] = identity
            return {"orderId": "ord_1", "status": "PENDING"}

        fake = FakeService(create=create)
        with patch_service(fake):
            response = index.handler(
                {
                    "routeKey": "POST /orders",
                    "requestContext": {"authorizer": {"jwt": {"claims": {
                        "sub": "user-42", "iss": ISSUER, "aud": "aud-client",
                    }}}},
                    "body": self.BODY,
                },
                None,
            )
        self.assertEqual(response["statusCode"], 201)
        self.assertTrue(captured["identity"].consumer_id.endswith("#aud-client"))


class TestDeliveryMarkingP02F(unittest.TestCase):
    """MO-RC4-P02F: POST vermerkt den Zustellausgang (best effort)."""

    BODY = json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                       "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
                       "currency": "EUR"})

    def _run(self, send_ok):
        marked = []

        def create(raw, subject_id=None, identity=None):
            return {"orderId": "ord_1", "status": "PENDING"}

        fake = FakeService(create=create)
        fake.mark_delivery_state = lambda order_id, state: marked.append((order_id, state))
        with patch_service(fake), \
             mock.patch.object(index, "SQS_QUEUE_URL", "https://sqs/queue"), \
             mock.patch.object(index, "_send_to_sqs", return_value=send_ok):
            response = index.handler(auth_event("POST /orders", body=self.BODY), None)
        return response, marked

    def test_successful_delivery_is_marked_sent(self):
        response, marked = self._run(True)
        self.assertEqual(response["statusCode"], 201)
        self.assertEqual(marked, [("ord_1", "sent")])

    def test_failed_delivery_is_marked_failed(self):
        response, marked = self._run(False)
        self.assertEqual(response["statusCode"], 201)  # API-Vertrag unverändert
        self.assertEqual(marked, [("ord_1", "failed")])

    def test_mark_failure_does_not_break_response(self):
        def create(raw, subject_id=None, identity=None):
            return {"orderId": "ord_1", "status": "PENDING"}

        fake = FakeService(create=create)

        def boom(order_id, state):
            raise RuntimeError("ddb down")

        fake.mark_delivery_state = boom
        with patch_service(fake), \
             mock.patch.object(index, "SQS_QUEUE_URL", "https://sqs/queue"), \
             mock.patch.object(index, "_send_to_sqs", return_value=True):
            response = index.handler(auth_event("POST /orders", body=self.BODY), None)
        self.assertEqual(response["statusCode"], 201)


class TestRecoveryInternalActionP02F(unittest.TestCase):
    def test_recovery_action_returns_report(self):
        fake = FakeService()
        with patch_service(fake), \
             mock.patch("boto3.resource"), \
             mock.patch("recovery.run_recovery", return_value={"status": "COMPLETED", "sent": 2}) as runner:
            response = index.handler({"internalAction": "recovery/scan",
                                      "options": {"limit": 5}}, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["sent"], 2)
        self.assertEqual(runner.call_args.kwargs["limit"], 5)

    def test_unknown_internal_action_is_rejected(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler({"internalAction": "recovery/other"}, None)
        self.assertEqual(response["statusCode"], 400)

    def test_recovery_requires_no_public_route(self):
        """Recovery ist nicht über eine HTTP-Route erreichbar (nur direkter Invoke)."""
        fake = FakeService()
        with patch_service(fake):
            response = index.handler({"routeKey": "POST /recovery"}, None)
        self.assertEqual(response["statusCode"], 400)


class TestProcessingFieldsNotPublicP02GA(unittest.TestCase):
    """MO-RC4-P02G-A: interne Verarbeitungsfelder sind nicht Teil der API."""

    BODY = json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                       "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 100}],
                       "currency": "EUR"})

    def test_post_rejects_processing_fields_in_body(self):
        """Der Validator (nicht der Handler-Stub) lehnt interne Felder ab."""
        from errors import OrderError
        from validation import validate_create_order

        for field, value in (("result", {"x": 1}), ("processingState", "succeeded"),
                             ("processingAttemptId", "a-1"),
                             ("completedAt", "2026-11-01T12:00:00.000Z"),
                             ("processingError", {"code": "X"})):
            with self.subTest(field=field):
                body = json.loads(self.BODY)
                body[field] = value
                with self.assertRaises(OrderError) as ctx:
                    validate_create_order(body)
                self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")

    def test_get_response_has_no_processing_fields(self):
        item = {"orderId": "ord_1", "status": "PENDING", "customer": {"name": "Max"},
                "items": [], "currency": "EUR", "totalAmount": 100,
                "createdAt": "2026-11-01T12:00:00.000Z", "updatedAt": "2026-11-01T12:00:00.000Z",
                "result": {"secret": 1}, "processingState": "succeeded"}

        fake = FakeService(get=lambda order_id: {
            k: v for k, v in item.items()
            if k not in {"pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk", "version",
                         "isTestData", "subjectId", "result", "processingState",
                         "processingAttemptId", "completedAt", "processingError"}
        })
        with patch_service(fake):
            response = index.handler({"routeKey": "GET /orders/{orderId}",
                                      "pathParameters": {"orderId": "ord_1"}}, None)
        self.assertEqual(response["statusCode"], 200)
        payload = json.loads(response["body"])
        self.assertNotIn("result", payload)
        self.assertNotIn("processingState", payload)
