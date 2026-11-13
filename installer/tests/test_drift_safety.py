"""MO-INSTALLER-UPGRADE-DRIFT-SAFETY-P0C-01: State-Baseline, Drift, No-op.

Rein lokal: keine AWS-/Terraform-Aufrufe (Runner wird gemockt).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from installer.cli.main import InstallerCLI
from installer.core.deployment_identity import DeploymentId, PlanOperation
from installer.core.drift import (
    CHANGES_PLANNED,
    DRIFT_DETECTED,
    DRIFT_UNKNOWN,
    NO_DRIFT,
    NO_OP_UNVERIFIED,
    NO_OP_VERIFIED,
    assess_plan,
    build_drift_report,
    render_drift_markdown,
    write_drift_report,
)
from installer.core.plan_manifest import PlanManifest
from installer.core.state_baseline import (
    MISSING_LINEAGE,
    MISSING_SERIAL,
    NO_STATE,
    UNREADABLE,
    VERIFIED,
    capture_state_baseline,
    compare_state_baseline,
)

DEPLOYMENT_ID = DeploymentId("240571105849", "mays-orders-rc4", "development")
STATE = {"version": 4, "terraform_version": "1.16.1", "serial": 7,
         "lineage": "lineage-abc", "resources": [{"type": "aws_dynamodb_table"}]}


def _runner(state=None, success=True, raw=None):
    runner = MagicMock()
    payload = raw if raw is not None else json.dumps(state or {})
    runner.state_pull.return_value = SimpleNamespace(success=success, stdout=payload, stderr="")
    return runner


def _plan(*changes, drift=None, outputs=None, complete=True):
    plan = {"resource_changes": list(changes), "complete": complete, "errored": False}
    if drift is not None:
        plan["resource_drift"] = drift
    if outputs is not None:
        plan["output_changes"] = outputs
    return plan


def _change(address, resource_type, actions):
    return {"address": address, "type": resource_type,
            "change": {"actions": actions}}


class TestStateBaseline(unittest.TestCase):
    def test_verified_baseline(self):
        baseline = capture_state_baseline(_runner(STATE))
        self.assertEqual(baseline.status, VERIFIED)
        self.assertEqual(baseline.serial, 7)
        self.assertEqual(baseline.lineage, "lineage-abc")
        self.assertEqual(baseline.resources, 1)
        self.assertRegex(baseline.fingerprint or "", r"^[0-9a-f]{64}$")

    def test_empty_state_is_no_state_with_identity(self):
        baseline = capture_state_baseline(
            _runner({"version": 4, "serial": 2, "lineage": "l", "resources": []})
        )
        self.assertEqual(baseline.status, NO_STATE)
        self.assertEqual(baseline.serial, 2)
        self.assertEqual(baseline.resources, 0)

    def test_missing_lineage(self):
        baseline = capture_state_baseline(
            _runner({"serial": 3, "resources": [{"type": "x"}]})
        )
        self.assertEqual(baseline.status, MISSING_LINEAGE)

    def test_missing_serial(self):
        baseline = capture_state_baseline(
            _runner({"lineage": "l", "resources": []})
        )
        self.assertEqual(baseline.status, MISSING_SERIAL)

    def test_unreadable_state(self):
        self.assertEqual(capture_state_baseline(_runner(success=False)).status, UNREADABLE)

    def test_invalid_json(self):
        self.assertEqual(capture_state_baseline(_runner(raw="{broken")).status, UNREADABLE)

    def test_report_contains_no_state_values(self):
        baseline = capture_state_baseline(_runner(STATE))
        payload = json.dumps(baseline.to_dict())
        self.assertNotIn("aws_dynamodb_table", payload)
        self.assertNotIn("lineage-abc\"", payload.replace('"lineage": "lineage-abc"', ""))

    def test_compare_match(self):
        baseline = capture_state_baseline(_runner(STATE))
        ok, code, _ = compare_state_baseline(baseline.to_dict(), baseline)
        self.assertTrue(ok, code)

    def test_compare_serial_mismatch(self):
        baseline = capture_state_baseline(_runner(STATE))
        current = capture_state_baseline(_runner({**STATE, "serial": 8}))
        ok, code, _ = compare_state_baseline(baseline.to_dict(), current)
        self.assertFalse(ok)
        self.assertEqual(code, "UPGRADE_STATE_BASELINE_MISMATCH")

    def test_compare_lineage_mismatch(self):
        baseline = capture_state_baseline(_runner(STATE))
        current = capture_state_baseline(_runner({**STATE, "lineage": "other"}))
        ok, code, _ = compare_state_baseline(baseline.to_dict(), current)
        self.assertFalse(ok)
        self.assertEqual(code, "UPGRADE_STATE_BASELINE_MISMATCH")

    def test_compare_missing_baseline(self):
        current = capture_state_baseline(_runner(STATE))
        ok, code, _ = compare_state_baseline(None, current)
        self.assertFalse(ok)
        self.assertEqual(code, "UPGRADE_STATE_BASELINE_MISSING")

    def test_compare_unreadable(self):
        ok, code, _ = compare_state_baseline({"serial": 1, "lineage": "x"}, capture_state_baseline(_runner(success=False)))
        self.assertFalse(ok)
        self.assertEqual(code, "UPGRADE_STATE_UNREADABLE")


class TestDriftClassification(unittest.TestCase):
    def test_no_prior_state(self):
        plan = _plan()
        assessment = assess_plan(plan, has_prior_state=False)
        self.assertEqual(assessment.drift_status, NO_DRIFT)
        self.assertEqual(assessment.noop_status, NO_OP_VERIFIED)

    def test_no_drift_with_empty_refresh(self):
        assessment = assess_plan(_plan(drift=[]), has_prior_state=True)
        self.assertEqual(assessment.drift_status, NO_DRIFT)
        self.assertEqual(assessment.noop_status, NO_OP_VERIFIED)

    def test_missing_drift_evidence_is_unknown(self):
        assessment = assess_plan(_plan(), has_prior_state=True)
        self.assertEqual(assessment.drift_status, DRIFT_UNKNOWN)
        self.assertEqual(assessment.noop_status, NO_OP_UNVERIFIED)

    def test_drift_detected(self):
        drift = [{"address": "module.sqs.aws_sqs_queue.orders",
                  "type": "aws_sqs_queue", "change": {"actions": ["update"]}}]
        assessment = assess_plan(_plan(drift=drift), has_prior_state=True)
        self.assertEqual(assessment.drift_status, DRIFT_DETECTED)
        self.assertEqual(len(assessment.drift_findings), 1)
        self.assertEqual(assessment.noop_status, NO_OP_UNVERIFIED)

    def test_unknown_drift_action_is_fail_closed(self):
        drift = [{"address": "x", "type": "aws_sqs_queue",
                  "change": {"actions": ["frobnicate"]}}]
        assessment = assess_plan(_plan(drift=drift), has_prior_state=True)
        self.assertEqual(assessment.drift_status, DRIFT_UNKNOWN)

    def test_planned_gsi_change(self):
        plan = _plan(_change("module.dynamodb.aws_dynamodb_table.orders",
                             "aws_dynamodb_table", ["update"]), drift=[])
        assessment = assess_plan(plan, has_prior_state=True)
        self.assertEqual(assessment.drift_status, NO_DRIFT)
        self.assertEqual(assessment.noop_status, CHANGES_PLANNED)
        self.assertEqual(assessment.planned_changes[0].address,
                         "module.dynamodb.aws_dynamodb_table.orders")

    def test_output_change_counts_as_change(self):
        plan = _plan(drift=[], outputs={"mo_version": {"actions": ["update"]}})
        assessment = assess_plan(plan, has_prior_state=True)
        self.assertEqual(assessment.noop_status, CHANGES_PLANNED)

    def test_incomplete_plan_is_unverified(self):
        plan = _plan(drift=[], complete=False)
        assessment = assess_plan(plan, has_prior_state=True)
        self.assertEqual(assessment.noop_status, NO_OP_UNVERIFIED)

    def test_unknown_plan_action_is_unverified(self):
        plan = _plan(_change("x", "aws_sqs_queue", ["frobnicate"]), drift=[])
        assessment = assess_plan(plan, has_prior_state=True)
        self.assertEqual(assessment.noop_status, NO_OP_UNVERIFIED)


class TestDriftReport(unittest.TestCase):
    def _assessment(self):
        return assess_plan(
            _plan(_change("module.sqs.aws_sqs_queue.orders", "aws_sqs_queue", ["update"]),
                  drift=[]),
            has_prior_state=True,
        )

    def test_report_fields_and_markdown(self):
        assessment = self._assessment()
        baseline = capture_state_baseline(_runner(STATE)).to_dict()
        report = build_drift_report(
            assessment,
            project="mays-orders-rc4",
            environment="development",
            workspace="mays-orders-rc4",
            baseline=baseline,
            source_version="0.1.0",
            target_version="0.2.0",
            git_commit="a" * 40,
            critical_changes=[],
            blocking_reasons=[],
        )
        self.assertEqual(report["schemaVersion"], 1)
        self.assertEqual(report["driftStatus"], NO_DRIFT)
        self.assertEqual(report["noopStatus"], CHANGES_PLANNED)
        self.assertEqual(report["state"]["serial"], 7)
        self.assertFalse(report["approved"])
        md = render_drift_markdown(report)
        for section in ("## State-Identitaet", "## Geplante Upgrade-Aenderungen",
                        "## Erkannte Drift", "## Blockierende Gruende",
                        "## Nachweisgrenzen"):
            self.assertIn(section, md)
        self.assertIn("keine Ausfuehrungsfreigabe", md)

    def test_report_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            assessment = self._assessment()
            baseline = capture_state_baseline(_runner(STATE)).to_dict()
            report = build_drift_report(
                assessment, project="p", environment="development", workspace="p",
                baseline=baseline, source_version=None, target_version="0.2.0",
                git_commit=None, critical_changes=[], blocking_reasons=[],
            )
            json_path, md_path = write_drift_report(tmp, report)
            self.assertTrue(json_path.exists() and md_path.exists())
            data = json.loads(json_path.read_text())
            self.assertEqual(data["workspace"], "p")
            self.assertNotIn("aws_dynamodb_table", json_path.read_text())


class TestManifestBaseline(unittest.TestCase):
    def test_roundtrip_with_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            baseline = capture_state_baseline(_runner(STATE)).to_dict()
            manifest = PlanManifest.create(
                plan,
                deployment_id=DEPLOYMENT_ID,
                operation=PlanOperation.DEPLOY,
                region="eu-central-1",
                workspace="mays-orders-rc4",
                backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate",
                         "region": "eu-central-1", "workspace_key_prefix": "env:"},
                git_commit="a" * 40,
                target_version="0.2.0",
                git_dirty=False,
                version_status="VERIFIED",
                version_source="terraform_output",
                state_baseline=baseline,
                drift_status=NO_DRIFT,
                noop_status=NO_OP_VERIFIED,
            )
            manifest.write(plan)
            loaded = PlanManifest.load(plan)
            self.assertEqual(loaded.state_baseline["serial"], 7)
            self.assertEqual(loaded.drift_status, NO_DRIFT)
            self.assertEqual(loaded.noop_status, NO_OP_VERIFIED)


class TestCliBaselineGate(unittest.TestCase):
    def _context(self):
        ctx = MagicMock()
        ctx.project_name = "mays-orders-rc4"
        ctx.environment = "development"
        ctx.terraform_workspace = "mays-orders-rc4"
        ctx.terraform_dir = "terraform"
        ctx.aws_region = "eu-central-1"
        ctx.aws_profile = "mayaws"
        ctx.deployment_version = "0.2.0"
        ctx.run_id = "run"
        ctx.development_phase = "H2"
        ctx.development_step = 0
        ctx.development_status = "development"
        ctx.dry_run = False
        ctx.allow_aws_operations = True
        ctx.validate_aws_context.return_value = True
        ctx.get_deployment_context.return_value = SimpleNamespace(deployment_id=DEPLOYMENT_ID)
        return ctx

    def _manifest_with_baseline(self, plan: Path, serial=7):
        baseline = capture_state_baseline(_runner({**STATE, "serial": serial})).to_dict()
        PlanManifest.create(
            plan,
            deployment_id=DEPLOYMENT_ID,
            operation=PlanOperation.DEPLOY,
            region="eu-central-1",
            workspace="mays-orders-rc4",
            backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate",
                     "region": "eu-central-1", "workspace_key_prefix": "env:"},
            git_commit="a" * 40,
            target_version="0.2.0",
            git_dirty=False,
            version_status="VERIFIED",
            version_source="terraform_output",
            state_baseline=baseline,
            drift_status=NO_DRIFT,
            noop_status=NO_OP_VERIFIED,
        ).write(plan)

    def test_matching_baseline_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            self._manifest_with_baseline(plan)
            cli = InstallerCLI()
            cli._make_runner = MagicMock(return_value=_runner(STATE))
            self.assertTrue(cli._verify_state_baseline(self._context(), plan))

    def test_serial_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            self._manifest_with_baseline(plan, serial=7)
            cli = InstallerCLI()
            cli._make_runner = MagicMock(return_value=_runner({**STATE, "serial": 8}))
            self.assertFalse(cli._verify_state_baseline(self._context(), plan))

    def test_missing_baseline_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            PlanManifest.create(
                plan, deployment_id=DEPLOYMENT_ID, operation=PlanOperation.DEPLOY,
                region="eu-central-1", workspace="mays-orders-rc4",
                backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate"},
                git_commit="a" * 40, target_version="0.2.0", git_dirty=False,
                version_status="VERIFIED", version_source="terraform_output",
            ).write(plan)
            cli = InstallerCLI()
            cli._make_runner = MagicMock(return_value=_runner(STATE))
            self.assertFalse(cli._verify_state_baseline(self._context(), plan))

    def test_apply_not_started_when_baseline_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            plan = run_dir / "plan.tfplan"
            plan.write_bytes(b"plan")
            cli = InstallerCLI()
            runner = MagicMock()
            runner.show_plan.return_value = SimpleNamespace(success=True, stdout="{}", stderr="")
            cli._make_runner = MagicMock(return_value=runner)
            parsed = SimpleNamespace(plan=str(plan), yes=False,
                                     allow_dirty_source=False, allow_legacy_source=False)
            with patch.object(InstallerCLI, "_verify_plan_manifest", return_value=True), \
                 patch.object(InstallerCLI, "_verify_version_binding", return_value=True), \
                 patch.object(InstallerCLI, "_verify_state_baseline", return_value=False):
                code = cli._cmd_deploy(self._context(), parsed, run_dir)
            self.assertEqual(code, 1)
            runner.apply.assert_not_called()

    def test_plan_integrates_drift_before_manifest(self):
        import inspect

        source = inspect.getsource(InstallerCLI._cmd_plan)
        self.assertIn("capture_state_baseline", source)
        self.assertIn("write_drift_report", source)
        self.assertLess(source.index("capture_state_baseline"),
                        source.index("PlanManifest.create"))

    def test_deploy_baseline_check_before_apply(self):
        import inspect

        source = inspect.getsource(InstallerCLI._cmd_deploy)
        self.assertIn("_verify_state_baseline", source)
        self.assertLess(source.index("_verify_state_baseline"),
                        source.index("runner.apply("))


if __name__ == "__main__":
    unittest.main()
