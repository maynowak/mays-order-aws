# Vier-Wochen-Plan — May's Orders

> Master-Dokument für die Schrittfolge der vier Projektwochen.
> Jedes Feature folgt dem Workflow aus Abschnitt §5 (Step 1–7 inkl. Checkpoint).

## Woche 1 — Analyse, Requirements, API & Architektur  ✅ (in Arbeit)

| # | Deliverable | Datei | Status |
|---|-------------|-------|--------|
| 1 | Business Requirements | `requirements/business-requirements.md` | DONE |
| 2 | Technical Requirements | `requirements/technical-requirements.md` | DONE |
| 3 | Assumptions & Constraints | `requirements/assumptions.md` | DONE |
| 4 | Order Lifecycle & State Machine | `order-lifecycle/state-machine.md` | DONE |
| 5 | Transition Matrix & Regeln | `order-lifecycle/transition-rules.md` | DONE |
| 6 | API Endpoint Design | `api/endpoints.md`, `api/api-documentation.md` | DONE |
| 7 | DynamoDB Access Patterns & Modell | `database/dynamodb-design.md`, `database/access-patterns.md` | DONE |
| 8 | Auth-Entscheidung (Cognito/JWT, HTTP vs REST) | `security/authentication-decision.md` | DONE |
| 9 | IAM-Konzept (Least Privilege) | `security/iam-design.md` | DONE |
| 10 | Architektur-Varianten + Entscheidung | `architecture/architecture-decisions.md` | DONE |
| 11 | Architekturdiagramm | `architecture/architecture-diagram.svg` | DONE |
| 12 | Request-Flow | `architecture/request-flow.md` | DONE |
| 13 | Monitoring-/Cost-/Reliability-Konzepte | `monitoring/`, `cost/`, `reliability/` | DONE |
| 14 | Vier-Wochen-Plan + Strategien | dieses Dokument | DONE |

**Checkpoint 1:** MENSCHLICHE PRÜFUNG vor Woche 2. → **STOP** (Anweisung §20).

## Woche 2 — Core Implementation

| # | Feature | Schritte |
|---|---------|----------|
| 1 | Repo-Setup: Node/TypeScript-Projekt, Test-Framework, Struktur | Setup + Unit-Test-Skeleton |
| 2 | Terraform-Grundgerüst (main/variables/outputs, Provider, DynamoDB, IAM) | `terraform validate` + `plan` |
| 3 | Cognito User Pool + Client + Gruppe `staff` (Terraform) | validate/plan, ggf. User anlegen |
| 4 | API Gateway (HTTP API) + Lambda-Integration + JWT-Autorisator | validate/plan |
| 5 | Lambda-Handler: POST/GET/GET-list/PATCH (Core) | Implementierung + Unit-Tests |
| 6 | DynamoDB-Integration (Conditional Writes, GSI-Query, Pagination) | Implementierung + Unit-Tests |
| 7 | Deployment + **Live-API-Tests** (alle 4 Endpunkte, Auth) | `terraform apply` (Freigabe!) + curl |
| 8 | Fehlerfälle verifizieren (400/401/404/409/500) | Live-Tests |
| 9 | CloudWatch-Logs verifizieren | Live-Check |

**Checkpoint nach jedem Feature** (Report → Tests → Build → git → push).

## Woche 3 — Business Rules, Reliability & Security

| # | Feature | Schritte |
|---|---------|----------|
| 1 | State Machine als Domain-Modul + Unit-Tests (alle 18 Fälle) | Implementierung + Tests |
| 2 | Conditional-Write-Integration + Konkurrenztest (R-01, R-02) | Tests + Live |
| 3 | Idempotenz-Semantik final festlegen + Test | Tests |
| 4 | Security: Auth-Authorization-Logik, Group-Checks, kein PII im Log | Tests + Live |
| 5 | CloudWatch-Alarme/Dashboard (kostenbewusst) | Terraform + Verify |
| 6 | Negativ-Tests (unauth, falsches Token, 401/403) | Live |
| 7 | Doku-Update aller Security-/Reliability-Entscheidungen | Docs |

## Woche 4 — Professionalization

| # | Feature | Schritte |
|---|---------|----------|
| 1 | Skalierungsanalyse (100 → 100k Orders/Tag, Hot Partitions, Query/Scan) | Analyse + Messung |
| 2 | Kostenmessung (Metered Usage, CloudWatch-Billing) | Messen + Dokumentieren |
| 3 | Well-Architected-Review (5 Säulen) | Review-Dokument |
| 4 | API-Doku/OpenAPI finalisieren | Docs |
| 5 | Test-Endbericht (`tests/test-results.md`) vollständig | Tests |
| 6 | Weekly Reports + Finale Präsentation | Docs + PDF |
| 7 | Cleanup-Bewertung (Terraform Destroy nach Freigabe) | Analyse |

## Feature-Workflow (verbindlich)

```text
Step 1  Analyse / Bestandsaufnahme
Step 2  AWS-Entscheidung + Konfiguration
Step 3  Implementierung
Step 4  Tests (Unit/API/Invalid-Transition)
Step 5  Live-Verifikation (bei Infra/API-Änderung)
Step 6  Dokumentation (Report + relevant Docs)
Step 7  Git Checkpoint: report → tests → build → git status → diff --check → secret-audit → commit → push
```

Ein Step gilt erst als COMPLETE, wenn der Checkpoint **gepusht** wurde.

## Recovery-Regel

Bei Absturz/Unterbrechung:

1. `git status` / Branch / `git rev-parse HEAD`
2. Remote-Stand prüfen
3. Feature-/Task-Report lesen (`docs/reports/`)
4. letzten COMPLETE-Checkpoint bestimmen
5. nur mit dem nächsten offenen Step fortfahren (nichts aus Chat-History rekonstruieren)