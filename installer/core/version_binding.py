"""MO-INSTALLER-UPGRADE-VERSIONING-P0B-01: Installationsversion + Bindung.

Erkennt die tatsaechlich installierte MO-Version aus dem Terraform-State
(Output ``mo_version``) und prueft die Versionsbindung eines Plan-Manifests
gegen den aktuellen Kontext.

Grundregel: Eine im Manifest angegebene Zielversion ist **kein** Nachweis der
installierten Ausgangsversion. Unbekannte Ausgangsversionen bleiben
``LEGACY_UNKNOWN`` — es wird nie eine Version angenommen (insbesondere nicht
``0.1.0``).

Kein AWS-Aufruf (nutzt ausschliesslich den bereits initialisierten
Terraform-Runner gegen das konfigurierte Backend).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

VERIFIED = "VERIFIED"
LEGACY_UNKNOWN = "LEGACY_UNKNOWN"
UNVERIFIED = "UNVERIFIED"
UNREADABLE = "UNREADABLE"

CODE_OK = "OK"
CODE_MISSING = "UPGRADE_VERSION_BINDING_MISSING"
CODE_MISMATCH = "UPGRADE_VERSION_BINDING_MISMATCH"
CODE_SOURCE_DIRTY = "UPGRADE_SOURCE_DIRTY"
CODE_SOURCE_UNVERIFIED = "UPGRADE_SOURCE_UNVERIFIED"
CODE_LEGACY_SOURCE = "UPGRADE_LEGACY_SOURCE_UNKNOWN"
CODE_STATE_UNREADABLE = "UPGRADE_STATE_UNREADABLE"


@dataclass(frozen=True)
class InstalledVersion:
    status: str
    version: Optional[str] = None
    source: Optional[str] = None
    resources: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "version": self.version,
            "source": self.source,
            "resources": self.resources,
        }


@dataclass
class VersionCheck:
    ok: bool
    code: str
    errors: List[str] = field(default_factory=list)

    def message(self) -> str:
        if self.ok:
            return "Version binding: OK"
        return "\n".join(self.errors)


def detect_installed_version(runner) -> InstalledVersion:
    """Liest die installierte Version aus dem Remote-State (read-only).

    - kein State / 0 Ressourcen -> UNVERIFIED (Neuinstallation)
    - State ohne ``mo_version``-Output -> LEGACY_UNKNOWN
    - State nicht lesbar -> UNREADABLE (fail-closed)
    """
    try:
        state = runner.state_list()
    except Exception as exc:  # defensiv: unbekannter Zustand ist nicht "neu"
        return InstalledVersion(status=UNREADABLE, source=f"state_error: {exc}")

    if not state.success:
        return InstalledVersion(
            status=UNREADABLE,
            source="state_unreadable",
        )

    resources = [line for line in (state.stdout or "").splitlines() if line.strip()]
    if not resources:
        return InstalledVersion(
            status=UNVERIFIED,
            version=None,
            source="no_remote_state",
            resources=0,
        )

    try:
        output = runner.output()
    except Exception:
        output = None

    if output is not None and output.success:
        try:
            data = json.loads(output.stdout or "{}")
        except (TypeError, ValueError):
            data = {}
        entry = data.get("mo_version")
        value = entry.get("value") if isinstance(entry, dict) else None
        if isinstance(value, str) and value.strip():
            return InstalledVersion(
                status=VERIFIED,
                version=value.strip(),
                source="terraform_output",
                resources=len(resources),
            )

    return InstalledVersion(
        status=LEGACY_UNKNOWN,
        version=None,
        source="state_without_version",
        resources=len(resources),
    )


def check_source_for_plan(identity, *, allow_dirty_source: bool = False) -> VersionCheck:
    """Preflight fuer einen verbindlichen Remote-(Upgrade-)Plan."""
    if not identity.available:
        return VersionCheck(
            ok=False,
            code=CODE_SOURCE_UNVERIFIED,
            errors=[
                f"{CODE_SOURCE_UNVERIFIED}: Git-Commit des Quellcodes nicht ermittelbar "
                f"({identity.reason or 'keine Git-Metadaten'})."
            ],
        )
    if identity.dirty and not allow_dirty_source:
        return VersionCheck(
            ok=False,
            code=CODE_SOURCE_DIRTY,
            errors=[
                f"{CODE_SOURCE_DIRTY}: Working Tree enthaelt ungetrackte Aenderungen an "
                f"getrackten Dateien; ein Commit allein beschreibt diesen Code nicht. "
                "Freigabe mit --allow-dirty-source oder vorher committen."
            ],
        )
    return VersionCheck(ok=True, code=CODE_OK)


def check_version_binding(
    manifest,
    *,
    current_target_version: str,
    identity,
    installed: InstalledVersion,
    allow_dirty_source: bool = False,
    allow_legacy_source: bool = False,
) -> VersionCheck:
    """Prueft Manifest-Version gegen aktuellen Kontext (vor Apply).

    Reihenfolge: fehlende Bindung -> Zielversion -> Commit -> Dirty ->
    Quellversion/Legacy.
    """
    if getattr(manifest, "manifest_version", 0) < 2:
        return VersionCheck(
            ok=False,
            code=CODE_MISSING,
            errors=[
                f"{CODE_MISSING}: Plan-Manifest (Version "
                f"{getattr(manifest, 'manifest_version', 0)}) enthaelt keine "
                "verbindliche Versionsbindung. Bitte mit `plan --remote` neu planen."
            ],
        )

    errors: List[str] = []

    if not manifest.target_version:
        errors.append(f"{CODE_MISMATCH}: targetVersion fehlt im Manifest.")
    elif manifest.target_version != current_target_version:
        errors.append(
            f"{CODE_MISMATCH}: targetVersion {manifest.target_version!r} passt nicht "
            f"zur aktuellen Deployment-Version {current_target_version!r}."
        )

    if not identity.available:
        errors.append(
            f"{CODE_SOURCE_UNVERIFIED}: Git-Commit des aktuellen Quellcodes nicht "
            f"ermittelbar ({identity.reason or 'keine Git-Metadaten'})."
        )
    elif not manifest.git_commit:
        errors.append(f"{CODE_MISMATCH}: gitCommit fehlt im Manifest.")
    elif manifest.git_commit != identity.commit:
        errors.append(
            f"{CODE_MISMATCH}: Quellcode-Commit {identity.commit} weicht vom Plan "
            f"({manifest.git_commit}) ab — zwischen Plan und Apply geaendert."
        )

    if manifest.git_dirty is None or identity.dirty is None:
        errors.append(f"{CODE_MISMATCH}: Dirty-Status nicht vollstaendig gebunden.")
    else:
        if manifest.git_dirty != identity.dirty:
            errors.append(
                f"{CODE_MISMATCH}: Dirty-Status hat sich geaendert (Plan: "
                f"{manifest.git_dirty}, jetzt: {identity.dirty})."
            )
        if identity.dirty and not allow_dirty_source:
            errors.append(
                f"{CODE_SOURCE_DIRTY}: Quellcode ist dirty; Apply mit "
                "--allow-dirty-source freigeben oder vorher committen."
            )

    status = manifest.version_status
    if status not in (VERIFIED, LEGACY_UNKNOWN, UNVERIFIED):
        errors.append(f"{CODE_MISMATCH}: Unbekannter versionStatus {status!r}.")
    elif installed.status == UNREADABLE:
        errors.append(
            f"{CODE_STATE_UNREADABLE}: Installierter State ist nicht lesbar; "
            "eine Neuinstallation darf nicht angenommen werden."
        )
    elif status == VERIFIED:
        if not manifest.source_version:
            errors.append(f"{CODE_MISMATCH}: versionStatus VERIFIED ohne sourceVersion.")
        elif installed.status != VERIFIED or installed.version != manifest.source_version:
            errors.append(
                f"{CODE_MISMATCH}: Installierte Version "
                f"({installed.version or installed.status}) entspricht nicht der "
                f"Plan-Ausgangsversion {manifest.source_version!r}."
            )
    elif status == LEGACY_UNKNOWN:
        if installed.status != LEGACY_UNKNOWN:
            errors.append(
                f"{CODE_MISMATCH}: Plan erwartet LEGACY_UNKNOWN, installiert ist "
                f"jetzt {installed.status}."
            )
        if not allow_legacy_source:
            errors.append(
                f"{CODE_LEGACY_SOURCE}: Ausgangsversion ist nicht verifizierbar "
                "(LEGACY_UNKNOWN). Apply mit --allow-legacy-source ausdruecklich "
                "freigeben; keine automatische Versionsannahme."
            )
    elif status == UNVERIFIED:
        if installed.status != UNVERIFIED:
            errors.append(
                f"{CODE_MISMATCH}: Plan wurde fuer eine Neuinstallation erstellt, "
                f"der State enthaelt aber {installed.resources} Ressource(n)."
            )

    if errors:
        code = CODE_MISMATCH
        for candidate in (CODE_STATE_UNREADABLE, CODE_SOURCE_DIRTY, CODE_LEGACY_SOURCE,
                          CODE_SOURCE_UNVERIFIED):
            if any(candidate in error for error in errors):
                code = candidate
                break
        return VersionCheck(ok=False, code=code, errors=errors)

    return VersionCheck(ok=True, code=CODE_OK)
