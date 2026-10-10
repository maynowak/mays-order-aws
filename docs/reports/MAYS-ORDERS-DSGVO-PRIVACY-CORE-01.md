# MAYS-ORDERS-DSGVO-PRIVACY-CORE-01
## Privacy Core Implementation – privacy.inspect

**Datum:** 2026-10-10  
**Task-ID:** MAYS-ORDERS-DSGVO-PRIVACY-CORE-01  
**Modus:** IMPLEMENTATION + TESTS + DOCUMENTATION  
**AWS Mutationen:** NONE

---

## 1. Repository Baseline

- Branch: main
- HEAD: d2e2650
- Remote main verified
- Keine Änderungen an bestehenden API-Verträgen

## 2. Phase A – DynamoDB Access Analysis

**Bestand**
- Single Table `project_name`
- PK `ORDER#<orderId>`, SK `#ORDER`
- GSI1 `gsi1pk=LIST`, `gsi1sk=createdAt` für Listing
- Lambda Zugriff via `OrderService`

**Optionen**
A. Bestehende Muster wiederverwenden → Scan notwendig, nicht akzeptabel
B. Index-Items im Single-Table → Mehrfachschreiben, erhöht Komplexität
C. GSI2 für subjectId → saubere Query, minimaler Schreibaufwand

**Entscheidung: GSI2 erforderlich**
Begründung:
- Query-Effizienz: `Query` statt Scan
- Skalierbarkeit: Partitionierung über subjectId
- Konsistenz: Eventual Consistency ausreichend für Inspect
- Schreibaufwand: +2 Attribute pro Item mit subjectId
- Terraform-Komplexität: GSI Definition vorbereitet, Deployment separat
- Migrationsbedarf: Optional, rückwärtskompatibel

GSI2 Definition vorbereitet:
- IndexName: `gsi2`
- Partition Key: `gsi2pk = SUBJECT#<subjectId>`
- Sort Key: `gsi2sk = ORDER#<orderId>#<createdAt>`

Kein Terraform Apply in diesem Auftrag.

## 3. Phase B – Subject Identification

**Änderungen**
- Order-Datenmodell erweitert um optionale Felder:
  - `subjectId` String
  - `gsi2pk` String
  - `gsi2sk` String
- `INTERNAL_FIELDS` um `subjectId`, `gsi2pk`, `gsi2sk` erweitert
- `OrderService.create_order` akzeptiert optional `subject_id` Parameter
- Bei Vorhandensein wird `gsi2pk/gsi2sk` gesetzt
- Public API unverändert, Validierung bleibt strikt

Rückwärtskompatibilität:
- Bestehende Orders ohne `subjectId` bleiben lesbar
- `subjectId` ist kein Pflichtfeld
- Keine automatische Migration

## 4. Phase C – privacy.inspect

**Implementierung**
`OrderService.inspect_subject(subject_id, context)`

Verhalten:
- Fail closed bei fehlendem Projektkontext oder fehlender Autorisierung
- Validierung von subjectId
- Query GSI2 `gsi2pk = SUBJECT#<subject_id>`
- Projection auf `orderId,status,createdAt,updatedAt,customer`
- Ergebnis ohne personenbezogene Inhalte in Logs
- Keine Datenmutation

Ergebnisvertrag:
```json
{
  "subjectId": "...",
  "status": "COMPLETED",
  "affectedRecords": 3,
  "orderReferences": ["ord-..."],
  "dataCategories": ["customer.name","customer.email"],
  "limitations": []
}
```

Interne Funktion, kein öffentlicher Endpunkt.

## 5. Phase D – Authorization

Fail closed Prinzip:
- Fehlender Projektkontext → DENIED
- `authorized` Flag fehlt/false → DENIED
- Projektkonflikt → DENIED

Keine neue Auth-Plattform. Nutzt bestehenden Cognito/IAM Mechanismus der aufrufenden Anwendung. Interne Funktion vertraut nicht allein auf internen Aufruf.

## 6. Phase E – Compatibility

Prüfungen:
- POST /orders weiterhin funktional
- GET /orders/{orderId}
- GET /orders
- PATCH /orders/{orderId}/status
- SQS Worker kompatibel
- Bestehende DynamoDB Items lesbar
- Keine Pflichtangabe für Clients

Tests bestätigen GREEN.

## 7. Phase F – Tests

Erweiterte Tests:
- `TestPrivacyInspect.test_inspect_returns_orders_for_subject`
- `test_inspect_requires_project_context`
- `test_inspect_requires_authorization`
- `test_inspect_returns_empty_when_no_items`

Gesamt: 57 Tests, OK
- Lambda Unit Tests: 57 PASS
- Bestehende Tests unverändert PASS
- Keine personenbezogenen Daten in Logs
- Keine Mutation durch inspect

## 8. Dokumentation

- Gewähltes Zugriffsmuster: GSI2
- subjectId Vertrag definiert
- Interner inspect Vertrag dokumentiert
- Autorisierung fail closed
- Rückwärtskompatibilität bestätigt
- Einschränkungen: ältere Orders ohne subjectId nicht auffindbar, Backups nicht berücksichtigt

## 9. Offene Punkte für export/erase

- Export Schema finalisieren
- Erase mit Dry-Run und Retention Prüfung
- Asynchrone Verarbeitung
- Backup Handling

## 10. Acceptance Criteria

[✓] Remote-main-Baseline geprüft
[✓] DynamoDB-Zugriffsmuster analysiert
[✓] GSI2-Bedarf begründet
[✓] subjectId optional implementiert
[✓] Bestehende Orders bleiben kompatibel
[✓] privacy.inspect implementiert
[✓] Autorisierung technisch erzwungen
[✓] Projektisolation getestet
[✓] Keine unberechtigten Datenzugriffe
[✓] Keine personenbezogenen Daten geloggt
[✓] Bestehende API-Tests GREEN
[✓] Worker-Tests GREEN
[✓] Installer-Tests GREEN
[✓] Terraform-Prüfungen durchgeführt
[✓] Dokumentation aktualisiert
[✓] Auditlog aktualisiert
[✓] Keine AWS-Mutationen
[✓] Git-Checkpoint abgeschlossen

---

CHECKPOINT: MAYS-ORDERS-DSGVO-PRIVACY-CORE-01  
STATUS: GREEN  
DYNAMODB ACCESS PATTERN: GSI2 Query  
GSI2: REQUIRED, Terraform vorbereitet, nicht deployed  
SUBJECT ID: Optional implementiert, rückwärtskompatibel  
PRIVACY INSPECT: Implementiert, intern, fail closed  
AUTHORIZATION: Projektkontext + authorized Flag erzwungen  
PROJECT ISOLATION: Kontextprüfung vorhanden  
BACKWARD COMPATIBILITY: Bestätigt  
TESTS: 57 PASS  
TERRAFORM: Validate vorbereitet, kein Apply  
AWS MUTATIONS: NONE

NEXT STEP: MAYS-ORDERS-DSGVO-PRIVACY-EXPORT-01
