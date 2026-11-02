"""MO-RC4-TERRAFORM-TIMEOUT-FIX-01: operation-specific Terraform timeouts.

Rein lokal: subprocess wird gemockt, es laufen keine Terraform-/AWS-Aufrufe.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from installer.terraform.runner import (
    APPLY_TIMEOUT_ENV_VAR,
    DEFAULT_APPLY_TIMEOUT_SECONDS,
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    TerraformRunner,
    resolve_apply_timeout,
)

MODULE_SUBPROCESS = "installer.terraform.runner.subprocess.run"


def _aws_context() -> MagicMock:
    ctx = MagicMock()
    ctx.validated = True
    ctx.get_environment.return_value = {}
    ctx.profile = "mayaws"
    ctx.region = "eu-central-1"
    return ctx


class TimeoutTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.plan = Path(self._tmp.name) / "deploy.tfplan"
        self.plan.write_bytes(b"plan")
        self._env = patch.dict(os.environ, {}, clear=False)
        self._env.start()
        self.addCleanup(self._env.stop)
        os.environ.pop(APPLY_TIMEOUT_ENV_VAR, None)

    def _runner(self) -> TerraformRunner:
        return TerraformRunner("/tmp", aws_context=_aws_context(), workspace="mays-orders-rc4")

    def _call(self, operation: str):
        with patch(MODULE_SUBPROCESS) as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner = self._runner()
            with patch.object(runner, "_ensure_workspace"):
                if operation == "apply":
                    result = runner.apply(str(self.plan))
                elif operation == "destroy":
                    result = runner.destroy(str(self.plan))
                elif operation == "plan":
                    result = runner.plan(out_file=str(self.plan))
                elif operation == "state":
                    result = runner.state_list()
                else:  # pragma: no cover - defensive
                    raise AssertionError(operation)
        return result, mock_run


class TestDefaultTimeouts(TimeoutTestCase):
    def test_apply_defaults_to_900(self):
        result, mock_run = self._call("apply")
        self.assertTrue(result.success)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 900)
        self.assertEqual(DEFAULT_APPLY_TIMEOUT_SECONDS, 900)

    def test_destroy_defaults_to_900(self):
        result, mock_run = self._call("destroy")
        self.assertTrue(result.success)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 900)

    def test_plan_keeps_180(self):
        result, mock_run = self._call("plan")
        self.assertTrue(result.success)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 180)
        self.assertEqual(DEFAULT_COMMAND_TIMEOUT_SECONDS, 180)

    def test_state_keeps_180(self):
        result, mock_run = self._call("state")
        self.assertTrue(result.success)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 180)


class TestTimeoutOverride(TimeoutTestCase):
    def test_apply_uses_valid_override(self):
        os.environ[APPLY_TIMEOUT_ENV_VAR] = "1234"
        result, mock_run = self._call("apply")
        self.assertTrue(result.success)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 1234)

    def test_destroy_uses_valid_override(self):
        os.environ[APPLY_TIMEOUT_ENV_VAR] = "1234"
        result, mock_run = self._call("destroy")
        self.assertTrue(result.success)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 1234)

    def test_plan_ignores_apply_override(self):
        os.environ[APPLY_TIMEOUT_ENV_VAR] = "1234"
        result, mock_run = self._call("plan")
        self.assertTrue(result.success)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 180)

    def test_valid_override_one_second(self):
        os.environ[APPLY_TIMEOUT_ENV_VAR] = "1"
        self.assertEqual(resolve_apply_timeout(), 1)


class TestInvalidOverride(TimeoutTestCase):
    def test_invalid_values_raise(self):
        for raw in ("abc", "0", "-5", "1.5", ""):
            with self.subTest(raw=raw):
                os.environ[APPLY_TIMEOUT_ENV_VAR] = raw
                if raw == "":
                    self.assertEqual(resolve_apply_timeout(), 900)
                else:
                    with self.assertRaises(Exception) as ctx:
                        resolve_apply_timeout()
                    self.assertIn(APPLY_TIMEOUT_ENV_VAR, str(ctx.exception))

    def test_invalid_override_fails_apply_without_execution(self):
        os.environ[APPLY_TIMEOUT_ENV_VAR] = "not-a-number"
        with patch(MODULE_SUBPROCESS) as mock_run:
            runner = self._runner()
            result = runner.apply(str(self.plan))
        self.assertFalse(result.success)
        self.assertIn(APPLY_TIMEOUT_ENV_VAR, result.stderr)
        mock_run.assert_not_called()

    def test_invalid_override_fails_destroy_without_execution(self):
        os.environ[APPLY_TIMEOUT_ENV_VAR] = "0"
        with patch(MODULE_SUBPROCESS) as mock_run:
            runner = self._runner()
            result = runner.destroy(str(self.plan))
        self.assertFalse(result.success)
        self.assertIn(APPLY_TIMEOUT_ENV_VAR, result.stderr)
        mock_run.assert_not_called()


class TestTimeoutProcessHandling(TimeoutTestCase):
    def test_timeout_is_reported_as_failure(self):
        with patch(MODULE_SUBPROCESS) as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["terraform", "apply"], timeout=900
            )
            runner = self._runner()
            with patch.object(runner, "_ensure_workspace"):
                result = runner.apply(str(self.plan))
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, -1)
        self.assertIn("timed out after 900s", result.stderr)

    def test_timeout_does_not_retry(self):
        with patch(MODULE_SUBPROCESS) as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["terraform", "apply"], timeout=900
            )
            runner = self._runner()
            with patch.object(runner, "_ensure_workspace"):
                runner.apply(str(self.plan))
        self.assertEqual(mock_run.call_count, 1)

    def test_timeout_uses_override_value_in_message(self):
        os.environ[APPLY_TIMEOUT_ENV_VAR] = "55"
        with patch(MODULE_SUBPROCESS) as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["terraform", "apply"], timeout=55
            )
            runner = self._runner()
            with patch.object(runner, "_ensure_workspace"):
                result = runner.apply(str(self.plan))
        self.assertIn("timed out after 55s", result.stderr)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 55)

    def test_timeout_returns_without_raising(self):
        """Kein unbehandelter Fehler, kein Hintergrund-Retry, deterministischer Status."""
        with patch(MODULE_SUBPROCESS) as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["terraform", "apply"], timeout=900
            )
            runner = self._runner()
            with patch.object(runner, "_ensure_workspace"):
                result = runner.apply(str(self.plan))
        self.assertIsNotNone(result)
        self.assertEqual(result.command[:2], ["terraform", "apply"])


if __name__ == "__main__":
    unittest.main()
