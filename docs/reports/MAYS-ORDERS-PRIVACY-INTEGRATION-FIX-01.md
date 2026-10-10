# MAYS-ORDERS-PRIVACY-INTEGRATION-FIX-01

## GSI2 IAM Fix
- `terraform/modules/dynamodb/outputs.tf`: Outputs `gsi2_name` und `gsi2_arn` hinzugefügt
- `terraform/modules/iam/variables.tf`: Variable `dynamodb_gsi2_arn` ergänzt
- `terraform/modules/iam/main.tf`: Ressourcenliste um `var.dynamodb_gsi2_arn` erweitert, Aktion `dynamodb:DeleteItem` für Erase Policy hinzugefügt
- `terraform/main.tf`: IAM Modul Aufruf um `dynamodb_gsi2_arn = module.dynamodb.gsi2_arn` erweitert

## Privacy Delete Permission
- `erase_subject` verwendet `delete_item` mit ConditionalExpression auf subjectId/version
- IAM Policy erweitert um `dynamodb:DeleteItem` auf Tabelle + GSI1 + GSI2
- Kein Wildcard, Least Privilege gewahrt

## Privacy Consistency
- GSI2 Query, Pagination, Conditional Writes vorhanden
- Projektprüfung und PRIVACY_INTERNAL_SECRET Fail-closed unverändert
- inspect_subject, export_subject, erase_subject PREVIEW/EXECUTE kompatibel
- Keine öffentlichen Endpunkte

## Tests
- Python Unit Tests: 67/67 PASS
- terraform fmt -check: PASS
- terraform validate: PASS für dynamodb und iam Module

## Verbleibende Risiken
- GSI2 noch nicht in AWS deployed → Integrationstests blockiert
- Internal Trust Boundary über Context-Dict, nicht kryptografisch erzwungen
- Anonymisierung unvollständig
- SQS/DLQ nicht getestet

## AWS-Testbereitschaft
- IAM und Terraform Verdrahtung jetzt komplett
- Deployment von GSI2 und IAM Policy Update erforderlich vor Live-Tests
