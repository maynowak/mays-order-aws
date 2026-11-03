"""MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01: Upgrade-Modus/Kompatibilitaet.

Rein lokal: keine AWS-/Terraform-Aufrufe.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from installer.cli.main import InstallerCLI
from installer.core.change_classification import (
    CRITICAL,
    REVIEW,
    SAFE,
    classify_changes,
    classify_planned_change,
)
from installer.core.compatibility import (
    COMPATIBLE,
    INCOMPATIBLE,
    MIGRATION_REQUIRED,
    REVIEW_REQUIRED,
    UNKNOWN,
    assess_compatibility,
)
from installer.core.plan_manifest import PlanManifest
from installer.core.deployment_identity import DeploymentId, PlanOperation
from installer.core.upgrade_readiness import (
    BLOCKED as READINESS_BLOCKED,
    NO_CHANGES,
    READY,
    REVIEW_REQUIRED as READINESS_REVIEW,
    ReadinessInput,
    build_readiness_report,
    decide_status,
    render_readiness_markdown,
)
from installer.core.upgrade_mode import (
    CODE_MISSING_INSTALLATION,
    CODE_REQUIRES_REMOTE,
    CODE_STATE_UNREADABLE,
    check_upgrade_source,
)


def _installed(status, version=None):
    return SimpleNamespace(status=status, version=version, resources=1)


class TestUpgradeSource(unittest.TestCase):
    def test_requires_remote(self):
        ok, code, _ = check_upgrade_source(_installed("VERIFIED"), remote=False)
        self.assertFalse(ok)
        self.assertEqual(code, CODE_REQUIRES_REMOTE)

    def test_missing_installation(self):
        ok, code, _ = check_upgrade_source(_installed("UNVERIFIED"), remote=True)
        self.assertFalse(ok)
        self.assertEqual(code, CODE_MISSING_INSTALLATION)

    def test_missing_installed_object(self):
        ok, code, _ = check_upgrade_source(None, remote=True)
        self.assertFalse(ok)
        self.assertEqual(code, CODE_MISSING_INSTALLATION)

    def test_unreadable_state(self):
        ok, code, _ = check_upgrade_source(_installed("UNREADABLE"), remote=True)
        self.assertFalse(ok)
        self.assertEqual(code, CODE_STATE_UNREADABLE)

    def test_verified_installation_allowed(self):
        ok, code, _ = check_upgrade_source(_installed("VERIFIED", "0.1.0"), remote=True)
        self.assertTrue(ok, code)

    def test_legacy_installation_allowed_but_version_unknown(self):
        """Legacy ist eine Installation; die Kompatibilitaet entscheidet danach."""
        ok, code, _ = check_upgrade_source(_installed("LEGACY_UNKNOWN"), remote=True)
        self.assertTrue(ok, code)


class TestCompatibility(unittest.TestCase):
    def _assess(self, source, target, **kwargs):
        return assess_compatibility(source, target, **kwargs)

    def test_same_version_compatible(self):
        self.assertEqual(self._assess("0.1.0", "0.1.0").status, COMPATIBLE)

    def test_patch_upgrade_compatible(self):
        self.assertEqual(self._assess("0.1.0", "0.1.1").status, COMPATIBLE)

    def test_minor_upgrade_requires_review(self):
        self.assertEqual(self._assess("0.1.0", "0.2.0").status, REVIEW_REQUIRED)

    def test_minor_upgrade_with_evidence_compatible(self):
        self.assertEqual(
            self._assess("0.1.0", "0.2.0", known_compatible=True).status,
            COMPATIBLE,
        )

    def test_major_upgrade_requires_migration(self):
        self.assertEqual(self._assess("0.1.0", "1.0.0").status, MIGRATION_REQUIRED)

    def test_downgrade_incompatible(self):
        self.assertEqual(self._assess("0.2.0", "0.1.0").status, INCOMPATIBLE)

    def test_invalid_target_unknown(self):
        self.assertEqual(self._assess("0.1.0", "not-a-version").status, UNKNOWN)

    def test_invalid_source_unknown(self):
        self.assertEqual(self._assess("x.y.z", "0.2.0").status, UNKNOWN)

    def test_legacy_source_unknown(self):
        assessment = self._assess(
            None, "0.2.0", source_status="LEGACY_UNKNOWN"
        )
        self.assertEqual(assessment.status, UNKNOWN)
        self.assertTrue(assessment.blocked)

    def test_blocking_statuses(self):
        self.assertTrue(self._assess("0.1.0", "1.0.0").blocked)
        self.assertTrue(self._assess("0.2.0", "0.1.0").blocked)
        self.assertTrue(self._assess("0.1.0", "x").blocked)
        self.assertFalse(self._assess("0.1.0", "0.1.1").blocked)


class TestChangeClassification(unittest.TestCase):
    def test_new_resource_safe(self):
        result = classify_planned_change(
            "module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["create"]
        )
        self.assertEqual(result.category, SAFE)

    def test_new_public_interface_review(self):
        result = classify_planned_change(
            "module.api.aws_apigatewayv2_api.orders", "aws_apigatewayv2_api", ["create"]
        )
        self.assertEqual(result.category, REVIEW)

    def test_update_review(self):
        result = classify_planned_change(
            "module.lambda.aws_lambda_function.handler", "aws_lambda_function", ["update"]
        )
        self.assertEqual(result.category, REVIEW)

    def test_delete_unprotected_review(self):
        result = classify_planned_change(
            "module.monitoring.aws_cloudwatch_metric_alarm.x",
            "aws_cloudwatch_metric_alarm", ["delete"],
        )
        self.assertEqual(result.category, REVIEW)

    def test_unknown_action_critical(self):
        result = classify_planned_change("x", "aws_sqs_queue", ["frobnicate"])
        self.assertEqual(result.category, CRITICAL)

    def test_safety_finding_critical(self):
        result = classify_changes(
            safety_findings=[{
                "address": "module.dynamodb.aws_dynamodb_table.orders",
                "type": "aws_dynamodb_table",
                "actions": ["create", "delete"],
                "reason": "Ersetzen wuerde Daten zerstoeren.",
            }]
        )
        self.assertEqual(result.overall, CRITICAL)

    def test_protected_drift_critical(self):
        drift = SimpleNamespace(
            address="module.dynamodb.aws_dynamodb_table.orders",
            resource_type="aws_dynamodb_table",
            actions=["update"],
        )
        result = classify_changes(
            drift_status="DRIFT_DETECTED", drift_findings=[drift],
            protected_types=["aws_dynamodb_table"],
        )
        self.assertEqual(result.overall, CRITICAL)

    def test_unprotected_drift_review(self):
        drift = SimpleNamespace(
            address="module.monitoring.aws_cloudwatch_metric_alarm.x",
            resource_type="aws_cloudwatch_metric_alarm",
            actions=["update"],
        )
        result = classify_changes(
            drift_status="DRIFT_DETECTED", drift_findings=[drift],
            protected_types=["aws_dynamodb_table"],
        )
        self.assertEqual(result.overall, REVIEW)

    def test_drift_unknown_critical(self):
        result = classify_changes(drift_status="DRIFT_UNKNOWN")
        self.assertEqual(result.overall, CRITICAL)

    def test_noop_unverified_critical(self):
        result = classify_changes(noop_status="NO_OP_UNVERIFIED")
        self.assertEqual(result.overall, CRITICAL)

    def test_compatibility_review_and_blocking(self):
        self.assertEqual(
            classify_changes(compatibility_status="REVIEW_REQUIRED").overall, REVIEW
        )
        self.assertEqual(
            classify_changes(compatibility_status="MIGRATION_REQUIRED").overall,
            CRITICAL,
        )

    def test_overall_is_maximum(self):
        planned = [SimpleNamespace(
            address="module.x.aws_sqs_queue.q", resource_type="aws_sqs_queue",
            actions=["create"],
        )]
        result = classify_changes(
            planned_changes=planned,
            compatibility_status="REVIEW_REQUIRED",
        )
        self.assertEqual(result.overall, REVIEW)
        self.assertEqual(len(result.by_category(SAFE)), 1)


def _readiness_input(**overrides):
    data = dict(
        project="mays-orders-rc4",
        environment="development",
        region="eu-central-1",
        account_id="240571105849",
        backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate",
                 "workspace_key_prefix": "env:"},
        workspace="mays-orders-rc4",
        baseline={"serial": 7, "lineage": "l", "resources": 3, "status": "VERIFIED"},
        source_version="0.1.0",
        target_version="0.2.0",
        git_commit="a" * 40,
        plan_sha256="deadbeef",
        compatibility_status="COMPATIBLE",
        compatibility_reason="Patch-Upgrade",
        drift_status="NO_DRIFT",
        noop_status="CHANGES_PLANNED",
        planned_changes=[{"address": "module.x.aws_sqs_queue.q",
                          "type": "aws_sqs_queue", "actions": ["create"]}],
        classification={"overall": "SAFE", "changes": [], "reasons": []},
        blocking_reasons=[],
    )
    data.update(overrides)
    return ReadinessInput(**data)


class TestReadiness(unittest.TestCase):
    def test_ready(self):
        report = build_readiness_report(_readiness_input())
        self.assertEqual(report["status"], READY)
        self.assertFalse(report["approved"])

    def test_review_by_compatibility(self):
        payload = _readiness_input(compatibility_status="REVIEW_REQUIRED")
        self.assertEqual(decide_status(payload), READINESS_REVIEW)

    def test_review_by_classification(self):
        payload = _readiness_input(classification={"overall": "REVIEW", "changes": []})
        self.assertEqual(decide_status(payload), READINESS_REVIEW)

    def test_blocked_by_reasons(self):
        payload = _readiness_input(blocking_reasons=["UPGRADE_BLOCKED_COMPATIBILITY: x"])
        self.assertEqual(decide_status(payload), READINESS_BLOCKED)

    def test_blocked_by_critical_classification(self):
        payload = _readiness_input(classification={"overall": "CRITICAL", "changes": []})
        self.assertEqual(decide_status(payload), READINESS_BLOCKED)

    def test_no_changes(self):
        payload = _readiness_input(noop_status="NO_OP_VERIFIED", planned_changes=[])
        self.assertEqual(decide_status(payload), NO_CHANGES)

    def test_report_fields_and_markdown(self):
        report = build_readiness_report(_readiness_input())
        for key in ("schemaVersion", "status", "project", "environment", "aws",
                    "backend", "workspace", "state", "sourceVersion",
                    "targetVersion", "gitCommit", "compatibility", "driftStatus",
                    "noopStatus", "plannedChanges", "classification",
                    "migrationRequired", "blockingReasons", "nextSteps",
                    "evidenceLimits"):
            self.assertIn(key, report)
        md = render_readiness_markdown(report)
        for section in ("## 1. Projekt und Umgebung", "## 8. Versionskompatibilitaet",
                        "## 12. SAFE-/REVIEW-/CRITICAL-Klassifikation",
                        "## 14. Blockierende Gruende",
                        "## 15. Ergebnis und naechste Schritte"):
            self.assertIn(section, md)
        self.assertIn("keine Ausfuehrungsfreigabe", md)


class TestReadinessGate(unittest.TestCase):
    def _context(self, version="0.2.0"):
        ctx = MagicMock()
        ctx.deployment_version = version
        return ctx

    def _manifest(self, plan, *, compatibility=None, target="0.2.0"):
        PlanManifest.create(
            plan,
            deployment_id=DeploymentId("240571105849", "mays-orders-rc4", "development"),
            operation=PlanOperation.DEPLOY,
            region="eu-central-1",
            workspace="mays-orders-rc4",
            backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate"},
            git_commit="a" * 40,
            source_version="0.1.0",
            target_version=target,
            git_dirty=False,
            version_status="VERIFIED",
            version_source="terraform_output",
            compatibility_status=compatibility,
            readiness_status="READY",
        ).write(plan)

    def _check(self, compatibility, *, accept=False, target="0.2.0", context_version=None):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            self._manifest(plan, compatibility=compatibility, target=target)
            cli = InstallerCLI()
            parsed = SimpleNamespace(accept_upgrade_review=accept)
            return cli._verify_upgrade_readiness(
                self._context(context_version or target), plan, parsed
            )

    def test_non_upgrade_plan_passes(self):
        self.assertTrue(self._check(None))

    def test_compatible_passes(self):
        # Patch-Upgrade 0.1.0 -> 0.1.1 ist ohne Zusatznachweis COMPATIBLE.
        self.assertTrue(self._check("COMPATIBLE", target="0.1.1"))

    def test_review_blocks_without_flag(self):
        self.assertFalse(self._check("REVIEW_REQUIRED"))

    def test_review_allowed_with_flag(self):
        self.assertTrue(self._check("REVIEW_REQUIRED", accept=True))

    def test_migration_blocks(self):
        self.assertFalse(self._check("MIGRATION_REQUIRED"))

    def test_incompatible_blocks(self):
        self.assertFalse(self._check("INCOMPATIBLE"))

    def test_apply_not_started_when_readiness_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            plan = run_dir / "plan.tfplan"
            plan.write_bytes(b"plan")
            self._manifest(plan, compatibility="MIGRATION_REQUIRED")
            cli = InstallerCLI()
            runner = MagicMock()
            runner.show_plan.return_value = SimpleNamespace(success=True, stdout="{}", stderr="")
            cli._make_runner = MagicMock(return_value=runner)
            ctx = MagicMock()
            ctx.allow_aws_operations = True
            ctx.dry_run = False
            ctx.terraform_dir = "terraform"
            ctx.aws_region = "eu-central-1"
            ctx.aws_profile = "mayaws"
            ctx.project_name = "mays-orders-rc4"
            ctx.environment = "development"
            ctx.terraform_workspace = "mays-orders-rc4"
            ctx.deployment_version = "0.2.0"
            ctx.development_phase = "H2"
            ctx.development_step = 0
            ctx.development_status = "development"
            ctx.run_id = "run"
            ctx.validate_aws_context.return_value = True
            ctx.get_deployment_context.return_value = SimpleNamespace(
                deployment_id=DeploymentId("240571105849", "mays-orders-rc4", "development")
            )
            parsed = SimpleNamespace(plan=str(plan), yes=False,
                                     allow_dirty_source=False, allow_legacy_source=False,
                                     accept_upgrade_review=False)
            with patch.object(InstallerCLI, "_verify_plan_manifest", return_value=True), \
                 patch.object(InstallerCLI, "_verify_version_binding", return_value=True), \
                 patch.object(InstallerCLI, "_verify_state_baseline", return_value=True):
                code = cli._cmd_deploy(ctx, parsed, run_dir)
            self.assertEqual(code, 1)
            runner.apply.assert_not_called()


class TestUpgradeCliFlag(unittest.TestCase):
    def test_parser_accepts_upgrade(self):
        cli = InstallerCLI()
        parsed = cli.parser.parse_args(["--project-name", "mays-orders-rc4", "plan", "--remote", "--upgrade"])
        self.assertTrue(parsed.remote)
        self.assertTrue(parsed.upgrade)

    def test_default_is_not_upgrade(self):
        cli = InstallerCLI()
        parsed = cli.parser.parse_args(["--project-name", "mays-orders-rc4", "plan", "--remote"])
        self.assertFalse(parsed.upgrade)

    def test_plan_rejects_upgrade_without_remote(self):
        import inspect

        source = inspect.getsource(InstallerCLI._cmd_plan)
        self.assertIn("UPGRADE_REQUIRES_REMOTE", source)
        self.assertIn("check_upgrade_source", source)


if __name__ == "__main__":
    unittest.main()
