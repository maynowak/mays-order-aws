"""MO-RC4-P02G-A — Daten- und Datenschutzvertrag fuer Verarbeitungsergebnisse.

Dieser Checkpoint bereitet NUR den Vertrag vor:
- Feldnamen und optionale Semantik,
- technische Validierung (Groesse, Tiefe, Typen),
- datensparsame Privacy-Zusammenfassung,
- Schreibschutz-Bedingung fuer P02G-B.

Es gibt bewusst KEINE Funktion, die Ergebnisfelder in eine Order schreibt.
Der spaetere Schreibpfad (P02G-B) muss:
- ausschliesslich intern erfolgen (kein API-Feld),
- die Bedingung `RESULT_WRITE_GUARD` in den Conditional Write aufnehmen,
- `result` als potenziell personenbezogen behandeln.

Felder (alle optional, keine Initialisierung von Bestandsdaten):
    processingState       pending | running | succeeded | failed
    processingAttemptId   Kennung eines Verarbeitungsversuchs (Idempotenz)
    result                kleines strukturiertes Ergebnis (JSON-kompatibel)
    completedAt           ISO-8601-Zeitpunkt des fachlichen Abschlusses
    processingError       kontrollierte Fehlerinformation (code/message)
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Dict, Iterable, Mapping, Optional

from errors import validation_error

# --- Feldnamen -------------------------------------------------------------
FIELD_PROCESSING_STATE = "processingState"
FIELD_PROCESSING_ATTEMPT_ID = "processingAttemptId"
FIELD_RESULT = "result"
FIELD_COMPLETED_AT = "completedAt"
FIELD_PROCESSING_ERROR = "processingError"

PROCESSING_FIELDS = (
    FIELD_PROCESSING_STATE,
    FIELD_PROCESSING_ATTEMPT_ID,
    FIELD_RESULT,
    FIELD_COMPLETED_AT,
    FIELD_PROCESSING_ERROR,
)

PROCESSING_STATES = ("pending", "running", "succeeded", "failed")

# --- konservative Grenzen --------------------------------------------------
RESULT_MAX_BYTES = 16 * 1024        # serialisiertes JSON, UTF-8
RESULT_MAX_DEPTH = 5                # Verschachtelungstiefe
RESULT_MAX_ITEMS_PER_CONTAINER = 100
RESULT_MAX_KEY_LENGTH = 64
RESULT_MAX_STRING_LENGTH = 2000
ERROR_MAX_CODE_LENGTH = 64
ERROR_MAX_MESSAGE_LENGTH = 500
ATTEMPT_ID_MAX_LENGTH = 128

_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_ATTEMPT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")

# Bedingung fuer den spaeteren Schreibpfad (P02G-B): ein Ergebnis darf nur an
# eine Order geschrieben werden, die noch einen Eigentuemer besitzt. Nach
# ANONYMIZE wird `subjectId` entfernt -> Schreiben ist dann unmoeglich.
RESULT_WRITE_GUARD = "attribute_exists(subjectId)"


def _fail(message: str, path: str = "result") -> None:
    raise validation_error(message, {"path": path})


def _check_json_value(value: Any, depth: int, path: str) -> int:
    """Prueft Typ/Groesse rekursiv; liefert die Anzahl der Elemente."""
    if depth > RESULT_MAX_DEPTH:
        _fail(f"'{path}' exceeds maximum nesting depth {RESULT_MAX_DEPTH}", path)
    if value is None or isinstance(value, bool):
        return 1
    if isinstance(value, (int, float, Decimal)):
        return 1
    if isinstance(value, str):
        if len(value) > RESULT_MAX_STRING_LENGTH:
            _fail(f"'{path}' exceeds maximum string length {RESULT_MAX_STRING_LENGTH}", path)
        return 1
    if isinstance(value, (list, tuple)):
        if len(value) > RESULT_MAX_ITEMS_PER_CONTAINER:
            _fail(
                f"'{path}' exceeds maximum of {RESULT_MAX_ITEMS_PER_CONTAINER} items",
                path,
            )
        total = 1
        for index, entry in enumerate(value):
            total += _check_json_value(entry, depth + 1, f"{path}[{index}]")
        return total
    if isinstance(value, Mapping):
        if len(value) > RESULT_MAX_ITEMS_PER_CONTAINER:
            _fail(
                f"'{path}' exceeds maximum of {RESULT_MAX_ITEMS_PER_CONTAINER} keys",
                path,
            )
        total = 1
        for key, entry in value.items():
            if not isinstance(key, str) or not _KEY_RE.match(key):
                _fail(f"'{path}' contains an invalid key", path)
            total += _check_json_value(entry, depth + 1, f"{path}.{key}")
        return total
    _fail(
        f"'{path}' contains a non-JSON value of type {type(value).__name__}",
        path,
    )
    return 0


def _serialized_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError):
        _fail("result is not JSON serializable")
        raise


def validate_processing_state(value: Any) -> str:
    if not isinstance(value, str) or value not in PROCESSING_STATES:
        raise validation_error(
            f"processingState must be one of: {', '.join(PROCESSING_STATES)}",
            {"path": FIELD_PROCESSING_STATE},
        )
    return value


def validate_processing_attempt_id(value: Any) -> str:
    if not isinstance(value, str) or not _ATTEMPT_ID_RE.match(value):
        raise validation_error(
            "processingAttemptId must be 1..128 characters of [A-Za-z0-9._:-]",
            {"path": FIELD_PROCESSING_ATTEMPT_ID},
        )
    return value


def validate_completed_at(value: Any) -> str:
    if not isinstance(value, str) or not _ISO_RE.match(value):
        raise validation_error(
            "completedAt must be an ISO-8601 UTC timestamp (e.g. 2026-11-01T12:00:00.000Z)",
            {"path": FIELD_COMPLETED_AT},
        )
    return value


def validate_processing_error(value: Any) -> Dict[str, Any]:
    """Kontrollierte Fehlerinfo: nur `code` und `message`, keine freien Felder."""
    if not isinstance(value, Mapping):
        raise validation_error(
            "processingError must be an object with optional 'code' and 'message'",
            {"path": FIELD_PROCESSING_ERROR},
        )
    unknown = [key for key in value if key not in ("code", "message")]
    if unknown:
        raise validation_error(
            f"processingError contains unknown field '{unknown[0]}'",
            {"path": f"{FIELD_PROCESSING_ERROR}.{unknown[0]}"},
        )
    code = value.get("code")
    message = value.get("message")
    if code is not None:
        if not isinstance(code, str) or not code or len(code) > ERROR_MAX_CODE_LENGTH:
            raise validation_error(
                f"processingError.code must be a non-empty string (max {ERROR_MAX_CODE_LENGTH})",
                {"path": f"{FIELD_PROCESSING_ERROR}.code"},
            )
    if message is not None:
        if not isinstance(message, str) or len(message) > ERROR_MAX_MESSAGE_LENGTH:
            raise validation_error(
                f"processingError.message must be a string (max {ERROR_MAX_MESSAGE_LENGTH})",
                {"path": f"{FIELD_PROCESSING_ERROR}.message"},
            )
    if code is None and message is None:
        raise validation_error(
            "processingError requires at least 'code' or 'message'",
            {"path": FIELD_PROCESSING_ERROR},
        )
    return dict(value)


def validate_processing_result(value: Any) -> Any:
    """Validiert die Struktur eines Ergebnisses (keine PII-Erkennung!).

    Technische Validierung ersetzt KEINE Datenschutzpruefung: `result` bleibt
    grundsaetzlich potenziell personenbezogen und wird von Erase/Anonymize
    vollstaendig entfernt.
    """
    if value is None:
        return None
    _check_json_value(value, 0, FIELD_RESULT)
    if _serialized_size(value) > RESULT_MAX_BYTES:
        _fail(f"result exceeds maximum size of {RESULT_MAX_BYTES} bytes")
    return value


def processing_summary(items: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Datensparsame Zusammenfassung fuer privacy/inspect (KEINE Inhalte)."""
    has_result = False
    has_error = False
    states = set()
    for item in items:
        if item.get(FIELD_RESULT) is not None:
            has_result = True
        if item.get(FIELD_PROCESSING_ERROR):
            has_error = True
        state = item.get(FIELD_PROCESSING_STATE)
        if isinstance(state, str) and state:
            states.add(state)
    return {
        "hasProcessingResult": has_result,
        "hasProcessingError": has_error,
        "processingStates": sorted(states),
    }


def public_projection_fields() -> tuple:
    """Felder, die niemals in oeffentlichen API-Antworten erscheinen duerfen."""
    return PROCESSING_FIELDS
