# MO-ORDER-PARTIQL-DIAGNOSTICS-P3D-01

**P3D — Schreibgeschütztes PartiQL-Diagnosepaket für die Order-Tabelle**

**Datum:** 2026-11-03
**Basis:** `feature/mo-builder-upgrade-p2` @ `5ecbe58`
**Arbeitsbranch:** `feature/mo-order-partiql-diagnostics-p3d`
**Charakter:** lokale Diagnoseartefakte und statische Tests — **keine AWS-/Terraform-Operation,
keine Migration, keine Änderung an Order-Modell, Lambda oder RIS**

---

## 1. Git-Ausgangsstand

| Prüfung | Ergebnis |
|---|---|
| Erwarteter Basis-HEAD | `5ecbe58` — vorhanden |
| Branch erstellt | `feature/mo-order-partiql-diagnostics-p3d` |
| Working Tree vor Beginn | CLEAN |
| Builder-Tests (vorher) | 128 PASS |
| Installer-Tests (vorher) | 422 PASS |
| Auditlog | gelesen; Regeln auch für Analyse-Agenten eingehalten |

---

## 2. Tatsächliches DynamoDB-Schema

Quelle ist der ausgeführte Code, nicht das Design-Dokument. Details:
`docs/diagnostics/dynamodb/schema-reference.md`.

| Element | Befund | Status | Beleg |
|---|---|---|---|
| Tabelle | `var.project_name`, Single-Table | VERIFIED | `terraform/modules/dynamodb/main.tf:11-24` |
| `pk` | `ord_` + `orderId` → `ord_ord_<24hex>` | VERIFIED | `order_service.py:84-85,201-205`; `test_order_access_authorization.py:43` |
| `sk` | `#ORDER` | VERIFIED | `order_types.py:22` |
| `gsi1pk` / `gsi1sk` | `LIST` / `createdAt` | VERIFIED | `order_service.py:216-217` |
| `gsi2pk` / `gsi2sk` | `SUBJECT#<subjectId>` / `ord_<orderId>#<createdAt>` | VERIFIED | `order_service.py:225-226` |
| `gsi3pk` / `gsi3sk` | `PROCESSING#RUNNING` / Claim-Zeit | VERIFIED | `sqs_handler.py:48,336,351-353` |
| GSI1-Projektion | `INCLUDE` (6 Attribute) | VERIFIED | `main.tf:59-73` |
| GSI2-Projektion | `INCLUDE` (9 Attribute, **ohne** `consumerId`) | VERIFIED | `main.tf:75-92` |
| GSI3-Projektion | **`KEYS_ONLY`** | VERIFIED | `main.tf:94-110` |
| PITR | enabled | VERIFIED (nie restauriert/getestet) | `main.tf:108-110` |
| Streams / TTL | nicht konfiguriert | VERIFIED | Modul |
| Verschlüsselung | AWS-owned, kein KMS | VERIFIED | Modul |

### PII-Attribute

- `customer.name`, `customer.email` (in GSI1/GSI2 **mitprojiziert**).
- `subjectId`, `ownerId`, `actorId` (pseudonym, personenbeziehbar).
- `result` / `processingError` können fachliche Daten enthalten.
- Kein Erasure-Ledger → Restore-Risiko (P3E).

---

## 3. Abweichungen Dokumentation ↔ Code

| # | Abweichung | Bewertung |
|---|---|---|
| 1 | `database/dynamodb-design.md:31` nennt `pk = ORDER#<orderId>`; Code nutzt `ord_ord_<24hex>` | **CONFLICT** — Diagnose darf kein einheitliches Muster annehmen |
| 2 | Design-Doc-Indexabschnitt listet nur `gsi1`; `gsi2`/`gsi3` fehlen dort | veraltet, Code maßgeblich |
| 3 | `BACKUP-01`/`BACKUP-02` sagen „kein PITR“; aktuelles Modul hat PITR | Doku veraltet, PITR ungetestet |
| 4 | RIS schreibt direkt, teils ohne `subjectId` und mit eigenem `pk`-Muster | DOCUMENTED ONLY — nicht verändert |
| 5 | `AGENTS.md` nennt 53 Lambda-Tests; tatsächlich 326 | Doku-Drift, im Bericht korrigiert |
| 6 | `gsi2` projiziert kein `consumerId` | Consumer-Prüfung braucht vollständiges Item |

---

## 4. Unterstützte Diagnoseabfragen

| Datei | Zweck | Zugriff |
|---|---|---|
| `order-lookup.partiql` | Order per `pk`/`sk` exakt finden, Existenz prüfen | Punktzugriff (`GetItem`-äquivalent) |
| `order-status.partiql` | Status/Zeitstempel einer bekannten Order; Zeitfenster über GSI1 | Key + GSI1 |
| `gsi-diagnostics.partiql` | GSI1-Zeitfenster, GSI2-Subject, GSI3-Claims + zweiter Basiszugriff | GSI1/2/3 |
| `subject-diagnostics.partiql` | Subject-Orders, Anonymisierungsmerkmale | GSI2 + Basis |
| `restore-comparison.partiql` | gleicher Schlüssel in Original- und Restore-Tabelle, Existenzstichprobe | Punktzugriff je Tabelle |

Alle Statements sind `SELECT`; Beispielwerte sind Platzhalter
(`<TABLE_NAME>`, `<ORDER_PK>`, `<SUBJECT_ID>`, `<FROM_ISO>`, `<TO_ISO>`,
`<RESTORE_TABLE_NAME>`, `<REGION>`, `<ACCOUNT_ID>`).

**Nicht enthalten (bewusst):** Statusabfrage ohne Key (Scan), unbegrenzte Scans,
`SELECT *`, Joins, Aggregationen, schreibende Statements.

---

## 5. Indexnutzung

| Abfrage | Index | Effizienz | Einschränkung |
|---|---|---|---|
| `pk` + `sk` | Basistabelle | Punktzugriff | `pk` muss korrekt gebildet werden |
| `gsi1sk BETWEEN` | GSI1 | partitionierter Query | Konstanter `LIST`-PK → Hot-Partition |
| `gsi2pk = SUBJECT#…` | GSI2 | partitionierter Query | nach `ANONYMIZE` nicht mehr auffindbar |
| `gsi3pk = PROCESSING#RUNNING` | GSI3 | partitionierter Query | **nur Schlüssel**; Details per zweitem `GetItem` |
| Status ohne Key | — | **Scan** | nicht als Standardabfrage angeboten |

GSI2 liefert `customer` mit (PII); Diagnosen projektieren es nicht.

---

## 6. Scan- und Kostenhinweise

- Key-/Indexzugriff ist der Regelfall; jede Abfrage im Paket nutzt einen Schlüssel.
- `LIMIT` begrenzt nur die Ergebnismenge, **nicht** die gelesene Datenmenge —
  ausdrücklich als keine Kostengarantie dokumentiert.
- Große Zeitfenster ohne `BETWEEN` können viele Items lesen.
- `SELECT *` ist wegen PII und Item-Größe untersagt (statisch geprüft).
- Nicht indizierte Statusfilter bleiben eine dokumentierte Grenze; kein neuer GSI
  in diesem Auftrag.

---

## 7. IAM- und DSGVO-Grenzen

- Minimalrechte: `dynamodb:PartiQLSelect`, `GetItem`, `Query`, optional
  `DescribeTable`; **kein** `Scan`, **kein** `PutItem`/`UpdateItem`/`DeleteItem`,
  **kein** `PartiQLInsert/Update/Delete`, kein `dynamodb:*`.
- Ressourcen nur auf Tabelle + `gsi1`/`gsi2`/`gsi3` (+ Restore-Muster); keine
  Änderung der Lambda-/Worker-Rollen.
- **IAM-Leserechte erzeugen keine Mandantenisolation.** Owner-/Consumer-Prüfung
  ist Anwendungslogik; die Diagnose-Rolle sieht alle Items. Das ist ausdrücklich
  dokumentiert, ebenso die nötige Beschränkung auf freigegebene Personen/Umgebungen.
- Keine echten Kontonummern, keine E-Mail-Adressen, keine Secrets, keine
  PII-Beispieldaten in den Artefakten (statisch geprüft).
- Keine DSGVO-Konformitätsbehauptung; Erasure-/Restore-Nachweis bleibt P3E.

---

## 8. Erstellte Dateien

```text
docs/diagnostics/dynamodb/README.md
docs/diagnostics/dynamodb/schema-reference.md
docs/diagnostics/dynamodb/order-lookup.partiql
docs/diagnostics/dynamodb/order-status.partiql
docs/diagnostics/dynamodb/gsi-diagnostics.partiql
docs/diagnostics/dynamodb/subject-diagnostics.partiql
docs/diagnostics/dynamodb/restore-comparison.partiql
docs/diagnostics/dynamodb/security-and-iam.md
installer/tests/test_partiql_diagnostics.py
```

---

## 9. Testergebnisse (lokal, ohne AWS)

| Lauf | Ergebnis |
|---|---|
| Neue P3D-Tests | **15 PASS** |
| Installer gesamt (`discover -s installer/tests`) | **437 PASS** (422 + 15) |
| Builder (`discover -s module_builder/tests`) | **128 PASS** |
| Lambda (`discover -s tests`, inkl. `compileall`) | **326 PASS** |

Geprüft wird u. a.:

- Dateien vollständig; jedes Statement beginnt mit `SELECT`.
- Keine schreibenden Keywords außerhalb von Kommentaren/Strings
  (Selbsttest beweist, dass die Prüfung nicht nur Textsuche ist).
- Kein `SELECT *`; Platzhalter konsistent und im README dokumentiert.
- Keine 12-stelligen Kontonummern, keine E-Mails, keine Credentials, kein
  „Max Mustermann“.
- GSI-Namen, Projektionen und `non_key_attributes` stimmen mit
  `terraform/modules/dynamodb/main.tf` überein; GSI3 ist als `KEYS_ONLY` mit
  zweitem `GetItem` beschrieben.
- Schlüsselmuster und `ORDER#`-Konflikt sind dokumentiert.

**Nicht ausgeführt:** AWS-Aufrufe, DynamoDB-Scans, Terraform. Die PartiQL-Beispiele
wurden daher **nicht gegen eine echte Tabelle ausgeführt**; syntaktische Gültigkeit
wurde manuell gegen das DynamoDB-PartiQL-Sprachprofil geprüft (nur `SELECT`,
`BETWEEN`, `LIMIT`, Index-`FROM`).

---

## 10. Bekannte Einschränkungen

1. Keine Ausführung gegen AWS → keine Laufzeitbestätigung der Beispiele.
2. Kein vollständiger Konsistenznachweis; Stichproben beweisen keine Migration.
3. Kein Status-Index → Statusfilter ohne Key bleibt Scan und ist nicht Teil des Pakets.
4. GSI3 liefert nur Schlüssel; Details nur über die Basistabelle.
5. Keine Mandantenisolation durch IAM/SQL; sie bleibt Anwendungslogik.
6. Erasure-/Restore-Schutz (P3E) und Backup-Nachweis (P3A) fehlen weiterhin.
7. Design-Dokumente (`database/dynamodb-design.md`, BACKUP-01/02) bleiben veraltet;
   dieser Auftrag ändert sie nicht.

---

## 11. Git-Commits

| Commit | Inhalt |
|---|---|
| `b506b0b` | Schema-Discovery und Referenzdokumentation |
| `7e27645` | PartiQL-Abfragen, README, IAM-/DSGVO-Leitfaden |
| `dacd671` | Statische Sicherheits- und Konsistenztests |
| *(dieser Commit)* | Abschlussbericht, Migrationsfahrplan, Auditlog |

---

## 12. Empfehlungen für P3A (Backup)

1. **Evidenz statt Behauptung:** Backup erst als erfolgreich führen, wenn
   `DescribeBackup` `AVAILABLE` meldet; ARN, Tabellen-ARN, Account, Region,
   Größe und Zeitpunkt im Evidenz-JSON festhalten.
2. **PITR-Fenster prüfen:** `DescribeContinuousBackups` (Status +
   `EarliestRestorableDateTime`) dokumentieren, nicht nur „enabled“.
3. **Keine PII in Evidenzdateien:** nur Metadaten/Hashes, keine Item-Inhalte.
4. **Retention-Entscheidung** (O-04) vor dem ersten produktiven Backup treffen.
5. **Diagnose vor Migration:** Restore-Tabelle mit den P3D-Abfragen stichprobenartig
   prüfen; vollständige Validierung bleibt P3C.
6. **Erasure-Ledger (P3E)** vor Restore/Cutover klären, damit gelöschte PII nicht
   unbemerkt zurückkehrt.

---

## 13. Status

```text
P3D COMPLETE — PARTIQL DIAGNOSTICS VERIFIED
```

Verifikation bezieht sich auf die lokalen Artefakte und statischen Tests; die
PartiQL-Ausführung gegen AWS ist **nicht** Teil dieses Auftrags. **STOP — keine
weiteren P3-Phasen ohne Freigabe.**
