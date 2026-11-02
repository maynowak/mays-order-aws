"""MO-RC4-P02I-E2B: Remote-Plan-Vertrag, Backend-Init und State-Guard.

Reine lokale Tests: kein Terraform, kein AWS.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from installer.core.deployment_identity import (
    DeploymentId,
    DevelopmentPhase,
    PlanMetadata,
    PlanOperation,
    SemanticVersion,
)
from installer.core.plan_contract import (
    BackendContractError,
    PlanOutputError,
    load_backend_contract,
    parse_backend_contract,
    resolve_plan_output,
    validate_remote_plan,
)
from installer.core.state_guard import (
    StateMigrationBlocked,
    assert_no_state_migration,
    inspect_local_state,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = REPO_ROOT / "terraform"


def _metadata(project: str = "mays-orders-rc4", account: str = "240571105849"):
    return PlanMetadata(
        deployment_id=DeploymentId(account_id=account, project=project, environment="development"),
        version=SemanticVersion.parse("0.1.0"),
        development_phase=DevelopmentPhase.parse("H2"),
        operation=PlanOperation.DEPLOY,
        sequence_number=1,
    )


class TestBackendContract(unittest.TestCase):
    def test_repository_backend_is_parsed(self):
        contract = load_backend_contract(TERRAFORM_DIR)
        self.assertEqual(contract.backend_type, "s3")
        self.assertEqual(contract.bucket, "mays-orders-tfstate-central-240571105849")
        self.assertEqual(contract.key, "terraform.tfstate")
        self.assertEqual(contract.region, "eu-central-1")
        self.assertEqual(contract.workspace_key_prefix, "env:")
        self.assertEqual(contract.dynamodb_table, "mays-orders-terraform-locks")
        self.assertFalse(contract.use_lockfile)
        self.assertTrue(contract.encrypt)

    def test_state_key_matches_terraform_semantics(self):
        contract = load_backend_contract(TERRAFORM_DIR)
        self.assertEqual(
            contract.state_key("mays-orders-rc4"),
            "env:/mays-orders-rc4/terraform.tfstate",
        )
        self.assertEqual(contract.state_key("default"), "terraform.tfstate")

    def test_missing_backend_block_fails_closed(self):
        with self.assertRaises(BackendContractError):
            parse_backend_contract('terraform {\n  required_version = ">= 1.5.0"\n}\n')

    def test_non_s3_backend_is_rejected(self):
        text = 'terraform {\n  backend "local" {\n    path = "x"\n  }\n}\n'
        with self.assertRaises(BackendContractError):
            parse_backend_contract(text)

    def test_incomplete_backend_is_rejected(self):
        text = 'terraform {\n  backend "s3" {\n    bucket = "b"\n  }\n}\n'
        with self.assertRaises(BackendContractError):
            parse_backend_contract(text)


class TestRemotePlanValidation(unittest.TestCase):
    def setUp(self):
        self.contract = load_backend_contract(TERRAFORM_DIR)
        self.valid = dict(
            project_name="mays-orders-rc4",
            environment="development",
            region="eu-central-1",
            workspace="mays-orders-rc4",
            project_name_explicit=True,
            environment_explicit=True,
            output_explicit=True,
        )

    def _errors(self, **overrides):
        kwargs = dict(self.valid)
        kwargs.update(overrides)
        return validate_remote_plan(self.contract, **kwargs)

    def test_valid_remote_plan_passes(self):
        self.assertEqual(self._errors(), [])

    def test_project_name_must_be_explicit(self):
        self.assertTrue(any("--project-name" in e for e in self._errors(project_name_explicit=False)))

    def test_environment_must_be_explicit(self):
        self.assertTrue(any("--environment" in e for e in self._errors(environment_explicit=False)))

    def test_output_must_be_explicit(self):
        self.assertTrue(any("--out" in e for e in self._errors(output_explicit=False)))

    def test_default_workspace_is_rejected(self):
        errors = self._errors(workspace="default", project_name="mays-orders-rc4")
        self.assertTrue(any("default" in e for e in errors))

    def test_workspace_must_match_project(self):
        errors = self._errors(workspace="mays-orders")
        self.assertTrue(any("Workspace" in e for e in errors))

    def test_region_mismatch_is_rejected(self):
        errors = self._errors(region="us-east-1")
        self.assertTrue(any("Region" in e for e in errors))

    def test_missing_locking_is_rejected(self):
        from dataclasses import replace

        contract = replace(self.contract, dynamodb_table=None, use_lockfile=False)
        errors = validate_remote_plan(contract, **self.valid)
        self.assertTrue(any("Locking" in e for e in errors))

    def test_use_lockfile_satisfies_locking(self):
        from dataclasses import replace

        contract = replace(self.contract, dynamodb_table=None, use_lockfile=True)
        self.assertEqual(validate_remote_plan(contract, **self.valid), [])

    def test_unencrypted_backend_is_rejected(self):
        from dataclasses import replace

        contract = replace(self.contract, encrypt=False)
        errors = validate_remote_plan(contract, **self.valid)
        self.assertTrue(any("encrypt" in e for e in errors))

    def test_invalid_project_name_is_rejected(self):
        errors = self._errors(project_name="Mays_Orders", workspace="Mays_Orders")
        self.assertTrue(any("Ungueltiger project_name" in e for e in errors))


class TestPlanOutputResolution(unittest.TestCase):
    def setUp(self):
        self.meta = _metadata()
        self.canonical = self.meta.to_filename()

    def test_default_output_is_canonical_in_terraform_dir(self):
        path = resolve_plan_output(TERRAFORM_DIR, None, self.canonical, self.meta)
        self.assertEqual(path.name, self.canonical)
        self.assertEqual(path.parent, TERRAFORM_DIR.resolve())

    def test_directory_output_keeps_canonical_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = resolve_plan_output(TERRAFORM_DIR, tmp, self.canonical, self.meta)
            self.assertEqual(path.name, self.canonical)
            self.assertEqual(path.parent, Path(tmp).resolve())

    def test_identity_filename_is_accepted(self):
        path = resolve_plan_output(TERRAFORM_DIR, self.canonical, self.canonical, self.meta)
        self.assertEqual(path.name, self.canonical)

    def test_foreign_identity_filename_is_rejected(self):
        foreign = _metadata(project="mays-orders").to_filename()
        with self.assertRaises(PlanOutputError):
            resolve_plan_output(TERRAFORM_DIR, foreign, self.canonical, self.meta)

    def test_unparseable_plan_filename_is_rejected(self):
        with self.assertRaises(PlanOutputError):
            resolve_plan_output(TERRAFORM_DIR, "deploy.tfplan", self.canonical, self.meta)


class TestStateGuard(unittest.TestCase):
    def test_missing_local_state_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = assert_no_state_migration(tmp)
            self.assertFalse(meta["exists"])

    def test_empty_local_state_is_allowed_but_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "terraform.tfstate").write_text(
                json.dumps({"version": 4, "serial": 1, "resources": []}), encoding="utf-8"
            )
            meta = inspect_local_state(tmp)
            self.assertTrue(meta["exists"])
            self.assertEqual(meta["resources"], 0)
            assert_no_state_migration(tmp)

    def test_local_state_with_resources_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "terraform.tfstate").write_text(
                json.dumps({"version": 4, "serial": 2, "resources": [{"type": "x"}]}),
                encoding="utf-8",
            )
            with self.assertRaises(StateMigrationBlocked):
                assert_no_state_migration(tmp)

    def test_unreadable_local_state_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "terraform.tfstate").write_text("{not json", encoding="utf-8")
            with self.assertRaises(StateMigrationBlocked):
                assert_no_state_migration(tmp)


class TestInitIsNonInteractive(unittest.TestCase):
    def _aws_ctx(self):
        ctx = MagicMock()
        ctx.validated = True
        ctx.get_environment.return_value = {}
        ctx.profile = "mayaws"
        ctx.region = "eu-central-1"
        return ctx

    @patch("installer.terraform.runner.subprocess.run")
    def test_init_always_uses_input_false(self, mock_run):
        from installer.terraform.runner import TerraformRunner

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner = TerraformRunner("/tmp", aws_context=self._aws_ctx(), workspace="mays-orders-rc4")
        runner.init(backend=True)
        argv = mock_run.call_args.args[0]
        self.assertIn("-input=false", argv)
        self.assertNotIn("-backend=false", argv)

    @patch("installer.terraform.runner.subprocess.run")
    def test_init_without_backend_still_non_interactive(self, mock_run):
        from installer.terraform.runner import TerraformRunner

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner = TerraformRunner("/tmp", aws_context=self._aws_ctx(), workspace="mays-orders-rc4")
        runner.init(backend=False)
        argv = mock_run.call_args.args[0]
        self.assertIn("-input=false", argv)
        self.assertIn("-backend=false", argv)


if __name__ == "__main__":
    unittest.main()
