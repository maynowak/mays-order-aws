import unittest
from unittest.mock import MagicMock, patch
import sys
sys.path.insert(0, '/home/dci-student/projects/Mays-Orders-AWS')
from installer.terraform.runner import TerraformRunner, TerraformError

class TestWorkspaceSafety(unittest.TestCase):
    @patch('installer.terraform.runner.subprocess.run')
    def test_workspace_select_success(self, mock_run):
        # select succeeds, show returns workspace
        mock_select = MagicMock(returncode=0, stdout='', stderr='')
        mock_show = MagicMock(returncode=0, stdout='myproj\n', stderr='')
        mock_run.side_effect = [mock_select, mock_show]
        ctx = MagicMock()
        ctx.to_env.return_value = {}
        runner = TerraformRunner('/tmp', aws_context=ctx, workspace='myproj')
        runner._ensure_workspace()
        self.assertEqual(mock_run.call_count, 2)

    @patch('installer.terraform.runner.subprocess.run')
    def test_workspace_missing_creates(self, mock_run):
        mock_select = MagicMock(returncode=1, stdout='', stderr="doesn't exist")
        mock_create = MagicMock(returncode=0, stdout='', stderr='')
        mock_show = MagicMock(returncode=0, stdout='myproj\n', stderr='')
        mock_run.side_effect = [mock_select, mock_create, mock_show]
        ctx = MagicMock()
        ctx.to_env.return_value = {}
        runner = TerraformRunner('/tmp', aws_context=ctx, workspace='myproj')
        runner._ensure_workspace()
        self.assertEqual(mock_run.call_count, 3)

    @patch('installer.terraform.runner.subprocess.run')
    def test_workspace_select_failure_raises(self, mock_run):
        mock_select = MagicMock(returncode=1, stdout='', stderr='some error')
        mock_run.return_value = mock_select
        ctx = MagicMock()
        ctx.to_env.return_value = {}
        runner = TerraformRunner('/tmp', aws_context=ctx, workspace='myproj')
        with self.assertRaises(TerraformError):
            runner._ensure_workspace()

if __name__ == '__main__':
    unittest.main()


class TestWorkspaceFailClosed(unittest.TestCase):
    """MO-RC4-P02I-E1B: kein stiller Fallback auf den "default"-Workspace."""

    def _ctx(self):
        ctx = MagicMock()
        ctx.to_env.return_value = {}
        ctx.validated = True
        return ctx

    def test_default_workspace_rejected_for_project_isolated_runner(self):
        with self.assertRaises(ValueError):
            TerraformRunner(
                '/tmp', aws_context=self._ctx(), workspace='default',
                require_explicit_workspace=True,
            )

    def test_empty_workspace_rejected(self):
        with self.assertRaises(ValueError):
            TerraformRunner('/tmp', aws_context=self._ctx(), workspace='  ')

    def test_project_workspace_accepted(self):
        runner = TerraformRunner(
            '/tmp', aws_context=self._ctx(), workspace='mays-orders-rc4',
            require_explicit_workspace=True,
        )
        self.assertEqual(runner.workspace, 'mays-orders-rc4')

    def test_context_derives_workspace_from_project_name(self):
        from installer.core.context import InstallationContext
        ctx = InstallationContext(project_name='mays-orders-rc4')
        self.assertEqual(ctx.terraform_workspace, 'mays-orders-rc4')

    def test_context_never_keeps_default_workspace(self):
        from installer.core.context import InstallationContext
        ctx = InstallationContext(project_name='mays-orders-rc4',
                                  terraform_workspace='default')
        self.assertEqual(ctx.terraform_workspace, 'mays-orders-rc4')

    def test_context_rejects_blank_project_name(self):
        from installer.core.context import InstallationContext
        with self.assertRaises(ValueError):
            InstallationContext(project_name='   ')

    def test_cli_runner_enforces_explicit_workspace(self):
        from installer.cli.main import InstallerCLI
        ctx = MagicMock()
        ctx.terraform_dir = '/tmp'
        ctx.aws_execution_context = MagicMock(validated=True)
        ctx.terraform_workspace = 'default'
        with self.assertRaises(ValueError):
            InstallerCLI._make_runner(ctx)

        ctx.terraform_workspace = 'mays-orders-rc4'
        runner = InstallerCLI._make_runner(ctx)
        self.assertEqual(runner.workspace, 'mays-orders-rc4')
        self.assertTrue(runner.require_explicit_workspace)
