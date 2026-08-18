# Changelog — May's Orders

> Nur tatsächliche Änderungen. Jeder Eintrag referenziert einen echten Checkpoint.

## 2026-08-18 — Presentation Technical Q&A (Dokumentations-Nachzug)

### Dokumentation
- `docs/reports/PRESENTATION-TECHNICAL-QA.md` (neu): Vorbereitung für die
  Projektbesprechung/Präsentation — Project Context (schulische Vorgabe vs.
  technische Umsetzung vs. technische Alternative), Current Architecture,
  Node.js vs Python 3.14, FastAPI vs API Gateway (Alternative, nicht
  implementiert), HTTP/JSON API, Cognito + JWT, Lambda, Error Handling
  (400/404/409/500), DynamoDB + GSI, IAM, Terraform, Terraform State (≠ Order
  State), S3 Backend (T011-09 optional), validate/plan/apply, Fragen + kurze +
  vertiefte Antworten, Open Questions.
- Reiner Dokumentationsnachzug auf Basis von `main` `6933680`. Keine Code-,
  Architektur- oder Feature-Änderung; kein `terraform plan`/`apply`; keine
  AWS-Ressourcen.

### Status
- Unverändert: T011-01…T011-07 COMPLETE · T011-08 PLANNED (Freigabe
  erforderlich) · T011-09 OPTIONAL · AWS Resources: NONE.

## 2026-08-18 — Terraform Validate + Plan Review T011-07 (F011, Branch `feature/t011-07-plan-review`)

### Verifikation (read-only, kein Code-Change)
- `terraform version`: v1.15.8 · `terraform providers`: aws `~> 6.0` (6.60.0).
- `terraform fmt -check`: PASS · `terraform init`: PASS (Lockfile wiederverwendet) ·
  `terraform validate`: PASS.
- `terraform plan`: RUN — **16 to add, 0 to change, 0 to destroy**; ausschließlich
  Neu-Erstellungen der dokumentierten Ressourcen (DynamoDB, IAM, Lambda python3.14,
  Cognito, HTTP API + 4 Routen + JWT-Authorizer + Permission); keine unexpected
  changes, kein REPLACE, keine Discrepancies.
- Plan-Klassifikation: **A) EXPECTED/CLEAN**.
- `git diff --check`: PASS · Secret-Audit: PASS.
- `terraform apply`: NOT RUN — Freigabe erforderlich (T011-08).
- Report: `docs/reports/T011-07-TERRAFORM-PLAN-REVIEW.md`.

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01…07 + T011-04-CLEANUP COMPLETE ·
  T011-08 NEXT · AWS Resources: NONE.

## 2026-08-18 — T011-04 Python Cleanup (F011, Branch `feature/lambda-python-cleanup`)

### Implementierung
- Node.js/TypeScript-Baseline (T011-04) aus dem aktiven Lambda-Projekt entfernt:
  `lambda/src/index.ts`, `orderService.ts`, `stateMachine.ts`, `validation.ts`,
  `errors.ts`, `types.ts` sowie `lambda/tests/orderService.test.ts`,
  `stateMachine.test.ts`, `validation.test.ts`, `lambda/package.json`,
  `lambda/package-lock.json`, `lambda/tsconfig.json`, `lambda/vitest.config.ts`.
- Lokal entfernt (gitignored): `lambda/node_modules/`, `lambda/dist/index.js`.
- Keine Python-Codeänderung; `python3.14` bleibt aktive Lambda-Runtime
  (`terraform/main.tf` unverändert). Baseline via Git-Historie `449cdd7`.
- Kein `plan`, kein `apply`; T011-05/T011-06 (Cognito, HTTP API) unverändert.

### Validation
- `python3 -m compileall -q src tests` PASS · Python unittest 49/49 PASS.
- `python3 build_zip.py` PASS (6 Module) · `unzip -t dist/lambda.zip` PASS.
- Terraform `fmt -check` / `init` / `validate` PASS · `git diff --check` PASS ·
  Secret-Audit PASS.
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe).

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01…06 + T011-04-CLEANUP COMPLETE ·
  T011-07 NEXT · AWS Resources: NONE.

## 2026-08-18 — HTTP API T011-06 (F011 / F003, Branch `feature/http-api`)

### Implementierung
- `terraform/main.tf`: `aws_apigatewayv2_api.orders` (`mays-orders-api`, HTTP/ADR-004) +
  `aws_apigatewayv2_stage.default` (`$default`, auto_deploy).
- `terraform/main.tf`: `aws_apigatewayv2_authorizer.jwt` (JWT, identity_sources
  `$request.header.Authorization`; issuer = `https://<cognito-endpoint>` aus
  `aws_cognito_user_pool.users.endpoint`, audience = `aws_cognito_user_pool_client.app.id`
  — keine hardcodierten IDs).
- `terraform/main.tf`: `aws_apigatewayv2_integration.lambda` (AWS_PROXY, Payload 2.0,
  URI = `aws_lambda_function.handler.invoke_arn` — bestehende Python-3.14-Lambda).
- `terraform/main.tf`: vier `aws_apigatewayv2_route.*` — `POST /orders`,
  `GET /orders/{orderId}`, `GET /orders`, `PATCH /orders/{orderId}/status` — alle
  `authorization_type = "JWT"` + `authorizer_id`.
- `terraform/main.tf`: `aws_lambda_permission.api_gateway` (principal
  `apigateway.amazonaws.com`, `source_arn = ${execution_arn}/*/*`).
- `terraform/outputs.tf`: `api_gateway_endpoint`, `api_gateway_id`,
  `api_gateway_authorizer_id`.
- `terraform/README.md`: §2.5 HTTP API + Ressourcentabelle.
- `lambda/src/index.py`: **unverändert** — Event-Contract (v2) passt exakt (verifiziert).
- Bewusst NICHT in T011-06: REST API, öffentliche Routen, `cognito:groups`-Auswertung
  im Lambda (Woche 3), plan (T011-07), apply (T011-08).

### Validation
- Terraform `fmt`/`init`/`validate`: PASS (AWS-Provider 6.60.0, ohne Warnungen).
- `git diff --check`: PASS · Secret-Audit: PASS.
- Python-Validierung: NOT RUN — `index.py` unverändert (bestehender Nachweis gültig).
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe).

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01…06 COMPLETE · T011-07 NEXT ·
  F003 T003-01…06 COMPLETE (Terraform) · AWS Resources: NONE.

## 2026-08-18 — Cognito T011-05 (F011 / F002, Branch `feature/cognito`)

### Implementierung
- `terraform/main.tf`: `aws_cognito_user_pool.users` (${var.project_name}-users) —
  `admin_create_user_config.allow_admin_create_user_only = true` (Staff-Admin-Anlage,
  keine offene Registrierung), Passwortrichtlinie Standardwerte (min. 8,
  Upper/Lower/Number/Symbol), `mfa_configuration = "OFF"`.
- `terraform/main.tf`: `aws_cognito_user_pool_client.app` (${var.project_name}-client) —
  `explicit_auth_flows = [ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH]`,
  `generate_secret = false` (Public Client, Voraussetzung für USER_PASSWORD_AUTH).
- `terraform/main.tf`: `aws_cognito_user_group.staff` (Gruppe `staff` → Claim
  `cognito:groups`, Basis der Authorization A-09). Ressourcen-Typ `aws_cognito_user_group`
  (Provider 6.60.0; nicht `aws_cognito_user_pool_group`).
- `terraform/outputs.tf`: `cognito_user_pool_id`, `cognito_user_pool_arn`,
  `cognito_user_pool_client_id`, `cognito_user_pool_group_name`.
- `terraform/README.md`: §2.4 Cognito (Ressourcentabelle, JWT-Flow, bewusste Nicht-Features).
- Bewusst NICHT in T011-05: `user_pool_domain` (kein Hosted-UI nötig), API-GW/JWT-Authorizer/
  Lambda-Invoke-Permission (T011-06), Testbenutzer (T002-04).
- Integration: `feature/lambda-python-314` → `main` gemerged (Commit `20bfb05`,
  Pflicht-Voraussetzung); `feature/cognito` → `main` gemerged (Commit `dd9bb58`);
  `feature/http-api` → `main` gemerged (Commit `8a85b5e`). Feature-Branches bleiben erhalten.

### Validation
- Terraform `fmt`/`init`/`validate`: PASS (AWS-Provider 6.60.0, ohne Warnungen).
- `git diff --check`: PASS · Secret-Audit: PASS.
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe).
- Live/Login: NOT RUN (kein apply).

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01…05 COMPLETE · T011-06 NEXT ·
  F002 T002-01…03 COMPLETE (Terraform) · AWS Resources: NONE.

## 2026-08-18 — Lambda-Migration auf Python 3.14 (F011 / T011-04, Checkpoint `64130a9`, Branch `feature/lambda-python-314`)

### Implementierung
- `lambda/src/*.py` (neu): Python-Port des Lambda-Order-Handlers — `index.py`
  (Handler, API-GW-v2-Event, Routing, Fehler→HTTP), `order_service.py` (AP1..AP4,
  boto3), `state_machine.py` (Transition-Matrix), `validation.py`, `errors.py`,
  `order_types.py` (bewusst NICHT `types.py` — kollidiert mit Stdlib-`types` im
  Lambda-ZIP). Node.js/TypeScript-Baseline (T011-04) bleibt vollständig erhalten.
- `lambda/tests/test_*.py` (neu, unittest): `test_state_machine.py`,
  `test_validation.py`, `test_order_service.py` (portierte Fälle) sowie
  `test_index.py` (Handler-Verhalten).
- `lambda/build_zip.py` (neu): reproduzierbarer Python-ZIP-Build →
  `dist/lambda.zip` (6 Module, ~6,6 KB). Boto3 von der Lambda-Runtime →
  kein `requirements.txt`, kein Boto3-Bundling. Keine Secrets.
- `lambda/README.md` (neu): Build-/Test-Anleitung (Python aktiv + Node-Baseline).
- `terraform/main.tf`: `aws_lambda_function.handler` `runtime = "nodejs22.x"` →
  `"python3.14"` (einzige Terraform-Änderung; Handler `index.handler`, Env, Role,
  DynamoDB unverändert).
- `.gitignore`: `__pycache__/`, `*.pyc` ergänzt.
- `docs/architecture/LAMBDA_RUNTIME_COMPARISON.md` (neu),
  `docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md` (neu).

### Validation
- Python `compileall` (Syntax): PASS.
- Python-Tests (unittest): PASS — 49 Test-Methoden (state_machine 4,
  validation 19, orderService 12, index 14), lokal Python 3.12.3.
- Python-ZIP-Build + `unzip -t` (Integrität) + Handler-Import-Smoke aus
  ZIP-Root-Layout: PASS.
- Node-Baseline unverändert: Vitest 45/45 PASS · `tsc --noEmit` PASS.
- Terraform `fmt`/`init`/`validate`: PASS (AWS-Provider 6.60.0).
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe).
- `git diff --check`: PASS · Secret-Audit: PASS.

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01…04 + Lambda-Python-3.14-Migration
  COMPLETE · T011-05 NEXT · AWS Resources: NONE.

## 2026-08-17 — Checkpoint `449cdd7` (F011 / T011-04 — Lambda Order Handler + Zip-Build)

### Implementierung
- `lambda/` (neu): TypeScript-Handler für die vier Order-Operationen (AP1 Create, AP2 Get by ID,
  AP3 Listing über GSI1-Query, AP4 Status-Update mit Conditional Write) gemäß `api/endpoints.md`
  und `database/access-patterns.md`. Module: `src/index.ts` (Handler, API-GW-v2-Eventformat,
  Fehler→HTTP-Mapping), `src/orderService.ts`, `src/stateMachine.ts`, `src/validation.ts`,
  `src/errors.ts`, `src/types.ts`; Unit-Tests unter `tests/`.
- `lambda/package.json` + `package-lock.json`: `npm run build` (tsc --noEmit + esbuild-Bundle),
  `npm run package` (bestzip → `dist/lambda.zip`), `npm test` (Vitest). Runtime `nodejs22.x`.
- `terraform/main.tf`: `aws_lambda_function.handler` ergänzt (Runtime nodejs22.x,
  Handler `index.handler`, Timeout 10, Env `ORDERS_TABLE`, `source_code_hash` auf
  `../lambda/dist/lambda.zip`); Execution Role `aws_iam_role.handler` aus T011-03 verwendet.
- `terraform/outputs.tf`: `lambda_function_name`, `lambda_function_arn`.
- `terraform/README.md`: Lambda-Abschnitt (§2.3) + Ressourcentabelle aktualisiert.
- Beträge als ganze Cent (Integer) — Vorab-Definition `database/dynamodb-design.md` §7 finalisiert
  (maßgebliches Schema: `api/api-documentation.md` §3; float-Beispiele in `api/endpoints.md`
  bewusst unverändert).
- API-GW→Lambda Invoke-Permission (`aws_lambda_permission`) bewusst NICHT in T011-04 — folgt
  in T011-06 (HTTP API + Routen + Authorizer).

### Validation
- Vitest `npm test`: PASS (45/45 — stateMachine 14, validation 19, orderService 12).
- `npm run build`: PASS · `npm run package`: PASS (dist/lambda.zip, ~156 KB) · `npm audit`: 0.
- `terraform init`: PASS (aws provider v6.60.0) · `terraform validate`: PASS (ohne Warnungen).
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe erforderlich).
- `git diff --check`: PASS · Secret-Audit: PASS.

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01…04 COMPLETE · T011-05 NEXT · AWS Resources: NONE.

## 2026-08-17 — Final Diagnostic: VS Code / terraform-ls stale AWS-Provider-Schema 5.100.0 (F011)

### Verifikation (kein Code-Change)
- terraform-ls 0.39.0 direkt per LSP (serve, Root = Repo) getrieben:
  Root-Modul `terraform/` erkannt; Provider-Erkennung sieht nur noch 6.60.0.
- `ObtainSchema`/`SchemaModuleValidation`/`ReferenceValidation` → alle err = nil,
  **keine Diagnostics** → main.tf ist im aktuellen Zustand fehlerfrei.
- `textDocument/completion` im GSI-Block schlägt `key_schema` vor → modernes
  AWS-Provider-Schema (≥ 6.29.0) aktiv; legacy `hash_key`/`range_key` nur noch deprecated.
- Root Cause belegt: GSI-`key_schema` existiert erst ab AWS-Provider v6.29.0 (PR #46602);
  5.100.0 (Altstand T011-01) erzeugt exakt die gemeldeten Fehler
  (`hash_key` required + `key_schema` not expected). terraform-ls hält das Schema
  in-memory pro Session (kein Disk-Cache) und übernimmt Lockfile-Änderungen erst
  nach Neustart des Language Servers (Initialize-Log: "dynamic watched files … may
  not be reflected at runtime").
- Optionale Altlast: `/tmp/terraform-provider1730277575` = Distributions-Zip aws 5.100.0
  (149 MB) — löschbar. `.terraform/providers` enthält nur noch 6.60.0.

### Abschluss
- `terraform validate`: PASS · `git diff --check`: PASS · Secret-Audit: PASS.
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe erforderlich).
- VS Code: "Developer: Reload Window" bzw. "Terraform: Restart Language Server".

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01…03 COMPLETE · T011-04 NEXT · AWS Resources: NONE.

## 2026-08-17 — Provider 6.x Compatibility & Toolchain Verification (F011, Diagnose)

### Verifikation
- `terraform version`: Terraform v1.15.8 + AWS Provider 6.60.0; Lockfile `6.60.0`, `~> 6.0`.
- `terraform providers schema -json` (autoritativ): `aws_dynamodb_table` top-level
  `hash_key`/`range_key` optional & **nicht** deprecated; GSI1 `key_schema`-Blocks unterstützt,
  GSI-`hash_key`/`range_key` deprecated. IAM-/Provider-Argumente kompatibel.
- Gesamter Terraform-Bestand ist AWS-Provider-6.60.0-kompatibel — **keine Code-Änderung nötig**.
- VS-Code-Diagnostics (5.100.0-Schema: GSI `hash_key` required, kein `key_schema`) erklären sich
  durch veraltetes Editor-/Language-Server-Schema; CLI und Editor werden getrennt bewertet.

### Änderung
- Nur lokaler Cache: veraltetes Plugin `terraform/.terraform/providers/.../aws/5.100.0` entfernt
  (gitignoriert, keine Projektdatei); `terraform init` PASS → nur `6.60.0` installiert.
- `terraform validate`: PASS · `git diff --check`: PASS · Secret-Audit: PASS.
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe erforderlich).

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01…03 COMPLETE · T011-04 NEXT · AWS Resources: NONE.

## 2026-08-17 — Korrektur-Check aws_dynamodb_table.orders (F011, kein Code-Change)

### Verifikation
- Gemeldeter Fehler `Required attribute "hash_key" not specified` wurde geprüft.
- Aktueller Stand: Tabelle enthält `hash_key = "pk"` und `range_key = "sk"`; GSI1 nutzt
  `key_schema`-Blocks (Provider ≥ 6.29.0), nicht die deprecated `hash_key`/`range_key`-Syntax.
- `terraform validate`: PASS (AWS-Provider 6.60.0) · `git diff --check`: PASS · Secret-Audit: PASS.
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe erforderlich).
- **Keine Code-Änderung erforderlich**; Arbeitsbaum == Commit `48a236c`.

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-03 COMPLETE · AWS Resources: NONE.

## 2026-08-17 — Checkpoint 21ed0f4 (F011 / T011-03 — IAM Lambda Execution Role)

### Implementierung
- `terraform/main.tf`: `data.aws_iam_policy_document.handler_trust` (Trust: `lambda.amazonaws.com`),
  `data.aws_iam_policy_document.handler` (Least Privilege: `dynamodb:PutItem/GetItem/
  UpdateItem/Query` auf Tabellen-ARN + `/index/gsi1`; `logs:CreateLogGroup/CreateLogStream/
  PutLogEvents` auf `*`), `aws_iam_role.handler` (`${var.project_name}-handler-role`),
  `aws_iam_role_policy.handler`. Fachquelle: `security/iam-design.md` §2.1.
- `terraform/outputs.tf`: `iam_handler_role_name`, `iam_handler_role_arn`.
- `terraform/README.md`: IAM-Design (T011-03) inkl. Least-Privilege-Permissions-Tabelle.
- `docs/features/F011-terraform-infrastructure.md`: IAM-Lernbezug (Role, Policy, Trust Policy, Least Privilege).

### Validation
- `terraform validate`: PASS (ohne Warnungen, AWS-Provider 6.60.0).
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe erforderlich).
- `git diff --check`: PASS · Secret-Audit: PASS.

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-03 COMPLETE · AWS Resources: NONE.
- Keine AWS-Aktionen; keine Kosten.

## 2026-08-17 — AWS-Provider-Upgrade `~> 5.0` → `~> 6.0` (F011)

### Implementierung
- `terraform/main.tf`: `required_providers.aws` von `~> 5.0` auf `~> 6.0` angehoben.
- `terraform/main.tf`: GSI1 von deprecated `hash_key`/`range_key` auf `key_schema`-Blocks
  (HASH `gsi1pk`, RANGE `gsi1sk`) umgestellt — Provider ≥ 6.29.0.
- `terraform/.terraform.lock.hcl`: aws provider `5.100.0` → `6.60.0` (`init -upgrade`).
- `terraform/README.md`: Provider- und GSI-Syntax-Hinweis aktualisiert.

### Validation
- `terraform init -upgrade`: PASS (aws provider v6.60.0) · `terraform validate`: PASS (ohne Warnungen).
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe erforderlich).
- `git diff --check`: PASS · Secret-Audit: PASS.

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-02 COMPLETE · AWS Resources: NONE.
- Keine AWS-Aktionen; keine Kosten.

## 2026-08-17 — Checkpoint 5d291bd (F011 / T011-02 — DynamoDB-Tabelle + GSI1)

### Implementierung
- `terraform/main.tf`: `aws_dynamodb_table.orders` ergänzt — Tabellen-Name `var.project_name`
  (`mays-orders`), On-Demand (`PAY_PER_REQUEST`, ADR-007), Primary Key `pk`/`sk` (S),
  GSI1 `gsi1pk`/`gsi1sk` (S) mit `INCLUDE`-Projection (`orderId, status, customer,
  totalAmount, createdAt, updatedAt`). Fachquelle: `database/dynamodb-design.md`, ADR-002.
- `terraform/outputs.tf`: `dynamodb_table_name`, `dynamodb_table_arn` (Outputs ab T011-02).
- `terraform/README.md`: DynamoDB-Design (T011-02) inkl. Access-Pattern-Abbildung dokumentiert.
- `docs/features/F011-terraform-infrastructure.md`: GSI1-Begründung (AP3 → Query statt Scan).

### Validation
- `terraform init`: PASS (aws provider v5.100.0) · `terraform validate`: PASS.
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe erforderlich).
- `git diff --check`: PASS · Secret-Audit: PASS.

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-02 COMPLETE · AWS Resources: NONE.
- Keine AWS-Aktionen; keine Kosten.

## 2026-08-17 — Checkpoint 67f02a3 (F011 / T011-01 — Terraform-Gerüst)

### Implementierung
- `terraform/main.tf`: `terraform`-Block (`required_version`, AWS-Provider `~> 5.0`),
  `provider "aws"` mit Region (Variable) und Default-Tags.
- `terraform/variables.tf`: `project_name`, `aws_region`, `tags`.
- `terraform/outputs.tf`: leer — Outputs werden je Ressource ab T011-02 ergänzt.
- `terraform/README.md`: Struktur auf aktuellen T011-01-Stand aktualisiert.
- `.terraform.lock.hcl` committet (Reproduzierbarkeit).

### Validation
- `terraform init`: PASS (aws provider v5.100.0) · `terraform validate`: PASS.
- `terraform plan`: NOT RUN (zu T011-07) · `terraform apply`: NOT RUN (Freigabe erforderlich).
- `git diff --check`: PASS · Secret-Audit: PASS.

### Status
- Week 2 IN PROGRESS · F011 IN PROGRESS · T011-01 COMPLETE · AWS Resources: NONE.
- Keine AWS-Aktionen; keine Kosten.

## 2026-08-17 — Checkpoint 4515029 (Woche 1)

### Foundation
- Git-Repo initialisiert, GitHub-Remote `maynowak/mays-order-aws` eingerichtet.
- Remote-„Initial commit" (LICENSE, README, .gitignore) per `--allow-unrelated-histories` zusammengeführt; Konflikte gelöst.

### Dokumentation (Woche 1)
- `requirements/`: Business-, Technical-Requirements, Assumptions & Constraints.
- `order-lifecycle/`: State Machine, Transition Matrix (18 Fälle), Konkurrenz-Schutz-Konzept.
- `api/`: Endpoint-Design, API-Dokumentation, Testfälle (T-01…16, A-01…04).
- `database/`: Single-Table-Design (GSI1), Access-Pattern-Analyse.
- `security/`: Auth-Entscheidung (Cognito, HTTP API, JWT-Flow), IAM-Least-Privilege-Design.
- `architecture/`: ADR-001…007, Request-Flow, Architekturdiagramm (SVG).
- `monitoring/`, `reliability/`, `cost/`: Monitoring-, Konsistenz-, Kosten-Konzept.
- `docs/reports/`: Vier-Wochen-Plan, Test-/Kosten-/Recovery-Strategie, Weekly-Report, Feature-Report.

### Status
- Woche 1 — COMPLETE. Keine AWS-Ressourcen. Keine Implementierung.
- Build: NOT APPLICABLE · Live-API: NOT RUN (kein Code) · Secret-Audit: PASS · `git diff --check`: PASS.

## 2026-08-17 — Dokumentations-Transfer (Checkpoint 2a89e73)

### Dokumentation
- Zentrales Statusdokument `docs/PROJECT_STATUS.md`.
- Portfolio `docs/PROJECT_PORTFOLIO.md`, Changelog `docs/CHANGELOG.md`.
- AI-/Projektkontext-Dokumente nach Mays-Jobsearch-Muster (`docs/AGENTS.md`, `docs/AI_CONTEXT.md`, …).
- Feature-Dokumentation `docs/features/` (F001–F011).
- Weekly-Reports strukturiert als `docs/reports/WEEK-01…04.md`.
- `docs/BUILD.md`, `docs/DEPLOYMENT.md` (Planung, Status offen).

### Status
- Woche 1 weiterhin COMPLETE; kein Code, keine AWS-Ressourcen.
- Checkpoint `2a89e73` gepusht.
- Statusnachzug Checkpoint `729ae73` gepusht (Checkpoint-Historie aktualisiert).

## 2026-08-17 — Korrektur Review-Inkonsistenzen (Checkpoint 4a0a6e7)

### Dokumentation
- `docs/PROJECT_STATUS.md`: `729ae73` als aktueller letzter Checkpoint (Historie: `4515029 → 2a89e73 → 729ae73`).
- `README.md` + `docs/reports/four-week-plan.md`: Woche-1-Status eindeutig **COMPLETE** (kein „in Arbeit").
- Commit-/Push-Regel vereinheitlicht (normale Tasks: Checkpoint-Commit/-Push selbstständig;
  kosten-/sicherheitsrelevante AWS-Aktionen weiterhin nur mit menschlicher Freigabe):
  `docs/AGENTS.md`, `docs/AI_TEAM.md`, `docs/AI_AGENT_PLAYBOOK.md`, `docs/AI_DEVELOPMENT_GUIDE.md`.
- Konsistenz-Nachzug in `docs/features/F001-project-foundation.md`, `docs/reports/documentation-transfer-report.md`.

### Status
- Week 1 COMPLETE · Documentation COMPLETE · AWS NO RESOURCES · Application NOT STARTED ·
  Terraform Apply NOT RUN · Live API NOT RUN.

## 2026-08-17 — Persistent Feature Progress & Crash-Recovery-Regel

### Workflow
- Verbindliche Regel eingeführt: Arbeitsstand wird während der Bearbeitung **fortlaufend**
  in der Feature-Dokumentation aktualisiert (`docs/features/_progress-template.md`).
- Feature-Doku (FXXX) führt künftig: Status, Current Task, Completed/In Progress/Pending Tasks,
  Changes Made, Tests, Validation, Known Issues, Blockers, Current Checkpoint, Next Step.
- Status-Disziplin: aktive Features `IN PROGRESS`; Feature erst `COMPLETE` nach Implementation,
  Tests, Validation, Doku, bekannte Probleme, Git-Checkpoint und Push.
- Recovery-Regel erweitert: semantischer Stand aus Feature-Doku ist die maßgebliche
  Recovery-Quelle; bei Unsicherheit `UNKNOWN / NEEDS VERIFICATION`, nicht raten.

### Geänderte Dateien
- `docs/AI_AGENT_PLAYBOOK.md` (neue Sektion), `docs/AGENTS.md`, `docs/AI_DEVELOPMENT_GUIDE.md`
- `docs/features/README.md`, `docs/features/_progress-template.md` (neu)
- `docs/reports/recovery-checkpoint-strategy.md`, `docs/PROJECT_STATUS.md`

### Status
- Keine AWS-Aktionen; Freigabepflichtige Aktionen unverändert (apply/destroy, Produktions-
  deployment, destruktive Operationen, kostenrelevante Ressourcen, Architekturänderungen).
- Checkpoint `7f37340` gepusht; `docs/PROJECT_STATUS.md` auf aktuellen HEAD nachgezogen.