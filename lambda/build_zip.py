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

MODULES = [
    "index.py",
    "order_service.py",
    "state_machine.py",
    "validation.py",
    "errors.py",
    "order_types.py",
]


def build() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for module in MODULES:
            source = SRC_DIR / module
            if not source.exists():
                raise FileNotFoundError(f"Missing source module: {source}")
            archive.write(source, arcname=module)

    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes, sha256 {digest})")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        for info in archive.infolist():
            print(f"  {info.filename}  ({info.file_size} bytes)")


if __name__ == "__main__":
    build()