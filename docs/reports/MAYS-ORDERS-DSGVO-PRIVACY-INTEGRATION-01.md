# MAYS-ORDERS-DSGVO-PRIVACY-INTEGRATION-01

## Baseline
- HEAD: e602ca1
- Remote main verifiziert

## Phase 1 – Baseline
- Repo-Governance gelesen
- Git Status clean
- Privacy-Berichte berücksichtigt

## Phase 2 – DynamoDB / GSI2
- GSI2 Terraform: **BLOCKED** – In `terraform/modules/dynamodb/main.tf` nur GSI1 vorhanden, GSI2 nicht definiert. Code erwartet `gsi2` Index.
- Indexprojektion: nicht vorhanden
- Pagination: Code implementiert, kann nicht getestet ohne GSI2
- subjectId-Zuordnung: Code setzt `gsi2pk`/`gsi2sk` bei Create, aber ohne Index nutzlos
- Versionierung: vorhanden, Conditional Writes implementiert

## Phase 3 – Internal Trust
- Tokenprüfung via `PRIVACY_INTERNAL_SECRET` und `internal_token` implementiert, `secrets.compare_digest` genutzt
- Secret muss gesetzt sein, sonst BLOCKED
- **WARNING**: Token wird über `context` Dict übergeben, Herkunft nicht technisch erzwungen. Keine Garantie gegen HTTP-Weitergabe.
- Projekt- und Environment-Isolation vorhanden
- Keine öffentlichen Privacy-Routen

## Phase 4 – Erase Safety
- PREVIEW mutationsfrei: PASS
- EXECUTE erfordert explizite Policy: PASS
- Retention-Policy ERASE/ANONYMIZE/RETAIN: PASS
- Conditional Writes mit subjectId + version: PASS
- Idempotenz: PASS
- **WARNING**: Keine kryptografische Bindung PREVIEW→EXECUTE

## Phase 5 – Remaining Risks
- Anonymisierung: Nur `customer.name/email` anonymisiert, weitere PII-Felder nicht geprüft → **WARNING**
- SQS/DLQ-Retry: Nicht getestet → **NOT TESTED**
- Datenwiederherstellung nach Löschung: DynamoDB PITR vorhanden → Risiko dokumentiert
- Legacy Orders ohne subjectId: Werden nicht erfasst → **WARNING**

## Phase 6 – Test Readiness
- Lokale Tests: 67/67 PASS
- Installer-Tests: nicht ausgeführt im Preflight
- Isoliertes Testprojekt: nicht vorbereitet
- Testdatenkonzept: vorhanden via `make_order`
- AWS-Kosten: GSI2 würde On-Demand kosten, geschätzt gering

## Review Klassifikation
- DynamoDB GSI2: BLOCKED
- Internal Trust: WARNING
- Erase Safety: PASS mit WARNING
- Anonymization: WARNING
- SQS Safety: NOT TESTED
- Tests: PASS

## Deployment Blocker
1. GSI2 fehlt in Terraform
2. Vertrauensgrenze nicht kryptografisch erzwungen
3. Anonymisierung unvollständig

## Empfehlung
Integrationstest erst nach Bereitstellung von GSI2 und Entscheidung zur Vertrauensgrenze.
