import contextlib
import json
import os
import sys
import types
import unittest
from unittest import mock

import index
import order_service
import secret_provider

ARN_A = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:orders/a-AbCdEf"
ARN_B = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:orders/b-AbCdEf"


class FakeSecretsManagerClient:
    def __init__(self):
        self.calls = []
        self.token = "handler-token"

    def get_secret_value(self, **kwargs):
        self.calls.append(kwargs["SecretId"])
        return {"SecretString": self.token}

    def describe_secret(self, **kwargs):
        raise AssertionError("CMK verification must not run without PRIVACY_KMS_KEY_ARN")


class FakeBoto3Module(types.ModuleType):
    def __init__(self, client):
        super().__init__("boto3")
        self._client = client

    def client(self, service_name, **kwargs):
        if service_name != "secretsmanager":
            raise AssertionError(f"unexpected AWS client: {service_name}")
        return self._client


class FakeTable:
    def query(self, **kwargs):
        return {"Items": []}


class FakeDynamoResource:
    def Table(self, table_name):
        return FakeTable()


class TestHandlerAwsManagedPath(unittest.TestCase):
    def setUp(self):
        secret_provider.reset_default_secret_provider()
        self.secret_client = FakeSecretsManagerClient()
        self.boto3 = FakeBoto3Module(self.secret_client)
        self.env = {
            "AWS_REGION": "eu-central-1",
            "ORDERS_TABLE": "mays-orders",
            "ORDERS_PROJECT_NAME": "mays-orders",
            "PRIVACY_SECRET_PROVIDER": "secretsmanager",
            "PRIVACY_SECRET_ID": ARN_A,
        }
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(mock.patch.dict(sys.modules, {"boto3": self.boto3}))
        self.stack.enter_context(mock.patch.dict(os.environ, self.env, clear=True))
        self.stack.enter_context(
            mock.patch(
                "order_service._get_dynamodb_resource",
                return_value=FakeDynamoResource(),
            )
        )

    def tearDown(self):
        self.stack.close()
        secret_provider.reset_default_secret_provider()

    def _event(self, token="handler-token", subject_id="user-1"):
        return {
            "internalAction": "privacy/inspect",
            "payload": {"subjectId": subject_id},
            "authContext": {
                "project": "mays-orders",
                "authorized": True,
                "privacy_inspect": True,
                "internal_token": token,
            },
        }

    def test_two_handler_invocations_reuse_module_provider_and_cache(self):
        first = index.handler(self._event(), None)
        second = index.handler(self._event(), None)
        self.assertEqual(first["statusCode"], 200)
        self.assertEqual(second["statusCode"], 200)
        self.assertEqual(self.secret_client.calls, [ARN_A])

    def test_handler_rebuilds_provider_on_reference_change(self):
        self.assertEqual(index.handler(self._event(), None)["statusCode"], 200)
        os.environ["PRIVACY_SECRET_ID"] = ARN_B
        self.assertEqual(index.handler(self._event(), None)["statusCode"], 200)
        self.assertEqual(self.secret_client.calls, [ARN_A, ARN_B])

    def test_handler_cache_invalidation_forces_fetch(self):
        self.assertEqual(index.handler(self._event(), None)["statusCode"], 200)
        secret_provider.reset_default_secret_provider()
        self.assertEqual(index.handler(self._event(), None)["statusCode"], 200)
        self.assertEqual(self.secret_client.calls, [ARN_A, ARN_A])

    def test_handler_negative_provider_config_fails_closed_before_fetch(self):
        os.environ["PRIVACY_INTERNAL_SECRET"] = "must-not-be-used"
        response = index.handler(self._event(), None)
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(self.secret_client.calls, [])
        body = json.loads(response["body"])
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")

    def test_handler_wrong_token_fails_closed_without_leaking(self):
        response = index.handler(self._event(token="wrong-token"), None)
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(self.secret_client.calls, [ARN_A])
        self.assertNotIn("handler-token", response["body"])


if __name__ == "__main__":
    unittest.main()
