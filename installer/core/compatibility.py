"""MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01: Versionskompatibilitaet.

Bewertet das Upgrade von der installierten Ausgangsversion (P0B) auf die
Zielversion. Die SemVer-Differenz allein ist **kein** technischer
Kompatibilitaetsnachweis; sie liefert nur die Grundklassifikation.

Regeln:
- unbekannte/legacy Ausgangsversion -> UNKNOWN (blockiert)
- ungueltige Version            -> UNKNOWN (blockiert)
- Downgrade                     -> INCOMPATIBLE (blockiert)
- gleiche Version / Patch       -> COMPATIBLE
- Minor                         -> REVIEW_REQUIRED, ausser explizit
                                   nachgewiesene Kompatibilitaet
- Major                         -> MIGRATION_REQUIRED (blockiert)

COMPATIBLE ersetzt niemals P0A/P0B/P0C-Pruefungen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from installer.core.deployment_identity import SemanticVersion
from installer.core.version_matrix import lookup_compatibility

COMPATIBLE = "COMPATIBLE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
INCOMPATIBLE = "INCOMPATIBLE"
UNKNOWN = "UNKNOWN"

BLOCKING_STATUSES = (MIGRATION_REQUIRED, INCOMPATIBLE, UNKNOWN)


@dataclass(frozen=True)
class CompatibilityAssessment:
    status: str
    source_version: Optional[str]
    target_version: Optional[str]
    reason: str

    @property
    def blocked(self) -> bool:
        return self.status in BLOCKING_STATUSES

    @property
    def review_required(self) -> bool:
        return self.status == REVIEW_REQUIRED


def assess_compatibility(
    source_version: Optional[str],
    target_version: Optional[str],
    *,
    source_status: str = "VERIFIED",
    known_compatible: bool = False,
) -> CompatibilityAssessment:
    """Bewertet die Kompatibilitaet (fail-closed)."""
    if source_status != "VERIFIED" or not source_version:
        return CompatibilityAssessment(
            status=UNKNOWN,
            source_version=source_version,
            target_version=target_version,
            reason=(
                "Ausgangsversion ist nicht verifiziert (LEGACY_UNKNOWN/unbekannt); "
                "eine automatische Kompatibilitaetsannahme ist nicht zulaessig."
            ),
        )

    try:
        source = SemanticVersion.parse(str(source_version))
    except (TypeError, ValueError):
        return CompatibilityAssessment(
            status=UNKNOWN,
            source_version=source_version,
            target_version=target_version,
            reason=f"Ungueltige Ausgangsversion {source_version!r}.",
        )

    try:
        target = SemanticVersion.parse(str(target_version))
    except (TypeError, ValueError):
        return CompatibilityAssessment(
            status=UNKNOWN,
            source_version=source_version,
            target_version=target_version,
            reason=f"Ungueltige Zielversion {target_version!r}.",
        )

    if target.to_tuple() == source.to_tuple():
        return CompatibilityAssessment(
            status=COMPATIBLE,
            source_version=str(source),
            target_version=str(target),
            reason="Gleiche Version: erneuter Plan/Apply auf denselben Stand.",
        )
    if target.to_tuple() < source.to_tuple():
        return CompatibilityAssessment(
            status=INCOMPATIBLE,
            source_version=str(source),
            target_version=str(target),
            reason="Downgrade: kein Kompatibilitaetsnachweis fuer aeltere Version.",
        )
    if target.major != source.major:
        return CompatibilityAssessment(
            status=MIGRATION_REQUIRED,
            source_version=str(source),
            target_version=str(target),
            reason=(
                "Major-Upgrade: Migrationspruefung erforderlich "
                "(SemVer-Differenz allein ist kein Kompatibilitaetsnachweis)."
            ),
        )
    if target.minor != source.minor:
        matrix_entry = lookup_compatibility(str(source), str(target))
        if matrix_entry is not None:
            return CompatibilityAssessment(
                status=COMPATIBLE,
                source_version=str(source),
                target_version=str(target),
                reason=(
                    "Minor-Upgrade durch Evidenzmatrix belegt: "
                    f"{matrix_entry.reason}"
                ),
            )
        if known_compatible:
            return CompatibilityAssessment(
                status=COMPATIBLE,
                source_version=str(source),
                target_version=str(target),
                reason="Minor-Upgrade mit dokumentiertem Kompatibilitaetsnachweis.",
            )
        return CompatibilityAssessment(
            status=REVIEW_REQUIRED,
            source_version=str(source),
            target_version=str(target),
            reason=(
                "Minor-Upgrade: manuelle Kompatibilitaetspruefung erforderlich "
                "(kein hinterlegter Nachweis)."
            ),
        )

    return CompatibilityAssessment(
        status=COMPATIBLE,
        source_version=str(source),
        target_version=str(target),
        reason="Patch-Upgrade: grundsaetzlich kompatibel (Gates bleiben verbindlich).",
    )
