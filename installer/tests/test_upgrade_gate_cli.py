"""MO-INSTALLER-UPGRADE-SAFETY-P0A-01: Gate-Integration in den Installer.

Rein lokal: Terraform-Aufrufe und Apply werden gemockt.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from installer.cli.main import InstallerCLI
from installer.core.deployment_identity import DeploymentId


def _plan(*changes) -> dict:
    return {"resource_changes": list(changes)}


def _change(address: str, resource_type: str, actions) -> dict:
    return {"address": address, "type": resource_type, "change": {"actions": actions}}


CRITICAL_PLAN = _plan(
    _change("module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["create", "delete"])
)
SAFE_PLAN = _plan(
    _change("module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["update"])
)
DESTROY_PLAN = _plan(
    _change("module.dynamodb.aws_dynamodb_table.orders", "aws_dynamodb_table", ["delete"])
)


class UpgradeGateTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name)
        self.plan_file = self.run_dir / "plan.tfplan"
        self.plan_file.write_bytes(b"plan")

    def _context(self):
        ctx = MagicMock()
        ctx.project_name = "mays-orders-rc4"
        ctx.environment = "development"
        ctx.terraform_workspace = "mays-orders-rc4"
        ctx.terraform_dir = "terraform"
        ctx.aws_region = "eu-central-1"
        ctx.aws_profile = "mayaws"
        ctx.dry_run = False
        ctx.allow_aws_operations = True
        ctx.deployment_version = "0.1.0"
        ctx.development_phase = "H2"
        ctx.development_step = 0
        ctx.development_status = "development"
        ctx.run_id = "run-1"
        ctx.validate_aws_context.return_value = True
        ctx.get_deployment_context.return_value = SimpleNamespace(
            deployment_id=DeploymentId("240571105849", "mays-orders-rc4", "development")
        )
        return ctx

    def _cli_with_plan(self, plan_json):
        cli = InstallerCLI()
        runner = MagicMock()
        runner.show_plan.return_value = SimpleNamespace(
            success=True, stdout=json.dumps(plan_json), stderr=""
        )
        cli._make_runner = MagicMock(return_value=runner)
        return cli, runner


class TestEnforceUpgradeSafety(UpgradeGateTestCase):
    def test_safe_plan_passes(self):
        cli, _ = self._cli_with_plan(SAFE_PLAN)
        self.assertTrue(cli._enforce_upgrade_safety(self._context(), self.plan_file, self.run_dir))

    def test_critical_plan_blocks_and_writes_migration_plan(self):
        cli, _ = self._cli_with_plan(CRITICAL_PLAN)
        self.assertFalse(cli._enforce_upgrade_safety(self._context(), self.plan_file, self.run_dir))
        self.assertTrue((self.run_dir / "upgrade-migration-plan.json").exists())
        self.assertTrue((self.run_dir / "upgrade-migration-plan.md").exists())

    def test_unreadable_plan_fails_closed(self):
        cli, runner = self._cli_with_plan({})
        runner.show_plan.return_value = SimpleNamespace(success=False, stdout="", stderr="boom")
        self.assertFalse(cli._enforce_upgrade_safety(self._context(), self.plan_file, self.run_dir))

    def test_invalid_json_fails_closed(self):
        cli, runner = self._cli_with_plan({})
        runner.show_plan.return_value = SimpleNamespace(success=True, stdout="{broken", stderr="")
        self.assertFalse(cli._enforce_upgrade_safety(self._context(), self.plan_file, self.run_dir))

    def test_unknown_plan_structure_fails_closed(self):
        cli, _ = self._cli_with_plan({"foo": "bar"})
        self.assertFalse(cli._enforce_upgrade_safety(self._context(), self.plan_file, self.run_dir))


class TestDestroyPlanGuard(UpgradeGateTestCase):
    def test_delete_only_plan_is_accepted(self):
        cli, _ = self._cli_with_plan(DESTROY_PLAN)
        ok, reason = cli._verify_destroy_plan(self._context(), self.plan_file)
        self.assertTrue(ok, reason)

    def test_deploy_plan_is_rejected(self):
        cli, _ = self._cli_with_plan(SAFE_PLAN)
        ok, reason = cli._verify_destroy_plan(self._context(), self.plan_file)
        self.assertFalse(ok)
        self.assertIn("kein Destroy-Plan", reason)

    def test_unreadable_plan_fails_closed(self):
        cli, runner = self._cli_with_plan({})
        runner.show_plan.return_value = SimpleNamespace(success=False, stdout="", stderr="boom")
        ok, _ = cli._verify_destroy_plan(self._context(), self.plan_file)
        self.assertFalse(ok)


class TestDeployBlockedNoApply(UpgradeGateTestCase):
    def test_blocked_gate_prevents_apply(self):
        cli, runner = self._cli_with_plan(SAFE_PLAN)
        parsed = SimpleNamespace(plan=str(self.plan_file), yes=False)
        with patch.object(InstallerCLI, "_verify_plan_manifest", return_value=True), \
             patch.object(InstallerCLI, "_enforce_upgrade_safety", return_value=False):
            exit_code = cli._cmd_deploy(self._context(), parsed, self.run_dir)
        self.assertEqual(exit_code, 1)
        runner.apply.assert_not_called()

    def test_gate_runs_before_apply_in_source(self):
        """Reihenfolge absichern: Gate vor dem Apply-Aufruf."""
        import inspect

        source = inspect.getsource(InstallerCLI._cmd_deploy)
        self.assertIn("_enforce_upgrade_safety", source)
        self.assertLess(
            source.index("_enforce_upgrade_safety"),
            source.index("runner.apply("),
        )

    def test_plan_gate_runs_before_manifest_write(self):
        import inspect

        source = inspect.getsource(InstallerCLI._cmd_plan)
        self.assertLess(
            source.index("_enforce_upgrade_safety"),
            source.index("PlanManifest.create"),
        )


if __name__ == "__main__":
    unittest.main()
