"""MO-RC4-P0C-DRIFT-FIX-01: Normalisierungs- und Fingerprint-Tests."""

from __future__ import annotations

import json
import unittest

from installer.core.change_classification import SAFE, classify_changes
from installer.core.drift import (
    DRIFT_DETECTED,
    assess_plan,
)
from installer.core.state_baseline import capture_state_baseline
from installer.core.state_fingerprint import (
    StateFingerprintError,
    canonical_state_fingerprint,
)

POLICY = json.dumps(
    {"Version": "2012-10-17", "Statement": [{"Sid": "AWSCloudTrailAclCheck"}]},
    sort_keys=True,
)
OTHER_POLICY = json.dumps(
    {"Version": "2012-10-17", "Statement": [{"Sid": "Changed"}]},
    sort_keys=True,
)


def _plan(*, bucket_actions=("no-op",), policy_actions=("no-op",), policy=OTHER_POLICY,
          resource_policy=None, bucket_before_policy="", bucket_extra=False,
          extra_drift=None):
    resource_policy = policy if resource_policy is None else resource_policy
    changes = [
        {
            "address": "module.cloudtrail.aws_s3_bucket.trail",
            "type": "aws_s3_bucket",
            "change": {
                "actions": list(bucket_actions),
                "before": {"policy": bucket_before_policy, **({"tags": {"a": "b"}} if bucket_extra else {})},
                "after": {"policy": policy, **({"tags": {"a": "c"}} if bucket_extra else {})},
            },
        },
        {
            "address": "module.cloudtrail.aws_s3_bucket_policy.trail_policy",
            "type": "aws_s3_bucket_policy",
            "change": {
                "actions": list(policy_actions),
                "before": {"policy": resource_policy},
                "after": {"policy": resource_policy},
            },
        },
    ]
    drift = [{
        "address": "module.cloudtrail.aws_s3_bucket.trail",
        "type": "aws_s3_bucket",
        "change": {
            "actions": ["update"],
            "before": {"policy": bucket_before_policy, **({"tags": {"a": "b"}} if bucket_extra else {})},
            "after": {"policy": policy, **({"tags": {"a": "c"}} if bucket_extra else {})},
        },
    }]
    if extra_drift:
        drift.extend(extra_drift)
    return {
        "complete": True,
        "errored": False,
        "resource_changes": changes,
        "resource_drift": drift,
    }


def _cognito_plan(*, pool_actions=("no-op",), before=None, after=None,
                  extra_drift=None):
    changes = [{
        "address": "module.cognito.aws_cognito_user_pool.users",
        "type": "aws_cognito_user_pool",
        "change": {
            "actions": list(pool_actions),
            "before": {"auto_verified_attributes": before, "username_attributes": before},
            "after": {"auto_verified_attributes": after, "username_attributes": after},
        },
    }]
    drift = [{
        "address": "module.cognito.aws_cognito_user_pool.users",
        "type": "aws_cognito_user_pool",
        "change": {
            "actions": ["update"],
            "before": {"auto_verified_attributes": before, "username_attributes": before},
            "after": {"auto_verified_attributes": after, "username_attributes": after},
        },
    }]
    if extra_drift:
        drift.extend(extra_drift)
    return {
        "complete": True,
        "errored": False,
        "resource_changes": changes,
        "resource_drift": drift,
    }


def _finding(plan, address):
    assessment = assess_plan(plan, has_prior_state=True)
    return next(f for f in assessment.drift_findings if f.address == address)


class TestStateFingerprint(unittest.TestCase):
    def _state(self):
        return {
            "version": 4,
            "serial": 7,
            "lineage": "lineage-1",
            "outputs": {"mo_version": {"value": "0.1.0"}},
            "resources": [
                {
                    "module": "module.a",
                    "mode": "managed",
                    "type": "aws_s3_bucket",
                    "name": "one",
                    "instances": [{"attributes": {"name": "one"}}],
                },
                {
                    "module": "module.a",
                    "mode": "managed",
                    "type": "aws_s3_bucket",
                    "name": "two",
                    "instances": [{"attributes": {"name": "two"}}],
                },
            ],
            "check_results": [
                {"object_kind": "var", "config_addr": "var.b", "objects": []},
                {"object_kind": "var", "config_addr": "var.a", "objects": []},
            ],
        }

    def test_check_results_and_resource_order_do_not_change_fingerprint(self):
        state = self._state()
        reordered = json.loads(json.dumps(state))
        reordered["check_results"].reverse()
        reordered["resources"].reverse()
        self.assertEqual(
            canonical_state_fingerprint(state),
            canonical_state_fingerprint(reordered),
        )

    def test_json_key_order_does_not_change_fingerprint(self):
        a = '{"serial":1,"lineage":"l","resources":[],"outputs":{}}'
        b = '{"outputs":{},"resources":[],"lineage":"l","serial":1}'
        self.assertEqual(canonical_state_fingerprint(a), canonical_state_fingerprint(b))

    def test_semantic_changes_change_fingerprint(self):
        state = self._state()
        changed = json.loads(json.dumps(state))
        changed["resources"][0]["instances"][0]["attributes"]["name"] = "changed"
        self.assertNotEqual(
            canonical_state_fingerprint(state), canonical_state_fingerprint(changed)
        )

    def test_output_change_changes_fingerprint(self):
        state = self._state()
        changed = json.loads(json.dumps(state))
        changed["outputs"]["mo_version"]["value"] = "0.2.0"
        self.assertNotEqual(
            canonical_state_fingerprint(state), canonical_state_fingerprint(changed)
        )

    def test_lineage_and_serial_change_fingerprint(self):
        state = self._state()
        for key, value in (("lineage", "other"), ("serial", 8)):
            changed = json.loads(json.dumps(state))
            changed[key] = value
            self.assertNotEqual(
                canonical_state_fingerprint(state), canonical_state_fingerprint(changed)
            )

    def test_invalid_state_fails(self):
        with self.assertRaises(StateFingerprintError):
            canonical_state_fingerprint("{broken")

    def test_capture_uses_canonical_fingerprint(self):
        state = self._state()
        raw = json.dumps(state)
        runner = type("Runner", (), {"state_pull": lambda self: type(
            "Result", (), {"success": True, "stdout": raw, "stderr": ""}
        )()})()
        baseline = capture_state_baseline(runner)
        self.assertEqual(baseline.fingerprint, canonical_state_fingerprint(raw))
        self.assertEqual(baseline.fingerprint_version, "canonical-sha256-v1")


class TestS3Normalization(unittest.TestCase):
    def test_policy_drift_with_separate_unchanged_policy_is_benign(self):
        finding = _finding(_plan(), "module.cloudtrail.aws_s3_bucket.trail")
        self.assertTrue(finding.benign)
        self.assertIn("separate", finding.benign_reason)

    def test_policy_resource_update_is_not_benign(self):
        finding = _finding(
            _plan(policy_actions=("update",)),
            "module.cloudtrail.aws_s3_bucket.trail",
        )
        self.assertFalse(finding.benign)

    def test_bucket_update_is_not_benign(self):
        finding = _finding(
            _plan(bucket_actions=("update",)),
            "module.cloudtrail.aws_s3_bucket.trail",
        )
        self.assertFalse(finding.benign)

    def test_different_policy_is_not_benign(self):
        finding = _finding(
            _plan(policy=OTHER_POLICY, resource_policy=POLICY),
            "module.cloudtrail.aws_s3_bucket.trail",
        )
        self.assertFalse(finding.benign)

    def test_additional_bucket_drift_is_not_benign(self):
        finding = _finding(
            _plan(bucket_extra=True), "module.cloudtrail.aws_s3_bucket.trail"
        )
        self.assertFalse(finding.benign)


class TestCognitoNormalization(unittest.TestCase):
    def test_null_to_empty_lists_is_benign(self):
        finding = _finding(
            _cognito_plan(before=None, after=[]),
            "module.cognito.aws_cognito_user_pool.users",
        )
        self.assertTrue(finding.benign)
        self.assertIn("Normalisierung", finding.benign_reason)

    def test_empty_to_null_is_benign(self):
        finding = _finding(
            _cognito_plan(before=[], after=None),
            "module.cognito.aws_cognito_user_pool.users",
        )
        self.assertTrue(finding.benign)

    def test_nonempty_values_are_not_benign(self):
        finding = _finding(
            _cognito_plan(before=None, after=["email"]),
            "module.cognito.aws_cognito_user_pool.users",
        )
        self.assertFalse(finding.benign)

    def test_planned_pool_change_is_not_benign(self):
        finding = _finding(
            _cognito_plan(pool_actions=("update",), before=None, after=[]),
            "module.cognito.aws_cognito_user_pool.users",
        )
        self.assertFalse(finding.benign)

    def test_benign_drift_is_classified_safe_not_critical(self):
        plan = _plan()
        assessment = assess_plan(plan, has_prior_state=True)
        self.assertEqual(assessment.drift_status, DRIFT_DETECTED)
        result = classify_changes(
            drift_status=assessment.drift_status,
            drift_findings=assessment.drift_findings,
            planned_changes=[],
            protected_types=("aws_s3_bucket", "aws_cognito_user_pool"),
        )
        s3 = next(c for c in result.changes if c.address.endswith("aws_s3_bucket.trail"))
        self.assertEqual(s3.category, SAFE)
        self.assertNotEqual(result.overall, "CRITICAL")


class TestExistingRevalidationEvidence(unittest.TestCase):
    def test_repository_revalidation_evidence_passes_gate(self):
        from pathlib import Path
        from installer.core.backup_gate import BACKUP_VERIFIED, assess_backup_evidence

        path = (
            Path(__file__).resolve().parents[2]
            / "docs/reports/MO-RC4-P3A-EVIDENCE-REBIND-01/order-backup-evidence.json"
        )
        result = assess_backup_evidence(
            path,
            required=True,
            expected_project="mays-orders-rc4-test",
            expected_environment="rc4-test",
            expected_account="240571105849",
            expected_region="eu-central-1",
            state_lineage="45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad",
            state_serial=4,
            state_fingerprint="670bc917fe4671df2ecb7b317068160c8fc452e02e87aa7a63b3b63e864f2a4a",
            expected_backup_arn=(
                "arn:aws:dynamodb:eu-central-1:240571105849:table/"
                "mays-orders-rc4-test/backup/01793737895744-2f886092"
            ),
        )
        self.assertEqual(result.status, BACKUP_VERIFIED)


class TestBackupFingerprintGate(unittest.TestCase):
    def test_manifest_summary_contains_fingerprint_version(self):
        from installer.tests.test_rc4_release_gates import assess, valid_evidence
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "order-backup-evidence.json"
            path.write_text(json.dumps(valid_evidence()), encoding="utf-8")
            summary = assess(path).to_manifest()
        self.assertIn("stateFingerprint", summary)
        self.assertEqual(summary["stateFingerprintVersion"], "canonical-sha256-v1")

    def test_fingerprint_mismatch_blocks(self):
        from installer.tests.test_rc4_release_gates import FINGERPRINT, assess, valid_evidence
        import tempfile
        from pathlib import Path
        from installer.core.backup_gate import BACKUP_STALE

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "order-backup-evidence.json"
            path.write_text(json.dumps(valid_evidence()), encoding="utf-8")
            result = assess(path, state_fingerprint="b" * 64)
        self.assertEqual(result.status, BACKUP_STALE)

    def test_missing_fingerprint_blocks(self):
        from installer.tests.test_rc4_release_gates import assess, valid_evidence
        import tempfile
        from pathlib import Path
        from installer.core.backup_gate import BACKUP_INVALID, CODE_FINGERPRINT_MISSING

        data = valid_evidence()
        data.pop("stateFingerprint")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "order-backup-evidence.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = assess(path)
        self.assertEqual(result.status, BACKUP_INVALID)
        self.assertEqual(result.code, CODE_FINGERPRINT_MISSING)

    def test_missing_version_blocks(self):
        from installer.tests.test_rc4_release_gates import assess, valid_evidence
        import tempfile
        from pathlib import Path
        from installer.core.backup_gate import BACKUP_INVALID, CODE_FINGERPRINT_VERSION_UNKNOWN

        data = valid_evidence()
        data.pop("stateFingerprintVersion")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "order-backup-evidence.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = assess(path)
        self.assertEqual(result.status, BACKUP_INVALID)
        self.assertEqual(result.code, CODE_FINGERPRINT_VERSION_UNKNOWN)

    def test_unknown_version_blocks(self):
        from installer.tests.test_rc4_release_gates import assess, valid_evidence
        import tempfile
        from pathlib import Path
        from installer.core.backup_gate import BACKUP_INVALID

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "order-backup-evidence.json"
            path.write_text(json.dumps(valid_evidence(stateFingerprintVersion="legacy-raw-v0")), encoding="utf-8")
            result = assess(path)
        self.assertEqual(result.status, BACKUP_INVALID)


if __name__ == "__main__":
    unittest.main()
