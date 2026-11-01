#!/usr/bin/env python3
"""Build the deployment ZIP for the May's Orders Lambda (Python 3.14).

Output: dist/lambda.zip — contains ALL Python source modules from `src/` at the
ZIP root (handler entry: index.handler). Boto3 is provided by the AWS Lambda
runtime, so no third-party dependencies are bundled (no requirements.txt).

Determinism (MO-RC4-P02I-C1):
- modules are taken from a sorted glob of `src/*.py` (no hand-maintained list —
  a new module can never be forgotten again),
- ZIP entries use a FIXED timestamp (1980-01-01) and fixed permissions, so the
  archive bytes are reproducible for identical sources.

Usage:
    cd lambda && python3 build_zip.py
"""
from __future__ import annotations

import hashlib
import pathlib
import zipfile

SRC_DIR = pathlib.Path(__file__).resolve().parent / "src"
DIST_DIR = pathlib.Path(__file__).resolve().parent / "dist"
ZIP_PATH = DIST_DIR / "lambda.zip"

# Fixed timestamp → deterministic archive (reproducible-builds convention).
ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)

# Entry points that must always be present in the deployment package.
REQUIRED_MODULES = ("index.py", "sqs_handler.py")


def runtime_modules() -> list[pathlib.Path]:
    """All runtime modules, deterministically sorted (no caches, no secrets)."""
    return sorted(
        (path for path in SRC_DIR.glob("*.py") if path.is_file()),
        key=lambda path: path.name,
    )


def build(zip_path: pathlib.Path = ZIP_PATH) -> None:
    modules = runtime_modules()
    if not modules:
        raise FileNotFoundError(f"No Python modules found in {SRC_DIR}")

    present = {module.name for module in modules}
    missing_required = [name for name in REQUIRED_MODULES if name not in present]
    if missing_required:
        raise FileNotFoundError(
            f"Missing required handler module(s) in {SRC_DIR}: {missing_required}"
        )

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for source in modules:
            info = zipfile.ZipInfo(source.name, date_time=ZIP_DATE_TIME)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"Built {zip_path} ({zip_path.stat().st_size} bytes, sha256 {digest})")
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            print(f"  {info.filename}  ({info.file_size} bytes)")


if __name__ == "__main__":
    build()
