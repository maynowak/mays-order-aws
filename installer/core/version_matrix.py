"""MO-RC4-UPGRADE-RELEASE-GATES-01: Evidenzmatrix fuer Minor-Upgrades.

Die Matrix ist bewusst klein und versionsspezifisch. Sie ersetzt keine
Terraform-Planpruefung (P0A/P0C) und keine Backup-/Privacy-Gates.

Wichtig: Release-Tags (v0.5.0-rc.3) und Deployment-Versionen (SemVer im
Terraform-Output `mo_version`) sind unterschiedliche Namensraeume. Die Matrix
verwendet die tatsaechlich vom Installer verglichenen Deployment-Versionen
(0.1.0 -> 0.2.0, belegt in P0B/P1). Eine Abbildung von Release-Tags auf
Deployment-Versionen muss der Betreiber bestaetigen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

MATRIX_SCHEMA_VERSION = 1

RC3_PACKAGING_COMMIT = "086a8be"
RC3_RELEASE_LABEL = "v0.5.0-rc.3 (Tag nicht erstellt)"
RC4_RELEASE_LABEL = "RC4 (Release-Label offen, Q-12)"


@dataclass(frozen=True)
class CompatibilityMatrixEntry:
    source_version: str
    target_version: str
    source_release: str
    target_release: str
    reason: str
    evidence: Tuple[str, ...]
    conditions: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "sourceVersion": self.source_version,
            "targetVersion": self.target_version,
            "sourceRelease": self.source_release,
            "targetRelease": self.target_release,
            "status": "COMPATIBLE",
            "reason": self.reason,
            "evidence": list(self.evidence),
            "conditions": list(self.conditions),
        }


# Bewusst nur exakt belegte Paare. Kein Wildcard, keine Bereichsannahme.
MATRIX: Tuple[CompatibilityMatrixEntry, ...] = (
    CompatibilityMatrixEntry(
        source_version="0.1.0",
        target_version="0.2.0",
        source_release=(
            f"RC3-Baseline ({RC3_PACKAGING_COMMIT}, {RC3_RELEASE_LABEL})"
        ),
        target_release=RC4_RELEASE_LABEL,
        reason=(
            "Minor-Upgrade 0.1.0 -> 0.2.0 ist durch die RC4-Aenderungsanalyse "
            "belegt: additive GSI3, keine Aenderung an pk/sk oder Tabellenidentitaet, "
            "kein Backfill. P0A/P0C/P1 bleiben verbindlich."
        ),
        evidence=(
            "terraform/modules/dynamodb/main.tf:94-106 (GSI3 KEYS_ONLY, additiv)",
            "docs/reports/MO-RC4-P02I-B2-AUTOMATIC-PROCESSING-RECOVERY.md (GSI3)",
            "docs/reports/MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01.md (0.2.0-Ziel)",
            "docs/reports/MO-INSTALLER-UPGRADE-VERSIONING-P0B-01.md (mo_version)",
            "installer/core/upgrade_safety.py:35-40 (P0A-Schutz)",
        ),
        conditions=(
            "Ausgangsversion ist VERIFIED (kein LEGACY_UNKNOWN).",
            "Der konkrete Plan enthaelt 0 replace/0 delete der geschuetzten Ressourcen.",
            "P0A/P0C/P1-Gates sind PASS; die Matrix ersetzt sie nicht.",
            "Keine Datenmigration/kein Backfill; kein Restore/Cutover.",
            "Backup-Evidenz ist fuer den Upgrade-Plan separat erforderlich.",
            "Deployment-Version 0.1.0/0.2.0 muss zum tatsaechlichen mo_version passen; "
            "Release-Tags sind nicht automatisch auf Deployment-Versionen abgebildet.",
        ),
    ),
)


def lookup_compatibility(
    source_version: str, target_version: str
) -> Optional[CompatibilityMatrixEntry]:
    """Liefert nur exakt belegte Paare; keine Bereichs- oder Wildcard-Freigabe."""
    for entry in MATRIX:
        if entry.source_version == str(source_version) and entry.target_version == str(
            target_version
        ):
            return entry
    return None


def matrix_report() -> Dict[str, object]:
    return {
        "schemaVersion": MATRIX_SCHEMA_VERSION,
        "entries": [entry.to_dict() for entry in MATRIX],
        "limits": [
            "Nur exakte Deployment-Versionspaare; keine Bereichsfreigabe.",
            "Release-Tags und Deployment-Versionen sind getrennte Namensraeume.",
            "Matrix ersetzt keine P0A/P0C/P1-/Backup-/Privacy-Pruefung.",
        ],
    }
