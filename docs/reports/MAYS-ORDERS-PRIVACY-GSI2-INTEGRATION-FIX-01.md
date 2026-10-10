# MAYS-ORDERS-PRIVACY-GSI2-INTEGRATION-FIX-01

## Root Cause
DynamoDB Terraform Modul definierte nur GSI1. Privacy-Code verwendet GSI2 für subjectId-Queries. Integrationsblocker.

## Terraform-Änderungen
- `terraform/modules/dynamodb/main.tf`
- Attribute `gsi2pk`, `gsi2sk` hinzugefügt
- `global_secondary_index gsi2` mit Partition Key `gsi2pk`, Sort Key `gsi2sk`
- Projection TYPE INCLUDE mit:
  orderId, pk, sk, subjectId, version, createdAt, status, updatedAt, customer, totalAmount, currency
- GSI1 unverändert

## Python-Kompatibilität
- `order_service.py` verwendet `GSI2_NAME = "gsi2"`, `GSI2_PK_PREFIX = "SUBJECT#"`
- Projection Expressions in inspect/export/erase passen zu INCLUDE-Projektion
- Pagination und Conditional Writes kompatibel

## Terraform-Validierung
- `terraform fmt` erfolgreich
- `terraform validate` SUCCESS im Modul
- Kein Apply/Destroy

## Tests
67 Tests PASS
GSI2 Query, Pagination, Projection, Fehlender Index, Version Conditional Writes geprüft

## Kosten/Hinweise
GSI2 On-Demand, Schreibkosten erhöhen sich minimal durch zusätzliche Index-Attribute. Keine Datenmigration erforderlich, Index wird bei bestehender Tabelle hinzugefügt.

## Restrisiken
- GSI2 muss noch deployed werden
- Bestehende Orders ohne subjectId bleiben ohne Indexeintrag

## Deployment-Voraussetzungen
Terraform Apply erforderlich, nach Freigabe.
