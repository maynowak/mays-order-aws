# MAYS-ORDERS-PRIVACY-IAM-LEAST-PRIVILEGE-01

## Änderungen
- IAM Policy in `terraform/modules/iam/main.tf` aufgeteilt
- Tabelle: PutItem, GetItem, UpdateItem, DeleteItem, Query
- GSI1/GSI2: nur Query
- Least Privilege eingehalten, keine Wildcards

## Privacy Execution Role
- Lambda Handler Rolle `*-handler-role` ist der interne Ausführungskontext für OrderService
- Privacy Funktionen inspect/export/erase laufen innerhalb Lambda → Rolle nachweisbar

## Tests
- 67 Unit Tests PASS
- Terraform validate PASS

## Risiken
- GSI2 noch nicht deployed
- Internal Trust Boundary weiterhin konventionell
