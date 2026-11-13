"""Opt-in B2 privacy live tests for G3X-PRV-X01..X13.

All tests are skipped before any boto3 import/connection unless every privacy
gate is explicitly enabled. The existing ``E2ERun``, ``ApiClient``,
``LiveCleanupBackend`` and ``ExactKeyCleanupBackend`` components are reused.
"""

from __future__ import annotations

import json
import os
import time
import unittest
import uuid
from datetime import datetime, timezone

from tests.e2e_harness import (
    ApiClient,
    E2ERun,
    ExactKeyCleanupBackend,
    LiveCleanupBackend,
    Urllib3Transport,
    response_json,
)
from tests.privacy_e2e_harness import (
    PrivacyInvokeClient,
    boto3_invoker,
    decode_jwt_subject,
    make_privacy_context,
    resolve_privacy_config,
    run_marker,
)

CONFIRM_TIMEOUT_SECONDS = int(os.environ.get("PRIVACY_E2E_CONFIRM_TIMEOUT_SECONDS", "90"))


def _now():
    now = datetime.now(timezone.utc)
    return f"{now:%Y-%m-%dT%H:%M:%S}.{now.microsecond // 1000:03d}Z"


class PrivacyLiveE2E(unittest.TestCase):
    """Run-scoped B2 suite; blocked by default and never connects without gates."""

    @classmethod
    def setUpClass(cls):
        cls.config = resolve_privacy_config(os.environ)
        if not cls.config.ready:
            raise unittest.SkipTest(cls.config.blocked_reason)

        import boto3

        cls.session = boto3.Session(
            profile_name=os.environ.get("AWS_PROFILE", "mayaws"),
            region_name=cls.config.region,
        )
        cls.sts = cls.session.client("sts")
        cls.ddb = cls.session.client("dynamodb")
        cls.lambda_client = cls.session.client("lambda")
        cls.sqs = cls.session.client("sqs")

        cls._verify_preflight()
        cls.run = E2ERun()
        cls.normal_a = []
        cls.normal_b = []
        cls.exact = []
        cls.api_a = ApiClient(
            cls.config.api_base_url,
            access_token=cls.config.access_token_a,
            transport=Urllib3Transport(),
        )
        cls.api_b = ApiClient(
            cls.config.api_base_url,
            access_token=cls.config.access_token_b,
            transport=Urllib3Transport(),
        )
        cls.invoker = PrivacyInvokeClient(
            boto3_invoker(cls.config.function_name, cls.lambda_client)
        )
        try:
            cls.a1 = cls._create_order(cls.api_a, 1, cls.normal_a)
            cls.a2 = cls._create_order(cls.api_a, 2, cls.normal_a)
            cls.b1 = cls._create_order(cls.api_b, 3, cls.normal_b)
            cls.foreign = cls._create_direct_fixture(
                cls.config.subject_a, "foreign", cls.config.consumer_id + "-foreign"
            )
            cls.anon_subject = f"privacy-anon-{cls.run.run_id}"
            cls.anon = cls._create_direct_fixture(
                cls.anon_subject, "anon", cls.config.consumer_id
            )
            cls.scope_subject = f"privacy-scope-{cls.run.run_id}"
            cls.scope_match = cls._create_direct_fixture(
                cls.scope_subject, "scope-match", cls.config.consumer_id
            )
            cls.scope_foreign = cls._create_direct_fixture(
                cls.scope_subject, "scope-foreign", cls.config.consumer_id + "-foreign"
            )
        except Exception:
            cls._cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        if not getattr(cls, "config", None) or not cls.config.ready:
            return
        cls._cleanup()

    @classmethod
    def _verify_preflight(cls):
        identity = cls.sts.get_caller_identity()
        if identity.get("Account") != cls.config.account_id:
            raise RuntimeError("privacy live account mismatch")
        if cls.config.region != "eu-central-1":
            raise RuntimeError("privacy live region mismatch")
        cfg = cls.lambda_client.get_function_configuration(
            FunctionName=cls.config.function_name
        )
        if cfg.get("State") != "Active" or cfg.get("LastUpdateStatus") != "Successful":
            raise RuntimeError("privacy live handler is not Active/Successful")
        if cfg.get("CodeSha256") != cls.config.code_sha256:
            raise RuntimeError("privacy live CodeSha256 mismatch")
        table = cls.ddb.describe_table(TableName=cls.config.table_name)["Table"]
        if table.get("TableStatus") != "ACTIVE" or int(table.get("ItemCount", -1)) != 0:
            raise RuntimeError("privacy live table baseline is not empty/active")
        for url in (cls.config.queue_url, cls.config.dlq_url):
            attrs = cls.sqs.get_queue_attributes(
                QueueUrl=url,
                AttributeNames=[
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                ],
            )["Attributes"]
            if any(int(value) != 0 for value in attrs.values()):
                raise RuntimeError("privacy live queue baseline is not 0")
        if decode_jwt_subject(cls.config.access_token_a) != cls.config.subject_a:
            raise RuntimeError("privacy live subject A does not match token")
        if decode_jwt_subject(cls.config.access_token_b) != cls.config.subject_b:
            raise RuntimeError("privacy live subject B does not match token")

    @classmethod
    def _create_order(cls, client, sequence, bucket):
        synthetic = cls.run.synthetic_order(sequence)
        response = client.post("/orders", synthetic.payload)
        if response.status != 201:
            raise RuntimeError(f"privacy live order creation failed: {response.status}")
        order = response_json(response)
        order_id = order["orderId"]
        owned = cls.run.register_created(order_id, synthetic.marker)
        bucket.append(owned)
        deadline = time.monotonic() + CONFIRM_TIMEOUT_SECONDS
        last_status = None
        while time.monotonic() < deadline:
            get_response = client.get(f"/orders/{order_id}")
            if get_response.status != 200:
                raise RuntimeError(f"privacy live order read failed: {get_response.status}")
            last_status = response_json(get_response).get("status")
            if last_status == "CONFIRMED":
                return owned
            time.sleep(3)
        raise RuntimeError(f"privacy live order not CONFIRMED: {last_status}")

    @classmethod
    def _create_direct_fixture(cls, subject_id, marker_suffix, consumer_id):
        order_id = "ord_" + uuid.uuid4().hex[:24]
        marker = run_marker(cls.run.run_id, marker_suffix)
        owned = cls.run.register_created(order_id, marker)
        now = _now()
        item = {
            "pk": {"S": f"ord_{order_id}"},
            "sk": {"S": "#ORDER"},
            "orderId": {"S": order_id},
            "status": {"S": "CONFIRMED"},
            "orderType": {"S": "generic"},
            "version": {"N": "1"},
            "deliveryState": {"S": "sent"},
            "subjectId": {"S": subject_id},
            "consumerId": {"S": consumer_id},
            "gsi2pk": {"S": f"SUBJECT#{subject_id}"},
            "gsi2sk": {"S": f"ord_{order_id}#{now}"},
            "customer": {"M": {"name": {"S": marker}, "email": {"S": "privacy@example.invalid"}}},
            "items": {"L": [{"M": {"sku": {"S": marker}, "quantity": {"N": "1"}, "unitPrice": {"N": "100"}}}]},
            "currency": {"S": "EUR"},
            "totalAmount": {"N": "100"},
            "createdAt": {"S": now},
            "updatedAt": {"S": now},
        }
        cls.ddb.put_item(
            TableName=cls.config.table_name,
            Item=item,
            ConditionExpression="attribute_not_exists(pk)",
        )
        cls.exact.append(owned)
        return owned

    @classmethod
    def _cleanup(cls):
        normal_a = getattr(cls, "normal_a", [])
        normal_b = getattr(cls, "normal_b", [])
        exact = getattr(cls, "exact", [])
        if normal_a:
            backend_a = LiveCleanupBackend(
                table_name=cls.config.table_name,
                region=cls.config.region,
                subject_id=cls.config.subject_a,
            )
            for order in normal_a:
                backend_a(order)
        if normal_b:
            backend_b = LiveCleanupBackend(
                table_name=cls.config.table_name,
                region=cls.config.region,
                subject_id=cls.config.subject_b,
            )
            for order in normal_b:
                backend_b(order)
        if exact:
            backend_exact = ExactKeyCleanupBackend(
                table_name=cls.config.table_name,
                region=cls.config.region,
                run_id=cls.run.run_id,
            )
            for order in exact:
                backend_exact(order)
        for order in getattr(cls.run, "orders", []) if hasattr(cls, "run") else []:
            item = cls.ddb.get_item(
                TableName=cls.config.table_name,
                Key={"pk": {"S": f"ord_{order.order_id}"}, "sk": {"S": "#ORDER"}},
                ConsistentRead=True,
            ).get("Item")
            if item:
                raise RuntimeError(f"privacy live cleanup left order {order.order_id}")
        count = None
        for _ in range(15):
            count = int(
                cls.ddb.describe_table(TableName=cls.config.table_name)["Table"].get(
                    "ItemCount", -1
                )
            )
            if count == 0:
                break
            time.sleep(2)
        if count != 0:
            raise RuntimeError("privacy live cleanup left table rows")
        for url in (cls.config.queue_url, cls.config.dlq_url):
            attrs = {}
            for _ in range(15):
                attrs = cls.sqs.get_queue_attributes(
                    QueueUrl=url,
                    AttributeNames=[
                        "ApproximateNumberOfMessages",
                        "ApproximateNumberOfMessagesNotVisible",
                    ],
                )["Attributes"]
                if all(int(value) == 0 for value in attrs.values()):
                    break
                time.sleep(2)
            if any(int(value) != 0 for value in attrs.values()):
                raise RuntimeError("privacy live cleanup left queue messages")

    def _context(self, permission, **overrides):
        return make_privacy_context(self.config, permission, **overrides)

    def _invoke(self, action, subject_id, permission, **overrides):
        context = self._context(permission, **overrides)
        return self.invoker.invoke(action, subject_id, context)

    def _get_item(self, order_id):
        return self.ddb.get_item(
            TableName=self.config.table_name,
            Key={"pk": {"S": f"ord_{order_id}"}, "sk": {"S": "#ORDER"}},
            ConsistentRead=True,
        ).get("Item")

    def _assert_no_order_data(self, body):
        for field in ("customer", "items", "orders", "totalAmount"):
            self.assertNotIn(field, body)

    def _assert_validation_error(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.body.get("error", {}).get("code"), "VALIDATION_ERROR")
        self._assert_no_order_data(response.body)

    # A — authentication -------------------------------------------------
    def test_x02_wrong_project_is_rejected(self):
        response = self._invoke(
            "privacy/inspect", self.config.subject_a, "privacy_inspect",
            project="wrong-project",
        )
        self._assert_validation_error(response)

    def test_x03_wrong_internal_token_is_rejected(self):
        response = self._invoke(
            "privacy/inspect", self.config.subject_a, "privacy_inspect",
            token="wrong-token",
        )
        self._assert_validation_error(response)

    def test_x04_authorized_false_is_rejected(self):
        response = self._invoke(
            "privacy/inspect", self.config.subject_a, "privacy_inspect",
            authorized=False,
        )
        self._assert_validation_error(response)

    def test_x13_missing_secret_requires_secret_absent_stack(self):
        # A secret-enabled B2 run cannot reproduce a missing Lambda env secret
        # without a second configuration change. Local `test_privacy_requires_
        # internal_secret` covers that branch; X13 stays explicitly blocked.
        self.skipTest(
            "BLOCKED: missing-secret state requires a secret-absent stack; "
            "local unit test covers the fail-closed branch"
        )

    # B — inspect --------------------------------------------------------
    def test_x01_inspect_own_subject(self):
        response = self._invoke("privacy/inspect", self.config.subject_a, "privacy_inspect")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("status"), "COMPLETED")
        self.assertEqual(response.body.get("affectedRecords"), 2)
        self.assertCountEqual(
            response.body.get("orderReferences", []),
            [self.a1.order_id, self.a2.order_id],
        )
        self.assertNotIn("customer", response.body)
        self.assertNotIn("items", response.body)

    def test_x01_empty_subject_is_empty(self):
        response = self._invoke(
            "privacy/inspect", "privacy-subject-does-not-exist", "privacy_inspect"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("affectedRecords"), 0)
        self.assertEqual(response.body.get("orderReferences"), [])

    def test_x01_consumer_scope_excludes_foreign_consumer(self):
        response = self._invoke(
            "privacy/inspect", self.config.subject_a, "privacy_inspect",
            include_consumer=False,
        )
        self.assertEqual(response.body.get("affectedRecords"), 3)
        scoped = self._invoke(
            "privacy/inspect", self.config.subject_a, "privacy_inspect",
            consumer_id=self.config.consumer_id,
        )
        self.assertEqual(scoped.body.get("affectedRecords"), 2)
        self.assertNotIn(self.foreign.order_id, scoped.body.get("orderReferences", []))

    # C — export ---------------------------------------------------------
    def test_x05_export_own_subject(self):
        response = self._invoke("privacy/export", self.config.subject_a, "privacy_export")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("status"), "COMPLETED")
        self.assertEqual(response.body.get("recordCount"), 2)
        self.assertEqual(
            {order["orderId"] for order in response.body.get("orders", [])},
            {self.a1.order_id, self.a2.order_id},
        )
        for order in response.body.get("orders", []):
            for internal in ("pk", "sk", "subjectId", "consumerId", "gsi2pk", "gsi2sk"):
                self.assertNotIn(internal, order)

    def test_x06_export_foreign_subject_excludes_a(self):
        response = self._invoke("privacy/export", self.config.subject_b, "privacy_export")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("recordCount"), 1)
        self.assertEqual([o["orderId"] for o in response.body.get("orders", [])], [self.b1.order_id])

    # D — erasure --------------------------------------------------------
    def test_x07_preview_does_not_mutate(self):
        before = self._get_item(self.a2.order_id)
        response = self._invoke(
            "privacy/erase", self.config.subject_a, "privacy_erase",
            options={"mode": "PREVIEW", "policy": "ERASE"},
        )
        after = self._get_item(self.a2.order_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("status"), "PREVIEW")
        self.assertEqual(response.body.get("plannedDeletes"), 2)
        self.assertEqual(before, after)

    def test_x08_execute_without_policy_does_not_mutate(self):
        before = self._get_item(self.a2.order_id)
        response = self._invoke(
            "privacy/erase", self.config.subject_a, "privacy_erase",
            options={"mode": "EXECUTE"},
        )
        after = self._get_item(self.a2.order_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("status"), "BLOCKED")
        self.assertEqual(response.body.get("deletedRecords"), 0)
        self.assertEqual(before, after)

    def test_x09_erase_b_is_idempotent(self):
        response = self._invoke(
            "privacy/erase", self.config.subject_b, "privacy_erase",
            options={"mode": "EXECUTE", "policy": "ERASE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("deletedRecords"), 1)
        self.assertIsNone(self._get_item(self.b1.order_id))
        repeat = self._invoke(
            "privacy/erase", self.config.subject_b, "privacy_erase",
            options={"mode": "EXECUTE", "policy": "ERASE"},
        )
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(repeat.body.get("deletedRecords"), 0)

    def test_x10_retain_does_not_mutate(self):
        before_a1 = self._get_item(self.a1.order_id)
        before_a2 = self._get_item(self.a2.order_id)
        response = self._invoke(
            "privacy/erase", self.config.subject_a, "privacy_erase",
            options={"mode": "EXECUTE", "policy": "RETAIN"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("status"), "PARTIALLY_COMPLETED")
        self.assertEqual(response.body.get("retainedRecords"), 2)
        self.assertEqual(before_a1, self._get_item(self.a1.order_id))
        self.assertEqual(before_a2, self._get_item(self.a2.order_id))

    def test_x11_anonymize_one_order(self):
        # Use a dedicated one-order subject: erase_subject operates per subject,
        # so A1/A2 must remain untouched for the later consumer-scope test.
        response = self._invoke(
            "privacy/erase", self.anon_subject, "privacy_erase",
            options={"mode": "EXECUTE", "policy": "ANONYMIZE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("anonymizedRecords"), 1)
        self.assertIsNone((self._get_item(self.anon.order_id) or {}).get("subjectId"))
        self.assertEqual(self.api_a.get(f"/orders/{self.a2.order_id}").status, 200)

    def test_x12_consumer_scope_erase(self):
        before_foreign = self._get_item(self.scope_foreign.order_id)
        response = self._invoke(
            "privacy/erase", self.scope_subject, "privacy_erase",
            consumer_id=self.config.consumer_id,
            options={"mode": "EXECUTE", "policy": "ERASE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body.get("deletedRecords"), 1)
        self.assertTrue(
            any("outside consumer scope" in item for item in response.body.get("limitations", []))
        )
        self.assertIsNone(self._get_item(self.scope_match.order_id))
        self.assertEqual(before_foreign, self._get_item(self.scope_foreign.order_id))
        # The unrelated A subject remains untouched.
        self.assertIsNotNone(self._get_item(self.a1.order_id))
        self.assertIsNotNone(self._get_item(self.a2.order_id))


if __name__ == "__main__":
    unittest.main()
