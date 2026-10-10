# MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01
## Privacy Capability Design – Mays-Orders-AWS

**Datum:** 2026-10-10  
**Task-ID:** MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01  
**Modus:** DESIGN + CONTRACT + TEST SPECIFICATION – READ ONLY  
**AWS Mutationen:** NONE

---

## 1. Architekturentscheidung

### Prinzipien
* Trennung Business vs Privacy Operations
* Interne, privilegierte Funktionen, keine öffentliche API
* Keine neue Authentifizierungsplattform
* Wiederverwendbar pro Installation, projektbezogen
* Keine Abhängigkeit von Mays-RIS / Mays-Jobsearch
* Bestehende Infrastruktur nutzen: DynamoDB, Lambda, SQS, Cognito/IAM

Privacy Capability ist eine interne Schicht über bestehendem Order-Layer:
- Business: `order.create / get / update_status / cancel`
- Privacy: `privacy.inspect / export / erase [rectify / restrict]`

CANCELLED ≠ gelöscht. Privacy-Operationen funktionieren unabhängig vom Order-Lifecycle.

---

## 2. Bestehendes Datenmodell

**DynamoDB Single Table** `project_name`
- PK: `ORDER#<orderId>`
- SK: `#ORDER`
- Attribute: `orderId`, `status`, `customer.{name,email}`, `items[]`, `currency`, `totalAmount`, `createdAt`, `updatedAt`, `version`, `gsi1pk=LIST`, `gsi1sk=createdAt`

**Personenbezogene Daten**
- `customer.name`
- `customer.email`
- Indirekt: `orderId` als Referenz in SQS Nachrichten, CloudWatch Logs

**Fehlend**
- `subjectId` / persistente Personenreferenz
- Index für Suche nach Person
- Pseudonymisierung

Quelle: `database/dynamodb-design.md`, `api/endpoints.md`

---

## 3. Subject Identification

### Problemstellung
Aktuell keine stabile Personen-ID. Zuordnung nur über `customer.name` + `customer.email`. Name ist nicht eindeutig, E-Mail kann sich ändern.

### Vorgeschlagene Strategie
**subjectId** als stabile, projektinterne Referenz.

Eigenschaften:
- Wird von aufrufender Anwendung bereitgestellt
- Enthält keine personenbezogenen Informationen
- Eindeutig innerhalb Projekt-/Installationskontext
- Immutabel nach Vergabe
- Technisch: UUID v4 oder deterministischer Hash über externe IdP-Subject

### Datenmodell-Ergänzung
Neues Attribut im Order-Item:
- `subjectId` String, optional
- GSI2 für personbezogene Suche:
  - GSI2PK = `SUBJECT#<subjectId>`
  - GSI2SK = `ORDER#<orderId>#<createdAt>`

Vorteile:
- Effiziente Suche aller Orders einer Person
- Trennung von Kontakt-Daten und technischer Referenz
- Migration bestehender Daten möglich, nicht zwingend für Grundfunktion

### Umgang mit bestehenden Daten
- Orders ohne `subjectId` bleiben auffindbar über Fallback-Mapping `customer.email` → nur für Inspect/Export mit expliziter Freigabe
- Keine automatische Migration in diesem Auftrag
- Unvollständige Zuordnungen werden im Inspect-Ergebnis gemeldet

### Risiken
- Gemeinsame Bestellungen: mehrere Personen beteiligt → `subjectId` Array oder getrennte Items
- Dritte Personen in `customer.name` → nur über Freigabe
- Duplikate bei fehlender subjectId

---

## 4. Privacy Capability Contract

Allgemeines Ergebnisformat:
```json
{
  "operationId": "uuid",
  "capability": "privacy.inspect|export|erase",
  "status": "PREVIEW|PENDING|PROCESSING|COMPLETED|PARTIALLY_COMPLETED|BLOCKED|FAILED",
  "subjectId": "string",
  "project": "string",
  "requestedBy": "principal",
  "authorizedBy": "policy",
  "affectedRecords": 0,
  "details": {},
  "errors": [],
  "completedAt": "ISO8601"
}
```

Statuswerte eindeutig definiert:
- PREVIEW: Dry-Run
- PENDING: Wartet auf Freigabe
- PROCESSING: Laufend
- COMPLETED: Erfolg ohne Einschränkung
- PARTIALLY_COMPLETED: Teilweise ausgeführt, Rest blockiert
- BLOCKED: Aufbewahrungspflicht / fehlende Freigabe
- FAILED: Fehler

---

## 5. Privacy.inspect Contract

**Signatur**
`privacy.inspect(subjectId, context)`

**Eingabe**
- `subjectId`: String
- `context`: `{ project, callerPrincipal, authorizationToken, includeMetadata }`

**Ausgabe**
- `affectedOrders`: Anzahl
- `dataCategories`: [`order_master`, `customer_contact`, `items`]
- `references`: Liste `{ orderId, status, createdAt }`
- `missingSubjectId`: Anzahl Orders ohne Zuordnung
- `deletionObstacles`: [`retention_lock`, `legal_hold`, `backup_pending`]
- `technicalLimitations`: Hinweis auf SQS/Logs/Backups

**Prüfungen**
- Autorisierung prüfen
- Existenz subjectId prüfen
- GSI2 Query falls vorhanden, sonst Fallback Scan mit Freigabe
- Keine personenbezogenen Inhalte in Logs speichern

**Sicherheit**
Nur interne Aufrufe, Audit-Trail Pflicht.

---

## 6. Privacy.export Contract

**Signatur**
`privacy.export(subjectId, context)`

**Ausgabeformat**
JSON, definiertes Schema:
```json
{
  "exportId": "...",
  "subjectId": "...",
  "project": "...",
  "exportedAt": "...",
  "orders": [
    {
      "orderId": "...",
      "status": "...",
      "createdAt": "...",
      "customer": { "name": "...", "email": "..." },
      "items": [...]
    }
  ],
  "metadata": { "recordCount": 0, "schemaVersion": "1.0" }
}
```

**Anforderungen**
- Maschinenlesbar, vollständige Daten
- Keine Daten anderer Personen
- Keine Protokollierung personenbezogener Inhalte
- Sichere Autorisierung
- Klare Fehlerbehandlung
- Keine dauerhafte Kopie

Unterscheidung:
- Auskunft: menschenlesbar, vollständig
- Export: strukturiert
- Datenübertragbarkeit: strukturiert + standardisiert

---

## 7. Privacy.erase Contract

**Signatur**
`privacy.erase(subjectId, context, options)`

Options:
- `dryRun`: boolean
- `mode`: `delete` | `anonymize` | `pseudonymize`
- `retentionPolicy`: Betreiberdefinierte Regeln
- `force`: boolean

**Ablauf**
1. Autorisierung prüfen
2. Betroffene Datensätze ermitteln via GSI2 / Fallback
3. Dry-Run → Vorschau ohne Mutation
4. Aufbewahrungspflichten prüfen
5. Ausführung:
   - DynamoDB: Update/Delete Items
   - SQS/DLQ: Nachrichten identifizieren, keine Löschung garantiert
   - Logs/CloudTrail: getrennte Verfahren
6. Ergebnisbericht

**Unterschiede**
- Vollständige Löschung: Item entfernen
- Partielle Löschung: `customer` Felder leeren, `subjectId` entfernen
- Anonymisierung: nicht-reversibel ersetzen
- Aufschub: Datensatz markieren `deletionPending` bis Retention abgelaufen

**Wichtig**
Capability entscheidet nicht über Recht. Sie wendet Betreiber-Regeln an und bricht bei fehlenden Freigaben sicher ab.

---

## 8. Dry-Run

Jede destruktive Operation unterstützt `dryRun=true`.

Vorschau enthält:
- Anzahl betroffener Datensätze
- Vorgesehene Operationen pro Datensatz
- Nicht löschbare Datensätze mit Grund
- Erforderliche Freigaben
- Erkannte Risiken

Kein Schreibzugriff bei Dry-Run.

Schutz gegen Änderungen zwischen Dry-Run und Ausführung via `operationId` + Konsistenzprüfung.

---

## 9. Authorization

Privacy-Operationen sind privilegiert.

Kontrollen:
- Aufruferidentität via Cognito/IAM Principal
- Berechtigung: dedizierte Policy `privacy:*`
- Projektkontext: `project_name` aus Kontext, keine Cross-Project Operationen
- Zielperson: `subjectId` muss im selben Projekt liegen
- Audit Kontext: Aufruf erfassen, kein personenbezogener Inhalt in Logs

Verhindern:
- Fremdzugriffe
- Projektübergreifende Operationen
- Unberechtigte Exporte/Löschungen
- Manipulierte subjectIds

Interne Funktionsaufrufe sind nicht automatisch vertrauenswürdig.

---

## 10. Retention Handling

Berücksichtigt werden:
- DynamoDB Active Data
- SQS / DLQ
- CloudWatch Logs
- CloudTrail
- S3
- PITR / Backups

Kategorien:
- ACTIVE DATA: unmittelbar manipulierbar
- RETAINED DATA: Lifecycle gesteuert
- BACKUP DATA: gesondertes Verfahren
- AUDIT DATA: unveränderlich

Privacy-Operationen können ACTIVE DATA bearbeiten. BACKUP DATA erfordert separaten Prozess. Keine vollständige Löschung bestätigen, solange Backups betroffen sind.

---

## 11. Backup Considerations

DynamoDB PITR, On-Demand Backups, Cognito Backup.

Löschung aus aktiven Daten ≠ Löschung aus Backups.

Empfehlung:
- Backups mit Retention Policy
- Löschanfrage in Backups als Marker, keine sofortige physische Löschung
- Dokumentation der Restrisiken

---

## 12. Async Processing

Privacy-Operationen können asynchron laufen.

Gründe:
- Viele Orders pro Person
- Retry-Verhalten
- Idempotenz
- Statusabfrage

Nutze bestehende SQS Infrastruktur.

Vorschlag:
- `privacy.erase` startet Job, gibt `operationId` zurück
- Job verarbeitet via Worker, schreibt Ergebnis in DynamoDB Job Table
- Statusabfrage via `operationId`

Keine neuen AWS Ressourcen.

---

## 13. Error Handling

Fehlerkategorien:
- AUTHORIZATION_FAILED
- SUBJECT_NOT_FOUND
- PARTIAL_FAILURE
- RETENTION_BLOCKED
- BACKUP_CONFLICT
- INTERNAL_ERROR

Jeder Fehler liefert maschinenlesbaren Code, human lesbare Nachricht, keine personenbezogenen Daten in Fehlermeldungen.

---

## 14. Test Strategy

Testfälle ohne produktive Daten:
- Eine Person mit einer Bestellung
- Eine Person mit mehreren Bestellungen
- Zwei Personen mit gemeinsamen Daten
- Unbekannte subjectId
- Fehlende Berechtigung
- Projektübergreifender Zugriff
- Vollständiger / unvollständiger Export
- Dry-Run ohne Mutation
- Vollständige Löschung
- Partielle Löschung / Anonymisierung
- Gesetzlich aufzubewahrende Daten
- Wiederholter Löschaufruf – Idempotenz
- Unterbrochene Löschung – Wiederaufnahme
- Gleichzeitige Änderungen
- Daten in SQS/DLQ
- Backup-Wiederherstellung

---

## 15. Migration Considerations

Bestehende Orders ohne `subjectId`:
- Fallback über E-Mail Hash nur mit Freigabe
- Migration ist optional und Betreiberentscheidung
- Keine automatische Migration in diesem Auftrag
- Dokumentation der Lücke im Inspect Ergebnis

---

## 16. Risks

- Fehlende subjectId führt zu unvollständiger Erfassung
- Log-Retention kann PII länger speichern als Order-Daten
- Backups verhindern sofortige vollständige Löschung
- Gemeinsame Bestellungen erfordern Mehrfachzuordnung
- Falsche subjectId Zuordnung → Löschung falscher Person

---

## 17. Implementation Roadmap

1. Subject Identification Schema definieren
2. Privacy Capability Contracts spezifizieren
3. Autorisierung Modell definieren
4. Inspect / Export / Erase Schnittstellen designen
5. Retention & Backup Handling definieren
6. Test Spezifikation finalisieren
7. Dokumentation konsolidieren
8. Review & Freigabe

Keine Implementierung in diesem Auftrag.

---

## 18. Acceptance Criteria

[✓] Governance geprüft
[✓] Datenmodell analysiert
[✓] Subject-ID Strategie definiert
[✓] Inspect spezifiziert
[✓] Export spezifiziert
[✓] Erase spezifiziert
[✓] Autorisierung definiert
[✓] Retention berücksichtigt
[✓] Backups berücksichtigt
[✓] Dry-Run spezifiziert
[✓] Fehlerbehandlung definiert
[✓] Teststrategie erstellt
[✓] Migration berücksichtigt
[✓] Implementierungsroadmap erstellt
[✓] Auditlog-Konformität geprüft
[✓] Keine Runtime-Änderungen
[✓] Keine AWS-Mutationen

---

CHECKPOINT: MAYS-ORDERS-DSGVO-PRIVACY-CAPABILITY-01  
STATUS: GREEN – Design abgeschlossen, Implementierung offen  
AWS MUTATIONS: NONE  
BRANCH: main  
HEAD: 874d3f0 → Commit pending

NEXT STEP: Git Checkpoint
