"""Interne Order-Handler-Registry (MO-RC4-P02E).

Der Worker bestimmt anhand von `orderType` (aus dem gespeicherten Order-Item,
NICHT aus der SQS-Nachricht), welche interne Verarbeitungsroutine laeuft.

Regeln:
- Explizite Registrierung ueber `@register("<typ>")` — keine dynamischen Imports,
  keine Modul-/Dateipfade, keine externe Agenten-Registry.
- Der Handler fuehrt ausschliesslich fachliche Arbeit aus. Statusuebergaenge
  schreibt IMMER der Worker ueber `sqs_handler._process_order` (P02C-Schutz).
- Handler werfen bei Fehlern; der Worker quittiert das nicht als Erfolg
  (Item-Failure -> Retry -> DLQ).
- Unbekannte Typen werden abgelehnt (kein stiller Fallback auf `generic`);
  nur ein FEHLENDES Feld (`orderType` fehlt) gilt als Legacy und laeuft als
  `generic`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from order_types import DEFAULT_ORDER_TYPE
from validation import validate_order_type

# Handler-Signatur: (order_item, payload) -> None
OrderHandler = Callable[[Mapping[str, Any], Mapping[str, Any]], None]

_HANDLERS: Dict[str, OrderHandler] = {}


def register(order_type: str, handler: OrderHandler = None):
    """Registriert einen Handler explizit (deterministisch, ohne Duplikate).

    Nutzbar als `register("typ", funktion)` oder als Dekorator
    `@register("typ")`. Keine dynamischen Imports, keine Duplikate.
    """

    def _register(fn: OrderHandler) -> OrderHandler:
        validated = validate_order_type(order_type)
        if validated in _HANDLERS:
            raise ValueError(f"Handler for orderType '{validated}' is already registered")
        _HANDLERS[validated] = fn
        return fn

    if handler is None:
        return _register
    return _register(handler)


def get_handler(order_type: str):
    """Liefert den registrierten Handler oder None (unbekannter Typ)."""
    return _HANDLERS.get(order_type)


def is_registered(order_type: str) -> bool:
    return order_type in _HANDLERS


def registered_types():
    """Sortierte Liste der registrierten Typen (fuer Tests/Diagnose)."""
    return sorted(_HANDLERS)


def _generic_handler(order: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    """Bewahrt das bisherige Verhalten: keine zusaetzliche Fachlogik.

    Der Statusuebergang (PENDING -> CONFIRMED) erfolgt wie bisher durch den
    Worker nach erfolgreicher Handler-Ausfuehrung.
    """
    return None


# Einziger produktiver Handler. Weitere interne Handler werden hier explizit
# ergaenzt (z. B. @register("internal.report.generate")).
register(DEFAULT_ORDER_TYPE, _generic_handler)
