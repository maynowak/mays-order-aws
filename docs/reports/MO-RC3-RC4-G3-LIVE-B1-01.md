# MO-RC3-RC4-G3-LIVE-B1-01

**Controlled DLQ, Recovery & Compatibility E2E**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `aff4948efc251d20d290f7c8e63d5a20727a5e83`
**Modus:** autorisierte Live-Tests ausschließlich im RC4-Teststack;
keine Privacy-Tests, kein Terraform, keine Produktänderung, kein Push/Merge.

```text
G3-LIVE-B1: PARTIAL
```

**Begründung:** DLQ, Compatibility, Cleanup und zentrale Recovery-Pfade sind
PASS. Der GSI3-Haupttest liefert die erwarteten Sends/Skips und keine
Statusregression, aber `candidates=4` statt der im alten Manifest erwarteten
`8`; das ist ein Manifest-/Semantik-Mismatch, kein Status-/Datenfehler.
Der Foreign-Identity-Test bleibt ohne zweite autorisierte Testidentität
BLOCKED.

---

## 1. Baseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `aff4948efc251d20d290f7c8e63d5a20727a5e83` |
| Working Tree vor Lauf | CLEAN |
| Lambda CodeSha Handler | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Lambda CodeSha Worker | derselbe Hash |
| Teststack | `mays-orders-rc4-test` |
| Account/Region | `240571105849` / `eu-central-1` |
| Test-Run-ID | `g3b133a3dd52a0` |

---

## 2. Preflight

- Beide Lambda-Funktionen `Active` / `LastUpdateStatus=Successful`.
- ESM `dbde8c61-c116-42f1-97e6-782edd900c3d` Enabled, Batch 5,
  `ReportBatchItemFailures`.
- Main Queue und DLQ vor dem Lauf 0/0.
- DynamoDB ACTIVE, 0 Items; GSI3 ACTIVE/KEYS_ONLY, Query 0.
- Cognito-Pool leer; kein Testbenutzer vorhanden.
- Keine konkurrierende Pipeline/Deployment-Aktivität.

---

## 3. Ausgeführte Tests

### 3.1 RC3/RC4 Compatibility

| Test | Ergebnis |
|---|---|
| RC3-Body ohne `orderType` → 201/PENDING | **PASS** |
| Worker → CONFIRMED | **PASS** (90-s-Poll) |
| Response `orderType=generic` | **PASS** |
| Expliziter `orderType=generic` → 201 | **PASS** |
| PATCH `CONFIRMED→PROCESSING` | **PASS** (200) |
| PATCH ungültig (`PROCESSING→CANCELLED`) | **PASS** (409 `INVALID_TRANSITION`) |
| Legacy-Order ohne Identität → 404 | **PASS** (korrigierter Lauf) |
| Fremde Identität | **BLOCKED** — keine zweite autorisierte Testidentität |
| Unauthentifizierter 401 | bereits G3 PASS; in B1 nicht wiederholt |

Testkorrektur: Der erste Legacy-Versuch verwendete eine Order-ID ohne
`ord_`-Präfix und wurde daher bereits von der API-Validierung mit 400
abgewiesen. Das war ein Testfixture-Fehler, kein Produktfehler. Der korrigierte
Lauf mit `ord_g3b1legacy7543469e` lieferte erwartungsgemäß **404**.

### 3.2 DLQ / Retry

| Test | Ergebnis |
|---|---|
| DLQ-01 malformed Nachricht → DLQ | **PASS**; MessageId `2f2f572e…` |
| DLQ-02 gültige Nachricht, Order fehlt → DLQ | **PASS**; MessageId `9f5dbeb6…` |
| Kein DDB-Write für DLQ-01/02 | **PASS** (`GetItem` leer) |
| Main Queue nach Verarbeitung 0/0 | **PASS** |
| DLQ nach Cleanup 0/0 | **PASS** |
| `maxReceiveCount=1` / Redrive | **PASS** (Konfiguration + beobachtete Zustellung) |

Beim ersten Cleanup war die DLQ-Zustellung noch nicht sichtbar; beide eigenen
Nachrichten wurden anschließend gezielt per `ReceiveMessage` + `DeleteMessage`
entfernt. **Kein Purge**, keine fremde Nachricht.

### 3.3 GSI3 / Recovery

Run-ID `g3b133a3dd52a0`; 10 Fixtures A/B/C/D/E/F/G/I/L/M.

Erster Scan `limit=20`:

```text
scanned=8  checked=8  candidates=4  sent=4  failed=0
budgetExhausted=1
skipped={anonymized:1, budget_exhausted:1, cancelled:1, not_running:1}
```

Snapshots nach dem Lauf:

| Fixture | Status | Version |
|---|---|---|
| A | CONFIRMED | 2 |
| B | CONFIRMED | 2 |
| L | SHIPPED | 2 |
| M | CONFIRMED | 3 |

- Keine Statusänderung für A/B/L; M wurde einmalig `PENDING→CONFIRMED`.
- Zweiter Scan mit denselben Fixtures: gleicher Report; A/B/L/M unverändert;
  M blieb Version 3. **Keine Doppelverarbeitung/Status-Writes.**
- GSI3-Skip-Zähler entsprechen dem Vertrag.
- **Mismatch:** Das G3-EXT-Manifest erwartete `candidates=8`; deployed G3-FIX
  meldet `candidates=4` (Anzahl ausgewählter gültiger Kandidaten), während
  `scanned=8` und `sent=4` stimmen. Das ist ein Manifest-/Feld-Semantik-
  Mismatch, kein Recovery-/Datenfehler. **PARTIAL** für den exakten
  Candidate-Count-Vertrag.

#### GAP-01/02 Starvation

Separater Lauf `g3b1starve0e673193`, 5 Fixtures: 2× CANCELLED, 2× Budget,
1× gültig PENDING, `limit=2`:

```text
scanned=5 candidates=1 checked=5 sent=1
budgetExhausted=2
skipped={budget_exhausted:2, cancelled:2}
valid_status=CONFIRMED, version=3
```

**PASS:** Die 4 Skips verdrängen den gültigen Kandidaten nicht; er wird
innerhalb des Scan-Budgets verarbeitet.

#### GAP-03 Expired Claim

CloudWatch-Worker-Logs für Fixture L:

```text
Worker processing: order_id=g3b133a3dd52a0L, status=SHIPPED
Order g3b133a3dd52a0L already in status SHIPPED (idempotent)
```

Das belegt: Recovery sendet für `SHIPPED` den aktuellen Status, der Worker
führt keinen Statusrücksprung aus. **PASS** für den GAP-03-Pfad (ohne
produktiven Processing-Handler ist kein Claim-Ergebnisclaim möglich).

---

## 4. Cleanup-Nachweis

Nach Abschluss aller Testblöcke:

| Prüfung | Ergebnis |
|---|---|
| DynamoDB `ItemCount` | **0** |
| GSI3 `PROCESSING#RUNNING` | **Count 0** |
| Main Queue visible/not-visible | **0 / 0** |
| DLQ visible/not-visible | **0 / 0** |
| Cognito-Pool users | **0** |
| Testbenutzer gelöscht | **JA** |
| Testorders/Fixtures gelöscht | **JA**, exakte Keys |
| Queue Purge | **NEIN** |

Ein temporärer Legacy-Fixture-Lauf (`ord_g3b1legacy7543469e`) wurde ebenfalls
bereinigt.

---

## 5. AWS-Ressourcen / Grenzen

Verwendet:

- `mays-orders-rc4-test-handler` (Lambda-Invoke für `processing/scan`)
- `mays-orders-rc4-test-sqs-worker`
- `mays-orders-rc4-test-orders-queue` / DLQ
- `mays-orders-rc4-test` DDB/GSI3
- ein synthetischer Cognito-Testbenutzer (gelöscht)
- API-Endpunkt `37fldhw7fi`

Nicht verwendet/geändert:

- Privacy-Funktionen (`privacy/inspect|export|erase`) — B2
- Terraform, IAM, Secrets, Lambda-Konfiguration, Cognito-Konfiguration
- Produktion/RIS
- Pipeline

---

## 6. Unerwartete Ereignisse

1. Legacy-Testfixture hatte zunächst kein `ord_`-Präfix → 400 statt 404;
   korrigierter Lauf mit gültigem ID-Format → 404. Testfehler, kein
   Produktdefekt.
2. DLQ-Cleanup war wegen verzögerter Zustellung zunächst unvollständig;
   beide eigenen Nachrichten wurden anschließend gezielt entfernt.
3. GSI3 `candidates` weicht vom alten Manifestwert ab (4 vs. 8), während
   `scanned`, `sent`, Skips und Status korrekt sind.

---

## 7. Verbleibende Risiken

- GSI3-Manifest sollte auf die tatsächliche `candidates`-Semantik abgestimmt
  werden; keine Produktänderung in B1.
- Foreign-Identity-Test braucht eine zweite autorisierte Testidentität.
- Privacy live bleibt B2/Secret-blockiert.
- Processing-Claim/Result ist ohne produktiven Processing-Handler nicht
  live prüfbar.
- DLQ-03/04 wurden nicht ausgeführt (optional).
- Keine G4-Freigabe; P00/API-Idempotenz/Processing/SEC-06 bleiben offen.

---

## 8. Ergebnisstatus

```text
G3-LIVE-B1: PARTIAL
DLQ-01/02: PASS
GSI3 Recovery (Sends/Skips/Status): PASS
GSI3 Candidate-Count-Vertrag: PARTIAL (Manifest 8 vs report 4)
GAP-01/02 Starvation: PASS
GAP-03 SHIPPED/Processing path: PASS
Compatibility: PASS (foreign identity BLOCKED)
Cleanup: VERIFIED
Privacy: NOT RUN (B2)
```

Keine Produktdatei geändert, kein Terraform, kein Push/Merge.

---

## 9. Auditlog / Commit

Vorgesehener Eintrag:

```text
MO-RC3-RC4-G3-LIVE-B1-01 → docs/reports/MO-RC3-RC4-G3-LIVE-B1-01.md
(autorisierte Live-Tests: DLQ-01/02 PASS, RC3/RC4 + PATCH + Legacy-404 PASS,
GSI3 10-Fixture-Recovery sent=4/status stabil, GAP-01/02 Starvation PASS,
GAP-03 SHIPPED idempotent PASS; candidates=4 vs Manifest 8 = PARTIAL;
Cleanup table/GSI3/queues/users 0; foreign identity BLOCKED; keine Privacy/
Terraform/Produktänderung, kein Push)
```

Commit nach diesem Bericht; Working Tree wird danach geprüft.
