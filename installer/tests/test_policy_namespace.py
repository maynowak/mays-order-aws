"""MO-RC4-P02I-E1B: Policy-Gate-Tests fuer den S3-Namensraum.

Laedt `terraform/policy/validate-plan.py` direkt (Dateiname enthaelt einen
Bindestrich) und prueft die Namespace-/Laengen-/Zeichen-Regeln gegen synthetische
Plan-JSONs. Keine AWS-Aufrufe, kein Terraform.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_SCRIPT = REPO_ROOT / "terraform" / "policy" / "validate-plan.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("mo_policy_gate", POLICY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE = _load_gate()
POLICY = GATE.load_json(GATE.POLICY_PATH)


def _plan_with_bucket(bucket_name: str, project: str) -> Dict[str, Any]:
    return {
        "resource_changes": [
            {
                "address": "module.cognito_backup[0].aws_s3_bucket.cognito_backup",
                "type": "aws_s3_bucket",
                "name": "cognito_backup",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "bucket": bucket_name,
                        "tags_all": {
                            "Project": project,
                            "Maker": "mays-orders",
                            "Environment": "Development",
                        },
                    },
                },
            }
        ]
    }


def _errors(bucket_name: str, project: str) -> List[str]:
    return GATE.check(_plan_with_bucket(bucket_name, project), POLICY)


class TestPolicyNamespace(unittest.TestCase):
    def test_project_scoped_backup_bucket_passes(self) -> None:
        errors = _errors("mays-orders-rc4-cognito-backup-development", "mays-orders-rc4")
        self.assertEqual(errors, [])

    def test_legacy_default_bucket_still_passes(self) -> None:
        errors = _errors(
            "mays-orders-cognito-backup-Development-mays-orders".lower(), "mays-orders"
        )
        self.assertEqual(errors, [])

    def test_prefix_based_name_for_other_project_is_rejected(self) -> None:
        """Exakt der P02I-E1A-Fund: hartcodiertes Praefix + neues Projekt."""
        errors = _errors(
            "mays-orders-cognito-backup-Development-mays-orders-rc4".lower(),
            "mays-orders-rc4",
        )
        self.assertTrue(any("outside the project namespace" in e for e in errors), errors)

    def test_foreign_project_bucket_is_rejected(self) -> None:
        errors = _errors("mays-ris-dev-data", "mays-orders-rc4")
        self.assertTrue(any("outside the project namespace" in e for e in errors), errors)

    def test_too_long_bucket_name_is_rejected(self) -> None:
        name = ("mays-orders-rc4-cognito-backup-" + ("x" * 40))[:64]
        self.assertEqual(len(name), 64)
        errors = _errors(name, "mays-orders-rc4")
        self.assertTrue(any("63-character limit" in e for e in errors), errors)

    def test_invalid_characters_are_rejected(self) -> None:
        errors = _errors("mays-orders-rc4-cognito-backup-Development", "mays-orders-rc4")
        self.assertTrue(any("invalid characters" in e for e in errors), errors)

    def test_unknown_bucket_name_is_not_guessed(self) -> None:
        """Unbekannte Bucket-Namen (known-after-apply) werden nicht bewertet."""
        plan = _plan_with_bucket("placeholder", "mays-orders-rc4")
        plan["resource_changes"][0]["change"]["after"]["bucket"] = None
        self.assertEqual(GATE.check(plan, POLICY), [])


if __name__ == "__main__":
    unittest.main()
