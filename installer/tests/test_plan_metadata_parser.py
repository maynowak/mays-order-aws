"""MO-RC4-PLAN-METADATA-PARSER-FIX-05: hyphenierte Deployment-IDs."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from installer.core.deployment_identity import (
    DeploymentId,
    DevelopmentPhase,
    PlanDiscovery,
    PlanMetadata,
    PlanOperation,
    SemanticVersion,
)


def _metadata(project="mays-orders-rc4-test", environment="rc4-test", account="240571105849"):
    return PlanMetadata(
        deployment_id=DeploymentId(account_id=account, project=project, environment=environment),
        version=SemanticVersion.parse("0.2.0"),
        development_phase=DevelopmentPhase.parse("H2"),
        operation=PlanOperation.DEPLOY,
        sequence_number=1,
    )


class TestHyphenatedPlanMetadata(unittest.TestCase):
    def test_rc4_plan_filename_resolves_with_expected_identity(self):
        meta = _metadata()
        filename = meta.to_filename()
        parsed = PlanMetadata.parse_filename(
            filename, expected_deployment_id=meta.deployment_id
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.deployment_id, meta.deployment_id)
        self.assertEqual(parsed.deployment_id.project, "mays-orders-rc4-test")
        self.assertEqual(parsed.deployment_id.environment, "rc4-test")
        self.assertEqual(parsed.version, meta.version)

    def test_validate_plan_context_accepts_known_rc4_filename(self):
        meta = _metadata()
        discovery = PlanDiscovery(base_dir=Path("/tmp/nonexistent"))
        ok, message = discovery.validate_plan_context(
            Path(meta.to_filename()), meta.deployment_id
        )
        self.assertTrue(ok, message)

    def test_other_hyphenated_project_environment_combinations(self):
        for project, environment in (
            ("mays-orders-rc4-test", "rc4-test"),
            ("my-project", "pre-prod"),
            ("project-with-many-hyphens", "env-with-hyphens"),
        ):
            meta = _metadata(project=project, environment=environment)
            parsed = PlanMetadata.parse_filename(
                meta.to_filename(), expected_deployment_id=meta.deployment_id
            )
            self.assertIsNotNone(parsed, f"{project}/{environment}")
            self.assertEqual(parsed.deployment_id.project, project)
            self.assertEqual(parsed.deployment_id.environment, environment)

    def test_legacy_filename_without_hyphenated_environment(self):
        meta = _metadata(project="mays-orders-rc4", environment="development")
        parsed = PlanMetadata.parse_filename(meta.to_filename())
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.deployment_id.project, "mays-orders-rc4")
        self.assertEqual(parsed.deployment_id.environment, "development")

    def test_wrong_account_is_blocked(self):
        meta = _metadata()
        discovery = PlanDiscovery(base_dir=Path("/tmp/nonexistent"))
        wrong = DeploymentId("999999999999", meta.deployment_id.project, meta.deployment_id.environment)
        ok, _ = discovery.validate_plan_context(Path(meta.to_filename()), wrong)
        self.assertFalse(ok)

    def test_wrong_project_is_blocked(self):
        meta = _metadata()
        discovery = PlanDiscovery(base_dir=Path("/tmp/nonexistent"))
        wrong = DeploymentId(meta.deployment_id.account_id, "other-project", meta.deployment_id.environment)
        ok, _ = discovery.validate_plan_context(Path(meta.to_filename()), wrong)
        self.assertFalse(ok)

    def test_wrong_environment_is_blocked(self):
        meta = _metadata()
        discovery = PlanDiscovery(base_dir=Path("/tmp/nonexistent"))
        wrong = DeploymentId(meta.deployment_id.account_id, meta.deployment_id.project, "other-env")
        ok, _ = discovery.validate_plan_context(Path(meta.to_filename()), wrong)
        self.assertFalse(ok)

    def test_manipulated_suffix_is_blocked(self):
        meta = _metadata()
        filename = meta.to_filename()
        manipulated = filename.replace("-H2-", "-INVALID-")
        discovery = PlanDiscovery(base_dir=Path("/tmp/nonexistent"))
        ok, _ = discovery.validate_plan_context(Path(manipulated), meta.deployment_id)
        self.assertFalse(ok)

    def test_extra_filename_segment_is_blocked(self):
        meta = _metadata()
        filename = meta.to_filename().replace("-0001.tfplan", "-extra-0001.tfplan")
        parsed = PlanMetadata.parse_filename(
            filename, expected_deployment_id=meta.deployment_id
        )
        self.assertIsNone(parsed)

    def test_manifest_discovery_finds_hyphenated_plan(self):
        meta = _metadata()
        with tempfile.TemporaryDirectory() as tmp:
            plans = Path(tmp) / "run" / "plans"
            plans.mkdir(parents=True)
            (plans / meta.to_filename()).write_bytes(b"plan")
            discovery = PlanDiscovery(base_dir=Path(tmp))
            found = discovery.find_latest_plan(meta.deployment_id, PlanOperation.DEPLOY)
        self.assertIsNotNone(found)
        self.assertEqual(found.metadata.deployment_id, meta.deployment_id)

    def test_ambiguous_filename_without_expected_identity_is_not_authority(self):
        # The legacy parser cannot know where the hyphenated environment starts.
        # Security-relevant callers always pass the validated expected identity.
        meta = _metadata()
        legacy = PlanMetadata.parse_filename(meta.to_filename())
        self.assertIsNotNone(legacy)
        self.assertNotEqual(legacy.deployment_id, meta.deployment_id)
        strict = PlanMetadata.parse_filename(
            meta.to_filename(), expected_deployment_id=meta.deployment_id
        )
        self.assertEqual(strict.deployment_id, meta.deployment_id)


if __name__ == "__main__":
    unittest.main()
