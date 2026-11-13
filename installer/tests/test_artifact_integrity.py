import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from installer.core.artifact_integrity import verify_lambda_zip


# Handler-Module sind in jedem gueltigen Artefakt Pflicht (MO-RC4-P02I-C1).
DEFAULT_MODULES = {
    "index.py": "def handler(event, context):\n    return {}\n",
    "sqs_handler.py": "def handler(event, context):\n    return {}\n",
}


def _stage(modules=None, *, omit=(), archive_modules=None):
    merged = dict(DEFAULT_MODULES)
    merged.update(modules or {})
    for name in omit:
        merged.pop(name, None)
    tmp = TemporaryDirectory()
    root = Path(tmp.name)
    (root / "src").mkdir()
    (root / "dist").mkdir()
    for name, content in merged.items():
        (root / "src" / name).write_text(content)
    entries = merged if archive_modules is None else archive_modules
    with zipfile.ZipFile(root / "dist" / "lambda.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in entries.items():
            z.writestr(name, content)
    return tmp, root


class TestArtifactIntegrity(unittest.TestCase):
    def test_fresh_artifact_passes(self):
        tmp, root = _stage({"index.py": "x = 1\n", "errors.py": "y = 2\n"})
        try:
            ok, msg = verify_lambda_zip(root)
            self.assertTrue(ok, msg)
        finally:
            tmp.cleanup()

    def test_modified_source_detected(self):
        tmp, root = _stage({"index.py": "x = 1\n"})
        try:
            (root / "src" / "index.py").write_text("x = 2\n")
            ok, msg = verify_lambda_zip(root)
            self.assertFalse(ok)
            self.assertIn("stale", msg)
            self.assertIn("index.py", msg)
        finally:
            tmp.cleanup()

    def test_missing_module_detected(self):
        tmp, root = _stage({"index.py": "x = 1\n"})
        try:
            (root / "src" / "new_mod.py").write_text("z = 3\n")
            ok, msg = verify_lambda_zip(root)
            self.assertFalse(ok)
            self.assertIn("new_mod.py", msg)
        finally:
            tmp.cleanup()

    def test_missing_zip_detected(self):
        tmp, root = _stage({"index.py": "x = 1\n"})
        try:
            (root / "dist" / "lambda.zip").unlink()
            ok, msg = verify_lambda_zip(root)
            self.assertFalse(ok)
            self.assertIn("build_zip.py", msg)
        finally:
            tmp.cleanup()

    def test_empty_zip_detected(self):
        tmp, root = _stage(archive_modules={})
        try:
            ok, msg = verify_lambda_zip(root)
            self.assertFalse(ok)
            self.assertIn("missing modules", msg)
        finally:
            tmp.cleanup()

    def test_missing_handler_module_detected(self):
        tmp, root = _stage(omit=("sqs_handler.py",))
        try:
            ok, msg = verify_lambda_zip(root)
            self.assertFalse(ok)
            self.assertIn("Missing handler module", msg)
            self.assertIn("sqs_handler.py", msg)
        finally:
            tmp.cleanup()

    def test_corrupt_zip_detected(self):
        tmp, root = _stage()
        try:
            (root / "dist" / "lambda.zip").write_bytes(b"not a zip")
            ok, msg = verify_lambda_zip(root)
            self.assertFalse(ok)
            self.assertIn("not a valid ZIP", msg)
        finally:
            tmp.cleanup()

    def test_real_repo_artifact_current(self):
        repo_lambda = Path(__file__).resolve().parents[2] / "lambda"
        ok, msg = verify_lambda_zip(repo_lambda)
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
