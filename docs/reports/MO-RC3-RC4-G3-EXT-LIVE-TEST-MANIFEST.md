# MO-RC3-RC4-G3-EXT — LIVE TEST MANIFEST

**Status:** `READY FOR LIVE APPROVAL` — **NOT EXECUTED**
**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `8736dc88f571b95ed05e49b026865c4a38e3cf17`
**Scope:** ausschließlich RC4-Teststack `mays-orders-rc4-test`

> Dieses Manifest ist die Voraussetzung für Gate B. Ohne neue ausdrückliche
> Nutzerfreigabe werden keine der unten genannten Mutationen ausgeführt.

---

## 1. Erlaubte Umgebung / Identität

| Feld | Wert |
|---|---|
| AWS Account | `240571105849` |
| Region | `eu-central-1` |
| Profil | `mayaws` (nur Teststack) |
| Tabelle | `mays-orders-rc4-test` |
| Queue | `mays-orders-rc4-test-orders-queue` |
| DLQ | `mays-orders-rc4-test-orders-queue-dlq` |
| API | `https://37fldhw7fi.execute-api.eu-central-1.amazonaws.com` |
| Lambda Handler | `mays-orders-rc4-test-handler` |
| Lambda Worker | `mays-orders-rc4-test-sqs-worker` |
| Cognito Pool | `eu-central-1_OZ7TK51EK` (`mays-orders-rc4-test-users`) |
| Cognito Client | `415t3lt2k1umrmoaibn4f302sn` |

Testidentität: **neu angelegter synthetischer Testbenutzer** über das
dokumentierte Verfahren (`scripts/tests/setup_test_user.py`); nur für den Lauf,
danach `AdminDeleteUser`. Kein Produktions-/RIS-Pool.

---

## 2. Erlaubte Mutationen (nur nach Freigabe)

| Mutation | Zweck | Begrenzung |
|---|---|---|
| Cognito `AdminCreateUser`, `AdminSetUserPassword`, `AdminAddUserToGroup` | Testidentität | genau ein Benutzer, danach löschen |
| `POST /orders` | Order-/Worker-/Legacy-Tests | run-scoped synthetische Orders |
| `SendMessage` an Test-Queue | DLQ-/Retry-Test | nur markierte Nachrichten |
| `ReceiveMessage`/`DeleteMessage` auf Test-DLQ | Cleanup eigener Nachrichten | kein Purge, keine fremden Messages |
| Lambda `Invoke` `processing/scan` | GSI3-Recovery-Test | nur Teststack, run-scoped |
| DynamoDB `PutItem`/`DeleteItem` | GSI3-Fixtures/Cleanup | nur exakte run-präfixierte Keys, nur wenn separat freigegeben |
| `AdminDeleteUser` | Testbenutzer-Cleanup | exakt der eine Testbenutzer |

**Verboten:** Terraform Apply/Destroy/Import, Queue-Purge, Produktions-/RIS-
Ressourcen, fremde Orders, Secrets erzeugen/ändern, IAM-Änderungen,
Cognito-Benutzer außerhalb des Testlaufs.

---

## 3. Testfälle

### 3.1 DLQ / Retry

| ID | Aktion | Erwartung | DDB-Write |
|---|---|---|---|
| G3X-DLQ-01 | Markierte malformed Nachricht an Main-Queue | Worker: parse failure, Main→DLQ, Order absent | nein |
| G3X-DLQ-02 | Markierte gültige Nachricht für nicht existierende synthetische Order | Worker: missing, Main→DLQ, DDB unverändert | nein |
| G3X-DLQ-03 (optional) | Eigene PENDING-Order + Nachricht `SHIPPED` | Worker: invalid transition, Status bleibt PENDING, DLQ | nein |
| G3X-DLQ-04 (control) | Eigene Order normal | PENDING→CONFIRMED, Main queue leer | ja (API) |

**Erwartete DLQ-Zustellung:** genau eine Worker-Verarbeitung pro Nachricht;
Main-Queue danach 0/0; DLQ +1 (bis 180 s), Body marker-/byte-identisch;
`maxReceiveCount=1`; keine Retry-Schleife. Der G3-Cleanup-Race-Rest zählt
**nicht** als DLQ-Test.

**Cleanup:** exakte `MessageId` + `testRunId` + `testId`; Receive/Delete
maximal eigener Nachrichten; kein Purge; danach Main/DLQ 0/0.

### 3.2 GSI3 / Recovery

| ID | Fixture/Aktion | Erwartung |
|---|---|---|
| G3X-GSI3-PRE-01 | Identity/Table/GSI3/Queue/Lambda/Schedules read-only | Baselines 0, ACTIVE, CodeSha `vW8n…` |
| G3X-GSI3-SETUP-02 | 10 run-präfixierte Items mit `processingState=running`, gestaffelten Claims | 10 exakte Keys, keine fremden |
| G3X-GSI3-IDX-03 | GSI3-Query `PROCESSING#RUNNING` | genau 8 Kandidaten |
| G3X-GSI3-RUN1-04 | `processing/scan limit=20` | Report: 8 candidates, 4 sent, Skips budget/cancelled/anonymized/not_running |
| G3X-GSI3-WRK-05 | Worker-Folgen | A/B/L unverändert, M CONFIRMED/version 3; keine Claim-Writes |
| G3X-GSI3-RUN2-06 | zweiter Scan | identischer Report; Duplikat NOOP, M version bleibt 3 |
| G3X-GSI3-ISO-07 | Fremd-/Legacy-IDs | nicht berührt/gesendet |
| G3X-GSI3-CLN-08 | exakte 10 Keys löschen | GSI3 0, Queue/DLQ 0, keine Reste |

**Bekannte Grenzen:** GAP-01/02 Starvation, GAP-03 Status `PROCESSING`/
`SHIPPED`; nur `generic` produktiv. Der Test darf diese Grenzen nicht als
Pass deklarieren; optionale Tests `G3X-GSI3-LIMIT-01`/`-PROC-02` dokumentieren
sie.

### 3.3 Privacy

**Live aktuell BLOCKED:** `PRIVACY_INTERNAL_SECRET` nicht provisioniert,
kein `lambda:InvokeFunction`-Testprinzipal, F-PRV-01 bestätigt.

| ID | Aktion | Erwartung |
|---|---|---|
| G3X-PRV-X01 | Inspect Subject A | 200, COMPLETED, 2 refs, keine PII |
| G3X-PRV-X02 | falsches Projekt | 400, kein DDB-Read |
| G3X-PRV-X03 | falsches internal_token | 400 |
| G3X-PRV-X04 | `authorized=false` | 400 |
| G3X-PRV-X05 | Export A | COMPLETED, 2, keine internen Felder |
| G3X-PRV-X06 | Export B | nur B, A fehlt |
| G3X-PRV-X07 | Erase PREVIEW A | PREVIEW, 2 geplant, keine Mutation |
| G3X-PRV-X08 | Erase EXECUTE ohne Policy | BLOCKED, keine Mutation |
| G3X-PRV-X09 | Erase B | 1 gelöscht, Wiederholung idempotent |
| G3X-PRV-X10 | RETAIN A | PARTIALLY_COMPLETED, 2 retained, keine Mutation |
| G3X-PRV-X11 | ANONYMIZE eine Order | 1 anonymisiert, Owner-GET 404 |
| G3X-PRV-X12 | Consumer-Scope-Erase | **expected defect F-PRV-01**: 0 affected/limitation; als DEFECT dokumentieren |
| G3X-PRV-X13 | Secret fehlt | 400, kein Datenzugriff |

Cleanup: ERASE bereits gelöscht; RETAIN/ANONYMIZE eigene Keys mit SKU-/Run-
Marker; für ANONYMIZE ist `LiveCleanupBackend` nicht ausreichend
(`subjectId` entfernt) — separater, freigegebener Key-Cleanup nötig.

### 3.4 RC3/RC4 Compatibility

| ID | Aktion | Erwartung |
|---|---|---|
| G3X-COMPAT-01 | POST ohne `orderType` | 201, PENDING, generic, Owner/GSI2 |
| G3X-COMPAT-02 | POST mit namespaced `orderType` | 201, gespeichert; unbekannter Typ → Worker Batch-Failure/DLQ |
| G3X-COMPAT-03 | GET/PATCH own order | 200/200; ungültiger Übergang 409 |
| G3X-COMPAT-04 | fremde Identität | 404 (zweiter Testbenutzer nötig) |
| G3X-COMPAT-05 | RC3-Bestandsorder ohne `subjectId` | **erwartet 404**; Migration separat entscheiden |

---

## 4. Abbruchbedingungen

- Keine neue ausdrückliche Live-Freigabe / kein Testmanifest akzeptiert.
- Account/Region/Stack/Profile nicht wie oben.
- GSI3/Queue/DLQ/Item-Baseline nicht 0; fremde Daten vorhanden.
- Lambda-CodeSha/Runtime/State abweichend.
- Sender-IAM für Queue/DLQ/Lambda nicht nachgewiesen.
- Fremde Order-ID/Nachricht ohne Run-Marker in Reichweite.
- Unerwartete Status-/Versionsänderung, fremder Write, unerwarteter DLQ-
  Zustand, Cleanup-Fehler.
- Jede Produkt-/Terraform-/IAM-/Secret-Änderung erforderlich.

---

## 5. Cleanup und Nachweis

- Testbenutzer exakt löschen, `list-users` = 0.
- Eigene Orders nur per exaktem `pk`/`sk` + `subjectId`/Run-Marker löschen;
  ANONYMIZE separat per Key/Marker.
- DLQ nur markierte eigene Nachrichten per ReceiptHandle; kein Purge.
- Main-Queue/DLQ nach Lauf 0/0; Tabelle 0 Items; GSI3 0.
- Evidence: Test-ID, Run-ID, MessageIds, Snapshots, Cleanup-Status, keine
  Tokens/Passwörter/PII.
- Keine Terraform-/State-Änderung.

---

## 6. Gate-Status

```text
Gate A (read-only preparation): PASS
Gate B (new mutating live tests): BLOCKED — NEW APPROVAL REQUIRED
Gate C (product changes): NOT APPLICABLE / separate approval
Overall: READY FOR LIVE APPROVAL — NOT EXECUTED
```
