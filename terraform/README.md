# Terraform — May's Orders

> Stand Woche 2 (T011-02): **DynamoDB-Tabelle + GSI1 umgesetzt.** AWS-Provider `~> 6.0`. Noch kein `apply` ausgeführt.

## 1. Ziel

Die AWS-Infrastruktur wird vollständig als Infrastructure as Code abgebildet:

- API Gateway (HTTP API)
- Lambda (Order Handler)
- DynamoDB (`mays-orders`)
- IAM (Lambda Execution Role, Resource-Based Policy)
- Cognito User Pool + Client + Gruppe `staff`

Keine manuell erzeugte Infrastruktur als finales Ergebnis.

## 2. Struktur

**Aktueller Stand (T011-02, DynamoDB + GSI1):**

```text
terraform/
├── main.tf         terraform-Block, AWS-Provider, Region, Default-Tags, DynamoDB-Tabelle + GSI1
├── variables.tf    Eingabevariablen (Region, Projekt-Name, Tags)
├── outputs.tf      Outputs (DynamoDB-Name/-ARN; weitere je Ressource in Folge-Tasks)
└── README.md       dieses Dokument
```

**Geplante Erweiterung (ab T011-03):** Die übrigen Ressourcen (IAM, Lambda, API GW,
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

## 3. Geplante Ressourcen

| Ressource | Terraform-Typ (Vorschlag) |
|-----------|---------------------------|
| DynamoDB-Tabelle | `aws_dynamodb_table` (On-Demand, GSI1) |
| Lambda | `aws_lambda_function` (Zip aus Build) |
| IAM-Rolle | `aws_iam_role` + `aws_iam_role_policy` |
| Lambda-Permission | `aws_lambda_permission` (API GW invoke) |
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

- Lambda-Zip muss vor `apply` gebaut sein (Build-Step im Feature-Workflow).
- API-GW-Route → Integration → Lambda-Permission → Lambda-Deployment.