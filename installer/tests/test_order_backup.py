"""P3A-01: lokale Fake-Client-Tests fuer die Order-Backup-Orchestrierung.

Kein boto3, kein AWS, kein Terraform. Der DynamoDB-Client wird injiziert.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from installer.core import order_backup as ob
from installer.core.order_backup import (
    BACKUP_AVAILABLE,
    BACKUP_CREATING,
    BACKUP_FAILED,
    BACKUP_TIMEOUT,
    CODE_ACCESS_DENIED,
    CODE_ARN_MISSING,
    CODE_BACKUP_IDENTITY_MISMATCH,
    CODE_BACKUP_FAILED,
    CODE_CREATE_FAILED,
    CODE_DESCRIBE_FAILED,
    CODE_EVIDENCE_MISMATCH,
    CODE_IDENTITY_MISMATCH,
    CODE_NAME_CONFLICT,
    CODE_NAME_INVALID,
    CODE_PITR_UNVERIFIED,
    CODE_STATE_BASELINE_REQUIRED,
    CODE_TABLE_NOT_ACTIVE,
    CODE_TABLE_NOT_FOUND,
    CODE_TIMEOUT,
    OVERALL_FAILED,
    OVERALL_PARTIAL,
    OVERALL_UNVERIFIED,
    OVERALL_VERIFIED,
    PITR_DISABLED,
    PITR_ENABLED,
    PITR_UNKNOWN,
    OrderBackupError,
    TableIdentity,
    build_backup_name,
    check_pitr,
    execute_order_backup,
    expected_table_identity,
    plan_order_backup,
    validate_evidence_binding,
    verify_table_identity,
    write_evidence,
    write_plan,
)

FIXED_NOW = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
BASELINE = {
    "status": "VERIFIED",
    "serial": 42,
    "lineage": "lineage-abc",
    "fingerprint": "f" * 64,
    "fingerprintVersion": "canonical-sha256-v1",
    "captured_at": "2026-11-03T11:59:00+00:00",
}


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.value = start

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class FakeClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code, "Message": "fake"}}


def make_expected(**overrides) -> TableIdentity:
    values = dict(
        project="mays-orders",
        environment="Development",
        aws_account="123456789012",
        region="eu-central-1",
        state_baseline=BASELINE,
    )
    values.update(overrides)
    return expected_table_identity(**values)


class FakeDynamo:
    def __init__(
        self,
        expected: TableIdentity,
        *,
        statuses=("CREATING", "AVAILABLE"),
        pitr_status="ENABLED",
        earliest="2026-11-01T00:00:00Z",
        latest="2026-11-03T00:00:00Z",
    ) -> None:
        self.expected = expected
        self.statuses = list(statuses)
        self.table_status = "ACTIVE"
        self.actual_table_arn = expected.table_arn
        self.actual_table_name = expected.table_name
        self.create_error: Exception | None = None
        self.describe_error: Exception | None = None
        self.pitr_error: Exception | None = None
        self.create_omits_arn = False
        self.describe_omits_arn = False
        self.describe_arn_override: str | None = None
        self.describe_source_arn_override: str | None = None
        self.describe_source_name_override: str | None = None
        self.describe_name_override: str | None = None
        self.pitr_response = {
            "ContinuousBackupsDescription": {
                "ContinuousBackupsStatus": "ENABLED" if pitr_status == "ENABLED" else "DISABLED",
                "PointInTimeRecoveryDescription": {
                    "PointInTimeRecoveryStatus": pitr_status,
                    **(
                        {
                            "EarliestRestorableDateTime": earliest,
                            "LatestRestorableDateTime": latest,
                        }
                        if pitr_status == "ENABLED"
                        else {}
                    ),
                },
            }
        }
        self.table_calls = 0
        self.create_calls = 0
        self.describe_calls = 0
        self.pitr_calls = 0
        self.last_backup_name: str | None = None
        self.backup_arn: str | None = None

    def describe_table(self, TableName):  # noqa: N803 - AWS-Form
        self.table_calls += 1
        return {
            "Table": {
                "TableName": self.actual_table_name,
                "TableArn": self.actual_table_arn,
                "TableStatus": self.table_status,
            }
        }

    def create_backup(self, TableName, BackupName):  # noqa: N803
        self.create_calls += 1
        self.last_backup_name = BackupName
        if self.create_error:
            raise self.create_error
        arn = f"arn:aws:dynamodb:{self.expected.region}:{self.expected.aws_account}:table/{self.expected.table_name}/backup/01700000000000-abcdef"
        self.backup_arn = arn
        details = {"BackupName": BackupName, "BackupStatus": "CREATING"}
        if not self.create_omits_arn:
            details["BackupArn"] = arn
        return {"BackupDetails": details}

    def describe_backup(self, BackupArn):  # noqa: N803
        self.describe_calls += 1
        if self.describe_error:
            raise self.describe_error
        status = self.statuses.pop(0) if self.statuses else "CREATING"
        arn = self.describe_arn_override or self.backup_arn
        details = {
            "BackupName": self.describe_name_override or self.last_backup_name,
            "BackupStatus": status,
        }
        if not self.describe_omits_arn:
            details["BackupArn"] = arn
        source = {
            "TableArn": self.describe_source_arn_override or self.expected.table_arn,
            "TableName": self.describe_source_name_override or self.expected.table_name,
        }
        return {"BackupDescription": {"BackupDetails": details, "SourceTableDetails": source}}

    def describe_continuous_backups(self, TableName):  # noqa: N803
        self.pitr_calls += 1
        if self.pitr_error:
            raise self.pitr_error
        return self.pitr_response


def run_backup(client, expected=None, **kwargs):
    expected = expected or make_expected()
    clock = FakeClock()
    defaults = dict(
        now_fn=clock.now,
        sleep_fn=clock.sleep,
        wall_clock=lambda: FIXED_NOW,
        poll_interval=5.0,
        timeout_seconds=60.0,
        max_attempts=5,
        suffix="test",
    )
    defaults.update(kwargs)
    return execute_order_backup(client, expected, **defaults)


class TestIdentityAndName(unittest.TestCase):
    def test_expected_identity_derives_table_from_project(self) -> None:
        identity = make_expected()
        self.assertEqual(identity.table_name, "mays-orders")
        self.assertEqual(
            identity.table_arn,
            "arn:aws:dynamodb:eu-central-1:123456789012:table/mays-orders",
        )
        self.assertEqual(identity.state_serial, 42)

    def test_identity_rejects_missing_project_or_bad_region(self) -> None:
        with self.assertRaises(OrderBackupError) as ctx:
            expected_table_identity(
                project="", environment="Dev", aws_account="123456789012",
                region="eu-central-1",
            )
        self.assertEqual(ctx.exception.code, CODE_IDENTITY_MISMATCH)
        with self.assertRaises(OrderBackupError):
            expected_table_identity(
                project="p", environment="Dev", aws_account="123456789012",
                region="not-a-region",
            )

    def test_verify_identity_success(self) -> None:
        expected = make_expected()
        result = verify_table_identity(FakeDynamo(expected), expected)
        self.assertEqual(result["tableStatus"], "ACTIVE")
        self.assertEqual(result["identity"].table_arn, expected.table_arn)

    def test_verify_identity_rejects_incomplete_expectation(self) -> None:
        expected = dataclasses.replace(make_expected(), aws_account="")
        with self.assertRaises(OrderBackupError) as ctx:
            verify_table_identity(FakeDynamo(make_expected()), expected)
        self.assertEqual(ctx.exception.code, CODE_IDENTITY_MISMATCH)

    def test_table_not_found(self) -> None:
        client = FakeDynamo(make_expected())

        def missing(TableName):  # noqa: N803
            raise FakeClientError("ResourceNotFoundException")

        client.describe_table = missing
        with self.assertRaises(OrderBackupError) as ctx:
            verify_table_identity(client, make_expected())
        self.assertEqual(ctx.exception.code, CODE_TABLE_NOT_FOUND)

    def test_account_mismatch_blocks(self) -> None:
        expected = make_expected()
        client = FakeDynamo(expected)
        client.actual_table_arn = expected.table_arn.replace("123456789012", "999999999999")
        with self.assertRaises(OrderBackupError) as ctx:
            verify_table_identity(client, expected)
        self.assertEqual(ctx.exception.code, CODE_IDENTITY_MISMATCH)
        self.assertIn("awsAccount", ctx.exception.details["mismatchedFields"])

    def test_region_mismatch_blocks(self) -> None:
        expected = make_expected()
        client = FakeDynamo(expected)
        client.actual_table_arn = expected.table_arn.replace("eu-central-1", "us-east-1")
        with self.assertRaises(OrderBackupError) as ctx:
            verify_table_identity(client, expected)
        self.assertEqual(ctx.exception.code, CODE_IDENTITY_MISMATCH)

    def test_table_name_mismatch_blocks(self) -> None:
        expected = make_expected()
        client = FakeDynamo(expected)
        client.actual_table_name = "other-table"
        with self.assertRaises(OrderBackupError) as ctx:
            verify_table_identity(client, expected)
        self.assertEqual(ctx.exception.code, CODE_IDENTITY_MISMATCH)

    def test_arbitrary_expected_table_name_is_rejected(self) -> None:
        expected = dataclasses.replace(make_expected(), table_name="other-table")
        with self.assertRaises(OrderBackupError) as ctx:
            verify_table_identity(FakeDynamo(make_expected()), expected)
        self.assertEqual(ctx.exception.code, CODE_IDENTITY_MISMATCH)

    def test_inconsistent_expected_arn_is_rejected(self) -> None:
        expected = dataclasses.replace(
            make_expected(),
            table_arn="arn:aws:dynamodb:eu-central-1:123456789012:table/other-table",
        )
        with self.assertRaises(OrderBackupError) as ctx:
            verify_table_identity(FakeDynamo(make_expected()), expected)
        self.assertEqual(ctx.exception.code, CODE_IDENTITY_MISMATCH)

    def test_table_not_active_blocks(self) -> None:
        client = FakeDynamo(make_expected())
        client.table_status = "UPDATING"
        with self.assertRaises(OrderBackupError) as ctx:
            verify_table_identity(client, make_expected())
        self.assertEqual(ctx.exception.code, CODE_TABLE_NOT_ACTIVE)

    def test_backup_name_is_sanitized_and_stable(self) -> None:
        name = build_backup_name("My Project", "Dev/Test", now=FIXED_NOW, suffix="a b")
        self.assertEqual(name, "My-Project-Dev-Test-orders-preupgrade-20261103T120000Z-ab")
        self.assertRegex(name, r"^[A-Za-z0-9_.-]{3,255}$")

    def test_backup_name_too_long_is_truncated(self) -> None:
        name = build_backup_name("p" * 300, "Dev", now=FIXED_NOW)
        self.assertLessEqual(len(name), 255)
        self.assertGreaterEqual(len(name), 3)

    def test_backup_name_invalid_when_empty(self) -> None:
        with self.assertRaises(OrderBackupError) as ctx:
            build_backup_name("", "", now=FIXED_NOW)
        self.assertEqual(ctx.exception.code, CODE_NAME_INVALID)


class TestBackupExecution(unittest.TestCase):
    def test_creating_to_available_is_verified(self) -> None:
        client = FakeDynamo(make_expected(), statuses=("CREATING", "AVAILABLE"))
        evidence = run_backup(client)
        self.assertEqual(evidence.backup_status, BACKUP_AVAILABLE)
        self.assertEqual(evidence.pitr_status, PITR_ENABLED)
        self.assertEqual(evidence.overall_status, OVERALL_VERIFIED)
        self.assertEqual(evidence.backup_arn, client.backup_arn)
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(client.describe_calls, 2)
        self.assertIsNotNone(evidence.backup_verified_at)
        self.assertEqual(evidence.error_code, None)

    def test_pitr_disabled_is_partial_not_fake_success(self) -> None:
        client = FakeDynamo(make_expected(), pitr_status="DISABLED")
        evidence = run_backup(client)
        self.assertEqual(evidence.backup_status, BACKUP_AVAILABLE)
        self.assertEqual(evidence.pitr_status, PITR_DISABLED)
        self.assertEqual(evidence.overall_status, OVERALL_PARTIAL)
        self.assertIsNone(evidence.earliest_restorable_at)

    def test_pitr_unknown_is_partial_with_code(self) -> None:
        client = FakeDynamo(make_expected())
        client.pitr_response = {
            "ContinuousBackupsDescription": {
                "ContinuousBackupsStatus": "ENABLED",
                "PointInTimeRecoveryDescription": {
                    "PointInTimeRecoveryStatus": "ENABLED",
                },
            }
        }
        evidence = run_backup(client)
        self.assertEqual(evidence.pitr_status, PITR_UNKNOWN)
        self.assertEqual(evidence.overall_status, OVERALL_PARTIAL)
        self.assertEqual(evidence.error_code, CODE_PITR_UNVERIFIED)
        self.assertIsNone(evidence.latest_restorable_at)

    def test_pitr_invalid_window_is_unknown(self) -> None:
        client = FakeDynamo(make_expected(), earliest="2026-11-03T00:00:00Z", latest="2026-11-01T00:00:00Z")
        evidence = run_backup(client)
        self.assertEqual(evidence.pitr_status, PITR_UNKNOWN)
        self.assertEqual(evidence.error_code, CODE_PITR_UNVERIFIED)

    def test_pitr_accepts_datetime_objects(self) -> None:
        client = FakeDynamo(make_expected())
        client.pitr_response = {
            "ContinuousBackupsDescription": {
                "ContinuousBackupsStatus": "ENABLED",
                "PointInTimeRecoveryDescription": {
                    "PointInTimeRecoveryStatus": "ENABLED",
                    "EarliestRestorableDateTime": datetime(2026, 11, 1, tzinfo=timezone.utc),
                    "LatestRestorableDateTime": datetime(2026, 11, 3, tzinfo=timezone.utc),
                },
            }
        }
        evidence = run_backup(client)
        self.assertEqual(evidence.pitr_status, PITR_ENABLED)
        self.assertEqual(evidence.overall_status, OVERALL_VERIFIED)
        self.assertTrue(evidence.earliest_restorable_at.startswith("2026-11-01"))

    def test_pitr_read_error_keeps_verified_backup_as_partial(self) -> None:
        client = FakeDynamo(make_expected())
        client.pitr_error = FakeClientError("AccessDeniedException")
        evidence = run_backup(client)
        self.assertEqual(evidence.backup_status, BACKUP_AVAILABLE)
        self.assertEqual(evidence.pitr_status, PITR_UNKNOWN)
        self.assertEqual(evidence.overall_status, OVERALL_PARTIAL)
        self.assertEqual(evidence.error_code, CODE_PITR_UNVERIFIED)
        self.assertIsNotNone(evidence.backup_verified_at)

    def test_backup_failed_is_failed(self) -> None:
        client = FakeDynamo(make_expected(), statuses=("CREATING", "FAILED"))
        evidence = run_backup(client)
        self.assertEqual(evidence.backup_status, BACKUP_FAILED)
        self.assertEqual(evidence.overall_status, OVERALL_FAILED)
        self.assertEqual(evidence.error_code, CODE_BACKUP_FAILED)
        self.assertIsNone(evidence.backup_verified_at)

    def test_backup_stays_creating_times_out(self) -> None:
        client = FakeDynamo(make_expected(), statuses=("CREATING", "CREATING", "CREATING"))
        evidence = run_backup(client)
        self.assertEqual(evidence.backup_status, BACKUP_TIMEOUT)
        self.assertEqual(evidence.overall_status, OVERALL_FAILED)
        self.assertEqual(evidence.error_code, CODE_TIMEOUT)

    def test_unknown_backup_status_is_not_success(self) -> None:
        client = FakeDynamo(make_expected(), statuses=("DELETING",))
        evidence = run_backup(client)
        self.assertEqual(evidence.overall_status, OVERALL_FAILED)
        self.assertEqual(evidence.error_code, CODE_BACKUP_FAILED)

    def test_create_backup_error_is_blocked(self) -> None:
        client = FakeDynamo(make_expected())
        client.create_error = RuntimeError("boom")
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client)
        self.assertEqual(ctx.exception.code, CODE_CREATE_FAILED)
        self.assertEqual(client.describe_calls, 0)

    def test_create_backup_access_denied(self) -> None:
        client = FakeDynamo(make_expected())
        client.create_error = FakeClientError("AccessDeniedException")
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client)
        self.assertEqual(ctx.exception.code, CODE_ACCESS_DENIED)

    def test_create_backup_name_conflict(self) -> None:
        client = FakeDynamo(make_expected())
        client.create_error = FakeClientError("BackupInUseException")
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client)
        self.assertEqual(ctx.exception.code, CODE_NAME_CONFLICT)

    def test_missing_backup_arn_after_create(self) -> None:
        client = FakeDynamo(make_expected())
        client.create_omits_arn = True
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client)
        self.assertEqual(ctx.exception.code, CODE_ARN_MISSING)

    def test_describe_backup_error(self) -> None:
        client = FakeDynamo(make_expected())
        client.describe_error = RuntimeError("network")
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client)
        self.assertEqual(ctx.exception.code, CODE_DESCRIBE_FAILED)

    def test_describe_backup_wrong_arn_is_identity_mismatch(self) -> None:
        client = FakeDynamo(make_expected())
        client.describe_arn_override = "arn:aws:dynamodb:eu-central-1:123456789012:table/x/backup/other"
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client)
        self.assertEqual(ctx.exception.code, CODE_BACKUP_IDENTITY_MISMATCH)

    def test_describe_backup_wrong_source_table(self) -> None:
        client = FakeDynamo(make_expected())
        client.describe_source_arn_override = "arn:aws:dynamodb:eu-central-1:123456789012:table/other"
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client)
        self.assertEqual(ctx.exception.code, CODE_BACKUP_IDENTITY_MISMATCH)

    def test_describe_backup_missing_arn(self) -> None:
        client = FakeDynamo(make_expected())
        client.describe_omits_arn = True
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client)
        self.assertEqual(ctx.exception.code, CODE_ARN_MISSING)

    def test_missing_state_baseline_blocks_before_any_call(self) -> None:
        expected = dataclasses.replace(
            make_expected(), state_baseline_status=None, state_lineage=None, state_serial=None
        )
        client = FakeDynamo(expected)
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(client, expected=expected)
        self.assertEqual(ctx.exception.code, CODE_STATE_BASELINE_REQUIRED)
        self.assertEqual(client.table_calls, 0)

    def test_unverified_state_baseline_blocks(self) -> None:
        expected = expected_table_identity(
            project="mays-orders", environment="Development",
            aws_account="123456789012", region="eu-central-1",
            state_baseline={"status": "MISSING_SERIAL", "lineage": "x", "serial": None},
        )
        with self.assertRaises(OrderBackupError) as ctx:
            run_backup(FakeDynamo(expected), expected=expected)
        self.assertEqual(ctx.exception.code, CODE_STATE_BASELINE_REQUIRED)


class TestPitr(unittest.TestCase):
    def test_pitr_disabled(self) -> None:
        expected = make_expected()
        result = check_pitr(FakeDynamo(expected, pitr_status="DISABLED"), expected)
        self.assertEqual(result.status, PITR_DISABLED)
        self.assertFalse(result.verified)

    def test_pitr_missing_timestamps_is_unverified(self) -> None:
        client = FakeDynamo(make_expected())
        client.pitr_response = {
            "ContinuousBackupsDescription": {
                "ContinuousBackupsStatus": "ENABLED",
                "PointInTimeRecoveryDescription": {"PointInTimeRecoveryStatus": "ENABLED"},
            }
        }
        result = check_pitr(client, make_expected())
        self.assertEqual(result.status, PITR_UNKNOWN)
        self.assertEqual(result.error_code, CODE_PITR_UNVERIFIED)
        self.assertIsNone(result.earliest_restorable_at)

    def test_pitr_access_denied(self) -> None:
        client = FakeDynamo(make_expected())
        client.pitr_error = FakeClientError("AccessDeniedException")
        with self.assertRaises(OrderBackupError) as ctx:
            check_pitr(client, make_expected())
        self.assertEqual(ctx.exception.code, CODE_ACCESS_DENIED)


class TestEvidence(unittest.TestCase):
    def test_evidence_json_and_md_written_without_pii(self) -> None:
        evidence = run_backup(FakeDynamo(make_expected()))
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = write_evidence(tmp, evidence)
            data = json.loads(Path(json_path).read_text(encoding="utf-8"))
            self.assertEqual(data["schemaVersion"], 1)
            self.assertEqual(data["overallStatus"], OVERALL_VERIFIED)
            self.assertEqual(data["backupStatus"], BACKUP_AVAILABLE)
            self.assertEqual(data["pitrStatus"], PITR_ENABLED)
            self.assertEqual(data["stateSerial"], 42)
            self.assertEqual(data["stateLineage"], "lineage-abc")
            for forbidden in ("customer", "items", "email", "subjectId", "token"):
                self.assertNotIn(forbidden, json.dumps(data).lower())
            self.assertIn("Order-Backup-Evidenz", Path(md_path).read_text(encoding="utf-8"))

    def test_evidence_binding_accepts_matching_context(self) -> None:
        expected = make_expected()
        evidence = run_backup(FakeDynamo(expected), expected=expected)
        validate_evidence_binding(evidence, expected)

    def test_tampered_evidence_context_is_rejected(self) -> None:
        expected = make_expected()
        evidence = run_backup(FakeDynamo(expected), expected=expected)
        tampered = dataclasses.replace(evidence, project="other-project")
        with self.assertRaises(OrderBackupError) as ctx:
            validate_evidence_binding(tampered, expected)
        self.assertEqual(ctx.exception.code, CODE_EVIDENCE_MISMATCH)
        self.assertIn("project", ctx.exception.details["mismatchedFields"])

    def test_tampered_state_fingerprint_is_rejected(self) -> None:
        expected = make_expected()
        evidence = run_backup(FakeDynamo(expected), expected=expected)
        tampered = dataclasses.replace(evidence, state_fingerprint="0" * 64)
        with self.assertRaises(OrderBackupError) as ctx:
            validate_evidence_binding(tampered, expected)
        self.assertEqual(ctx.exception.code, CODE_EVIDENCE_MISMATCH)
        self.assertIn("stateFingerprint", ctx.exception.details["mismatchedFields"])

    def test_default_backup_names_are_unique(self) -> None:
        first = run_backup(FakeDynamo(make_expected()), suffix=None)
        second = run_backup(FakeDynamo(make_expected()), suffix=None)
        self.assertNotEqual(first.backup_name, second.backup_name)

    def test_missing_backup_arn_in_evidence_is_rejected(self) -> None:
        expected = make_expected()
        evidence = run_backup(FakeDynamo(expected), expected=expected)
        with self.assertRaises(OrderBackupError):
            validate_evidence_binding(dataclasses.replace(evidence, backup_arn=None), expected)

    def test_verified_marker_without_available_backup_is_rejected(self) -> None:
        expected = make_expected()
        evidence = run_backup(FakeDynamo(expected, statuses=("CREATING", "FAILED")), expected=expected)
        tampered = dataclasses.replace(evidence, overall_status=OVERALL_VERIFIED)
        with self.assertRaises(OrderBackupError):
            validate_evidence_binding(tampered, expected)


class TestDryRunAndSafety(unittest.TestCase):
    def test_dry_run_plan_claims_nothing(self) -> None:
        plan = plan_order_backup(
            project="mays-orders",
            environment="Development",
            aws_account=None,
            region="eu-central-1",
            wall_clock=lambda: FIXED_NOW,
            suffix="test",
        )
        data = plan.to_dict()
        self.assertEqual(data["mode"], "DRY_RUN")
        self.assertEqual(data["overallStatus"], OVERALL_UNVERIFIED)
        self.assertFalse(data["identityVerified"])
        self.assertEqual(data["pitrStatus"], PITR_UNKNOWN)
        self.assertIsNone(data["tableArn"])
        self.assertIn("dynamodb:CreateBackup", data["requiredPermissions"])
        self.assertTrue(data["backupName"].startswith("mays-orders-Development-orders-preupgrade-"))

    def test_dry_run_writes_plan_files(self) -> None:
        plan = plan_order_backup(
            project="mays-orders", environment="Development", aws_account=None,
            region="eu-central-1", wall_clock=lambda: FIXED_NOW,
        )
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = write_plan(tmp, plan)
            self.assertTrue(Path(json_path).exists())
            self.assertIn("dry-run", Path(md_path).read_text(encoding="utf-8").lower())
            text = Path(json_path).read_text(encoding="utf-8")
            self.assertNotIn('"backupStatus"', text)
            self.assertNotIn('"backupArn"', text)

    def test_core_module_does_not_import_boto3(self) -> None:
        source = Path(ob.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import boto3", source)
        self.assertNotIn("botocore", source)

    def test_execute_requires_injected_client(self) -> None:
        with self.assertRaises(TypeError):
            execute_order_backup(expected=make_expected())  # type: ignore[call-arg]

    def test_no_network_in_dry_run_plan(self) -> None:
        # plan_order_backup hat keinen Client-Parameter; ein Aufruf kann keinen
        # AWS-Client verwenden. Zusaetzlich: keine Methode namens "client".
        import inspect

        params = inspect.signature(plan_order_backup).parameters
        self.assertNotIn("client", params)


class TestCliSafety(unittest.TestCase):
    def _run_cli(self, args):
        import contextlib
        import io

        from installer.cli.main import InstallerCLI

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    return InstallerCLI().run(args)
            finally:
                os.chdir(cwd)

    def test_cli_dry_run_is_offline_and_unverified(self) -> None:
        code = self._run_cli(
            [
                "--project-name", "mays-orders",
                "--environment", "Development",
                "backup", "--orders", "--dry-run",
            ]
        )
        self.assertEqual(code, 0)

    def test_cli_execute_without_double_gate_is_blocked(self) -> None:
        old_exec = os.environ.pop("MAYS_ORDER_BACKUP_ALLOW_EXECUTE", None)
        old_allow = os.environ.pop("ALLOW_AWS_OPERATIONS", None)
        try:
            code = self._run_cli(
                [
                    "--project-name", "mays-orders",
                    "--environment", "Development",
                    "backup", "--orders", "--execute",
                ]
            )
        finally:
            if old_exec is not None:
                os.environ["MAYS_ORDER_BACKUP_ALLOW_EXECUTE"] = old_exec
            if old_allow is not None:
                os.environ["ALLOW_AWS_OPERATIONS"] = old_allow
        self.assertEqual(code, 2)

    def test_cli_dry_run_never_imports_boto3(self) -> None:
        import sys
        from unittest import mock

        class Exploding:
            def __getattr__(self, name):
                raise AssertionError(f"boto3 must not be used in dry-run: {name}")

        with mock.patch.dict(sys.modules, {"boto3": Exploding()}):
            code = self._run_cli(
                [
                    "--project-name", "mays-orders",
                    "--environment", "Development",
                    "backup", "--orders", "--dry-run",
                ]
            )
        self.assertEqual(code, 0)

    def test_cli_dry_run_and_execute_are_mutually_exclusive(self) -> None:
        code = self._run_cli(
            [
                "--project-name", "mays-orders",
                "--environment", "Development",
                "backup", "--orders", "--dry-run", "--execute",
            ]
        )
        self.assertEqual(code, 2)

    def test_cli_requires_orders_flag(self) -> None:
        code = self._run_cli(
            [
                "--project-name", "mays-orders",
                "--environment", "Development",
                "backup", "--dry-run",
            ]
        )
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
