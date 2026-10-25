"""Unit-Tests für den Module Builder (MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01).

Reine Python-Tests — kein terraform, kein AWS. Quelle ist das echte Repo
(read-only); Ziele liegen in temporären Verzeichnissen.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from module_builder import __version__
from module_builder.builder import (
    build,
    substitute_project_name,
    validate_project_name,
    _extract_terraform_block,
)
from module_builder.cli import main
from module_builder.catalog import MODULE_CATALOG
from module_builder.spec import PRESETS

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPreflightFailClosed(unittest.TestCase):
    """Fail-closed-Verhalten: Fehler NACHDEM irgendetwas geschrieben wurde, ist verboten."""

    def _build(self, **kwargs):
        args = dict(
            target_dir=kwargs.get("target"),
            project_name=kwargs.get("project_name", "my-orders"),
            preset_name=kwargs.get("preset", "complete"),
            source_root=kwargs.get("source", REPO_ROOT),
            force=kwargs.get("force", False),
        )
        return build(**args)

    def test_unknown_preset_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                self._build(target=Path(tmp) / "out", preset="does-not-exist")
            self.assertIn("complete", str(ctx.exception))

    def test_invalid_project_names_rejected(self):
        # Spiegelt die Terraform-Regex `^[a-z0-9][a-z0-9-]*$` exakt:
        # führender Bindestrich/Unterstrich/Punkt/Großbuchstaben → reject;
        # "ab-" ist laut Quell-Regex zulässig (bekannte Terraform-Quirk,
        # deren Fehlertext mehr behauptet als die Regex erzwingt).
        for bad in ("AB", "ab", "a", "-ab", "ab_cd", "ab.cd"):
            with self.assertRaises(SystemExit, msg=bad):
                validate_project_name(bad)

    def test_valid_project_names_accepted(self):
        for good in ("my-orders", "ris-mo", "abc123", "a9-b", "ab-"):
            validate_project_name(good)  # no exception

    def test_missing_artifact_fails_closed_without_writing(self):
        """Quelle ohne lambda.zip → Fehler, Zielordner bleibt UNANGETASTET."""
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as out:
            src_root = Path(src)
            # Minimalbaum: terraform/main.tf vorhanden, Artefakt FEHLT absichtlich
            (src_root / "terraform").mkdir()
            (src_root / "terraform" / "main.tf").write_text('terraform {\n}\n')
            target = Path(out) / "generated"
            with self.assertRaises(SystemExit) as ctx:
                self._build(target=target, source=src_root)
            msg = str(ctx.exception)
            self.assertIn("fail-closed", msg)
            self.assertIn("lambda/dist/lambda.zip", msg)
            self.assertIn("build_zip.py", msg)  # Lösungshinweis enthalten
            # NICHTS geschrieben:
            self.assertFalse(target.exists() or any(target.iterdir()) if target.exists() else False)

    def test_nonempty_target_refused_without_force(self):
        with tempfile.TemporaryDirectory() as out:
            target = Path(out) / "generated"
            target.mkdir()
            (target / "foreign.txt").write_text("keep me")
            with self.assertRaises(SystemExit) as ctx:
                self._build(target=target)
            self.assertIn("--force", str(ctx.exception))
            self.assertEqual((target / "foreign.txt").read_text(), "keep me")

    def test_force_keeps_foreign_files(self):
        with tempfile.TemporaryDirectory() as out:
            target = Path(out) / "generated"
            self._build(target=target)
            (target / "foreign.txt").write_text("keep me")
            self._build(target=target, force=True)  # kein Fehler
            self.assertEqual((target / "foreign.txt").read_text(), "keep me")
            self.assertTrue((target / "terraform" / "main.tf").is_file())


class TestGeneratedProject(unittest.TestCase):
    """Vollständiger Build gegen das echte Repo-Quellverzeichnis."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls._tmp.name) / "my-orders"
        cls.result = build(
            target_dir=cls.target,
            project_name="my-orders",
            preset_name="complete",
            source_root=REPO_ROOT,
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _tree(self) -> set:
        return {str(p.relative_to(self.target)) for p in self.target.rglob("*") if p.is_file()}

    def test_expected_layout(self):
        tree = self._tree()
        for expected in [
            "terraform/main.tf", "terraform/variables.tf", "terraform/outputs.tf",
            "terraform/versions.tf", "terraform/terraform.tfvars.example",
            "terraform/README.md",
            "lambda/dist/lambda.zip", "lambda/dist/cognito_backup.zip",
            "lambda/build_zip.py", "scripts/seed_orders.py",
            "database/seed/orders_seed_demo_50.json",
            "README.md", "module-builder.manifest.json",
            # F1 (HARDENING-01): Cognito-Backup-Quelle + Build-Skript im Ziel
            "lambda/cognito_backup_handler.py",
            "lambda/build_cognito_backup_zip.py",
            "cognito_backup/__init__.py", "cognito_backup/backup.py",
        ]:
            self.assertIn(expected, tree, f"Fehlt: {expected}")
        for module in PRESETS["complete"]["modules"]:
            mod_files = [f for f in tree if f.startswith(f"terraform/modules/{module}/")]
            self.assertTrue(mod_files and all(f.endswith(".tf") for f in mod_files),
                            f"Modul {module} ohne .tf-Dateien")
        # Package-Tests gehören NICHT ins generierte Projekt (Artefakt-Konvention)
        self.assertNotIn("cognito_backup/tests/test_manifest.py", tree)

    def test_cognito_backup_artifact_reproducible_in_target(self):
        """F1-Kern: Das generierte Projekt kann das Cognito-Backup-Artefakt
        selbst deterministisch neu bauen — gleicher sha256 wie das Quell-Repo."""
        import hashlib
        import subprocess
        script = self.target / "lambda" / "build_cognito_backup_zip.py"
        result = subprocess.run(
            ["python3", str(script)], cwd=self.target / "lambda",
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        target_zip = self.target / "lambda" / "dist" / "cognito_backup.zip"
        source_zip = REPO_ROOT / "lambda" / "dist" / "cognito_backup.zip"
        self.assertEqual(
            hashlib.sha256(target_zip.read_bytes()).hexdigest(),
            hashlib.sha256(source_zip.read_bytes()).hexdigest(),
            "Rebuild im generierten Projekt weicht vom Quell-Artefakt ab.",
        )

    # ---------- F2 (HARDENING-01): Policy-Gate im generierten Projekt ----------

    def _run_gate(self, plan: dict):
        import subprocess
        import tempfile
        gate = self.target / "terraform" / "policy" / "validate-plan.py"
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, dir="/tmp/opencode"
        ) as fh:
            json.dump(plan, fh)
            plan_path = fh.name
        result = subprocess.run(
            ["python3", str(gate), plan_path],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode, result.stdout + result.stderr

    @staticmethod
    def _plan(region: str = "eu-central-1", resource_type: str = "aws_dynamodb_table",
              tags: dict | None = None, billing_mode: str = "PAY_PER_REQUEST") -> dict:
        tags = tags if tags is not None else {
            "Project": "my-orders",
            "Maker": "Maymilly Nowak",
            "Environment": "Development",
        }
        return {
            "format_version": "1.2",
            "terraform_version": "1.16.1",
            "resource_changes": [
                {
                    "address": f"{resource_type}.orders",
                    "type": resource_type,
                    "name": "orders",
                    "change": {
                        "actions": ["create"],
                        "after": {
                            "name": "my-orders",
                            "billing_mode": billing_mode,
                            "tags_all": tags,
                        },
                    },
                }
            ],
            "configuration": {
                "provider_config": {
                    "aws": {"expressions": {"region": {"constant_value": region}}}
                }
            },
        }

    def test_policy_files_present_in_target(self):
        tree = self._tree()
        self.assertIn("terraform/policy/validate-plan.py", tree)
        self.assertIn("terraform/policy/resource-policy.json", tree)

    def test_policy_project_substituted(self):
        policy = json.loads(
            (self.target / "terraform" / "policy" / "resource-policy.json").read_text()
        )
        self.assertEqual(policy["project"], "my-orders")
        # Kern-Regeln bleiben erhalten (keine stille Aufweichung):
        self.assertIn("eu-central-*", policy["region"]["allowed_patterns"])
        self.assertEqual(policy["required_tags"], ["Project", "Maker", "Environment"])
        self.assertFalse(policy["environment"]["production"]["allowed"])

    def test_policy_gate_positive(self):
        """Positivtest: valider Plan gegen das GENERIERTE Gate → Exit 0."""
        code, output = self._run_gate(self._plan())
        self.assertEqual(code, 0, f"Gate hätte PASS sein müssen: {output}")

    def test_policy_gate_negative_region(self):
        """Negativtest: verbotene Region → Exit 1 (FAIL, nicht umgangen)."""
        code, output = self._run_gate(self._plan(region="us-east-1"))
        self.assertEqual(code, 1)
        self.assertIn("region", output.lower())

    def test_policy_gate_negative_resource_type(self):
        """Negativtest: nicht erlaubter Ressourcentyp → Exit 1."""
        code, output = self._run_gate(
            self._plan(resource_type="aws_redshift_cluster")
        )
        self.assertEqual(code, 1)
        self.assertIn("not allowed", output)

    def test_policy_gate_negative_missing_tag(self):
        """Negativtest: Pflicht-Tag fehlt → Exit 1."""
        code, output = self._run_gate(
            self._plan(tags={"Project": "my-orders", "Environment": "Development"})
        )
        self.assertEqual(code, 1)

    def test_versions_tf_contains_terraform_block(self):
        versions = (self.target / "terraform" / "versions.tf").read_text()
        main_tf = (self.target / "terraform" / "main.tf").read_text()
        self.assertIn("required_providers", versions)
        self.assertIn('source  = "hashicorp/aws"', versions)
        self.assertNotIn("required_providers", main_tf)
        self.assertIn('provider "aws"', main_tf)
        self.assertIn('module "dynamodb"', main_tf)

    def test_project_name_default_substituted(self):
        variables = (self.target / "terraform" / "variables.tf").read_text()
        self.assertIn('default     = "my-orders"', variables)
        # Terraform-Validierung des Namens bleibt erhalten:
        self.assertIn("variable \"project_name\"", variables)

    def test_no_backend_and_no_state_plan_artifacts(self):
        tree = self._tree()
        for forbidden in [f for f in tree if re.search(
                r"backend\.tf$|\.tfstate|\.tfplan|(^|/)tfplan|\.terraform|lock\.hcl", f)]:
            self.fail(f"Verbotene Datei im generierten Projekt: {forbidden}")

    def test_no_original_repo_dependency_in_terraform(self):
        for tf_file in self.target.rglob("*.tf"):
            text = tf_file.read_text()
            self.assertNotIn("git::", text, f"git::-Quelle in {tf_file}")
            self.assertNotIn("mays-order-aws", text, f"Repo-Referenz in {tf_file}")
        # Modul-Quellen bleiben relativ:
        main_tf = (self.target / "terraform" / "main.tf").read_text()
        self.assertIn('source       = "./modules/dynamodb"', main_tf)

    def test_lambda_artifact_hashes_match_source(self):
        import hashlib
        src_zip = REPO_ROOT / "lambda" / "dist" / "lambda.zip"
        digest = hashlib.sha256(src_zip.read_bytes()).hexdigest()
        self.assertEqual(self.result.artifacts["lambda/dist/lambda.zip"], digest)

    def test_manifest_content(self):
        manifest = json.loads((self.target / "module-builder.manifest.json").read_text())
        self.assertEqual(manifest["preset"], "complete")
        self.assertEqual(manifest["project_name"], "my-orders")
        self.assertEqual(manifest["source"]["repo"], "maynowak/mays-order-aws")
        self.assertIn("BLOCKED", manifest["notes"]["privacy_production_activation"])
        self.assertIn("lambda/dist/lambda.zip", manifest["artifacts_sha256"])
        self.assertIn("terraform/main.tf", manifest["files_written"])

    def test_readme_mentions_privacy_blocked_and_backend(self):
        readme = (self.target / "README.md").read_text()
        self.assertIn("my-orders", readme)
        self.assertIn("BLOCKED", readme)
        self.assertIn("Backend", readme)
        self.assertIn("terraform init -backend=false", readme)

    def test_rebuild_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            second = build(
                target_dir=Path(tmp) / "my-orders",
                project_name="my-orders",
                source_root=REPO_ROOT,
            )
            def tree_files(root: Path) -> dict:
                return {
                    str(p.relative_to(root)): p.read_bytes()
                    for p in root.rglob("*")
                    if p.is_file() and p.name != "module-builder.manifest.json"
                }
            self.assertEqual(tree_files(self.target), tree_files(second.target))


class TestTransformations(unittest.TestCase):

    def test_extract_terraform_block(self):
        block, rest = _extract_terraform_block(
            'terraform {\n  required_version = ">= 1.5.0"\n}\n\nprovider "aws" {\n}\n'
        )
        self.assertIn("required_version", block)
        self.assertTrue(block.startswith("terraform {"))
        self.assertTrue(block.rstrip().endswith("}"))
        self.assertTrue(rest.startswith('provider "aws"'))
        self.assertNotIn("required_version", rest)

    def test_extract_unclosed_block_fails(self):
        with self.assertRaises(SystemExit):
            _extract_terraform_block('terraform {\n  x = 1\n')

    def test_substitute_project_name(self):
        source = (
            'variable "project_name" {\n  type    = string\n'
            '  default = "mays-orders"\n}\n\nvariable "other" {\n'
            '  default = "mays-orders"\n}\n'
        )
        result = substitute_project_name(source, "ris-mo")
        self.assertIn('"ris-mo"', result)
        # Nur das ERSTE Vorkommen (project_name-Block) wird ersetzt:
        self.assertEqual(result.count('default = "mays-orders"'), 1)

    def test_substitute_fails_when_pattern_missing(self):
        with self.assertRaises(SystemExit):
            substitute_project_name('# nothing here\n', "x")


class TestCli(unittest.TestCase):

    def _run(self, argv):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(argv)
        return code, stdout.getvalue()

    def test_presets_command(self):
        code, out = self._run(["presets"])
        self.assertEqual(code, 0)
        self.assertIn("complete", out)

    def test_build_requires_target_and_project_name(self):
        with self.assertRaises(SystemExit) as ctx:
            self._run(["build"])
        self.assertEqual(ctx.exception.code, 2)  # argparse: fehlende Pflichtargumente

    def test_build_complete_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "cli-orders"
            code, out = self._run([
                "build", "--target", str(target),
                "--project-name", "cli-orders", "--preset", "complete",
            ])
            self.assertEqual(code, 0)
            self.assertIn("Build OK", out)
            self.assertTrue((target / "terraform" / "main.tf").is_file())

    def test_unknown_preset_via_cli_lists_choices(self):
        with self.assertRaises(SystemExit) as ctx:
            self._run(["build", "--target", "/tmp/x", "--project-name", "abc",
                       "--preset", "nope"])
        self.assertEqual(ctx.exception.code, 2)


class TestModuleSelectionB1(unittest.TestCase):
    """B1: freie Modulauswahl — Fail-closed-Validierung + auswahlgetriebene Generierung."""

    def _build(self, target: Path, modules, project_name="sel-test"):
        return build(
            target_dir=target,
            project_name=project_name,
            preset_name="complete",
            source_root=REPO_ROOT,
            modules=modules,
        )

    def _names(self, root: Path, pattern: str) -> set:
        import re as _re
        text = (root / "terraform" / "main.tf").read_text()
        return set(_re.findall(pattern, text))

    def test_single_module_dynamodb(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "db-only"
            self._build(target, ["dynamodb"])
            tree = {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()}
            self.assertIn("terraform/modules/dynamodb/main.tf", tree)
            self.assertEqual(len([f for f in tree if f.startswith("terraform/modules/")]), 3)
            # Keine Lambda-/Backup-Ressourcen ohne Bedarf:
            self.assertNotIn("lambda/dist/lambda.zip", tree)
            self.assertNotIn("lambda/dist/cognito_backup.zip", tree)
            self.assertNotIn("cognito_backup/backup.py", tree)
            # Policy-Gate bleibt immer dabei:
            self.assertIn("terraform/policy/validate-plan.py", tree)
            # Seed gehört zu dynamodb:
            self.assertIn("scripts/seed_orders.py", tree)
            main_modules = self._names(target, r'module\s+"([a-z_]+)"')
            self.assertEqual(main_modules, {"dynamodb"})
            vars_kept = set(re.findall(r'^variable\s+"([a-z_]+)"',
                (target / "terraform" / "variables.tf").read_text(), re.M))
            self.assertEqual(vars_kept, {"project_name", "aws_region", "tags",
                                         "seed_example_data", "seed_file_path"})
            outs = set(re.findall(r'^output\s+"([a-z_]+)"',
                (target / "terraform" / "outputs.tf").read_text(), re.M))
            self.assertEqual(outs, {"dynamodb_table_name", "dynamodb_table_arn"})

    def test_valid_combination_lambda_chain(self):
        """dynamodb,sqs,iam,lambda — gültige Kette mit Lambda-Artefakt, ohne Backup-Zip."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lambda-chain"
            self._build(target, ["dynamodb", "sqs", "iam", "lambda"])
            tree = {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()}
            self.assertIn("lambda/dist/lambda.zip", tree)
            self.assertIn("lambda/build_zip.py", tree)
            self.assertNotIn("lambda/dist/cognito_backup.zip", tree)
            self.assertNotIn("cognito_backup/backup.py", tree)
            main_modules = self._names(target, r'module\s+"([a-z_]+)"')
            self.assertEqual(main_modules, {"dynamodb", "sqs", "iam", "lambda"})
            vars_kept = set(re.findall(r'^variable\s+"([a-z_]+)"',
                (target / "terraform" / "variables.tf").read_text(), re.M))
            self.assertIn("monitoring_enabled", vars_kept)   # lambda braucht sie
            self.assertIn("log_retention_days", vars_kept)
            self.assertNotIn("api_5xx_threshold", vars_kept)  # kein monitoring
            self.assertNotIn("notification_email", vars_kept)
            outs = set(re.findall(r'^output\s+"([a-z_]+)"',
                (target / "terraform" / "outputs.tf").read_text(), re.M))
            self.assertEqual(outs, {
                "dynamodb_table_name", "dynamodb_table_arn",
                "iam_handler_role_name", "iam_handler_role_arn",
                "lambda_function_name", "lambda_function_arn", "lambda_invoke_arn",
                # Neu seit MODULE-CONTRACT-01: Queue-Outputs referenzieren module.sqs
                # (in dieser Auswahl enthalten) und werden mitgefiltert:
                "sqs_queue_url", "sqs_queue_arn", "sqs_queue_name",
            })

    def test_missing_dependencies_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                self._build(Path(tmp) / "x", ["lambda"])
            msg = str(ctx.exception)
            for needed in ("dynamodb", "iam", "B2"):
                self.assertIn(needed, msg)
            # PHASE2: sqs ist KEINE Pflicht-Dep von lambda mehr — darf nicht als
            # fehlend gemeldet werden:
            self.assertNotIn("'lambda' benötigt: dynamodb, iam, sqs", msg)

    def test_transitive_dependency_reported(self):
        """iam ohne dynamodb → fehlend: dynamodb (vollständige Diagnose je Modul)."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                self._build(Path(tmp) / "x", ["sqs", "iam"])
            self.assertIn("'iam'", str(ctx.exception))
            self.assertIn("dynamodb", str(ctx.exception))

    def test_sqs_worker_still_requires_sqs(self):
        """Worker-Abhängigkeiten bleiben hart: sqs_worker ohne sqs → fail-closed."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                self._build(Path(tmp) / "x", ["dynamodb", "sqs_worker"])
            self.assertIn("sqs_worker", str(ctx.exception))
            self.assertIn("sqs", str(ctx.exception))

    # ---------- PHASE2: SQS optional für iam/lambda ----------

    def test_iam_without_sqs_valid(self):
        """IAM ohne Queue-ARN: gültige Auswahl, kein SQS-Wiring, Gate AUS."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "iam-only"
            self._build(target, ["dynamodb", "iam"])
            main_tf = (target / "terraform" / "main.tf").read_text()
            self.assertNotIn("sqs_queue_arn", main_tf)
            self.assertNotIn("module.sqs", main_tf)
            # GAP-06: ohne sqs-Modul wird auch das Gate-Flag entfernt
            # (IAM-Default false) — sonst würde die ARN-Precondition scheitern.
            self.assertNotIn("sqs_enabled", main_tf)
            iam_module = (
                target / "terraform" / "modules" / "iam" / "main.tf"
            ).read_text()
            # Count-Gating: ausschließlich das boolesche Gate steuert die Anzahl
            self.assertEqual(iam_module.count("count = var.sqs_enabled ? 1 : 0"), 1)
            self.assertEqual(iam_module.count("count  = var.sqs_enabled ? 1 : 0"), 1)
            self.assertNotIn("var.sqs_queue_arn != ", iam_module)
            # Basis-Policy (DDB+Logs) bleibt im handler-Dokument:
            self.assertIn("DynamoDBTable", iam_module)
            self.assertIn("Logs", iam_module)

    def test_lambda_without_sqs_sync_only(self):
        """Lambda ohne Queue: gültig (synchroner Handler), kein queue_url-Wiring."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sync-only"
            self._build(target, ["dynamodb", "iam", "lambda"])
            main_tf = (target / "terraform" / "main.tf").read_text()
            self.assertNotIn("queue_url", main_tf)
            self.assertIn('module "lambda"', main_tf)
            # Handler-Artefakt wird nach wie vor geliefert (Lambda ist ausgewählt):
            self.assertTrue((target / "lambda" / "dist" / "lambda.zip").is_file())

    def test_iam_with_sqs_keeps_wiring(self):
        """Mit sqs in der Auswahl bleiben ARN- und Gate-Wiring erhalten."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "with-sqs"
            self._build(target, ["dynamodb", "sqs", "iam"])
            main_tf = (target / "terraform" / "main.tf").read_text()
            self.assertIn("sqs_queue_arn      = module.sqs.queue_arn", main_tf)
            self.assertRegex(main_tf, r"sqs_enabled\s*=\s*true")

    def test_sqs_outputs_dropped_without_sqs_module(self):
        """GAP-02: sqs_queue_name referenziert module.sqs — ohne sqs-Modul darf
        kein SQS-Output (auch nicht der neue Name) im Output-Vertrag landen."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "no-sqs-outputs"
            self._build(target, ["dynamodb", "iam"])
            outputs_text = (target / "terraform" / "outputs.tf").read_text()
            self.assertNotIn("sqs_queue_name", outputs_text)
            self.assertNotIn("module.sqs", outputs_text)
            names = set(re.findall(r'^output\s+"([a-z_]+)"', outputs_text, re.M))
            self.assertEqual(names, {"dynamodb_table_name", "dynamodb_table_arn",
                                     "iam_handler_role_name", "iam_handler_role_arn"})

    def test_lambda_without_sqs_readme_note(self):
        """Generiertes README dokumentiert den synchronen Betrieb ohne SQS."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "readme-check"
            self._build(target, ["dynamodb", "iam", "lambda"])
            readme = (target / "README.md").read_text()
            self.assertIn("SQS nicht ausgewählt", readme)

    def test_unknown_module_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                self._build(Path(tmp) / "x", ["dynamodb", "foo"])
            self.assertIn("unbekannte Module", str(ctx.exception))
            self.assertIn("Verfügbare Module", str(ctx.exception))

    def test_duplicate_module_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                self._build(Path(tmp) / "x", ["dynamodb", "dynamodb"])
            self.assertIn("doppelte Module", str(ctx.exception))

    def test_nothing_added_silently(self):
        """Auswahl bleibt exakt die Auswahl — keine stillschweigende Ergänzung."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "exact"
            self._build(target, ["cognito", "cloudtrail"])
            main_modules = self._names(target, r'module\s+"([a-z_]+)"')
            self.assertEqual(main_modules, {"cognito", "cloudtrail"})
            mod_dirs = {f.split("/")[2] for f in
                        {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()}
                        if f.startswith("terraform/modules/")}
            self.assertEqual(mod_dirs, {"cognito", "cloudtrail"})

    def test_full_custom_selection_equivalent_to_complete(self):
        """Alle 11 Module via --modules ≈ Preset complete (Modul-/Variablen-/Output-Mengen)."""
        all_modules = sorted(MODULE_CATALOG)
        with tempfile.TemporaryDirectory() as tmp:
            custom = self._build(Path(tmp) / "custom", all_modules)
            complete = build(
                target_dir=Path(tmp) / "complete",
                project_name="sel-test",
                source_root=REPO_ROOT,
            )
            def names_in(root: Path, filename: str, pattern: str) -> set:
                return set(re.findall(pattern, (root / "terraform" / filename).read_text(), re.M))
            for filename, pattern in [
                ("main.tf", r'^module\s+"([a-z_]+)"'),
                ("variables.tf", r'^variable\s+"([a-z_]+)"'),
                ("outputs.tf", r'^output\s+"([a-z_]+)"'),
            ]:
                self.assertEqual(
                    names_in(custom.target, filename, pattern),
                    names_in(complete.target, filename, pattern),
                    f"Mengen weichen ab: {filename}",
                )

    def test_custom_manifest_contains_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "manifest-check"
            self._build(target, ["dynamodb", "sqs"])
            manifest = json.loads((target / "module-builder.manifest.json").read_text())
            self.assertEqual(manifest["preset"], "custom")
            self.assertEqual(manifest["modules"], ["dynamodb", "sqs"])
            self.assertEqual(manifest["project_name"], "sel-test")

    def test_custom_build_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self._build(Path(tmp) / "a", ["cognito", "cloudtrail"])
            second = self._build(Path(tmp) / "b", ["cognito", "cloudtrail"])
            def tree_files(root: Path) -> dict:
                return {
                    str(p.relative_to(root)): p.read_bytes()
                    for p in root.rglob("*")
                    if p.is_file() and p.name != "module-builder.manifest.json"
                }
            self.assertEqual(tree_files(first.target), tree_files(second.target))

    def test_custom_output_free_of_states_and_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean"
            self._build(target, ["dynamodb"])
            for f in {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()}:
                self.assertIsNone(
                    re.search(r"\.tfstate|\.tfplan|(^|/)tfplan|(^|/)credentials|(^|/)\.env", f),
                    f"Verbotene Datei: {f}",
                )


class TestModuleSelectionCliB1(unittest.TestCase):

    def _run(self, argv):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(argv)
        return code, stdout.getvalue()

    def test_cli_modules_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "cli-sel"
            code, out = self._run([
                "build", "--target", str(target),
                "--project-name", "cli-sel", "--modules", "dynamodb,cognito",
            ])
            self.assertEqual(code, 0)
            self.assertIn("Build OK", out)
            self.assertTrue((target / "terraform" / "modules" / "dynamodb").is_dir())

    def test_cli_preset_and_modules_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as ctx:
            self._run(["build", "--target", "/tmp/opencode/never", "--project-name", "abc",
                       "--preset", "complete", "--modules", "dynamodb"])
        self.assertEqual(ctx.exception.code, 2)

    def test_cli_unknown_module_message(self):
        with self.assertRaises(SystemExit) as ctx:
            self._run(["build", "--target", "/tmp/opencode/never2", "--project-name", "abc",
                       "--modules", "nope"])
        self.assertIn("unbekannte Module", str(ctx.exception))


class TestWithDepsB2(unittest.TestCase):
    """B2: --with-deps — transitive Pflichtabhängigkeits-Ergänzung."""

    def _build(self, target: Path, modules, with_deps=True, project_name="b2-test"):
        return build(
            target_dir=target,
            project_name=project_name,
            preset_name="complete",
            source_root=REPO_ROOT,
            modules=modules,
            with_deps=with_deps,
        )

    def _manifest(self, target: Path) -> dict:
        return json.loads((target / "module-builder.manifest.json").read_text())

    def test_wp3_a_iam_direct_dependency(self):
        """A) iam --with-deps → dynamodb + iam."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a"
            self._build(target, ["iam"])
            m = self._manifest(target)
            self.assertEqual(m["modules"], ["dynamodb", "iam"])
            self.assertEqual(m["modules_requested"], ["iam"])
            self.assertEqual(m["modules_added"], ["dynamodb"])

    def test_wp3_b_lambda_transitive_without_sqs(self):
        """B) lambda --with-deps → dynamodb, iam, lambda — KEIN SQS (optional bleibt optional)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "b"
            self._build(target, ["lambda"])
            m = self._manifest(target)
            self.assertEqual(m["modules"], ["dynamodb", "iam", "lambda"])
            self.assertNotIn("sqs", m["modules"])
            self.assertEqual(m["modules_added"], ["dynamodb", "iam"])

    def test_wp3_c_sqs_worker_full_chain(self):
        """C) sqs_worker --with-deps → dynamodb, sqs, sqs_worker."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "c"
            self._build(target, ["sqs_worker"])
            m = self._manifest(target)
            self.assertEqual(m["modules"], ["dynamodb", "sqs", "sqs_worker"])

    def test_wp3_d_api_all_transitive(self):
        """D) api --with-deps → alle transitiven Pflichtabhängigkeiten."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "d"
            self._build(target, ["api"])
            m = self._manifest(target)
            self.assertEqual(m["modules"],
                             ["api", "cognito", "dynamodb", "iam", "lambda"])

    def test_wp3_e_dynamodb_no_additions(self):
        """E) dynamodb --with-deps → keine Ergänzungen."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "e"
            self._build(target, ["dynamodb"])
            m = self._manifest(target)
            self.assertEqual(m["modules"], ["dynamodb"])
            self.assertEqual(m["modules_added"], [])

    def test_multi_used_dependency_appears_once(self):
        """Mehrfach verwendete Abhängigkeit (dynamodb) erscheint genau einmal."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "multi"
            self._build(target, ["api", "monitoring", "sqs_worker"])
            m = self._manifest(target)
            self.assertEqual(m["modules"].count("dynamodb"), 1)
            self.assertEqual(m["modules"], sorted(set(m["modules"])))

    def test_unknown_module_rejected_with_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                self._build(Path(tmp) / "x", ["iam", "nope"])
            self.assertIn("unbekannte Module", str(ctx.exception))

    def test_duplicates_rejected_with_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                self._build(Path(tmp) / "x", ["iam", "iam"])
            self.assertIn("doppelte Module", str(ctx.exception))

    def test_cycle_detected_fail_closed(self):
        """Zyklus im Katalog → verständliche Meldung mit Zyklus-Pfad."""
        from module_builder.catalog import resolve_with_deps
        cyclic = {
            "a": {"dir": "a", "deps": ["b"], "optional_deps": []},
            "b": {"dir": "b", "deps": ["c"], "optional_deps": []},
            "c": {"dir": "c", "deps": ["a"], "optional_deps": []},
        }
        with mock.patch("module_builder.catalog.MODULE_CATALOG", cyclic):
            with self.assertRaises(SystemExit) as ctx:
                resolve_with_deps(["a"])
            msg = str(ctx.exception)
            self.assertIn("Abhängigkeitszyklus", msg)
            self.assertIn("a -> b -> c -> a", msg)

    def test_inconsistent_catalog_entry_fail_closed(self):
        """Katalogeintrag ohne deps-Feld → fail-closed."""
        from module_builder.catalog import resolve_with_deps
        broken = {"a": {"dir": "a"}}
        with mock.patch("module_builder.catalog.MODULE_CATALOG", broken):
            with self.assertRaises(SystemExit) as ctx:
                resolve_with_deps(["a"])
            self.assertIn("inkonsistenter Katalogeintrag", str(ctx.exception))

    def test_b1_without_with_deps_still_fail_closed(self):
        """Ohne --with-deps bleibt das B1-Verhalten exakt erhalten."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                self._build(Path(tmp) / "x", ["lambda"], with_deps=False)
            self.assertIn("fehlende Pflichtabhängigkeiten", str(ctx.exception))

    def test_with_deps_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self._build(Path(tmp) / "a", ["sqs_worker"])
            second = self._build(Path(tmp) / "b", ["sqs_worker"])
            def tree_files(root: Path) -> dict:
                return {
                    str(p.relative_to(root)): p.read_bytes()
                    for p in root.rglob("*")
                    if p.is_file() and p.name != "module-builder.manifest.json"
                }
            self.assertEqual(tree_files(first.target), tree_files(second.target))

    def test_readme_documents_added_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "readme"
            self._build(target, ["sqs_worker"])
            readme = (target / "README.md").read_text()
            self.assertIn("--with-deps", readme)
            self.assertIn("dynamodb", readme)

    def test_cli_with_deps_transparency_output(self):
        """WP5: CLI unterscheidet Requested / Added / Final."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "cli-b2"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([
                    "build", "--target", str(target),
                    "--project-name", "cli-b2",
                    "--modules", "sqs_worker", "--with-deps",
                ])
            out = stdout.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("Requested modules:", out)
            self.assertIn("sqs_worker", out)
            self.assertIn("Automatically added dependencies:", out)
            self.assertIn("dynamodb", out)
            self.assertIn("sqs", out)
            self.assertIn("Final module selection:", out)
            self.assertIn("dynamodb, sqs, sqs_worker", out)

    def test_cli_without_with_deps_output_unchanged(self):
        """B1-CLI-Ausgabe bleibt unverändert (keine Deps-Blöcke)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "cli-b1"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([
                    "build", "--target", str(target),
                    "--project-name", "cli-b1",
                    "--modules", "dynamodb,sqs,iam",
                ])
            out = stdout.getvalue()
            self.assertEqual(code, 0)
            self.assertNotIn("Automatically added dependencies:", out)
            self.assertIn("Module:      dynamodb, iam, sqs", out)


class TestOrdersServiceModule(unittest.TestCase):
    """MAYS-ORDERS-MODULE-CONTRACT-01: orders-service-Modul-Generierung."""

    @classmethod
    def setUpClass(cls):
        from module_builder.builder import build_module
        cls._tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls._tmp.name) / "Mays-Order-AWS"
        cls.result = build_module(
            target_dir=cls.target,
            project_name="contract-orders",
            source_root=REPO_ROOT,
        )

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _tree(self) -> set:
        return {str(p.relative_to(self.target)) for p in self.target.rglob("*") if p.is_file()}

    def test_module_layout(self):
        tree = self._tree()
        for expected in [
            "main.tf", "variables.tf", "outputs.tf", "versions.tf", "README.md",
            "modules/dynamodb/main.tf", "modules/sqs/main.tf", "modules/iam/main.tf",
            "modules/lambda/main.tf", "modules/cognito/main.tf", "modules/api/main.tf",
            "modules/sqs-worker/main.tf",
            "lambda/dist/lambda.zip", "lambda/build_zip.py", "lambda/src/index.py",
            "module-builder.manifest.json",
        ]:
            self.assertIn(expected, tree, f"Fehlt: {expected}")
        # Vertrag: KEINE Bestandteile außerhalb des Orders-Service
        for absent in [
            "modules/monitoring", "modules/cloudtrail", "modules/cognito_backup",
            "modules/cognito_backup_automation", "scripts", "database",
            "terraform", "terraform.tfvars.example",
            "policy/validate-plan.py", "policy/resource-policy.json",
            "dist/cognito_backup.zip", "cognito_backup",
        ]:
            self.assertFalse(any(f.startswith(absent) for f in tree),
                            f"Vertragsfremd im Modul: {absent}")

    def test_main_composition(self):
        main_tf = (self.target / "main.tf").read_text()
        # Genau die 7 Vertragsmodule
        modules = set(re.findall(r'^module\s+"([a-z_]+)"', main_tf, re.M))
        self.assertEqual(modules, {"api", "cognito", "dynamodb", "iam",
                                  "lambda", "sqs", "sqs_worker"})
        # Kindmodul-Vertrag: kein Provider-/terraform-Block im Modul-main
        self.assertNotRegex(main_tf, r'^provider\s', "Provider-Block im Modul verboten")
        self.assertNotRegex(main_tf, r'^terraform\s', "terraform-Block gehört in versions.tf")
        # Kein Seed (kein Bestandteil des Orders-Service-Vertrags)
        self.assertNotIn("terraform_data", main_tf)
        self.assertNotIn("seed", main_tf)
        # Artefakte modulrelativ (path.module statt path.root)
        self.assertEqual(main_tf.count('${path.module}/lambda/dist/lambda.zip'), 2)
        self.assertNotIn("path.root", main_tf)
        # Tag-Parität: alle 7 Modulblöcke nutzen local.default_tags (Maker/Environment)
        self.assertEqual(main_tf.count("tags         = local.default_tags")
                         + len(re.findall(r"tags\s*=\s*local\.default_tags", main_tf)) >= 1
                         and len(re.findall(r"tags\s*=\s*local\.default_tags", main_tf)), 7)

    def test_variables_contract(self):
        variables = set(re.findall(r'^variable\s+"([a-z_]+)"',
                          (self.target / "variables.tf").read_text(), re.M))
        self.assertEqual(variables, {"project_name", "tags",
                                     "monitoring_enabled", "log_retention_days",
                                     "external_cognito"})
        text = (self.target / "variables.tf").read_text()
        self.assertIn('"contract-orders"', text)  # project_name-Default substituiert

    def test_outputs_contract(self):
        """WP5 + GAP-02: 19 Bestands-Outputs + sqs_queue_name = 20."""
        outputs_text = (self.target / "outputs.tf").read_text()
        outputs = set(re.findall(r'^output\s+"([a-z_]+)"', outputs_text, re.M))
        for required in [
            "api_gateway_endpoint", "api_gateway_id", "api_gateway_stage_name",
            "api_gateway_authorizer_id",
            "dynamodb_table_name", "dynamodb_table_arn",
            "sqs_queue_url", "sqs_queue_arn", "sqs_queue_name",
            "sqs_worker_lambda_arn",
            "lambda_function_name", "lambda_function_arn", "lambda_invoke_arn",
            "iam_handler_role_name", "iam_handler_role_arn",
            "cognito_user_pool_id", "cognito_user_pool_arn",
            "cognito_user_pool_endpoint", "cognito_user_pool_client_id",
            "cognito_user_pool_group_name",
        ]:
            self.assertIn(required, outputs, f"Output fehlt: {required}")
        self.assertEqual(len(outputs), 20)
        # GAP-02: der Queue-Name stammt aus dem vorhandenen sqs-Modul-Output
        # (keine zweite Namenskonstruktion, kein hartcodierter Projektname).
        block = re.search(
            r'output "sqs_queue_name" \{(.*?)\n\}', outputs_text, re.S
        )
        self.assertIsNotNone(block)
        self.assertRegex(block.group(1), r"value\s*=\s*module\.sqs\.queue_name")
        self.assertNotIn("${", block.group(1))
        self.assertNotIn("project_name", block.group(1))
        # Alle Referenzen bleiben im Vertragsbestand
        refs = set(re.findall(r"module\.([a-z_]+)", outputs_text))
        self.assertTrue(refs.issubset({"api", "cognito", "dynamodb", "iam",
                                       "lambda", "sqs", "sqs_worker"}))

    def test_iam_sqs_gate_contract(self):
        """GAP-06: beide counts hängen NUR am booleschen Gate; der ARN bleibt
        Policy-Resource (keine Wildcard) und wird per Precondition geprüft."""
        iam_main = (self.target / "modules" / "iam" / "main.tf").read_text()
        iam_vars = (self.target / "modules" / "iam" / "variables.tf").read_text()

        # Beide ehemals ARN-abhängigen counts sind jetzt gate-abhängig.
        self.assertEqual(iam_main.count("var.sqs_enabled ? 1 : 0"), 2)
        self.assertNotRegex(iam_main, r"count[^\n]*var\.sqs_queue_arn")
        self.assertNotIn('var.sqs_queue_arn != ""', iam_main)

        sqs_doc = iam_main.split('data "aws_iam_policy_document" "sqs" {')[1]
        sqs_doc = sqs_doc.split('resource "aws_iam_role_policy" "sqs" {')[0]
        self.assertIn("resources = [var.sqs_queue_arn]", sqs_doc)
        self.assertNotIn('"*"', sqs_doc)
        self.assertIn("precondition {", sqs_doc)
        self.assertIn('trimspace(var.sqs_queue_arn) != ""', sqs_doc)

        # Interner Vertrag: bool, Default false → kein 6. öffentlicher Input.
        self.assertRegex(
            iam_vars,
            r'variable "sqs_enabled" \{[\s\S]*?type\s*=\s*bool[\s\S]*?default\s*=\s*false',
        )
        # Kein check-Block (liefert nur Warnungen; GAP-06 verlangt hart).
        self.assertNotIn('check "', iam_main)

    def test_iam_sqs_gate_wired_plan_known(self):
        """GAP-06: der Root-Aufrufer setzt das Gate als Literal (plan-bekannt),
        abgeleitet aus der festen Modulkonfiguration — nicht aus ARN/Namen."""
        main_tf = (self.target / "main.tf").read_text()
        iam_block = main_tf.split('module "iam" {')[1].split("\n}")[0]
        self.assertRegex(iam_block, r"(?m)^\s*sqs_enabled\s*=\s*true\s*$")
        self.assertIn("sqs_queue_arn      = module.sqs.queue_arn", iam_block)
        self.assertNotIn("sqs_enabled = module.", iam_block)
        # Genau 5 öffentliche Inputs (kein zusätzlicher Gate-Input):
        variables = set(re.findall(
            r'^variable\s+"([a-z_]+)"',
            (self.target / "variables.tf").read_text(), re.M))
        self.assertEqual(variables, {"project_name", "tags",
                                     "monitoring_enabled", "log_retention_days",
                                     "external_cognito"})

    def test_versions_tf_contains_terraform_block(self):
        versions = (self.target / "versions.tf").read_text()
        main_tf = (self.target / "main.tf").read_text()
        self.assertIn("required_providers", versions)
        self.assertIn('source  = "hashicorp/aws"', versions)
        self.assertNotIn("required_providers", main_tf)

    def test_manifest_contract(self):
        manifest = json.loads(
            (self.target / "module-builder.manifest.json").read_text()
        )
        self.assertEqual(manifest["preset"], "orders-service")
        self.assertEqual(manifest["modules"],
                         ["api", "cognito", "dynamodb", "iam", "lambda",
                          "sqs", "sqs_worker"])
        self.assertEqual(manifest["project_name"], "contract-orders")
        self.assertIn("lambda/dist/lambda.zip", manifest["artifacts_sha256"])

    def test_readme_contract_and_example(self):
        readme = (self.target / "README.md").read_text()
        self.assertIn('module "orders"', readme)
        self.assertIn("source =", readme)
        self.assertIn("project_name", readme)
        self.assertIn("sqs_queue_url", readme)          # Outputs dokumentiert
        self.assertIn("sqs_queue_name", readme)
        self.assertIn("sqs_worker_lambda_arn", readme)
        self.assertIn("BLOCKED", readme)                # Privacy-Hinweis
        self.assertIn("Orders-Service", readme)         # Vertrag benannt

    def test_module_mode_deterministic(self):
        from module_builder.builder import build_module
        with tempfile.TemporaryDirectory() as tmp:
            second = build_module(
                target_dir=Path(tmp) / "Mays-Order-AWS",
                project_name="contract-orders",
                source_root=REPO_ROOT,
            )
            def tree_files(root: Path) -> dict:
                return {
                    str(p.relative_to(root)): p.read_bytes()
                    for p in root.rglob("*")
                    if p.is_file() and p.name != "module-builder.manifest.json"
                }
            self.assertEqual(tree_files(self.target), tree_files(second.target))

    def test_module_mode_fail_closed_missing_artifact(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as out:
            src_root = Path(src)
            (src_root / "terraform").mkdir()
            (src_root / "terraform" / "main.tf").write_text("terraform {\n}\n")
            from module_builder.builder import build_module
            with self.assertRaises(SystemExit) as ctx:
                build_module(target_dir=Path(out) / "m", project_name="fail-test",
                            source_root=src_root)
            self.assertIn("fail-closed", str(ctx.exception))

    def test_module_mode_respects_force_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            foreign = self.target.parent / "force-test"
            foreign.mkdir(exist_ok=True)
            (foreign / "keep.txt").write_text("foreign")
            from module_builder.builder import build_module
            with self.assertRaises(SystemExit) as ctx:
                build_module(target_dir=foreign, project_name="force-test",
                             source_root=REPO_ROOT)
            self.assertIn("--force", str(ctx.exception))
            self.assertEqual((foreign / "keep.txt").read_text(), "foreign")
            (foreign / "keep.txt").unlink()

    def test_cli_orders_service_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Mays-Order-AWS"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([
                    "build", "--preset", "orders-service",
                    "--target", str(target),
                    "--project-name", "cli-module",
                ])
            self.assertEqual(code, 0)
            out = stdout.getvalue()
            self.assertIn("orders-service (Terraform-Modul)", out)
            self.assertTrue((target / "main.tf").is_file())

    def test_cli_orders_service_rejects_modules(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["build", "--preset", "orders-service", "--target", "/tmp/opencode/x",
                  "--project-name", "abc", "--modules", "dynamodb"])
        self.assertEqual(ctx.exception.code, 2)  # Mutual-Exclusion (argparse)


class TestExternalCognitoIntegration(unittest.TestCase):
    """MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01: MANAGED/EXTERNAL im
    generierten Orders-Modul (nur Builder-Scope; Stamm-Repo unangetastet)."""

    @classmethod
    def setUpClass(cls):
        from module_builder.builder import build_module
        cls._tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls._tmp.name) / "Mays-Order-AWS"
        build_module(target_dir=cls.target, project_name="cognito-modes",
                    source_root=REPO_ROOT)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _main(self) -> str:
        return (self.target / "main.tf").read_text()

    def _variables(self) -> str:
        return (self.target / "variables.tf").read_text()

    def _outputs(self) -> str:
        return (self.target / "outputs.tf").read_text()

    def test_managed_is_default(self):
        """1) MANAGED bleibt Standard: external_cognito = null."""
        self.assertRegex(self._variables(),
                         r'variable\s+"external_cognito"[\s\S]*?default\s*=\s*null')

    def test_managed_cognito_module_with_count_gate(self):
        """2) MANAGED erzeugt Cognito wie bisher (count=1 bei null)."""
        main = self._main()
        self.assertIn('module "cognito" {', main)
        self.assertRegex(
            main, r"count\s*=\s*var\.external_cognito == null \? 1 : 0")
        self.assertTrue((self.target / "modules" / "cognito" / "main.tf").is_file())

    def test_external_uses_existing_references(self):
        """3) EXTERNAL verwendet die Referenzen über locals."""
        main = self._main()
        self.assertRegex(
            main,
            r"cognito_endpoint\s*=\s*var\.external_cognito == null \? "
            r"one\(module\.cognito\[\*\]\.user_pool_endpoint\) : "
            r"var\.external_cognito\.user_pool_endpoint")
        self.assertRegex(
            main,
            r"cognito_client_id\s*=\s*var\.external_cognito == null \? "
            r"one\(module\.cognito\[\*\]\.user_pool_client_id\) : "
            r"var\.external_cognito\.user_pool_client_id")

    def test_external_creates_no_cognito_resources(self):
        """4/5) EXTERNAL erzeugt keinen Pool und keinen App-Client:
        module.cognito ist ausschließlich count-gated instanziiert."""
        main = self._main()
        self.assertEqual(main.count('module "cognito" {'), 1)
        # api-Block referenziert NUR die locals, nie direkt module.cognito:
        api_block = main[main.index('module "api" {'):]
        api_block = api_block[:api_block.index("}")]
        self.assertNotIn("module.cognito", api_block)

    def test_jwt_authorizer_stays_active(self):
        """6) JWT-Authorizer bleibt in beiden Varianten aktiv
        (api-Eingaben bleiben gesetzt, Werte nie leer — kein Default ""!)."""
        api_block = self._main().split('module "api" {')[1].split("}")[0]
        self.assertRegex(api_block, r"cognito_user_pool_endpoint\s*=\s*local\.cognito_endpoint")
        self.assertRegex(api_block, r"cognito_user_pool_client_id\s*=\s*local\.cognito_client_id")

    def test_incomplete_external_refs_fail_closed(self):
        """7) Unvollständige externe Referenzen werden verständlich abgelehnt."""
        variables = self._variables()
        self.assertIn("validation {", variables)
        self.assertIn("fail-closed", variables)
        # HCL-escapte Regex (Datei enthält \\., String-Wert enthält \.)
        self.assertIn("cognito-idp\\\\.[a-z0-9-]+", variables)

    def test_worker_sqs_dynamodb_stay_mandatory(self):
        """8-10) Worker, SQS, eigene Tabelle bleiben enthalten."""
        modules = set(re.findall(r'^module\s+"([a-z_]+)"', self._main(), re.M))
        self.assertIn("sqs_worker", modules)
        self.assertIn("sqs", modules)
        self.assertIn("dynamodb", modules)

    def test_tags_preserved(self):
        """11) Bestehende Tags bleiben erhalten (local.default_tags)."""
        self.assertEqual(len(re.findall(r"tags\s*=\s*local\.default_tags", self._main())), 7)

    def test_output_names_and_external_safe_values(self):
        """12) 20 Output-Namen (19 Bestand + sqs_queue_name/GAP-02) + EXTERNAL-sichere Werte."""
        outputs = self._outputs()
        names = set(re.findall(r'^output\s+"([a-z_]+)"', outputs, re.M))
        self.assertEqual(len(names), 20)
        self.assertIn("sqs_queue_name", names)
        # Modus-sichere Wertformen:
        self.assertIn("value       = local.cognito_endpoint", outputs)
        self.assertIn("value       = local.cognito_client_id", outputs)
        self.assertIn("value       = one(module.cognito[*].user_pool_id)", outputs)
        self.assertIn("value       = one(module.cognito[*].user_pool_arn)", outputs)
        self.assertIn("value       = one(module.cognito[*].user_pool_group_staff_name)", outputs)
        # Keine ungesicherten Direktreferenzen mehr:
        self.assertNotIn("= module.cognito.", outputs)

    def test_readme_documents_both_modes(self):
        readme = (self.target / "README.md").read_text()
        self.assertIn("MANAGED", readme)
        self.assertIn("EXTERNAL", readme)
        self.assertIn("external_cognito", readme)
        self.assertIn("NICHT automatisiert", readme)  # Migration-Warnung

    def test_manifest_notes_external_cognito(self):
        manifest = json.loads(
            (self.target / "module-builder.manifest.json").read_text())
        self.assertIn("external_cognito", manifest["notes"])


if __name__ == "__main__":
    unittest.main()
