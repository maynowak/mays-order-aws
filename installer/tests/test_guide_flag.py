"""Tests for the --guide flag (Installer Guide pointer).

The flag must print the guide path plus table of contents and exit 0 —
no AWS, no Terraform, no side effects.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from installer.cli.guide import (
    GUIDE_RELATIVE_PATH,
    extract_sections,
    find_guide_path,
    render_guide_info,
)
from installer.cli.main import InstallerCLI


class TestGuideHelpers(unittest.TestCase):

    def test_guide_file_exists_in_repo(self):
        path = find_guide_path()
        self.assertEqual(path.name, "INSTALLER_GUIDE.md")
        self.assertTrue(path.is_file(), f"Guide fehlt: {path}")

    def test_relative_path_convention(self):
        self.assertEqual(GUIDE_RELATIVE_PATH, "docs/INSTALLER_GUIDE.md")

    def test_extract_sections_returns_known_headings(self):
        sections = extract_sections(find_guide_path())
        self.assertIsInstance(sections, list)
        self.assertTrue(
            any("Sicherheitskontext" in s for s in sections),
            f"Sicherheitskontext fehlt: {sections}",
        )
        self.assertTrue(
            any("Kontrollierter Destroy" in s for s in sections),
            f"Destroy-Abschnitt fehlt: {sections}",
        )
        # Collision-Check section from the 2026-10 incident
        self.assertTrue(
            any("Namenskollisions-Check" in s for s in sections),
            f"Kollisions-Abschnitt fehlt: {sections}",
        )

    def test_extract_sections_missing_file_returns_empty(self):
        self.assertEqual(extract_sections(Path("/nonexistent/guide.md")), [])

    def test_render_guide_info_contains_path_and_toc(self):
        text = render_guide_info()
        self.assertIn("docs/INSTALLER_GUIDE.md", text)
        self.assertIn("Inhaltsverzeichnis", text)
        self.assertIn("gefunden", text)

    def test_render_missing_guide_reports_absence(self):
        # Simulate a repo without the guide: neutralize the repo-root fallback.
        with tempfile.TemporaryDirectory() as tmp:
            with patch("installer.cli.guide._REPO_ROOT", Path(tmp)):
                text = render_guide_info(start=Path(tmp))
        self.assertIn("NICHT gefunden", text)


class TestGuideFlagCLI(unittest.TestCase):

    def _run_capture(self, args):
        cli = InstallerCLI()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.run(args)
        return code, stdout.getvalue()

    def test_guide_flag_alone_exits_zero(self):
        code, out = self._run_capture(["--guide"])
        self.assertEqual(code, 0)
        self.assertIn("docs/INSTALLER_GUIDE.md", out)
        self.assertIn("Inhaltsverzeichnis", out)

    def test_guide_flag_takes_precedence_over_command(self):
        # --guide exits before any command (no AWS/terraform touched)
        code, out = self._run_capture(["--guide", "validate"])
        self.assertEqual(code, 0)
        self.assertIn("Installer-Handbuch", out)

    def test_no_command_without_guide_still_prints_help(self):
        code, out = self._run_capture([])
        self.assertEqual(code, 1)
        self.assertIn("usage:", out)


if __name__ == "__main__":
    unittest.main()
