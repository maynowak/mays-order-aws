"""Builder core: plan (fail-closed preflight) → copy → generate.

Safety model:
- Phase A (verify): ALL source inputs are checked BEFORE anything is written.
  Missing artifacts abort with a clear message — no partial target, no dummies.
- Phase B (execute): allowlisted copies only (*.tf, declared artifacts/sources,
  seed files). Nothing matching state/plan/lock patterns is ever copied.
- Target protection: an existing NON-EMPTY target is refused unless --force.
  With --force, only files owned by the builder are overwritten; foreign files
  remain untouched (the builder never deletes anything).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from module_builder import __version__
from module_builder.spec import get_preset

# Terraform-side project_name validation (mirrors terraform/variables.tf).
PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Never copied — regardless of where they appear.
FORBIDDEN_NAME_RE = re.compile(
    r"(^\.terraform)|(\.tfstate)|(\.tfplan)|(^tfplan)|(\.lock\.hcl$)|(^credentials)|(^\.env)"
)

TERRAFORM_BLOCK_RE = re.compile(r"^terraform\s*\{", re.MULTILINE)


def _fail(message: str) -> None:
    raise SystemExit(f"module-builder: FEHLER: {message}")


def validate_project_name(name: str) -> None:
    if not name or len(name) < 3 or not PROJECT_NAME_RE.match(name):
        _fail(
            f"Ungültiger Projektname '{name}': mind. 3 Zeichen, nur "
            f"Kleinbuchstaben, Ziffern und Bindestriche, kein führendes/"
            f"trailendes Sonderzeichen (identisch zur Terraform-Validierung)."
        )


def _extract_terraform_block(main_tf_text: str) -> tuple:
    """Split main.tf into (terraform-block, rest) via brace matching.

    The terraform block (required_version/providers) becomes versions.tf of
    the generated project; the remainder stays main.tf.
    """
    match = TERRAFORM_BLOCK_RE.search(main_tf_text)
    if match is None:
        _fail("main.tf enthält keinen terraform-Block (required_version/providers).")
    depth = 0
    i = match.start()
    while i < len(main_tf_text):
        if main_tf_text[i] == "{":
            depth += 1
        elif main_tf_text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                block = main_tf_text[match.start():end]
                rest = (main_tf_text[:match.start()] + main_tf_text[end:]).lstrip("\n")
                return block, rest
        i += 1
    _fail("terraform-Block in main.tf nicht korrekt geschlossen (Brace-Matching).")


def substitute_project_name(variables_tf_text: str, project_name: str) -> str:
    """Replace the default value inside variable "project_name"."""
    pattern = re.compile(
        r'(variable\s+"project_name"\s*\{[\s\S]*?default\s*=\s+)"mays-orders"'
    )
    new_text, count = pattern.subn(rf'\g<1>"{project_name}"', variables_tf_text, count=1)
    if count != 1:
        _fail(
            "Konnte den default-Wert von variable \"project_name\" in "
            "variables.tf nicht sicher ersetzen (Muster nicht gefunden)."
        )
    return new_text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_tf_tree(src_dir: Path, dst_dir: Path, written: List[str]) -> None:
    """Copy ONLY *.tf and README.md files (allowlist — secrets cannot slip in)."""
    for src_file in sorted(src_dir.iterdir()):
        if src_file.is_dir():
            continue
        if FORBIDDEN_NAME_RE.search(src_file.name):
            continue
        if src_file.suffix == ".tf" or src_file.name == "README.md":
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_dir / src_file.name)
            written.append(str((dst_dir / src_file.name)))


def _copy_file(src: Path, dst: Path, written: List[str]) -> None:
    if FORBIDDEN_NAME_RE.search(src.name):
        _fail(f"Verweigert: Kopieren von {src.name} (State-/Plan-/Lock-Muster).")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    written.append(str(dst))


def _render_readme(project_name: str) -> str:
    return f"""# {project_name} — Standalone Terraform Deployment

Generiert vom **Mays-Orders-AWS Module Builder** (Preset: `complete`).
Eigenständige Terraform-Bereitstellung — **keine Abhängigkeit zum Quell-Repository**
(Modul-Quellen sind relative Kopien unter `./terraform/modules/`).

## Layout

```text
{project_name}/
├── terraform/            # Root-Wiring + 11 Kindmodule (main, variables, outputs, versions)
├── lambda/
│   ├── src/              # Python-Quelle (Reproduzierbarkeit)
│   ├── dist/             # Lambda-Artefakte (lambda.zip, cognito_backup.zip)
│   └── build_zip.py      # Artefakt-Rebuild: cd lambda && python3 build_zip.py
├── database/seed/        # Demo-Seed (opt-in via var.seed_example_data)
└── scripts/seed_orders.py
```

## Quickstart (read-only Prüfung)

```bash
cd terraform
terraform init -backend=false
terraform validate
terraform plan   # erfordert AWS-Credentials + eigenes Backend
```

## Wichtige Hinweise

- **Backend:** Es wird KEIN Remote-Backend mitgeneriert (lokaler State).
  Für Produktion ein eigenes S3-Backend konfigurieren — niemals das Backend
  eines fremden Projekts verwenden.
- **Namen:** Alle Ressourcennamen leiten sich aus `project_name = "{project_name}"`
  ab (variables.tf) — Parallelinstallationen sind namenlich getrennt.
- **Freigaben:** `terraform apply`/`destroy` nur nach menschlicher Freigabe.
  Vor jedem Deployment Identität/Konto/Region prüfen.
- **Privacy:** Die internen Privacy-Funktionen sind **nicht produktiv aktiviert**
  (Secret-Management/Rotation fehlen) — Produktion Privacy Activation: **BLOCKED**.
- **Seed:** `seed_example_data = false` (Standard) — kein Demo-Import.
- **Provenance:** Siehe `module-builder.manifest.json` (Dateien + Artefakt-Hashes).
"""


def _render_tfvars_example(project_name: str) -> str:
    return f"""# Beispiel-Konfiguration — nach terraform.tfvars kopieren und anpassen.
# project_name ist bereits als Default in variables.tf gesetzt ({project_name}).

# aws_region      = "eu-central-1"
# seed_example_data = false
# enable_cognito_backup           = true
# enable_cognito_backup_automation = true
# monitoring_enabled = true
# tags = {{
#   ManagedBy = "terraform"
# }}
"""


class BuildResult:
    def __init__(self, target: Path, files: List[str], artifacts: Dict[str, str]):
        self.target = target
        self.files = files
        self.artifacts = artifacts


def build(
    target_dir: Path,
    project_name: str,
    preset_name: str = "complete",
    source_root: Optional[Path] = None,
    force: bool = False,
) -> BuildResult:
    """Plan → verify → execute a build. Fail-closed; never mutates AWS."""
    validate_project_name(project_name)
    preset = get_preset(preset_name)

    if source_root is None:
        source_root = Path(__file__).resolve().parents[1]
    source_root = Path(source_root).resolve()
    target_dir = Path(target_dir).resolve()

    # ---------- Phase A: verify (no writes yet) ----------
    missing: List[str] = []
    if not (source_root / "terraform").is_dir():
        _fail(f"Quelle ungültig: kein terraform/ unter {source_root}")
    for name in preset["root_tf_files"]:
        if not (source_root / "terraform" / name).is_file():
            missing.append(f"terraform/{name}")
    for module in preset["modules"]:
        mod_dir = source_root / "terraform" / "modules" / module
        if not mod_dir.is_dir() or not any(mod_dir.glob("*.tf")):
            missing.append(f"terraform/modules/{module}/")
    for artifact in preset["artifacts"]:
        if not (source_root / artifact).is_file():
            missing.append(artifact)
    for aux in preset["lambda_source"] + preset["seed_files"] + preset["doc_files"]:
        if not (source_root / aux).exists():
            missing.append(aux)
    if missing:
        hint = ""
        if any("lambda/dist" in m for m in missing):
            hint = (
                "\nHinweis: Lambda-Artefakte fehlen — im Quell-Repo ausführen: "
                "cd lambda && python3 build_zip.py (betrifft lambda.zip). "
                "cognito_backup.zip muss aus der bestehenden Freigabe vorliegen."
            )
        _fail(
            "Erforderliche Quell-Bestandteile fehlen (fail-closed, nichts wurde "
            f"geschrieben):\n  - " + "\n  - ".join(missing) + hint
        )

    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        _fail(
            f"Zielordner ist nicht leer: {target_dir}\n"
            f"Bestehende Inhalte werden ohne --force nicht überschritten "
            f"(--force überschreibt nur Builder-eigene Dateien, löscht nichts)."
        )

    # ---------- Phase B: execute ----------
    written: List[str] = []

    # Child modules (allowlist *.tf + README.md)
    for module in preset["modules"]:
        _copy_tf_tree(
            source_root / "terraform" / "modules" / module,
            target_dir / "terraform" / "modules" / module,
            written,
        )

    # Root wiring: split terraform block → versions.tf, rest → main.tf
    main_tf_text = (source_root / "terraform" / "main.tf").read_text(encoding="utf-8")
    versions_block, main_rest = _extract_terraform_block(main_tf_text)
    tf_dir = target_dir / "terraform"
    tf_dir.mkdir(parents=True, exist_ok=True)
    (tf_dir / "versions.tf").write_text(versions_block + "\n", encoding="utf-8")
    (tf_dir / "main.tf").write_text(main_rest, encoding="utf-8")
    written.append(str(tf_dir / "versions.tf"))
    written.append(str(tf_dir / "main.tf"))

    # variables.tf with substituted project_name default
    variables_text = (source_root / "terraform" / "variables.tf").read_text(encoding="utf-8")
    variables_text = substitute_project_name(variables_text, project_name)
    (tf_dir / "variables.tf").write_text(variables_text, encoding="utf-8")
    written.append(str(tf_dir / "variables.tf"))

    # outputs.tf verbatim
    _copy_file(
        source_root / "terraform" / "outputs.tf",
        tf_dir / "outputs.tf",
        written,
    )

    # Reference documentation
    for doc in preset["doc_files"]:
        _copy_file(source_root / doc, target_dir / doc, written)

    # Example configuration
    (tf_dir / "terraform.tfvars.example").write_text(
        _render_tfvars_example(project_name), encoding="utf-8"
    )
    written.append(str(tf_dir / "terraform.tfvars.example"))

    # Lambda artifacts + source + seed tooling
    artifact_hashes: Dict[str, str] = {}
    for artifact in preset["artifacts"]:
        src = source_root / artifact
        dst = target_dir / artifact
        _copy_file(src, dst, written)
        artifact_hashes[artifact] = _sha256(dst)
    for entry in preset["lambda_source"] + preset["seed_files"]:
        src = source_root / entry
        if src.is_dir():
            for py_file in sorted(src.glob("*.py")):
                _copy_file(py_file, target_dir / entry / py_file.name, written)
        else:
            _copy_file(src, target_dir / entry, written)

    # Generated README
    readme = target_dir / "README.md"
    readme.write_text(_render_readme(project_name), encoding="utf-8")
    written.append(str(readme))

    # Build manifest (provenance, written last)
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=source_root, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        commit = "unknown"
    manifest = {
        "builder_version": __version__,
        "preset": preset_name,
        "project_name": project_name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"repo": "maynowak/mays-order-aws", "commit": commit},
        "artifacts_sha256": artifact_hashes,
        "files_written": sorted(str(Path(p).relative_to(target_dir)) for p in written),
        "notes": {
            "backend": "not included — configure your own remote backend",
            "privacy_production_activation": "BLOCKED (secret management missing)",
            "aws_mutations_by_builder": "none",
        },
    }
    manifest_path = target_dir / "module-builder.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    return BuildResult(target=target_dir, files=written, artifacts=artifact_hashes)
