# MO-ORDER-DATA-MIGRATION-P3-PLANNING-01

**P3-Architektur und Implementierungsplan — Order-Daten, Backup, Migration, Cutover**

**Datum:** 2026-11-03
**Branch:** `feature/mo-builder-upgrade-p2` · **HEAD:** `f567669` · **Working Tree:** CLEAN
**Modus:** ausschließlich Analyse und Planung; keine AWS-/Terraform-Operation, keine Implementierung, kein Push

---

## 1. Executive Summary

P0A–P2 schützen **Infrastruktur** (keine kritischen DELETE/REPLACE, Versions-/State-/Drift-
Bindung, Upgrade-Readiness, Builder-Dateien). Für **Order-Daten** fehlt bisher jede
verifizierte Sicherung: PITR ist im Terraform aktiviert, aber **nie getestet**; es gibt
**kein On-Demand-Backup, kein Restore-Verfahren, keine Migrationstooling, keinen
Erasure-Nachweis**. Genau diese Lücken adressiert P3.

**Kernentscheidung:** P3 wird **kein allgemeines Terraform-Rollback**. Geschützt wird die
Bestellung (Daten), getrennt von der Infrastruktur:

```text
Backup → ggf. neue Tabelle → kontrollierte Migration → Validierung → Cutover
```

**Wichtigster Befund:** Ein Restore aus Backup/PITR kann **bereits gelöschte/anonymisierte
personenbezogene Daten wiederherstellen**. Es existiert **kein Erasure-Ledger**, mit dem sich
das nachweisen/verhindern ließe. Das ist eine fachlich-rechtliche Entscheidung (P3E), keine
rein technische.

**Status:** `P3 PLANNING COMPLETE — ORDER DATA MIGRATION ARCHITECTURE REVIEWED`

---

## 2. Ausgangsstand (verifiziert)

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/mo-builder-upgrade-p2` |
| HEAD | `f567669` |
| Working Tree | CLEAN |
| Builder-Tests | 128 PASS |
| Installer-Tests | 422 PASS |
| P0A–P2 | lokal implementiert, nicht nach `main` integriert |
| Auditlog | gelesen; Regeln gelten auch für Analyse-/Explore-Agenten |

---

## 3. Belegte Architektur

### 3.1 DynamoDB / Datenmodell

| Aspekt | Befund | Evidence |
|---|---|---|
| Tabelle | Single-Table, Name = `project_name` | `terraform/modules/dynamodb/main.tf:11-12` |
| Keys | `pk` (S), `sk` (S) | `main.tf:13-24` |
| Order-Item | `pk = "ord_" + orderId`, `sk = "#ORDER"` | `lambda/src/order_service.py:201-205`, `order_types.py:16,22` |
| **Doc/Impl-Diskrepanz** | Design-Doc nennt `ORDER#<orderId>`; Implementierung nutzt `ord_ord_<hex>` (doppeltes Präfix) | `database/dynamodb-design.md:31` vs. Code |
| GSI1 | `gsi1pk = "LIST"`, `gsi1sk = createdAt`, INCLUDE (Listen) | `terraform/modules/dynamodb/main.tf:59-73`; `order_service.py:216-217` |
| GSI2 | `gsi2pk = "SUBJECT#<sub>"`, `gsi2sk = "ord_<id>#<createdAt>"`, INCLUDE (Owner-Zugriff) | `main.tf:75-92`; `order_service.py:225-226` |
| GSI3 | Claim-Index `gsi3pk/gsi3sk`, KEYS_ONLY | `main.tf:94-110` |
| PITR | **enabled** (`point_in_time_recovery`) | `main.tf:108-110` |
| Streams | **nicht aktiviert** | Modul enthält keinen `stream_enabled` |
| TTL | **nicht konfiguriert** | Modul enthält kein `ttl` |
| Verschlüsselung | AWS-owned (keine `server_side_encryption`-Konfiguration, kein KMS) | Modul |
| On-Demand-Backup | **nicht vorhanden** (keine `aws_dynamodb_table_backup`/AWS-Backup-Plan) | `grep` in `terraform/` |
| Restore-Tooling | **nicht vorhanden** | `scripts/` enthält nur Seed-Tools |

### 3.2 Schreibpfade / Lifecycle

| Aspekt | Befund | Evidence |
|---|---|---|
| API-Schreibpfad | `POST/PATCH` → Lambda → `PutItem`/`UpdateItem` (conditional, `version`) | `order_service.py:201-430` |
| Worker | SQS → Claim/Lease, `UpdateItem`, Completion | `lambda/src/sqs_handler.py` |
| Statusmodell | `PENDING→CONFIRMED→PROCESSING→SHIPPED→DELIVERED`, `CANCELLED` nur aus PENDING/CONFIRMED | `order-lifecycle/state-machine.md:19-40` |
| Tabellenbindung | `ORDERS_TABLE`-Env aus Terraform | `terraform/modules/lambda/main.tf:18`, `modules/sqs-worker/main.tf:12` |
| Dual-Write/CDC | **nicht vorhanden** | kein Streams, kein zweiter Schreibpfad |

### 3.3 Mandanten-/Partnerisolation

| Aspekt | Befund | Evidence |
|---|---|---|
| Consumer | `consumerId = cognito:<issuer>#<client>`; GET/PATCH prüfen Owner **und** Consumer | `order_service.py:139-166`; `api/endpoints.md:78-95` |
| Liste | GSI2 + Consumer-Filter in der Anwendung | `order_service.py:290-320` |
| Legacy | fehlende Identität → 404 (fail-closed) | `api/endpoints.md:95-97` |
| RIS-Direktschreiben | dokumentiert, ohne `subjectId`, abweichendes `pk`-Muster | `architecture/architecture-decisions.md:123-131` |

### 3.4 IAM / Verschlüsselung / Audit

| Aspekt | Befund | Evidence |
|---|---|---|
| Handler-Rolle | `Put/Get/Update/Delete/Query` auf Tabelle + GSIs; **kein** `Scan/BatchWrite/CreateTable` | `terraform/modules/iam/main.tf:31-50` |
| Worker-Rolle | `Get/Update` | `terraform/modules/sqs-worker/iam.tf:18-24` |
| Migration müsste | `Scan/BatchWriteItem/CreateTable/Backup/Restore` nutzen → **separate Rolle**, nicht die Lambda-Rolle | Gap |
| Verschlüsselung | AWS-owned; **kein KMS** | ADR-008-Kontext |
| Audit | CloudTrail Management Events; DynamoDB-Datenzugriff nicht auditiert | `docs/security/cloudtrail-design.md` (Management) |

### 3.5 DSGVO / Löschung / Retention

| Aspekt | Befund | Evidence |
|---|---|---|
| Erasure | `erase_subject` mit PREVIEW/EXECUTE, Policies `ERASE`/`ANONYMIZE`/`RETAIN`, Consumer-Scope, Conditional-Check (idempotent) | `order_service.py:579-770` |
| Anonymisierung | `customer` → `ANONYMIZED`, `subjectId`/GSI2/GSI3/Ergebnisse entfernt | `order_service.py:730-755` |
| **Erasure-Ledger** | **fehlt** — kein Nachweis, welche Subjects gelöscht wurden | Gap |
| Retention | **keine** Retention-Felder/TTL/Fristen; ADR-008 nur PROPOSED | `architecture/architecture-decisions.md:111` |
| Backups/PITR | enthalten PII; Restore kann gelöschte Daten zurückbringen | P3E-Risiko |
| Privacy-Auth | `PRIVACY_INTERNAL_SECRET` fehlt in Terraform → Laufzeit fail-closed | `order_service.py:159-166` |

### 3.6 Backup / Recovery (Bestand)

| Aspekt | Befund | Evidence |
|---|---|---|
| PITR | im Code aktiviert (seit RC4), aber **nie verifiziert/restored** | `main.tf:108-110` |
| On-Demand-Backup | fehlt | — |
| AWS-Backup-Plan | fehlt | — |
| Restore-Doku | BACKUP-02 ist **Design-only** (2026-09-26), Aussagen zu PITR veraltet | `docs/reports/BACKUP-02-RECOVERY-STRATEGY.md:54-56` |
| Backup-Retention | keine Regel für Order-Backups | — |

### 3.7 Installer-Gates (P0A–P1)

| Gate | Befund | Evidence |
|---|---|---|
| P0A | `aws_dynamodb_table` DELETE/REPLACE = **BLOCK** | `installer/core/upgrade_safety.py` |
| P0C | Drift/No-op + Baseline-Gate | `installer/core/drift.py`, `state_baseline.py` |
| P1 | Kompatibilität/Readiness; `--accept-upgrade-review` nur für REVIEW | `installer/core/compatibility.py`, `upgrade_readiness.py` |
| **Backup-Nachweis** | **kein Gate/Feld** | Gap |
| **Migrationspflicht** | **kein Feld** (nur CRITICAL-Kategorie) | Gap |
| **Cutover-Freigabe** | **kein Konzept** | Gap |

---

## 4. Statusübersicht

| Bereich | Status |
|---|---|
| Single-Table + GSIs + PITR | **IMPLEMENTED / VERIFIED (Code)** |
| Order-Lifecycle + Ownership/Consumer | **IMPLEMENTED / VERIFIED (Code + Tests)** |
| Erasure (ERASE/ANONYMIZE/RETAIN, Consumer-Scope) | **IMPLEMENTED / TESTED (Lambda-Tests)** |
| PITR verifiziert (Restore getestet) | **MISSING** |
| On-Demand-Backup / Backup-Retention | **MISSING** |
| Restore in neue Tabelle | **MISSING** |
| Datenmigration / Cutover | **MISSING** |
| Erasure-Ledger / Restore-PII-Schutz | **MISSING** |
| Retention-Fristen/TTL | **DOCUMENTED ONLY (ADR-008 PROPOSED)** |
| KMS/Secret-Management | **MISSING/BLOCKED** |
| Dual-Write/CDC | **MISSING** |
| Installer-Backup-/Migrations-Gate | **MISSING** |
| RIS-Direktschreibpfad | **DOCUMENTED ONLY** |
| AWS-Backup-Plan | **UNKNOWN/not decided** |

---

## 5. Tatsächliche Lücken

1. **Kein verifizierter Sicherungspunkt:** PITR ist aktiv, aber weder Restore noch
   Wiederherstellungsfenster wurden getestet; kein On-Demand-Backup.
2. **Kein Restore-Verfahren:** keine Namensstrategie, keine Rekonfiguration (PITR/Tags/IAM),
   keine Freigabe.
3. **Keine Migration:** kein Tool, keine Idempotenz, keine Validierung, kein Cutover.
4. **Kein Erasure-Nachweis:** Restore kann gelöschte/anonymisierte Daten zurückbringen.
5. **Keine Schreibkonsistenz während Migration:** kein Streams/CDC/Dual-Write.
6. **Keine Gate-Integration:** Installer verlangt keinen Backup-/Migrationsnachweis.
7. **Doc/Impl-Diskrepanz** beim `pk`-Muster (`ORDER#` vs. `ord_`) und RIS-Fremdschreibungen
   erschweren eine pauschale Migration.

---

## 6. Empfohlene P3-Architektur

**Grundsatz:** Backup ist Voraussetzung, Migration ist ein eigener, freigegebener Vorgang;
Terraform bleibt für Infrastruktur zuständig.

```text
① P3A Backup (verifiziert AVAILABLE)
        ↓
② P3B Restore in <table>-restore-<ts> (optional, nie produktiv)
        ↓
③ P3C Migration in neue Ziele-Tabelle (idempotent, validiert)
        ↓
④ P3D PartiQL-Diagnose (read-only, vor/nach Migration)
        ↓
⑤ P3E DSGVO/Nachweise (Erasure-Ledger, PII-Prüfung)
        ↓
⑥ P3F Cutover/Recovery (Matrix, Freigaben, Abbruchbedingungen)
```

**Keine automatische Ausführung.** Jeder Schritt erzeugt ein Artefakt (JSON/MD) mit
nachprüfbaren Nachweisen; „gestartet“ ≠ „erfolgreich“.

---

## 7. Phasenplan

### P3A — DynamoDB-Backup

| Feld | Inhalt |
|---|---|
| **Ist-Zustand** | PITR enabled (`main.tf:108`); **kein** On-Demand-Backup, keine Retention, keine Verifikation |
| **Fehlende Funktion** | Backup-Anforderung, Status-Polling bis `AVAILABLE`, Nachweisdatei, PITR-Fensterprüfung |
| **Technischer Ansatz** | `CreateBackup` (`<table>-upgrade-<UTC-ts>`), `DescribeBackup` pollen, `DescribeContinuousBackups` (PITR enabled + EarliestRestorable), Metadaten (Backup-ARN, Größe, Zeit, Account/Region/Table-ARN) in `backup-evidence.json`; **kein** Erfolg ohne `AVAILABLE`; IAM separat (`dynamodb:CreateBackup/DescribeBackup/ListBackups` auf Tabelle/Backup) |
| **Risiken** | Kosten (Backup-Storage), Retention/Datenschutz (PII im Backup), Rechteausweitung |
| **Abhängigkeiten** | Keine Codeänderung an der App; AWS-Schreibfreigabe |
| **Tests** | Lokal: Fake-Client (PENDING→AVAILABLE, Fehler, Timeout, fehlende Rechte); AWS später: echtes Backup im Teststack |
| **Freigabekriterien** | Backup `AVAILABLE`, ARN/Table/Account dokumentiert, PITR-Fenster notiert, kein „success“ bei Fehler |

### P3B — Restore in separate Tabelle

| Feld | Inhalt |
|---|---|
| **Ist-Zustand** | kein Restore |
| **Fehlende Funktion** | Restore-Namensstrategie, Rekonfiguration, Schutz der Originaltabelle |
| **Technischer Ansatz** | `RestoreTableFromBackup`/`RestoreTableToPointInTime` → `<table>-restore-<ts>`; Original bleibt unangetastet; nach Restore: Tags setzen, PITR reaktivieren, TTL (falls eingeführt) setzen, Streams bewusst aus, IAM-Policies für neue ARN separat; App **nicht** umschalten |
| **Risiken** | PII-Wiederauferstehung, Kosten, versehentliche Nutzung der Restore-Tabelle |
| **Abhängigkeiten** | P3A-Nachweis; Namens-/Tag-Konvention |
| **Tests** | Lokal: Namens-/Konfig-Checks; AWS: Restore aus Backup/PITR im Testkonto, Integritätsstichproben |
| **Freigabekriterien** | Restore-Tabelle `ACTIVE`, Original unverändert, Konfiguration dokumentiert, keine App-Bindung |

### P3C — Neue Tabelle und Datenmigration

| Feld | Inhalt |
|---|---|
| **Ist-Zustand** | keine Migration; nur Seed-Tools |
| **Fehlende Funktion** | Kopier-/Transformationsjob, Idempotenz, Validierung, Schreibkonsistenz, Cutover |
| **Technischer Ansatz** | Separate Migrationsrolle (`Scan`, `BatchWriteItem`, ggf. `CreateTable`, `DescribeTable`); Kopie per paginiertem Scan, **idempotente** `PutItem`-Upserts je `pk/sk`, Erhalt von `version`, `subjectId`, `consumerId`, GSI-Keys, `createdAt`; Validierung (Counts je Status/Consumer, Stichproben-Hashes, Key-Set-Diff); Schreibfenster: Queue drain oder Dual-Write-Entscheidung |
| **Risiken** | Verlust/Doppelverarbeitung, inkonsistente GSIs, PII, Kosten, lange Laufzeit |
| **Abhängigkeiten** | P3A-Backup, Zieltabellen-Schema, Entscheidung Dual-Write vs. Wartungsfenster |
| **Tests** | Lokal: Fake-Client, Idempotenz (2× Lauf = gleiches Ergebnis), Abbruch/Resume, Validierungslogik; AWS: Migration im Teststack mit Stichproben |
| **Freigabekriterien** | Key-Set/Count-Checks 0 Diff, keine offenen Schreibvorgänge, Validierungsreport, Cutover separat freigegeben |

### P3D — PartiQL-Diagnosepaket

| Feld | Inhalt |
|---|---|
| **Ist-Zustand** | keine Diagnose-Dokumente |
| **Fehlende Funktion** | read-only Abfragen am echten Schema |
| **Technischer Ansatz** | `docs/diagnostics/dynamodb/` mit `orders-diagnostics.md` + `restore-compare.md`: `SELECT` per `pk`/`sk`, GSI2-Owner-Abfrage, Status-/Zeitfenster, Restore-vs-Ziel-Vergleich, Stichproben; **nur lesend**, keine PII-Beispiele, Scan-Warnung + Kostenschätzung, Mandanten-/IAM-Grenzen |
| **Risiken** | Scan-Kosten, PII in Screenshots/Logs, falsche Erwartung „PartiQL = Migration“ |
| **Abhängigkeiten** | keine (Doku) |
| **Tests** | statische Prüfung: nur `SELECT`, keine Write-Statements, keine echten Daten |
| **Freigabekriterien** | Dokumente vorhanden, read-only geprüft, Warnhinweise enthalten |

### P3E — DSGVO/Security-Migration

| Feld | Inhalt |
|---|---|
| **Ist-Zustand** | Erasure implementiert (hard delete/anonymize), **kein Ledger**, keine Retention |
| **Fehlende Funktion** | Nachweis gelöschter Subjects, Restore-Schutz, Retention-Entscheidung |
| **Technischer Ansatz** | Minimales **Erasure-Ledger** (Item `ERASURE#<hash(subjectId)>` mit Zeit/operationId, **ohne PII**) oder externes Ledger; Restore-Prüfung: Ledger gegen Restore-Tabelle → betroffene Items erneut löschen/anonymisieren **vor** Cutover; Retention-Fristen als Entscheidung (ADR-008) |
| **Risiken** | Rechtliche Bewertung, Ledger selbst personenbeziehbar (Hash), Vollständigkeit |
| **Abhängigkeiten** | Fachlich-rechtliche Freigabe; P3A/P3B |
| **Tests** | Lokal: Ledger-Schreiben idempotent, Restore-Prüflogik mit Fixtures; AWS: Erase→Backup→Restore→Re-Erase im Testkonto |
| **Freigabekriterien** | dokumentierte Entscheidung, technischer Nachweis, Restore ohne PII-Wiederauferstehung |

### P3F — Cutover und Recovery

| Feld | Inhalt |
|---|---|
| **Ist-Zustand** | Table-Name über Env; kein Cutover-/Rollback-Konzept |
| **Fehlende Funktion** | Umschaltverfahren, Recovery-Matrix, Abbruchbedingungen |
| **Technischer Ansatz** | Runbook mit Matrix (Fehler vor/während Migration, vor/nach Cutover, neue Orders, Restore aus Alt-Backup); Cutover via Env-Wechsel + Redeploy **nur** nach Drain/Dual-Write; alte Tabelle bleibt lesbar/erhalten; Rückfall nur bei nachweisbar konsistenter alter Tabelle |
| **Risiken** | Datenverlust nach Cutover (neue Orders), SQS-In-Flight, doppelte Verarbeitung |
| **Abhängigkeiten** | P3C-Validierung, P3E-Nachweise |
| **Tests** | Trockenlauf im Teststack, Fehlerinjektion, Rollback-Probe |
| **Freigabekriterien** | dokumentierte Matrix, bestandene Validierung, explizite Cutover-Freigabe |

---

## 8. Integration mit P0A–P2

| Gate | Künftige Ergänzung (Planung) |
|---|---|
| P0A | unverändert: Tabellen-DELETE/REPLACE bleibt blockiert |
| P0C | Tabellen-Drift/State-Änderung bleibt sichtbar |
| P1 | Readiness/Manifest erhält Felder `backupEvidence` (ARN/Status/Zeit), `dataMigrationRequired`, `cutoverApproved`; `BLOCKED`, wenn Tabellen-Replace oder Migration erforderlich und Nachweis fehlt |
| `--accept-upgrade-review` | darf **nur** REVIEW freigeben; CRITICAL/MIGRATION bleibt blockiert (bereits so implementiert: P0A-Gate greift unabhängig; Readiness blockt MIGRATION/UNKNOWN) |
| Zweiter Apply-Pfad | **nicht** einführen; Migration ist separates Operator-Tooling, kein Terraform-Apply |

---

## 9. Implementierungsreihenfolge und Priorisierung

| Rang | Phase | Begründung |
|---|---|---|
| 1 | **P3D** (Doku) | sofort, risikolos, hilft bei allen späteren Prüfungen |
| 2 | **P3A** (Backup) | schützt Daten vor jedem weiteren Schritt; P0-Risiko |
| 3 | **P3E-Design** (Erasure-Ledger) | blockiert P3B/P3C fachlich; Entscheidung nötig |
| 4 | **P3B** (Restore) | Voraussetzung für Migrationsproben |
| 5 | **P3C** (Migration) | Kern, höchste Komplexität |
| 6 | **P3F** (Cutover/Recovery) | baut auf validierter Migration auf |

**Lokal implementierbar:** P3D, P3A-Orchestrierung (Fake-Client), P3B-Namens-/Konfiglogik,
P3C-Kopier-/Validierungslogik (Fake-Client), P3E-Ledger-Logik.

**AWS-Tests (separat freigeben):** echtes Backup, PITR-Restore, Restore-Tabelle, Migration
im Teststack, Cutover-Trockenlauf, Re-Erase nach Restore.

**Fachlich/rechtlich:** Retention-Fristen, Erasure-Ledger-Inhalt (Hash/Zweck), Umgang mit
PII in Backups, Cutover-Fenster, Löschpflichten.

---

## 10. Teststrategie

| Ebene | Inhalt |
|---|---|
| Unit (lokal) | Backup-Statusmaschine, Namensstrategie, Idempotenz, Pfad-/PII-Schutz, Validierungslogik, Ledger |
| Fixtures | synthetische Order-Items (keine echten Daten), Restore-/Ziel-Diffs |
| Negativ | Timeout, fehlende Rechte, abgebrochener Job, doppelte Kopie, PII im Restore, fehlende Freigabe |
| AWS (später) | Backup→Restore→Compare im Wegwerf-Stack; Migration mit 1k Items; Cutover-Probe; Erase→Restore→Re-Erase |
| Nicht behaupten | „DSGVO-konform“, „verlustfreier Rollback“, „PITR verifiziert“ ohne Nachweis |

---

## 11. Offene Architekturentscheidungen

| ID | Frage | Entscheider |
|---|---|---|
| O-01 | Erasure-Ledger: Hash-Item in der Tabelle vs. externes Ledger vs. Audit-Log? | Recht/Technik |
| O-02 | Retention-Fristen (ADR-008 PROPOSED) | Fachlich/rechtlich |
| O-03 | Cutover: Wartungsfenster vs. Dual-Write (App-Änderung) | Architektur/Betrieb |
| O-04 | Backup-Retention (Tage, Löschregel) | Betrieb/Recht |
| O-05 | KMS/Secret-Management (Blocked) | Security |
| O-06 | Legacy-`pk`-Muster/RIS-Direktschreibungen: normalisieren oder tolerant migrieren? | Architektur |

---

## 12. Konkrete nächste Entwicklungsaufträge

1. **P3D-01** — `docs/diagnostics/dynamodb/` mit read-only PartiQL-Queries + Kost-/PII-Hinweisen.
2. **P3A-01** — Backup-Orchestrierung (CreateBackup → DescribeBackup bis `AVAILABLE`) + Evidenz-JSON + Fake-Client-Tests.
3. **P3E-01** — Erasure-Ledger-Design + lokale Logik (kein AWS), Entscheidungsvorlage für O-01/O-02.
4. **P3B-01** — Restore-Namens-/Konfigurationslogik (kein AWS-Aufruf) + Tests.
5. **P3C-01** — Kopier-/Validierungslogik (Scan/BatchWrite, idempotent) gegen Fake-Client.
6. **P3F-01** — Cutover-/Recovery-Runbook + Matrix.

---

## 13. Risiken (Übersicht)

| ID | Risiko | Schwere |
|---|---|---|
| R-01 | Restore reaktiviert gelöschte/anonymisierte PII (kein Ledger) | **hoch** |
| R-02 | PITR ungetestet; Wiederherstellbarkeit unbewiesen | **hoch** |
| R-03 | Migration ohne Streams/Dual-Write → verlorene/doppelte Orders | **hoch** |
| R-04 | Falsche Erfolgsmeldung bei Backup/Restore | mittel |
| R-05 | IAM-Ausweitung für Migration | mittel |
| R-06 | Doc/Impl-Diskrepanz `pk` + RIS-Fremdschreiben | mittel |
| R-07 | Backup-Kosten/Retention | mittel |
| R-08 | Cutover-Rollback bei neuen Orders nicht verlustfrei | **hoch** |

---

## 14. Status

```text
P3 PLANNING COMPLETE — ORDER DATA MIGRATION ARCHITECTURE REVIEWED
```

Keine AWS-Operation, kein Terraform, keine Implementierung. **STOP — P3-Implementierung nur
mit gesonderter Freigabe.**
