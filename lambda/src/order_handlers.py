"""Interne Order-Handler-Registry (MO-RC4-P02E, erweitert P02G-B).

Der Worker bestimmt anhand von `orderType` (aus dem gespeicherten Order-Item,
NICHT aus der SQS-Nachricht), welche interne Verarbeitungsroutine laeuft.

Zwei Handler-Klassen:

1. **Status-Handler** (`processing=False`, z. B. `generic`)
   Verhalten wie bisher: der Worker fuehrt nach erfolgreicher Ausfuehrung den
   Statusuebergang aus (P02C). Kein Processing-State, kein Ergebnis.

2. **Processing-Handler** (`processing=True`)
   Der Worker setzt vorher einen Processing-Claim (`processingState=running`,
   `processingAttemptId`), ruft den Handler mit einem Kontext auf und uebernimmt
   das Ergebnis atomar. Der Handler gibt ein strukturiertes Ergebnis zurueck
   oder wirft `ProcessingFailure` fuer einen kontrollierten fachlichen Fehler.

Regeln (unveraendert):
- Explizite Registrierung, keine dynamischen Imports, keine Duplikate.
- Handler schreiben NIE Status, Ownership oder Ergebnis selbst.
- Unbekannte Typen werden abgelehnt; nur ein FEHLENDES `orderType` gilt als
  Legacy und laeuft als `generic`.

Idempotenzvertrag fuer Processing-Handler (MO-RC4-P02I-A):
- `context["attemptId"]` ist die Identitaet EINES Versuchs (Claim-Fencing,
  Ergebnisuebernahme, Diagnose). Sie ist bei jedem Wiederholungsversuch neu und
  taugt NICHT als alleiniger externer Idempotency Key.
- `orderId` (im Order-Item und in der SQS-Nachricht) ist die stabile fachliche
  Auftragsidentitaet und eignet sich als externer Idempotency Key.
- MO garantiert idempotente Status-/Ergebnisuebernahme, NICHT idempotente
  externe Seiteneffekte. Handler muessen eigene Seiteneffekte gegen `orderId`
  absichern (keine Exactly-once-Zusage).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from order_types import DEFAULT_ORDER_TYPE
from validation import validate_order_type

# Status-Handler: (order_item, payload) -> None
StatusHandler = Callable[[Mapping[str, Any], Mapping[str, Any]], None]
# Processing-Handler: (order_item, payload, context) -> strukturiertes Ergebnis
ProcessingHandler = Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], Any]

Handler = Any


class ProcessingFailure(Exception):
    """Kontrollierter fachlicher Fehler eines Processing-Handlers.

    Wird vom Worker als `processingState=failed` mit validiertem
    `processingError` gespeichert (kein Stacktrace, keine freie Exception).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class HandlerSpec:
    handler: Handler
    processing: bool = False


_HANDLERS: Dict[str, HandlerSpec] = {}


def register(order_type: str, handler: Handler = None, *, processing: bool = False):
    """Registriert einen Handler explizit (deterministisch, ohne Duplikate).

    Nutzbar als `register("typ", funktion)`, `register("typ", processing=True)`
    oder als Dekorator `@register("typ", processing=True)`.
    """

    def _register(fn: Handler) -> Handler:
        validated = validate_order_type(order_type)
        if validated in _HANDLERS:
            raise ValueError(f"Handler for orderType '{validated}' is already registered")
        _HANDLERS[validated] = HandlerSpec(handler=fn, processing=processing)
        return fn

    if handler is None:
        return _register
    return _register(handler)


def get_handler_spec(order_type: str) -> Optional[HandlerSpec]:
    return _HANDLERS.get(order_type)


def get_handler(order_type: str):
    """Liefert die registrierte Funktion oder None (Kompatibilitaets-API)."""
    spec = _HANDLERS.get(order_type)
    return spec.handler if spec else None


def is_registered(order_type: str) -> bool:
    return order_type in _HANDLERS


def is_processing_handler(order_type: str) -> bool:
    spec = _HANDLERS.get(order_type)
    return bool(spec and spec.processing)


def registered_types():
    """Sortierte Liste der registrierten Typen (fuer Tests/Diagnose)."""
    return sorted(_HANDLERS)


def _generic_handler(order: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    """Bewahrt das bisherige Verhalten: keine zusaetzliche Fachlogik.

    Der Statusuebergang (PENDING -> CONFIRMED) erfolgt wie bisher durch den
    Worker nach erfolgreicher Handler-Ausfuehrung. Dieser Handler ist bewusst
    NICHT processing-faehig.
    """
    return None


# Einziger produktiver Handler. Processing-Handler werden explizit mit
# `processing=True` registriert (kein stilles Umschalten bestehender Handler).
register(DEFAULT_ORDER_TYPE, _generic_handler)
