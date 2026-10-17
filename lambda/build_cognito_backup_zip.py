#!/usr/bin/env python3
"""Build the deployment ZIP for the Cognito User Data Backup Lambda.

Output: dist/cognito_backup.zip — handler at the ZIP root
(entry: cognito_backup_handler.handler) plus the `cognito_backup` package.
Boto3 is provided by the AWS Lambda runtime (stdlib-only packaging).

Reproducibility (MAYS-ORDERS-MODULE-BUILDER-HARDENING-01, F1):
- All runtime sources live in this repository: this script, the handler at
  `lambda/cognito_backup_handler.py` and the package at `<repo-root>/cognito_backup/`.
- Zip entries use a FIXED timestamp (1980-01-01) → identical sha256 on every
  rebuild, in the source repo AND in module-builder generated projects.
- `__pycache__/` and `tests/` are deliberately NOT packaged (the historical
  artifact 492b0c54… accidentally contained .pyc files; runtime content is
  byte-identical, see HARDENING-01 report).

Usage:
    cd lambda && python3 build_cognito_backup_zip.py
"""
from __future__ import annotations

import hashlib
import pathlib
import zipfile

LAMBDA_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = LAMBDA_DIR.parent
DIST_DIR = LAMBDA_DIR / "dist"
ZIP_PATH = DIST_DIR / "cognito_backup.zip"
PACKAGE_DIR = REPO_ROOT / "cognito_backup"
PACKAGE_ROOT = PACKAGE_DIR
HANDLER = LAMBDA_DIR / "cognito_backup_handler.py"

# Fixed timestamp → deterministic archive (reproducible-builds convention).
ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)

EXCLUDED_DIRS = {"__pycache__", "tests"}


def _package_files() -> list:
    if not PACKAGE_DIR.is_dir():
        raise FileNotFoundError(f"Missing package directory: {PACKAGE_DIR}")
    files = []
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(PACKAGE_ROOT).parts):
            continue
        files.append((path, f"cognito_backup/{path.relative_to(PACKAGE_ROOT).as_posix()}"))
    return files


def build() -> None:
    if not HANDLER.is_file():
        raise FileNotFoundError(f"Missing handler: {HANDLER}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    entries = [(HANDLER, "cognito_backup_handler.py")] + _package_files()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, arcname in entries:
            info = zipfile.ZipInfo(arcname, date_time=ZIP_DATE_TIME)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())

    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes, sha256 {digest})")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for info in archive.infolist():
            print(f"  {info.filename}  ({info.file_size} bytes)")


if __name__ == "__main__":
    build()
