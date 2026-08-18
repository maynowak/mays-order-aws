import base64
import json
import unittest
from contextlib import contextmanager
from unittest import mock

import index
from errors import order_not_found


class FakeService:
    def __init__(self, create=None, get=None, list_orders=None, update=None):
        self.create_order = create or (lambda raw: {"orderId": "ord_1", "status": "PENDING"})
        self.get_order = get or (lambda order_id: {"orderId": order_id, "status": "PENDING"})
        self.list_orders = list_orders or (
            lambda limit, next_token=None: {"orders": [], "count": 0}
        )
        self.update_order_status = update or (
            lambda order_id, status: {"orderId": order_id, "status": status}
        )


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

        def create(raw):
            captured["raw"] = raw
            return {"orderId": "ord_1", "status": "PENDING", "totalAmount": 2000}

        fake = FakeService(create=create)
        with patch_service(fake):
            response = index.handler(
                {
                    "routeKey": "POST /orders",
                    "body": json.dumps(
                        {
                            "customer": {"name": "Max", "email": "max@example.com"},
                            "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 2000}],
                            "currency": "EUR",
                        }
                    ),
                },
                None,
            )
        self.assertEqual(response["statusCode"], 201)
        self.assertEqual(captured["raw"]["customer"]["name"], "Max")

    def test_post_orders_decodes_base64_body(self):
        captured = {}

        def create(raw):
            captured["raw"] = raw
            return {"orderId": "ord_1", "status": "PENDING"}

        fake = FakeService(create=create)
        payload = json.dumps({"customer": {"name": "Max", "email": "max@example.com"},
                              "items": [{"sku": "SKU-1", "quantity": 1, "unitPrice": 2000}],
                              "currency": "EUR"})
        with patch_service(fake):
            index.handler(
                {
                    "routeKey": "POST /orders",
                    "body": base64.b64encode(payload.encode("utf-8")).decode("utf-8"),
                    "isBase64Encoded": True,
                },
                None,
            )
        self.assertEqual(captured["raw"]["customer"]["name"], "Max")

    def test_post_orders_invalid_json_returns_400(self):
        fake = FakeService()
        with patch_service(fake):
            response = index.handler({"routeKey": "POST /orders", "body": "not json"}, None)
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
        def create_boom(raw):
            raise RuntimeError("boom")

        fake = FakeService(create=create_boom)
        with patch_service(fake):
            response = index.handler(
                {"routeKey": "POST /orders", "body": json.dumps({"customer": {}, "items": [], "currency": ""})},
                None,
            )
        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "INTERNAL_ERROR")


if __name__ == "__main__":
    unittest.main()