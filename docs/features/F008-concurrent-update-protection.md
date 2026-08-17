# F008 — Concurrent Update Protection

| Feld | Wert |
|------|------|
| **ID** | F008 |
| **Name** | Concurrent Update Protection |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 3 |
| **Abhängigkeiten** | F007 |
| **Fachquelle** | `reliability/consistency-and-failure-handling.md`, `order-lifecycle/transition-rules.md` (§4) |

## Beschreibung

Konkurrierende Statusänderungen erzeugen nie einen inkonsistenten Zustand. DynamoDB
Conditional Write (`status = :current`) ist atomar; der Verlierer erhält 409
`CONFLICTED_UPDATE`. Zusätzliche `version`-Spalte als Reserve (Optimistic Locking).

## Tasks

| ID | Task | Status |
|----|------|--------|
| T008-01 | Conditional-Write-Implementierung verifizieren | ⏳ PLANNED |
| T008-02 | Konkurrenztest R-01 (PROCESSING vs. CANCELLED) | ⏳ PLANNED |
| T008-03 | Konkurrenztest R-02 (Idempotenz) | ⏳ PLANNED |
| T008-04 | 409 CONFLICTED_UPDATE-Mapping | ⏳ PLANNED |
| T008-05 | (Optional) Version-Column als Optimistic Locking | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Konkurrenz-Unit-/Integrationstests | NOT RUN |
| Live: parallele Updates | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T008-01 (Conditional-Write-Verifikation) — nach Freigabe.