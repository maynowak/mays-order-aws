# F006 — Order Listing

| Feld | Wert |
|------|------|
| **ID** | F006 |
| **Name** | Order Listing |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 2 |
| **Abhängigkeiten** | F002, F003, F011 |
| **Fachquelle** | `api/endpoints.md` (§2.3), `database/access-patterns.md` (AP3), `database/dynamodb-design.md` (GSI1) |

## Beschreibung

`GET /orders`: `Query` auf GSI1 (`gsi1pk=LIST`, `ScanIndexForward=false`) mit `limit` und
`nextToken`-Pagination. **Kein Scan.**

## Tasks

| ID | Task | Status |
|----|------|--------|
| T006-01 | GSI1 in Terraform definieren | ⏳ PLANNED |
| T006-02 | Query-Logik (Sortierung, Limit) | ⏳ PLANNED |
| T006-03 | Pagination (nextToken = LastEvaluatedKey) | ⏳ PLANNED |
| T006-04 | Kompakte Listen-Response | ⏳ PLANNED |
| T006-05 | Automatisierte Tests (T-10…T-12) | ⏳ PLANNED |
| T006-06 | Live-API-Verifikation (inkl. Pagination) | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Unit-Tests (Query/Pagination) | NOT RUN |
| Live: GET /orders 200 | NOT RUN |
| Live: Pagination | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T006-01 (GSI1 in Terraform) — nach Freigabe.