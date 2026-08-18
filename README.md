# May's Orders — AWS Serverless Order Management System

> mays-order-aws — Design and implement a serverless backend for managing the complete lifecycle of customer orders.

Serverless Order-Management-System für den fiktiven Händler **OrderFlow GmbH**.

## Ziel

Implementierung eines vollständigen, dokumentierten und präsentierbaren AWS-Serverless-Projekts,
das den kompletten Lebenszyklus einer Bestellung abbildet:

```text
PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED
```

inkl. definierter Cancellation-Pfade und Ablehnung ungültiger Statusübergänge.

## Architektur (Zielbild)

```text
Client
  │
  ▼
Authentication (Cognito, Entscheidung dokumentiert)
  │
  ▼
API Gateway (HTTP vs. REST, Entscheidung dokumentiert)
  │
  ▼
Lambda (Python 3.14, Handler: index.handler)
  │
  ▼
DynamoDB
  │
  ▼
CloudWatch
```

IAM regelt ausschließlich die Service-to-Service-Berechtigungen (Least Privilege).
Benutzer-Authentifizierung und AWS-Berechtigungen sind strikt getrennt.

## Repository-Struktur

```text
mays-orders/
├── README.md
├── requirements/     Business-/Technical-Requirements, Assumptions
├── architecture/     Architekturdiagramm, Request Flow, Decisions
├── api/              API-Dokumentation, Endpoints, Test-Cases
├── order-lifecycle/  State Machine, Transition Rules
├── database/         DynamoDB-Design, Access Patterns
├── security/         IAM-Design
├── monitoring/       Monitoring-Design
├── reliability/      Konsistenz & Fehlerbehandlung
├── cost/             Kostenanalyse
├── terraform/        Infrastructure as Code (AWS)
├── tests/            Test-Ergebnisse
├── presentation/     Finale Präsentation
└── docs/reports/     Feature-/Task-Reports, Weekly Reports
```

## Projektstatus

| Status | Bedeutung |
|--------|-----------|
| `WEEK 1` | Analyse, Requirements, API, Architektur (dokumentiert) |
| `WEEK 2` | Core Implementation (Lambda/API Gateway/DynamoDB) |
| `WEEK 3` | Business Rules, Reliability, Security |
| `WEEK 4` | Professionalization (Skalierung, Kosten, Well-Architected) |

Aktueller Status: **WEEK 1 — COMPLETE** (Analyse & Architektur abgeschlossen; noch keine Implementierung).

## Workflow-Garantien

- Test-first / evidenzbasierte Ergebnisse — nichts wird behauptet, ohne getestet zu sein.
- Checkpoints nach jedem Schritt (Report → Tests → Build → `git status` → `git diff --check` → Commit → Push).
- Recovery ausschließlich über die Feature-/Task-Reports (`docs/reports/`).
- Keine Secrets, keine API Keys im Source, keine unnötigen AWS-Services.
- Kostenbewusst: Free-Tier beachten, keine dauerhaft laufenden Ressourcen ohne Begründung.

## Dokumentation (Woche 1)

Die Woche-1-Dokumentation liegt in den jeweiligen Unterordnern. Einstieg:

- [Business Requirements](requirements/business-requirements.md)
- [Technical Requirements](requirements/technical-requirements.md)
- [Assumptions & Constraints](requirements/assumptions.md)
- [Order State Machine](order-lifecycle/state-machine.md)
- [State Transition Rules](order-lifecycle/transition-rules.md)
- [API Endpoints](api/endpoints.md)
- [DynamoDB Access Patterns](database/access-patterns.md)
- [Architecture Decisions](architecture/architecture-decisions.md)
- [Vier-Wochen-Plan](docs/reports/four-week-plan.md)

## Projektakte (`docs/`)

- [Project Status](docs/PROJECT_STATUS.md) — zentraler Entwicklungsstand (Single Source of Truth)
- [Project Portfolio](docs/PROJECT_PORTFOLIO.md) — vollständiger Projektweg
- [Changelog](docs/CHANGELOG.md)
- [AGENTS](docs/AGENTS.md) — Projektübersicht & Regeln für AI-/menschliche Mitarbeit
- [Features](docs/features/README.md) — Feature-/Task-Dokumentation (F001–F011)
- [Weekly Reports](docs/reports/) — `WEEK-01…04.md`
- [Documentation Transfer Report](docs/reports/documentation-transfer-report.md)
