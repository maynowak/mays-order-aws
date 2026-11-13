"""MO-RC4-P02I-E2B: Cleanup-/Destroy-Vertrag (lokale Regeln).

Kein AWS, kein Terraform: prueft die Schutzregeln fuer State-Cleanup und
Residual-Audit.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from installer.core.cleanup_contract import (
    PROTECTED_RESOURCES,
    PROTECTED_STATE_KEYS,
    expected_state_key,
    residual_resources,
    validate_cleanup_target,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLEANUP_MODULE = REPO_ROOT / "installer" / "core" / "cleanup_contract.py"


class TestCleanupTarget(unittest.TestCase):
    def test_rc4_state_is_accepted(self):
        key = "env:/mays-orders-rc4/terraform.tfstate"
        self.assertEqual(key, expected_state_key("mays-orders-rc4"))
        self.assertEqual(validate_cleanup_target(key, "mays-orders-rc4"), [])

    def test_default_project_state_is_rejected(self):
        errors = validate_cleanup_target("env:/mays-orders/terraform.tfstate", "mays-orders-rc4")
        self.assertTrue(errors)
        self.assertIn("geschuetzt", " ".join(errors))

    def test_legacy_default_key_is_rejected(self):
        errors = validate_cleanup_target("terraform.tfstate", "mays-orders-rc4")
        self.assertTrue(errors)

    def test_other_known_project_state_is_rejected(self):
        errors = validate_cleanup_target(
            "env:/mays-order-par/terraform.tfstate", "mays-orders-rc4"
        )
        self.assertTrue(any("geschuetzt" in e for e in errors))

    def test_unknown_state_is_rejected(self):
        errors = validate_cleanup_target("env:/other/terraform.tfstate", "mays-orders-rc4")
        self.assertTrue(any("nicht der State des Projekts" in e for e in errors))

    def test_empty_project_name_is_rejected(self):
        self.assertTrue(validate_cleanup_target("env:/x/terraform.tfstate", ""))

    def test_shared_and_ris_resources_are_listed_as_protected(self):
        joined = " ".join(PROTECTED_RESOURCES)
        self.assertIn("mays-orders-tfstate-central-240571105849", joined)
        self.assertIn("mays-orders-terraform-locks", joined)
        self.assertIn("RIS", joined)
        self.assertIn("env:/mays-orders/terraform.tfstate", PROTECTED_STATE_KEYS)


class TestResidualAudit(unittest.TestCase):
    def test_empty_state_output(self):
        self.assertEqual(residual_resources(""), [])
        self.assertEqual(residual_resources("\n\n"), [])

    def test_remaining_resources_are_detected(self):
        output = "module.dynamodb.aws_dynamodb_table.orders\nmodule.sqs.aws_sqs_queue.orders\n"
        self.assertEqual(len(residual_resources(output)), 2)

    def test_no_prefix_based_deletion_in_cleanup_module(self):
        """Cleanup darf nicht auf Namenspraefixen oder AWS-Clients basieren."""
        text = CLEANUP_MODULE.read_text(encoding="utf-8")
        self.assertNotIn("boto3", text)
        self.assertNotIn("delete_", text)
        self.assertNotIn("subprocess", text)
        self.assertIn("Terraform-State", text)


if __name__ == "__main__":
    unittest.main()
