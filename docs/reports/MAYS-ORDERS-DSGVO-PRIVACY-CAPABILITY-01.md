# MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01
## Wiederverwendbare Privacy Capability für Mays-Orders-AWS

**Datum:** 2026-10-10  
**Branch:** main  
**HEAD:** 0b689ee22273c172bfd8b11d9950428506042e7d  
**Status:** DESIGN + CONTRACT + TEST SPECIFICATION – READ ONLY  
**AWS Mutationen:** NONE

---

## 1. Architekturentscheidung

### Kontext
Mays-Orders-AWS ist eigenständige Auftragsverarbeitung. Privacy-Operationen müssen intern, autorisiert und projekt-isoliert verfügbar sein, ohne neue Benutzerverwaltung, ohne Compliance-Plattform, ohne Abhängigkeit zu Mays-RIS / Mays-Jobsearch.

### Entscheidung
Privacy Capability als intern aufrufbare Funktionen `privacy.inspect`, `privacy.export`, `privacy.erase` im Auftragsdatenbereich implementieren.  
Trennung Business vs. Privacy:

* **Business Operations:** `order.create`, `order.get`, `order.update_status`, `order.cancel`
* **Privacy Operations:** `privacy.inspect`, `privacy.export`, `privacy.erase`

Privacy Capability arbeitet unabhängig vom Order-Lifecycle. Ein `CANCELLED` Auftrag ist nicht automatisch gelöscht.

**ADR-Prinzipien**
* Fail closed
* Server-side authorisation, keine Client-Provided Authority
* Projekt-Kontext `project_name` + `environment` erzwingt Isolation
* Keine neue Auth Plattform; bestehende Cognito/IAM Mechanismen nutzen
* Keine neue AWS Ressourcen

---

## 2. Bestehendes Datenmodell

**Datenbank:** Single-Table DynamoDB `mays-orders`

Item Shape Order:
* `pk = ORDER#<orderId>`
* `sk = #ORDER`
* `orderId`
* `status`
* `customer: { name, email }`
* `items`
* `currency`
* `totalAmount`
* `createdAt`, `updatedAt`
* `version`
* `gsi1pk = LIST`, `gsi1sk = createdAt`

Indexe: Table PK/SK, GSI1 für Listing.

**Personenbezogene Attribute bestätigt:**
* `customer.name`
* `customer.email`

**Fehlend:**
* `subjectId`
* Objektbezogene Autorisierung
* TTL/Retention
* Delete API

Evidenz: `database/dynamodb-design.md`, `api/endpoints.md`

---

## 3. Subject Identification

### Analyse
Aktuell existiert keine stabile Personenreferenz. Zuordnung erfolgt nur über `customer.name` + `customer.email` innerhalb einer Order.

### Strategie
**Preferred: subjectId**

`subjectId` wird von aufrufender Anwendung bereitgestellt. Sie ist:
* Projekt-/Installationskontext-gebunden
* Enthält keine unnötigen personenbezogenen Informationen
* Eindeutig innerhalb eines Projekts

Mapping:
* Neue Orders: `subjectId` optional im Request, falls vorhanden persistieren
* Bestehende Orders ohne `subjectId`: keine automatische Migration, keine Zuordnung ausschließlich über Name/E-Mail
* Mehrere Orders pro Person möglich
* Gemeinsame Bestellungen / Dritte: explizite Dokumentation erforderlich

**Indexierung:**
* Empfehlung: GSI2 `subjectIndex` mit `gsi2pk = SUBJECT#<subjectId>` und `gsi2sk = ORDER#<orderId>` für effiziente Suche.  
  *Hinweis: Design-Option, keine Umsetzung im Rahmen dieser Spezifikation.*

**Einschränkungen**
* Keine automatische Rückschlussbildung von Name/E-Mail auf `subjectId`
* Widersprüchliche Zuordnungen -> Inspect markiert als unvollständig
* Fehlende `subjectId` -> Order nicht über Privacy Capability adressierbar

---

## 4. Privacy Capability Contract

**Aufrufkontext**
Alle Operationen erfordern:
* Aufruferidentität
* Projektkontext `project_name` / `environment`
* Berechtigung `privacy.*`
* Ziel `subjectId`
* Audit-Kontext

**Allgemeiner Response-Schema**

```json
{
  "operationId": "uuid",
  "capability": "privacy.inspect|privacy.export|privacy.erase",
  "status": "PREVIEW|PENDING|PROCESSING|COMPLETED|PARTIALLY_COMPLETED|BLOCKED|FAILED",
  "subjectId": "...",
  "project": "...",
  "affectedRecords": 0,
  "deletedRecords": 0,
  "retainedRecords": 0,
  "errors": [],
  "completedAt": "ISO-8601"
}
```

**Statuswerte**
* `PREVIEW` – Dry-Run Ergebnis
* `PENDING` – Eingereiht
* `PROCESSING` – Laufend
* `COMPLETED` – Erfolgreich, Umfang spezifiziert
* `PARTIALLY_COMPLETED` – Teilweise Erfolg
* `BLOCKED` – Retention / Freigabe fehlt
* `FAILED` – Fehler

---

## 5. Inspect Contract

**Funktion:** `privacy.inspect(subjectId, context)`

**Ziel:** Auffinden aller personenbezogenen Daten der Person im autorisierten Datenbestand.

**Eingabe**
* `subjectId` string, required
* `context`: aufrufer, projekt, berechtigung

**Ausgabe**
```json
{
  "operationId": "...",
  "capability": "privacy.inspect",
  "status": "COMPLETED",
  "subjectId": "...",
  "affectedRecords": 3,
  "dataCategories": ["order_master","customer_contact"],
  "references": [
    {"orderId":"ord_...","pk":"ORDER#...","sk":"#ORDER"},
    ...
  ],
  "deletionObstacles": [
    {"orderId":"...","reason":"retention_lock","until":"2027-01-01"}
  ],
  "incompleteMappings": [
    {"orderId":"...","reason":"missing_subjectId"}
  ],
  "technicalLimitations": [
    "SQS messages retain orderId for 4 days","CloudWatch Logs may contain PII"
  ]
}
```

**Regeln**
* Keine personenbezogenen Inhalte in Prüfprotokollen speichern
* Fail closed bei fehlender Berechtigung
* Keine Cross-Project Operationen

---

## 6. Export Contract

**Funktion:** `privacy.export(subjectId, context)`

**Ziel:** Strukturierte Bereitstellung zugeordneter personenbezogener Daten.

**Anforderungen**
* Maschinenlesbares JSON
* Definiertes Schema
* Vollständigkeitsprüfung
* Sichere Autorisierung
* Keine Daten anderer Personen
* Keine unkontrollierte Protokollierung
* Klare Fehlerbehandlung
* Keine unbeabsichtigte dauerhafte Kopie

**Schema Vorschlag**

```json
{
  "exportId": "...",
  "subjectId": "...",
  "generatedAt": "...",
  "data": [
    {
      "orderId": "...",
      "status": "...",
      "createdAt": "...",
      "customer": {"name":"...","email":"..."},
      "items": [...]
    }
  ],
  "metadata": {
    "recordCount": 3,
    "schemaVersion": "1.0"
  }
}
```

Unterscheidung Datenschutz:
* Auskunft / Export / Datenübertragbarkeit sind rechtlich unterschiedlich. Technisch wird Export als Datenbereitstellung umgesetzt. Rechtliche Einordnung bleibt Betreiberverantwortung.

**Fehler**
* 403 bei fehlender Berechtigung
* 404 wenn subjectId unbekannt
* 409 bei laufender Erasure Operation

---

## 7. Erase Contract

**Funktion:** `privacy.erase(subjectId, context, options)`

**Optionen**
* `dryRun`: bool
* `force`: bool – zur Freigabe von Retention-Blocks
* `retentionPolicyId`: string

**Ziel:** Kontrollierte Löschung personenbezogener Daten innerhalb autorisierten Bestands.

**Mechanismen**
* Vollständige Löschung: Order Item entfernen
* Partielle Löschung: `customer.name`/`email` maskieren, `items` behalten falls nicht personenbezogen
* Anonymisierung: Ersetzung durch Pseudonyme, falls Aufbewahrungspflicht besteht
* Zurückstellung wegen Aufbewahrungspflicht

**Dry-Run Vorschau**
```json
{
  "operationId":"...",
  "capability":"privacy.erase",
  "status":"PREVIEW",
  "subjectId":"...",
  "affectedRecords":5,
  "plannedOperations":[
    {"orderId":"...","action":"delete|mask|retain"}
  ],
  "nonDeletable":[
    {"orderId":"...","reason":"legal_hold","until":"2027-01-01"}
  ],
  "requiredApprovals":["legal_retention_override"]
}
```

**Ergebnis**
```json
{
  "operationId":"...",
  "status":"PARTIALLY_COMPLETED",
  "deletedRecords":3,
  "maskedRecords":1,
  "retainedRecords":1,
  "errors":[]
}
```

**Regeln**
* Berechtigungsprüfung vor Ausführung
* Eindeutige Personenreferenz via `subjectId`
* Wiederholbarkeit / Idempotenz
* Nachvollziehbares Ergebnis
* Kein Löschen wenn Regeln fehlen – Operation abbricht oder explizite Entscheidung verlangt

---

## 8. Authorization

Privacy-Operationen sind privilegierte interne Funktionen.

**Kontrollen**
* Aufruferidentität via bestehendem Cognito JWT oder IAM Role
* Berechtigung `privacy.*` auf Funktions-Ebene
* Projektkontext Erzwingung
* Zielperson `subjectId` muss zum Projekt gehören
* Audit Logging

**Verhindern**
* Fremdzugriffe
* Projektübergreifende Operationen
* Manipulierte `subjectId`
* Unberechtigte Exporte/Löschungen

**Hinweis:** Interne Funktionsaufrufe dürfen nicht allein des Vertrauens wegen akzeptiert werden.

---

## 9. Retention Handling

**Bereiche**
* ACTIVE DATA: DynamoDB Orders
* RETAINED DATA: DynamoDB PITR, Backups
* BACKUP DATA: DynamoDB PITR, S3 ggf.
* AUDIT DATA: CloudTrail, CloudWatch Logs
* TRANSIENT: SQS/DLQ

**DynamoDB**
* Aktuelle Daten können gelöscht/ maskiert werden
* PITR und Backups bleiben bestehen, Löschung erst nach Backup-Retention

**CloudWatch Logs**
* Retention konfigurierbar via `var.log_retention_days`
* Löschung nur auf Log-Group Ebene

**CloudTrail**
* Unbegrenzt, kein Lifecycle definiert
* Keine unmittelbare Bearbeitung durch Privacy Capability

**SQS/DLQ**
* Standard Retention 4 Tage
* Nachrichten werden nach Konsum gelöscht

**Ergebnis**
Keine vollständige Löschung bestätigen solange relevante Datenkopien nicht berücksichtigt.

---

## 10. Backup Considerations

DynamoDB PITR, Backups, CloudTrail S3, Terraform State.

Privacy-Operationen betreffen nur aktive Daten. Backup-Daten erfordern separate Verfahren:
* PITR Restore mit Filter -> nicht praktikabel
* Erwartetes Verhalten: Löschung aus aktiven Systemen, Backups behalten personenbezogene Daten bis Backup-Rotation

Dokumentation dieser Einschränkung im Inspect Ergebnis `technicalLimitations`.

---

## 11. Async Processing

Größe und Anzahl der Orders pro Person kann groß sein.

**Empfehlung**
* Privacy-Operationen asynchron über SQS ausführen
* Statusabfrage via `operationId`
* Idempotenz über `operationId` / Idempotency Key
* Retry-Verhalten, Dead Letter Queue
* Wiederaufnahme nach Fehler

Bestehende Infrastruktur bevorzugen. Keine neuen AWS Ressourcen im Design.

---

## 12. Error Handling

Standard Fehlerformat:
```json
{"error":{"code":"...","message":"...","details":{}}}
```

Codes:
* `UNAUTHORIZED` 401
* `FORBIDDEN` 403
* `VALIDATION_ERROR` 400
* `NOT_FOUND` 404
* `CONFLICT` 409
* `SERVICE_UNAVAILABLE` 503

Alle Security Failures fail closed.

---

## 13. Test Strategy

Tests ohne produktive personenbezogene Daten.

**Szenarien**
* Eine Person mit einer Bestellung
* Eine Person mit mehreren Bestellungen
* Zwei Personen mit gemeinsamen Daten
* Unbekannte `subjectId`
* Fehlende Berechtigung
* Projektübergreifender Zugriff
* Vollständiger Export
* Unvollständiger Export
* Dry-Run ohne Mutation
* Vollständige Löschung
* Partielle Löschung
* Gesetzlich aufzubewahrende Daten
* Wiederholter Löschaufruf
* Unterbrochene Löschung
* Gleichzeitige Änderungen
* Daten in SQS/DLQ
* Backup-Wiederherstellung

Acceptance Criteria: Fail closed, keine Datenlecks, Dry-Run verändert nichts, Audit Trail vorhanden.

---

## 14. Migration Considerations

* Bestehende Orders ohne `subjectId` bleiben unadressierbar
* Keine automatische Datenmigration
* Keine Rückschlussbildung Name/E-Mail -> `subjectId`
* Optionaler manueller Mapping Prozess außerhalb dieser Capability

---

## 15. Risks

* Fehlende `subjectId` -> Privacy Rechte technisch nicht umsetzbar
* Logging enthält PII -> Maskierung erforderlich
* Backup-Retention verhindert vollständige Löschung
* Objektbezogene Autorisierung fehlt im Basis-System
* Gemeinsame Bestellungen -> Dritte betroffen

---

## 16. Implementation Roadmap

**Phase 1 – Design & Contract**
* ✅ Archivierte Analyse MAYS-ORDERS-DSGVO-CONSOLIDATION-01
* ✅ Privacy Capability Contract

**Phase 2 – Data Model Extension**
* GSI für `subjectId` evaluieren
* Subject Mapping Regeln definieren

**Phase 3 – Core Functions**
* `privacy.inspect` implementieren
* `privacy.export` implementieren
* `privacy.erase` mit Dry-Run

**Phase 4 – Security & Audit**
* Autorisierung, Audit Logging
* Test Suite

**Phase 5 – Retention & Backup**
* Dokumentation Backup-Limitierungen
* Installer Optionen für Retention

Kein Start ohne Freigabe.

---

## 17. Acceptance Criteria

- [x] Governance geprüft
- [x] Bestehendes Datenmodell analysiert
- [x] Subject-ID Strategie definiert
- [x] Inspect spezifiziert
- [x] Export spezifiziert
- [x] Erase spezifiziert
- [x] Autorisierung definiert
- [x] Retention berücksichtigt
- [x] Backups berücksichtigt
- [x] Dry-Run spezifiziert
- [x] Fehlerbehandlung definiert
- [x] Teststrategie erstellt
- [x] Migration berücksichtigt
- [x] Implementierungsroadmap erstellt
- [x] Auditlog-Konformität geprüft
- [x] Keine Runtime-Änderungen
- [x] Keine AWS-Mutationen
- [ ] Git-Checkpoint abgeschlossen

---

## 18. Final Checkpoint

CHECKPOINT: MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01

STATUS: YELLOW

BRANCH: main

HEAD: 0b689ee22273c172bfd8b11d9950428506042e7d

ARCHITECTURE: DESIGN COMPLETE

SUBJECT IDENTIFICATION: subjectId STRATEGY DEFINED

INSPECT: SPECIFIED

EXPORT: SPECIFIED

ERASE: SPECIFIED

AUTHORIZATION: DEFINED

RETENTION: DOCUMENTED

BACKUPS: DOCUMENTED

TEST STRATEGY: DEFINED

ROADMAP: DEFINED

AUDITLOG: COMPLIANT

AWS MUTATIONS: NONE

FILES CHANGED: docs/reports/MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01.md

GIT COMMIT: pending

PUSH: pending

NEXT STEP: Await orchestration review, no implementation.

---

*Dokument erstellt im Design + Contract + Test Specification Modus. Keine Implementierung autorisiert.*
