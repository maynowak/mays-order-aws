# MAYS-ORDERS-PRIVACY-AWS-TEST-PREFLIGHT-01

## Baseline
- Branch: main
- Remote HEAD: 550506d19c43bb3f99d036a271bae1fcd7a34a2e
- Local HEAD: 550506d19c43bb3f99d036a271bae1fcd7a34a2e
- Working Tree: clean except uncommitted changes in terraform/backend.tf, terraform/main.tf, terraform/modules/cognito_backup_automation/*
  → Uncommitted changes preserved per governance

## Test Project Discovery
- Project isolation via `var.project_name` default `mays-orders`
- Region: `eu-central-1`
- Terraform Workspace: `default`
- DynamoDB table name = `var.project_name`
- State Isolation: S3 backend + DynamoDB lock, workspace per project
- Installer supports project_name, environment, workspace isolation

**Fazit Testprojekt**
- A. Existierendes Testprojekt: Nicht zweifelsfrei nachgewiesen
- B. Ohne Produktionsrisiko nutzbar: NOT VERIFIED – Isolation nicht verifiziert
- C. Neues isoliertes Testprojekt nötig: Empfehlung JA
- D. Wiederverwendbare Installer-Funktionen: `plan`, `validate`, `state` vorhanden

## Terraform Preflight
`terraform/modules/dynamodb/main.tf`
- GSI1 unverändert: ✓
- GSI2 definiert: ✓
  - IndexName: gsi2
  - Partition Key: gsi2pk String
  - Sort Key: gsi2sk String
  - projection_type: INCLUDE
  - non_key_attributes: orderId, subjectId, version, createdAt, status, updatedAt, customer, totalAmount, currency
- Primärschlüssel pk/sk automatisch verfügbar: nach DynamoDB-Regeln ja
- Keine unerwarteten Tabellenänderungen im Modul

Terraform Plan:
- Ausführung BLOCKED – Isolation nicht zweifelsfrei nachgewiesen, Backend-Locking, uncommitted Änderungen
- Keine State-Mutation

## IAM Preflight
`terraform/modules/iam/main.tf`
- Aktuelle Policy erlaubt:
  dynamodb:PutItem, GetItem, UpdateItem, Query
  Ressourcen: `var.dynamodb_table_arn`, `var.dynamodb_gsi1_arn`
- GSI2 ARN nicht in Ressourcenliste enthalten
- `arn:aws:dynamodb:*:*:table/<table>/index/gsi2` fehlt → Query auf GSI2 aktuell nicht autorisiert

**Ergebnis IAM:** BLOCKED für GSI2

## GSI2 Deployment Readiness
- Konfiguration vorhanden, Deployment nicht erfolgt
- Bei `terraform apply` zu erwarten:
  - Neues GSI2 wird erstellt
  - Index Backfill über alle bestehenden Items
  - On-Demand Billing → keine Kapazitätsänderung nötig
  - Kosten: zusätzliche Read/Write Einheiten proportional zu Datenmenge
- Ressourcen:
  - CREATE: global_secondary_index gsi2
  - CHANGE: keine
  - REPLACE: keine
- Status ACTIVE muss vor Tests erreicht sein

## Privacy Test Scenarios – geplant, nicht ausgeführt
A: Order mit subjectId erstellen
B: GSI2 Query durchführen
C: Mehrere Orders derselben subjectId prüfen
D: Isolation unterschiedlicher subjectIds prüfen
E: inspect_subject ausführen
F: export_subject ausführen
G: erase_subject PREVIEW ausführen
H: Fehlende Privacy-Berechtigung prüfen
I: Fehlenden/falschen internen Token prüfen
J: GSI2 Pagination prüfen

Keine ERAS E/ANONYMIZE Ausführung.

## Security Review
- PRIVACY_INTERNAL_SECRET erforderlich, Fail-closed implementiert
- ORDERS_PROJECT_NAME Prüfung vorhanden
- Projektisolierung über project_name + Tags
- internal_token Herkunft über Context-Dict, nicht technisch erzwungen → WARNING
- Keine Secrets in Logs/Reports
- Keine neuen öffentlichen Endpunkte

## Cost Review
- GSI2 On-Demand: geringe laufende Kosten, Backfill einmalig
- Testdaten synthetisch, minimal
- Lambda Aufrufe im Free Tier Rahmen
- Keine kostenverursachenden Änderungen durchgeführt

## Review Gate
A. Projektisolierung nachgewiesen? NOT VERIFIED
B. Terraform-State korrekt? WARNING – uncommitted Änderungen
C. GSI2-Konfiguration korrekt? PASS
D. Keine Resource Replacement? PASS
E. IAM ausreichend? BLOCKED
F. Testfälle vorbereitet? PASS
G. Keine produktiven Daten? NOT VERIFIED
H. Keine AWS-Mutationen? PASS
I. Kosten transparent? WARNING
J. Deployment sicher planbar? BLOCKED

**Overall Klassifikation:** BLOCKED

## Empfehlung
- Isoliertes Testprojekt definieren, Workspace und State klar trennen
- IAM Policy um GSI2 ARN erweitern
- Terraform Plan erst nach Isolation verifizieren
- Erst nach GSI2 ACTIVE und IAM Fix Integrationstests ausführen

## Remaining Blockers
1. Projektisolierung nicht zweifelsfrei nachgewiesen
2. IAM Policy fehlt GSI2 ARN
3. GSI2 noch nicht deployed
4. Uncommitted Terraform Änderungen

Basis für nächste Schritte: menschliche Freigabe für Testprojekt und IAM Anpassung.
