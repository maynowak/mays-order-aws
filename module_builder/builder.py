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
from module_builder.catalog import MODULE_REF_RE
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


# ---------- B1: Block-Splitter für freie Modulauswahl ----------

# Verdrahtungs-Flags ohne module.-Referenz, die dennoch nur mit einem
# bestimmten optionalen Modul sinnvoll sind (GAP-06): `sqs_enabled = true`
# steuert die SQS-IAM-Policy; ohne sqs-Modul muss das Gate AUS bleiben
# (Default false) und die Zeile wird entfernt.
OPTIONAL_MODULE_FLAGS = {"sqs_enabled": "sqs"}

BLOCK_HEADER_RE = re.compile(
    r'^(?P<kind>terraform|locals|provider|module|resource|moved|variable|output)\s*'
    r'(?P<names>(?:"[^"]*"\s*)+)?'
    r'\{'
)


def _split_blocks(text: str) -> List[Dict]:
    """Zerlegt eine .tf-Datei in Top-Level-Blöcke (inkl. vorangestellter
    Kommentar-Zeilen). Fail-closed: nicht geschlossene Blöcke sind ein Fehler.

    Rückgabe: Liste von dicts {kind, name, text} — name ist der erste
    Bezeichner in Anführungszeichen (module/output/variable) bzw. der
    Funktionsname bei provider/resource (z. B. "aws", "terraform_data.seed_orders").
    """
    blocks: List[Dict] = []
    pending: List[str] = []  # Kommentar-/Leerzeilen vor dem nächsten Block
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        match = BLOCK_HEADER_RE.match(line)
        if match is None:
            pending.append(line)
            i += 1
            continue
        kind = match.group("kind")
        quoted = re.findall(r'"([^"]*)"', match.group("names") or "")
        name = quoted[0] if quoted else ""
        depth = line.count("{") - line.count("}")
        block_lines = [line]
        i += 1
        while depth > 0:
            if i >= len(lines):
                _fail(
                    f"Block '{kind} {name}' in der Quelle nicht geschlossen "
                    f"(Brace-Matching) — Abbruch, nichts wird generiert."
                )
            depth += lines[i].count("{") - lines[i].count("}")
            block_lines.append(lines[i])
            i += 1
        block_text = "\n".join(block_lines)
        blocks.append(
            {
                "kind": kind,
                "name": name,
                "header": "\n".join(l for l in pending),
                "text": block_text,
            }
        )
        pending = []
    if pending and pending != [""]:
        blocks.append({"kind": "comment", "name": "", "header": "", "text": "\n".join(pending).strip("\n")})
    return blocks


def _render_blocks(blocks: List[Dict]) -> str:
    """Blöcke zu einer fmt-freundlichen Datei zusammenfügen (Ein Leerzeile dazwischen)."""
    parts = []
    for block in blocks:
        chunk = block["text"]
        header = block.get("header", "").strip("\n")
        if header.strip():
            chunk = header + "\n" + chunk
        parts.append(chunk)
    return "\n\n".join(parts) + "\n"


def _strip_unselected_module_inputs(block: Dict, selection: set) -> Dict:
    """PHASE2: Eingabe-Zeilen, die ein NICHT gewähltes optionales Modul
    referenzieren, entfernen (z. B. `sqs_queue_arn = module.sqs.queue_arn` im
    iam-Block bzw. `queue_url = module.sqs.queue_url` im lambda-Block).

    Sicher, weil: jede module.<x>-Referenz in einem Modulblock entweder auf
    eine Pflicht-Dep geht (per validate_selection_closure garantiert in der
    Auswahl) oder auf die optionale sqs-Dep — alle betroffenen Variablen
    haben Defaults (""), und das iam-Modul erzeugt ohne ARN keine
    sqs-Berechtigung. Nur Zuweisungen (`= module.<x>.`) werden entfernt —
    Kommentare und source-Zeilen bleiben unberührt.

    GAP-06: `sqs_enabled` ist eine Verdrahtungs-Flag OHNE module.-Referenz,
    die dennoch nur mit dem optionalen sqs-Modul sinnvoll ist. Ohne sqs in der
    Auswahl wird sie mit entfernt → IAM-Default `false`, keine SQS-Policy
    (sonst würde die ARN-Precondition beim Plan fehlschlagen).
    """
    from module_builder.catalog import MODULE_REF_RE

    lines = block["text"].split("\n")
    kept_lines = []
    for line in lines:
        assignment = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if assignment is not None:
            flag_owner = OPTIONAL_MODULE_FLAGS.get(assignment.group(1))
            if flag_owner is not None and flag_owner not in selection:
                continue
        if re.match(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*module\.", line):
            refs = set(MODULE_REF_RE.findall(line))
            if refs and not refs.issubset(selection):
                continue  # Wiring-Zeile auf nicht gewähltes optionales Modul entfernen
        kept_lines.append(line)
    new_block = dict(block)
    new_block["text"] = "\n".join(kept_lines).rstrip("\n")
    return new_block


def _filter_main_blocks(blocks: List[Dict], selection: set) -> List[Dict]:
    """Root-main.tf für die Auswahl filtern.

    - terraform → versions.tf (Aufrufer entnimmt ihn separat)
    - locals / provider → immer (Identität, default_tags)
    - module X → nur wenn X ausgewählt; PHASE2: Wiring-Zeilen auf nicht
      gewählte optionale Deps werden entfernt (siehe _strip_unselected_module_inputs)
    - resource/output/moved → nur wenn ALLE module.<x>-Referenzen ausgewählt sind
    """
    kept: List[Dict] = []
    for block in blocks:
        kind = block["kind"]
        if kind == "terraform":
            continue
        if kind in ("locals", "provider"):
            kept.append(block)
            continue
        if kind == "module":
            if block["name"] in selection:
                kept.append(_strip_unselected_module_inputs(block, selection))
            continue
        refs = set(MODULE_REF_RE.findall(block["text"]))
        if refs and refs.issubset(selection):
            kept.append(block)
        elif not refs:
            kept.append(block)
    return kept


def _filter_named_blocks(
    blocks: List[Dict], keep_names: set, kind: str
) -> List[Dict]:
    """variable-/output-Blöcke nach Namen bzw. Modul-Referenzen filtern."""
    from module_builder.catalog import MODULE_REF_RE

    kept: List[Dict] = []
    for block in blocks:
        if block["kind"] != kind:
            continue
        if kind == "variable":
            if block["name"] in keep_names:
                kept.append(block)
            continue
        refs = set(MODULE_REF_RE.findall(block["text"]))
        if not refs or refs.issubset(keep_names):
            kept.append(block)
    return kept


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


def sorted_module_catalog() -> List[str]:
    from module_builder.catalog import MODULE_CATALOG
    return sorted(MODULE_CATALOG)


def _render_readme(project_name: str, modules: Optional[List[str]] = None,
                   added: Optional[List[str]] = None) -> str:
    module_section = ""
    if modules is not None:
        module_section = (
            f"\n- **Ausgewählte Module (--modules):** {', '.join(sorted(modules))}\n"
            f"  Alle Pflichtabhängigkeiten sind Teil der Auswahl; der Builder\n"
            f"  ergänzt nichts automatisch, wenn `--with-deps` nicht gesetzt ist\n"
            f"  (bewusste B1-Regel)."
        )
        if added:
            module_section += (
                f"\n- **Automatisch ergänzte Pflichtabhängigkeiten (--with-deps):** "
                f"{', '.join(sorted(added))}"
            )
        if "sqs" not in modules and ({"iam", "lambda"} & set(modules)):
            module_section += (
                "\n- **SQS nicht ausgewählt (PHASE2):** Der Handler erhält KEINE\n"
                "  sqs-Berechtigung (count-gated) und arbeitet ohne Enqueue synchron\n"
                "  (POST /orders → 201, kein Worker-Kick). Bei Bedarf `sqs` (und für\n"
                "  asynchrone Verarbeitung `sqs_worker`) ergänzen."
            )
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
``{module_section}

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

## Policy-Gate (Pflicht vor jedem apply)

Das Projekt enthält das Policy-Gate (`terraform/policy/`): ein selbstenthaltenes,
offline lauffähiges Python-Prüfskript (stdlib-only) mit der zugehörigen
`resource-policy.json` — bereits auf **deinen Projektnamen `{project_name}`**
eingestellt (Namespace-, Regions-, Tag- und Ressourcenlimits).

```bash
cd terraform
terraform plan -out=tfplan                 # benötigt AWS-Credentials (read-only)
terraform show -json tfplan > tfplan.json
python3 policy/validate-plan.py tfplan.json
```

Exit-Codes: `0` = PASS · `1` = **FAIL** (Deployment blockieren, niemals umgehen) · `2` = Usage-Fehler.

Erzwungen werden u. a.: Region `eu-central-*`, Environment `Development`,
Pflicht-Tags (`Project`, `Maker`, `Environment`), Ressourcen-Typ-Allowlist,
Projekt-Namespace bei S3/IAM/API-GW/Cognito, PAY_PER_REQUEST-DynamoDB,
Lambda-Limits. Anpassungen der Policy sind eine bewusste Governance-Entscheidung
des Konsumenten — dokumentieren, nicht umgehen.
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
    modules: Optional[List[str]] = None,
    with_deps: bool = False,
) -> BuildResult:
    """Plan → verify → execute a build. Fail-closed; never mutates AWS.

    modules=None → Preset-Verhalten (complete, byte-identisch zum Foundation-Stand).
    modules=[...] → B1: freie Modulauswahl (fail-closed validiert, keine Ergänzung).
    with_deps=True → B2: fehlende Pflichtabhängigkeiten werden transitiv ergänzt
    (optionale Deps bleiben optional; B1-Fehler bleibt ohne Flag erhalten).
    """
    validate_project_name(project_name)
    preset = get_preset(preset_name)

    if source_root is None:
        source_root = Path(__file__).resolve().parents[1]
    source_root = Path(source_root).resolve()
    target_dir = Path(target_dir).resolve()

    # ---------- B1/B2: Auswahl-Plan berechnen ----------
    selection: Optional[set] = None
    requested: Optional[List[str]] = None
    added: List[str] = []
    module_dirs: List[str] = preset["modules"]
    keep_vars: Optional[set] = None
    artifacts: List[str] = preset["artifacts"]
    lambda_source: List[str] = preset["lambda_source"]
    backup_source: List[str] = preset.get("cognito_backup_source", [])
    seed_files: List[str] = preset["seed_files"]
    if modules is not None:
        from module_builder.catalog import (
            BACKUP_SOURCE_MODULES,
            BACKUP_ZIP_MODULES,
            LAMBDA_SOURCE_MODULES,
            LAMBDA_ZIP_MODULES,
            MODULE_CATALOG,
            SEED_MODULES,
            required_variables,
            resolve_with_deps,
            validate_module_names,
            validate_selection_closure,
        )
        requested = list(modules)
        validate_module_names(requested)
        if with_deps:
            modules, added = resolve_with_deps(requested)
        else:
            validate_selection_closure(requested)
        selection = set(modules)
        module_dirs = [MODULE_CATALOG[name]["dir"] for name in modules]
        keep_vars = required_variables(list(modules))
        artifacts = []
        if selection & LAMBDA_ZIP_MODULES:
            artifacts.append("lambda/dist/lambda.zip")
        if selection & BACKUP_ZIP_MODULES:
            artifacts.append("lambda/dist/cognito_backup.zip")
        lambda_source = (
            ["lambda/src", "lambda/build_zip.py"]
            if selection & LAMBDA_SOURCE_MODULES else []
        )
        backup_source = (
            ["cognito_backup", "lambda/cognito_backup_handler.py",
             "lambda/build_cognito_backup_zip.py"]
            if selection & BACKUP_SOURCE_MODULES else []
        )
        seed_files = preset["seed_files"] if selection & SEED_MODULES else []

    # ---------- Phase A: verify (no writes yet) ----------
    missing: List[str] = []
    if not (source_root / "terraform").is_dir():
        _fail(f"Quelle ungültig: kein terraform/ unter {source_root}")
    for name in preset["root_tf_files"]:
        if not (source_root / "terraform" / name).is_file():
            missing.append(f"terraform/{name}")
    for module in module_dirs:
        mod_dir = source_root / "terraform" / "modules" / module
        if not mod_dir.is_dir() or not any(mod_dir.glob("*.tf")):
            missing.append(f"terraform/modules/{module}/")
    for artifact in artifacts:
        if not (source_root / artifact).is_file():
            missing.append(artifact)
    for aux in lambda_source + backup_source + seed_files + preset["doc_files"] + preset["policy_files"]:
        if not (source_root / aux).exists():
            missing.append(aux)
    if missing:
        hint = ""
        if any("lambda/dist" in m for m in missing):
            hint = (
                "\nHinweis: Lambda-Artefakte fehlen — im Quell-Repo ausführen: "
                "cd lambda && python3 build_zip.py (lambda.zip) bzw. "
                "python3 build_cognito_backup_zip.py (cognito_backup.zip). "
                "Beide Builds sind deterministisch aus der Repo-Quelle reproduzierbar."
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

    # Child modules (allowlist *.tf + README.md) — nur die Auswahl
    for module in module_dirs:
        _copy_tf_tree(
            source_root / "terraform" / "modules" / module,
            target_dir / "terraform" / "modules" / module,
            written,
        )

    # Root wiring: terraform-Block → versions.tf; main.tf verbatim (Preset)
    # oder auswahlgefiltert (B1: nur gewählte Module, referenzkonforme
    # resource-/moved-Blöcke; locals/provider immer).
    main_tf_text = (source_root / "terraform" / "main.tf").read_text(encoding="utf-8")
    if selection is None:
        versions_block, main_rest = _extract_terraform_block(main_tf_text)
    else:
        blocks = _split_blocks(main_tf_text)
        terraform_blocks = [b for b in blocks if b["kind"] == "terraform"]
        if len(terraform_blocks) != 1:
            _fail("Erwartete genau einen terraform-Block in main.tf.")
        versions_block = terraform_blocks[0]["text"]
        main_rest = _render_blocks(_filter_main_blocks(blocks, selection))
    tf_dir = target_dir / "terraform"
    tf_dir.mkdir(parents=True, exist_ok=True)
    (tf_dir / "versions.tf").write_text(versions_block + "\n", encoding="utf-8")
    (tf_dir / "main.tf").write_text(main_rest, encoding="utf-8")
    written.append(str(tf_dir / "versions.tf"))
    written.append(str(tf_dir / "main.tf"))

    # variables.tf: Preset → komplett; B1 → nur erforderliche Variablen.
    # project_name-Default wird in beiden Wegen substituiert.
    variables_text = (source_root / "terraform" / "variables.tf").read_text(encoding="utf-8")
    if selection is not None:
        variables_text = _render_blocks(
            _filter_named_blocks(_split_blocks(variables_text), keep_vars, "variable")
        )
    variables_text = substitute_project_name(variables_text, project_name)
    (tf_dir / "variables.tf").write_text(variables_text, encoding="utf-8")
    written.append(str(tf_dir / "variables.tf"))

    # outputs.tf: Preset → verbatim; B1 → nur Outputs, deren Modul-Referenzen
    # vollständig in der Auswahl sind.
    if selection is None:
        _copy_file(
            source_root / "terraform" / "outputs.tf",
            tf_dir / "outputs.tf",
            written,
        )
    else:
        outputs_text = _render_blocks(
            _filter_named_blocks(
                _split_blocks((source_root / "terraform" / "outputs.tf").read_text(encoding="utf-8")),
                selection,
                "output",
            )
        )
        (tf_dir / "outputs.tf").write_text(outputs_text, encoding="utf-8")
        written.append(str(tf_dir / "outputs.tf"))

    # Reference documentation
    for doc in preset["doc_files"]:
        _copy_file(source_root / doc, target_dir / doc, written)

    # Example configuration
    (tf_dir / "terraform.tfvars.example").write_text(
        _render_tfvars_example(project_name), encoding="utf-8"
    )
    written.append(str(tf_dir / "terraform.tfvars.example"))

    # F2 (HARDENING-01): Policy-Gate übernehmen — validate-plan.py verbatim,
    # resource-policy.json mit dem Projektnamen des Konsumenten. POLICY_PATH
    # in validate-plan.py ist dateirelativ → das Paar funktioniert unverändert
    # an jedem Ort (research-befund). Fail-closed bleibt gewahrt: FAIL (Exit 1)
    # blockiert Deployments; das generierte README dokumentiert die Nutzung.
    policy_dir = tf_dir / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    for policy_file in preset["policy_files"]:
        dst = target_dir / policy_file
        if dst.name == "resource-policy.json":
            policy_json = json.loads(
                (source_root / policy_file).read_text(encoding="utf-8")
            )
            policy_json["project"] = project_name
            dst.write_text(
                json.dumps(policy_json, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            written.append(str(dst))
        else:
            _copy_file(source_root / policy_file, dst, written)

    # Lambda artifacts + source + seed tooling — nur bei Bedarf (B1)
    artifact_hashes: Dict[str, str] = {}
    for artifact in artifacts:
        src = source_root / artifact
        dst = target_dir / artifact
        _copy_file(src, dst, written)
        artifact_hashes[artifact] = _sha256(dst)
    for entry in lambda_source + backup_source + seed_files:
        src = source_root / entry
        if src.is_dir():
            for py_file in sorted(src.glob("*.py")):
                _copy_file(py_file, target_dir / entry / py_file.name, written)
        else:
            _copy_file(src, target_dir / entry, written)

    # Generated README
    readme = target_dir / "README.md"
    readme.write_text(
        _render_readme(project_name, modules, added), encoding="utf-8"
    )
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
        "preset": preset_name if selection is None else "custom",
        "modules": sorted(selection) if selection is not None else sorted_module_catalog(),
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
    if requested is not None:
        # B2-Transparenz: angefragte Auswahl vs. ergänzte Pflichtabhängigkeiten
        manifest["modules_requested"] = sorted(requested)
        manifest["modules_added"] = sorted(added)
    manifest_path = target_dir / "module-builder.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    return BuildResult(target=target_dir, files=written, artifacts=artifact_hashes)


# ---------------------------------------------------------------------------
# Orders-Service-Vertrag (MAYS-ORDERS-MODULE-CONTRACT-01): Modul-Generator
# ---------------------------------------------------------------------------

# EXTERNAL-Cognito (MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01): Im generierten
# Orders-Modul wählbare Cognito-Bereitstellungsart. Format abgeleitet aus dem
# bestehenden api-Modul (issuer = "https://${cognito_user_pool_endpoint}" —
# der Endpoint ist das Pool-endpoint-Attribut OHNE Scheme).
EXTERNAL_COGNITO_VARIABLE = '''
# Cognito-Bereitstellungsart (MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01):
# null (Default) = MANAGED: das Modul erstellt und verwaltet den eigenen
# Cognito User Pool + App Client + Gruppe "staff" (bisheriges Verhalten).
# Objekt gesetzt  = EXTERNAL: ein vorhandener Pool/Client des integrierenden
# Projekts wird verwendet; das Modul erzeugt KEINE Cognito-Ressourcen und
# verändert KEINE fremden Ressourcen. Der JWT-Authorizer bleibt in beiden
# Varianten aktiv (fail-closed: unvollständige Referenzen werden abgelehnt).
variable "external_cognito" {
  description = "Externe Cognito-Referenzen (EXTERNAL) oder null fuer eigenen Pool (MANAGED, Standard)."
  type = object({
    user_pool_endpoint = string # Pool-Endpoint OHNE Scheme (api-Modul ergaenzt https://)
    user_pool_client_id = string # App-Client-ID (Audience des JWT-Authorizers)
  })
  default = null

  validation {
    condition = var.external_cognito == null || (
      can(regex("^cognito-idp\\\\.[a-z0-9-]+\\\\.amazonaws\\\\.com/[a-zA-Z0-9_-]+$", var.external_cognito.user_pool_endpoint))
      && var.external_cognito.user_pool_client_id != ""
    )
    error_message = "external_cognito erfordert einen vollstaendigen user_pool_endpoint im Format 'cognito-idp.<region>.amazonaws.com/<pool-id>' (ohne https://) und eine nicht leere user_pool_client_id - unvollstaendige Referenzen werden fail-closed abgelehnt."
  }
}
'''

# Modus-sichere Output-Werte (EXTERNAL: managed-fremde Werte → null statt
# Verweis auf nicht existierende Instanzen; endpoint/client_id geben die
# tatsächlich verwendeten Referenzen zurück — semantisch übertragbar).
EXTERNAL_COGNITO_OUTPUT_REPLACEMENTS = [
    ("value       = module.cognito.user_pool_endpoint",
     "value       = local.cognito_endpoint"),
    ("value       = module.cognito.user_pool_client_id",
     "value       = local.cognito_client_id"),
    ("value       = module.cognito.user_pool_id",
     "value       = one(module.cognito[*].user_pool_id)"),
    ("value       = module.cognito.user_pool_arn",
     "value       = one(module.cognito[*].user_pool_arn)"),
    ("value       = module.cognito.user_pool_group_staff_name",
     "value       = one(module.cognito[*].user_pool_group_staff_name)"),
]

ORDERS_SERVICE_README_TEMPLATE = """# Mays-Order-AWS — Orders-Service Terraform-Modul

**Vertrag (MAYS-ORDERS-MODULE-CONTRACT-01):** Dieses Verzeichnis ist ein
vollständiges, wiederverwendbares Terraform-Modul, das den **Orders-Service**
bereitstellt. Feste Zusammensetzung (nicht abwählbar):

- Orders-API (HTTP API v2, JWT-Autorisierung) + Orders-Handler-Lambda
- Orders-Worker-Lambda (SQS-Consumer, Status-Verarbeitung)
- Orders-SQS-Queue (asynchrone Verarbeitung)
- Eigene Orders-DynamoDB-Tabelle (GSI1/GSI2)
- Erforderliche Orders-IAM-Rollen/Policies (Least Privilege; SQS-Berechtigung
  nur bei plan-bekanntem `sqs_enabled`-Gate — der Queue-ARN bleibt Policy-Resource)
- Cognito User Pool/Client/Gruppe `staff` (JWT-Grundlage der Orders-API)

Nicht Bestandteil des Vertrags (Verantwortung des integrierenden Projekts):
Monitoring, CloudTrail, Cognito-Backups, Seed-Daten, Remote-Backend,
Policy-Gate-Ausführung (Root-Ebene), externe Infrastruktur.

## Nutzung (lokales Modul)

```hcl
provider "aws" {{
  region = "eu-central-1" # Region liefert der Aufrufer — das Modul setzt keine Region
}}

module "orders" {{
  source = "../module/Mays-Order-AWS"

  project_name = "{project_name}"     # Pflicht (Ressourcen-Namen + Project-Tag)
  # tags                 = {{ ManagedBy = "terraform" }}  # optional
  # monitoring_enabled  = true                              # optional (Default true)
  # log_retention_days   = 7                                 # optional (Default 7)
}}

output "orders_api" {{
  value = module.orders.api_gateway_endpoint
}}
```

## Variablen (vollständiger Input-Vertrag)

| Variable | Typ | Default | Bedeutung |
|---|---|---|---|
| `project_name` | string | `"{project_name}"` | Präfix aller Orders-Ressourcen + `Project`-Tag |
| `tags` | map(string) | `{{}}` | Zusatz-Tags; `Maker`/`Environment` werden intern ergänzt (Tag-Parität zum Stamm-Deploy) |
| `monitoring_enabled` | bool | `true` | Log-Group/Retention-Steuerung in Lambda-/Worker-Modulen |
| `log_retention_days` | number | `7` | CloudWatch-Log-Retention |
| `external_cognito` | object | `null` | **MANAGED (Default/null):** eigener Pool + App Client + Gruppe `staff`. **EXTERNAL (Objekt):** vorhandener Pool des integrierenden Projekts — `user_pool_endpoint` (Format `cognito-idp.<region>.amazonaws.com/<pool-id>`, **ohne** `https://`) + `user_pool_client_id`. Fail-closed bei unvollständigen Referenzen. |

## Cognito-Varianten (MANAGED / EXTERNAL)

**MANAGED (Standard):** Ohne `external_cognito` erstellt das Modul seinen
eigenen Cognito User Pool + App Client + Gruppe `staff` — identisch zum
bisherigen Verhalten; JWT-Authorizer nutzt `https://<pool-endpoint>`.

**EXTERNAL:** Mit gültigem `external_cognito` verwendet das Modul den
vorhandenen Pool/Client; es werden **keine** Cognito-Ressourcen erzeugt und
**keine** fremden Ressourcen verändert. Der JWT-Authorizer bleibt aktiv
(issuer/audience aus den externen Referenzen).

```hcl
module "orders" {{
  source = "../module/Mays-Order-AWS"

  project_name = "{project_name}"
  external_cognito = {{
    user_pool_endpoint = "cognito-idp.eu-central-1.amazonaws.com/eu-central-1_XXXXXXX"
    user_pool_client_id = "1a2b3c4d5e6f7g8h9i0j1k2l3"
  }}
}}
```

**Outputs im EXTERNAL-Modus:** `cognito_user_pool_endpoint` und
`cognito_user_pool_client_id` geben die tatsächlich verwendeten externen
Referenzen zurück. `cognito_user_pool_id`, `cognito_user_pool_arn` und
`cognito_user_pool_group_name` sind `null` (vom Modul nicht verwaltet —
dokumentierte Inkompatibilität statt stiller Umdeutung; Lösungsvorschlag:
optionale Zusatzfelder im `external_cognito`-Objekt, freizugeben).

**Migration MANAGED → EXTERNAL (NICHT automatisiert):** Ein Wechsel eines
bestehenden Deployments führt zur geplanten Entfernung des verwalteten Pools
(inkl. Nutzer/Gruppen). Kontrollierter Wechsel erfordert: menschliche Freigabe,
Nutzer-/Gruppen-Migration in den Zitpool, bewusstes `terraform state rm` der
Cognito-Adressen oder Destruktion des Modul-Pools, anschließende EXTERNAL-
Konfiguration. Keine automatische Umschaltung/State-Migration durch das Modul.

## Outputs (vollständiger Output-Vertrag)

`dynamodb_table_name`, `dynamodb_table_arn`, `iam_handler_role_name`,
`iam_handler_role_arn`, `lambda_function_name`, `lambda_function_arn`,
`lambda_invoke_arn`, `cognito_user_pool_id`, `cognito_user_pool_arn`,
`cognito_user_pool_endpoint`, `cognito_user_pool_client_id`,
`cognito_user_pool_group_name`, `api_gateway_endpoint`, `api_gateway_id`,
`api_gateway_stage_name`, `api_gateway_authorizer_id`, `sqs_queue_url`,
`sqs_queue_arn`, `sqs_queue_name`, `sqs_worker_lambda_arn`

## Betriebs- und Vertragsnotizen

- **Artefakte:** `lambda/dist/lambda.zip` liegt im Modul (`${{path.module}}`),
  Rebuild über `cd lambda && python3 build_zip.py` (Quelle in `lambda/src/`).
- **Keine AWS-Dienste über den Orders-Service hinaus**; keine Provider-Region,
  kein Backend, keine Tags-Dritter im Modul.
- **Upgrades:** Adressen (`module.orders.*`) und Outputs bleiben stabil;
  Ressourcen-Identitäten/Naming-Konventionen unverändert. Nach einem Modul-
  Austausch prüft das integrierende Projekt seinen Plan (keine automatische
  State-Migration).
- **Governance:** Policy-Gate ist Root-Sache des Aufrufers; das MO-Gate liegt
  im Quell-Repo (`terraform/policy/`).
- **Privacy:** interne Privacy-Funktionen sind nicht produktiv aktiviert
  (BLOCKED — Secret-Management fehlt).
"""


def build_module(
    target_dir: Path,
    project_name: str,
    source_root: Optional[Path] = None,
    force: bool = False,
) -> BuildResult:
    """Orders-Service-Modul generieren (WP2–WP5, MAYS-ORDERS-MODULE-CONTRACT-01).

    Wiederverwendung der Foundation-Generatorfunktionen; feste 7-Modul-
    Zusammensetzung; Dateien liegen DIREKT im Zielordner (lokales Modul).
    """
    from module_builder.spec import ORDERS_SERVICE_MODULES, ORDERS_SERVICE_VARIABLES

    validate_project_name(project_name)
    if source_root is None:
        source_root = Path(__file__).resolve().parents[1]
    source_root = Path(source_root).resolve()
    target_dir = Path(target_dir).resolve()
    core = set(ORDERS_SERVICE_MODULES)

    # ---------- Phase A: verify ----------
    missing: List[str] = []
    if not (source_root / "terraform").is_dir():
        _fail(f"Quelle ungültig: kein terraform/ unter {source_root}")
    for name in ("main.tf", "variables.tf", "outputs.tf"):
        if not (source_root / "terraform" / name).is_file():
            missing.append(f"terraform/{name}")
    for module in ORDERS_SERVICE_MODULES:
        from module_builder.catalog import MODULE_CATALOG
        mod_dir = source_root / "terraform" / "modules" / MODULE_CATALOG[module]["dir"]
        if not mod_dir.is_dir() or not any(mod_dir.glob("*.tf")):
            missing.append(f"terraform/modules/{MODULE_CATALOG[module]['dir']}/")
    for artifact in ("lambda/dist/lambda.zip",) + tuple(
        ["lambda/src", "lambda/build_zip.py"]
    ):
        if not (source_root / artifact).exists():
            missing.append(artifact)
    if missing:
        _fail(
            "Erforderliche Quell-Bestandteile fehlen (fail-closed, nichts wurde "
            f"geschrieben):\n  - " + "\n  - ".join(missing)
        )
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        _fail(
            f"Zielordner ist nicht leer: {target_dir}\n"
            f"Bestehende Inhalte werden ohne --force nicht überschrieben."
        )

    # ---------- Phase B: execute ----------
    written: List[str] = []
    for module in ORDERS_SERVICE_MODULES:
        from module_builder.catalog import MODULE_CATALOG
        _copy_tf_tree(
            source_root / "terraform" / "modules" / MODULE_CATALOG[module]["dir"],
            target_dir / "modules" / MODULE_CATALOG[module]["dir"],
            written,
        )

    # main.tf: locals (erweitert um default_tags) + die 7 Modulblöcke mit
    # Modus-Transforms (path.module-Artefakte, Tag-Parität); versions.tf aus
    # dem terraform-Block. Provider-/Seed-/moved-/Nicht-Kern-Blöcke entfallen.
    main_tf_text = (source_root / "terraform" / "main.tf").read_text(encoding="utf-8")
    blocks = _split_blocks(main_tf_text)
    terraform_blocks = [b for b in blocks if b["kind"] == "terraform"]
    if len(terraform_blocks) != 1:
        _fail("Erwartete genau einen terraform-Block in main.tf.")
    locals_blocks = [b for b in blocks if b["kind"] == "locals"]
    if len(locals_blocks) != 1:
        _fail("Erwartete genau einen locals-Block in main.tf.")
    locals_text = locals_blocks[0]["text"].rstrip()
    if not locals_text.endswith("}"):
        _fail("locals-Block nicht korrekt geschlossen.")
    locals_text = (
        locals_text[:-1].rstrip("\n")
        + "\n\n  # Tag-Parität zum Stamm-Deploy (WP3): Maker/Environment bleiben"
        + "\n  # auch ohne Provider-default_tags an jeder Orders-Ressource."
        + "\n  default_tags = merge({ \"Maker\" = local.maker, \"Environment\" = local.environment }, var.tags)"
        + "\n\n  # Cognito-Bereitstellungsart (EXTERNAL-COGNITO-INTEGRATION-01):"
        + "\n  # MANAGED (external_cognito = null): eigener Pool (module.cognito count=1)."
        + "\n  # EXTERNAL (external_cognito gesetzt): vorhandener Pool; das Modul"
        + "\n  # erzeugt KEINE Cognito-Ressourcen (count=0, splat bleibt leer)."
        + "\n  # one() macht beide Zweige auswertungssicher (kein Index-Fehler)."
        + "\n  cognito_endpoint = var.external_cognito == null ? one(module.cognito[*].user_pool_endpoint) : var.external_cognito.user_pool_endpoint"
        + "\n  cognito_client_id = var.external_cognito == null ? one(module.cognito[*].user_pool_client_id) : var.external_cognito.user_pool_client_id"
        + "\n}"
    )
    kept_blocks = [{"kind": "locals", "name": "", "header": "", "text": locals_text}]
    for block in blocks:
        if block["kind"] != "module" or block["name"] not in core:
            continue
        text = block["text"]
        text = text.replace(
            "${path.root}/../lambda/dist/lambda.zip",
            "${path.module}/lambda/dist/lambda.zip",
        )
        text = re.sub(r"tags(\s*)=\s*var\.tags", r"tags\1= local.default_tags", text)
        if block["name"] == "cognito":
            # EXTERNAL-Variante: Pool nur im MANAGED-Modus instanziieren
            # (null = Default). Impliziter Terraform-Move module.cognito →
            # module.cognito[0] bei Bestandsupgrades (TF ≥1.3, dokumentiert).
            text = text.replace(
                'module "cognito" {',
                'module "cognito" {\n'
                '  count = var.external_cognito == null ? 1 : 0',
                1,
            )
        if block["name"] == "api":
            # JWT-Autorisierung bleibt in beiden Varianten aktiv; die Werte
            # stammen aus den locals (MANAGED: eigener Pool; EXTERNAL: Referenz).
            text = text.replace(
                "module.cognito.user_pool_endpoint", "local.cognito_endpoint"
            )
            text = text.replace(
                "module.cognito.user_pool_client_id", "local.cognito_client_id"
            )
        kept_blocks.append(dict(block, text=text))
    (target_dir / "versions.tf").write_text(
        terraform_blocks[0]["text"] + "\n", encoding="utf-8"
    )
    written.append(target_dir / "versions.tf")
    (target_dir / "main.tf").write_text(_render_blocks(kept_blocks), encoding="utf-8")
    written.append(target_dir / "main.tf")

    # variables.tf: auditierte 4 Vertrags-Eingaben + Projektnamen-Substitution
    variables_text = _render_blocks(
        _filter_named_blocks(
            _split_blocks(
                (source_root / "terraform" / "variables.tf").read_text(encoding="utf-8")
            ),
            set(ORDERS_SERVICE_VARIABLES),
            "variable",
        )
    )
    variables_text = substitute_project_name(variables_text, project_name)
    # EXTERNAL-Cognito-Vertragsvariable (generiert, nicht Stamm-Bestand):
    # null = MANAGED (Standard), Objekt = EXTERNAL; fail-closed-Validierung.
    variables_text = variables_text.rstrip("\n") + "\n" + EXTERNAL_COGNITO_VARIABLE
    (target_dir / "variables.tf").write_text(variables_text, encoding="utf-8")
    written.append(target_dir / "variables.tf")

    # outputs.tf: referenzgefilterte Quell-Outputs (die 3 neuen Vertrag-Outputs
    # sind in der Quelle enthalten und werden über den Filter automatisch
    # übernommen — refs: module.sqs / module.sqs_worker ∈ Kern).
    # EXTERNAL-Modus-Sicherheit: alle module.cognito-Werte werden auf
    # auswertungssichere Formen umgestellt (one(splat) / locals).
    outputs_text = _render_blocks(
        _filter_named_blocks(
            _split_blocks(
                (source_root / "terraform" / "outputs.tf").read_text(encoding="utf-8")
            ),
            core,
            "output",
        )
    )
    for old, new in EXTERNAL_COGNITO_OUTPUT_REPLACEMENTS:
        if old not in outputs_text:
            _fail(f"Erwarteter Output-Ausdruck fehlt in der Quelle: {old!r}")
        outputs_text = outputs_text.replace(old, new)
    (target_dir / "outputs.tf").write_text(outputs_text, encoding="utf-8")
    written.append(target_dir / "outputs.tf")

    # README (Vertrag + Nutzung + vollständige Variablen-/Output-Listen)
    readme = target_dir / "README.md"
    readme.write_text(
        ORDERS_SERVICE_README_TEMPLATE.format(project_name=project_name),
        encoding="utf-8",
    )
    written.append(readme)

    # Artefakte: lambda.zip + Quelle + Build-Skript (modulsrelativ, path.module)
    artifact_hashes: Dict[str, str] = {}
    _copy_file(
        source_root / "lambda/dist/lambda.zip",
        target_dir / "lambda/dist/lambda.zip",
        written,
    )
    artifact_hashes["lambda/dist/lambda.zip"] = _sha256(
        target_dir / "lambda/dist/lambda.zip"
    )
    _copy_file(source_root / "lambda/build_zip.py",
               target_dir / "lambda/build_zip.py", written)
    for py_file in sorted((source_root / "lambda/src").glob("*.py")):
        _copy_file(py_file, target_dir / "lambda/src" / py_file.name, written)

    # Manifest
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=source_root, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        commit = "unknown"
    manifest = {
        "builder_version": __version__,
        "preset": "orders-service",
        "modules": sorted(core),
        "project_name": project_name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"repo": "maynowak/mays-order-aws", "commit": commit},
        "artifacts_sha256": artifact_hashes,
        "files_written": sorted(str(Path(p).relative_to(target_dir)) for p in written),
        "notes": {
            "contract": "MAYS-ORDERS-MODULE-CONTRACT-01: fixed 7-module Orders-Service composition",
            "external_cognito": "runtime variable: null = MANAGED (own pool, default), object = EXTERNAL (existing pool, fail-closed validated)",
            "module_mode": "local Terraform module (no provider block, path.module artifacts)",
            "policy_gate": "root-level responsibility of the integrating project",
            "privacy_production_activation": "BLOCKED (secret management missing)",
            "aws_mutations_by_builder": "none",
        },
    }
    (target_dir / "module-builder.manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Deterministische Formatierung: terraform fmt (Write) fixt die Ausrichtung
    # der transformierten Zeilen; ohne terraform bleibt der Stand unformatiert
    # (dann scheitert --validate an fmt -check mit klarer Meldung).
    if shutil.which("terraform"):
        subprocess.run(
            ["terraform", "fmt", str(target_dir)],
            capture_output=True, text=True, timeout=120,
        )

    return BuildResult(target=target_dir, files=written, artifacts=artifact_hashes)
