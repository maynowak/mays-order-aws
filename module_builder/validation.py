"""Optional terraform validation for generated projects (--validate flag).

Runs read-only checks only:
    terraform fmt -check → terraform init -backend=false → terraform validate

NO apply, NO destroy, NO AWS mutations (init -backend=false + validate never
touch AWS). Fail-closed if the terraform CLI is missing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class ValidationError(SystemExit):
    pass


def _run(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)


def validate_generated_project(terraform_dir: Path) -> None:
    """Run fmt -check, init -backend=false and validate; raise on failure."""
    terraform_dir = Path(terraform_dir).resolve()
    if not (terraform_dir / "main.tf").is_file():
        raise ValidationError(f"Kein main.tf unter {terraform_dir}")

    if shutil.which("terraform") is None:
        raise ValidationError(
            "--validate angefordert, aber 'terraform' ist nicht im PATH "
            "(fail-closed; ohne terraform CLI keine Validierung möglich)."
        )

    steps = [
        (["terraform", "fmt", "-check"], "terraform fmt -check"),
        (["terraform", "init", "-backend=false"], "terraform init -backend=false"),
        (["terraform", "validate"], "terraform validate"),
    ]
    for cmd, label in steps:
        result = _run(cmd, terraform_dir)
        if result.returncode != 0:
            tail = (result.stdout + result.stderr).strip()[-800:]
            raise ValidationError(
                f"Validierungsschritt fehlgeschlagen: {label}\n--- terraform output ---\n{tail}"
            )
