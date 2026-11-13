"""MO-RC4-P02I-E1B: statischer Vertragstest fuer den Cognito-Backup-Namensraum.

Die Bucket-Namensbildung liegt in HCL (terraform/modules/cognito_backup) und
kann ohne `terraform plan` nicht ausgewertet werden. Dieser Test pinnt den
Vertrag deshalb statisch an den tatsaechlichen Namensausdruecken:

* Default-Installation ("mays-orders") behaelt ihren historischen Namen
  (kein Bucket-Replacement durch die Namespace-Reparatur).
* Jedes andere Projekt bekommt einen Namen im eigenen "<project>-"Namespace
  (Policy-Gate-konform).
* Laengen-/Zeichen-Grenzen sind als Plan-Precondition abgesichert.

Keine AWS-Aufrufe, kein Terraform.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "terraform" / "modules" / "cognito_backup"
MODULE_MAIN = MODULE_DIR / "main.tf"
MODULE_VARS = MODULE_DIR / "variables.tf"
ROOT_MAIN = REPO_ROOT / "terraform" / "main.tf"

LEGACY_BUCKET_NAME = "mays-orders-cognito-backup-development-mays-orders"
RC4_BUCKET_NAME = "mays-orders-rc4-cognito-backup-development"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def project_scoped_bucket_name(project_name: str, environment: str = "Development") -> str:
    """Python-Spiegel der HCL-Regel fuer Nicht-Default-Projekte."""
    return f"{project_name}-cognito-backup-{environment}".lower()


class TestBackupBucketNamingContract(unittest.TestCase):
    def test_default_project_keeps_historical_bucket_name(self) -> None:
        """Regression: der Default-Name darf sich nicht aendern (kein Replacement)."""
        main = _read(MODULE_MAIN)
        self.assertIn(
            'legacy_default_bucket_name = lower("mays-orders-cognito-backup-'
            '${var.environment}-${var.project_name}")',
            main,
        )
        # Der historische Name fuer die Default-Installation bleibt identisch.
        self.assertEqual(
            "mays-orders-cognito-backup-Development-mays-orders".lower(),
            LEGACY_BUCKET_NAME,
        )
    def test_non_default_project_uses_project_namespace(self) -> None:
        main = _read(MODULE_MAIN)
        self.assertIn(
            'project_scoped_bucket_name = lower("${var.project_name}-cognito-backup-'
            '${var.environment}")',
            main,
        )
        name = project_scoped_bucket_name("mays-orders-rc4")
        self.assertTrue(name.startswith("mays-orders-rc4-"))
        self.assertEqual(name, RC4_BUCKET_NAME)

    def test_legacy_project_would_not_be_project_scoped(self) -> None:
        """Der Default-Name ist absichtlich NICHT im Projekt-Namespace.

        Er ist nur fuer die bestehende Default-Installation zulaessig; das
        Policy Gate prueft die Namespace-Zugehoerigkeit fuer alle anderen
        Projekte (siehe test_policy_namespace.py).
        """
        self.assertFalse(LEGACY_BUCKET_NAME.startswith("mays-orders-rc4-"))
        self.assertTrue(LEGACY_BUCKET_NAME.startswith("mays-orders-"))

    def test_bucket_name_length_within_s3_limit(self) -> None:
        for name in (LEGACY_BUCKET_NAME, RC4_BUCKET_NAME):
            self.assertLessEqual(len(name), 63, f"{name} ueberschreitet das S3-Limit")

    def test_plan_precondition_rejects_invalid_names(self) -> None:
        main = _read(MODULE_MAIN)
        self.assertIn("precondition", main)
        self.assertIn("<= 63", main)
        self.assertIn('regex("^[a-z0-9][a-z0-9.-]*$"', main)

    def test_prefix_override_defaults_to_null(self) -> None:
        variables = _read(MODULE_VARS)
        prefix_block = variables.split('variable "bucket_name_prefix"', 1)[1]
        self.assertIn("default     = null", prefix_block)
        # Kein hartcodiertes Default-Praefix mehr (Root Cause aus P02I-E1A).
        self.assertNotIn('default     = "mays-orders-cognito-backup"', variables)

    def test_root_passes_project_name_into_backup_modules(self) -> None:
        root = _read(ROOT_MAIN)
        self.assertRegex(
            root,
            re.compile(r'module "cognito_backup"[\s\S]*?project_name\s*=\s*var\.project_name'),
        )
        self.assertRegex(
            root,
            re.compile(
                r'module "cognito_backup_automation"[\s\S]*?project_name\s*=\s*var\.project_name'
            ),
        )

    def test_names_are_valid_s3_bucket_names(self) -> None:
        pattern = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
        for name in (LEGACY_BUCKET_NAME, RC4_BUCKET_NAME):
            self.assertRegex(name, pattern)


if __name__ == "__main__":
    unittest.main()
