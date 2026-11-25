"""MO-RIS-UPDATER-03B: actual generated module contract + atomic legacy adoption.

Copy to module_builder/tests/test_ris_updater_03b.py in the MO repo.
Run from the repository root: python -m unittest module_builder.tests.test_ris_updater_03b
"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from module_builder.builder import build_module
from module_builder.cli import main as cli_main

REPO = Path(__file__).resolve().parents[2]
OUTPUT_NAMES = ('results_queue_url', 'results_queue_arn', 'result_hmac_secret_arn')
MANDATORY_ENV = ('ORDERS_TABLE', 'SQS_QUEUE_URL', 'ORDERS_PROJECT_NAME',
                 'ORDERS_COGNITO_ISSUER', 'ORDERS_COGNITO_CLIENT_ID')


class TestGeneratedOrdersServiceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='mo-ris-updater-03b-')
        cls.generated = Path(cls.tmp.name) / 'generated'
        build_module(target_dir=cls.generated, project_name='mo-03b-test',
                     source_root=REPO, force=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_real_lambda_environment_merge(self):
        parent = (self.generated / 'main.tf').read_text(encoding='utf8')
        parent_var = (self.generated / 'variables.tf').read_text(encoding='utf8')
        child = (self.generated / 'modules/lambda/main.tf').read_text(encoding='utf8')
        child_var = (self.generated / 'modules/lambda/variables.tf').read_text(encoding='utf8')
        self.assertRegex(parent, r'additional_environment\s*=\s*var\.additional_environment')
        self.assertRegex(child, r'variables\s*=\s*merge\(\s*\{[\s\S]*?\},\s*var\.additional_environment\s*\)')
        self.assertEqual(child.count('var.additional_environment'), 1)
        for key in MANDATORY_ENV:
            self.assertRegex(child, r'\b' + key + r'\s*=')
        for text in (parent_var, child_var):
            self.assertIn('variable "additional_environment"', text)
            self.assertRegex(text, r'default\s*=\s*\{\}')
            for reserved in ('AWS_', 'ORDERS_', 'PRIVACY_', 'COGNITO_',
                             'ORDER_RESULT_', 'SQS_QUEUE_URL'):
                self.assertIn(reserved, text)

    def test_output_references_once_each(self):
        text = (self.generated / 'outputs.tf').read_text(encoding='utf8')
        for name in OUTPUT_NAMES:
            self.assertEqual(len(re.findall(r'output\s+"' + name + r'"\s*\{', text)), 1)
            self.assertIn(f'try(module.agent_transport[0].{name}, "")', text)
        self.assertNotRegex(text, r'(?m)^resource\s+')

    def test_legacy_adoption_deviation_writes_no_manifest(self):
        legacy = Path(self.tmp.name) / 'legacy'
        shutil.copytree(self.generated, legacy)
        manifest_file = legacy / 'module-builder.manifest.json'
        data = json.loads(manifest_file.read_text(encoding='utf8'))
        data.pop('manifest_version', None)
        data.pop('files', None)
        manifest_file.write_text(json.dumps(data, indent=2) + '\n', encoding='utf8')
        (legacy / 'main.tf').write_text((legacy / 'main.tf').read_text() + '\n# edit\n')
        before = manifest_file.read_bytes()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli_main(['upgrade', '--project', str(legacy), '--source',
                             str(REPO), '--adopt-legacy', '--apply'])
        self.assertNotEqual(code, 0, buf.getvalue())
        self.assertIn('BLOCKED', buf.getvalue())
        self.assertEqual(manifest_file.read_bytes(), before)


    @unittest.skipUnless(shutil.which('terraform'), 'Terraform CLI not installed')
    def test_reserved_keys_with_offline_terraform_plan(self):
        """Validate actual generated variable; no provider and no AWS access."""
        child = (self.generated / 'modules/lambda/variables.tf').read_text(encoding='utf8')
        block = child[child.index('variable "additional_environment" {'):]
        offline = Path(self.tmp.name) / 'offline-terraform'
        offline.mkdir(exist_ok=True)
        (offline / 'main.tf').write_text(block + "\n" + (
            'output "environment" {\n'
            '  value = merge({\n'
            '    ORDERS_TABLE = "table"\n'
            '    SQS_QUEUE_URL = "queue"\n'
            '    ORDERS_PROJECT_NAME = "project"\n'
            '    ORDERS_COGNITO_ISSUER = "issuer"\n'
            '    ORDERS_COGNITO_CLIENT_ID = "client"\n'
            '  }, var.additional_environment)\n'
            '}\n'), encoding='utf8')
        # Isolate the offline run from any inherited backend/data-dir state.
        import os
        env = dict(os.environ)
        env['TF_DATA_DIR'] = str(offline / '.tfdata')
        init = subprocess.run(['terraform', 'init', '-backend=false', '-input=false',
                               '-no-color'], cwd=offline, text=True,
                              capture_output=True, env=env)
        self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
        def plan(param=None):
            cmd = ['terraform', 'plan', '-input=false', '-no-color', '-refresh=false']
            if param is not None:
                cmd.extend(['-var', 'additional_environment={' + param + '}'])
            return subprocess.run(cmd, cwd=offline, text=True,
                                  capture_output=True, env=env)
        default = plan()
        self.assertEqual(default.returncode, 0, default.stdout + default.stderr)
        self.assertIn('ORDERS_COGNITO_ISSUER', default.stdout)
        allowed = plan('ORDER_DISPATCH_QUEUE_URL="dispatch"')
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        self.assertIn('ORDER_DISPATCH_QUEUE_URL', allowed.stdout)
        for key in ('ORDERS_TABLE', 'ORDERS_COGNITO_ISSUER', 'SQS_QUEUE_URL',
                    'AWS_REGION', 'PRIVACY_INTERNAL_SECRET', 'ORDER_RESULT_SECRET_ARN'):
            with self.subTest(reserved_key=key):
                result = plan(key + '="invalid"')
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('additional_environment keys', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
