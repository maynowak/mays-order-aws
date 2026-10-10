# MAYS-ORDERS-DSGVO-PRIVACY-ERASURE-01

## Ziel
Implementierung der dritten Kernfunktion der Privacy Capability:
`privacy.erase(subjectId, context, options)` mit PREVIEW/EXECUTE, Retention-Entscheidungen, Anonymisierung, Conditional Writes, Idempotenz.

## Security Gate
Authentisierung fail-closed:
- `context.project` muss `ORDERS_PROJECT_NAME` entsprechen
- `context.authorized` muss truthy sein
- Keine client-seitige Berechtigung, keine pauschale `privacy:*`
Bestehende `inspect_subject`/`export_subject` Autorisierung wurde beibehalten und auf `erase_subject` übertragen.

## Architektur
- Interne Service-Funktion `OrderService.erase_subject`
- Kein öffentlicher API-Endpunkt
- Nutzt bestehende DynamoDB GSI2: `gsi2pk = SUBJECT#<subjectId>`
- Query statt Scan, Pagination vollständig
- Kein AWS-Mutation außerhalb Lambda

## Contract

### Preview
```json
{
  "operationId": "...",
  "subjectId": "...",
  "status": "PREVIEW",
  "affectedRecords": 3,
  "plannedDeletes": 2,
  "plannedAnonymizations": 0,
  "plannedRetentions": 1,
  "completedAt": "..."
}
```

### Execute Ergebnis
```json
{
  "schemaVersion": "1.0",
  "operationId": "...",
  "subjectId": "...",
  "status": "COMPLETED|PARTIALLY_COMPLETED|BLOCKED",
  "affectedRecords": 3,
  "deletedRecords": 2,
  "anonymizedRecords": 0,
  "retainedRecords": 1,
  "failedRecords": 0,
  "completedAt": "..."
}
```

## Retention-Entscheidungen
- ERASE: `delete_item` mit ConditionExpression `subjectId = :sid`
- ANONYMIZE: `update_item` setzt customer.name/email auf anonymisiert, entfernt `subjectId`, `gsi2pk`, `gsi2sk`
- RETAIN: keine Mutation
- BLOCK: bei fehlender Entscheidung oder Sicherheitsverletzung

## Safety
- Conditional Writes verhindern Race Conditions
- Idempotenz durch ConditionalExpression und wiederholbare Aufrufe
- PREVIEW mutiert niemals DynamoDB/SQS
- Keine personenbezogenen Daten in Auditlogs

## SQS/Worker
Bei Löschung bleibt Worker-Risiko bestehen. Dokumentiert, keine neuen Ressourcen. Worker sollten subjectId prüfen vor Verarbeitung.

## Tests
65 Tests passing, inkl.:
- PREVIEW ohne Mutation
- ERASE löschen
- ANONYMIZE
- Autorisierung
- Projektmismatch
- Pagination
- Conditional Write Fehler
- Idempotenz

## Einschränkungen
- Backups/PITR werden nicht gelöscht
- CloudTrail/CloudWatch bleiben erhalten
- Orders ohne subjectId werden nicht erfasst
- Vollständige DSGVO-Löschung erfordert Betreiber-Prozesse außerhalb Mays-Orders

## Deployment
Keine Terraform-Änderungen, keine Apply/Destroy.
