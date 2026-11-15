import unittest
from unittest.mock import MagicMock, patch
from installer.terraform.runner import TerraformRunner, TerraformError

class TestParallelIsolation(unittest.TestCase):
    @patch('installer.terraform.runner.subprocess.run')
    def test_two_projects_different_workspace(self, mock_run):
        """Each runner must select and verify only its own explicit workspace."""
        mock_select = MagicMock(returncode=0, stdout='', stderr='')
        mock_show_a = MagicMock(returncode=0, stdout='mays-orders\n', stderr='')
        mock_show_b = MagicMock(returncode=0, stdout='mays-orders-privacy-test\n', stderr='')
        ctx = MagicMock()
        ctx.get_environment.return_value = {}

        runner_a = TerraformRunner(
            '/tmp', aws_context=ctx, workspace='mays-orders', require_explicit_workspace=True
        )
        runner_b = TerraformRunner(
            '/tmp', aws_context=ctx, workspace='mays-orders-privacy-test',
            require_explicit_workspace=True
        )

        mock_run.side_effect = [mock_select, mock_show_a, mock_select, mock_show_b]
        runner_a._ensure_workspace()
        runner_b._ensure_workspace()

        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertEqual(
            commands,
            [
                ['terraform', 'workspace', 'select', 'mays-orders'],
                ['terraform', 'workspace', 'show'],
                ['terraform', 'workspace', 'select', 'mays-orders-privacy-test'],
                ['terraform', 'workspace', 'show'],
            ],
        )
        self.assertNotIn('default', [arg for cmd in commands for arg in cmd])

        # The fail-closed constructor must reject default/empty workspaces.
        with self.assertRaises(ValueError):
            TerraformRunner(
                '/tmp', aws_context=ctx, workspace='default', require_explicit_workspace=True
            )
        with self.assertRaises(ValueError):
            TerraformRunner(
                '/tmp', aws_context=ctx, workspace='', require_explicit_workspace=True
            )

        # A workspace-show mismatch is an error, not a silent fallback.
        mismatch_runner = TerraformRunner(
            '/tmp', aws_context=ctx, workspace='project-c', require_explicit_workspace=True
        )
        mock_run.side_effect = [
            mock_select,
            MagicMock(returncode=0, stdout='project-a\n', stderr=''),
        ]
        with self.assertRaises(TerraformError):
            mismatch_runner._ensure_workspace()

if __name__ == '__main__':
    unittest.main()
