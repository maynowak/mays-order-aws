"""MO-RC4-P02I-E1B: Resource-Identity-Regressionstest.

Prueft statisch, dass Terraform-Module bereits existierende Ressourcen ueber
tatsaechliche Attribute/Outputs referenzieren (ARN/ID/URL) und keine ARNs aus
Namenskonventionen rekonstruieren. Reine Textpruefung, kein Terraform, kein AWS.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TF = REPO_ROOT / "terraform"


def _read(rel: str) -> str:
    return (TF / rel).read_text(encoding="utf-8")


def _all_tf_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in TF.rglob("*.tf"))


class TestNoArnReconstruction(unittest.TestCase):
    def test_no_dynamodb_arn_is_reconstructed(self) -> None:
        self.assertNotIn("arn:aws:dynamodb", _all_tf_text())

    def test_no_sqs_arn_is_reconstructed(self) -> None:
        self.assertNotIn("arn:aws:sqs", _all_tf_text())

    def test_no_lambda_arn_is_reconstructed(self) -> None:
        self.assertNotIn("arn:aws:lambda", _all_tf_text())

    def test_no_cognito_arn_is_reconstructed(self) -> None:
        self.assertNotIn("arn:aws:cognito-idp", _all_tf_text())

    def test_s3_arn_is_not_rebuilt_from_bucket_name(self) -> None:
        automation = _read("modules/cognito_backup_automation/main.tf")
        # Die Policy verwendet die uebergebene Identitaet, nicht den Namen.
        self.assertIn("local.bucket_arn", automation)
        self.assertNotIn('"arn:aws:s3:::${var.bucket_name}",', automation)
        self.assertNotIn('"arn:aws:s3:::${var.bucket_name}/*"', automation)
        # Der ARN-Fallback existiert nur noch als dokumentierter Legacy-Pfad
        # innerhalb des bucket_arn-Locals (abwaertskompatibler Modulvertrag).
        fallback = 'bucket_arn = var.bucket_arn != null ? var.bucket_arn : "arn:aws:s3:::${var.bucket_name}"'
        self.assertIn(fallback, automation)
        self.assertEqual(automation.count('"arn:aws:s3:::${var.bucket_name}"'), 1)


class TestModuleIdentityWiring(unittest.TestCase):
    def test_iam_uses_table_and_gsi_arns(self) -> None:
        iam = _read("modules/iam/main.tf")
        for expected in (
            "var.dynamodb_table_arn",
            "var.dynamodb_gsi1_arn",
            "var.dynamodb_gsi2_arn",
            "var.dynamodb_gsi3_arn",
            "var.sqs_queue_arn",
        ):
            self.assertIn(expected, iam)

    def test_sqs_worker_uses_queue_and_table_arns(self) -> None:
        worker = _read("modules/sqs-worker/iam.tf")
        self.assertIn("var.sqs_queue_arn", worker)
        self.assertIn("var.dynamodb_table_arn", worker)

    def test_sqs_redrive_uses_dlq_arn(self) -> None:
        sqs = _read("modules/sqs/main.tf")
        self.assertIn("deadLetterTargetArn = aws_sqs_queue.dlq.arn", sqs)

    def test_recovery_uses_function_arn(self) -> None:
        recovery = _read("modules/recovery/main.tf")
        self.assertIn("Resource = [var.function_arn]", recovery)
        self.assertGreaterEqual(recovery.count("arn      = var.function_arn"), 2)

    def test_api_uses_lambda_invoke_arn_and_execution_arn(self) -> None:
        api = _read("modules/api/main.tf")
        self.assertIn("integration_uri        = var.lambda_invoke_arn", api)
        self.assertIn("aws_apigatewayv2_api.orders.execution_arn", api)
        self.assertIn("var.cognito_user_pool_client_id", api)

    def test_lambda_consumes_queue_url_and_table_name(self) -> None:
        lam = _read("modules/lambda/main.tf")
        self.assertIn("SQS_QUEUE_URL       = var.queue_url", lam)
        self.assertIn("ORDERS_TABLE        = var.dynamodb_table_name", lam)
        root = _read("main.tf")
        self.assertIn("queue_url           = module.sqs.queue_url", root)
        self.assertIn("dynamodb_table_name = module.dynamodb.table_name", root)

    def test_root_passes_backup_bucket_arn(self) -> None:
        root = _read("main.tf")
        self.assertIn("bucket_arn         = try(module.cognito_backup[0].bucket_arn, null)", root)

    def test_cloudtrail_source_arn_exception_is_documented(self) -> None:
        """aws:SourceArn ist die einzige bewusste Ausnahme (Bucket-Policy-Zyklus)."""
        trail = _read("modules/cloudtrail/main.tf")
        self.assertIn("aws:SourceArn", trail)
        self.assertIn("Zyklus", trail)
        self.assertIn("Resource = aws_s3_bucket.trail.arn", trail)


if __name__ == "__main__":
    unittest.main()
