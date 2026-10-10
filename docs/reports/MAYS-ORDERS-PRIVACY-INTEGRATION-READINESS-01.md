# MAYS-ORDERS-PRIVACY-INTEGRATION-READINESS-01

## GSI2 Terraform & Python Kompatibilität
- GSI2 in Terraform vorhanden, Attribute `gsi2pk`/`gsi2sk`, Projection INCLUDE ohne pk/sk
- Python-Code nutzt `GSI2_NAME`, `GSI2_PK_PREFIX`, ProjectionExpression enthält `pk/sk` – automatisch verfügbar
- Erase_subject korrigiert: pk/sk direkt aus Query nutzen, keine Rekonstruktion

## Internal Trust
- Tokenprüfung via `PRIVACY_INTERNAL_SECRET` + `internal_token` mit `secrets.compare_digest`
- Token wird über `context` Dict übergeben, Herkunft nicht technisch erzwungen → WARNING
- Projekt-Isolation, separate Permissions vorhanden

## Erase Safety
- PREVIEW mutationsfrei
- EXECUTE erfordert explizite Policy
- Conditional Writes mit `subjectId` + `version`
- Idempotenz gewährleistet

## Anonymisierung
- Nur `customer.name/email` anonymisiert, `subjectId` entfernt
- Weitere PII-Felder nicht geprüft → WARNING

## PREVIEW/EXECUTE
- Keine kryptografische Bindung → WARNING

## SQS/DLQ
- Nicht getestet → NOT TESTED

## Tests
- 67 Tests PASS
- Terraform validate SUCCESS

## Integration Test Readiness
- A. Blocker für isolierte Integrationstests: GSI2 muss deployed sein
- B. Blocker für produktive Privacy-Operationen: Vertrauensgrenze, Anonymisierung, SQS

## Empfehlung
Integrationstest nur mit deployed GSI2, dokumentierte Restrisiken akzeptieren.
