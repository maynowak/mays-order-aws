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
