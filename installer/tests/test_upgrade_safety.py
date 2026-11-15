"""MO-INSTALLER-UPGRADE-SAFETY-P0A-01: Plan-Analyse und Migrationsplan.

Rein lokal: kein Terraform, kein AWS.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from installer.core.upgrade_safety import (
    MIGRATION_PLAN_JSON,
    MIGRATION_PLAN_MD,
    STATUS_MIGRATION_REQUIRED,
    STATUS_SAFE,
    STATUS_UNKNOWN,
    analyze_plan,
    build_migration_plan,
    format_block_message,
    is_destroy_plan,
    write_migration_plan,
)


def _change(
    address: str,
    resource_type: str,
    actions,
    replace_paths=None,
) -> dict:
    change = {"actions": actions}
    if replace_paths is not None:
        change["replace_paths"] = replace_paths
    return {
        "address": address,
        "type": resource_type,
        "name": address.split(".")[-1],
        "change": change,
    }


def _plan(*changes) -> dict:
    return {"format_version": "1.2", "resource_changes": list(changes)}


class TestStatusClassification(unittest.TestCase):
    def test_empty_plan_is_safe(self):
        self.assertEqual(analyze_plan({"resource_changes": []}).status, STATUS_SAFE)

    def test_noop_plan_is_safe(self):
        plan = _plan(_change("module.sqs.aws_sqs_queue.orders", "aws_sqs_queue", ["no-op"]))
        self.assertEqual(analyze_plan(plan).status, STATUS_SAFE)

    def test_create_table_is_safe(self):
        plan = _plan(_change("module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["create"]))
        self.assertEqual(analyze_plan(plan).status, STATUS_SAFE)

    def test_create_bucket_is_safe(self):
        plan = _plan(_change("module.x.aws_s3_bucket.b", "aws_s3_bucket", ["create"]))
        self.assertEqual(analyze_plan(plan).status, STATUS_SAFE)

    def test_update_table_is_safe(self):
        plan = _plan(_change("module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["update"]))
        self.assertEqual(analyze_plan(plan).status, STATUS_SAFE)

    def test_gsi_add_is_safe(self):
        plan = _plan(_change("module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["update"]))
        self.assertEqual(analyze_plan(plan).status, STATUS_SAFE)

    def test_unprotected_delete_is_not_blocked(self):
        plan = _plan(_change("module.lambda.aws_lambda_function.handler", "aws_lambda_function", ["delete"]))
        self.assertEqual(analyze_plan(plan).status, STATUS_SAFE)

    def test_read_only_plan_is_safe(self):
        plan = _plan(_change("data.aws_caller_identity.current", "aws_caller_identity", ["read"]))
        self.assertEqual(analyze_plan(plan).status, STATUS_SAFE)


class TestProtectedResources(unittest.TestCase):
    def _assert_blocked(self, resource_type: str, actions):
        plan = _plan(_change(f"module.x.{resource_type}.r", resource_type, actions))
        assessment = analyze_plan(plan)
        self.assertEqual(assessment.status, STATUS_MIGRATION_REQUIRED, (resource_type, actions))
        self.assertEqual(len(assessment.findings), 1)
        self.assertEqual(assessment.findings[0].resource_type, resource_type)
        self.assertTrue(assessment.findings[0].requires_migration)

    def test_dynamodb_delete(self):
        self._assert_blocked("aws_dynamodb_table", ["delete"])

    def test_dynamodb_replace_create_delete(self):
        self._assert_blocked("aws_dynamodb_table", ["create", "delete"])

    def test_dynamodb_replace_delete_create(self):
        self._assert_blocked("aws_dynamodb_table", ["delete", "create"])

    def test_s3_delete(self):
        self._assert_blocked("aws_s3_bucket", ["delete"])

    def test_s3_replace(self):
        self._assert_blocked("aws_s3_bucket", ["create", "delete"])

    def test_cognito_delete(self):
        self._assert_blocked("aws_cognito_user_pool", ["delete"])

    def test_cognito_replace(self):
        self._assert_blocked("aws_cognito_user_pool", ["delete", "create"])

    def test_sqs_delete(self):
        self._assert_blocked("aws_sqs_queue", ["delete"])

    def test_sqs_replace(self):
        self._assert_blocked("aws_sqs_queue", ["create", "delete"])

    def test_replace_paths_are_reported(self):
        plan = _plan(
            _change(
                "module.dynamodb.aws_dynamodb_table.orders",
                "aws_dynamodb_table",
                ["create", "delete"],
                replace_paths=[["name"], ["hash_key"]],
            )
        )
        finding = analyze_plan(plan).findings[0]
        self.assertEqual(finding.replace_paths, ["name", "hash_key"])


class TestFailClosed(unittest.TestCase):
    def test_missing_resource_changes(self):
        self.assertEqual(analyze_plan({}).status, STATUS_UNKNOWN)

    def test_missing_actions(self):
        plan = {"resource_changes": [{"address": "x", "type": "aws_dynamodb_table", "change": {}}]}
        self.assertEqual(analyze_plan(plan).status, STATUS_UNKNOWN)

    def test_unknown_action(self):
        plan = _plan(_change("x", "aws_dynamodb_table", ["frobnicate"]))
        self.assertEqual(analyze_plan(plan).status, STATUS_UNKNOWN)

    def test_non_dict_change(self):
        self.assertEqual(analyze_plan({"resource_changes": ["nope"]}).status, STATUS_UNKNOWN)

    def test_plan_not_a_dict(self):
        self.assertEqual(analyze_plan(None).status, STATUS_UNKNOWN)

    def test_sha_is_preserved(self):
        assessment = analyze_plan({"resource_changes": []}, plan_sha256="abc")
        self.assertEqual(assessment.plan_sha256, "abc")


class TestDestroyPlanDetection(unittest.TestCase):
    def test_all_delete_is_destroy_plan(self):
        ok, _ = is_destroy_plan(
            _plan(_change("module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["delete"]))
        )
        self.assertTrue(ok)

    def test_deploy_plan_is_not_destroy_plan(self):
        ok, reason = is_destroy_plan(
            _plan(_change("module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["create"]))
        )
        self.assertFalse(ok)
        self.assertIn("kein Destroy-Plan", reason)

    def test_update_plan_is_not_destroy_plan(self):
        ok, _ = is_destroy_plan(
            _plan(_change("module.sqs.aws_sqs_queue.orders", "aws_sqs_queue", ["update"]))
        )
        self.assertFalse(ok)

    def test_empty_plan_is_not_destroy_plan(self):
        ok, _ = is_destroy_plan({"resource_changes": []})
        self.assertFalse(ok)


class TestMigrationPlanArtifacts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)
        self.plan = _plan(
            _change(
                "module.dynamodb.aws_dynamodb_table.orders",
                "aws_dynamodb_table",
                ["create", "delete"],
                replace_paths=[["name"]],
            )
        )
        self.assessment = analyze_plan(self.plan, plan_sha256="deadbeef")
        self.migration = build_migration_plan(
            self.assessment,
            project="mays-orders-rc4",
            environment="development",
            workspace="mays-orders-rc4",
        )

    def test_json_schema(self):
        self.assertEqual(self.migration["schemaVersion"], 1)
        self.assertEqual(self.migration["status"], "MIGRATION_REQUIRED")
        self.assertEqual(self.migration["project"], "mays-orders-rc4")
        self.assertEqual(self.migration["workspace"], "mays-orders-rc4")
        self.assertIsNone(self.migration["sourceVersion"])
        self.assertIsNone(self.migration["targetVersion"])
        self.assertEqual(self.migration["planSha256"], "deadbeef")
        self.assertFalse(self.migration["approved"])
        resource = self.migration["resources"][0]
        self.assertEqual(resource["address"], "module.dynamodb.aws_dynamodb_table.orders")
        self.assertEqual(resource["type"], "aws_dynamodb_table")
        self.assertEqual(resource["actions"], ["create", "delete"])
        self.assertEqual(resource["replacePaths"], ["name"])
        self.assertEqual(resource["risk"], "CRITICAL")
        self.assertTrue(resource["requiresMigration"])

    def test_files_are_written(self):
        json_path, md_path = write_migration_plan(self.run_dir, self.migration, self.assessment)
        self.assertEqual(json_path.name, MIGRATION_PLAN_JSON)
        self.assertEqual(md_path.name, MIGRATION_PLAN_MD)
        self.assertTrue(json_path.exists() and md_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "MIGRATION_REQUIRED")

    def test_markdown_has_required_sections(self):
        _, md_path = write_migration_plan(self.run_dir, self.migration, self.assessment)
        text = md_path.read_text(encoding="utf-8")
        for section in (
            "## 1. Ausgangsumgebung",
            "## 2. Zielumgebung",
            "## 3. Planidentitaet",
            "## 4. Erkannte kritische Aenderungen",
            "## 5. Datenverlustrisiken",
            "## 6. Betroffene Ressourcen",
            "## 7. Mögliche Migrationsstrategien",
            "## 8. Erforderliche Vorbedingungen",
            "## 9. Prüf- und Abnahmekriterien",
            "## 10. Offene Entscheidungen",
        ):
            self.assertIn(section, text)
        self.assertIn("keine Ausfuehrungsfreigabe", text)
        self.assertIn("Es wurde keine Migration", text)

    def test_block_message_is_explicit(self):
        message = format_block_message(self.assessment)
        self.assertIn("UPGRADE_BLOCKED_MIGRATION_REQUIRED", message)
        self.assertIn("module.dynamodb.aws_dynamodb_table.orders", message)
        self.assertIn("Migrationspruefung", message)


if __name__ == "__main__":
    unittest.main()
