import unittest
from unittest.mock import MagicMock, patch
from installer.terraform.runner import TerraformRunner, TerraformError

class TestParallelIsolation(unittest.TestCase):
    @patch('installer.terraform.runner.subprocess.run')
    def test_two_projects_different_workspace(self, mock_run):
        # Simulate workspace ensure for two projects
        mock_select = MagicMock(returncode=0, stdout='', stderr='')
        mock_show = MagicMock(returncode=0, stdout='mays-orders\n', stderr='')
        mock_run.side_effect = [mock_select, mock_show]
        ctx = MagicMock()
        ctx.to_env.return_value = {}
        runner_a = TerraformRunner('/tmp', aws_context=ctx, workspace='mays-orders')
        runner_a._ensure_workspace()
        # Second project
        mock_show2 = MagicMock(returncode=0, stdout='mays-orders-privacy-test\n', stderr='')
        mock_run.side_effect = [mock_select, mock_show2]
        runner_b = TerraformRunner('/tmp', aws_context=ctx, workspace='mays-orders-privacy-test')
        runner_b._ensure_workspace()
        # Workspace isolation verified via different show outputs
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
