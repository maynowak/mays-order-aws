"""MO-RC4-TESTSUITE-HARDENING-10E-A — Installer safety gates.

These tests execute the actual approval-context, workspace-boundary and
fail-closed functions. No Terraform process, AWS client or network is used.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from installer.core.approval import (
    ApprovalContext,
    ApprovalGate,
    create_approval_context,
    verify_approval_context,
)
from installer.core.deployment_identity import (
    DeploymentContext,
    DeploymentId,
    DevelopmentPhase,
    DevelopmentState,
    PlanOperation,
    SemanticVersion,
)
from installer.core.fail_closed import (
    FailClosedConfig,
    FailClosedError,
    FailClosedGuard,
    FailClosedPolicy,
    FailClosedValidator,
    DeploymentMismatchError,
    LockFailureError,
    PlanIntegrityError,
    UncertainStateError,
    UnknownAWSStateError,
    ValidationFailedError,
    create_fail_closed_config,
    fail_closed,
    fail_closed_context,
    fail_closed_scope,
    lenient_fail_closed,
    strict_fail_closed,
)
from installer.core.workspace import (
    WorkspaceError,
    WorkspaceIntegrity,
    create_workspace_integrity,
    validate_workspace_path,
)


def _valid_approval_context() -> ApprovalContext:
    return ApprovalContext(
        deployment_id="123456789012:mays-orders:test",
        operation="deploy",
        plan_file="deploy.tfplan",
        run_id="run-1",
    )


class TestApprovalContext(unittest.TestCase):
    def test_valid_context_has_no_issues(self):
        valid, issues = verify_approval_context(_valid_approval_context())
        self.assertTrue(valid)
        self.assertEqual(issues, [])

    def test_missing_deployment_id_is_rejected(self):
        context = _valid_approval_context()
        context.deployment_id = ""
        valid, issues = verify_approval_context(context)
        self.assertFalse(valid)
        self.assertIn("Missing deployment_id", issues)

    def test_missing_plan_file_is_rejected(self):
        context = _valid_approval_context()
        context.plan_file = ""
        valid, issues = verify_approval_context(context)
        self.assertFalse(valid)
        self.assertIn("Missing plan_file", issues)

    def test_missing_run_id_is_rejected(self):
        context = _valid_approval_context()
        context.run_id = ""
        valid, issues = verify_approval_context(context)
        self.assertFalse(valid)
        self.assertIn("Missing run_id", issues)

    def test_invalid_operation_is_rejected(self):
        for operation in ("Deploy", "dry-run", "", "APPLY"):
            with self.subTest(operation=operation):
                context = _valid_approval_context()
                context.operation = operation
                valid, issues = verify_approval_context(context)
                self.assertFalse(valid)
                self.assertTrue(any("Invalid operation" in issue for issue in issues))

    def test_skip_approval_without_auto_approve_is_rejected(self):
        with self.assertRaises(ValueError):
            ApprovalContext(
                deployment_id="123456789012:mays-orders:test",
                operation="destroy",
                plan_file="destroy.tfplan",
                run_id="run-2",
                auto_approve=False,
                skip_approval=True,
            )

    def test_skip_approval_with_auto_approve_is_accepted(self):
        context = ApprovalContext(
            deployment_id="123456789012:mays-orders:test",
            operation="destroy",
            plan_file="destroy.tfplan",
            run_id="run-2",
            auto_approve=True,
            skip_approval=True,
        )
        valid, issues = verify_approval_context(context)
        self.assertTrue(valid)
        self.assertEqual(issues, [])

    def test_create_context_uses_operation_and_auto_approval(self):
        context = create_approval_context(
            deployment_id="123456789012:mays-orders:test",
            operation="destroy",
            plan_file="destroy.tfplan",
            run_id="run-3",
            auto_approve=True,
        )
        self.assertEqual(context.operation, "destroy")
        self.assertTrue(context.auto_approve)

    def test_operation_is_not_bound_to_plan_or_workspace(self):
        """Characterizes a current contract gap; no binding logic is invented."""
        context = _valid_approval_context()
        context.plan_file = "another-project-destroy.tfplan"
        context.operation = "deploy"
        valid, issues = verify_approval_context(context)
        self.assertTrue(valid)
        self.assertEqual(issues, [])

    def test_approval_gate_can_be_constructed_and_evaluated(self):
        context = _valid_approval_context()
        context.auto_approve = True
        gate = ApprovalGate(context)
        proceed, failed = gate.evaluate(SimpleNamespace())
        self.assertTrue(proceed)
        self.assertEqual(failed, [])

    def test_approval_gate_denies_interactive_no(self):
        context = _valid_approval_context()
        gate = ApprovalGate(context)
        with mock.patch("builtins.input", return_value="n") as prompt:
            proceed, failed = gate.evaluate(SimpleNamespace())
        self.assertFalse(proceed)
        self.assertEqual(failed, ["User declined approval"])
        prompt.assert_called_once()


class TestWorkspaceIsolation(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / "workspace"
        self.outside = Path(self.tempdir.name) / "outside"
        self.outside.mkdir()
        self.integrity = WorkspaceIntegrity(self.root)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_path_inside_workspace_is_accepted(self):
        target = self.root / "runs" / "run-1" / "context.json"
        self.assertEqual(self.integrity.validate_path(target), target.resolve())

    def test_path_outside_workspace_is_rejected(self):
        target = self.outside / "foreign.json"
        with self.assertRaises(WorkspaceError):
            self.integrity.validate_path(target)

    def test_relative_traversal_is_rejected(self):
        with self.assertRaises(WorkspaceError):
            self.integrity.validate_relative_path("../outside/foreign.json", base=self.root)

    def test_relative_path_inside_workspace_is_accepted(self):
        target = self.integrity.validate_relative_path("runs/run-1/plan.tfplan", base=self.root)
        self.assertTrue(target.is_relative_to(self.root.resolve()))

    def test_is_within_workspace_returns_false_for_outside_path(self):
        self.assertFalse(self.integrity.is_within_workspace(self.outside / "foreign.json"))

    def test_symlink_escape_is_rejected(self):
        link = self.root / "escape"
        os.symlink(self.outside, link)
        with self.assertRaises(WorkspaceError):
            self.integrity.validate_path(link / "foreign.json")

    def test_allowed_paths_are_explicit_and_scoped(self):
        allowed = self.integrity.get_allowed_paths()
        self.assertEqual(set(allowed), {"workspace_root", "runs", "terraform"})
        self.assertEqual(allowed["workspace_root"], self.root.resolve())

    def test_ensure_within_workspace_reports_description(self):
        with self.assertRaises(WorkspaceError) as raised:
            self.integrity.ensure_within_workspace(
                self.outside / "foreign.json", description="order backup"
            )
        self.assertIn("order backup access", str(raised.exception))

    def test_factory_uses_explicit_workspace_root(self):
        integrity = create_workspace_integrity(
            workspace_root=Path(self.tempdir.name) / "factory-root"
        )
        self.assertEqual(
            integrity.get_allowed_paths()["workspace_root"],
            (Path(self.tempdir.name) / "factory-root").resolve(),
        )

    def test_convenience_helper_enforces_supplied_workspace_root(self):
        foreign = self.outside / "foreign.json"
        with self.assertRaises(WorkspaceError):
            validate_workspace_path(
                foreign,
                workspace_root=Path(self.tempdir.name) / "unrelated-root",
            )

    def test_convenience_helper_accepts_path_inside_supplied_root(self):
        target = self.root / "allowed.json"
        self.assertEqual(
            validate_workspace_path(target, workspace_root=self.root),
            target.resolve(),
        )


class TestFailClosedGuard(unittest.TestCase):
    def test_validation_failure_is_denied(self):
        guard = FailClosedGuard()
        with self.assertRaises(ValidationFailedError):
            guard.require_valid(False)

    def test_valid_condition_passes(self):
        guard = FailClosedGuard()
        self.assertIsNone(guard.require_valid(True))

    def test_unknown_state_is_denied(self):
        guard = FailClosedGuard()
        with self.assertRaises(UncertainStateError):
            guard.require_known_state(None)

    def test_known_state_is_returned(self):
        guard = FailClosedGuard()
        value = object()
        self.assertIs(guard.require_known_state(value), value)

    def test_deployment_mismatch_is_denied(self):
        guard = FailClosedGuard()
        actual = DeploymentId("123456789012", "mays-orders", "test")
        expected = DeploymentId("123456789012", "mays-orders", "prod")
        with self.assertRaises(DeploymentMismatchError):
            guard.require_deployment_match(actual, expected)

    def test_matching_deployment_passes(self):
        guard = FailClosedGuard()
        actual = DeploymentId("123456789012", "mays-orders", "test")
        guard.require_deployment_match(actual, actual)

    def test_missing_lock_is_denied(self):
        guard = FailClosedGuard()
        with self.assertRaises(LockFailureError):
            guard.require_lock(False)

    def test_acquired_lock_passes(self):
        guard = FailClosedGuard()
        guard.require_lock(True)

    def test_unknown_aws_state_is_denied(self):
        guard = FailClosedGuard()
        with self.assertRaises(UnknownAWSStateError):
            guard.require_aws_state(None)

    def test_matching_plan_and_fingerprint_pass(self):
        guard = FailClosedGuard()
        deployment_id = DeploymentId("123456789012", "mays-orders", "test")
        plan = SimpleNamespace(
            deployment_id=deployment_id,
            operation=PlanOperation.DEPLOY,
            version=SemanticVersion(0, 2, 0),
            plan_sha256="a" * 64,
        )
        expected = SimpleNamespace(
            deployment_id=deployment_id,
            operation=PlanOperation.DEPLOY,
            version=SemanticVersion(0, 2, 0),
            plan_sha256="a" * 64,
        )
        guard.require_plan_match(plan, expected)

    def test_plan_mismatch_and_missing_fingerprint_are_denied(self):
        guard = FailClosedGuard()
        deployment_id = DeploymentId("123456789012", "mays-orders", "test")
        plan = SimpleNamespace(
            deployment_id=deployment_id,
            operation=PlanOperation.DEPLOY,
            version=SemanticVersion(0, 2, 0),
            plan_sha256="a" * 64,
        )
        mismatched = SimpleNamespace(
            deployment_id=DeploymentId("123456789012", "mays-orders", "prod"),
            operation=PlanOperation.DEPLOY,
            version=SemanticVersion(0, 2, 0),
            plan_sha256="a" * 64,
        )
        with self.assertRaises(PlanIntegrityError):
            guard.require_plan_match(plan, mismatched)

        missing_fingerprint = SimpleNamespace(
            deployment_id=deployment_id,
            operation=PlanOperation.DEPLOY,
            version=SemanticVersion(0, 2, 0),
        )
        with self.assertRaises(PlanIntegrityError):
            guard.require_plan_match(plan, missing_fingerprint)

    def test_lenient_policy_does_not_raise_on_validation(self):
        guard = FailClosedGuard(lenient_fail_closed())
        guard.require_valid(False)
        self.assertFalse(lenient_fail_closed().fail_on_validation_error)

    def test_strict_policy_enables_all_failure_switches(self):
        config = strict_fail_closed()
        self.assertEqual(config.policy, FailClosedPolicy.STRICT)
        self.assertTrue(config.fail_on_validation_error)
        self.assertTrue(config.fail_on_unknown_state)
        self.assertTrue(config.treat_timeout_as_failure)

    def test_create_config_rejects_unknown_policy(self):
        with self.assertRaises(ValueError):
            create_fail_closed_config("unknown")

    def test_create_config_applies_known_override(self):
        config = create_fail_closed_config("standard", fail_on_lock_failure=False)
        self.assertFalse(config.fail_on_lock_failure)


class TestFailClosedErrors(unittest.TestCase):
    def test_fail_closed_decorator_wraps_unexpected_exception(self):
        @fail_closed()
        def explode():
            raise RuntimeError("unexpected")

        with self.assertRaises(FailClosedError):
            explode()

    def test_fail_closed_decorator_preserves_successful_result(self):
        @fail_closed()
        def succeed():
            return "ok"

        self.assertEqual(succeed(), "ok")

    def test_fail_closed_context_wraps_unexpected_exception(self):
        with self.assertRaises(FailClosedError):
            with fail_closed_context():
                raise ValueError("unexpected")

    def test_fail_closed_scope_wraps_unexpected_exception(self):
        with self.assertRaises(FailClosedError):
            with fail_closed_scope():
                raise ValueError("unexpected")

    def test_aws_validator_rejects_unvalidated_context(self):
        validator = FailClosedValidator()
        context = SimpleNamespace(validated=False)
        with self.assertRaises(UnknownAWSStateError):
            validator.validate_aws_context(context)

    def test_aws_validator_rejects_missing_account(self):
        validator = FailClosedValidator()
        context = SimpleNamespace(
            validated=True,
            account_id="",
            region="eu-central-1",
            identity_arn="arn:aws:iam::123456789012:user/test",
        )
        with self.assertRaises(ValidationFailedError):
            validator.validate_aws_context(context)

    def test_aws_validator_accepts_complete_context(self):
        validator = FailClosedValidator()
        context = SimpleNamespace(
            validated=True,
            account_id="123456789012",
            region="eu-central-1",
            identity_arn="arn:aws:iam::123456789012:user/test",
        )
        validator.validate_aws_context(context)

    def test_plan_integrity_validator_accepts_matching_context(self):
        validator = FailClosedValidator()
        deployment_id = DeploymentId("123456789012", "mays-orders", "test")
        plan = SimpleNamespace(
            deployment_id=deployment_id,
            operation=PlanOperation.DEPLOY,
            version=SemanticVersion(0, 2, 0),
            plan_sha256="b" * 64,
        )
        expected = SimpleNamespace(
            deployment_id=deployment_id,
            operation=PlanOperation.DEPLOY,
            version=SemanticVersion(0, 2, 0),
            plan_sha256="b" * 64,
        )
        validator.validate_plan_integrity(plan, expected)

    def test_plan_integrity_validator_rejects_mismatch_and_missing_data(self):
        validator = FailClosedValidator()
        deployment_id = DeploymentId("123456789012", "mays-orders", "test")
        plan = SimpleNamespace(
            deployment_id=deployment_id,
            operation=PlanOperation.DEPLOY,
            version=SemanticVersion(0, 2, 0),
            plan_sha256="b" * 64,
        )
        with self.assertRaises(DeploymentMismatchError):
            validator.validate_plan_integrity(
                plan,
                SimpleNamespace(
                    deployment_id=DeploymentId(
                        "123456789012", "mays-orders", "prod"
                    ),
                    operation=PlanOperation.DEPLOY,
                    version=SemanticVersion(0, 2, 0),
                    plan_sha256="b" * 64,
                ),
            )
        with self.assertRaises(ValidationFailedError):
            validator.validate_plan_integrity(plan, SimpleNamespace())

    def test_deployment_context_validator_accepts_complete_context(self):
        validator = FailClosedValidator()
        version = SemanticVersion(0, 2, 0)
        context = DeploymentContext(
            deployment_id=DeploymentId("123456789012", "mays-orders", "test"),
            version=version,
            development_state=DevelopmentState(
                version=version,
                phase=DevelopmentPhase("H2"),
            ),
        )
        validator.validate_deployment_context(context)

    def test_deployment_context_validator_rejects_invalid_identity(self):
        validator = FailClosedValidator()
        version = SemanticVersion(0, 2, 0)
        incomplete = SimpleNamespace(
            deployment_id=None,
            version=version,
            development_state=DevelopmentState(
                version=version,
                phase=DevelopmentPhase("H2"),
            ),
            allow_aws_operations=False,
        )
        with self.assertRaises(DeploymentMismatchError):
            validator.validate_deployment_context(incomplete)


if __name__ == "__main__":
    unittest.main()
