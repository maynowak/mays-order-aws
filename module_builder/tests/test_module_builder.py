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
        """IAM ohne Queue-ARN: gültige Auswahl, kein SQS-Wiring, count-Gated Modul."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "iam-only"
            self._build(target, ["dynamodb", "iam"])
            main_tf = (target / "terraform" / "main.tf").read_text()
            self.assertNotIn("sqs_queue_arn", main_tf)
            self.assertNotIn("module.sqs", main_tf)
            iam_module = (
                target / "terraform" / "modules" / "iam" / "main.tf"
            ).read_text()
            # Count-Gating: ohne Queue-ARN entsteht KEINE sqs-Berechtigung
            self.assertIn('count = var.sqs_queue_arn != "" ? 1 : 0', iam_module)
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
        """Mit sqs in der Auswahl bleibt das SQS-Wiring unverändert erhalten."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "with-sqs"
            self._build(target, ["dynamodb", "sqs", "iam"])
            main_tf = (target / "terraform" / "main.tf").read_text()
            self.assertIn("sqs_queue_arn      = module.sqs.queue_arn", main_tf)

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


if __name__ == "__main__":
    unittest.main()
