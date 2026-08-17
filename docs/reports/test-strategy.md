# Teststrategie — May's Orders

## 1. Prinzipien

- **Test-first / evidenzbasiert:** Kein Ergebnis wird als PASS gemeldet, ohne dass der
  Test tatsächlich lief.
- Klare Trennung der Aussagen: `Build: PASS` ≠ `Live API: PASS`.
- Jede Testebene hat ein eigenes Artefakt/dokumentiertes Ergebnis.

## 2. Testpyramide

```text
        ┌──────────────┐
        │ Live API     │  (curl gegen deployed Gateway)
        ├──────────────┤
        │ Integration  │  (Lambda-Handler + DynamoDB, lokal via Testcontainers/mock)
        ├──────────────┤
        │ Unit         │  (State Machine, Validierung, Betragsberechnung)
        └──────────────┘
```

| Ebene | Werkzeug (Vorschlag) | Abdeckung |
|-------|----------------------|-----------|
| Unit | Vitest/Jest (Node/TS) | State Machine (SM-01…18), Validierung, `totalAmount` |
| Integration | AWS-SDK gegen DynamoDB (lokal oder Dev) | Put/Get/Query/Update + Conditional-Write-Konkurrenz |
| Live API | `curl` + Cognito-Token | alle Endpoints, Auth, Fehlerfälle (T-01…16, A-01…04) |
| Terraform | `terraform validate`, `terraform plan`, ggf. `tflint` | IaC-Korrektheit, Policy-Review |

## 3. Welche Tests werden wann ausgeführt

| Phase | Tests |
|-------|-------|
| Nach jedem Feature | Syntax, Type-Check, Unit-Tests, Build |
| Vor Deployment | `terraform validate` + `terraform plan` (Review) |
| Nach Deployment | Live-API-Tests (alle Endpoints + Auth + Fehlerfälle) |
| Woche 3 | Konkurrenz-Tests, Invalid-Transition-Tests, Auth-Negativ-Tests |
| Woche 4 | Last/Skalierungs-Messung, Kosten-Messung, Well-Architected-Check |

## 4. Ergebnisdokumentation

- Alle Ergebnisse in `tests/test-results.md`, tabellarisch, mit Datum/Uhrzeit.
- **NOT VERIFIED** für alles, was nicht ausgeführt wurde.
- Fehlschläge → Blocked-Bericht in `docs/reports/` + Checkpoint (Commit/Push des Zustands).

## 5. Keine erfundenen Ergebnisse

- Ergebnisse nur nach tatsächlicher Ausführung eintragen.
- Bei AWS-Abhängigkeit ohne Zugriff: Status `NOT RUN (kein Zugriff)` eintragen — nie erfinden.