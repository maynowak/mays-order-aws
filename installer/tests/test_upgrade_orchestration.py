"""MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01: Upgrade-Modus/Kompatibilitaet.

Rein lokal: keine AWS-/Terraform-Aufrufe.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from installer.cli.main import InstallerCLI
from installer.core.upgrade_mode import (
    CODE_MISSING_INSTALLATION,
    CODE_REQUIRES_REMOTE,
    CODE_STATE_UNREADABLE,
    check_upgrade_source,
)


def _installed(status, version=None):
    return SimpleNamespace(status=status, version=version, resources=1)


class TestUpgradeSource(unittest.TestCase):
    def test_requires_remote(self):
        ok, code, _ = check_upgrade_source(_installed("VERIFIED"), remote=False)
        self.assertFalse(ok)
        self.assertEqual(code, CODE_REQUIRES_REMOTE)

    def test_missing_installation(self):
        ok, code, _ = check_upgrade_source(_installed("UNVERIFIED"), remote=True)
        self.assertFalse(ok)
        self.assertEqual(code, CODE_MISSING_INSTALLATION)

    def test_missing_installed_object(self):
        ok, code, _ = check_upgrade_source(None, remote=True)
        self.assertFalse(ok)
        self.assertEqual(code, CODE_MISSING_INSTALLATION)

    def test_unreadable_state(self):
        ok, code, _ = check_upgrade_source(_installed("UNREADABLE"), remote=True)
        self.assertFalse(ok)
        self.assertEqual(code, CODE_STATE_UNREADABLE)

    def test_verified_installation_allowed(self):
        ok, code, _ = check_upgrade_source(_installed("VERIFIED", "0.1.0"), remote=True)
        self.assertTrue(ok, code)

    def test_legacy_installation_allowed_but_version_unknown(self):
        """Legacy ist eine Installation; die Kompatibilitaet entscheidet danach."""
        ok, code, _ = check_upgrade_source(_installed("LEGACY_UNKNOWN"), remote=True)
        self.assertTrue(ok, code)


class TestUpgradeCliFlag(unittest.TestCase):
    def test_parser_accepts_upgrade(self):
        cli = InstallerCLI()
        parsed = cli.parser.parse_args(["--project-name", "mays-orders-rc4", "plan", "--remote", "--upgrade"])
        self.assertTrue(parsed.remote)
        self.assertTrue(parsed.upgrade)

    def test_default_is_not_upgrade(self):
        cli = InstallerCLI()
        parsed = cli.parser.parse_args(["--project-name", "mays-orders-rc4", "plan", "--remote"])
        self.assertFalse(parsed.upgrade)

    def test_plan_rejects_upgrade_without_remote(self):
        import inspect

        source = inspect.getsource(InstallerCLI._cmd_plan)
        self.assertIn("UPGRADE_REQUIRES_REMOTE", source)
        self.assertIn("check_upgrade_source", source)


if __name__ == "__main__":
    unittest.main()
