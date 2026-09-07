# Terraform — May's Orders

> Stand T011-12: **Modularisierte Terraform-Infrastruktur** — DynamoDB, IAM, Lambda, Cognito, API Gateway HTTP API, CloudWatch Monitoring in 6 Child Modules. AWS-Provider `~> 6.0`. Noch kein `apply` ausgeführt.
>
> Stand T011 (CloudTrail): **7. Child-Modul `cloudtrail`** hinzugefügt — Account-weiter AWS-API-Audit-Trail (Trail + zweckgebundener S3-Bucket, SSE-S3, Public-Access-Block, Bucket-Policy). Kein `apply`.
>
> Stand T013 (Installation Identity): erste sichere Installations-Schicht — **Projekt-Identität**. `project_name` bleibt der zentrale Namens-/Identitäts-Hebel; `Maker`-Provenance als unveränderlicher Tag hinzugefügt (siehe §9). Kein `apply`.
>
> Stand T014 (Installation Cost Profile): **Cost-Profile-Entscheidung** definiert — Default-Profil `LOWEST / PROTOTYPE`, entspricht exakt der aktuellen Konfiguration; als Design dokumentiert, **keine** neue Terraform-Variable (kein Consumer, §9.5). Kein `apply`.
>
> Stand T015 (Installation Region): **Region-Entscheidung** definiert — Default `eu-central-1` (Europe (Frankfurt)), bereits sauber variable-getrieben via `var.aws_region`; **keine** neue Variable (§9.6). Kein `apply`.
>
> Stand T016 (Installation Availability): **Availability-Entscheidung** definiert — Profil `LOW / PROTOTYPE` (Single Region, managed Serverless, kein VPC/Failover); **keine** Terraform-Änderung (§9.7). Kein `apply`.
>
> Stand T017 (Installation Data Strategy): **Data-Strategy-Entscheidung** definiert — Single-Region DynamoDB, keine Replikation, PITR/KMS/Streams deferred; **keine** Terraform-Änderung (§9.8). Kein `apply`.
>
> Stand T018 (Installation Security Profile): **Security-Profile-Entscheidung** definiert — Profil `LOW / PROTOTYPE` (IAM Least Privilege, Cognito+JWT, managed Verschlüsselung, CloudTrail); Gruppen-Authorization/KMS deferred; **keine** Terraform-Änderung (§9.9). Kein `apply`.

## 1. Ziel

Die AWS-Infrastruktur wird vollständig als Infrastructure as Code abgebildet:

- API Gateway (HTTP API)
- Lambda (Order Handler)
- DynamoDB (`mays-orders`)
- IAM (Lambda Execution Role, Resource-Based Policy)
- Cognito User Pool + Client + Gruppe `staff`
- CloudWatch Monitoring (Dashboard, Alarme, Log-Retention)

Keine manuell erzeugte Infrastruktur als finales Ergebnis.

## 2. Struktur

**Aktueller Stand (T011-12, Clean Target Architecture):**

```text
terraform/
├── main.tf         Root Orchestrator: Provider, 6 Module Calls, Seed Resource
├── variables.tf    Root Variables (Region, Project Name, Tags, Seed, Monitoring, Alarm Thresholds)
├── outputs.tf      Root Outputs (re-exported from modules)
├── monitoring.tf   Placeholder — resources moved to module.monitoring
└── modules/
    ├── dynamodb/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── iam/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── lambda/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── cognito/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── api/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── monitoring/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── cloudtrail/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

**Quellcode der Lambda:** `lambda/` (Python 3.14, aktiv; Node.js/TypeScript-
Baseline T011-04 entfernt, historisch via Git `449cdd7`) — siehe §2.3.

**Modulzuordnung (T011-12):**

| Modul | Ressourcen |
|-------|------------|
| `module.dynamodb` | DynamoDB Tabelle + GSI1 |
| `module.iam` | IAM Role + Policy (Least Privilege) |
| `module.lambda` | Lambda Function + CloudWatch Log Group |
| `module.cognito` | User Pool + App Client + Group `staff` |
| `module.api` | HTTP API Gateway + Stage + JWT Authorizer + Integration + 4 Routes + Lambda Permission |
| `module.monitoring` | CloudWatch Dashboard + 6 Alarme (T011-11) |
| `module.cloudtrail` | CloudTrail Trail + S3-Log-Bucket + Policy (T011) |

Alle AWS-Ressourcen sind in den Child Modules kapselt. Das Root-Modul fungiert als Orchestrator.

---

## STATE MIGRATION

**WICHTIG**: Die 26 `moved` Blöcke, die während der Refactoring-Phase (T011-12) implementiert wurden, sind **Migrations-Mechanismen für bestehende Terraform-States**, nicht Teil der Zielarchitektur.

**Für eine saubere Erst-Deployment (Clean Initial Deployment):**
- Keine `moved` Blöcke erforderlich
- Ressourcen werden direkt an ihren finalen Modul-Adressen erstellt
- `terraform plan` zeigt 24 Ressourcen als `create` an ihren finalen Modul-Adressen

**Für Migration eines bestehenden flat Terraform States:**
- Die 26 `moved` Blöcke würden benötigt, um bestehende Ressourcen-Adressen zu migrieren
- Ohne `moved` Blöcke würde Terraform `destroy` + `create` planen
- Die Migration ist als separates Verfahren dokumentiert (siehe `docs/reports/T011-12-TERRAFORM-MODULES-EXECUTION-LOG.md`)

**WICHTIG:**
- **Kein `terraform apply` wurde ausgeführt**
- **Keine AWS-Ressourcen existieren unter Terraform-State**
- **Keine State-Migration wurde live ausgeführt**
- Die `moved` Blöcke sind Refactoring-Artefakte, wurden für den Clean Target Architecture entfernt

## 2.1 DynamoDB-Tabelle (T011-02)

Fachliche Grundlage: `database/dynamodb-design.md` (Item-Modell, Index-Struktur),
`database/access-patterns.md` (AP2/AP3), ADR-002, ADR-007.

| Eigenschaft | Wert | Quelle |
|-------------|------|--------|
| Tabellen-Name | `var.project_name` (= `mays-orders`) | Single-Table-Design |
| Capacity | On-Demand (`PAY_PER_REQUEST`) | ADR-007 |
| Primary Key | `pk` (S) = `ORDER#<orderId>`, `sk` (S) = `#ORDER` | `database/dynamodb-design.md` §2 |
| GSI1 | `gsi1pk` (S) = `LIST`, `gsi1sk` (S) = `createdAt` | ADR-002, `database/access-patterns.md` §2.3 |
| GSI1-Projection | `INCLUDE`: `orderId, status, customer, totalAmount, createdAt, updatedAt` | `database/dynamodb-design.md` §3 |
| GSI1-Key-Syntax | `key_schema`-Blocks (HASH/RANGE), Provider `~> 6.0` | AWS-Provider ≥ 6.29.0 |

Access-Pattern-Abbildung:

```text
AP2 (GET /orders/{orderId})  → GetItem(pk=ORDER#<id>, sk=#ORDER)   → Primary Key
AP3 (GET /orders)            → Query(gsi1, gsi1pk=LIST, absteigend) → GSI1
```

Kein Scan für irgendein Pattern (ADR-002).

### Demo-Daten-Seed (T011-10, opt-in)

Die 50 Demo-Orders (`database/seed/orders_seed_demo_50.json`) werden **nur** mit
bewusster Aktivierung importiert (`seed_example_data`, **Default `false`**):

```bash
terraform plan                       # 16 to add — kein Beispiel-Import
terraform apply -var="seed_example_data=true"   # nach Freigabe → Infrastruktur + 50 Demo-Orders
```

`terraform_data.seed_orders` (count = `seed_example_data`) triggert über den
SHA256 der Seed-Datei + Tabellenname; der Importer ist zusätzlich idempotent.
Details: `docs/reports/DYNAMODB-SEED-DEMO-50.md`.

## 2.2 IAM — Lambda Execution Role (T011-03)

Fachliche Grundlage: `security/iam-design.md` §2.1. Least Privilege verpflichtend.

| Komponente | Wert | Quelle |
|------------|------|--------|
| Role | `aws_iam_role.handler`, Name `${var.project_name}-handler-role` | `security/iam-design.md` §2.1 |
| Trust Policy | `lambda.amazonaws.com` (`sts:AssumeRole`) | `security/iam-design.md` §2.1 |
| Inline Policy | `aws_iam_role_policy.handler` | `terraform/README.md` Ressourcentabelle |

Permissions (nur, was die Lambda für die Access Patterns braucht):

```text
Permission                     Purpose                 Resource
─────────────                   ───────                 ────────
dynamodb:PutItem      → AP1 Create (POST /orders)      Tabelle (ARN)
dynamodb:GetItem      → AP2 Get by ID (GET /orders/{id}) Tabelle (ARN)
dynamodb:UpdateItem   → AP4 Status-Update (Conditional) Tabelle (ARN)
dynamodb:Query        → AP3 Listing (GET /orders, GSI1) Tabelle + /index/gsi1
logs:CreateLogGroup   → Lambda-Logging                  "*" (Logs entstehen zur Laufzeit)
logs:CreateLogStream  → Lambda-Logging                  "*"
logs:PutLogEvents     → Lambda-Logging                  "*"
```

Bewusst **nicht** erlaubt: `dynamodb:Scan`, `dynamodb:DeleteItem`, `dynamodb:BatchWriteItem`,
`dynamodb:CreateTable`, `s3:*`, `sqs:*`, `iam:*` (`security/iam-design.md` §2.1).

Kein IAM-User, keine Access Keys — Benutzer-Auth läuft über Cognito (ADR-003).

## 2.3 Lambda — Order Handler (T011-04)

Fachliche Grundlage: `api/endpoints.md`, `api/api-documentation.md`,
`database/access-patterns.md` (AP1…AP4), ADR-001.

| Eigenschaft | Wert |
|-------------|------|
| Funktion | `aws_lambda_function.handler`, Name `${var.project_name}-handler` |
| Runtime / Handler | `python3.14` · `index.handler` (Migration von `nodejs22.x` → `python3.14`) |
| Execution Role | `aws_iam_role.handler` aus T011-03 (Least Privilege) |
| Deployment Package | `lambda/dist/lambda.zip` (reproduzierbar: `cd lambda && python3 build_zip.py`; boto3 von der Runtime, kein requirements.txt) |
| Env-Variable | `ORDERS_TABLE` = DynamoDB-Tabellenname (`aws_dynamodb_table.orders.name`) |
| Timeout | 10 s (Cold-Start + DynamoDB-Latenz; Default 3 s zu knapp) |
| API-GW Invoke-Permission | **offen → T011-06** (`aws_lambda_permission`, wenn HTTP API existiert) |

Umgesetzte Order-Operationen (Lambda-Business-Logik, `lambda/src/order_service.py`):

| Access Pattern | Endpoint | DynamoDB-Zugriff |
|----------------|----------|------------------|
| AP1 Create | `POST /orders` | `PutItem` (PENDING, `totalAmount` server-seitig, GSI1-Eintrag) |
| AP2 Get by ID | `GET /orders/{orderId}` | `GetItem` |
| AP3 Listing | `GET /orders` | `Query` auf GSI1 (absteigend, paginiert) |
| AP4 Status-Update | `PATCH /orders/{orderId}/status` | `UpdateItem` + Conditional Write (Race-Schutz) |

Beträge werden als **ganze Cent** (Integer) verarbeitet (Vorab-Definition
`database/dynamodb-design.md` §7; finale Darstellung gemäß `api/api-documentation.md` §3).

## 2.4 Cognito — User Pool + Client + Gruppe (T011-05)

Fachliche Grundlage: `security/authentication-decision.md` (ADR-003, JWT-Flow §3),
`security/iam-design.md` (Auth ≠ IAM), F002 (T002-01…03).

| Ressource | Terraform-Typ | Name | Konfiguration |
|-----------|---------------|------|---------------|
| User Pool | `aws_cognito_user_pool.users` | `${var.project_name}-users` | Admin-Create-User (keine offene Selbst-Registrierung), Passwortrichtlinie Standardwerte (min. 8, Upper/Lower/Number/Symbol), MFA `OFF` |
| App Client | `aws_cognito_user_pool_client.app` | `${var.project_name}-client` | `explicit_auth_flows`: `ALLOW_USER_PASSWORD_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH`; `generate_secret = false` (Public Client, Voraussetzung für USER_PASSWORD_AUTH) |
| Gruppe | `aws_cognito_user_group.staff` | `staff` | Claim `cognito:groups` → Basis der Authorization (A-09) |

> Hinweis: Provider 6.60.0 nutzt den Ressourcen-Typ `aws_cognito_user_group`
> (nicht `aws_cognito_user_pool_group`).

**Bewusst NICHT in T011-05:**
- Kein `aws_cognito_user_pool_domain` — Login via `USER_PASSWORD_AUTH` benötigt kein
  Hosted-UI/OAuth-Redirect (Domain nur "falls nötig").
- Keine API-GW-Anbindung / kein JWT-Authorizer / keine Lambda-Invoke-Permission — folgen in T011-06.
- Keine offene Registrierung, keine IAM Access Keys für Benutzer (TR-15).

JWT-Flow (aus `security/authentication-decision.md` §3):

```text
Benutzer → login (USER_PASSWORD_AUTH) → Cognito User Pool
Benutzer ← Access Token (JWT, ~1 h)  ← Cognito
Benutzer → API-Request "Authorization: Bearer <JWT>" (ab T011-06)
```

## 2.5 API Gateway HTTP API (T011-06)

Fachliche Grundlage: `architecture/architecture-decisions.md` (ADR-004: HTTP API V2),
`api/endpoints.md`, `api/api-documentation.md` (Auth: `Authorization: Bearer <JWT>`),
`security/iam-design.md` §3 (API-GW→Lambda Invoke-Permission).

| Ressource | Terraform-Typ | Name | Konfiguration |
|-----------|---------------|------|---------------|
| HTTP API | `aws_apigatewayv2_api.orders` | `${var.project_name}-api` | `protocol_type = "HTTP"` |
| Stage | `aws_apigatewayv2_stage.default` | `$default` | `auto_deploy = true` |
| JWT-Authorizer | `aws_apigatewayv2_authorizer.jwt` | `${var.project_name}-jwt-authorizer` | `authorizer_type = "JWT"`, `identity_sources = ["$request.header.Authorization"]`, Issuer = `https://<cognito-endpoint>` (aus User Pool), Audience = App Client ID |
| Integration | `aws_apigatewayv2_integration.lambda` | – | `AWS_PROXY` + `payload_format_version = "2.0"` auf `aws_lambda_function.handler.invoke_arn` |
| Routen | `aws_apigatewayv2_route.*` | – | 4 Routen, alle `authorization_type = "JWT"` + `authorizer_id` |
| Invoke-Permission | `aws_lambda_permission.api_gateway` | – | `apigateway.amazonaws.com`, `source_arn = ${execution_arn}/*/*` |

Vier dokumentierte Routen (`api/endpoints.md`):

| Method | Path | Lambda Operation | Auth |
|--------|------|------------------|------|
| POST | `/orders` | AP1 Create | JWT (Cognito) |
| GET | `/orders/{orderId}` | AP2 Get by ID | JWT (Cognito) |
| GET | `/orders` | AP3 Listing | JWT (Cognito) |
| PATCH | `/orders/{orderId}/status` | AP4 Status-Update | JWT (Cognito) |

Bewusste Entscheidungen T011-06:
- **Payload Format 2.0** — exakt der Event-Contract des Python-Handlers
  (`lambda/src/index.py` routet über `routeKey`; v2-Proxy-Response). Keine Änderung an
  `index.py` nötig (verifiziert).
- **Kein REST API** (`aws_api_gateway_*`) — ADR-004 sieht HTTP API (V2) vor.
- **Authorization-Logik über `cognito:groups`** wird in T011-06 noch nicht im Lambda
  ausgewertet (A-09); der JWT-Authorizer stellt sicher, dass nur Tokens des User Pools
  (Issuer) mit korrekter Audience (App Client) passieren. Gruppenscoping bleibt für
  die Security-Features (Woche 3) offen.
- Keine zusätzlichen/öffentlichen Routen.

## 2.6 CloudWatch Monitoring (T011-11)

Fachliche Grundlage: `monitoring/monitoring-design.md` (Source of Truth),
`cost/cost-analysis.md` §2 (kostenbewusst), F010.

| Ressource | Terraform-Typ | Name | Konfiguration |
|-----------|---------------|------|---------------|
| Dashboard | `aws_cloudwatch_dashboard` | `${var.project_name}-overview` | „May's Orders — Order Management Overview"; Bereiche SYSTEM HEALTH, ORDER OPERATIONS, ERROR ANALYSIS; Widgets mit echten AWS-Metriken |
| Alarme ×6 | `aws_cloudwatch_metric_alarm` | `${var.project_name}-api-5xx/-api-4xx/-lambda-errors/-lambda-duration/-lambda-throttles/-dynamodb-throttled` | AWS/ApiGateway, AWS/Lambda, AWS/DynamoDB; Schwellwerte als Variablen; `treat_missing_data = "notBreaching"`; kein SNS |
| Log-Group | `aws_cloudwatch_log_group` | `/aws/lambda/${var.project_name}-handler` | `retention_in_days = var.log_retention_days` (Default 7) |

- **Nur echte AWS-Namespaces:** `AWS/ApiGateway` (Count, 4XXError, 5XXError),
  `AWS/Lambda` (Invocations, Errors, Duration, Throttles, ConcurrentExecutions),
  `AWS/DynamoDB` (ThrottledRequests, ConditionalCheckFailedRequests).
- **Business-Metriken** (Orders Created / by Status / Success Rate) sind **GAP /
  PLANNED** (keine Custom Metrics, keine erfundenen Metric Names) —
  `monitoring/monitoring-design.md` §9.
- **Variablen:** `monitoring_enabled` (Default `true`; `false` → keine Monitoring-
  Ressourcen), `dashboard_enabled`, `log_retention_days`, `alarm_period_seconds`,
  `alarm_evaluation_periods`, 6 Alarm-Schwellwerte („Initial threshold / starting
  value — requires calibration with real AWS metrics.").
- Plan-Effekt: default **24 to add** (16 bestehende + 8 Monitoring: 1 Dashboard,
  6 Alarme, 1 Log-Group). Kein `apply` in T011-11.

## 2.7 CloudTrail Audit Layer (T011)

Fachliche Grundlage: `security/cloudtrail-design.md` (Source of Truth). CloudTrail ist
**Account-Level Audit**, KEINE Anwendungs-Business-Logik → bewusst ein eigenes kleines
Child-Modul (analog `module.monitoring`, kein Consumer-Modul, keine neuen Root-Inputs/-Outputs).

| Ressource | Terraform-Typ | Name | Konfiguration |
|-----------|---------------|------|---------------|
| Trail | `aws_cloudtrail.trail` | `${var.project_name}-trail` | `is_multi_region_trail = true`, `include_global_service_events = true`, Management Events Read+Write (`All`), `enable_log_file_validation = true`, `enable_logging = true` |
| Log-Bucket | `aws_s3_bucket.trail` | `${var.project_name}-cloudtrail-<account-id>` | Zweckgebunden; Account-ID via `data.aws_caller_identity` (global eindeutig) |
| Bucket-Eigentum | `aws_s3_bucket_ownership_controls.trail` | – | `BucketOwnerEnforced` (ACLs deaktiviert) |
| Public-Access-Block | `aws_s3_bucket_public_access_block.trail` | – | alle vier Flags `true` |
| Verschlüsselung at rest | `aws_s3_bucket_server_side_encryption_configuration.trail` | – | SSE-S3 (`AES256`), explizit |
| Bucket-Policy | `aws_s3_bucket_policy.trail` | – | nur `cloudtrail.amazonaws.com` `PutObject` auf `AWSLogs/<account>/CloudTrail/*` (SourceArn-Condition) |

**CloudWatch vs. CloudTrail:** CloudWatch (`module.monitoring`) = operational/application
monitoring (Logs, Metriken, Alarme, Dashboard); CloudTrail (`module.cloudtrail`) =
AWS-API-Activity / Audit-Trail (WHO/WHAT/WHEN/WHERE). Strikte Trennung.

**Bewusst NICHT (Prototyp-Scope):** Data Events, KMS (SSE-S3 statt SSE-KMS),
S3-Lifecycle/Retention, SNS-Alarme — siehe `security/cloudtrail-design.md` §7.

- Plan-Effekt (T011): **30 to add** (24 bestehende + 6 CloudTrail: Trail, Bucket,
  Ownership-Controls, Public-Access-Block, SSE-Config, Bucket-Policy). Kein `apply`.

## 3. Implementierte Ressourcen (T011-12 Modularisiert)

| Ressource | Terraform-Typ | Modul |
|-----------|---------------|-------|
| DynamoDB-Tabelle | `aws_dynamodb_table` (On-Demand, GSI1) | `module.dynamodb` |
| IAM Role | `aws_iam_role` | `module.iam` |
| IAM Policy | `aws_iam_role_policy` | `module.iam` |
| IAM Policy Documents (data) | `data.aws_iam_policy_document` | `module.iam` |
| Lambda Function | `aws_lambda_function` | `module.lambda` |
| Lambda Log Group | `aws_cloudwatch_log_group` | `module.lambda` |
| Lambda Permission | `aws_lambda_permission` | `module.api` |
| HTTP API | `aws_apigatewayv2_api` | `module.api` |
| API Stage | `aws_apigatewayv2_stage` | `module.api` |
| JWT Authorizer | `aws_apigatewayv2_authorizer` | `module.api` |
| Lambda Integration | `aws_apigatewayv2_integration` | `module.api` |
| API Routes (4) | `aws_apigatewayv2_route` | `module.api` |
| Cognito User Pool | `aws_cognito_user_pool` | `module.cognito` |
| Cognito User Pool Client | `aws_cognito_user_pool_client` | `module.cognito` |
| Cognito User Group | `aws_cognito_user_group` | `module.cognito` |
| CloudWatch Dashboard | `aws_cloudwatch_dashboard` | `module.monitoring` |
| CloudWatch Alarms (6) | `aws_cloudwatch_metric_alarm` | `module.monitoring` |
| CloudTrail Trail | `aws_cloudtrail` | `module.cloudtrail` |
| CloudTrail S3 Bucket | `aws_s3_bucket` | `module.cloudtrail` |
| CloudTrail S3 Bucket Policy | `aws_s3_bucket_policy` | `module.cloudtrail` |
| CloudTrail S3 Access/SSE-Config | `aws_s3_bucket_ownership_controls` / `aws_s3_bucket_public_access_block` / `aws_s3_bucket_server_side_encryption_configuration` | `module.cloudtrail` |

## 4. Workflow

```text
terraform init
terraform validate
terraform plan      → Review (kein blindes Apply)
terraform apply     → nur nach Freigabe
```

## 5. State & Backend

- Anfangs lokaler State (`.tfstate` — in `.gitignore`).
- **Offen:** S3-Backend mit DynamoDB-Lock ab Woche 2 (Empfehlung für Team-Zusammenarbeit;
  Kosten minimal). Entscheidung wird mit Doku-Update getroffen.

## 6. Sicherheit

- Keine Secrets in `.tfvars` committen (`.gitignore`; Beispiel-Datei `terraform.example.tfvars`).
- Keine harten ARNs/Account-IDs im Code (Variablen verwenden).
- Least-Privilege-Policies (siehe `security/iam-design.md`).

## 7. Abhängigkeiten

- Lambda-Zip muss vor `plan`/`apply` gebaut sein (`cd lambda && python3 build_zip.py`).
- API-GW-Route → Integration → Lambda-Permission (T011-06) → Lambda-Deployment.

## 8. Root Outputs — Infrastruktur-Interfaces

Das Root-Modul re-exportet die wichtigsten Cross-Module-Interfaces für Operatoren,
CLI/Automation und externe Consumers:

| Output | Quelle | Typ | Zweck |
|--------|--------|-----|-------|
| `dynamodb_table_name` | `module.dynamodb` | Name | Tabellenname für CLI/Seed/Scripts |
| `dynamodb_table_arn` | `module.dynamodb` | ARN | IAM-Policies, Cross-Account-Referenzen |
| `iam_handler_role_name` | `module.iam` | Name | Execution Role Identifikation |
| `iam_handler_role_arn` | `module.iam` | ARN | Lambda `iam_role_arn` Input |
| `lambda_function_name` | `module.lambda` | Name | API Integration, Monitoring, CLI |
| `lambda_function_arn` | `module.lambda` | ARN | Resource-basierte Policies |
| `lambda_invoke_arn` | `module.lambda` | Invoke ARN | Direkte Lambda-Invocation (Testing) |
| `cognito_user_pool_id` | `module.cognito` | ID | User Pool Referenz |
| `cognito_user_pool_arn` | `module.cognito` | ARN | Cross-Account/Resource Policies |
| `cognito_user_pool_endpoint` | `module.cognito` | Endpoint | JWT Issuer URL (Token-Validierung) |
| `cognito_user_pool_client_id` | `module.cognito` | ID | App Client (Auth Flow, API GW Audience) |
| `cognito_user_pool_group_name` | `module.cognito` | Name | `staff` Gruppe (Authorization Claim) |
| `api_gateway_endpoint` | `module.api` | Endpoint | HTTP API Invoke-URL (Client-Zugriff) |
| `api_gateway_id` | `module.api` | ID | Monitoring, CLI, Resource Policies |
| `api_gateway_stage_name` | `module.api` | Name | API Stage (`$default`) für CLI/Monitoring |
| `api_gateway_authorizer_id` | `module.api` | ID | JWT Authorizer Referenz |

**Nicht re-exportet:** Monitoring-Outputs (Dashboard/Alarme — bedingt, Read-Only Consumer),
CloudTrail-Outputs (`trail_*`, `s3_bucket_*` — kein Consumer-Modul, nur Verifikation),
interne IDs (`integration_id`, `policy_name`, `log_group_name`, `gsi1_*`, `table_stream_arn`).

Struktur in `terraform/outputs.tf`:
```text
# DynamoDB Outputs
# IAM Outputs
# Lambda Outputs
# Cognito Outputs
# API Gateway Outputs
# Monitoring Outputs (nicht re-exportet)
# CloudTrail Outputs (nicht re-exportet)
```

## 9. Projekt-Identität (Installation Layer, T013)

> Erste sichere Installations-Schicht aus dem Konzept `architecture/installation-concept.md`.
> Nur die **Projekt-Identität** ist implementiert. Alle übrigen Installations-
> Entscheidungen (Cost Profile, Region, Availability, Data Strategy, Security Profile,
> Optional Features, User Confirmation) bleiben **Future Work**.

### 9.1 Identitäts-Modell

| Feld | Quelle | Verwendung | Verändert Ressourcen-Name? | Mutable? |
|------|--------|------------|---------------------------|----------|
| `Project` | `var.project_name` (Variable, Default `mays-orders`) | Ressourcen-Namen-Prefix (`${var.project_name}-*`, DynamoDB-Tabelle = `project_name`) + `Project`-Tag | **JA** | konfigurierbar **vor** erstem `apply`; nach Apply umbenennen = destroy/create |
| `Maker` | `local.maker` (Konstante `mays-orders` in `main.tf`) | nur `Maker`-Tag via `default_tags` | **NEIN** | **unveränderlich** (Provenance) |
| `ManagedBy` / `CreatedBy` | optional via `var.tags` (Deployment-Metadaten) | nur Tags | **NEIN** | konfigurierbar |

- **Projekt-Identität (configurable)** = `project_name` → bestimmt Ressourcen-Namen & `Project`-Tag.
- **Maker / Provenance (preserved)** = `local.maker` → nur als `Maker`-Tag, bewusst **nie**
  in Ressourcen-Namen, damit eine Kunden-Umbenennung die Original-Provenance nicht verliert.
- `Maker` ist ein **neutraler Projekt-Slug** (`mays-orders`), kein persönlicher Name.
- `ManagedBy`/`CreatedBy` sind als Deployment-Metadaten über das bereits vorhandene
  `var.tags` ausdrückbar (z. B. `-var='tags={"ManagedBy":"Mays Orders"}'`); eigene
  Variablen werden in dieser minimalen Schicht bewusst **nicht** angelegt.

### 9.2 Naming-Safety

- `provider.default_tags` trägt `Project` + `Maker` automatisch auf **alle** tag-fähigen
  Ressourcen; die Modul-eigenen `tags = merge({ "Project" = ... }, var.tags)` bleiben
  unverändert und setzen `Project` gleichlautend (kein Konflikt).
- **Validierung:** `project_name` muss mind. 3 Zeichen lang sein und nur `[a-z0-9-]`
  enthalten (kein führender/trailing Bindestrich) — `terraform/variables.tf`.
  Kleinschreibung + Bindestrich ist über alle verwendeten Ressourcen gültig
  (DynamoDB-Tabelle == `project_name` → min. 3; S3-Bucket ist kleinschreibungs-pflichtig).
- **Empfehlung:** `project_name` kurz halten (≲ 32 Zeichen), da Lambda-/IAM-Namen
  (`${project_name}-handler`, `-handler-role`) 64-Zeichen-Limits und der CloudTrail-Bucket
  (`${project_name}-cloudtrail-<account-id>`) das 63-Zeichen-Limit haben.

### 9.3 Vor / Nach Apply Warnung

| Zeitpunkt | Verhalten |
|-----------|-----------|
| **VOR erstem Apply** | `project_name` kann sicher gewählt werden (alle Namen leiten sich konsistent ab). |
| **NACH Apply** | Ändern von `project_name` **erzeugt neue Ressourcen** (destroy/create), da der Name in Ressourcen-Identifern steckt (DynamoDB-Tabellenname, Lambda-/IAM-/Cognito-/API-/Trail-Namen, S3-Bucket). State-/Migrations-Implikationen beachten. |

> Keine automatische Umbenennung, keine Migration — dies bleibt ein bewusster,
> menschlich freigegebener Schritt.

### 9.4 Was ist jetzt konfigurierbar / was bleibt Future Work

- **Jetzt konfigurierbar:** `project_name` (Projekt-Identität), `tags` (inkl. `ManagedBy`/
  `CreatedBy`), `Maker` (Provenance-Tag, Konstante), `aws_region` (Region, §9.6).
- **Definiert (Design, keine Variable):** Cost Profile (§9.5), Availability (§9.7),
  Data Strategy (§9.8), Security Profile (§9.9).
- **Future Work (NICHT implementiert):** Optional Features → User Confirmation.

### 9.5 Cost Profile (Installation Layer, T014)

> Zweite Installations-Entscheidung aus dem Konzept `architecture/installation-concept.md` §3.
> **Nur definiert (Design), keine `cost_profile`-Variable implementiert** — kein Consumer.

- **Vier Profile** (Taxonomie, §3): `LOWEST/PROTOTYPE`, `STANDARD`, `HIGH AVAILABILITY`, `CUSTOM`.
- **Default = `LOWEST / PROTOTYPE`** — die aktuelle Terraform-Konfiguration entspricht exakt
  diesem Profil (Single Region, On-Demand-DynamoDB, kein PITR/KMS/custom-domain, SSE-S3,
  HTTP-App, 7-Tage-Retention, optionale Hardening-Features sämtlich deferred).
- **Empfohlene spätere Repräsentation:** eine `cost_profile`-Variable mit `validation {}`
  (`lowest`/`standard`/`high_availability`/`custom`), die kostensteigernde Features **gated**,
  aber selbst keine Ressourcen erzeugt. `CUSTOM` erfordert explizite Bestätigung (§10 Konzept).
- **Bewusst KEINE Variable jetzt:** der Installations-Workflow konsumiert den Wert noch nicht;
  jede kostenrelevante Option ist bereits auf LOWEST gepinnt. Die Variable soll erst eingeführt
  werden, wenn eine Option erstmals profil-abhängig wird (Availability/Data-Strategy oder
  Optional-Features-Task).

Vollständiges Konzept: `architecture/installation-concept.md`.

### 9.6 Region (Installation Layer, T015)

> Dritte Installations-Entscheidung aus dem Konzept `architecture/installation-concept.md` §3.2.
> **Bereits sauber implementiert via `var.aws_region`** — keine neue Variable nötig.

- **Default / aktuell:** `eu-central-1` („Europe (Frankfurt)“) — `terraform/variables.tf`
  (`var.aws_region`, Default `"eu-central-1"`).
- **Konsumenten (verified):** Root-Provider `region = var.aws_region` (`main.tf:27`);
  `module.monitoring` erhält `aws_region` (`main.tf:152`, CloudWatch-Widget-Region);
  `module.cloudtrail` leitet die Region via `data "aws_region" "current"` ab. **Kein Provider-Alias
  → Single-Region-Design.**
- **Begründung:** Europäischer/deutscher Projektkontext; Frankfurt ist eine gut etablierte
  EU-Region, die alle genutzten Services unterstützt (DynamoDB, Lambda, Cognito, HTTP-API,
  CloudWatch, CloudTrail, S3). Projektwahl, keine Universalaussage.
- **Beziehung zu Cost Profile (T014 `LOWEST/PROTOTYPE`):** Single Region bevorzugt; keine
  zweite Region eingeführt.
- **Beziehung zu Availability (T016) / Data Strategy (T017):** *deferred* — Region ≠ AZ-Design
  ≠ Daten-Replikation (siehe Konzept §3.2/§4).
- **Region ändern:** vor erstem `apply` (State leer) → zielt nur auf andere Region; nach `apply`
  → Redeploy aller regionalen Ressourcen in die neue Region.**

### 9.7 Availability (Installation Layer, T016)

> Vierte Installations-Entscheidung aus dem Konzept `architecture/installation-concept.md` §3.3.
> **Nur definiert (Design)** — keine Terraform-Änderung, da die aktuelle Architektur das
> gewählte Profil bereits korrekt abbildet.

- **Gewählt:** `LOW / PROTOTYPE` — Single Region (`eu-central-1`), voll auf AWS-managed
  Serverless-Diensten, **keine** eigene Netzwerk-/Failover-Infrastruktur.
- **Architektur (verified):** kein VPC, keine Subnets, kein IGW/NAT, keine VPC-Endpoints, kein
  EC2. Lambda ohne `vpc_config` (AWS-managed Ausführungsumgebung); API GW, DynamoDB, Cognito,
  CloudWatch, CloudTrail + S3-Bucket sind managed Services.
- **Wichtig:** das Fehlen einer VPC ist für diese Serverless-Architektur **kein**
  Availability-Defizit; eine VPC wird bewusst nicht nur für den Anschein von HA eingeführt.
- **Abgrenzung:** Region ≠ Availability Zone ≠ Service-Verfügbarkeit ≠ Daten-Replikation.
- **Bewusst deferred:** VPC/Subnets, NAT/IGW, VPC-Endpoints, Route-53-Failover, zweite Region,
  DynamoDB Global Tables, Replikation, zusätzliche Failover-Services — erst unter einem
  späteren `HIGH AVAILABILITY`/`CUSTOM`-Profil mit expliziter Bestätigung.
- **Data Strategy (T017):** *deferred* — API/Compute-Verfügbarkeit ist getrennt von
  Datenreplikation zu entscheiden.

### 9.8 Data Strategy (Installation Layer, T017)

> Fünfte Installations-Entscheidung aus dem Konzept `architecture/installation-concept.md` §3.4.
> **Nur definiert (Design)** — keine Terraform-Änderung, da die aktuelle DynamoDB-Konfiguration
> die gewählte Strategie bereits korrekt abbildet.

- **Primärer Datenspeicher:** DynamoDB (Single Table `aws_dynamodb_table.orders`, `PAY_PER_REQUEST`,
  Key `pk`/`sk`, GSI1 `INCLUDE-Projection`) in `eu-central-1`.
- **Replikation:** Single Region — **keine** Global Tables / cross-region Replicas.
- **Backup / PITR:** **NICHT aktiviert** (kein `point_in_time_recovery`). Bewusster
  LOWEST/PROTOTYPE-Trade-off (Kosten/Einfachheit vs. Recovery); Wiederaufnahme als optionaler
  Punkt in T019.
- **Verschlüsselung:** DynamoDB encrypts at rest by default (AWS-owned KMS) — **kein**
  explizites `server_side_encryption`-Block, **kein** customer-managed KMS.
- **Deletion Protection / TTL / Streams:** nicht konfiguriert (der Modul-Output
  `table_stream_arn` ist mangels `stream`-Block leer).
- **Konsistenz:** Lambda nutzt Standard-DynamoDB-Reads (GetItem/Query, keine
  `ConsistentRead`/Transaktionen) → eventually-consistent Reads; Strongly-consistent /
  transaktionale Anforderungen sind Week-3-Arbeit.
- **Kosten (T014 `LOWEST/PROTOTYPE`):** keine Global Tables/Replikation/KMS/Backup-Infra →
  `LOW`.
- **Security Profile (T018) / Optional Features (T019):** *deferred* — KMS, PITR, Streams
  werden dort als explizite Optionen bewertet.

### 9.9 Security Profile (Installation Layer, T018)

> Sechste Installations-Entscheidung aus dem Konzept `architecture/installation-concept.md` §3.5.
> **Nur definiert (Design)** — keine Terraform-Änderung, da die aktuelle Architektur das Profil
> bereits korrekt abbildet.

- **Gewählt:** `LOW / PROTOTYPE` — IAM Least Privilege, Cognito + API-Gateway-JWT, managed
  Verschlüsselung, CloudWatch-Logging + CloudTrail-Management-Audit.
- **Identity/Auth:** Cognito User Pool (admin-create, MFA OFF), Public Client
  (`USER_PASSWORD_AUTH` + Refresh), Gruppe `staff`. Benutzer-Auth über Cognito, nie IAM-Keys.
- **API-GW-Authorization:** JWT-Authorizer (Issuer = Cognito, Audience = Client-ID); **alle 4
  Routen** sind `JWT`-geschützt (keine public Routen).
- **Application-Authorization (GAP):** `cognito:groups`-Auswertung im Lambda **nicht**
  implementiert (Week-3/A-09) — der Authorizer prüft nur Issuer/Audience.
- **IAM:** eine Lambda-Execution-Role mit Inline-Policy (`PutItem/GetItem/UpdateItem/Query`
  nur auf Tabelle+GSI1; `logs:*`); kein `Scan/Delete/Batch`, kein `iam:*`, kein `PassRole`,
  kein `AdministratorAccess`. API-GW→Lambda als separate resource-based Permission.
- **Permissions Boundary:** `MaysOrders-Terraform-Developer-Boundary` (Policy-Gate, optional,
  nicht in den Terraform-Modulen) — beschränkt die Deployment-Identität; kein Pflicht-Bestandteil.
- **Verschlüsselung:** DynamoDB AWS-managed default (kein KMS-Kundenkey); CloudTrail-S3
  explizit SSE-S3/AES256 + Public-Access-Block + `BucketOwnerEnforced`.
- **Transport:** HTTP API V2 (`protocol_type = "HTTP"`), kein Custom-Domain/ACM; AWS-managed
  Endpoint liefert TLS am AWS-Edge; Custom-Domain optional.
- **Audit:** CloudWatch (Lambda-Log-Group 7 Tage + Dashboard + 6 Alarme); CloudTrail
  (multi-region, global service events, Mgmt-Events Read+Write, Log-Validierung, S3 mit
  Least-Privilege-Bucket-Policy).
- **Netzwerk:** kein VPC/Subnet/SG/NACL/NAT/IGW (managed Serverless). Kein Sicherheitsdefizit.
- **Kosten (T014):** kein KMS/Data-Events/WAF/GuardDuty/Custom-Domain → `LOW`.
- **Deferred (→ T019):** Gruppen-Authorization, KMS, CloudTrail Data Events/Hardening,
  Custom-Domain/TLS, ggf. WAF/GuardDuty.