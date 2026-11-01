"""MO-RC4-P02I-C2 — CI-Artefakt-Gate in der Validate-Buildspec.

Reiner Text-/Struktur-Test (keine AWS-Aufrufe): stellt sicher, dass die
Validate-Stage das Lambda-Artefakt VOR einem Rebuild prueft, den Rebuild
byte-identisch vergleicht und die Packaging-Tests ausfuehrt.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDSPEC = ROOT / "ci" / "buildspecs" / "validate.yml"


class TestValidateBuildspecArtifactGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = BUILDSPEC.read_text(encoding="utf-8")
        cls.lines = [line.strip() for line in cls.text.splitlines()]

    def _index_of(self, needle):
        for index, line in enumerate(self.lines):
            if needle in line:
                return index
        self.fail(f"Buildspec enthaelt nicht: {needle}")

    def test_committed_artifact_is_verified_before_rebuild(self):
        verify = self._index_of("verify_lambda_zip('lambda')")
        rebuild = self._index_of("build_zip.build(")
        self.assertLess(verify, rebuild, "Artefakt muss VOR dem Rebuild geprueft werden")

    def test_rebuild_is_compared_byte_identically(self):
        rebuild = self._index_of("build_zip.build(")
        compare = self._index_of("cmp lambda/dist/lambda.zip")
        self.assertLess(rebuild, compare, "Vergleich muss nach dem Rebuild erfolgen")

    def test_packaging_tests_are_executed(self):
        self._index_of("unittest tests.test_build_zip")
        self._index_of("installer.tests.test_artifact_integrity")
        self._index_of("module_builder.tests.test_module_builder.TestArtifactIntegrityGate")

    def test_existing_terraform_validation_is_preserved(self):
        self.assertIn("terraform validate", self.text)
        self.assertIn("terraform fmt -check", self.text)

    def test_artifact_gate_uses_no_error_suppression(self):
        start = self._index_of("Verifying committed Lambda artifact")
        end = self._index_of("Running installer validation")
        for line in self.lines[start:end]:
            self.assertNotIn("|| true", line)
            self.assertNotIn("|| :", line)
            self.assertNotIn("set +e", line)

    def test_buildspec_yaml_is_parsable(self):
        try:
            import yaml
        except ImportError:  # pragma: no cover - CI-freundlich
            self.skipTest("PyYAML nicht installiert")
        document = yaml.safe_load(self.text)
        commands = document["phases"]["build"]["commands"]
        self.assertTrue(any("verify_lambda_zip" in str(command) for command in commands))


if __name__ == "__main__":
    unittest.main()
