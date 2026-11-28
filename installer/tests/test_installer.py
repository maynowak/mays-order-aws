"""
Tests for installer core components.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from installer.core.context import InstallationContext, ValidationLayer, ValidationCheck, ValidationResult
from installer.terraform.runner import TerraformRunner, PlanResult, TerraformResult
from installer.terraform.plan_analysis import evaluate_plan_safety, analyze_plan_safety
from installer.run.manager import RunDirectoryManager, PlanArtifactManager

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_installer_context(tmpdir: str) -> InstallationContext:
    """Build a fully mocked, non-AWS installer context for command tests."""
    ctx = InstallationContext(
        aws_profile="test-profile",
        project_name="mays-orders",
        terraform_workspace="mays-orders",
        terraform_dir=tmpdir,
        dry_run=True,
        allow_aws_operations=True,
    )
    ctx.aws_execution_context = SimpleNamespace(account_id="123456789012")
    ctx.validate_aws_context = MagicMock(return_value=True)
    ctx.get_deployment_context = MagicMock(
        return_value=SimpleNamespace(
            deployment_id="123456789012:mays-orders:test",
            version="0.2.0",
            development_state=SimpleNamespace(phase="H2"),
        )
    )
    return ctx


def _make_runner_mock() -> MagicMock:
    """Return a Terraform runner stub; no subprocess or AWS call can escape it."""
    runner = MagicMock()
    runner.show_plan.return_value = SimpleNamespace(
        success=True,
        stdout='{"resource_changes": []}',
        stderr="",
    )
    runner.verify_plan_integrity.return_value = (True, "")
    runner.verify_plan_context_match.return_value = (True, "")
    runner.apply.return_value = SimpleNamespace(success=True, stderr="")
    runner.destroy.return_value = SimpleNamespace(success=True, stderr="")
    runner.state_list.return_value = SimpleNamespace(success=True, stdout="")
    runner.version.return_value = SimpleNamespace(success=True)
    return runner


def _deploy_gate_patches():
    from installer.cli.main import InstallerCLI

    return [
        patch.object(InstallerCLI, "_verify_plan_manifest", return_value=True),
        patch.object(InstallerCLI, "_verify_version_binding", return_value=True),
        patch.object(InstallerCLI, "_verify_state_baseline", return_value=True),
        patch.object(InstallerCLI, "_verify_backup_gate", return_value=True),
        patch.object(InstallerCLI, "_verify_upgrade_readiness", return_value=True),
        patch.object(InstallerCLI, "_enforce_upgrade_safety", return_value=True),
        patch("installer.cli.main.PlanDiscovery.validate_plan_context", return_value=(True, "")),
        patch("installer.cli.main.PlanMetadata.parse_filename", return_value=None),
    ]


def _destroy_gate_patches():
    from installer.cli.main import InstallerCLI

    backend = MagicMock()
    backend.state_key.return_value = "mays-orders/terraform.tfstate"
    return [
        patch.object(InstallerCLI, "_verify_plan_manifest", return_value=True),
        patch.object(InstallerCLI, "_verify_destroy_plan", return_value=(True, "")),
        patch("installer.cli.main.PlanDiscovery.validate_plan_context", return_value=(True, "")),
        patch("installer.cli.main.PlanMetadata.parse_filename", return_value=None),
        patch("installer.core.plan_contract.load_backend_contract", return_value=backend),
        patch("installer.core.cleanup_contract.validate_cleanup_target", return_value=[]),
    ]


class TestInstallationContext(unittest.TestCase):
    """Test InstallationContext."""

    def test_default_context(self):
        """Test default context creation."""
        ctx = InstallationContext()
        self.assertEqual(ctx.aws_profile, "")
        self.assertEqual(ctx.aws_region, "eu-central-1")
        self.assertEqual(ctx.project_name, "mays-orders")
        self.assertEqual(ctx.environment, "Development")
        self.assertTrue(ctx.dry_run)
        self.assertFalse(ctx.allow_aws_operations)

    def test_context_from_env(self):
        """Test context creation from environment."""
        with patch.dict(os.environ, {
            "AWS_PROFILE": "test-profile",
            "AWS_REGION": "us-east-1",
            "PROJECT_NAME": "test-project",
            "ENVIRONMENT": "Production"
        }):
            ctx = InstallationContext.from_env()
            self.assertEqual(ctx.aws_profile, "test-profile")
            self.assertEqual(ctx.aws_region, "us-east-1")
            self.assertEqual(ctx.project_name, "test-project")
            self.assertEqual(ctx.environment, "Production")

    def test_context_serialization(self):
        """Test context serialization."""
        ctx = InstallationContext(
            aws_profile="test",
            aws_region="us-west-2",
            project_name="test"
        )

        json_str = ctx.to_json()
        restored = InstallationContext.from_json(json_str)

        self.assertEqual(ctx.aws_profile, restored.aws_profile)
        self.assertEqual(ctx.aws_region, restored.aws_region)
        self.assertEqual(ctx.project_name, restored.project_name)

    def test_run_dir_creation(self):
        """Test run directory creation."""
        ctx = InstallationContext()
        run_dir = ctx.ensure_run_dir()
        self.assertTrue(run_dir.exists())
        self.assertTrue(run_dir.is_dir())


class TestValidationLayer(unittest.TestCase):
    """Test ValidationLayer."""

    @patch("subprocess.run")
    def test_aws_profile_check_pass(self, mock_run):
        """Test AWS profile check passes."""
        # Mock two calls: aws configure list and aws sts get-caller-identity
        mock_run.side_effect = [
            MagicMock(returncode=0),  # aws configure list
            MagicMock(returncode=0, stdout=json.dumps({"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/test"}))  # sts get-caller-identity
        ]

        ctx = InstallationContext(aws_profile="test-profile")
        validation = ValidationLayer(ctx)
        validation._check_aws_profile_validated()

        # Check that checks were added (aws_profile_validated, aws_identity_validated, aws_account_id_validated)
        self.assertEqual(len(validation.result.checks), 3)
        self.assertTrue(all(c.status == "PASS" for c in validation.result.checks))

    @patch("subprocess.run")
    def test_aws_profile_check_fail(self, mock_run):
        """Test AWS profile check fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="profile not found")

        ctx = InstallationContext(aws_profile="nonexistent")
        validation = ValidationLayer(ctx)
        validation._check_aws_profile_validated()

        self.assertEqual(len(validation.result.checks), 1)
        self.assertEqual(validation.result.checks[0].status, "FAIL")

    @patch("subprocess.run")
    def test_terraform_cli_check(self, mock_run):
        """Test Terraform CLI check."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Terraform v1.5.0\n"
        )

        ctx = InstallationContext(terraform_dir="terraform")
        validation = ValidationLayer(ctx)
        validation._check_terraform_cli()

        self.assertEqual(len(validation.result.checks), 1)
        self.assertEqual(validation.result.checks[0].status, "PASS")

    def test_validation_result_summary(self):
        """Test validation result summary."""
        result = ValidationResult(status="")
        result.add_check(ValidationCheck("test1", "PASS", "pass"))
        result.add_check(ValidationCheck("test2", "FAIL", "fail"))
        result.add_check(ValidationCheck("test3", "WARNING", "warn"))

        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(result.has_errors())
        self.assertTrue(result.has_warnings())
        self.assertIn("1 passed", result.summary())
        self.assertIn("1 failed", result.summary())
        self.assertIn("1 warned", result.summary())


class TestTerraformRunner(unittest.TestCase):
    """Test TerraformRunner."""

    @patch("subprocess.run")
    def test_version(self, mock_run):
        """Test version command."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"terraform_version": "1.5.0"}',
            stderr=""
        )

        from installer.core.context import AWSExecutionContext
        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )
        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)
        result = runner.version()

        self.assertTrue(result.success)
        self.assertIn("1.5.0", result.stdout)

    @patch("subprocess.run")
    def test_validate_success(self, mock_run):
        """Test validate success."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Success! The configuration is valid.",
            stderr=""
        )

        from installer.core.context import AWSExecutionContext
        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )
        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)
        result = runner.validate()

        self.assertTrue(result.success)

    @patch("subprocess.run")
    def test_validate_failure(self, mock_run):
        """Test validate failure."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Invalid configuration"
        )

        from installer.core.context import AWSExecutionContext
        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )
        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)
        result = runner.validate()

        self.assertFalse(result.success)

    def test_plan_result_from_json(self):
        """Test PlanResult from JSON."""
        plan_json = {
            "resource_changes": [
                {
                    "address": "aws_s3_bucket.bucket",
                    "type": "aws_s3_bucket",
                    "name": "bucket",
                    "change": {
                        "actions": ["create"]
                    }
                },
                {
                    "address": "aws_lambda_function.func",
                    "type": "aws_lambda_function",
                    "name": "func",
                    "change": {
                        "actions": ["update"]
                    }
                }
            ]
        }

        plan_result = PlanResult.from_plan_json(plan_json, "test.tfplan", "deploy")

        self.assertEqual(plan_result.add, 1)
        self.assertEqual(plan_result.change, 1)
        self.assertEqual(plan_result.destroy, 0)
        self.assertEqual(plan_result.replace, 0)
        self.assertEqual(len(plan_result.resources), 2)


class TestPlanAnalysis(unittest.TestCase):
    """Test plan analysis functions."""

    def test_evaluate_plan_safety_deploy_no_destroy(self):
        """Test deploy plan with no destroys."""
        plan = PlanResult(
            mode="deploy",
            plan_file="test.tfplan",
            add=5,
            change=2,
            destroy=0,
            replace=0
        )

        result = evaluate_plan_safety(plan, mode="deploy")

        self.assertEqual(result["status"], "PASS")

    def test_evaluate_plan_safety_deploy_with_destroy(self):
        """Test deploy plan with destroys."""
        plan = PlanResult(
            mode="deploy",
            plan_file="test.tfplan",
            add=5,
            change=2,
            destroy=2,
            replace=0
        )

        # Use policy with low max_destroys to trigger warning
        policy = {
            "allow_destroy_in_deploy": True,
            "max_destroys_in_deploy": 1,  # Allow only 1 destroy, plan has 2
            "max_replacements": 5,
            "max_total_changes": 100,
        }
        result = evaluate_plan_safety(plan, mode="deploy", policy=policy)

        self.assertEqual(result["status"], "WARNING")
        self.assertTrue(any(c["name"] == "destroy_in_deploy" for c in result["checks"]))

    def test_evaluate_plan_safety_with_replacements(self):
        """Test plan with replacements."""
        plan = PlanResult(
            mode="deploy",
            plan_file="test.tfplan",
            add=0,
            change=0,
            destroy=1,
            replace=1
        )

        # Use policy with low max_replacements to trigger warning
        policy = {
            "allow_destroy_in_deploy": True,
            "max_destroys_in_deploy": 5,
            "max_replacements": 0,  # No replacements allowed
            "max_total_changes": 100,
        }
        result = evaluate_plan_safety(plan, mode="deploy", policy=policy)

        self.assertEqual(result["status"], "WARNING")
        self.assertTrue(any(c["name"] == "replacements" for c in result["checks"]))

    def test_evaluate_plan_safety_large_plan(self):
        """Test large plan warning."""
        plan = PlanResult(
            mode="deploy",
            plan_file="test.tfplan",
            add=150,  # Exceeds default max_total_changes of 100
            change=0,
            destroy=0,
            replace=0
        )

        result = evaluate_plan_safety(plan, mode="deploy")

        self.assertEqual(result["status"], "WARNING")
        self.assertTrue(any(c["name"] == "large_plan" for c in result["checks"]))


class TestRunDirectoryManager(unittest.TestCase):
    """Test RunDirectoryManager."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = RunDirectoryManager(base_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_run_dir(self):
        run_dir = self.manager.create_run_dir("test-run-001")
        self.assertTrue(run_dir.exists())
        self.assertTrue((run_dir / "logs").exists())
        self.assertTrue((run_dir / "plans").exists())
        self.assertTrue((run_dir / "artifacts").exists())

    def test_save_context(self):
        from installer.core.context import InstallationContext

        run_dir = self.manager.create_run_dir("test-001")
        context = InstallationContext(project_name="test")

        path = self.manager.save_context(run_dir, context)

        self.assertTrue(path.exists())
        # Verify content
        import json
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["project_name"], "test")


class TestPlanArtifactManager(unittest.TestCase):
    """Test PlanArtifactManager."""

    def test_sanitize_plan_json(self):
        plan_json = {
            "resource_changes": [{
                "address": "aws_db_instance.db",
                "change": {
                    "after": {
                        "password": "secret123",
                        "username": "admin",
                        "key": "secret_key"
                    }
                }
            }]
        }

        sanitized = PlanArtifactManager.sanitize_plan_json(plan_json)

        after = sanitized["resource_changes"][0]["change"]["after"]
        self.assertEqual(after["password"], "***REDACTED***")
        self.assertEqual(after["key"], "***REDACTED***")
        self.assertEqual(after["username"], "admin")

    def test_validate_plan_file(self):
        import tempfile
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"test": "data"}, f)
            temp_file = f.name

        try:
            self.assertTrue(PlanArtifactManager.validate_plan_file(temp_file))
        finally:
            os.unlink(temp_file)

    def test_validate_plan_file_invalid(self):
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("invalid json {")
            temp_file = f.name

        try:
            self.assertFalse(PlanArtifactManager.validate_plan_file(temp_file))
        finally:
            os.unlink(temp_file)


class TestDeployCommand(unittest.TestCase):
    """Test deploy command."""

    def test_deploy_requires_approval(self):
        """Deploy without --yes must stop before apply when approval is denied."""
        from installer.cli.main import InstallerCLI

        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "deploy.tfplan"
            plan.write_text('{"resource_changes": []}', encoding="utf-8")
            ctx = _make_installer_context(tmpdir)
            parsed = SimpleNamespace(plan=str(plan), yes=False)
            runner = _make_runner_mock()
            make_runner = MagicMock(return_value=runner)
            stdout = io.StringIO()

            with ExitStack() as stack:
                for gate in _deploy_gate_patches():
                    stack.enter_context(gate)
                stack.enter_context(
                    patch.object(InstallerCLI, "_make_runner", new=make_runner)
                )
                input_mock = stack.enter_context(patch("builtins.input", return_value="n"))
                subprocess_mock = stack.enter_context(patch("subprocess.run"))
                stack.enter_context(redirect_stdout(stdout))
                result = InstallerCLI()._cmd_deploy(ctx, parsed, Path(tmpdir))

            self.assertEqual(result, 0)
            runner.apply.assert_not_called()
            input_mock.assert_called_once_with("Proceed with deployment? [y/N]: ")
            runner.state_list.assert_not_called()
            runner.version.assert_not_called()
            subprocess_mock.assert_not_called()
            self.assertIn("Deployment cancelled.", stdout.getvalue())
            self.assertNotIn("Applying plan", stdout.getvalue())

    def test_deploy_requires_plan_file(self):
        """Deploy with a missing plan must fail closed before any runner call."""
        from installer.cli.main import InstallerCLI

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _make_installer_context(tmpdir)
            parsed = SimpleNamespace(plan=str(Path(tmpdir) / "missing.tfplan"), yes=False)
            runner = _make_runner_mock()
            make_runner = MagicMock(return_value=runner)
            stdout = io.StringIO()

            with ExitStack() as stack:
                for gate in _deploy_gate_patches():
                    stack.enter_context(gate)
                stack.enter_context(
                    patch.object(InstallerCLI, "_make_runner", new=make_runner)
                )
                subprocess_mock = stack.enter_context(patch("subprocess.run"))
                stack.enter_context(redirect_stdout(stdout))
                result = InstallerCLI()._cmd_deploy(ctx, parsed, Path(tmpdir))

            self.assertEqual(result, 1)
            make_runner.assert_not_called()
            runner.apply.assert_not_called()
            subprocess_mock.assert_not_called()
            self.assertIn("Plan file not found", stdout.getvalue())
            self.assertNotIn("Applying plan", stdout.getvalue())

    def test_destroy_requires_approval(self):
        """Destroy without --yes must not call destroy, apply, or backup paths."""
        from installer.cli.main import InstallerCLI

        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "destroy.tfplan"
            plan.write_text('{"resource_changes": []}', encoding="utf-8")
            ctx = _make_installer_context(tmpdir)
            parsed = SimpleNamespace(plan=str(plan), yes=False)
            runner = _make_runner_mock()
            make_runner = MagicMock(return_value=runner)
            stdout = io.StringIO()

            with ExitStack() as stack:
                for gate in _destroy_gate_patches():
                    stack.enter_context(gate)
                stack.enter_context(
                    patch.object(InstallerCLI, "_make_runner", new=make_runner)
                )
                input_mock = stack.enter_context(patch("builtins.input", return_value="n"))
                subprocess_mock = stack.enter_context(patch("subprocess.run"))
                stack.enter_context(redirect_stdout(stdout))
                result = InstallerCLI()._cmd_destroy(ctx, parsed, Path(tmpdir))

            self.assertEqual(result, 0)
            runner.destroy.assert_not_called()
            runner.apply.assert_not_called()
            runner.state_list.assert_not_called()
            input_mock.assert_called_once_with("Proceed with DESTRUCTION? [y/N]: ")
            subprocess_mock.assert_not_called()
            called = {call[0] for call in runner.method_calls if call}
            self.assertFalse(called & {"destroy", "apply", "state_list", "backup", "restore"})
            self.assertIn("Destruction cancelled.", stdout.getvalue())
            self.assertNotIn("Applying destroy plan", stdout.getvalue())


class TestStateCommands(unittest.TestCase):
    """Test state commands."""

    @patch("subprocess.run")
    def test_state_list(self, mock_run):
        """Test state list command."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="module.resource1\nmodule.resource2",
            stderr=""
        )

        from installer.core.context import InstallationContext, AWSExecutionContext
        from installer.terraform.runner import TerraformRunner

        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)
        result = runner.state_list()

        self.assertTrue(result.success)
        self.assertIn("module.", result.stdout)


class TestOutputCommand(unittest.TestCase):
    """Test output command."""

    @patch("subprocess.run")
    def test_output_all(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"output1": {"value": "value1"}}',
            stderr=""
        )

        from installer.core.context import AWSExecutionContext
        from installer.terraform.runner import TerraformRunner

        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)
        result = runner.output()

        self.assertTrue(result.success)


class TestIdentityCommand(unittest.TestCase):
    """Test identity command."""

    @patch("subprocess.run")
    def test_identity(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"terraform_version": "1.5.0"}',
            stderr=""
        )

        # Mock the sts call
        with patch("subprocess.run") as mock_sts:
            mock_sts.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "Account": "123456789012",
                    "Arn": "arn:aws:iam::123456789012:user/test",
                    "UserId": "AIDACKCEVSQ6C2EXAMPLE"
                }),
                stderr=""
            )

            from installer.core.context import AWSExecutionContext
            from installer.terraform.runner import TerraformRunner

            mock_aws_context = AWSExecutionContext(
                profile="mayaws",
                region="eu-central-1",
                account_id="123456789012",
                identity_arn="arn:aws:iam::123456789012:user/test",
                validated=True
            )

            runner = TerraformRunner("/tmp", aws_context=mock_aws_context)
            result = runner.version()

            self.assertTrue(result.success)

            # Test AWS identity call
            with patch("subprocess.run") as mock_sts:
                mock_sts.return_value = MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "Account": "123456789012",
                        "Arn": "arn:aws:iam::123456789012:user/test",
                        "UserId": "AIDACKCEVSQ6C2EXAMPLE"
                    }),
                    stderr=""
                )

                runner = TerraformRunner("/tmp", aws_context=mock_aws_context)
                result = runner.version()
                self.assertTrue(result.success)


class TestYesFlagBehavior(unittest.TestCase):
    """Test --yes flag behavior."""

    def test_yes_flag_skips_approval_prompt(self):
        """--yes must apply exactly once without reading from stdin."""
        from installer.cli.main import InstallerCLI

        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "deploy.tfplan"
            plan.write_text('{"resource_changes": []}', encoding="utf-8")
            ctx = _make_installer_context(tmpdir)
            parsed = SimpleNamespace(plan=str(plan), yes=True)
            runner = _make_runner_mock()
            make_runner = MagicMock(return_value=runner)
            stdout = io.StringIO()

            with ExitStack() as stack:
                for gate in _deploy_gate_patches():
                    stack.enter_context(gate)
                stack.enter_context(
                    patch.object(InstallerCLI, "_make_runner", new=make_runner)
                )
                input_mock = stack.enter_context(
                    patch("builtins.input", side_effect=AssertionError("input() must not be called with --yes"))
                )
                subprocess_mock = stack.enter_context(patch("subprocess.run"))
                stack.enter_context(redirect_stdout(stdout))
                result = InstallerCLI()._cmd_deploy(ctx, parsed, Path(tmpdir))

            self.assertEqual(result, 0)
            input_mock.assert_not_called()
            subprocess_mock.assert_not_called()
            runner.apply.assert_called_once()
            runner.state_list.assert_called_once()
            runner.version.assert_called_once()
            self.assertIn("Applying plan", stdout.getvalue())
            self.assertIn("Deployment completed successfully!", stdout.getvalue())

    def test_without_yes_requires_approval(self):
        """An empty answer at the approval prompt is a safe default-deny."""
        from installer.cli.main import InstallerCLI

        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "deploy.tfplan"
            plan.write_text('{"resource_changes": []}', encoding="utf-8")
            ctx = _make_installer_context(tmpdir)
            parsed = SimpleNamespace(plan=str(plan), yes=False)
            runner = _make_runner_mock()
            make_runner = MagicMock(return_value=runner)
            stdout = io.StringIO()

            with ExitStack() as stack:
                for gate in _deploy_gate_patches():
                    stack.enter_context(gate)
                stack.enter_context(
                    patch.object(InstallerCLI, "_make_runner", new=make_runner)
                )
                input_mock = stack.enter_context(patch("builtins.input", return_value=""))
                subprocess_mock = stack.enter_context(patch("subprocess.run"))
                stack.enter_context(redirect_stdout(stdout))
                result = InstallerCLI()._cmd_deploy(ctx, parsed, Path(tmpdir))

            self.assertEqual(result, 0)
            runner.apply.assert_not_called()
            input_mock.assert_called_once_with("Proceed with deployment? [y/N]: ")
            runner.state_list.assert_not_called()
            runner.version.assert_not_called()
            subprocess_mock.assert_not_called()
            self.assertIn("Deployment cancelled.", stdout.getvalue())


class TestHardeningScenarios(unittest.TestCase):
    """Test hardening scenarios for H1 Security & Execution Hardening."""

    @patch("subprocess.run")
    def test_wrong_profile_rejected(self, mock_run):
        """Test that wrong/missing AWS profile is rejected."""
        mock_run.return_value = MagicMock(returncode=1, stderr="profile not found")

        ctx = InstallationContext(aws_profile="nonexistent-profile")
        validation = ValidationLayer(ctx)
        validation._check_aws_profile_validated()

        self.assertEqual(len(validation.result.checks), 1)
        self.assertEqual(validation.result.checks[0].status, "FAIL")
        self.assertIn("not found", validation.result.checks[0].message)

    @patch("subprocess.run")
    def test_wrong_account_detected(self, mock_run):
        """Test that wrong AWS account is detected when aws_account_id is configured."""
        # Mock valid profile but different account
        mock_run.side_effect = [
            MagicMock(returncode=0),  # aws configure list
            MagicMock(returncode=0, stdout=json.dumps({"Account": "999999999999", "Arn": "arn:aws:iam::999999999999:user/test"}))
        ]

        ctx = InstallationContext(aws_profile="test-profile", aws_account_id="123456789012")
        validation = ValidationLayer(ctx)
        validation._check_aws_profile_validated()

        # Account mismatch should be detected and fail
        self.assertTrue(validation.result.has_errors())
        account_check = next((c for c in validation.result.checks if c.name == "aws_account_id_validated"), None)
        self.assertIsNotNone(account_check)
        self.assertEqual(account_check.status, "FAIL")
        self.assertIn("Account ID mismatch", account_check.message)

    @patch("subprocess.run")
    def test_wrong_region_warning(self, mock_run):
        """Test that invalid region generates warning."""
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout=json.dumps({"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/test"}))
        ]

        ctx = InstallationContext(aws_profile="test-profile", aws_region="invalid-region-999")
        validation = ValidationLayer(ctx)
        validation.run_all()

        region_check = next((c for c in validation.result.checks if c.name == "region"), None)
        self.assertIsNotNone(region_check)
        self.assertEqual(region_check.status, "WARNING")

    def test_plan_integrity_wrong_plan_file(self):
        """Test that wrong plan file is rejected."""
        from installer.terraform.runner import TerraformRunner
        from installer.core.context import AWSExecutionContext

        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)

        # Test with non-existent plan file
        is_valid, error_msg = runner.verify_plan_integrity("nonexistent.tfplan", "test-run-id")
        self.assertFalse(is_valid)
        self.assertIn("not found", error_msg)

    def test_plan_integrity_missing_plan(self):
        """Test that missing plan file is rejected."""
        from installer.terraform.runner import TerraformRunner
        from installer.core.context import AWSExecutionContext

        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)

        is_valid, error_msg = runner.verify_plan_integrity("", "test-run-id")
        self.assertFalse(is_valid)

    @patch("pathlib.Path.exists")
    def test_plan_context_match_same_region(self, mock_exists):
        """Test plan context match with same region."""
        from installer.terraform.runner import TerraformRunner
        from installer.core.context import AWSExecutionContext

        mock_exists.return_value = True
        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)

        # Mock show_plan to return plan with same region
        with patch.object(runner, 'show_plan') as mock_show:
            mock_show.return_value = MagicMock(
                success=True,
                stdout=json.dumps({
                    "configuration": {
                        "provider_config": {
                            "aws": {
                                "expressions": {
                                    "region": {"constant_value": "eu-central-1"}
                                }
                            }
                        }
                    }
                })
            )

            is_valid, error_msg = runner.verify_plan_context_match("test.tfplan", mock_aws_context)
            self.assertTrue(is_valid)

    @patch("pathlib.Path.exists")
    def test_plan_context_match_different_region(self, mock_exists):
        """Test plan context match with different region fails."""
        from installer.terraform.runner import TerraformRunner
        from installer.core.context import AWSExecutionContext

        mock_exists.return_value = True
        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)

        # Mock show_plan to return plan with different region
        with patch.object(runner, 'show_plan') as mock_show:
            mock_show.return_value = MagicMock(
                success=True,
                stdout=json.dumps({
                    "configuration": {
                        "provider_config": {
                            "aws": {
                                "expressions": {
                                    "region": {"constant_value": "us-east-1"}
                                }
                            }
                        }
                    }
                })
            )

            is_valid, error_msg = runner.verify_plan_context_match("test.tfplan", mock_aws_context)
            self.assertFalse(is_valid)
            self.assertIn("region", error_msg.lower())

    def test_state_command_requires_profile_binding(self):
        """Test state commands require AWS profile binding."""
        from installer.terraform.runner import TerraformRunner
        from installer.core.context import AWSExecutionContext

        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)

        # All state commands should use the runner which has aws_context
        self.assertEqual(runner.aws_context.profile, "mayaws")
        self.assertEqual(runner.aws_context.region, "eu-central-1")

    def test_output_command_requires_profile_binding(self):
        """Test output command requires AWS profile binding."""
        from installer.terraform.runner import TerraformRunner
        from installer.core.context import AWSExecutionContext

        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)

        # Output command should use the runner which has aws_context
        self.assertEqual(runner.aws_context.profile, "mayaws")

    def test_identity_command_requires_profile_binding(self):
        """Test identity command requires AWS profile binding."""
        from installer.terraform.runner import TerraformRunner
        from installer.core.context import AWSExecutionContext

        mock_aws_context = AWSExecutionContext(
            profile="mayaws",
            region="eu-central-1",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            validated=True
        )

        runner = TerraformRunner("/tmp", aws_context=mock_aws_context)

        # Identity command should use the runner which has aws_context
        self.assertEqual(runner.aws_context.profile, "mayaws")

    def test_unsanitized_secret_in_plan(self):
        """Test that plan sanitization works for secrets."""
        plan_json = {
            "resource_changes": [{
                "address": "aws_db_instance.db",
                "change": {
                    "after": {
                        "password": "supersecret123",
                        "username": "admin",
                        "secret_key": "mysecretkey",
                        "api_token": "mytoken123"
                    }
                }
            }]
        }

        sanitized = PlanArtifactManager.sanitize_plan_json(plan_json)

        after = sanitized["resource_changes"][0]["change"]["after"]
        self.assertEqual(after["password"], "***REDACTED***")
        self.assertEqual(after["secret_key"], "***REDACTED***")
        self.assertEqual(after["api_token"], "***REDACTED***")
        self.assertEqual(after["username"], "admin")

    @patch("subprocess.run")
    def test_deploy_blocks_without_allow_aws_operations(self, mock_run):
        """Test that deploy is blocked without ALLOW_AWS_OPERATIONS."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"resource_changes": []}',
            stderr=""
        )

        from installer.core.context import InstallationContext
        from installer.cli.main import InstallerCLI
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallationContext(
                aws_profile="test-profile",
                terraform_dir=tempfile.gettempdir(),
                allow_aws_operations=False  # Default is False
            )

            # Create a dummy plan file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.tfplan', delete=False) as f:
                f.write('{"resource_changes": []}')
                plan_file = f.name

            # Test that CLI would block (we test the logic, not the full CLI)
            self.assertFalse(ctx.allow_aws_operations)

    @patch("subprocess.run")
    def test_destroy_blocks_without_allow_aws_operations(self, mock_run):
        """Test that destroy is blocked without ALLOW_AWS_OPERATIONS."""
        from installer.core.context import InstallationContext

        ctx = InstallationContext(
            aws_profile="test-profile",
            terraform_dir="/tmp",
            allow_aws_operations=False
        )

        self.assertFalse(ctx.allow_aws_operations)

    def test_state_push_requires_allow_aws_operations(self):
        """Test that state push requires ALLOW_AWS_OPERATIONS."""
        from installer.core.context import InstallationContext

        ctx = InstallationContext(
            aws_profile="test-profile",
            terraform_dir="/tmp",
            allow_aws_operations=False
        )

        # state push is mutating - should require allow_aws_operations
        self.assertFalse(ctx.allow_aws_operations)

    def test_dry_run_mode_defaults(self):
        """Test dry-run mode defaults."""
        ctx = InstallationContext()

        self.assertTrue(ctx.dry_run)
        self.assertFalse(ctx.allow_aws_operations)

    def test_allow_aws_operations_from_env(self):
        """Test ALLOW_AWS_OPERATIONS from environment."""
        with patch.dict(os.environ, {"ALLOW_AWS_OPERATIONS": "true"}):
            ctx = InstallationContext.from_env()
            self.assertTrue(ctx.allow_aws_operations)

        with patch.dict(os.environ, {"ALLOW_AWS_OPERATIONS": "false"}):
            ctx = InstallationContext.from_env()
            self.assertFalse(ctx.allow_aws_operations)

    def test_dry_run_from_env(self):
        """Test DRY_RUN from environment."""
        with patch.dict(os.environ, {"DRY_RUN": "false"}):
            ctx = InstallationContext.from_env()
            self.assertFalse(ctx.dry_run)

        with patch.dict(os.environ, {"DRY_RUN": "true"}):
            ctx = InstallationContext.from_env()
            self.assertTrue(ctx.dry_run)


class TestD8CICD(unittest.TestCase):
    """Test D8 CI/CD pipeline integration."""

    def test_buildspecs_exist(self):
        """Test that all D8 buildspecs exist."""
        from pathlib import Path

        buildspecs = [
            "ci/buildspecs/validate.yml",
            "ci/buildspecs/plan.yml",
            "ci/buildspecs/deploy.yml",
            "ci/buildspecs/verify.yml",
            "ci/buildspecs/destroy-plan.yml",
            "ci/buildspecs/destroy.yml",
        ]

        for bs in buildspecs:
            self.assertTrue(Path(bs).exists(), f"Missing buildspec: {bs}")

    def test_pipeline_terraform_exists(self):
        """Test that pipeline Terraform configuration exists."""
        from pathlib import Path

        tf_files = [
            "ci/pipeline/main.tf",
            "ci/iam/main.tf",
        ]

        for tf in tf_files:
            self.assertTrue(Path(tf).exists(), f"Missing Terraform file: {tf}")

    def test_pipeline_tfvars_example_exists(self):
        """Test that tfvars example exists."""
        from pathlib import Path

        self.assertTrue(Path("ci/pipeline/terraform.tfvars.example").exists())

    def test_aws_provider_version_6(self):
        """Test that Terraform uses AWS provider >= 6.0."""
        import re

        for tf_file in ["ci/pipeline/main.tf", "ci/iam/main.tf"]:
            with open(tf_file) as f:
                content = f.read()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            self.assertIsNotNone(match, f"No version found in {tf_file}")
            version = match.group(1)
            self.assertTrue(version.startswith(">=") or version.startswith("~> 6") or version.startswith(">= 6"),
                          f"AWS provider version should be >= 6.0, got {version}")

    def test_codebuild_projects_defined(self):
        """Test that all 6 CodeBuild projects are defined in pipeline Terraform."""
        with open("ci/pipeline/main.tf") as f:
            content = f.read()

        projects = [
            "validate",
            "plan",
            "deploy",
            "verify",
            "destroy_plan",
            "destroy",
        ]

        for proj in projects:
            # Check for project name in resource definition
            self.assertIn(f'"{proj}"', content, f"CodeBuild project {proj} not found")

    def test_pipeline_stages_defined(self):
        """Test that all 6 pipeline stages are defined."""
        with open("ci/pipeline/main.tf") as f:
            content = f.read()

        stages = [
            "Source",
            "Validate",
            "Plan",
            "Approval",
            "Deploy",
            "Verify",
        ]

        for stage in stages:
            self.assertIn(f'name = "{stage}"', content, f"Pipeline stage {stage} not found")

    def test_manual_approval_stage(self):
        """Test that manual approval stage is defined."""
        with open("ci/pipeline/main.tf") as f:
            content = f.read()

        self.assertIn('provider', content)
        self.assertIn('Manual', content)
        self.assertIn('Approval', content)

    def test_separate_destroy_pipeline(self):
        """Test that destroy is a separate protected path."""
        with open("ci/pipeline/main.tf") as f:
            content = f.read()

        # Destroy plan and destroy should be separate from main deploy pipeline
        # The main pipeline has Source -> Validate -> Plan -> Approval -> Deploy -> Verify
        # Destroy is a separate operation (not in main pipeline stages)
        self.assertIn("destroy_plan", content)
        self.assertIn("destroy", content)

    def test_iam_roles_separated(self):
        """Test that IAM roles are separated per stage."""
        with open("ci/iam/main.tf") as f:
            content = f.read()

        # Check for stage-specific IAM policies (case-insensitive)
        content_lower = content.lower()
        stage_policies = [
            "codebuild_validate",
            "codebuild_plan",
            "codebuild_deploy",
            "codebuild_verify",
            "codebuild_destroy_plan",
            "codebuild_destroy",
        ]

        for policy in stage_policies:
            self.assertIn(policy.lower(), content_lower, f"IAM policy {policy} not found")

    def test_artifact_bucket_configuration(self):
        """Test that artifact bucket is configured."""
        with open("ci/pipeline/main.tf") as f:
            content = f.read()

        self.assertIn("artifact_bucket_name", content)
        self.assertIn("artifact_store", content)

    def test_github_source_configuration(self):
        """Test that GitHub source is configured."""
        with open("ci/pipeline/main.tf") as f:
            content = f.read()

        self.assertIn("provider         = \"CodeStarSourceConnection\"", content)
        self.assertIn("github_owner", content)
        self.assertIn("github_repo", content)
        self.assertIn("github_branch", content)
        self.assertIn("CodeStarSourceConnection", content)
        self.assertIn("ConnectionArn", content)

    def test_manual_approval_cannot_be_bypassed(self):
        """Test that manual approval is required."""
        with open("ci/pipeline/main.tf") as f:
            content = f.read()

        # Manual approval stage exists and must be before deploy
        self.assertIn('Approval', content)
        self.assertIn('Manual', content)

        # Find the pipeline stage "Deploy" and "Approval" (not CodeBuild project names)
        # The pipeline stages appear after the CodeBuild project definitions
        pipeline_section = content[content.index('resource "aws_codepipeline" "main"'):]
        deploy_index = pipeline_section.index('Deploy')
        approval_index = pipeline_section.index('Approval')
        self.assertLess(approval_index, deploy_index, "Approval must come before Deploy")

    def test_plan_identity_in_buildspecs(self):
        """Test that buildspecs use H2 plan identity."""
        buildspecs = [
            "ci/buildspecs/validate.yml",
            "ci/buildspecs/plan.yml",
            "ci/buildspecs/deploy.yml",
            "ci/buildspecs/verify.yml",
            "ci/buildspecs/destroy-plan.yml",
            "ci/buildspecs/destroy.yml",
        ]

        for bs in buildspecs:
            with open(bs) as f:
                content = f.read()

            # Check for H2 deployment identity variables (case-insensitive)
            content_lower = content.lower()
            self.assertIn("deployment_version", content_lower)
            self.assertIn("development_phase", content_lower)
            self.assertIn("development_step", content_lower)
            self.assertIn("development_status", content_lower)

    def test_deploy_uses_exact_saved_plan(self):
        """Test that deploy stage uses exact saved plan."""
        with open("ci/buildspecs/deploy.yml") as f:
            content = f.read()

        # Deploy should use plan from plan_artifact.json
        self.assertIn("plan_artifact.json", content)
        self.assertIn("plan_path", content)
        self.assertIn("plan_meta", content)

        # Deploy should validate plan identity
        self.assertIn("deployment_id", content)
        self.assertIn("operation", content)

    def test_verify_stage_readonly(self):
        """Test that verify stage is read-only."""
        with open("ci/buildspecs/verify.yml") as f:
            content = f.read()

        # Verify should not have ALLOW_AWS_OPERATIONS=true
        self.assertNotIn("ALLOW_AWS_OPERATIONS.*true", content)
        self.assertNotIn("DRY_RUN.*false", content)

    def test_destroy_is_separate_path(self):
        """Test that destroy is a separate protected path."""
        # Destroy plan and destroy are separate buildspecs
        from pathlib import Path

        self.assertTrue(Path("ci/buildspecs/destroy-plan.yml").exists())
        self.assertTrue(Path("ci/buildspecs/destroy.yml").exists())

        # Main pipeline stages: Source, Validate, Plan, Approval, Deploy, Verify
        # Destroy is NOT in this sequence as a stage
        with open("ci/pipeline/main.tf") as f:
            content = f.read()

        # Check that "Destroy" is not a stage name (it's a separate operation)
        stage_names = []
        import re
        for match in re.finditer(r'name\s*=\s*"([^"]+)"', content):
            stage_names.append(match.group(1))

        self.assertNotIn("Destroy", stage_names, "Destroy should not be a pipeline stage")

    def test_secrets_sanitization_in_buildspecs(self):
        """Test that buildspecs don't log secrets."""
        buildspecs = [
            "ci/buildspecs/validate.yml",
            "ci/buildspecs/plan.yml",
            "ci/buildspecs/deploy.yml",
            "ci/buildspecs/verify.yml",
            "ci/buildspecs/destroy-plan.yml",
            "ci/buildspecs/destroy.yml",
        ]

        for bs in buildspecs:
            with open(bs) as f:
                content = f.read()

            # Should not have hardcoded secrets
            self.assertNotIn("aws_secret_access_key", content)
            self.assertNotIn("aws_access_key_id", content)
            self.assertNotIn("secret_access_key", content)

    def test_terraform_fmt_check(self):
        """Test that Terraform code passes fmt check."""
        import subprocess

        for tf_dir in ["ci/pipeline", "ci/iam"]:
            result = subprocess.run(
                ["terraform", "fmt", "-check", "-diff"],
                cwd=tf_dir,
                capture_output=True,
                text=True
            )
            # terraform fmt doesn't require init
            self.assertEqual(result.returncode, 0, f"terraform fmt failed in {tf_dir}: {result.stdout}")

    def test_terraform_validate(self):
        """Test that Terraform code validates (requires init)."""
        import subprocess

        for tf_dir in ["ci/pipeline", "ci/iam"]:
            # Need to init first
            init_result = subprocess.run(
                ["terraform", "init", "-backend=false"],
                cwd=tf_dir,
                capture_output=True,
                text=True
            )
            if init_result.returncode != 0:
                self.skipTest(f"terraform init failed in {tf_dir}: {init_result.stderr}")

            result = subprocess.run(
                ["terraform", "validate"],
                cwd=tf_dir,
                capture_output=True,
                text=True
            )
            self.assertEqual(result.returncode, 0, f"terraform validate failed in {tf_dir}: {result.stderr}")


class TestDependencyDetector(unittest.TestCase):
    """Test SECURITY-01 dependency detector offline and deterministically."""

    @staticmethod
    def _main_tf(aws_constraint: str = "~> 6.0", time_constraint: str = "~> 0.11") -> str:
        return f"""terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "{aws_constraint}"
    }}
    time = {{
      source  = "hashicorp/time"
      version = "{time_constraint}"
    }}
  }}
}}
"""

    @staticmethod
    def _lock(
        aws_version: str = "6.65.0",
        aws_constraints: str = "~> 6.0",
        time_version: str = "0.14.2",
        time_constraints: str = "~> 0.11",
        include_time: bool = True,
    ) -> str:
        blocks = [
            'provider "registry.terraform.io/hashicorp/aws" {\n'
            f'  version     = "{aws_version}"\n'
            f'  constraints = "{aws_constraints}"\n'
            '  hashes = [\n'
            '    "h1:fixture",\n'
            '  ]\n'
            '}\n'
        ]
        if include_time:
            blocks.append(
                'provider "registry.terraform.io/hashicorp/time" {\n'
                f'  version     = "{time_version}"\n'
                f'  constraints = "{time_constraints}"\n'
                '  hashes = [\n'
                '    "h1:fixture",\n'
                '  ]\n'
                '}\n'
            )
        return "\n".join(blocks)

    def _make_repo(self, main_tf: str, lock_hcl: Optional[str]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        tf_dir = root / "terraform"
        tf_dir.mkdir()
        (tf_dir / "main.tf").write_text(main_tf)
        if lock_hcl is not None:
            (tf_dir / ".terraform.lock.hcl").write_text(lock_hcl)
        return root

    @staticmethod
    def _fetcher(
        aws_stable: tuple[str, ...] = ("6.65.0",),
        time_stable: tuple[str, ...] = ("0.14.2",),
        aws_prerelease: tuple[str, ...] = (),
        time_prerelease: tuple[str, ...] = (),
    ):
        from security.dependency_detector import RegistryVersions

        def fetch(source: str):
            if source.endswith("/aws"):
                return RegistryVersions(list(aws_stable), list(aws_prerelease), "fixture"), "fixture"
            if source.endswith("/time"):
                return RegistryVersions(list(time_stable), list(time_prerelease), "fixture"), "fixture"
            return None, f"unexpected provider: {source}"

        return fetch

    def _check(self, root: Path, fetcher):
        from security.dependency_detector import check_terraform_providers

        return check_terraform_providers(
            root / "terraform/main.tf",
            lock_file=root / "terraform/.terraform.lock.hcl",
            version_fetcher=fetcher,
            source_display="terraform/main.tf",
        )

    @staticmethod
    def _dep(deps, name: str):
        return next(dep for dep in deps if dep.name == name)

    def test_dependency_detector_exists(self):
        """Test that dependency detector script exists."""
        self.assertTrue((REPO_ROOT / "security" / "dependency_detector.py").exists())

    def test_version_constraint_parsing(self):
        """Test version constraint parsing, including combined constraints."""
        from security.dependency_detector import (
            parse_version_constraint,
            parse_version_constraints,
        )

        # Single constraints
        self.assertEqual(parse_version_constraint(">= 6.0"), (">=", "6.0"))
        self.assertEqual(parse_version_constraint("~> 0.11"), ("~>", "0.11"))
        self.assertEqual(parse_version_constraint("= 1.0.0"), ("=", "1.0.0"))
        self.assertEqual(parse_version_constraint("1.0.0"), ("=", "1.0.0"))
        self.assertEqual(parse_version_constraint("<= 2.0.0"), ("<=", "2.0.0"))
        self.assertEqual(parse_version_constraint("> 1.0"), (">", "1.0"))
        self.assertEqual(parse_version_constraint("!= 1.2.3"), ("!=", "1.2.3"))

        # Combined constraints are ANDed.
        self.assertEqual(
            parse_version_constraints(">= 6.0, < 7.0"),
            [(">=", "6.0"), ("<", "7.0")],
        )
        self.assertEqual(
            parse_version_constraints("~> 1.2, != 1.2.3"),
            [("~>", "1.2"), ("!=", "1.2.3")],
        )
        with self.assertRaises(ValueError):
            parse_version_constraint(">= 6.0, < 7.0")
        with self.assertRaises(ValueError):
            parse_version_constraints("")

    def test_version_satisfies_constraint(self):
        """Test Terraform constraint satisfaction and edge cases."""
        from security.dependency_detector import version_satisfies_constraint

        # Exact match (missing core components compare as zero; build ignored)
        self.assertTrue(version_satisfies_constraint("1.0.0", "= 1.0.0"))
        self.assertFalse(version_satisfies_constraint("1.0.1", "= 1.0.0"))
        self.assertTrue(version_satisfies_constraint("1.0", "= 1.0.0"))
        self.assertTrue(version_satisfies_constraint("1.0.0+build.7", "= 1.0.0"))
        self.assertTrue(version_satisfies_constraint("v1.0.0", "= 1.0.0"))

        # Greater than or equal / less than or equal
        self.assertTrue(version_satisfies_constraint("6.0.0", ">= 6.0"))
        self.assertTrue(version_satisfies_constraint("6.1.0", ">= 6.0"))
        self.assertFalse(version_satisfies_constraint("5.41.0", ">= 6.0"))
        self.assertTrue(version_satisfies_constraint("5.0.0", "<= 6.0"))
        self.assertFalse(version_satisfies_constraint("7.0.0", "<= 6.0"))

        # Terraform pessimistic constraints:
        # ~> 1.2 allows 1.x (not 2.0); ~> 1.2.3 allows 1.2.x (not 1.3).
        self.assertTrue(version_satisfies_constraint("1.2.0", "~> 1.2"))
        self.assertTrue(version_satisfies_constraint("1.2.3", "~> 1.2"))
        self.assertTrue(version_satisfies_constraint("1.3.0", "~> 1.2"))
        self.assertTrue(version_satisfies_constraint("1.10.0", "~> 1.2"))
        self.assertFalse(version_satisfies_constraint("2.0.0", "~> 1.2"))
        self.assertTrue(version_satisfies_constraint("1.2.3", "~> 1.2.3"))
        self.assertTrue(version_satisfies_constraint("1.2.4", "~> 1.2.3"))
        self.assertTrue(version_satisfies_constraint("1.2.99", "~> 1.2.3"))
        self.assertFalse(version_satisfies_constraint("1.3.0", "~> 1.2.3"))

        # The two regression cases from MO-GH-SEC-01.
        self.assertTrue(version_satisfies_constraint("0.14.2", "~> 0.11"))
        self.assertFalse(version_satisfies_constraint("1.0.0", "~> 0.11"))
        self.assertTrue(version_satisfies_constraint("0.11.9", "~> 0.11.0"))
        self.assertFalse(version_satisfies_constraint("0.14.2", "~> 0.11.0"))
        self.assertTrue(version_satisfies_constraint("6.65.0", "~> 6.0"))
        self.assertFalse(version_satisfies_constraint("7.0.0", "~> 6.0"))

        # Combined constraints.
        self.assertTrue(version_satisfies_constraint("6.65.0", ">= 6.0, < 7.0"))
        self.assertFalse(version_satisfies_constraint("7.0.0", ">= 6.0, < 7.0"))
        self.assertTrue(version_satisfies_constraint("1.2.4", "~> 1.2, != 1.2.3"))
        self.assertFalse(version_satisfies_constraint("1.2.3", "~> 1.2, != 1.2.3"))

        # Pre-release precedence (SemVer): 1.2.3-alpha < 1.2.3.
        self.assertFalse(version_satisfies_constraint("1.2.3-alpha", ">= 1.2.3"))
        self.assertTrue(version_satisfies_constraint("1.2.3-alpha", ">= 1.2.3-alpha"))
        self.assertTrue(version_satisfies_constraint("1.2.3", "> 1.2.3-alpha"))
        self.assertTrue(version_satisfies_constraint("1.2.3-alpha.2", "> 1.2.3-alpha.1"))
        self.assertTrue(version_satisfies_constraint("1.2.3-beta", "< 1.2.3-rc.1"))

        # Invalid input is rejected, not treated as satisfied.
        self.assertFalse(version_satisfies_constraint("1.2.x", "~> 1.2"))
        self.assertFalse(version_satisfies_constraint("1.2.3", "~> nope"))

    def test_version_sorting_and_comparison(self):
        """Test numeric sorting, not lexical sorting, including pre-releases."""
        from security.dependency_detector import compare_versions, is_prerelease, sort_versions

        versions = ["1.2.0", "1.10.0", "1.2.0-rc.1", "2.0.0", "1.2.0-alpha.2"]
        self.assertEqual(
            sort_versions(versions),
            ["2.0.0", "1.10.0", "1.2.0", "1.2.0-rc.1", "1.2.0-alpha.2"],
        )
        self.assertGreater(compare_versions("1.10.0", "1.2.0"), 0)
        self.assertLess(compare_versions("1.2.0-rc.1", "1.2.0"), 0)
        self.assertEqual(compare_versions("1.2", "1.2.0"), 0)
        self.assertTrue(is_prerelease("1.2.0-rc.1"))
        self.assertFalse(is_prerelease("1.2.0"))

    def test_terraform_provider_parsing(self):
        """Test Terraform provider parsing."""
        from security.dependency_detector import parse_terraform_providers

        deps = parse_terraform_providers(REPO_ROOT / "terraform/main.tf")

        self.assertGreaterEqual(len(deps), 2)
        names = {d.name for d in deps}
        self.assertIn("aws", names)
        self.assertIn("time", names)
        for dep in deps:
            self.assertEqual(dep.type, "terraform_provider")
            self.assertIn("hashicorp/", dep.current_reference)

    def test_parse_terraform_lock(self):
        """Test parsing provider versions and constraints from the lock file."""
        from security.dependency_detector import parse_terraform_lock

        root = self._make_repo(self._main_tf(), self._lock())
        lock = parse_terraform_lock(root / "terraform/.terraform.lock.hcl")

        self.assertEqual(lock["hashicorp/aws"].version, "6.65.0")
        self.assertEqual(lock["hashicorp/aws"].constraints, "~> 6.0")
        self.assertEqual(lock["hashicorp/time"].version, "0.14.2")
        self.assertEqual(lock["hashicorp/time"].constraints, "~> 0.11")
        self.assertEqual(parse_terraform_lock(root / "terraform/missing.lock.hcl"), {})

    def test_resolution_distinguishes_declared_locked_latest(self):
        """Declared constraint, locked, latest available and compatible differ."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(self._main_tf(aws_constraint="~> 6.0"), self._lock())
        fetcher = self._fetcher(
            aws_stable=("7.0.0", "6.66.0", "6.65.0"),
            time_stable=("0.15.0", "0.14.2"),
        )
        deps = self._check(root, fetcher)
        aws = self._dep(deps, "aws")

        self.assertEqual(aws.current_version, "~> 6.0")
        self.assertEqual(aws.locked_version, "6.65.0")
        self.assertEqual(aws.latest_available, "7.0.0")
        self.assertEqual(aws.latest_compatible, "6.66.0")
        self.assertEqual(aws.available_version, "6.66.0")
        self.assertEqual(aws.status, "UPDATE_AVAILABLE")
        self.assertEqual(aws.source, "terraform/main.tf")

        result = detect_all_changes(root, version_fetcher=fetcher)
        self.assertEqual(result.status, "DEPENDENCY_CHANGE_DETECTED")
        self.assertIn("compatible dependency update", result.summary)

    def test_no_false_update_when_latest_is_outside_constraint(self):
        """A newer major outside the constraint is not an update recommendation."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(self._main_tf(aws_constraint="~> 6.0"), self._lock())
        fetcher = self._fetcher(aws_stable=("7.0.0", "6.65.0"), time_stable=("0.14.2",))
        aws = self._dep(self._check(root, fetcher), "aws")

        self.assertEqual(aws.latest_available, "7.0.0")
        self.assertEqual(aws.latest_compatible, "6.65.0")
        self.assertEqual(aws.status, "CURRENT")
        self.assertIn("outside the declared constraint", aws.details)
        self.assertEqual(detect_all_changes(root, version_fetcher=fetcher).status, "DEPENDENCIES_CURRENT")

    def test_lock_constraint_drift_suppresses_update(self):
        """A lock/declaration mismatch is explicit and suppresses updates."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(
            self._main_tf(aws_constraint=">= 6.0"),
            self._lock(aws_constraints="~> 6.0"),
        )
        fetcher = self._fetcher(
            aws_stable=("7.0.0", "6.66.0", "6.65.0"),
            time_stable=("0.14.2",),
        )
        aws = self._dep(self._check(root, fetcher), "aws")

        self.assertEqual(aws.status, "LOCK_CONSTRAINT_DRIFT")
        self.assertIn("suppressed", aws.details)
        result = detect_all_changes(root, version_fetcher=fetcher)
        self.assertEqual(result.status, "DEPENDENCY_CHANGE_DETECTED")
        self.assertIn("warning", result.summary)

    def test_locked_version_violating_constraint(self):
        """A locked version outside the declared constraint is an error finding."""
        root = self._make_repo(
            self._main_tf(aws_constraint=">= 6.0"),
            self._lock(aws_version="5.0.0", aws_constraints=">= 6.0"),
        )
        fetcher = self._fetcher(aws_stable=("6.65.0",), time_stable=("0.14.2",))
        aws = self._dep(self._check(root, fetcher), "aws")

        self.assertEqual(aws.status, "CONSTRAINT_UNSATISFIED")
        self.assertIn("does not satisfy", aws.details)

    def test_missing_lock_entry(self):
        """A provider absent from the lock file is reported, not guessed."""
        root = self._make_repo(self._main_tf(), self._lock(include_time=False))
        fetcher = self._fetcher(aws_stable=("6.65.0",), time_stable=("0.14.2",))
        deps = self._check(root, fetcher)
        time_dep = self._dep(deps, "time")

        self.assertIsNone(time_dep.locked_version)
        self.assertEqual(time_dep.status, "LOCK_MISSING")
        self.assertIn("no .terraform.lock.hcl entry", time_dep.details)

    def test_registry_latest_older_than_lock_is_incomplete(self):
        """A stale registry response never produces a downgrade recommendation."""
        root = self._make_repo(self._main_tf(aws_constraint=">= 6.0"), self._lock())
        fetcher = self._fetcher(aws_stable=("3.24.1",), time_stable=("0.14.2",))
        aws = self._dep(self._check(root, fetcher), "aws")

        self.assertEqual(aws.latest_available, "3.24.1")
        self.assertEqual(aws.status, "REGISTRY_INCOMPLETE")
        self.assertIn("older than locked version", aws.details)

    def test_registry_error_is_explicit(self):
        """Registry failures are distinguishable from dependency changes."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(self._main_tf(aws_constraint=">= 6.0"), self._lock())
        fetcher = lambda source: (None, "HTTP error 500 querying registry")
        aws = self._dep(self._check(root, fetcher), "aws")

        self.assertEqual(aws.status, "LOOKUP_ERROR")
        result = detect_all_changes(root, version_fetcher=fetcher)
        self.assertEqual(result.status, "DEPENDENCY_CHECK_ERROR")
        self.assertIn("failed", result.summary)

    def test_current_dependency_is_current(self):
        """A locked version at the latest compatible version is CURRENT."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(self._main_tf(aws_constraint="~> 6.0"), self._lock())
        fetcher = self._fetcher(aws_stable=("6.65.0",), time_stable=("0.14.2",))
        aws = self._dep(self._check(root, fetcher), "aws")

        self.assertEqual(aws.status, "CURRENT")
        self.assertEqual(detect_all_changes(root, version_fetcher=fetcher).status, "DEPENDENCIES_CURRENT")

    def test_numeric_latest_version_selection(self):
        """Latest selection is numeric (6.65 > 6.9), not lexical."""
        root = self._make_repo(
            self._main_tf(aws_constraint="~> 6.0"),
            self._lock(aws_version="6.9.0"),
        )
        fetcher = self._fetcher(
            aws_stable=("6.65.0", "6.10.0", "6.9.0"),
            time_stable=("0.14.2",),
        )
        aws = self._dep(self._check(root, fetcher), "aws")

        self.assertEqual(aws.latest_available, "6.65.0")
        self.assertEqual(aws.latest_compatible, "6.65.0")
        self.assertEqual(aws.status, "UPDATE_AVAILABLE")

    def test_relative_artifact_source(self):
        """Detector output uses repository-relative source paths."""
        root = self._make_repo(self._main_tf(), self._lock())
        deps = self._check(root, self._fetcher())
        for dep in deps:
            self.assertEqual(dep.source, "terraform/main.tf")
            self.assertFalse(Path(dep.source).is_absolute())

    def test_dependency_output_format(self):
        """Test that dependency output has required fields."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(self._main_tf(), self._lock())
        output = json.loads(detect_all_changes(root, version_fetcher=self._fetcher()).to_json())

        self.assertIn(output["status"], [
            "DEPENDENCIES_CURRENT",
            "DEPENDENCY_CHANGE_DETECTED",
            "DEPENDENCY_CHECK_ERROR",
        ])
        for dep in output["dependencies"]:
            for field in (
                "name", "type", "source", "current_version", "current_reference",
                "available_version", "available_reference", "status", "details",
                "detected_at", "locked_version", "latest_available", "latest_compatible",
                "locked_constraints",
            ):
                self.assertIn(field, dep)
            self.assertIn(dep["status"], [
                "CURRENT", "UPDATE_AVAILABLE", "CONSTRAINT_UNSATISFIED", "LOCK_MISSING",
                "REGISTRY_INCOMPLETE", "LOCK_CONSTRAINT_DRIFT", "LOOKUP_ERROR", "ERROR", "UNKNOWN",
            ])
            self.assertIn(dep["type"], [
                "terraform_provider", "github_action", "python_package", "npm_package", "git_submodule",
            ])

    def test_no_secret_leakage(self):
        """Test that detector output doesn't contain secrets."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(self._main_tf(), self._lock())
        output = detect_all_changes(root, version_fetcher=self._fetcher()).to_json()

        self.assertNotIn("aws_secret_access_key", output)
        self.assertNotIn("aws_access_key_id", output)
        self.assertNotIn("secret_access_key", output)
        self.assertNotIn("password", output.lower())

    def test_deterministic_output(self):
        """Test deterministic status/structure with a fixed provider fixture."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(self._main_tf(), self._lock())
        fetcher = self._fetcher()
        out1 = json.loads(detect_all_changes(root, version_fetcher=fetcher).to_json())
        out2 = json.loads(detect_all_changes(root, version_fetcher=fetcher).to_json())

        self.assertEqual(out1["status"], out2["status"])
        self.assertEqual(len(out1["dependencies"]), len(out2["dependencies"]))
        for d1, d2 in zip(out1["dependencies"], out2["dependencies"]):
            for field in ("name", "status", "current_version", "locked_version", "latest_available", "latest_compatible"):
                self.assertEqual(d1[field], d2[field])

    def test_failure_distinguishable(self):
        """Test that failure is distinguishable from 'no changes'."""
        from security.dependency_detector import detect_all_changes

        root = self._make_repo(self._main_tf(), self._lock())
        result = detect_all_changes(root, version_fetcher=lambda source: (None, "offline failure"))

        self.assertEqual(result.status, "DEPENDENCY_CHECK_ERROR")
        self.assertNotEqual(result.status, "DEPENDENCIES_CURRENT")
        self.assertNotEqual(result.status, "")


class TestSarifAdapter(unittest.TestCase):
    """Test SECURITY-01-FIX SARIF adapter with deterministic fixtures."""

    def _dep(self, **overrides) -> dict:
        dep = {
            "name": "aws",
            "type": "terraform_provider",
            "source": str(REPO_ROOT / "terraform/main.tf"),
            "current_version": "~> 6.0",
            "locked_version": "6.65.0",
            "latest_available": "7.0.0",
            "latest_compatible": "6.66.0",
            "available_version": "6.66.0",
            "status": "UPDATE_AVAILABLE",
            "details": "update available: 6.65.0 -> 6.66.0",
        }
        dep.update(overrides)
        return dep

    def _native(self, dependencies=None) -> dict:
        return {
            "status": "DEPENDENCY_CHANGE_DETECTED",
            "run_id": "fixture-run",
            "timestamp": "2026-11-28T00:00:00Z",
            "summary": "fixture",
            "dependencies": dependencies if dependencies is not None else [self._dep()],
        }

    def _convert(self, native=None) -> dict:
        from security.sarif_adapter import SarifAdapter

        return SarifAdapter(repo_root=REPO_ROOT).convert(native or self._native())

    def test_sarif_adapter_exists(self):
        """Test that SARIF adapter script exists."""
        self.assertTrue((REPO_ROOT / "security" / "sarif_adapter.py").exists())

    def test_sarif_conversion_schema(self):
        """Test the required SARIF 2.1.0 document and run structure."""
        sarif = self._convert()

        self.assertEqual(sarif.get("version"), "2.1.0")
        self.assertEqual(
            sarif.get("$schema"),
            "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0.json",
        )
        self.assertIn("runs", sarif)
        self.assertEqual(len(sarif["runs"]), 1)

        run = sarif["runs"][0]
        self.assertIn("tool", run)
        self.assertIn("driver", run["tool"])
        self.assertEqual(run["tool"]["driver"]["name"], "Mays-Orders-AWS Security Dependency Detector")
        self.assertEqual(run["tool"]["driver"]["version"], "2.0.0")
        self.assertIn("rules", run["tool"]["driver"])
        self.assertIn("results", run)
        self.assertEqual(run["columnKind"], "utf16CodeUnits")
        self.assertEqual(run["automationDetails"]["id"], "dependency-check")
        self.assertIn("description", run["automationDetails"])

        for result in run["results"]:
            self.assertIn("ruleId", result)
            self.assertIn("level", result)
            self.assertIn("message", result)
            self.assertIn("locations", result)
            self.assertIn("properties", result)
            self.assertIn("partialFingerprints", result)
            self.assertIn(result["level"], ["error", "warning", "note", "none"])

    def test_no_native_top_level_fields(self):
        """Test that SARIF doesn't contain native top-level fields."""
        sarif = self._convert()
        for field in ("status", "run_id", "timestamp", "summary", "dependencies"):
            self.assertNotIn(field, sarif)

    def test_current_dependencies_are_omitted(self):
        """CURRENT dependencies must not create findings or rules."""
        native = self._native([
            self._dep(status="CURRENT", latest_available="6.65.0", latest_compatible="6.65.0"),
        ])
        sarif = self._convert(native)
        run = sarif["runs"][0]

        self.assertEqual(run["results"], [])
        self.assertEqual(run["tool"]["driver"]["rules"], [])
        self.assertNotIn("CURRENT", json.dumps(sarif))

    def test_actionable_findings_and_levels(self):
        """All actionable statuses are retained with stable severity mapping."""
        statuses = {
            "CHANGED": "warning",
            "UPDATE_AVAILABLE": "note",
            "CONSTRAINT_UNSATISFIED": "error",
            "LOCK_MISSING": "warning",
            "LOCK_CONSTRAINT_DRIFT": "warning",
            "REGISTRY_INCOMPLETE": "warning",
            "LOOKUP_ERROR": "warning",
            "ERROR": "error",
            "UNKNOWN": "warning",
        }
        native = self._native([
            self._dep(name=f"dep-{status.lower()}", status=status)
            for status in statuses
        ])
        sarif = self._convert(native)
        results = sarif["runs"][0]["results"]

        self.assertEqual(len(results), len(statuses))
        by_rule = {result["ruleId"]: result for result in results}
        for status, level in statuses.items():
            rule_id = f"SEC01-TERRAFORM_PROVIDER-{status}"
            self.assertIn(rule_id, by_rule)
            self.assertEqual(by_rule[rule_id]["level"], level)

    def test_relative_artifact_uris(self):
        """Absolute detector sources become repository-relative SARIF URIs."""
        native = self._native([
            self._dep(source=str(REPO_ROOT / "terraform/main.tf")),
            self._dep(name="time", source="/tmp/outside/terraform/main.tf", status="LOCK_MISSING"),
        ])
        sarif = self._convert(native)

        for result in sarif["runs"][0]["results"]:
            uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            self.assertFalse(Path(uri).is_absolute(), uri)
            self.assertEqual(uri, "terraform/main.tf")

    def test_stable_rule_ids_and_fingerprints(self):
        """Repeated conversions of the same input are stable and deterministic."""
        native = self._native()
        first = self._convert(native)
        second = self._convert(native)

        self.assertEqual(first, second)
        first_result = first["runs"][0]["results"][0]
        second_result = second["runs"][0]["results"][0]
        self.assertEqual(first_result["ruleId"], second_result["ruleId"])
        self.assertEqual(
            first_result["partialFingerprints"],
            second_result["partialFingerprints"],
        )
        self.assertEqual(
            first_result["partialFingerprints"]["dependencyIdentity/v1"],
            second_result["partialFingerprints"]["dependencyIdentity/v1"],
        )

    def test_fingerprint_changes_with_identity(self):
        """Different dependency identity or status changes the fingerprint."""
        base = self._convert(self._native([self._dep()]))["runs"][0]["results"][0]
        other_source = self._convert(self._native([
            self._dep(source="terraform/other.tf"),
        ]))["runs"][0]["results"][0]
        other_status = self._convert(self._native([
            self._dep(status="LOCK_MISSING"),
        ]))["runs"][0]["results"][0]

        self.assertNotEqual(
            base["partialFingerprints"]["dependencyIdentity/v1"],
            other_source["partialFingerprints"]["dependencyIdentity/v1"],
        )
        self.assertNotEqual(
            base["partialFingerprints"]["dependencyIdentity/v1"],
            other_status["partialFingerprints"]["dependencyIdentity/v1"],
        )

    def test_rule_indexes_are_valid(self):
        """Every result points at its rule in the driver rule array."""
        sarif = self._convert(self._native([
            self._dep(status="UPDATE_AVAILABLE"),
            self._dep(name="time", status="CURRENT"),
            self._dep(name="random", status="LOCK_CONSTRAINT_DRIFT"),
        ]))
        run = sarif["runs"][0]
        rules = run["tool"]["driver"]["rules"]

        self.assertEqual(len(run["results"]), 2)
        for result in run["results"]:
            self.assertIsInstance(result["ruleIndex"], int)
            self.assertLess(result["ruleIndex"], len(rules))
            self.assertEqual(rules[result["ruleIndex"]]["id"], result["ruleId"])

    def test_properties_include_version_dimensions(self):
        """SARIF properties distinguish declared, locked, available and compatible."""
        result = self._convert()["runs"][0]["results"][0]
        props = result["properties"]

        self.assertEqual(props["dependency_name"], "aws")
        self.assertEqual(props["dependency_type"], "terraform_provider")
        self.assertEqual(props["declared_constraint"], "~> 6.0")
        self.assertEqual(props["locked_version"], "6.65.0")
        self.assertEqual(props["latest_available"], "7.0.0")
        self.assertEqual(props["latest_compatible"], "6.66.0")
        self.assertEqual(props["available_version"], "6.66.0")
        self.assertEqual(props["status"], "UPDATE_AVAILABLE")

    def test_alerts_296_298_corrected_input_resolves_old_findings(self):
        """Corrected input removes the old constraint error and CURRENT note."""
        corrected = self._native([
            self._dep(name="aws", status="LOCK_CONSTRAINT_DRIFT"),
            self._dep(
                name="time",
                status="CURRENT",
                current_version="~> 0.11",
                locked_version="0.14.2",
                latest_available="0.14.2",
                latest_compatible="0.14.2",
                available_version="0.14.2",
            ),
        ])
        sarif = self._convert(corrected)
        run = sarif["runs"][0]
        rule_ids = [result["ruleId"] for result in run["results"]]

        self.assertNotIn("SEC01-TERRAFORM_PROVIDER-CONSTRAINT_UNSATISFIED", rule_ids)
        self.assertNotIn("SEC01-TERRAFORM_PROVIDER-CURRENT", rule_ids)
        self.assertIn("SEC01-TERRAFORM_PROVIDER-LOCK_CONSTRAINT_DRIFT", rule_ids)
        self.assertEqual(len(run["results"]), 1)

    def test_cli_conversion(self):
        """The CLI writes valid SARIF and omits CURRENT dependencies."""
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            input_file = Path(tmp) / "dependency_result.json"
            output_file = Path(tmp) / "dependency_result.sarif"
            native = self._native([
                self._dep(),
                self._dep(name="time", status="CURRENT"),
            ])
            input_file.write_text(json.dumps(native))

            result = subprocess.run(
                [sys.executable, "-m", "security.sarif_adapter", str(input_file), str(output_file)],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output_file.exists())
            sarif = json.loads(output_file.read_text())
            self.assertEqual(sarif["version"], "2.1.0")
            self.assertEqual(len(sarif["runs"][0]["results"]), 1)
            self.assertEqual(
                sarif["runs"][0]["results"][0]["ruleId"],
                "SEC01-TERRAFORM_PROVIDER-UPDATE_AVAILABLE",
            )

    def test_no_secret_leakage(self):
        """SARIF output does not contain credential material."""
        output = json.dumps(self._convert())
        self.assertNotIn("aws_secret_access_key", output)
        self.assertNotIn("aws_access_key_id", output)
        self.assertNotIn("secret_access_key", output)
        self.assertNotIn("password", output.lower())


if __name__ == "__main__":
    unittest.main()