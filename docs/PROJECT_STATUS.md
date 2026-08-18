# Project Status — May's Orders

> **Single Source of Truth für den Entwicklungsstand.**
> Nach jedem Checkpoint aktualisieren. Fachliche Entscheidungen liegen in den
> jeweiligen Bereichs-Dokumenten (`requirements/`, `architecture/`, `api/`, …).

## Aktueller Stand (zuletzt aktualisiert: 2026-08-18)

```text
May's Orders — AWS Serverless Order Management System
──────────────────────────────────────────────────────

Current Phase:
Week 2 — IN PROGRESS (Terraform)

Current Feature:
F011 — Terraform Infrastructure

Current Task:
T011-05 — Cognito (COMPLETE) · Next: T011-06 (HTTP API + Routen + Authorizer)

Current Checkpoint:
feature/cognito (T011-05 — Cognito User Pool + Client + Gruppe `staff`)

AWS Resources:
NONE

Application Code:
IMPLEMENTED (Lambda-Handler Python 3.14, `lambda/src/*.py`) — NICHT deployed (kein apply)
Node.js/TypeScript T011-04 bleibt als historische Baseline (45/45 Tests grün)

Terraform:
DynamoDB (T011-02) + IAM (T011-03) + Lambda (T011-04, runtime python3.14) + Cognito (T011-05) konfiguriert; API GW ausstehend

Authentication:
CONFIGURED (Terraform T011-05 — Pool, Client, Gruppe `staff`) — NOT CREATED (kein apply)

API Gateway:
DESIGNED — NOT IMPLEMENTED

Lambda:
CONFIGURED (Terraform + Python-3.14-Code) — NOT CREATED (kein apply)

DynamoDB:
CONFIGURED (Terraform) — NOT CREATED (kein apply)

IAM:
CONFIGURED (Terraform) — NOT CREATED (kein apply)

Cognito Authentication:
CONFIGURED (Terraform T011-05) — NOT CREATED (kein apply)

CloudWatch Monitoring:
DESIGNED — NOT IMPLEMENTED

Tests:
Terraform init/validate PASS (T011-01…T011-05; AWS-Provider ~> 6.0 / 6.60.0);
Python unittest 49/49 PASS · compileall PASS · ZIP-Build/Integrität PASS;
Node-Baseline: Vitest 45/45 PASS (unverändert)
```

## Verlauf der Checkpoints

| Checkpoint | Commit | Inhalt | Push | Status |
|------------|--------|--------|------|--------|
| W1-S1 | `4515029` | Woche-1-Analyse (Requirements, Architektur, Lifecycle, API, DB, Security, Cost, Strategien) + Merge `origin/main` (LICENSE) | SUCCESS | COMPLETE |
| DOC-TRANSFER | `2a89e73` | Dokumentationsübernahme nach Mays-Jobsearch-Muster (Projektakte, Features, Weekly Reports) | SUCCESS | COMPLETE |
| DOC-STATUS | `729ae73` | Statusnachzug Checkpoint `2a89e73` in Status/Changelog/Reports | SUCCESS | COMPLETE |
| DOC-CORRECTION | `4a0a6e7` + `7c12fc0` | Korrektur Review-Inkonsistenzen (Checkpoint 729ae73 als aktuell, WEEK-1 COMPLETE, Commit-/Push-Regel vereinheitlicht) + Statusnachzug | SUCCESS | COMPLETE |
| WORKFLOW-RULE | `7f37340` | Persistent Feature Progress & Crash-Recovery-Regel in Projektakte verankert | SUCCESS | COMPLETE |
| W2-T011-01 | `67f02a3` | F011/T011-01 Terraform-Grundgerüst (main/variables/outputs/README) + `init`/`validate` PASS | SUCCESS | COMPLETE |
| W2-T011-02 | `5d291bd` | F011/T011-02 DynamoDB-Tabelle + GSI1 (PK `pk`/`sk`, GSI1, On-Demand, Outputs) + `init`/`validate` PASS | SUCCESS | COMPLETE |
| W2-PROV-UPGRADE | `fc89aef` | AWS-Provider `~> 5.0` → `~> 6.0` (6.60.0), GSI1 auf `key_schema`-Syntax + `validate` PASS | SUCCESS | COMPLETE |
| W2-T011-03 | `21ed0f4` | F011/T011-03 IAM Lambda Execution Role + Least-Privilege Policy (DynamoDB Tabelle+GSI1, Logs) + `validate` PASS | SUCCESS | COMPLETE |
| W2-DIAG-COMPAT | `a4061e0` (+`6976bd0`) | Provider 6.x Compatibility & Toolchain Verification: Schema autoritativ (CLI 6.60.0), 5.100.0-Altlast bereinigt, `validate` PASS, Checkpoint-Nachzug | SUCCESS | COMPLETE |
| W2-DIAG-FINAL | `e1fd58b` | Final Diagnostic: VS Code/terraform-ls stale 5.100.0-Schema belegt (LSP-Test: SchemaModuleValidation/ReferenceValidation err=nil, `key_schema` in Completion; Root Cause: GSI-`key_schema` ab Provider 6.29.0) | SUCCESS | COMPLETE |
| W2-T011-04 | `449cdd7` | F011/T011-04 Lambda Order Handler (TypeScript, nodejs22.x, Zip-Build `dist/lambda.zip`, Execution Role T011-03, AP1..AP4) + Vitest 45/45 + init/validate PASS | SUCCESS | COMPLETE |
| W2-LAMBDA-PY-314 | `64130a9` (Branch `feature/lambda-python-314`) | Lambda-Migration auf Python 3.14: Handler funktional portiert (AP1..AP4), boto3 (Runtime), ZIP-Build `build_zip.py`, unittest 49/49, `runtime = "python3.14"`, Terraform fmt/init/validate PASS; Node-Baseline bleibt | SUCCESS | COMPLETE |
| W2-PY314-INTEGRATION | `20bfb05` | Python-3.14-Migration nach `main` integriert (`merge --no-ff` von `feature/lambda-python-314`) — Pflicht-Voraussetzung für T011-05; Branch bleibt erhalten | SUCCESS | COMPLETE |
| W2-T011-05 | (Branch `feature/cognito`) | F011/T011-05 Cognito: User Pool (`mays-orders-users`), App Client (`mays-orders-client`, USER_PASSWORD_AUTH + Refresh, Public Client), Gruppe `staff` (`aws_cognito_user_group`) + Outputs; `fmt`/`init`/`validate` PASS, diff-check PASS, Secret-Audit PASS | SUCCESS | COMPLETE |
## Phase-Level-Übersicht

| Bereich | Design | Implementierung | Tests | Live-Verifizierung |
|---------|--------|-----------------|-------|--------------------|
| Requirements | ✅ COMPLETE | – | – | – |
| Order Lifecycle / State Machine | ✅ COMPLETE | ⏳ PLANNED (W2/3) | ⏳ PLANNED | ⏳ PLANNED |
| API Design | ✅ COMPLETE | ⏳ PLANNED (W2) | ⏳ PLANNED | ⏳ PLANNED |
| DynamoDB | ✅ COMPLETE | 🟡 IMPLEMENTED (Terraform T011-02, kein apply) | ⏳ PLANNED | ⏳ PLANNED |
| Cognito Authentication | ✅ COMPLETE | 🟡 IMPLEMENTED (Terraform T011-05, kein apply) | ⏳ PLANNED | ⏳ PLANNED |
| IAM / Security | ✅ COMPLETE | 🟡 IMPLEMENTED (Terraform T011-03, kein apply) | ⏳ PLANNED | ⏳ PLANNED |
| API Gateway (HTTP API) | ✅ COMPLETE | ⏳ PLANNED (W2) | ⏳ PLANNED | ⏳ PLANNED |
| CloudWatch Monitoring | ✅ COMPLETE | ⏳ PLANNED (W3/4) | ⏳ PLANNED | ⏳ PLANNED |
| Terraform | ✅ COMPLETE (Design) | 🔵 IN PROGRESS (T011-05 Cognito konfiguriert) | ⏳ PLANNED | ⏳ PLANNED |
| Skalierung / Kosten / Well-Architected | ⏳ PLANNED (W4) | – | – | – |

## Feature-Status

| Feature | Status | Details |
|---------|--------|---------|
| F001 — Project Foundation | ✅ COMPLETE | Woche-1-Analyse, Docs, Git-Setup |
| F002 — Cognito Authentication | 🟡 DESIGNED | T002-01…03 COMPLETE (Terraform, via F011/T011-05); Design: `security/authentication-decision.md` |
| F003 — API Gateway | ⏳ PLANNED | Design: `architecture/architecture-decisions.md` (ADR-004) |
| F004 — Order Creation | ⏳ PLANNED | Design: `api/endpoints.md`, `database/access-patterns.md` |
| F005 — Order Retrieval | ⏳ PLANNED | Design: `api/endpoints.md` |
| F006 — Order Listing | ⏳ PLANNED | Design: `database/access-patterns.md` (GSI1) |
| F007 — Status Transition | ⏳ PLANNED | Design: `order-lifecycle/transition-rules.md` |
| F008 — Concurrent Update Protection | ⏳ PLANNED | Design: `reliability/consistency-and-failure-handling.md` |
| F009 — IAM / Security | ⏳ PLANNED | Design: `security/iam-design.md` |
| F010 — CloudWatch Monitoring | ⏳ PLANNED | Design: `monitoring/monitoring-design.md` |
| F011 — Terraform Infrastructure | 🔵 IN PROGRESS | T011-01 ✅ · T011-02 ✅ · T011-03 ✅ · T011-04 ✅ · T011-05 ✅ · T011-06 ⏳. Design: `terraform/README.md` |

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