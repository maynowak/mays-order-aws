"""MO-RC4-POLICY-GATE-REPAIR-01: Tests fuer die erweiterte Policy-Gate-Logik.

Deckt die ressourcenspezifische Lambda-Timeout-Regel und die gezielten
Sicherheitspruefungen fuer die neu freigegebenen Ressourcentypen ab.
Rein lokal: kein Terraform, kein AWS.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_SCRIPT = REPO_ROOT / "terraform" / "policy" / "validate-plan.py"
RC4_PLAN_JSON = Path("/tmp/opencode/mo-rc4-remote-plan-01.json")

TAGS = {"Project": "mays-orders-rc4", "Maker": "mays-anything", "Environment": "Development"}


def _load_gate():
    spec = importlib.util.spec_from_file_location("mo_policy_gate_repair", POLICY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE = _load_gate()
POLICY = GATE.load_json(GATE.POLICY_PATH)


def _change(resource_type: str, address: str, after: Dict[str, Any]) -> Dict[str, Any]:
    name = address.split(".")[-1]
    return {
        "address": address,
        "type": resource_type,
        "name": name,
        "change": {"actions": ["create"], "after": after},
    }


def _plan(*changes: Dict[str, Any]) -> Dict[str, Any]:
    return {"resource_changes": list(changes)}


def _lambda(address: str, timeout: int, runtime: str = "python3.14") -> Dict[str, Any]:
    return _change(
        "aws_lambda_function",
        address,
        {"runtime": runtime, "timeout": timeout, "tags_all": TAGS},
    )


def _errors(*changes: Dict[str, Any]) -> List[str]:
    return GATE.check(_plan(*changes), POLICY)


class TestLambdaTimeout(unittest.TestCase):
    def test_order_handler_10s_allowed(self):
        self.assertEqual(_errors(_lambda("module.lambda.aws_lambda_function.handler", 10)), [])

    def test_order_handler_300s_rejected(self):
        errors = _errors(_lambda("module.lambda.aws_lambda_function.handler", 300))
        self.assertTrue(any("resource-specific limit of 10s" in e for e in errors), errors)

    def test_order_worker_10s_allowed(self):
        self.assertEqual(
            _errors(_lambda("module.sqs_worker.aws_lambda_function.worker", 10)), []
        )

    def test_backup_lambda_300s_allowed(self):
        errors = _errors(
            _lambda(
                "module.cognito_backup_automation[0].aws_lambda_function.backup",
                300,
                runtime="python3.11",
            )
        )
        self.assertEqual(errors, [])

    def test_backup_lambda_over_300s_rejected(self):
        errors = _errors(
            _lambda(
                "module.cognito_backup_automation[0].aws_lambda_function.backup",
                301,
                runtime="python3.11",
            )
        )
        self.assertTrue(any("resource-specific limit of 300s" in e for e in errors), errors)

    def test_unknown_lambda_300s_rejected(self):
        """Unbekannte Lambdas erhalten nie das Backup-Override."""
        errors = _errors(_lambda("module.other.aws_lambda_function.custom", 300))
        self.assertTrue(any("resource-specific limit of 10s" in e for e in errors), errors)

    def test_disallowed_runtime_still_rejected(self):
        errors = _errors(_lambda("module.lambda.aws_lambda_function.handler", 10, runtime="nodejs22.x"))
        self.assertTrue(any("runtime" in e for e in errors), errors)


class TestAllowedBackupResourceTypes(unittest.TestCase):
    def test_new_types_with_required_shape_pass(self):
        errors = _errors(
            _change(
                "aws_s3_bucket_versioning",
                "module.cognito_backup[0].aws_s3_bucket_versioning.cognito_backup",
                {"versioning_configuration": [{"status": "Enabled"}]},
            ),
            _change(
                "aws_s3_bucket_lifecycle_configuration",
                "module.cognito_backup[0].aws_s3_bucket_lifecycle_configuration.cognito_backup",
                {"rule": [{"id": "lifecycle", "status": "Enabled"}]},
            ),
            _change(
                "aws_iam_policy",
                "module.cognito_backup_automation[0].aws_iam_policy.backup_policy",
                {"name": "mays-orders-rc4-cognito-backup-policy", "tags_all": TAGS},
            ),
            _change(
                "aws_iam_role_policy_attachment",
                "module.cognito_backup_automation[0].aws_iam_role_policy_attachment.backup_attach",
                {"role": "mays-orders-rc4-cognito-backup-role"},
            ),
            _change(
                "aws_sns_topic",
                "module.cognito_backup_automation[0].aws_sns_topic.notifications",
                {"name": "mays-orders-rc4-cognito-backup-notifications", "tags_all": TAGS},
            ),
            _change(
                "aws_sns_topic_policy",
                "module.cognito_backup_automation[0].aws_sns_topic_policy.notifications",
                {},
            ),
            _change(
                "aws_sns_topic_subscription",
                "module.cognito_backup_automation[0].aws_sns_topic_subscription.email[0]",
                {"protocol": "email", "endpoint": "ops@example.com"},
            ),
        )
        self.assertEqual(errors, [])


class TestTargetedSecurityChecks(unittest.TestCase):
    def test_unknown_resource_type_still_rejected(self):
        errors = _errors(_change("aws_lambda_layer_version", "module.x.aws_lambda_layer_version.y", {"layer_name": "x"}))
        self.assertTrue(any("not allowed by the project policy" in e for e in errors), errors)

    def test_versioning_disabled_rejected(self):
        errors = _errors(
            _change(
                "aws_s3_bucket_versioning",
                "module.cognito_backup[0].aws_s3_bucket_versioning.cognito_backup",
                {"versioning_configuration": [{"status": "Suspended"}]},
            )
        )
        self.assertTrue(any("versioning must be Enabled" in e for e in errors), errors)

    def test_lifecycle_without_enabled_rule_rejected(self):
        errors = _errors(
            _change(
                "aws_s3_bucket_lifecycle_configuration",
                "module.cognito_backup[0].aws_s3_bucket_lifecycle_configuration.cognito_backup",
                {"rule": [{"id": "x", "status": "Disabled"}]},
            )
        )
        self.assertTrue(any("enabled rule" in e for e in errors), errors)

    def test_iam_policy_name_outside_namespace_rejected(self):
        errors = _errors(
            _change(
                "aws_iam_policy",
                "module.cognito_backup_automation[0].aws_iam_policy.backup_policy",
                {"name": "foreign-policy", "tags_all": TAGS},
            )
        )
        self.assertTrue(any("outside the project namespace" in e for e in errors), errors)

    def test_iam_policy_wildcard_action_rejected(self):
        doc = json.dumps(
            {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]}
        )
        errors = _errors(
            _change(
                "aws_iam_policy",
                "module.cognito_backup_automation[0].aws_iam_policy.backup_policy",
                {"name": "mays-orders-rc4-policy", "policy": doc, "tags_all": TAGS},
            )
        )
        self.assertTrue(any("wildcard actions" in e for e in errors), errors)

    def test_attachment_to_foreign_role_rejected(self):
        errors = _errors(
            _change(
                "aws_iam_role_policy_attachment",
                "module.cognito_backup_automation[0].aws_iam_role_policy_attachment.backup_attach",
                {"role": "foreign-role"},
            )
        )
        self.assertTrue(any("outside the" in e for e in errors), errors)

    def test_sns_topic_outside_namespace_rejected(self):
        errors = _errors(
            _change(
                "aws_sns_topic",
                "module.cognito_backup_automation[0].aws_sns_topic.notifications",
                {"name": "foreign-topic", "tags_all": TAGS},
            )
        )
        self.assertTrue(any("outside the project namespace" in e for e in errors), errors)

    def test_sns_subscription_protocol_restricted(self):
        errors = _errors(
            _change(
                "aws_sns_topic_subscription",
                "module.cognito_backup_automation[0].aws_sns_topic_subscription.email[0]",
                {"protocol": "sms", "endpoint": "+491234"},
            )
        )
        self.assertTrue(any("protocol" in e for e in errors), errors)

    def test_sns_email_endpoint_validated(self):
        errors = _errors(
            _change(
                "aws_sns_topic_subscription",
                "module.cognito_backup_automation[0].aws_sns_topic_subscription.email[0]",
                {"protocol": "email", "endpoint": "not-an-email"},
            )
        )
        self.assertTrue(any("endpoint is invalid" in e for e in errors), errors)


class TestRepositoryPlan(unittest.TestCase):
    @unittest.skipUnless(RC4_PLAN_JSON.exists(), "RC4-Plan-JSON nicht vorhanden")
    def test_unchanged_rc4_plan_passes(self):
        plan = json.loads(RC4_PLAN_JSON.read_text(encoding="utf-8"))
        self.assertEqual(GATE.check(plan, POLICY), [])


if __name__ == "__main__":
    unittest.main()
