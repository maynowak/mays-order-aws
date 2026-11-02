"""MO-RC4-P02I-E2B: Plan-Manifest (Identitaetsbindung) und Apply-Schutz.

Reine lokale Tests: kein Terraform, kein AWS.
"""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from installer.cli.main import InstallerCLI
from installer.core.deployment_identity import DeploymentId, PlanOperation
from installer.core.plan_contract import load_backend_contract
from installer.core.plan_manifest import (
    PlanManifest,
    manifest_path_for,
    sha256_file,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = REPO_ROOT / "terraform"
DEPLOYMENT_ID = DeploymentId(
    account_id="240571105849", project="mays-orders-rc4", environment="development"
)


class ManifestTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.plan = self.tmp / "mays-orders-rc4-development-0.1.0-H2-240571105849-deploy-0001.tfplan"
        self.plan.write_bytes(b"fake-plan-bytes")
        self.backend = load_backend_contract(TERRAFORM_DIR)
        self.manifest = PlanManifest.create(
            self.plan,
            deployment_id=DEPLOYMENT_ID,
            operation=PlanOperation.DEPLOY,
            region="eu-central-1",
            workspace="mays-orders-rc4",
            backend=self.backend,
            variables={
                "project_name": "mays-orders-rc4",
                "recovery_enabled": "false",
                "processing_recovery_enabled": "false",
                "PRIVACY_INTERNAL_SECRET": "must-not-be-stored",
            },
            git_commit="5d162e1",
        )
        self.manifest.write(self.plan)

    def tearDown(self):
        self._tmp.cleanup()

    def _verify(self, **overrides):
        kwargs = dict(
            deployment_id=DEPLOYMENT_ID,
            region="eu-central-1",
            workspace="mays-orders-rc4",
            backend=self.backend,
            operation=PlanOperation.DEPLOY,
        )
        kwargs.update(overrides)
        return self.manifest.verify(self.plan, **kwargs)


class TestManifestRoundtrip(ManifestTestCase):
    def test_manifest_is_written_next_to_plan(self):
        self.assertTrue(manifest_path_for(self.plan).exists())

    def test_load_roundtrip(self):
        loaded = PlanManifest.load(self.plan)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.deployment_id, DEPLOYMENT_ID)
        self.assertEqual(loaded.workspace, "mays-orders-rc4")
        self.assertEqual(loaded.state_key, "env:/mays-orders-rc4/terraform.tfstate")
        self.assertEqual(loaded.plan_sha256, sha256_file(self.plan))

    def test_manifest_binds_identity_and_backend(self):
        data = json.loads(manifest_path_for(self.plan).read_text())
        self.assertEqual(data["deployment_id"]["project"], "mays-orders-rc4")
        self.assertEqual(data["backend"]["bucket"], "mays-orders-tfstate-central-240571105849")
        self.assertEqual(data["region"], "eu-central-1")
        self.assertEqual(data["workspace"], "mays-orders-rc4")

    def test_no_secrets_in_manifest(self):
        text = manifest_path_for(self.plan).read_text()
        self.assertNotIn("PRIVACY_INTERNAL_SECRET", text)
        self.assertNotIn("must-not-be-stored", text)
        self.assertNotIn("secret", text.lower())

    def test_missing_manifest_returns_none(self):
        manifest_path_for(self.plan).unlink()
        self.assertIsNone(PlanManifest.load(self.plan))

    def test_corrupt_manifest_raises(self):
        manifest_path_for(self.plan).write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            PlanManifest.load(self.plan)


class TestManifestVerification(ManifestTestCase):
    def test_matching_context_passes(self):
        ok, message = self._verify()
        self.assertTrue(ok, message)

    def test_tampered_plan_is_rejected(self):
        self.plan.write_bytes(b"tampered")
        ok, message = self._verify()
        self.assertFalse(ok)
        self.assertIn("Checksumme", message)

    def test_foreign_project_is_rejected(self):
        other = DeploymentId(
            account_id="240571105849", project="mays-orders", environment="development"
        )
        ok, message = self._verify(deployment_id=other)
        self.assertFalse(ok)
        self.assertIn("Identitaet", message)

    def test_foreign_account_is_rejected(self):
        other = DeploymentId(
            account_id="262370457690", project="mays-orders-rc4", environment="development"
        )
        ok, _ = self._verify(deployment_id=other)
        self.assertFalse(ok)

    def test_region_mismatch_is_rejected(self):
        ok, message = self._verify(region="us-east-1")
        self.assertFalse(ok)
        self.assertIn("Region", message)

    def test_workspace_mismatch_is_rejected(self):
        ok, message = self._verify(workspace="mays-orders")
        self.assertFalse(ok)
        self.assertIn("Workspace", message)

    def test_operation_mismatch_is_rejected(self):
        ok, message = self._verify(operation=PlanOperation.DESTROY)
        self.assertFalse(ok)
        self.assertIn("Operation", message)

    def test_backend_mismatch_is_rejected(self):
        from dataclasses import replace

        other_backend = replace(self.backend, bucket="other-bucket")
        ok, message = self._verify(backend=other_backend)
        self.assertFalse(ok)
        self.assertIn("Backend", message)

    def test_renamed_plan_is_rejected(self):
        renamed = self.tmp / "other-name.tfplan"
        renamed.write_bytes(self.plan.read_bytes())
        ok, message = self.manifest.verify(
            renamed,
            deployment_id=DEPLOYMENT_ID,
            region="eu-central-1",
            workspace="mays-orders-rc4",
            backend=self.backend,
            operation=PlanOperation.DEPLOY,
        )
        self.assertFalse(ok)
        self.assertIn("Dateiname", message)


class TestApplyPathBinding(ManifestTestCase):
    def _context(self):
        ctx = MagicMock()
        ctx.terraform_dir = str(TERRAFORM_DIR)
        ctx.aws_region = "eu-central-1"
        ctx.terraform_workspace = "mays-orders-rc4"
        ctx.get_deployment_context.return_value = SimpleNamespace(deployment_id=DEPLOYMENT_ID)
        return ctx

    def test_manifest_verified_for_deploy(self):
        cli = InstallerCLI()
        self.assertTrue(
            cli._verify_plan_manifest(self._context(), self.plan, PlanOperation.DEPLOY)
        )

    def test_foreign_manifest_rejected_for_deploy(self):
        other = DeploymentId(
            account_id="240571105849", project="mays-orders", environment="development"
        )
        self.manifest = PlanManifest.create(
            self.plan,
            deployment_id=other,
            operation=PlanOperation.DEPLOY,
            region="eu-central-1",
            workspace="mays-orders",
            backend=self.backend,
        )
        self.manifest.write(self.plan)
        cli = InstallerCLI()
        self.assertFalse(
            cli._verify_plan_manifest(self._context(), self.plan, PlanOperation.DEPLOY)
        )

    def test_manifest_rejected_for_destroy_operation(self):
        cli = InstallerCLI()
        self.assertFalse(
            cli._verify_plan_manifest(self._context(), self.plan, PlanOperation.DESTROY)
        )

    def test_deploy_verifies_deploy_operation_only(self):
        source = inspect.getsource(InstallerCLI._cmd_deploy)
        self.assertIn("_verify_plan_manifest(context, plan_file, PlanOperation.DEPLOY)", source)
        self.assertNotIn("PlanOperation.DESTROY", source)

    def test_destroy_verifies_destroy_operation_only(self):
        source = inspect.getsource(InstallerCLI._cmd_destroy)
        self.assertIn("_verify_plan_manifest(context, plan_file, PlanOperation.DESTROY)", source)
        self.assertNotIn("PlanOperation.DEPLOY", source)

    def test_legacy_plan_without_manifest_is_allowed(self):
        manifest_path_for(self.plan).unlink()
        cli = InstallerCLI()
        self.assertTrue(
            cli._verify_plan_manifest(self._context(), self.plan, PlanOperation.DEPLOY)
        )


if __name__ == "__main__":
    unittest.main()
