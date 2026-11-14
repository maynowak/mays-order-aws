#!/usr/bin/env python3
"""Build the deployment ZIP for the May's Orders Lambda (Python 3.14).

Output: dist/lambda.zip — contains the Python source modules at the ZIP root
(handler entry: index.handler). Boto3 is provided by the AWS Lambda runtime,
so no third-party dependencies are bundled (no requirements.txt needed).

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

MODULES = sorted(
    path.name for path in SRC_DIR.glob("*.py") if not path.name.startswith("_")
)

# Deterministic archive metadata: the ZIP must not depend on checkout mtimes.
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
FIXED_FILE_MODE = 0o644 << 16


def build() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for module in MODULES:
            source = SRC_DIR / module
            if not source.exists():
                raise FileNotFoundError(f"Missing source module: {source}")
            info = zipfile.ZipInfo(module, date_time=FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = FIXED_FILE_MODE
            # Normalise line endings: the same commit checks out as CRLF under
            # core.autocrlf=true and as LF otherwise. Python accepts both, but
            # the packaged bytes (and therefore the artifact hash) must not
            # depend on the builder's git configuration.
            payload = source.read_bytes().replace(b"\r\n", b"\n")
            archive.writestr(info, payload)

    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes, sha256 {digest})")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for info in archive.infolist():
            print(f"  {info.filename}  ({info.file_size} bytes)")


if __name__ == "__main__":
    build()