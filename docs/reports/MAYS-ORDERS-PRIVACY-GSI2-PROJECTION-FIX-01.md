# MAYS-ORDERS-PRIVACY-GSI2-PROJECTION-FIX-01

## Root Cause
GSI2 `non_key_attributes` enthielt `pk` und `sk`, obwohl diese Primärschlüssel Attribute in DynamoDB automatisch verfügbar sind und nicht explizit projiziert werden dürfen.

## Fix
- `terraform/modules/dynamodb/main.tf`
- `pk` und `sk` aus `non_key_attributes` von GSI2 entfernt
- Projection beibehalten: orderId, subjectId, version, createdAt, status, updatedAt, customer, totalAmount, currency
- GSI1 unverändert

## Python-Kompatibilität
- `erase_subject` Projection angepasst auf `orderId,subjectId,version,createdAt`
- `pk`/`sk` werden aus `orderId` abgeleitet (`ORDER_ID_PREFIX + orderId`, `ORDER_SK`)
- Inspect/Export unverändert kompatibel

## Terraform Validation
- `terraform fmt` OK
- `terraform validate` SUCCESS

## Tests
67 Tests PASS

## Review
- pk/sk nicht mehr explizit projiziert
- DynamoDB Schlüssel automatisch verfügbar
- Alle benötigten Attribute vorhanden
- GSI1 unverändert
- Keine neuen Ressourcen
