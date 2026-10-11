import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from installer.core.artifact_integrity import verify_lambda_zip


def _stage(modules):
    tmp = TemporaryDirectory()
    root = Path(tmp.name)
    (root / "src").mkdir()
    (root / "dist").mkdir()
    for name, content in modules.items():
        (root / "src" / name).write_text(content)
    with zipfile.ZipFile(root / "dist" / "lambda.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in modules.items():
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

    def test_real_repo_artifact_current(self):
        repo_lambda = Path(__file__).resolve().parents[2] / "lambda"
        ok, msg = verify_lambda_zip(repo_lambda)
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
