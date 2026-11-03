"""MO-BUILDER-UPGRADE-P2-01: Sicherer Upgrade-Modus fuer Builder-Projekte.

Der Builder erkennt bestehende, von ihm erzeugte Projekte, vergleicht den
vorhandenen Bestand mit einer neu generierten Version und wendet nur sichere
Aenderungen an. Der Installer bleibt fuer die Infrastruktur zustaendig.

Sicherheit:
- Kein Schreiben ausserhalb des Projektverzeichnisses.
- Keine Aenderung von Benutzerdateien/-konfigurationen (tfvars/.env/...).
- Keine automatische Loeschung veralteter Dateien.
- Konflikte blockieren; das Manifest wird nur nach erfolgreichem Apply ersetzt.
- Keine Geheimnisse oder vollstaendigen Dateiinhalte im Manifest/Bericht.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

MANIFEST_NAME = "module-builder.manifest.json"
MANIFEST_SCHEMA_VERSION = 2
RUN_DIR = ".mays-builder/runs"
REPORT_JSON = "builder-upgrade-report.json"
REPORT_MD = "builder-upgrade-report.md"

NEW_PROJECT = "NEW_PROJECT"
MANAGED_PROJECT = "MANAGED_PROJECT"
LEGACY_PROJECT = "LEGACY_PROJECT"
UNVERIFIED_PROJECT = "UNVERIFIED_PROJECT"
CONFLICTED_PROJECT = "CONFLICTED_PROJECT"

UNCHANGED = "UNCHANGED"
ADD = "ADD"
UPDATE_SAFE = "UPDATE_SAFE"
USER_MODIFIED = "USER_MODIFIED"
USER_OWNED = "USER_OWNED"
REMOVE_CANDIDATE = "REMOVE_CANDIDATE"
CONFLICT = "CONFLICT"

READY = "READY"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
BLOCKED = "BLOCKED"
NO_CHANGES = "NO_CHANGES"

CODE_READY = "BUILDER_UPGRADE_READY"
CODE_CONFLICT = "BUILDER_UPGRADE_CONFLICT"
CODE_UNVERIFIED = "BUILDER_PROJECT_UNVERIFIED"
CODE_LEGACY = "BUILDER_LEGACY_REVIEW_REQUIRED"
CODE_NO_CHANGES = "BUILDER_UPGRADE_NO_CHANGES"

_SKIP_DIRS = {".git", ".terraform", ".mays-builder", "__pycache__"}
_SKIP_SUFFIXES = {".tfstate", ".tfstate.backup", ".tfplan"}
_USER_CONFIG_SUFFIXES = (".tfvars", ".auto.tfvars")


class BuilderUpgradeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_user_config(rel: str) -> bool:
    parts = PurePosixPath(rel).parts
    name = parts[-1] if parts else ""
    if any(part in _SKIP_DIRS for part in parts):
        return True
    if any(part.startswith(".env") for part in parts):
        return True
    if name.endswith(_USER_CONFIG_SUFFIXES):
        return True
    if name.endswith(tuple(_SKIP_SUFFIXES)):
        return True
    if name == MANIFEST_NAME:
        return True
    return False


def _iter_files(root: Path) -> List[str]:
    files: List[str] = []
    if not root.exists():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = PurePosixPath(rel).parts
        if any(part in _SKIP_DIRS for part in parts):
            continue
        if path.name.endswith(tuple(_SKIP_SUFFIXES)):
            continue
        files.append(rel)
    return files


def _is_within(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_target(project_root: Path, rel: str) -> Path:
    """Validiert einen Manifest-/Zielpfad und liefert das Ziel (fail-closed)."""
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts or not rel:
        raise BuilderUpgradeError(CODE_CONFLICT, f"Unsafe path in manifest: {rel!r}")
    current = project_root
    for part in pure.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise BuilderUpgradeError(
                CODE_CONFLICT, f"Symlink im Zielpfad nicht erlaubt: {rel!r}"
            )
    target = project_root / rel
    if not _is_within(project_root, target.parent):
        raise BuilderUpgradeError(
            CODE_CONFLICT, f"Zielpfad ausserhalb des Projekts: {rel!r}"
        )
    return target


def read_manifest(project_dir: Path) -> Tuple[Optional[dict], str]:
    path = project_dir / MANIFEST_NAME
    if not path.exists():
        return None, "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"invalid: {exc}"
    if not isinstance(data, dict):
        return None, "invalid: not an object"
    return data, "ok"


def detect_project_status(
    project_dir: Path, expected_project_name: Optional[str] = None
) -> Tuple[str, Optional[dict], List[str]]:
    reasons: List[str] = []
    if not project_dir.exists():
        return NEW_PROJECT, None, ["Projektverzeichnis existiert nicht."]

    data, state = read_manifest(project_dir)
    if state == "missing":
        if any(project_dir.iterdir()):
            return UNVERIFIED_PROJECT, None, [
                "Verzeichnis ist nicht leer, aber es fehlt ein Builder-Manifest."
            ]
        return NEW_PROJECT, None, ["Leeres Verzeichnis."]
    if state.startswith("invalid"):
        return UNVERIFIED_PROJECT, None, [f"Builder-Manifest unlesbar: {state}."]

    project_name = data.get("project_name")
    if not isinstance(project_name, str) or not project_name:
        return CONFLICTED_PROJECT, data, ["Manifest ohne gueltigen project_name."]
    if expected_project_name and expected_project_name != project_name:
        return CONFLICTED_PROJECT, data, [
            f"Projektname im Manifest ({project_name}) weicht von der Anfrage "
            f"({expected_project_name}) ab."
        ]

    version = data.get("manifest_version")
    files = data.get("files")
    if version != MANIFEST_SCHEMA_VERSION or not isinstance(files, dict) or not files:
        return LEGACY_PROJECT, data, [
            "Builder-Manifest ohne Datei-Fingerprints (Legacy-Format); "
            "eine automatische Uebernahme ist nicht zulaessig."
        ]

    for rel in files:
        try:
            safe_target(project_dir, rel)
        except BuilderUpgradeError as exc:
            return CONFLICTED_PROJECT, data, [str(exc)]

    return MANAGED_PROJECT, data, reasons


@dataclass
class DiffEntry:
    path: str
    category: str
    reason: str
    expected_sha: Optional[str] = None
    actual_sha: Optional[str] = None
    new_sha: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "category": self.category,
            "reason": self.reason,
            "expectedSha256": self.expected_sha,
            "actualSha256": self.actual_sha,
            "newSha256": self.new_sha,
        }


@dataclass
class DiffResult:
    entries: List[DiffEntry] = field(default_factory=list)
    config_preserved: List[str] = field(default_factory=list)
    new_parameters: List[str] = field(default_factory=list)
    removed_parameters: List[str] = field(default_factory=list)

    def by_category(self, category: str) -> List[DiffEntry]:
        return [entry for entry in self.entries if entry.category == category]

    @property
    def conflicts(self) -> List[DiffEntry]:
        return self.by_category(CONFLICT)

    @property
    def writes(self) -> List[DiffEntry]:
        return self.by_category(ADD) + self.by_category(UPDATE_SAFE)


def _variable_names(path: Path) -> List[str]:
    if not path.exists():
        return []
    import re

    return re.findall(r'^\s*variable\s+"([^"]+)"', path.read_text(encoding="utf-8"), re.MULTILINE)


def diff_project(project_dir: Path, new_tree_dir: Path, manifest: dict) -> DiffResult:
    managed: Dict[str, str] = {
        str(k): str(v) for k, v in (manifest.get("files") or {}).items()
    }
    new_files = set(_iter_files(new_tree_dir))
    disk_files = set(_iter_files(project_dir))

    result = DiffResult()

    for rel in sorted(set(managed) | new_files | disk_files):
        if rel == MANIFEST_NAME:
            continue
        on_disk = rel in disk_files
        in_new = rel in new_files
        in_managed = rel in managed

        if _is_user_config(rel):
            if on_disk:
                result.config_preserved.append(rel)
            continue

        expected = managed.get(rel)
        actual = sha256_file(project_dir / rel) if on_disk else None

        if in_new and not on_disk:
            if in_managed:
                result.entries.append(DiffEntry(
                    rel, USER_MODIFIED,
                    "Verwaltete Datei wurde im Projekt entfernt; keine automatische Wiederherstellung.",
                    expected_sha=expected, actual_sha=None,
                    new_sha=sha256_file(new_tree_dir / rel),
                ))
            else:
                result.entries.append(DiffEntry(
                    rel, ADD, "Neue Datei der Zielgeneration.",
                    new_sha=sha256_file(new_tree_dir / rel),
                ))
            continue

        if in_new and on_disk:
            new_sha = sha256_file(new_tree_dir / rel)
            if not in_managed:
                result.entries.append(DiffEntry(
                    rel, CONFLICT,
                    "Datei existiert im Projekt, ist aber nicht als Builder-verwaltet registriert.",
                    actual_sha=actual, new_sha=new_sha,
                ))
                continue
            if actual != expected:
                if actual == new_sha:
                    result.entries.append(DiffEntry(
                        rel, USER_MODIFIED,
                        "Verwaltete Datei wurde manuell geaendert; Inhalt entspricht bereits der Zielversion.",
                        expected_sha=expected, actual_sha=actual, new_sha=new_sha,
                    ))
                else:
                    result.entries.append(DiffEntry(
                        rel, CONFLICT,
                        "Verwaltete Datei wurde manuell geaendert; die Zielversion weicht ab.",
                        expected_sha=expected, actual_sha=actual, new_sha=new_sha,
                    ))
                continue
            if new_sha == actual:
                result.entries.append(DiffEntry(
                    rel, UNCHANGED, "Datei unveraendert.",
                    expected_sha=expected, actual_sha=actual, new_sha=new_sha,
                ))
            else:
                result.entries.append(DiffEntry(
                    rel, UPDATE_SAFE, "Verwaltete Datei kann sicher aktualisiert werden.",
                    expected_sha=expected, actual_sha=actual, new_sha=new_sha,
                ))
            continue

        # not in new tree
        if on_disk:
            if in_managed:
                result.entries.append(DiffEntry(
                    rel, REMOVE_CANDIDATE,
                    "Vom neuen Builder nicht mehr erzeugt; keine automatische Loeschung.",
                    expected_sha=expected, actual_sha=actual,
                ))
            else:
                result.entries.append(DiffEntry(
                    rel, USER_OWNED, "Benutzerdatei (nicht Builder-verwaltet).",
                    actual_sha=actual,
                ))

    # Konfigurationsparameter (nur Vorschlag, keine Aenderung)
    old_vars = _variable_names(project_dir / "terraform" / "variables.tf")
    new_vars = _variable_names(new_tree_dir / "terraform" / "variables.tf")
    result.new_parameters = sorted(set(new_vars) - set(old_vars))
    result.removed_parameters = sorted(set(old_vars) - set(new_vars))

    return result


def decide_status(
    project_status: str, diff: DiffResult
) -> Tuple[str, str]:
    if project_status == NEW_PROJECT:
        return BLOCKED, CODE_UNVERIFIED
    if project_status == LEGACY_PROJECT:
        return BLOCKED, CODE_LEGACY
    if project_status in (UNVERIFIED_PROJECT, CONFLICTED_PROJECT):
        return BLOCKED, CODE_UNVERIFIED
    if diff.conflicts:
        return BLOCKED, CODE_CONFLICT
    if diff.by_category(USER_MODIFIED) or diff.by_category(REMOVE_CANDIDATE):
        return REVIEW_REQUIRED, CODE_READY
    if diff.writes:
        return READY, CODE_READY
    return NO_CHANGES, CODE_NO_CHANGES


def build_report(
    *,
    project_dir: Path,
    manifest: dict,
    new_manifest: dict,
    diff: DiffResult,
    project_status: str,
    status: str,
    code: str,
    target_version: Optional[str],
) -> dict:
    changes = [entry.to_dict() for entry in diff.entries if entry.category != UNCHANGED]
    conflicts = [entry.to_dict() for entry in diff.conflicts]
    user_changes = [
        entry.to_dict()
        for entry in diff.entries
        if entry.category in (USER_MODIFIED, USER_OWNED)
    ]
    removed = [entry.to_dict() for entry in diff.by_category(REMOVE_CANDIDATE)]
    manual_steps: List[str] = []
    if conflicts:
        manual_steps.append("Konflikte manuell aufloesen; betroffene Dateien pruefen.")
    if removed:
        manual_steps.append("Veraltete Dateien bewusst pruefen/entfernen (nicht automatisch).")
    if diff.new_parameters:
        manual_steps.append(
            "Neue Terraform-Parameter in eigene tfvars aufnehmen: "
            + ", ".join(diff.new_parameters)
        )
    if diff.removed_parameters:
        manual_steps.append(
            "Entfernte Parameter pruefen: " + ", ".join(diff.removed_parameters)
        )
    if project_status == LEGACY_PROJECT:
        manual_steps.append(
            "Legacy-Projekt: Manifest/Fingerprints manuell pruefen; "
            "kein automatisches Upgrade."
        )

    return {
        "schemaVersion": 1,
        "generatedAt": _now(),
        "project": {
            "name": manifest.get("project_name"),
            "path": str(project_dir),
            "status": project_status,
        },
        "builder": {
            "fromVersion": manifest.get("builder_version"),
            "toVersion": new_manifest.get("builder_version"),
            "targetVersion": target_version,
            "gitCommit": (new_manifest.get("source") or {}).get("commit"),
        },
        "modules": new_manifest.get("modules") or manifest.get("modules") or [],
        "fileChanges": changes,
        "userChanges": user_changes,
        "configChanges": {
            "preserved": diff.config_preserved,
            "newParameters": diff.new_parameters,
            "removedParameters": diff.removed_parameters,
        },
        "conflicts": conflicts,
        "removedFiles": removed,
        "security": {
            "pathTraversalChecked": True,
            "symlinksRejected": True,
            "userFilesOverwritten": False,
            "filesDeleted": False,
            "secretsInReport": False,
        },
        "result": {"status": status, "code": code},
        "manualSteps": manual_steps,
        "installerPrerequisites": [
            "Builder-Upgrade abgeschlossen und Manifest aktualisiert.",
            "Danach Installer: plan --remote --upgrade (P0A/P0B/P0C/P1).",
            "Keine automatische Terraform-Ausfuehrung durch den Builder.",
        ],
    }


def render_report_markdown(report: dict) -> str:
    lines: List[str] = []
    lines.append("# Builder-Upgrade-Bericht")
    lines.append("")
    lines.append(f"**Status:** `{report['result']['status']}` (`{report['result']['code']}`)")
    lines.append("")
    lines.append("> Keine Terraform-Apply-Freigabe. Der Installer prueft separat.")
    lines.append("")
    project = report["project"]
    lines.append("## 1. Projektidentitaet")
    lines.append("")
    lines.append(f"- Name: `{project.get('name')}`")
    lines.append(f"- Pfad: `{project.get('path')}`")
    lines.append(f"- Status: `{project.get('status')}`")
    lines.append("")
    builder = report["builder"]
    lines.append("## 2. Builder-Ausgangsversion")
    lines.append("")
    lines.append(f"- `{builder.get('fromVersion')}`")
    lines.append("")
    lines.append("## 3. Builder-Zielversion")
    lines.append("")
    lines.append(f"- `{builder.get('toVersion')}`")
    lines.append("")
    lines.append("## 4. Git-Commit")
    lines.append("")
    lines.append(f"- `{builder.get('gitCommit')}`")
    lines.append("")
    lines.append("## 5. Aktivierte Module")
    lines.append("")
    lines.append("- " + ", ".join(report.get("modules") or []))
    lines.append("")
    lines.append("## 6. Dateiaenderungen")
    lines.append("")
    for change in report.get("fileChanges") or []:
        lines.append(f"- `{change['category']}` `{change['path']}`: {change['reason']}")
    if not report.get("fileChanges"):
        lines.append("- keine")
    lines.append("")
    lines.append("## 7. Benutzeraenderungen")
    lines.append("")
    for change in report.get("userChanges") or []:
        lines.append(f"- `{change['category']}` `{change['path']}`")
    if not report.get("userChanges"):
        lines.append("- keine")
    lines.append("")
    lines.append("## 8. Konfigurationsaenderungen")
    lines.append("")
    config = report.get("configChanges") or {}
    lines.append(f"- Erhalten: {', '.join(config.get('preserved') or []) or 'keine'}")
    lines.append(f"- Neue Parameter: {', '.join(config.get('newParameters') or []) or 'keine'}")
    lines.append(f"- Entfernte Parameter: {', '.join(config.get('removedParameters') or []) or 'keine'}")
    lines.append("")
    lines.append("## 9. Konflikte")
    lines.append("")
    for conflict in report.get("conflicts") or []:
        lines.append(f"- `{conflict['path']}`: {conflict['reason']}")
    if not report.get("conflicts"):
        lines.append("- keine")
    lines.append("")
    lines.append("## 10. Entfernte oder veraltete Dateien")
    lines.append("")
    for removed in report.get("removedFiles") or []:
        lines.append(f"- `{removed['path']}` (nicht automatisch geloescht)")
    if not report.get("removedFiles"):
        lines.append("- keine")
    lines.append("")
    lines.append("## 11. Sicherheitsbewertung")
    lines.append("")
    for key, value in (report.get("security") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## 12. Ergebnis")
    lines.append("")
    lines.append(f"- `{report['result']['status']}` / `{report['result']['code']}`")
    lines.append("")
    lines.append("## 13. Erforderliche manuelle Schritte")
    lines.append("")
    for step in report.get("manualSteps") or []:
        lines.append(f"- {step}")
    if not report.get("manualSteps"):
        lines.append("- keine")
    lines.append("")
    lines.append("## 14. Voraussetzungen fuer den Installer")
    lines.append("")
    for item in report.get("installerPrerequisites") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_report(project_dir: Path, report: dict) -> Tuple[Path, Path]:
    run_dir = project_dir / RUN_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / REPORT_JSON
    md_path = run_dir / REPORT_MD
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def apply_upgrade(
    project_dir: Path,
    new_tree_dir: Path,
    diff: DiffResult,
    *,
    new_manifest: dict,
    previous_manifest: dict,
) -> dict:
    """Schreibt ausschliesslich ADD/UPDATE_SAFE und aktualisiert das Manifest."""
    if diff.conflicts:
        raise BuilderUpgradeError(
            CODE_CONFLICT,
            "Konflikte vorhanden; es wurde nichts geschrieben.",
        )

    project_root = project_dir.resolve()
    planned = diff.writes
    targets = []
    for entry in planned:
        target = safe_target(project_root, entry.path)
        source = new_tree_dir / entry.path
        if not source.exists():
            raise BuilderUpgradeError(
                CODE_CONFLICT, f"Generierte Datei fehlt: {entry.path}"
            )
        targets.append((entry, source, target))

    staging = project_root / ".mays-builder" / "staging" / datetime.now().strftime("%Y%m%d-%H%M%S")
    written: List[str] = []
    try:
        for entry, source, target in targets:
            staged = staging / entry.path
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, staged)
        for entry, source, target in targets:
            staged = staging / entry.path
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
            written.append(entry.path)
    except OSError as exc:
        raise BuilderUpgradeError(
            CODE_CONFLICT, f"Schreibfehler nach {len(written)} Datei(en): {exc}"
        ) from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    manifest = dict(new_manifest)
    manifest.setdefault("files", {})
    for rel in written:
        manifest["files"][rel] = sha256_file(project_root / rel)
    manifest["files"] = dict(sorted(manifest["files"].items()))
    manifest["manifest_version"] = MANIFEST_SCHEMA_VERSION
    manifest["upgraded_from"] = {
        "builder_version": previous_manifest.get("builder_version"),
        "generated_at": previous_manifest.get("generated_at"),
    }
    (project_root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"written": written, "manifest": str(project_root / MANIFEST_NAME)}
