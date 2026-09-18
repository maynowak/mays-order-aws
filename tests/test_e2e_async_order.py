"""
E2E Test Suite for Phase 2 — Async Order Processing

Tests the full flow:
Cognito → API Gateway → Producer Lambda → DynamoDB + SQS → Worker → DynamoDB

Environment:
- AWS profile: mayaws
- AWS region: eu-central-1
- TEST_USER_PASSWORD: environment variable for test user password

Usage:
    export AWS_PROFILE=mayaws
    export TEST_USER_PASSWORD="test_password_123!"
    python3 -m pytest tests/test_e2e_async_order.py -v
"""
import json
import os
import sys
import time
import unittest

import urllib3

http = urllib3.PoolManager()

API_BASE_URL = os.environ.get("API_BASE_URL", "https://ki2rbzvk99.execute-api.eu-central-1.amazonaws.com")
TEST_USER_EMAIL = os.environ.get("TEST_USER_EMAIL", "test-user@example.com")
TEST_USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "")

SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")


def get_access_token():
    """Authenticate with Cognito and return access token."""
    import boto3
    client_id = os.environ.get("COGNITO_CLIENT_ID", "")
    username = os.environ.get("TEST_USER_EMAIL", "")
    password = os.environ.get("TEST_USER_PASSWORD", "")

    if not all([client_id, username, password]):
        raise ValueError("COGNITO_CLIENT_ID, TEST_USER_EMAIL, and TEST_USER_PASSWORD must be set")

    cognito = boto3.client("cognito-idp", region_name="eu-central-1")
    response = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": password,
        }
    )
    return response["AuthenticationResult"]["AccessToken"]


class TestAsyncOrderFlow(unittest.TestCase):
    """Test the async order processing flow through SQS."""

    @classmethod
    def setUpClass(cls):
        cls.access_token = os.environ.get("ACCESS_TOKEN")
        if not cls.access_token:
            if TEST_USER_PASSWORD:
                cls.access_token = get_access_token()
            else:
                raise unittest.SkipTest("TEST_USER_PASSWORD not set, skipping E2E tests")

    def test_01_post_order_sends_to_sqs(self):
        """POST /orders should create order and send to SQS."""
        order_data = {
            "customer": {"name": "Test User", "email": "test-user@example.com"},
            "items": [{"sku": "TEST-SKU-001", "quantity": 1, "unitPrice": 1000}],
            "currency": "EUR"
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        response = http.request(
            "POST",
            f"{API_BASE_URL}/orders",
            body=json.dumps(order_data).encode("utf-8"),
            headers=headers
        )

        self.assertEqual(response.status, 201, f"Expected 201, got {response.status}: {response.data}")

        order = json.loads(response.data.decode("utf-8"))
        self.assertIn("orderId", order)
        self.assertEqual(order["status"], "PENDING")

        self.order_id = order["orderId"]

    def test_02_order_eventually_confirmed(self):
        """Order should transition from PENDING to CONFIRMED via SQS worker."""
        if not hasattr(self, "order_id"):
            self.skipTest("No order_id from previous test")

        max_wait = 60  # seconds
        poll_interval = 3

        start_time = time.time()

        while time.time() - start_time < max_wait:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            response = http.request(
                "GET",
                f"{API_BASE_URL}/orders/{self.order_id}",
                headers=headers
            )

            self.assertEqual(response.status, 200)
            order = json.loads(response.data.decode("utf-8"))

            if order["status"] == "CONFIRMED":
                self.order_status = "CONFIRMED"
                return

            if order["status"] not in ["PENDING", "CONFIRMED", "PROCESSING"]:
                self.fail(f"Unexpected status: {order['status']}")

            time.sleep(poll_interval)

        current_response = http.request(
            "GET",
            f"{API_BASE_URL}/orders/{self.order_id}",
            headers=headers
        )
        current_order = json.loads(current_response.data.decode("utf-8"))

        self.assertEqual(
            current_order["status"],
            "CONFIRMED",
            f"Order not confirmed after {max_wait}s, current status: {current_order['status']}"
        )

    def test_03_verify_order_data_integrity(self):
        """Order data should remain intact after transition."""
        if not hasattr(self, "order_id"):
            self.skipTest("No order_id from previous test")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        response = http.request(
            "GET",
            f"{API_BASE_URL}/orders/{self.order_id}",
            headers=headers
        )

        self.assertEqual(response.status, 200)
        order = json.loads(response.data.decode("utf-8"))

        self.assertEqual(order["status"], "CONFIRMED")
        self.assertEqual(order["currency"], "EUR")
        self.assertIn("customer", order)
        self.assertIn("items", order)
        self.assertEqual(len(order["items"]), 1)
        self.assertEqual(order["items"][0]["sku"], "TEST-SKU-001")


class TestWorkerIntegration(unittest.TestCase):
    """Verify worker processed the SQS message."""

    @classmethod
    def setUpClass(cls):
        try:
            import boto3
            cls.boto3 = boto3
        except ImportError:
            raise unittest.SkipTest("boto3 not available, skipping worker integration tests")

    def test_sqs_message_processed(self):
        """Verify SQS worker was invoked."""
        client = self.boto3.client("sqs", region_name="eu-central-1")

        queue_url = os.environ.get("SQS_QUEUE_URL", "https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-orders-queue")

        response = client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"]
        )

        msg_count = int(response["Attributes"].get("ApproximateNumberOfMessages", 0))

        self.assertEqual(msg_count, 0, f"Expected no visible messages, found {msg_count}")


if __name__ == "__main__":
    unittest.main()