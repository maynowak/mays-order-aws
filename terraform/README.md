# Terraform — May's Orders

> Stand Woche 2 (T011-04 + Python-3.14-Migration): **DynamoDB-Tabelle + GSI1, IAM (Execution Role) und Lambda (Order Handler, Python 3.14) umgesetzt.** AWS-Provider `~> 6.0`. Noch kein `apply` ausgeführt.

## 1. Ziel

Die AWS-Infrastruktur wird vollständig als Infrastructure as Code abgebildet:

- API Gateway (HTTP API)
- Lambda (Order Handler)
- DynamoDB (`mays-orders`)
- IAM (Lambda Execution Role, Resource-Based Policy)
- Cognito User Pool + Client + Gruppe `staff`

Keine manuell erzeugte Infrastruktur als finales Ergebnis.

## 2. Struktur

**Aktueller Stand (T011-04, Lambda):**

```text
terraform/
├── main.tf         terraform-Block, AWS-Provider, Region, Default-Tags,
│                   DynamoDB-Tabelle + GSI1, IAM (Role, Trust, Policy),
│                   Lambda (Order Handler)
├── variables.tf    Eingabevariablen (Region, Projekt-Name, Tags)
├── outputs.tf      Outputs (DynamoDB, IAM, Lambda; weitere je Ressource)
└── README.md       dieses Dokument
```

**Quellcode der Lambda:** `lambda/` (Python 3.14, aktiv; Node.js/TypeScript-
Baseline T011-04 bleibt als historischer Stand erhalten) — siehe §2.3.

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

## 3. Geplante Ressourcen

| Ressource | Terraform-Typ (Vorschlag) |
|-----------|---------------------------|
| DynamoDB-Tabelle | `aws_dynamodb_table` (On-Demand, GSI1) ✅ |
| IAM-Rolle | `aws_iam_role` + `aws_iam_role_policy` ✅ |
| Lambda | `aws_lambda_function` (Zip aus Build) ✅ |
| Lambda-Permission | `aws_lambda_permission` (API GW invoke) ⏳ T011-06 |
| HTTP API | `aws_apigatewayv2_api` + `aws_apigatewayv2_integration` + `aws_apigatewayv2_route` + `aws_apigatewayv2_authorizer` |
| Cognito | `aws_cognito_user_pool`, `aws_cognito_user_pool_client`, `aws_cognito_user_pool_domain` (falls nötig) |

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