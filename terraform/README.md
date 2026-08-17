# Terraform — May's Orders

> Stand Woche 2 (T011-01): **Grundgerüst angelegt.** Noch keine Ressourcen erzeugt, kein `apply`.

## 1. Ziel

Die AWS-Infrastruktur wird vollständig als Infrastructure as Code abgebildet:

- API Gateway (HTTP API)
- Lambda (Order Handler)
- DynamoDB (`mays-orders`)
- IAM (Lambda Execution Role, Resource-Based Policy)
- Cognito User Pool + Client + Gruppe `staff`

Keine manuell erzeugte Infrastruktur als finales Ergebnis.

## 2. Struktur

**Aktueller Stand (T011-01, Grundgerüst):**

```text
terraform/
├── main.tf         terraform-Block, AWS-Provider, Region, Default-Tags
├── variables.tf    Eingabevariablen (Region, Projekt-Name, Tags)
├── outputs.tf      Outputs (werden ab T011-02 je Ressource ergänzt)
└── README.md       dieses Dokument
```

**Geplante Erweiterung (ab T011-02):** Die Ressourcen (DynamoDB, IAM, Lambda, API GW,
Cognito) werden in `main.tf` ergänzt; relevante Outputs in `outputs.tf`.

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