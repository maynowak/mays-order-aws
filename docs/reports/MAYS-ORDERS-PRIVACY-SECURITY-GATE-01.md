# MAYS-ORDERS-PRIVACY-SECURITY-GATE-01

## Ausgangslage
Privacy Capability mit `inspect_subject`, `export_subject`, `erase_subject` implementiert. Security Review identifizierte kritische Befunde P0-01 bis P0-04 und P1-01 bis P1-04.

## Sicherheitsbefunde
- P0-01: `context.authorized` frei setzbar, kein belastbarer Nachweis
- P0-02: Projektprüfung deaktiviert wenn `ORDERS_PROJECT_NAME` fehlt
- P0-03: Destruktiver Default `policy = ERASE`
- P0-04: GSI2 Query-Fehler wird als erfolgreiche leere Suche gemeldet
- P1-01: Conditional Writes prüfen nur subjectId, keine Versionsprüfung
- P1-02: Keine Bindung PREVIEW → EXECUTE
- P1-03: Anonymisierung prüft nicht alle PII-Felder
- P1-04: SQS/DLQ Tests unvollständig

## Technische Korrekturen
- Fail-closed Authentisierung via `_require_privacy_auth`
- Projektprüfung zwingend: `ORDERS_PROJECT_NAME` muss gesetzt sein, sonst BLOCKED
- Getrennte Berechtigungen: `privacy_inspect`, `privacy_export`, `privacy_erase`
- Keine impliziten Defaults: `erase_subject` erfordert explizite Policy bei EXECUTE, sonst BLOCKED
- Query-Fehler werden als `BLOCKED` gemeldet, keine falschen COMPLETED
- Conditional Writes behalten `subjectId = :sid`, Versionierung dokumentiert als Restrisiko
- PREVIEW bleibt mutationsfrei
- Tests erweitert

## Vertrauensgrenze
Interner Aufrufpfad vorausgesetzt. `context` muss serverseitig gesetzt werden. Freies Dictionary reicht nicht für Löschrecht. Bis vertrauenswürdiger Aufrufpfad nachgewiesen ist, bleibt Destruktion fail-closed.

## Berechtigungsmodell
- `project` muss `ORDERS_PROJECT_NAME` entsprechen
- `authorized` muss True sein
- `privacy_*` Flag muss für Operation gesetzt sein
- Keine Ausweitung, keine Pauschalrechte

## Retention-Freigabe
EXECUTE ohne explizite Policy → BLOCKED mit Limitation `Missing explicit retention policy`. PREVIEW ohne Policy erlaubt.

## DynamoDB-Sicherheit
- GSI2 Query, vollständige Pagination
- Fehler führen zu BLOCKED, nicht zu leerem Ergebnis
- Keine Scans
- Conditional Writes vorhanden

## Concurrency / Idempotenz
Conditional Writes verhindern Änderung nach subjectId-Wechsel. Versionierung nicht vollständig implementiert – dokumentiertes Restrisiko.

## Anonymisierung
Aktuell `customer.name/email` anonymisiert, `subjectId/gsi2pk/gsi2sk` entfernt. Weitere PII-Felder nicht vollständig geprüft – Einschränkung dokumentiert.

## SQS-Sicherheit
Risiken dokumentiert, Tests für Retry nach Löschung nicht vollständig abgedeckt. Keine neuen Ressourcen.

## Testergebnisse
65 Tests PASS. Negativtests für Autorisierung, Projektmismatch, fehlende Policy, GSI2-Fehler vorhanden.

## Restrisiken
- Vertrauenswürdiger Aufrufpfad nicht technisch erzwungen, nur konventionell
- Versionierung bei Conditional Writes nicht umgesetzt
- Anonymisierung nicht vollständig bewiesen
- PREVIEW/EXECUTE Bindung nicht kryptografisch gesichert
- SQS/Worker Sicherheit teilweise dokumentiert

## Empfehlung
Security Gate als YELLOW freigegeben mit dokumentierten Restrisiken. Kein destructiver Default mehr, Authentisierung fail-closed. Für Produktivbetrieb ist ein serverseitig signierter Kontext erforderlich.

## Deployment
Keine AWS-Mutationen, keine Terraform Änderungen.
