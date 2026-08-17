# F004 — Order Creation

| Feld | Wert |
|------|------|
| **ID** | F004 |
| **Name** | Order Creation |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 2 |
| **Abhängigkeiten** | F002, F003, F011 |
| **Fachquelle** | `api/endpoints.md` (§2.1), `database/access-patterns.md` (AP1) |

## Beschreibung

`POST /orders`: Request-Validierung, Order-ID-Generierung, server-seitige
`totalAmount`-Berechnung, `PutItem` in DynamoDB mit Startstatus `PENDING`, Antwort 201.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T004-01 | Request-Modell / Typen definieren | ⏳ PLANNED |
| T004-02 | Input-Validierung (Pflichtfelder, E-Mail, Beträge) | ⏳ PLANNED |
| T004-03 | Order-ID-Generierung (`ord_` + eindeutig) | ⏳ PLANNED |
| T004-04 | `totalAmount` server-seitig berechnen (Cent) | ⏳ PLANNED |
| T004-05 | DynamoDB `PutItem` (pk, sk, gsi1pk, status=PENDING) | ⏳ PLANNED |
| T004-06 | Fehler-Handling (400/500) | ⏳ PLANNED |
| T004-07 | Automatisierte Tests (T-01…T-06) | ⏳ PLANNED |
| T004-08 | Live-API-Verifikation (201 + Validierungsfälle) | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Unit-Tests (Validierung, Betrag) | NOT RUN |
| Live: POST /orders 201 | NOT RUN |
| Live: 400-Fälle | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T004-01 (Request-Modell) — nach Freigabe.