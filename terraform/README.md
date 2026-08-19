# Terraform — May's Orders

> Stand Woche 2 (T011-11): **DynamoDB-Tabelle + GSI1, IAM (Execution Role), Lambda (Order Handler, Python 3.14), Cognito (User Pool + Client + Gruppe `staff`), API Gateway HTTP API (vier Routen, JWT-Authorizer, Lambda-Integration) und CloudWatch Monitoring (Dashboard, Alarme, Log-Retention) umgesetzt.** AWS-Provider `~> 6.0`. Noch kein `apply` ausgeführt.

## 1. Ziel

Die AWS-Infrastruktur wird vollständig als Infrastructure as Code abgebildet:

- API Gateway (HTTP API)
- Lambda (Order Handler)
- DynamoDB (`mays-orders`)
- IAM (Lambda Execution Role, Resource-Based Policy)
- Cognito User Pool + Client + Gruppe `staff`

Keine manuell erzeugte Infrastruktur als finales Ergebnis.

## 2. Struktur

**Aktueller Stand (T011-11, CloudWatch Monitoring):**

```text
terraform/
├── main.tf         terraform-Block, AWS-Provider, Region, Default-Tags,
│                   DynamoDB-Tabelle + GSI1, IAM (Role, Trust, Policy),
│                   Lambda (Order Handler), Cognito (User Pool, Client, Gruppe),
│                   HTTP API (V2) + Stage + JWT-Authorizer + Integration + 4 Routen,
│                   Lambda-Invoke-Permission (API GW), Seed-Opt-in (terraform_data)
├── monitoring.tf   CloudWatch Monitoring (T011-11): Dashboard (mays-orders-overview),
│                   Alarme (6), Lambda-Log-Group (Retention 7 Tage)
├── variables.tf    Eingabevariablen (Region, Projekt-Name, Tags, Seed-Opt-in,
│                   Monitoring-Schalter + Alarm-Schwellwerte)
├── outputs.tf      Outputs (DynamoDB, IAM, Lambda, Cognito, API GW)
└── README.md       dieses Dokument
```

**Quellcode der Lambda:** `lambda/` (Python 3.14, aktiv; Node.js/TypeScript-
Baseline T011-04 entfernt, historisch via Git `449cdd7`) — siehe §2.3.

**Geplante Erweiterung (ab T011-04):** Die übrigen Ressourcen (Lambda, API GW,
Cognito) werden in `main.tf` ergänzt; relevante Outputs in `outputs.tf`.

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

## 3. Geplante Ressourcen

| Ressource | Terraform-Typ (Vorschlag) |
|-----------|---------------------------|
| DynamoDB-Tabelle | `aws_dynamodb_table` (On-Demand, GSI1) ✅ |
| IAM-Rolle | `aws_iam_role` + `aws_iam_role_policy` ✅ |
| Lambda | `aws_lambda_function` (Zip aus Build) ✅ |
| Lambda-Permission | `aws_lambda_permission` (API GW invoke) ✅ |
| HTTP API | `aws_apigatewayv2_api` + `aws_apigatewayv2_integration` + `aws_apigatewayv2_route` + `aws_apigatewayv2_authorizer` ✅ |
| Cognito | `aws_cognito_user_pool`, `aws_cognito_user_pool_client`, `aws_cognito_user_group` ✅ |
| CloudWatch Dashboard | `aws_cloudwatch_dashboard` ✅ (T011-11) |
| CloudWatch Alarme | `aws_cloudwatch_metric_alarm` ✅ (T011-11) |
| CloudWatch Log-Group | `aws_cloudwatch_log_group` ✅ (T011-11, Retention 7 Tage) |

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