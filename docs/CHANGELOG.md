# Changelog — May's Orders

> Nur tatsächliche Änderungen. Jeder Eintrag referenziert einen echten Checkpoint.

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