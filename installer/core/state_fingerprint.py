"""MO-RC4-P0C-DRIFT-FIX-01: deterministischer Terraform-State-Fingerprint.

Terraform `state pull` serialisiert insbesondere `check_results` nicht stabil.
Der Fingerprint wird daher ueber eine kanonische Repraesentation berechnet:

- JSON-Objektschluessel sortiert
- `check_results` nach stabilem Schluessel sortiert
- `resources` und deren `instances` nach stabilen Identitaetsmerkmalen sortiert

Semantisch geordnete Listen innerhalb von Ressourcenattributen bleiben
unveraendert; nur die nachweislich ungeordneten State-Container werden sortiert.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

FINGERPRINT_VERSION = "canonical-sha256-v1"


class StateFingerprintError(ValueError):
    """State ist nicht kanonisierbar."""


def _canonical_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stable_sort_key(value: Any) -> str:
    return _canonical_dump(value)


def canonicalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Liefert eine deterministische Kopie des State.

    Die Funktion veraendert die Eingabe nicht. Fehlerhafte Strukturen werden
    fail-closed abgelehnt.
    """
    if not isinstance(state, dict):
        raise StateFingerprintError("State ist kein Objekt")
    try:
        normalized = json.loads(json.dumps(state))
    except (TypeError, ValueError) as exc:
        raise StateFingerprintError(f"State ist nicht JSON-serialisierbar: {exc}") from exc

    check_results = normalized.get("check_results")
    if isinstance(check_results, list):
        normalized["check_results"] = sorted(check_results, key=_stable_sort_key)

    resources = normalized.get("resources")
    if isinstance(resources, list):
        for resource in resources:
            if not isinstance(resource, dict):
                raise StateFingerprintError("Resource ist kein Objekt")
            instances = resource.get("instances")
            if isinstance(instances, list):
                resource["instances"] = sorted(instances, key=_stable_sort_key)
        normalized["resources"] = sorted(
            resources,
            key=lambda item: (
                str(item.get("module") or ""),
                str(item.get("mode") or ""),
                str(item.get("type") or ""),
                str(item.get("name") or ""),
                _stable_sort_key(item),
            ),
        )
    return normalized


def canonical_state_json(raw: str | bytes | Dict[str, Any]) -> str:
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StateFingerprintError("State ist nicht UTF-8") from exc
    if isinstance(raw, str):
        try:
            state = json.loads(raw)
        except ValueError as exc:
            raise StateFingerprintError(f"State ist kein gueltiges JSON: {exc}") from exc
    elif isinstance(raw, dict):
        state = raw
    else:
        raise StateFingerprintError("State-Typ wird nicht unterstuetzt")
    return _canonical_dump(canonicalize_state(state))


def canonical_state_fingerprint(raw: str | bytes | Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_state_json(raw).encode("utf-8")).hexdigest()
