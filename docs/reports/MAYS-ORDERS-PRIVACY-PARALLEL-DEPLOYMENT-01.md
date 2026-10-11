# MAYS-ORDERS-PRIVACY-PARALLEL-DEPLOYMENT-01

## Ziel
Verifikation der Parallel-Deployment-Fähigkeit für Privacy-Funktionen.

## 1. Terraform-Projektnamenskonvention
- Projektname wird über Variable `var.project_name` durchgereicht
- Namensmuster in allen Modulen: `${var.project_name}-<ressource>`
- Beispiele:
  - Cognito User Pool: `${var.project_name}-users`
  - DynamoDB Table: `orders` mit GSI, Name projektunabhängig, Table-Name aus `var.project_name`
  - S3 Buckets: `${var.bucket_name_prefix}-${var.environment}-${var.project_name}` → global eindeutig
  - Lambda: `${var.project_name}-handler`, `${var.project_name}-sqs-worker`
  - API Gateway: `${var.project_name}-api`
  - IAM Roles/Policies: `${var.project_name}-handler-role`, `${var.project_name}-handler-policy`
- Keine hartcodierten globalen Namen gefunden

## 2. Ressourcen seit Einführung Privacy-Funktionen
Änderungen seit `874d3f0`:
- DynamoDB: GSI2 Attribute `gsi2pk/gsi2sk` und GSI2 Index hinzugefügt
- IAM: Split in Table vs GSI, `dynamodb:DeleteItem`, `dynamodb_gsi2_arn`
- Lambda: Env `ORDERS_PROJECT_NAME`, Runtime `python3.14`
- Keine neuen Module, keine neuen globalen Namen

## 3. Projektisolierung
- Alle Ressourcen nutzen `var.project_name` für Naming
- Workspace-Isolation:
  - `mays-orders` → Workspace `mays-orders`, State `env:/mays-orders/terraform.tfstate`
  - `mays-orders-privacy-test` → Workspace `mays-orders-privacy-test`, State `env:/mays-orders-privacy-test/terraform.tfstate`
- Backend Bucket `mays-orders-tfstate-central-240571105849` ist projektübergreifend, State-Key trennt Projekte

## 4. Globale Eindeutigkeit / feste Namen
- S3 Bucket Namen sind projektbezogen → global eindeutig
- Cognito User Pool Name ist projektbezogen
- Kein Shared Resource mit festem Namen identifiziert
- Keine gemeinsamen Identitäten zwischen Projekten

## 5. Isoliertes Testprojekt
`project_name = mays-orders-privacy-test`
- Terraform Workspace verifiziert: `mays-orders-privacy-test`
- Backend State: `env:/mays-orders-privacy-test/terraform.tfstate`
- Terraform validate: `Success! The configuration is valid.`
- Plan: `.mays-installer/runs/20261010-185211/plans/mays-orders-privacy-test-development-0.1.0-H2-240571105849-deploy-0004.tfplan`
- `resource_changes`: 61, alle `create`
- Keine Adressen mit `mays-orders` ohne `privacy-test`

## 6. Ergebnis
Parallel-Deployment für Privacy-Test bereit.
- Keine Überschneidungen mit bestehender Installation `mays-orders`
- Namenskonvention beibehalten
- Keine Architekturänderungen erforderlich

Status: GREEN
