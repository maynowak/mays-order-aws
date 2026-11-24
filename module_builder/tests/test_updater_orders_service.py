"""MO-RIS-UPDATER-02: orders-service manifest v2 and upgrade path.

Covers the new v2 fingerprints, the dry-run on an unchanged module, the
conflict gate for manually modified managed files, and the legacy (v1)
adoption that only fingerprints files proven identical to the pinned source.
"""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from module_builder.builder import build_module
from module_builder.cli import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestOrdersServiceUpgrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._tmp.name) / "module"
        build_module(target_dir=cls.base, project_name="upgrade-contract",
                     source_root=REPO_ROOT, force=True)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _copy(self, name: str) -> Path:
        target = Path(self._tmp.name) / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.base, target)
        return target

    def _run(self, args) -> int:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(args)
        self.last_output = out.getvalue()
        return code

    def test_manifest_v2_has_fingerprints(self):
        manifest = json.loads(
            (self.base / "module-builder.manifest.json").read_text())
        self.assertEqual(2, manifest["manifest_version"])
        files = manifest["files"]
        self.assertTrue(files)
        self.assertIn("main.tf", files)
        self.assertIn("modules/agent_transport/main.tf", files)
        self.assertNotIn("module-builder.manifest.json", files)
        self.assertRegex(files["main.tf"], r"^[0-9a-f]{64}$")

    def test_unchanged_module_is_no_changes(self):
        target = self._copy("clean")
        code = self._run(["upgrade", "--project", str(target), "--dry-run"])
        self.assertEqual(0, code, self.last_output)
        self.assertIn("NO_CHANGES", self.last_output)

    def test_managed_file_conflict_blocks(self):
        target = self._copy("conflict")
        main_tf = target / "main.tf"
        main_tf.write_text(main_tf.read_text() + "\n# local edit\n")
        code = self._run(["upgrade", "--project", str(target), "--dry-run"])
        self.assertEqual(1, code, self.last_output)
        self.assertIn("BUILDER_UPGRADE_CONFLICT", self.last_output)

    def test_legacy_adoption_dry_run_does_not_write(self):
        target = self._copy("legacy")
        path = target / "module-builder.manifest.json"
        data = json.loads(path.read_text())
        data.pop("manifest_version", None)
        data.pop("files", None)
        path.write_text(json.dumps(data, indent=2) + "\n")

        before = path.read_bytes()
        code = self._run(["upgrade", "--project", str(target),
                          "--adopt-legacy", "--dry-run"])
        self.assertEqual(0, code, self.last_output)
        self.assertIn("ADOPTED", self.last_output)
        self.assertEqual(before, path.read_bytes())

    def test_legacy_adoption_requires_matching_pin(self):
        target = self._copy("legacy_mismatch")
        path = target / "module-builder.manifest.json"
        data = json.loads(path.read_text())
        data.pop("manifest_version", None)
        data.pop("files", None)
        data["source"]["commit"] = "0" * 40
        path.write_text(json.dumps(data, indent=2) + "\n")

        code = self._run(["upgrade", "--project", str(target),
                          "--adopt-legacy", "--dry-run"])
        self.assertEqual(1, code, self.last_output)
        self.assertIn("BUILDER_LEGACY_PIN_MISMATCH", self.last_output)


if __name__ == "__main__":
    unittest.main()
