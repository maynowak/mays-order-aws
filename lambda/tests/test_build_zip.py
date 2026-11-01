"""MO-RC4-P02I-C1 — Lambda-Artefakt: Vollständigkeit, Determinismus, Imports."""

import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import build_zip

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


class TestBuildZip(unittest.TestCase):
    def test_archive_contains_every_runtime_module(self):
        expected = sorted(path.name for path in SRC_DIR.glob("*.py"))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lambda.zip"
            build_zip.build(target)
            with zipfile.ZipFile(target) as archive:
                names = sorted(archive.namelist())
        self.assertEqual(names, expected)
        # Die vier Module, die im Audit fehlten, sind enthalten:
        for required in ("identity.py", "order_handlers.py",
                         "processing_result.py", "recovery.py"):
            self.assertIn(required, names)
        self.assertIn("index.py", names)
        self.assertIn("sqs_handler.py", names)

    def test_archive_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.zip"
            second = Path(tmp) / "b.zip"
            build_zip.build(first)
            build_zip.build(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_entries_use_fixed_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lambda.zip"
            build_zip.build(target)
            with zipfile.ZipFile(target) as archive:
                for info in archive.infolist():
                    self.assertEqual(info.date_time, build_zip.ZIP_DATE_TIME)

    def test_archive_contains_no_unexpected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lambda.zip"
            build_zip.build(target)
            with zipfile.ZipFile(target) as archive:
                for name in archive.namelist():
                    self.assertTrue(name.endswith(".py"), name)
                    self.assertNotIn("/", name)
                    self.assertNotIn("__pycache__", name)

    def test_handler_modules_import_from_extracted_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lambda.zip"
            build_zip.build(target)
            extract_dir = Path(tmp) / "unpacked"
            extract_dir.mkdir()
            with zipfile.ZipFile(target) as archive:
                archive.extractall(extract_dir)

            script = (
                "import index, sqs_handler, recovery, order_service, identity, "
                "order_handlers, processing_result; "
                "assert callable(index.handler); "
                "assert callable(sqs_handler.handler); "
                "assert callable(recovery.run_recovery); "
                "assert callable(recovery.run_processing_recovery); "
                "print('OK')"
            )
            env = dict(os.environ, PYTHONPATH=str(extract_dir))
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(extract_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
