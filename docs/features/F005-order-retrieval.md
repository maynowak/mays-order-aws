# F005 — Order Retrieval

| Feld | Wert |
|------|------|
| **ID** | F005 |
| **Name** | Order Retrieval |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 2 |
| **Abhängigkeiten** | F002, F003, F011 |
| **Fachquelle** | `api/endpoints.md` (§2.2), `database/access-patterns.md` (AP2) |

## Beschreibung

`GET /orders/{orderId}`: `GetItem` per Primärschlüssel; 404 bei nicht vorhandener ID,
400 bei ungültigem ID-Format.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T005-01 | orderId-Format validieren | ⏳ PLANNED |
| T005-02 | DynamoDB `GetItem` (pk=ORDER#<id>) | ⏳ PLANNED |
| T005-03 | 404 ORDER_NOT_FOUND Mapping | ⏳ PLANNED |
| T005-04 | Automatisierte Tests (T-07…T-09) | ⏳ PLANNED |
| T005-05 | Live-API-Verifikation | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Unit-Tests | NOT RUN |
| Live: GET 200 | NOT RUN |
| Live: 404 / 400 | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T005-01 (ID-Validierung) — nach Freigabe.