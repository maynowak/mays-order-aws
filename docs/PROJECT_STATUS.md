# Project Status — May's Orders

> **Single Source of Truth für den Entwicklungsstand.**
> Nach jedem Checkpoint aktualisieren. Fachliche Entscheidungen liegen in den
> jeweiligen Bereichs-Dokumenten (`requirements/`, `architecture/`, `api/`, …).

## Aktueller Stand (zuletzt aktualisiert: 2026-08-17)

```text
May's Orders — AWS Serverless Order Management System
──────────────────────────────────────────────────────

Current Phase:
Week 1 — COMPLETE (Analyse & Architektur)

Current Checkpoint:
7f37340 (Persistent Feature Progress & Crash-Recovery-Regel)

AWS Resources:
NONE

Application Code:
NOT STARTED

Terraform:
DESIGN ONLY

Authentication:
DESIGNED — NOT IMPLEMENTED

API Gateway:
DESIGNED — NOT IMPLEMENTED

Lambda:
DESIGNED — NOT IMPLEMENTED

DynamoDB:
DESIGNED — NOT IMPLEMENTED

CloudWatch Monitoring:
DESIGNED — NOT IMPLEMENTED

Tests:
NOT RUN (Woche 1, keine Implementierung)
```

## Verlauf der Checkpoints

| Checkpoint | Commit | Inhalt | Push | Status |
|------------|--------|--------|------|--------|
| W1-S1 | `4515029` | Woche-1-Analyse (Requirements, Architektur, Lifecycle, API, DB, Security, Cost, Strategien) + Merge `origin/main` (LICENSE) | SUCCESS | COMPLETE |
| DOC-TRANSFER | `2a89e73` | Dokumentationsübernahme nach Mays-Jobsearch-Muster (Projektakte, Features, Weekly Reports) | SUCCESS | COMPLETE |
| DOC-STATUS | `729ae73` | Statusnachzug Checkpoint `2a89e73` in Status/Changelog/Reports | SUCCESS | COMPLETE |
| DOC-CORRECTION | `4a0a6e7` + `7c12fc0` | Korrektur Review-Inkonsistenzen (Checkpoint 729ae73 als aktuell, WEEK-1 COMPLETE, Commit-/Push-Regel vereinheitlicht) + Statusnachzug | SUCCESS | COMPLETE |
| WORKFLOW-RULE | `7f37340` | Persistent Feature Progress & Crash-Recovery-Regel in Projektakte verankert | SUCCESS | COMPLETE |

## Phase-Level-Übersicht

| Bereich | Design | Implementierung | Tests | Live-Verifizierung |
|---------|--------|-----------------|-------|--------------------|
| Requirements | ✅ COMPLETE | – | – | – |
| Order Lifecycle / State Machine | ✅ COMPLETE | ⏳ PLANNED (W2/3) | ⏳ PLANNED | ⏳ PLANNED |
| API Design | ✅ COMPLETE | ⏳ PLANNED (W2) | ⏳ PLANNED | ⏳ PLANNED |
| DynamoDB | ✅ COMPLETE | ⏳ PLANNED (W2) | ⏳ PLANNED | ⏳ PLANNED |
| Cognito Authentication | ✅ COMPLETE | ⏳ PLANNED (W2) | ⏳ PLANNED | ⏳ PLANNED |
| IAM / Security | ✅ COMPLETE | ⏳ PLANNED (W2/3) | ⏳ PLANNED | ⏳ PLANNED |
| API Gateway (HTTP API) | ✅ COMPLETE | ⏳ PLANNED (W2) | ⏳ PLANNED | ⏳ PLANNED |
| CloudWatch Monitoring | ✅ COMPLETE | ⏳ PLANNED (W3/4) | ⏳ PLANNED | ⏳ PLANNED |
| Terraform | ✅ COMPLETE (Design) | ⏳ PLANNED (W2) | ⏳ PLANNED | ⏳ PLANNED |
| Skalierung / Kosten / Well-Architected | ⏳ PLANNED (W4) | – | – | – |

## Feature-Status

| Feature | Status | Details |
|---------|--------|---------|
| F001 — Project Foundation | ✅ COMPLETE | Woche-1-Analyse, Docs, Git-Setup |
| F002 — Cognito Authentication | ⏳ PLANNED | Design: `security/authentication-decision.md` |
| F003 — API Gateway | ⏳ PLANNED | Design: `architecture/architecture-decisions.md` (ADR-004) |
| F004 — Order Creation | ⏳ PLANNED | Design: `api/endpoints.md`, `database/access-patterns.md` |
| F005 — Order Retrieval | ⏳ PLANNED | Design: `api/endpoints.md` |
| F006 — Order Listing | ⏳ PLANNED | Design: `database/access-patterns.md` (GSI1) |
| F007 — Status Transition | ⏳ PLANNED | Design: `order-lifecycle/transition-rules.md` |
| F008 — Concurrent Update Protection | ⏳ PLANNED | Design: `reliability/consistency-and-failure-handling.md` |
| F009 — IAM / Security | ⏳ PLANNED | Design: `security/iam-design.md` |
| F010 — CloudWatch Monitoring | ⏳ PLANNED | Design: `monitoring/monitoring-design.md` |
| F011 — Terraform Infrastructure | ⏳ PLANNED | Design: `terraform/README.md` |

Detaillierte Feature-Dokumentation: `docs/features/`.

## Status-Konvention

| Status | Bedeutung |
|--------|-----------|
| ✅ COMPLETE | Design/Implementierung abgeschlossen, gepusht |
| ⏳ PLANNED | Geplant, noch nicht begonnen |
| 🔵 IN PROGRESS | Begonnen, Checkpoint offen |
| 🟡 DESIGNED | Design dokumentiert, Implementierung offen |
| 🚧 BLOCKED | Hindernis, Ursache im Report dokumentiert |
| ⚪ NOT VERIFIED | Implementiert, nicht (live) geprüft |

## Recovery-Einstieg

```
git HEAD
   ↓
docs/PROJECT_STATUS.md      (dieses Dokument — aktueller Gesamtstand)
   ↓
docs/reports/WEEK-NN.md     (Wochenreport)
   ↓
docs/features/README.md     (Feature-Index)
   ↓
Aktive Feature-Doku         (docs/features/FXXX-*.md — laufender Arbeitsstand,
   ↓                         Current Task, Changes, Tests, Next Step)
docs/reports/recovery-checkpoint-strategy.md
```

> Der semantische Arbeitsstand eines aktiven Features steht in der Feature-Dokumentation —
> nicht im Chatverlauf. Template: `docs/features/_progress-template.md`.