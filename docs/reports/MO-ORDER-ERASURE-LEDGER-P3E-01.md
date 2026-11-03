# MO-ORDER-ERASURE-LEDGER-P3E-01

**P3E-01 — Erasure-Ledger-Vertrag, Restore-Reconciliation und Privacy-Gates (lokal)**

**Datum:** 2026-11-03
**Basis:** `feature/mo-order-backup-orchestration-p3a` @ `8f37b21`
**Arbeitsbranch:** `feature/mo-order-erasure-ledger-p3e`
**Charakter:** lokale Domain-/Planungsphase. **Kein AWS, kein Restore, keine
Datenänderung, keine Ledger-Persistenz, keine Änderung an Lambda/Erasure-Consumer,
kein Push/Merge.**

---

## 1. Git-Ausgangsstand

| Prüfung | Ergebnis |
|---|---|
| Erwarteter Basis-HEAD | `8f37b21` — vorhanden |
| Working Tree vor Beginn | CLEAN |
| Installer (vorher) | 490 PASS |
| Builder (vorher) | 128 PASS |
| Lambda (vorher) | 326 PASS |
| Auditlog/ADR-008/P3-Berichte | gelesen und gegen Code geprüft |

---

## 2. Tatsächliche Erasure-Implementierung

Belege: `lambda/src/order_service.py`, `lambda/src/identity.py`,
`lambda/src/index.py`, `lambda/tests/test_order_service.py`.

| Eigenschaft | Befund | Status |
|---|---|---|
| ERASE | `DeleteItem` mit `subjectId` + `version`-Condition; hartes Löschen | IMPLEMENTED / TESTED |
| ANONYMIZE | setzt `customer.name/email` auf `ANONYMIZED`, entfernt `subjectId`, GSI2, `result`, `processingError`, `processingAttemptId`, GSI3 | IMPLEMENTED / TESTED |
| RETAIN | zählt nur, keine Mutation; `PARTIALLY_COMPLETED` bei `retained>0` | IMPLEMENTED |
| Idempotenz | `ConditionalCheckFailedException` → `skipped`, kein Fehler | IMPLEMENTED / TESTED |
| Consumer-Scope | optionaler `consumerId`-Filter; ohne Scope deployment-weit | IMPLEMENTED / TESTED |
| Subject-/Order-Identität | `subjectId`/JWT-`sub`, GSI2, `orderId` | IMPLEMENTED / TESTED |
| Löschabschluss | Response-Status/Zähler | IMPLEMENTED, **nicht persistent** |
| Wiederholungsversuche | keine automatische Retry-/Resume-Logik | **MISSING** |
| Nachweisführung | keine Historie, kein Ledger | **MISSING** |
| Restore-Schutz | — | **MISSING** |

### Antworten auf die Prüffragen

1. **ERASE entfernt** das gesamte Order-Item (inkl. `customer`), sofern die Condition passt.
2. **ANONYMIZE verändert** `customer` und entfernt Owner-/Ergebnis-/Fehlerfelder; Order,
   Betrag, Zeitstempel und `orderId` bleiben.
3. **RETAIN** behält alles; es ist keine Löschung und kein Nachweis.
4. **Identifikatoren:** `subjectId` (JWT-`sub`), `consumerId`, `orderId`, `pk`/`sk`,
   `version` (Conditional).
5. **Mehrere Orders:** GSI2-Query sammelt alle, Schleife bearbeitet jede einzeln.
6. **Fehlende Orders:** keine Aktion; eine leere Treffermenge ist kein Löschbeweis.
7. **Wiederholte Löschanforderung:** bereits gelöschte/parallel geänderte Items werden
   als `skipped` gewertet (idempotent), neue `operationId` pro Aufruf.
8. **Abschluss:** `COMPLETED` nur ohne Fehler/Retain; `PARTIALLY_COMPLETED` bei
   Fehlern/Retain; nicht gespeichert.
9. **Teilfehler:** `failedRecords` werden gezählt, die Schleife läuft weiter; kein
   automatischer Retry/Resume.
10. **Backup-Risiko:** PITR/Backups können gelöschte oder anonymisierte Daten vor dem
    Löschzeitpunkt wiederherstellen; es gibt keinen Ledger, der das erkennt.

---

## 3. Bestehende DSGVO-/Sicherheitsmechanismen

- Interne Privacy-Auth: Projektbindung, `authorized`, `privacy_erase`, Secret-Vergleich
  (`secrets.compare_digest`) — fail-closed.
- Optionaler Consumer-Scope verhindert Zugriff auf fremde Consumer, wenn gesetzt.
- Conditional Writes schützen vor fremden/parallelen Änderungen.
- Erasure-Response enthält keine vollständigen Payloads, aber `subjectId`; sie darf
  nicht in Logs/Ledger landen.
- ADR-008 (PROPOSED) beschreibt Secret-Management/Retention, ist aber nicht umgesetzt.
- PITR ist Terraform-seitig aktiv, aber nicht restauriert/getestet.

---

## 4. Erkannte Lücken

1. Keine persistente Historie von Lösch-/Anonymisierungsentscheidungen.
2. Kein Nachweis, welche Orders/Subjects eine Operation tatsächlich betraf.
3. Kein Restore-Schutz: Backup kann gelöschte PII wiederbringen.
4. Kein Umgang mit `PARTIALLY_COMPLETED`/`FAILED` über den Request hinaus.
5. Kein Ledger für `RETAIN`-Entscheidungen.
6. Keine pseudonymisierte Subject-Referenz.
7. Keine Retention-/Löschfristen (ADR-008 PROPOSED).
8. Keine Signatur/kein unabhängiger Store für Nachweise.
9. `ANONYMIZE` lässt Order-/Betragsdaten bestehen — fachlich korrekt, aber kein
   vollständiger Löschbeweis.

---

## 5. Ledger-Architekturvarianten

| Variante | Restore-Isolation | Aufwand | Bewertung |
|---|---|---|---|
| A: Items in Order-Tabelle | **schlecht** | niedrig | ungeeignet, wird mitrestauriert |
| B: separate Ledger-Tabelle | gut | mittel | pragmatische Zwischenstufe |
| C: unabhängiger Event-Store | **sehr gut** | hoch | empfohlen für Revisionsschutz |

Details: `docs/security/ORDER-ERASURE-LEDGER.md`.

---

## 6. Empfohlene Architektur

**PROPOSED:** unabhängiger, append-only Event-Store (Option C), mindestens aber eine
separate Ledger-Tabelle (Option B), mit eigener IAM-Rolle und eigener Retention.
**Keine Ressource in P3E-01 angelegt.** Schlüsselverwaltung über Secrets Manager/KMS
ist ebenfalls nur geplant (ADR-008 D-5/D-6).

---

## 7. Datenvertrag

`OrderErasureLedgerV1` (implementiert in `installer/core/order_erasure_ledger.py`):

- Ledger: `schemaVersion`, `ledgerId`, `source`, `completeHistory`,
  `coveredFrom`, `coveredUntil`, `createdAt`, `events`.
- Event: `eventId`, `operationId`, `operation` (`ERASE`/`ANONYMIZE`/`RETAIN`),
  `consumerId`, `subjectRef`, `orderRefs`, `decidedAt`, `appliedAt`, `status`,
  `idempotencyKey`, Zähler, `integritySha256`.
- **Pseudonymisierung:** keyed HMAC-SHA256, Schlüssel ≥ 32 Byte, `keyId` sichtbar,
  Schlüssel nie im Ledger; ungesalzene Hashes werden abgelehnt.
- **Datenminimierung:** keine Namen/E-Mails/Payloads/Items/Beträge/Secrets.
- **Integrität:** SHA-256 pro Event; erkennt Änderungen, ist **keine Signatur**.

---

## 8. Reconciliation-Verfahren

`plan_reconciliation` erzeugt nur einen Plan:

1. Restore-Kontext prüfen (ARN, Account, Region, Name, Restore-/Backup-Zeitpunkt).
2. Ledger laden: Schema, Pflichtfelder, Integrität, Dubletten, Chronologie.
3. Vollständigkeit + Abdeckung um `restoreAt` prüfen.
4. Ereignisse mit `appliedAt >= restoreAt` als auszuführende Aktionen vormerken;
   `appliedAt < restoreAt` gegen den restaurierten Zustand verifizieren.
5. Scope/Subject je Order prüfen; Konflikte sammeln.
6. Aktionen `DELETE`/`ANONYMIZE`/`RETAIN` ausgeben — **keine Ausführung**.
7. Readiness: maximal `REVIEW_REQUIRED`; `EXECUTION_NOT_VERIFIED`,
   `CUTOVER_BLOCKED`, `cutoverApproved=false`.

**Fail-closed:** fehlender/unvollständiger/ unbekannter Ledger, fehlende Integrität,
fehlender Restore-Zeitpunkt, ungültige Chronologie, Consumer-/Subject-Konflikt,
partielle Anwendung, unbekannte Order-Keys. Leere Restore-Menge oder keine Aktionen
führen **nicht** zu `PLAN_VERIFIED`.

`RETAIN` erzeugt nie `DELETE`.

---

## 9. Retention-Entscheidungen und offene Fragen

Matrix und Risiken: `docs/security/ORDER-ERASURE-RETENTION-DECISIONS.md`.

Alle Fristen sind **OPEN** (Order, Ledger, Backups, PITR, Restore-Tabellen, Evidenz,
CloudTrail). Es wurden **keine** gesetzlichen Fristen erfunden und **keine** TTL
konfiguriert. Insbesondere R-02 (Ledger muss Backups überdauern) blockiert eine
produktive Persistenz.

---

## 10. Sicherheits-Gates

`OrderRestorePrivacyReadinessV1` (Spezifikation in
`docs/security/ORDER-RESTORE-PRIVACY-GATES.md`):

- `planStatus`, `executionStatus`, `cutoverStatus`, `cutoverApproved`.
- In P3E-01 ist **kein** `VERIFIED` für Restore/Cutover möglich.
- `approve_cutover` verweigert ohne Ausführungsnachweis
  (`ORDER_RESTORE_CUTOVER_BLOCKED`).
- P1-Integration nur additiv spezifiziert; **keine P1-Gates verändert**.
- `--accept-upgrade-review` darf Datenschutz-/Migrationsblockaden nicht übergehen.

---

## 11. Lokale Tests

`installer/tests/test_order_erasure_ledger.py`: **49 Tests**, keine AWS-/Terraform-
Aufrufe, keine echten Order-Daten.

Positiv: ERASE/ANONYMIZE/RETAIN, mehrere Orders, wiederholte Events, Idempotenz,
Consumer-Zuordnung, vollständige Historie, Plan ohne Mutation, keine PII.
Negativ: fehlender/unvollständiger/unbekannter Ledger, fehlende Event-ID/Consumer,
Konflikte, fehlender Restore-Zeitpunkt, ungültige Chronologie, partielle Anwendung,
fehlerhafte Anonymisierung, manipulierte Integrität, unbekannte Order-Keys,
widersprüchliche Dubletten, fehlende Integrität, Cutover ohne Ausführungsnachweis,
leere Ergebnismenge.

---

## 12. Regressionsergebnisse

| Lauf | Ergebnis |
|---|---|
| Neue P3E-Tests | **49 PASS** |
| Installer gesamt | **539 PASS** (490 + 49) |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| `compileall installer` | OK |

Keine Terraform-Dateien geändert → kein `fmt/validate`. Kein AWS-Zugriff, kein
Restore, keine Datenänderung.

---

## 13. Git-Commits

| Commit | Inhalt |
|---|---|
| `1405009` | Erasure-Baseline, Ledger-Vertrag, Retention-Entscheidungen |
| `1ad2fbb` | Ledger-Domainmodell + Reconciliation-Planer |
| `3bbc397` | 49 lokale Tests |
| `575bcc2` | Restore-Privacy-Gate-Vertrag |
| `e3a0b05` | Fail-closed-Validierung manuell konstruierter Restore-Kontexte |
| *(dieser Commit)* | Abschlussbericht, Migrationsfahrplan, Auditlog |

---

## 14. Risiken

| ID | Risiko | Schwere |
|---|---|---|
| R-01 | Restore bringt gelöschte/anonymisierte PII zurück | **hoch** |
| R-02 | Ledger-Persistenz fehlt; nur Plan, kein Nachweis | **hoch** |
| R-03 | HMAC-Schlüssel/Rotation nicht produktiv geklärt | hoch |
| R-04 | Retention-/Löschfristen offen | hoch |
| R-05 | `PARTIALLY_COMPLETED`/Retry nicht abgesichert | mittel |
| R-06 | Selbst-Hash ist keine Signatur; Store manipulierbar | mittel |
| R-07 | Consumer-/Legacy-Scope unvollständig | mittel |
| R-08 | Falsche Freigabe durch leere Ergebnislisten | vermieden (Review) |

---

## 15. Empfehlungen für P3B und produktive Integration

**Vor P3B/produktivem Restore:**

1. R-02 (Ledger-Retention) und R-01 (Order-Retention) fachlich-rechtlich entscheiden.
2. Ledger-Store (Option C/B) und eigene IAM-Rolle freigeben.
3. Ledger-Schreibpfad additiv an den bestehenden Erasure-Consumer anbinden — erst nach
   separater Freigabe; **in P3E-01 nicht erfolgt**.
4. Key-Management/Rotation (Secrets Manager/KMS) festlegen.
5. P1-Readiness additiv um `backupEvidence`/`restorePrivacyReadiness` erweitern;
   keine Bypass-Möglichkeit für `--accept-upgrade-review`.

**P3B:**

- Restore nur in `<table>-restore-<timestamp>`, Original unangetastet.
- Reconciliation-Plan gegen die Restore-Tabelle ausführen und **Ausführung**
  separat nachweisen; erst dann Cutover-Antrag.
- Nach Ausführung erneut Ledger-/Zustandsprüfung; Evidenz an dieselbe
  State-Baseline binden.
- Ohne P3E-Freigabe kein Cutover.

---

## 16. Status

```text
P3E COMPLETE — ERASURE LEDGER CONTRACT AND PRIVACY GATES LOCALLY VERIFIED
```

Lokal verifiziert (49 Tests, Installer 539, Builder 128, Lambda 326). Keine
produktive Ledger-Persistenz, kein Restore, keine Cutover-Freigabe. **STOP.**
