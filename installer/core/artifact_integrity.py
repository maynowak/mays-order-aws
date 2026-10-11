"""
Lambda Artifact Integrity — Staleness-Erkennung für das Deployment-ZIP.

Stellt sicher, dass dist/lambda.zip exakt dem freigegebenen Quellcode in
src/ entspricht, bevor ein Deployment geplant/gestartet wird (Vorfall:
stale ZIP vom 18.09. ohne Fix 50efac4 wurde deployed).

Keine neue Pipeline: reine Lese-Prüfung, eingebunden in ValidationLayer.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Optional, Tuple


def verify_lambda_zip(lambda_dir: str | Path) -> Tuple[bool, str]:
    """Prüft dist/lambda.zip gegen src/.

    Returns:
        (True, message) wenn das ZIP jedes src/*.py byte-identisch enthält
        (False, Grund) bei fehlendem ZIP, fehlenden/abweichenden Modulen
        oder zusätzlichem Inhalt.
    """
    lambda_dir = Path(lambda_dir)
    src_dir = lambda_dir / "src"
    zip_path = lambda_dir / "dist" / "lambda.zip"

    if not src_dir.is_dir():
        return False, f"Lambda source directory missing: {src_dir}"
    if not zip_path.is_file():
        return False, (
            f"Lambda artifact missing: {zip_path} — "
            f"build with: cd {lambda_dir} && python3 build_zip.py"
        )

    expected = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(src_dir.glob("*.py"))
    }
    if not expected:
        return False, f"No Python modules found in {src_dir}"

    try:
        with zipfile.ZipFile(zip_path) as archive:
            archived = {}
            for info in archive.infolist():
                name = Path(info.filename).name
                if info.is_dir():
                    continue
                archived[name] = hashlib.sha256(archive.read(info.filename)).hexdigest()
    except zipfile.BadZipFile:
        return False, f"Lambda artifact is not a valid ZIP: {zip_path}"

    missing = sorted(set(expected) - set(archived))
    if missing:
        return False, f"Lambda artifact stale, missing modules: {missing}"

    extra = sorted(set(archived) - set(expected))
    if extra:
        return False, f"Lambda artifact contains unexpected files: {extra}"

    stale = sorted(name for name in expected if expected[name] != archived[name])
    if stale:
        return False, (
            f"Lambda artifact stale, rebuild required "
            f"(cd {lambda_dir} && python3 build_zip.py): {stale}"
        )

    return True, f"Lambda artifact current ({len(expected)} modules)"


def lambda_dir_for_context(terraform_dir: str | Path) -> Optional[Path]:
    """Leitet das Lambda-Verzeichnis aus dem Terraform-Verzeichnis ab."""
    candidate = Path(terraform_dir).parent / "lambda"
    if (candidate / "src").is_dir():
        return candidate
    candidate = Path(terraform_dir) / ".." / "lambda"
    resolved = candidate.resolve()
    if (resolved / "src").is_dir():
        return resolved
    return None
