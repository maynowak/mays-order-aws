"""MO-RC4-P02I-E1B: Projektkontext fuer Destroy-Plaene.

Stellt sicher, dass `plan-destroy` denselben Projektkontext wie `plan`
uebergibt und nicht auf den Terraform-Default ("mays-orders") zurueckfaellt.
Keine AWS-Aufrufe, keine echte Destroy-Ausfuehrung.
"""

from __future__ import annotations

import argparse
import unittest
from unittest.mock import MagicMock, patch

from installer.cli.main import build_plan_variables
from installer.terraform.runner import TerraformRunner


def _context(project_name: str = "mays-orders-rc4") -> MagicMock:
    ctx = MagicMock()
    ctx.project_name = project_name
    ctx.to_env.return_value = {}
    return ctx


def _aws_context() -> MagicMock:
    aws_ctx = MagicMock()
    aws_ctx.validated = True
    aws_ctx.get_environment.return_value = {}
    aws_ctx.profile = "mayaws"
    aws_ctx.region = "eu-central-1"
    return aws_ctx


class TestBuildPlanVariables(unittest.TestCase):
    def test_project_name_is_always_injected(self):
        parsed = argparse.Namespace(var=None, notification_email=None)
        var = build_plan_variables(_context("mays-orders-rc4"), parsed)
        self.assertEqual(var["project_name"], "mays-orders-rc4")

    def test_recovery_flags_are_explicitly_disabled(self):
        parsed = argparse.Namespace(var=None, notification_email=None)
        var = build_plan_variables(_context(), parsed)
        self.assertEqual(var["recovery_enabled"], "false")
        self.assertEqual(var["processing_recovery_enabled"], "false")

    def test_explicit_recovery_override_is_respected(self):
        parsed = argparse.Namespace(
            var=["recovery_enabled=true"], notification_email=None
        )
        var = build_plan_variables(_context(), parsed)
        self.assertEqual(var["recovery_enabled"], "true")
        self.assertEqual(var["processing_recovery_enabled"], "false")

    def test_explicit_project_override_wins(self):
        parsed = argparse.Namespace(var=["project_name=custom"], notification_email=None)
        var = build_plan_variables(_context("mays-orders-rc4"), parsed)
        self.assertEqual(var["project_name"], "custom")

    def test_notification_email_is_forwarded(self):
        parsed = argparse.Namespace(var=None, notification_email="ops@example.com")
        var = build_plan_variables(_context(), parsed)
        self.assertEqual(var["notification_email"], "ops@example.com")

    def test_malformed_var_entries_are_ignored(self):
        parsed = argparse.Namespace(var=["broken"], notification_email=None)
        var = build_plan_variables(_context(), parsed)
        self.assertEqual(var["project_name"], "mays-orders-rc4")
        self.assertNotIn("broken", var)


class TestDestroyPlanProjectContext(unittest.TestCase):
    @patch("installer.terraform.runner.subprocess.run")
    def test_plan_destroy_passes_project_name(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner = TerraformRunner(
            "/tmp", aws_context=_aws_context(), workspace="mays-orders-rc4"
        )

        with patch.object(runner, "_ensure_workspace"):
            runner.plan_destroy(
                out_file="destroy.tfplan", var={"project_name": "mays-orders-rc4"}
            )

        plan_calls = [
            call for call in mock_run.call_args_list if call.args and call.args[0][:2] == ["terraform", "plan"]
        ]
        self.assertEqual(len(plan_calls), 1)
        argv = plan_calls[0].args[0]
        self.assertIn("-destroy", argv)
        self.assertIn("-input=false", argv)
        self.assertIn("-var", argv)
        self.assertIn("project_name=mays-orders-rc4", argv)

    @patch("installer.terraform.runner.subprocess.run")
    def test_plan_destroy_without_var_would_be_explicit(self, mock_run):
        """Ohne var kein stilles Projekt: der Aufrufer muss den Kontext liefern."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner = TerraformRunner(
            "/tmp", aws_context=_aws_context(), workspace="mays-orders-rc4"
        )

        with patch.object(runner, "_ensure_workspace"):
            runner.plan_destroy(out_file="destroy.tfplan")

        argv = mock_run.call_args.args[0]
        self.assertNotIn("-var", argv)


if __name__ == "__main__":
    unittest.main()
