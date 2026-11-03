# MO-ORDER-LEDGER-PERSISTENCE-P3E-02

**P3E-02 — RC4-Scope-Entscheidung zur Erasure-Ledger-Persistenz**

**Datum:** 2026-11-03
**Basis:** `feature/mo-order-erasure-ledger-p3e` @ `f7f61cd`
**Arbeitsbranch:** `feature/mo-order-ledger-persistence-p3e02`
**Modus:** Analyse/Scope-Entscheidung. **Keine AWS-Operation, keine Ledger-Persistenz,
kein Restore, keine Migration, kein Cutover, keine Änderung an Lambda/Terraform/RIS.**

---

## 1. Git-Ausgangsstand

| Prüfung | Ergebnis |
|---|---|
| Erwarteter Basis-HEAD | `f7f61cd` — vorhanden |
| Working Tree vor Beginn | CLEAN |
| Installer (vorher) | 539 PASS |
| Builder (vorher) | 128 PASS |
| Lambda (vorher) | 326 PASS |
| Auditlog/P3E-01/P3A/P0A–P1 | gelesen und gegen Code geprüft |

---

## 2. RC4-SCOPE-GATE

### Entscheidung

```text
POST_RC4
```

**Ledger-Persistenz ist für den geplanten RC4-In-place-Upgrade-Pfad nicht erforderlich.**
Sie schützt ausschließlich Restore-, Migrations- und Cutover-Szenarien, die in RC4 nicht
freigegeben sind. Es wird **keine** Ledger-Infrastruktur allein wegen P3E-02 angelegt.

### Begründung im Einzelnen

| Frage | Befund | Beleg |
|---|---|---|
| 1. Ist Ledger-Persistenz für den geplanten RC4-Upgrade-Pfad erforderlich? | **NEIN** — RC4 aktualisiert die bestehende Tabelle; ein Restore/Cutover ist nicht Teil des Pfads. | P0A/P1; P3E-01; kein P3B/P3F |
| 2. Welche RC4-Änderungen betreffen die Order-Tabelle? | **Additiv:** GSI3 (`gsi3pk`/`gsi3sk`, KEYS_ONLY), neue Item-Felder; keine Änderung an `pk`/`sk`, kein Tabellen-Replace. | `terraform/modules/dynamodb/main.tf:94-106`; RC4-P02I-B2; Commit `f5a3b03` |
| 3. Upgrade ohne Datenmigration möglich? | **JA by design** für versionsgebundene Installationen: GSI-Add/Update in place, kein Backfill, keine Key-Änderung. `LEGACY_UNKNOWN` blockiert weiterhin. | `docs/reports/MO-BUILDER-INSTALLER-UPGRADE-READINESS-01.md` Szenario B/E; P1 |
| 4. Welche Risiken sind durch P0A/P0B/P0C/P1/P3A abgesichert? | Tabellen-DELETE/REPLACE blockiert (P0A), Versionsbindung (P0B), Drift/State-Baseline (P0C), Readiness/Review (P1), lokale Backup-Orchestrierung (P3A). | `installer/core/upgrade_safety.py:35-40`; P1/Gates |
| 5. Welche Risiken entstehen erst bei Restore/Migration? | Wiederauferstehung gelöschter/anonymisierter PII, Verlust der Ledger-Historie, Cutover ohne Reconciliation, Datenverlust durch neue Tabelle. | P3E-01; P3-Planung |
| 6. Welche Mindestlösung ist für RC4 erforderlich? | **Keine neue Persistenz.** Restore/Cutover bleiben gesperrt; P3E-01-Gates dokumentieren die Sperre. Optional: reales P3A-Backup vor dem Upgrade. | P3E-01 `CUTOVER_BLOCKED`; P3A |

**Keine fachliche oder rechtliche Entscheidung wurde ersetzt.** R-01/R-02 bleiben offen.

---

## 3. Erasure-Konsistenzanalyse (Ist-Zustand)

Ablauf heute:

```text
Anforderung (interner Invoke, Auth/Secret/Projekt/Consumer)
  → GSI2-Query (subjectId)
  → pro Item: DeleteItem oder UpdateItem (Conditional subjectId/version)
  → Zähler/Status in der Response
  → keine Persistenz des Vorgangs
```

| Phase | Ist-Zustand | Konsistenz |
|---|---|---|
| Anforderung | `privacy/erase`, `operationId` nur in der Response | nicht persistent |
| Order-Mutation | hartes Delete bzw. Anonymize, Conditional | atomar pro Item, nicht über den Vorgang |
| Ledger-Eintrag | **nicht vorhanden** | keine Kopplung |
| Bestätigung | `COMPLETED`/`PARTIALLY_COMPLETED`/`BLOCKED` | nur Response, kein Nachweis |

### Kritischer Fehlerfall

**Order gelöscht, Ledger-Schreiben schlägt fehl** — dieser Zustand ist heute nicht
möglich, weil kein Ledger existiert. Würde man Ledger-Schreiben nach der Mutation
ergänzen, wäre die Löschung bereits irreversibel und ohne Nachweis; das darf **nicht**
als vollständig abgesicherte Erasure bestätigt werden.

### Wäre eine atomare Transaktion möglich?

- DynamoDB unterstützt `TransactWriteItems` über bis zu 100 Aktionen, auch
  tabellenübergreifend im selben Account/Region.
- Theoretisch könnte `Delete`/`Update` der Order mit `Put` eines Ledger-Items
  kombiniert werden.
- **Nicht verwendbar ohne Umbau:** Die bestehende Schleife verarbeitet beliebig viele
  Items, nutzt einzelne Conditional-Writes und hat keine Transaktions-/Resume-Semantik;
  >100 Items, Teilfehler und Wiederholungen sind nicht abgedeckt. IAM und Consumer
  müssten geändert werden.
- **Falls später umgesetzt:** pro Item Transaktion **oder** Write-Ahead-Intent
  (`PENDING` → Mutation → `APPLIED`); ein `PENDING` blockiert Restore/Cutover. Keine
  Exactly-once-Behauptung.

**In P3E-02 wird keine dieser Varianten implementiert.**

---

## 4. Minimale Persistenz (nur als Option, nicht umgesetzt)

Falls RC4_REQUIRED gewesen wäre, wäre die kleinste Lösung:

- separate DynamoDB-Ledger-Tabelle (Option B aus P3E-01), nicht die Order-Tabelle;
- `OrderErasureLedgerV1`-Events, HMAC-`subjectRef`, keine Payloads;
- idempotente `PutItem`-Events mit `eventId`/`idempotencyKey`;
- IAM nur für die Erasure-Rolle, kein `dynamodb:*`, keine Lambda-Rollen-Erweiterung;
- keine TTL, solange R-02 offen ist;
- Transaktion oder Write-Ahead-Intent, kein Best-effort-Schreiben.

Diese Option ist **nicht** Teil von RC4 und wird hier nicht angelegt.

---

## 5. HMAC-Schlüssel und Retention

- HMAC-Schlüssel dürfen nicht hartcodiert, nicht in Git, nicht in Evidenzberichten und
  nicht im Ledger stehen.
- Produktiv wäre Secrets Manager/KMS nötig; diese Infrastruktur ist in RC4 **nicht**
  implementiert und durch P00/Q-02/Q-09/Q-10 sowie ADR-008 nur vorgeschlagen.
- R-01 (Order-Retention) und R-02 (Ledger-Retention) sind **offen**. Ohne R-02 ist ein
  produktiver Ledger-Store nicht sicher betreibbar; deshalb keine Persistenz.
- Key-ID/Rotation sind in `docs/security/ORDER-ERASURE-LEDGER.md` dokumentiert, aber
  nicht produktiv umgesetzt.

---

## 6. RC4-Sicherheitsgrenzen (unverändert)

- P0A blockiert `aws_dynamodb_table`-DELETE/REPLACE (`ORDER-Daten`).
- P0B bindet Quelle/Zielversion; `LEGACY_UNKNOWN` blockiert.
- P0C verlangt State-Baseline/Drift-Nachweis.
- P1 klassifiziert SAFE/REVIEW/CRITICAL; `--accept-upgrade-review` gibt nur REVIEW frei,
  **nie** Migration/CRITICAL.
- P3A ist lokal; ein realer Backup-Nachweis fehlt (siehe Precheck).
- P3E-01 hält Restore/Cutover blockiert (`EXECUTION_NOT_VERIFIED`, `CUTOVER_BLOCKED`).
- Kein zweiter Terraform-Apply-Pfad, keine automatische Migration, kein Restore.

**Neue Ledger-Ressourcen wurden nicht hinzugefügt**, daher entsteht auch kein neues
Upgrade-Risiko für bestehende Installationen.

---

## 7. Tests und Regression

Es wurde **kein Produktcode** geändert; daher keine neuen Tests. Die bestehenden
Suiten wurden vollständig ausgeführt (siehe Precheck):

| Lauf | Ergebnis |
|---|---|
| Installer | **539 PASS** |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |

Keine AWS-/Terraform-Aufrufe, keine Datenänderung.

---

## 8. Warum POST_RC4 vertretbar ist

1. RC4 ist ein In-place-Upgrade ohne Tabellen-Replace und ohne Datenmigration.
2. Restore, Migration und Cutover sind in RC4 nicht freigegeben und bleiben durch
   P3E-01 blockiert.
3. Ledger-Persistenz ohne R-02/Key-Infrastruktur wäre ein ungenehmigter neuer
   Produktionsspeicher mit offener Retention.
4. Der bestehende Erasure-Consumer bleibt unverändert; es entsteht keine
   Scheinsicherheit durch halb implementierte Ledger-Schreibvorgänge.
5. RC4-Releasefähigkeit wird durch die fehlende Ledger-Persistenz **nicht** verbessert,
   aber auch nicht blockiert — vorausgesetzt, Restore/Cutover bleiben gesperrt.

---

## 9. Was bis zur späteren Implementierung blockiert bleibt

- Jeder Restore in eine produktive Order-Tabelle.
- Jeder Cutover auf eine restaurierte/migrierte Tabelle.
- Jede Aussage „Löschung ist restore-fest nachgewiesen“.
- Jede DSGVO-Konformitätsbehauptung für Backups/Restores.

Die P3E-01-Sperre bleibt maßgeblich:
`PLAN_VERIFIED` ≠ `EXECUTION_NOT_VERIFIED` ≠ `CUTOVER_BLOCKED`.
Ein lokaler Plan gibt keinen Cutover frei.

---

## 10. Verbleibende Risiken

| ID | Risiko | Status |
|---|---|---|
| L-01 | Kein Ledger → Löschung nach Restore nicht nachweisbar | offen (POST_RC4) |
| L-02 | HMAC-Key-Infrastruktur fehlt | offen |
| L-03 | R-01/R-02 Retention offen | offen |
| L-04 | Kein realer AWS-Backup-Nachweis | offen (P3A) |
| L-05 | Kein AWS-Upgrade-E2E für Bestandsinstallation | offen |
| L-06 | P3A nicht in P1-Readiness verdrahtet | offen |
| L-07 | Erasure-Consumer ohne Ledger-Intent | offen |

---

## 11. Nächste Schritte (nach RC4, separat freizugeben)

1. R-01/R-02 fachlich-rechtlich entscheiden.
2. Ledger-Store (Option B/C) + eigene IAM-Rolle + Key-Management freigeben.
3. Transaktions-/Write-Ahead-Design für den Erasure-Consumer implementieren und testen
   (inkl. >100 Items, Teilfehler, Retry, `PENDING`-Blockade).
4. P3E-01-Reconciliation an die echte Restore-Tabelle anbinden (P3B).
5. P1-Readiness um `backupEvidence`/`restorePrivacyReadiness` erweitern; keine Bypässe.
6. Erst danach Cutover (P3F) diskutieren.

---

## 12. Status

```text
P3E-02 COMPLETE — RC4 SCOPE VERIFIED
```

Entscheidung: **POST_RC4**. Keine Ledger-Persistenz implementiert; Restore/Cutover
bleiben gesperrt. **STOP — keine automatische Fortsetzung mit P3B/P3C/P3F.**
