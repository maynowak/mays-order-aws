"""MO-INSTALLER-UPGRADE-DRIFT-SAFETY-P0C-01: State-Baseline.

Erfasst eine nicht-geheime Baseline des Terraform-States (Serial, Lineage,
Ressourcenanzahl, Fingerprint) und vergleicht sie mit einem gespeicherten
Plan-Manifest.

Sicherheit:
- Es werden KEINE State-Inhalte gespeichert oder geloggt (nur Metadaten und
  ein SHA-256-Fingerprint des Roh-States).
- Fehlende Lineage/Serial wird ausdruecklich gekennzeichnet, nicht erfunden.
- Unlesbarer State wird als Fehler behandelt, nicht als Neuinstallation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from installer.core.state_fingerprint import (
    FINGERPRINT_VERSION,
    StateFingerprintError,
    canonical_state_fingerprint,
)

VERIFIED = "VERIFIED"
NO_STATE = "NO_STATE"
MISSING_LINEAGE = "MISSING_LINEAGE"
MISSING_SERIAL = "MISSING_SERIAL"
UNREADABLE = "UNREADABLE"

CODE_OK = "OK"
CODE_MISSING = "UPGRADE_STATE_BASELINE_MISSING"
CODE_MISMATCH = "UPGRADE_STATE_BASELINE_MISMATCH"
CODE_UNREADABLE = "UPGRADE_STATE_UNREADABLE"

BASELINE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class StateBaseline:
    status: str
    serial: Optional[int] = None
    lineage: Optional[str] = None
    resources: Optional[int] = None
    fingerprint: Optional[str] = None
    fingerprint_version: str = FINGERPRINT_VERSION
    captured_at: str = ""
    source: str = "terraform_state_pull"
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "schemaVersion": BASELINE_SCHEMA_VERSION,
            "status": self.status,
            "serial": self.serial,
            "lineage": self.lineage,
            "resources": self.resources,
            "fingerprint": self.fingerprint,
            "fingerprintVersion": self.fingerprint_version,
            "captured_at": self.captured_at,
            "source": self.source,
            "reason": self.reason,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def capture_state_baseline(runner) -> StateBaseline:
    """Liest Serial/Lineage/Ressourcenanzahl aus `terraform state pull`.

    Der Roh-State wird nur im Speicher verarbeitet (Fingerprint); es werden
    keine Werte in Reports uebernommen.
    """
    try:
        result = runner.state_pull()
    except Exception as exc:  # defensiv: unbekannter Zustand bleibt Fehler
        return StateBaseline(status=UNREADABLE, captured_at=_now(), reason=str(exc)[:200])

    if not result.success:
        return StateBaseline(
            status=UNREADABLE,
            captured_at=_now(),
            reason=(result.stderr or "").strip()[:200],
        )

    raw = result.stdout or ""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        return StateBaseline(status=UNREADABLE, captured_at=_now(), reason=f"JSON: {exc}")

    if not isinstance(data, dict):
        return StateBaseline(status=UNREADABLE, captured_at=_now(), reason="State ist kein Objekt")

    serial = data.get("serial")
    lineage = data.get("lineage")
    resources = data.get("resources")
    try:
        fingerprint = canonical_state_fingerprint(raw)
    except StateFingerprintError as exc:
        return StateBaseline(
            status=UNREADABLE,
            captured_at=_now(),
            reason=f"Fingerprint: {exc}",
        )

    if not isinstance(serial, int):
        return StateBaseline(
            status=MISSING_SERIAL,
            serial=None,
            lineage=lineage if isinstance(lineage, str) else None,
            resources=len(resources) if isinstance(resources, list) else None,
            fingerprint=fingerprint,
            captured_at=_now(),
            reason="State enthaelt keine ganzzahlige Serial.",
        )
    if not isinstance(lineage, str) or not lineage:
        return StateBaseline(
            status=MISSING_LINEAGE,
            serial=serial,
            lineage=None,
            resources=len(resources) if isinstance(resources, list) else None,
            fingerprint=fingerprint,
            captured_at=_now(),
            reason="State enthaelt keine Lineage.",
        )

    count = len(resources) if isinstance(resources, list) else None
    return StateBaseline(
        status=NO_STATE if count == 0 else VERIFIED,
        serial=serial,
        lineage=lineage,
        resources=count,
        fingerprint=fingerprint,
        captured_at=_now(),
    )


def compare_state_baseline(
    manifest_baseline: Optional[dict],
    current: StateBaseline,
) -> Tuple[bool, str, str]:
    """Vergleicht Manifest-Baseline mit dem aktuellen State (vor Apply).

    Returns: (ok, code, message)
    """
    if not isinstance(manifest_baseline, dict) or not manifest_baseline:
        return (
            False,
            CODE_MISSING,
            f"{CODE_MISSING}: Plan-Manifest enthaelt keine State-Baseline; "
            "bitte mit `plan --remote` neu planen.",
        )

    if current.status == UNREADABLE:
        return (
            False,
            CODE_UNREADABLE,
            f"{CODE_UNREADABLE}: Aktueller Terraform-State ist nicht lesbar; "
            "Apply ist blockiert (keine Neuinstallations-Annahme).",
        )

    expected_serial = manifest_baseline.get("serial")
    expected_lineage = manifest_baseline.get("lineage")
    expected_fingerprint = manifest_baseline.get("fingerprint")
    expected_fingerprint_version = manifest_baseline.get("fingerprintVersion")

    errors = []
    if expected_serial is None or current.serial is None:
        errors.append("State-Serial fehlt (Manifest oder aktueller State).")
    elif expected_serial != current.serial:
        errors.append(
            f"State-Serial geaendert: Plan {expected_serial}, jetzt {current.serial}."
        )
    if not expected_lineage or not current.lineage:
        errors.append("State-Lineage fehlt (Manifest oder aktueller State).")
    elif expected_lineage != current.lineage:
        errors.append("State-Lineage geaendert (fremder/ersetzter State).")
    if expected_fingerprint:
        if expected_fingerprint_version != FINGERPRINT_VERSION:
            errors.append(
                "State-Fingerprint-Version fehlt oder ist unbekannt "
                f"(erwartet {FINGERPRINT_VERSION})."
            )
        elif current.fingerprint != expected_fingerprint:
            errors.append("State-Fingerprint geaendert (State wurde seit dem Plan geschrieben).")

    if errors:
        return (
            False,
            CODE_MISMATCH,
            f"{CODE_MISMATCH}: " + " ".join(errors),
        )

    return (True, CODE_OK, "State baseline: OK")
