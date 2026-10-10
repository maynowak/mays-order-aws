# MAYS-ORDERS-PRIVACY-INTERNAL-FINALIZATION-01

## Aufrufarchitektur
Privacy Funktionen `inspect_subject`, `export_subject`, `erase_subject` sind interne Service-Methoden ohne öffentliche API. Aufruf erfolgt ausschließlich aus Backend-Code.

## Vertrauensgrenze
- `_require_privacy_auth` prüft:
  - `ORDERS_PROJECT_NAME` gesetzt, fail closed
  - Projekt-Isolation
  - `authorized` Flag
  - Separate Permissions `privacy_inspect/export/erase`
  - Interner Token `internal_token` muss mit `PRIVACY_INTERNAL_SECRET` übereinstimmen
- Keine clientseitigen Berechtigungen, keine öffentlichen Endpunkte

## Sicherheitsmaßnahmen
- Fail closed bei fehlender Konfiguration
- Explizite Policy für ERASE erforderlich, kein destruktiver Default
- PREVIEW mutationsfrei
- Query Fehler → BLOCKED
- Conditional Writes mit `subjectId` und `version`
- Pagination vollständig
- Keine PII in Logs

## Codeänderungen
- `OrderService._require_privacy_auth` erweitert um internen Token
- `erase_subject` erfordert explizite Policy, Version in Conditional Writes
- Projection für Version hinzugefügt
- Tests angepasst mit interner Token

## Tests
65 Tests PASS
Negativtests für gefälschte Berechtigungen, fehlender Kontext, Cross-Project, fehlende Policy, GSI2-Fehler, Pagination, Concurrent Updates, wiederholte Löschung.

## Bekannte Einschränkungen
- Vertrauensgrenze basiert auf Umgebungsvariable, kein kryptografisches Signing
- Anonymisierung deckt nur customer.name/email ab, vollständige PII-Freiheit nicht nachgewiesen
- PREVIEW/EXECUTE Bindung nicht kryptografisch gesichert
- SQS/Worker-Retry-Sicherheit dokumentiert, nicht vollständig getestet

## Deployment Blocker
Keine. Kein AWS-Mutation, keine Terraform Änderungen.

## Empfehlung
Für Integrationstest freigeben mit dokumentierten Restrisiken. Produktivbetrieb erfordert serverseitig signierten Kontext.
