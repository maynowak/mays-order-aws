"""MO-RC4-UPGRADE-RELEASE-GATES-01: lokale Tests fuer Backup-Gate + Matrix.

Keine AWS-/Terraform-Aufrufe.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from installer.cli.main import InstallerCLI
from installer.core.backup_gate import (
    BACKUP_FAILED,
    BACKUP_IDENTITY_MISMATCH,
    BACKUP_INVALID,
    BACKUP_MISSING,
    BACKUP_NOT_REQUIRED,
    BACKUP_PARTIAL,
    BACKUP_STALE,
    BACKUP_VERIFIED,
    CODE_HASH_MISMATCH,
    CODE_IDENTITY_MISMATCH,
    CODE_MISSING,
    CODE_NOT_VERIFIED,
    CODE_STATE_MISMATCH,
    assess_backup_evidence,
    assess_manifest_evidence,
    requires_backup,
)
from installer.core.compatibility import (
    COMPATIBLE,
    REVIEW_REQUIRED,
    assess_compatibility,
)
from installer.core.deployment_identity import DeploymentId, PlanOperation
from installer.core.plan_manifest import PlanManifest
from installer.core.upgrade_readiness import (
    BLOCKED as READINESS_BLOCKED,
    READY,
    ReadinessInput,
    build_readiness_report,
    render_readiness_markdown,
)
from installer.core.version_matrix import (
    MATRIX,
    lookup_compatibility,
    matrix_report,
)

PROJECT = "mays-orders-rc4"
ENV = "development"
REGION = "eu-central-1"
ACCOUNT = "240571105849"
TABLE_ARN = f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{PROJECT}"
LINEAGE = "lineage-1"
SERIAL = 7
FINGERPRINT = "a" * 64
FINGERPRINT_VERSION = "canonical-sha256-v1"


def valid_evidence(**overrides):
    data = {
        "schemaVersion": 1,
        "project": PROJECT,
        "environment": ENV,
        "awsAccount": ACCOUNT,
        "region": REGION,
        "tableName": PROJECT,
        "tableArn": TABLE_ARN,
        "backupName": f"{PROJECT}-{ENV}-orders-preupgrade-20261103T120000Z",
        "backupArn": f"{TABLE_ARN}/backup/01700000000000-abcdef",
        "backupStatus": "AVAILABLE",
        "backupVerifiedAt": "2026-11-03T12:00:00+00:00",
        "pitrStatus": "ENABLED",
        "earliestRestorableAt": "2026-11-01T00:00:00+00:00",
        "latestRestorableAt": "2026-11-03T00:00:00+00:00",
        "overallStatus": "VERIFIED",
        "identityVerified": True,
        "stateLineage": LINEAGE,
        "stateSerial": SERIAL,
        "stateFingerprint": FINGERPRINT,
        "stateFingerprintVersion": FINGERPRINT_VERSION,
        "generatedAt": "2026-11-03T12:00:01+00:00",
    }
    data.update(overrides)
    return data


def assess(path, *, required=True, **overrides):
    values = dict(
        required=required,
        expected_project=PROJECT,
        expected_environment=ENV,
        expected_account=ACCOUNT,
        expected_region=REGION,
        state_lineage=LINEAGE,
        state_serial=SERIAL,
        state_fingerprint=FINGERPRINT,
    )
    values.update(overrides)
    return assess_backup_evidence(path, **values)


class TestVersionMatrix(unittest.TestCase):
    def test_rc3_rc4_exact_pair_is_evidenced(self):
        entry = lookup_compatibility("0.1.0", "0.2.0")
        self.assertIsNotNone(entry)
        self.assertIn("GSI3", entry.reason)
        self.assertTrue(any("main.tf" in item for item in entry.evidence))
        self.assertTrue(any("0 replace/0 delete" in item for item in entry.conditions))

    def test_matrix_has_no_wildcard(self):
        self.assertIsNone(lookup_compatibility("0.1.0", "0.2.1"))
        self.assertIsNone(lookup_compatibility("0.2.0", "0.3.0"))
        self.assertIsNone(lookup_compatibility("0.1.1", "0.2.0"))

    def test_matrix_report_lists_limits(self):
        report = matrix_report()
        self.assertEqual(report["schemaVersion"], 1)
        self.assertEqual(len(report["entries"]), len(MATRIX))
        self.assertTrue(any("Deployment" in item for item in report["limits"]))

    def test_compatibility_uses_matrix_for_exact_pair(self):
        result = assess_compatibility("0.1.0", "0.2.0")
        self.assertEqual(result.status, COMPATIBLE)
        self.assertIn("Evidenzmatrix", result.reason)

    def test_unlisted_minor_still_requires_review(self):
        self.assertEqual(
            assess_compatibility("0.2.0", "0.3.0").status, REVIEW_REQUIRED
        )

    def test_matrix_does_not_override_legacy_or_major(self):
        legacy = assess_compatibility(
            None, "0.2.0", source_status="LEGACY_UNKNOWN"
        )
        self.assertEqual(legacy.status, "UNKNOWN")
        self.assertEqual(
            assess_compatibility("0.1.0", "1.0.0").status, "MIGRATION_REQUIRED"
        )


class TestBackupGate(unittest.TestCase):
    def _write(self, data, tmp):
        path = Path(tmp) / "order-backup-evidence.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_not_required(self):
        result = assess(None, required=False)
        self.assertEqual(result.status, BACKUP_NOT_REQUIRED)
        self.assertFalse(result.blocking)
        self.assertTrue(result.verified)

    def test_missing_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(Path(tmp) / "missing.json")
        self.assertEqual(result.status, BACKUP_MISSING)
        self.assertTrue(result.blocking)
        self.assertEqual(result.code, CODE_MISSING)

    def test_valid_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(), tmp))
        self.assertEqual(result.status, BACKUP_VERIFIED)
        self.assertFalse(result.blocking)
        self.assertEqual(result.backup_arn, valid_evidence()["backupArn"])
        self.assertIsNotNone(result.sha256)

    def test_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(project="other"), tmp))
        self.assertEqual(result.status, BACKUP_IDENTITY_MISMATCH)
        self.assertEqual(result.code, CODE_IDENTITY_MISMATCH)

    def test_environment_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(environment="production"), tmp))
        self.assertEqual(result.status, BACKUP_IDENTITY_MISMATCH)

    def test_region_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(region="us-east-1"), tmp))
        self.assertEqual(result.status, BACKUP_IDENTITY_MISMATCH)

    def test_account_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(awsAccount="999999999999"), tmp))
        self.assertEqual(result.status, BACKUP_IDENTITY_MISMATCH)

    def test_table_arn_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(tableArn="arn:aws:dynamodb:eu-central-1:240571105849:table/other"), tmp))
        self.assertEqual(result.status, BACKUP_IDENTITY_MISMATCH)

    def test_state_serial_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(stateSerial=SERIAL + 1), tmp))
        self.assertEqual(result.status, BACKUP_STALE)
        self.assertEqual(result.code, CODE_STATE_MISMATCH)

    def test_state_lineage_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(stateLineage="other"), tmp))
        self.assertEqual(result.status, BACKUP_STALE)

    def test_backup_not_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(backupStatus="CREATING"), tmp))
        self.assertEqual(result.status, BACKUP_FAILED)
        self.assertEqual(result.code, CODE_NOT_VERIFIED)

    def test_partial_pitr(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(
                self._write(valid_evidence(overallStatus="PARTIAL", pitrStatus="DISABLED"), tmp)
            )
        self.assertEqual(result.status, BACKUP_PARTIAL)
        self.assertTrue(result.blocking)

    def test_unknown_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(schemaVersion=2), tmp))
        self.assertEqual(result.status, BACKUP_INVALID)

    def test_missing_required_field(self):
        data = valid_evidence()
        data.pop("backupArn")
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(data, tmp))
        self.assertEqual(result.status, BACKUP_INVALID)

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "order-backup-evidence.json"
            path.write_text("{not-json", encoding="utf-8")
            result = assess(path)
        self.assertEqual(result.status, BACKUP_INVALID)

    def test_tampered_evidence_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(valid_evidence(), tmp)
            result = assess(path, expected_sha256="0" * 64)
        self.assertEqual(result.status, BACKUP_INVALID)
        self.assertEqual(result.code, CODE_HASH_MISMATCH)

    def test_invalid_verified_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(self._write(valid_evidence(backupVerifiedAt="not-a-date"), tmp))
        self.assertEqual(result.status, BACKUP_INVALID)

    def test_manifest_evidence_resolves_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            path = self._write(valid_evidence(), tmp)
            assessment = assess(path)
            summary = assessment.to_manifest()
            result = assess_manifest_evidence(
                plan,
                summary,
                expected_project=PROJECT,
                expected_environment=ENV,
                expected_account=ACCOUNT,
                expected_region=REGION,
                state_lineage=LINEAGE,
                state_serial=SERIAL,
                state_fingerprint=FINGERPRINT,
            )
        self.assertEqual(result.status, BACKUP_VERIFIED)

    def test_manifest_evidence_detects_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            path = self._write(valid_evidence(), tmp)
            summary = assess(path).to_manifest()
            path.write_text(json.dumps(valid_evidence(pitrStatus="DISABLED")), encoding="utf-8")
            result = assess_manifest_evidence(
                plan,
                summary,
                expected_project=PROJECT,
                expected_environment=ENV,
                expected_account=ACCOUNT,
                expected_region=REGION,
                state_lineage=LINEAGE,
                state_serial=SERIAL,
                state_fingerprint=FINGERPRINT,
            )
        self.assertEqual(result.status, BACKUP_INVALID)
        self.assertEqual(result.code, CODE_HASH_MISMATCH)

    def test_requires_backup_only_for_version_change(self):
        self.assertTrue(requires_backup("0.1.0", "0.2.0"))
        self.assertFalse(requires_backup("0.1.0", "0.1.0"))
        self.assertFalse(requires_backup(None, "0.2.0"))
        self.assertFalse(requires_backup("0.1.0", "0.2.0", operation="destroy"))

    def test_manifest_summary_has_no_payload_or_pii(self):
        with tempfile.TemporaryDirectory() as tmp:
            assessment = assess(self._write(valid_evidence(), tmp))
        summary = assessment.to_manifest()
        text = json.dumps(summary)
        for forbidden in ("customer", "items", "email", "subjectId", "backupName"):
            self.assertNotIn(forbidden, text)
        self.assertIn("sha256", summary)


def readiness_input(**overrides):
    data = dict(
        project=PROJECT,
        environment=ENV,
        region=REGION,
        account_id=ACCOUNT,
        backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate"},
        workspace=PROJECT,
        baseline={"serial": SERIAL, "lineage": LINEAGE, "resources": 3, "status": "VERIFIED"},
        source_version="0.1.0",
        target_version="0.2.0",
        git_commit="a" * 40,
        plan_sha256="deadbeef",
        compatibility_status="COMPATIBLE",
        compatibility_reason="Minor-Upgrade durch Evidenzmatrix belegt",
        drift_status="NO_DRIFT",
        noop_status="CHANGES_PLANNED",
        planned_changes=[{"address": "module.x.aws_sqs_queue.q", "type": "aws_sqs_queue", "actions": ["create"]}],
        classification={"overall": "SAFE", "changes": [], "reasons": []},
        blocking_reasons=[],
        backup_required=True,
        backup_status=BACKUP_VERIFIED,
        backup_reason="Backup-Evidenz ist vollstaendig VERIFIED.",
        backup_evidence={"status": BACKUP_VERIFIED, "sha256": "f" * 64},
    )
    data.update(overrides)
    return ReadinessInput(**data)


class TestReadinessBackupGate(unittest.TestCase):
    def test_verified_backup_is_ready(self):
        report = build_readiness_report(readiness_input())
        self.assertEqual(report["status"], READY)
        self.assertTrue(report["backupRequired"])
        self.assertEqual(report["backupEvidence"]["status"], BACKUP_VERIFIED)

    def test_missing_backup_blocks(self):
        report = build_readiness_report(
            readiness_input(backup_status=BACKUP_MISSING, backup_reason="fehlt")
        )
        self.assertEqual(report["status"], READINESS_BLOCKED)

    def test_partial_backup_blocks(self):
        report = build_readiness_report(readiness_input(backup_status=BACKUP_PARTIAL))
        self.assertEqual(report["status"], READINESS_BLOCKED)

    def test_not_required_is_not_blocking(self):
        report = build_readiness_report(
            readiness_input(backup_required=False, backup_status=BACKUP_NOT_REQUIRED)
        )
        self.assertEqual(report["status"], READY)
        self.assertFalse(report["backupRequired"])

    def test_markdown_contains_backup_section(self):
        md = render_readiness_markdown(build_readiness_report(readiness_input()))
        self.assertIn("## 16. Backup-Evidenz (P3A)", md)
        self.assertIn("VERIFIED", md)

    def test_report_limit_states_local_evidence(self):
        report = build_readiness_report(readiness_input())
        limits = "\n".join(report["evidenceLimits"])
        self.assertIn("keinen realen AWS-Backup-Test", limits)


class TestManifestBackupBinding(unittest.TestCase):
    def test_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            manifest = PlanManifest.create(
                plan,
                deployment_id=DeploymentId(ACCOUNT, PROJECT, ENV),
                operation=PlanOperation.DEPLOY,
                region=REGION,
                workspace=PROJECT,
                backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate"},
                source_version="0.1.0",
                target_version="0.2.0",
                backup_required=True,
                backup_evidence={"status": BACKUP_VERIFIED, "fileName": "order-backup-evidence.json",
                                 "sha256": "f" * 64},
            )
            manifest.write(plan)
            loaded = PlanManifest.load(plan)
            self.assertTrue(loaded.backup_required)
            self.assertEqual(loaded.backup_evidence["status"], BACKUP_VERIFIED)

    def test_old_manifest_defaults_to_not_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            manifest = PlanManifest.create(
                plan,
                deployment_id=DeploymentId(ACCOUNT, PROJECT, ENV),
                operation=PlanOperation.DEPLOY,
                region=REGION,
                workspace=PROJECT,
                backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate"},
            )
            manifest.write(plan)
            loaded = PlanManifest.load(plan)
            self.assertIsNone(loaded.backup_required)
            self.assertIsNone(loaded.backup_evidence)


class TestDeployBackupGate(unittest.TestCase):
    def _context(self):
        return SimpleNamespace(
            project_name=PROJECT,
            environment=ENV,
            aws_region=REGION,
            aws_execution_context=SimpleNamespace(account_id=ACCOUNT),
        )

    def _manifest(self, plan, *, summary=None, required=True, source="0.1.0", target="0.2.0"):
        PlanManifest.create(
            plan,
            deployment_id=DeploymentId(ACCOUNT, PROJECT, ENV),
            operation=PlanOperation.DEPLOY,
            region=REGION,
            workspace=PROJECT,
            backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate"},
            source_version=source,
            target_version=target,
            backup_required=required,
            backup_evidence=summary,
            state_baseline={"status": "VERIFIED", "serial": SERIAL, "lineage": LINEAGE, "fingerprint": FINGERPRINT, "fingerprintVersion": FINGERPRINT_VERSION},
        ).write(plan)

    def _run(self, plan):
        with contextlib.redirect_stdout(io.StringIO()):
            return InstallerCLI()._verify_backup_gate(self._context(), plan)

    def test_verified_manifest_evidence_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            path = Path(tmp) / "order-backup-evidence.json"
            path.write_text(json.dumps(valid_evidence()), encoding="utf-8")
            summary = assess(path).to_manifest()
            self._manifest(plan, summary=summary)
            self.assertTrue(self._run(plan))

    def test_missing_summary_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            self._manifest(plan, summary=None)
            self.assertFalse(self._run(plan))

    def test_missing_file_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            self._manifest(plan, summary={"fileName": "order-backup-evidence.json",
                                          "sha256": "f" * 64})
            self.assertFalse(self._run(plan))

    def test_not_required_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            self._manifest(plan, required=False, source="0.2.0", target="0.2.0")
            self.assertTrue(self._run(plan))

    def test_manifest_flag_cannot_bypass_version_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.tfplan"
            plan.write_bytes(b"plan")
            self._manifest(plan, required=False, source="0.1.0", target="0.2.0")
            self.assertFalse(self._run(plan))

    def test_plan_and_deploy_are_wired_to_backup_gate(self):
        import inspect

        plan_source = inspect.getsource(InstallerCLI._cmd_plan)
        deploy_source = inspect.getsource(InstallerCLI._cmd_deploy)
        self.assertIn("assess_backup_evidence", plan_source)
        self.assertIn("copy_evidence_to_run_dir", plan_source)
        self.assertIn("backup_required", plan_source)
        self.assertIn("_verify_backup_gate", deploy_source)

    def test_parser_accepts_backup_evidence(self):
        parsed = InstallerCLI().parser.parse_args(
            ["--project-name", PROJECT, "plan", "--remote", "--upgrade",
             "--backup-evidence", "evidence.json"]
        )
        self.assertEqual(parsed.backup_evidence, "evidence.json")


if __name__ == "__main__":
    unittest.main()
