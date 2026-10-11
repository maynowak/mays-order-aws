import os
import unittest
from unittest.mock import patch

from installer.core.aws_context import (
    AWSProfileValidator,
    AWSExecutionContext,
    AWSValidationError,
    find_static_credentials,
    validate_aws_context,
)


def _fake_context(profile="mayaws", account_id="240571105849"):
    return AWSExecutionContext(
        profile=profile,
        region="eu-central-1",
        account_id=account_id,
        identity_arn=f"arn:aws:iam::{account_id}:user/Mayaws",
        validated=True,
        profile_source="explicit",
    )


class TestAWSProfileContextLive(unittest.TestCase):
    """Live check against the real mayaws profile (requires AWS credentials)."""

    def test_profile_mayaws_identity(self):
        ctx = validate_aws_context(profile="mayaws", region="eu-central-1")
        self.assertEqual(ctx.profile, "mayaws")
        self.assertEqual(ctx.account_id, "240571105849")
        self.assertTrue(ctx.identity_arn.startswith("arn:aws:iam::240571105849:"))


class TestAWSProfileContextUnit(unittest.TestCase):
    """Mock-based regression tests: no AWS calls."""

    def test_to_env_consistency(self):
        ctx = _fake_context()
        env = ctx.to_env()
        self.assertEqual(env.get("AWS_PROFILE"), "mayaws")
        self.assertEqual(env.get("AWS_REGION"), "eu-central-1")
        self.assertEqual(env.get("AWS_DEFAULT_REGION"), "eu-central-1")

    def test_no_global_mutation(self):
        before = dict(os.environ)
        ctx = _fake_context()
        _ = ctx.to_env()
        _ = ctx.get_environment()
        self.assertEqual(dict(os.environ), before)

    def test_profile_switch_changes_env(self):
        ctx_a = _fake_context(profile="mayaws")
        ctx_b = _fake_context(profile="other-profile")
        self.assertNotEqual(ctx_a.get_environment()["AWS_PROFILE"], ctx_b.get_environment()["AWS_PROFILE"])

    def test_conflicting_static_credentials_stop(self):
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "AKIAFAKE", "AWS_SECRET_ACCESS_KEY": "fake"}):
            self.assertIn("AWS_ACCESS_KEY_ID", find_static_credentials())
            validator = AWSProfileValidator("mayaws", "eu-central-1")
            with self.assertRaises(AWSValidationError) as cm:
                validator.validate()
            self.assertIn("Conflicting", str(cm.exception))

    def test_subprocess_env_strips_static_creds_for_profile(self):
        ctx = _fake_context(profile="mayaws")
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "AKIAFAKE", "AWS_SECRET_ACCESS_KEY": "fake"}):
            env = ctx.get_environment()
            self.assertNotIn("AWS_ACCESS_KEY_ID", env)
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
            self.assertEqual(env["AWS_PROFILE"], "mayaws")

    def test_subprocess_env_keeps_creds_without_profile(self):
        ctx = _fake_context(profile=None, account_id="240571105849")
        ctx.profile_source = "iam_role"
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "AKIAFAKE"}):
            env = ctx.get_environment()
            # IAM-role / env mode must keep static creds
            self.assertEqual(env.get("AWS_ACCESS_KEY_ID"), "AKIAFAKE")
            self.assertNotIn("AWS_PROFILE", env)

    def test_account_id_mismatch_fails_closed(self):
        with patch.object(
            AWSProfileValidator, "_validate_with_profile",
            return_value=_fake_context(account_id="240571105849"),
        ):
            with self.assertRaises(AWSValidationError):
                validate_aws_context(
                    profile="mayaws",
                    region="eu-central-1",
                    expected_account_id="999999999999",
                )

    def test_runner_env_explicit_no_global_mutation(self):
        from installer.terraform.runner import TerraformRunner

        before = dict(os.environ)
        ctx = _fake_context()
        runner = TerraformRunner("/tmp", aws_context=ctx, workspace="mays-orders-privacy-test")
        env = runner._get_terraform_env()
        self.assertEqual(env["AWS_PROFILE"], "mayaws")
        self.assertEqual(runner.workspace, "mays-orders-privacy-test")
        self.assertEqual(dict(os.environ), before)

    def test_context_post_init_no_global_mutation(self):
        from installer.core.context import InstallationContext

        before = dict(os.environ)
        # Ensure TERRAFORM_WORKSPACE from outer env does not leak into assertions
        os.environ.pop("TERRAFORM_WORKSPACE", None)
        before.pop("TERRAFORM_WORKSPACE", None)
        ctx = InstallationContext(project_name="mays-orders-privacy-test")
        self.assertEqual(ctx.terraform_workspace, "mays-orders-privacy-test")
        self.assertNotIn("TERRAFORM_WORKSPACE", os.environ)
        self.assertEqual(dict(os.environ), before)


if __name__ == "__main__":
    unittest.main()
