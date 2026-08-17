# F007 — Status Transition

| Feld | Wert |
|------|------|
| **ID** | F007 |
| **Name** | Status Transition (State Machine) |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 3 |
| **Abhängigkeiten** | F004 |
| **Fachquelle** | `order-lifecycle/state-machine.md`, `order-lifecycle/transition-rules.md` |

## Beschreibung

`PATCH /orders/{orderId}/status`: State Machine im Domain-Layer (kein Step Functions, ADR-005)
validiert den Übergang; `UpdateItem` mit Conditional Write setzt den neuen Status. Ungültige
Übergänge → 409, fehlende Order → 404, ungültiger Statuswert → 400.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T007-01 | State-Machine-Modul (Transition-Tabelle) implementieren | ⏳ PLANNED |
| T007-02 | Unit-Tests: 18 Fälle (SM-01…18) | ⏳ PLANNED |
| T007-03 | Conditional UpdateItem integrieren | ⏳ PLANNED |
| T007-04 | Fehler-Mappings (409/404/400) | ⏳ PLANNED |
| T007-05 | Idempotenz-Semantik festlegen + Test | ⏳ PLANNED |
| T007-06 | Live-Tests: gültige/ungültige Übergänge | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Unit-Tests (State Machine) | NOT RUN |
| Live: gültige Übergänge | NOT RUN |
| Live: ungültige Übergänge (409) | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T007-01 (State-Machine-Modul) — nach Freigabe.