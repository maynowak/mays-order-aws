# MAYS-ORDERS-RESOURCE-COUNT-RECONCILIATION-01

## Ausgangslage
Abweichung zwischen ursprünglich 37 Ressourcen und aktuell 56/61 geplanten Terraform-Ressourcen.

## 1. Git-Historie
- Letzter Stand vor Datenschutzarbeiten: `874d3f0e2f887c93ad3ec6ff6f6d4f674bf366ea`
- Erster Privacy-Commit: `d2e2650`
- Änderungen zwischen 874d3f0..HEAD in terraform/:
  `terraform/main.tf`, `terraform/modules/dynamodb/main.tf`, `terraform/modules/dynamodb/outputs.tf`, `terraform/modules/iam/main.tf`, `terraform/modules/iam/variables.tf`, `terraform/modules/lambda/main.tf`

Kernänderungen:
- DynamoDB: Attribute `gsi2pk`/`gsi2sk` + GSI2 `global_secondary_index` hinzugefügt
- IAM: Split DynamoDBTable vs DynamoDBGSI, `dynamodb:DeleteItem` hinzugefügt, `dynamodb_gsi2_arn` eingeführt
- Lambda: Env `ORDERS_PROJECT_NAME` hinzugefügt, `runtime = "python3.14"` gesetzt
- IAM Modul erhält neuen Input `dynamodb_gsi2_arn`

Anzahl definierter `resource`-Blöcke in Modulen:
- 874d3f0: 54 Ressourcen
- HEAD: 54 Ressourcen
→ Modul-Ressourcenanzahl unverändert. Zunahme entsteht durch neue Abhängigkeiten und GSI2-Projektion.

## 2. Bestehende Installation mays-orders
- Workspace verifiziert: `mays-orders`
- Remote State: `s3://mays-orders-tfstate-central-240571105849/env:/mays-orders/terraform.tfstate`
- Ressourcen im State: 25
  `aws_caller_identity 1, aws_cloudwatch_metric_alarm 2, aws_cognito_user_group 1, aws_cognito_user_pool 1, aws_cognito_user_pool_client 1, aws_iam_policy 1, aws_iam_policy_document 4, aws_iam_role 2, aws_iam_role_policy_attachment 1, aws_lambda_function 1, aws_lambda_permission 1, aws_s3_bucket 1, aws_s3_bucket_lifecycle_configuration 1, aws_s3_bucket_public_access_block 1, aws_s3_bucket_server_side_encryption_configuration 1, aws_s3_bucket_versioning 1, aws_scheduler_schedule 1, aws_sns_topic 1, aws_sns_topic_policy 1, aws_sns_topic_subscription 1`
- Keine DynamoDB-Tabelle, kein API Gateway, kein SQS im State → bestehende Installation ist teilweise / Ressourcen liegen außerhalb des betrachteten States.

## 3. Privacy-Test-Plan
- Projekt: `mays-orders-privacy-test`
- Workspace: `mays-orders-privacy-test`
- Plan: `.mays-installer/runs/20261010-185211/plans/mays-orders-privacy-test-development-0.1.0-H2-240571105849-deploy-0004.tfplan`
- `resource_changes`: 61, alle `create`
- Ressourcen-Typen u.a.:
  `aws_apigatewayv2_api 1`, `aws_apigatewayv2_route 4`, `aws_cognito_user_pool 1`, `aws_cognito_user_pool_client 1`, `aws_dynamodb_table 1`, `aws_lambda_function 3`, `aws_sqs_queue 1`, `aws_sns_topic 1`, `aws_s3_bucket 2`, `aws_iam_role 4`, `aws_iam_policy 2`

Vergleich mit bestehender Installation:
- Neue Gesamterstellung für leeren Workspace
- GSI2 ist Teil der DynamoDB-Tabelle und führt zu zusätzlicher Projektion
- IAM-Split erzeugt zusätzliche Policy-Dokumente/Attachments
- Lambda-Runtime und Projekt-Env führen zu veränderten Lambda-Ressourcen

Ursache der 56/61 geplanten Neuanlagen:
- Privacy-Test ist ein frischer, isolierter Workspace ohne bestehenden State
- Der Plan erstellt das komplette Modul-Set neu
- Zählbasis 37 bezog sich auf einen früheren Plan/State-Zustand ohne vollständiges Modul-Set und ohne GSI2/IAM-Erweiterungen

## Differenzliste
- DynamoDB GSI2: keine separate Terraform-Resource, aber zusätzliche Attribute + GSI → wirkt sich auf Table-Resource und IAM aus
- IAM: `DynamoDBGSI` Statement + `dynamodb_gsi2_arn` → zusätzliche Policy-Dokumente
- Lambda: zusätzliches Env + Runtime
- Vollständiges Modul-Set wird neu erstellt → 61 Creates vs 25 im bestehenden partiellen State

## Ursache eindeutig
Zählung bezieht sich auf unterschiedliche Basen:
- 37 Ressourcen = historischer Plan/Ansicht der bestehenden, nicht vollständig im State abgebildeten Installation
- 56/61 Ressourcen = vollständiger Fresh-Plan für neues isoliertes Projekt `mays-orders-privacy-test` mit aktuellen Modul-Änderungen

## Korrekturempfehlung
Keine Code-Änderung. Read-Only Reconciliation:
1. Dokumentation des bestehenden partiellen States für `mays-orders` beibehalten
2. Für `mays-orders-privacy-test` weiterhin isolierte Workspace-/State-Isolation nutzen
3. Zählungen zukünftig über `terraform state list` und `terraform plan -json` mit gleicher Basis vergleichen, nicht über historische Rundzahlen

Status: READ-ONLY, keine Mutationen ausgeführt
