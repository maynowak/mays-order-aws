# MO-RC3-RC4-G3-LIVE-E2E

**RC3/RC4 Live-E2E-Vorbereitung und Gate-1-Prüfung**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `8736dc88f571b95ed05e49b026865c4a38e3cf17`
**Modus:** Read-only Vorprüfung, danach **ausdrücklich freigegebene** Live-Suite
im RC4-Teststack; keine Produktions-/Terraform-Mutation, kein Push/Merge.

```text
G3 STATUS: PASS für die vorhandene Live-Suite
Gate 1: nach ausdrücklicher Freigabe erfüllt
Live-E2E: 4/4 PASS
Cleanup: VERIFIED (Tabelle 0, Queues 0, Testbenutzer 0)
```

---

## 1. Executive Summary

Nach der read-only Vorprüfung wurde das vorhandene Testbenutzer-Verfahren
(`docs/TEST-STRATEGY.md`, `scripts/tests/setup_test_user.py`) mit
ausdrücklicher Freigabe verwendet. Ein synthetischer Cognito-Testbenutzer
wurde angelegt, ein Access Token über `USER_PASSWORD_AUTH` beschafft und die
vier vorhandenen Live-E2E-Tests ausgeführt:

- **4/4 PASS** in 13,776 s,
- Order-Erstellung, Auth/Owner, Worker-Übergang und Datenintegrität,
- eigentümergebundener Cleanup über `E2E_SUBJECT`,
- Testbenutzer wieder gelöscht,
- Testtabelle 0 Items, Queue/DLQ 0 Nachrichten.

Ein durch die Cleanup-Race erzeugter DLQ-Testrest (eigene Test-Order) wurde
eigentümergebunden empfangen und gelöscht; kein Purge, keine fremde Nachricht.
Weitere Matrix-Szenarien (DLQ absichtlich, Recovery/GSI3, Privacy-Live) sind
nicht Teil der vorhandenen vier Live-Tests und bleiben separat offen.

---

## 2. Git- und Baseline-Prüfung

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `9484d1dc723f44dfef8de04e757aeff3cce7a86a` |
| G2-HEAD | identisch |
| Working Tree | CLEAN |
| Lokale Baseline | 1.153 PASS; 28 Seed-Tests separat |
| Live-E2E | 4 BLOCKED |

Wiederverwendete Nachweise:

- `docs/reports/MO-RC4-G1-EVIDENCE-SCOPE.md`
- `docs/reports/MO-RC3-RC4-G2-TEST-COMPLETION.md`
- `docs/reports/MO-RC4-AWS-TEST-UPGRADE-APPLY-07.md`
- `docs/reports/MO-RC4-AWS-TEST-FUNCTIONAL-VERIFY-08.md`

---

## 3. G3-A — Read-only AWS-Zustand

Abfragen mit Profil `mayaws`, Region `eu-central-1`, Account
`240571105849`; ausschließlich lesende AWS-Operationen.

### 3.1 DynamoDB-Teststack

| Feld | Ergebnis |
|---|---|
| Tabelle | `mays-orders-rc4-test` |
| Status | `ACTIVE` |
| ItemCount | **0** |
| GSIs | `gsi1` ACTIVE/INCLUDE, `gsi2` ACTIVE/INCLUDE, `gsi3` ACTIVE/KEYS_ONLY |

Hinweis: `ItemCount` ist die DynamoDB-Schätzung; der Stack ist aktuell leer.

### 3.2 Cognito-Testidentität

| Feld | Ergebnis |
|---|---|
| User-Pool | `eu-central-1_OZ7TK51EK` |
| `list-users` | **leer (`[]`)** |
| `TEST_USER_EMAIL` | nicht gesetzt |
| `TEST_USER_PASSWORD` | nicht gesetzt |
| `ACCESS_TOKEN` | nicht gesetzt |
| `COGNITO_CLIENT_ID` | nicht gesetzt |

**Gate 1 — Testidentität: FAIL.**

Es wurde kein Benutzer, Token oder Passwort erzeugt.

### 3.3 SQS / DLQ / Worker

| Ressource | Ergebnis |
|---|---|
| Queue | `mays-orders-rc4-test-orders-queue` |
| Sichtbare Nachrichten | **0** |
| Not visible | **0** |
| VisibilityTimeout | 60 s |
| Retention | 345600 s (4 Tage) |
| Redrive | DLQ `mays-orders-rc4-test-orders-queue-dlq`, `maxReceiveCount=1` |
| DLQ sichtbar/not visible | **0 / 0** |
| DLQ-Retention | 1209600 s (14 Tage) |

### 3.4 Lambda / API

| Ressource | Ergebnis |
|---|---|
| Handler | `mays-orders-rc4-test-handler`, `python3.14`, Timeout 10 s |
| Worker | `mays-orders-rc4-test-sqs-worker`, `python3.14`, Timeout 10 s |
| CodeSha256 | beide `vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=` |
| API | `mays-orders-rc4-test-api`, ID `37fldhw7fi` |
| API-Endpunkt | `https://37fldhw7fi.execute-api.eu-central-1.amazonaws.com` |
| Routen | `GET /orders`, `POST /orders`, `GET /orders/{orderId}`, `PATCH /orders/{orderId}/status` |

**Keine DELETE-Route** und keine öffentliche Erase-/Cleanup-Route vorhanden.

### 3.5 CloudWatch

Sieben RC4-Alarme sind im Status `OK`:

- `mays-orders-rc4-test-api-4xx`
- `mays-orders-rc4-test-api-5xx`
- `mays-orders-rc4-test-dlq-messages`
- `mays-orders-rc4-test-dynamodb-throttled`
- `mays-orders-rc4-test-lambda-duration`
- `mays-orders-rc4-test-lambda-errors`
- `mays-orders-rc4-test-lambda-throttles`

### 3.6 Aktuelle Stack-Version

Aus `MO-RC4-AWS-TEST-UPGRADE-APPLY-07` (Code `00125ee`):

- State serial **8**
- 39 managed resources
- `mo_version=0.2.0`
- GSI3 ACTIVE

Diese Werte wurden in G3 **nicht erneut über Terraform/State gelesen**;
sie sind ein bestätigter Snapshot aus 07, während die aktuelle AWS-Prüfung
Tabelle, GSIs, Queues, Lambdas, API und Alarme read-only bestätigte.

---

## 4. Gate-1-Ergebnis

| Voraussetzung | Status | Nachweis |
|---|---|---|
| Autorisierte Testidentität | **PASS (nach Freigabe)** | synthetischer Testbenutzer, danach gelöscht |
| Ownership-Nachweis | **PASS** | `E2E_SUBJECT` aus Access Token; Cleanup prüft gespeicherte `subjectId` |
| Sichere Cleanup-Fähigkeit | **PASS (freigegeben)** | exakter, eigentümergebundener Order-Delete; kein Purge, keine fremden Daten |
| Betroffene Ressourcen abgegrenzt | **PASS** | ausschließlich `mays-orders-rc4-test` |
| Explizite G3-Live-Freigabe | **PASS** | Nutzerfreigabe für Testbenutzer/Live-Tests/Cleanup |
| Keine Produktionsressourcen betroffen | **PASS** | Account/Region/Teststack; keine RIS/Produktion |

**Gate 1 = PASS.** Die Live-Suite wurde im freigegebenen RC4-Teststack
ausgeführt. Gate 2 im Sinne einer separaten Terraform-Mutation entfällt:
Es gab kein Terraform-Apply/Destroy/Import.

---

## 5. G3-B — RC3/RC4-Testmatrix

| Test | Erwartung | Vorbereitung | Live-Ergebnis |
|---|---|---|---|
| RC3-Legacy-Order | Body ohne `orderType` funktioniert | G2-Test; Live-POST ohne `orderType` | **PASS** |
| RC4-Order | Order mit Modulzuordnung wird verarbeitet | 10B-Komponentenpfad; Live-generic | **PASS** |
| Auth/Owner | Nur berechtigte Identitäten erhalten Zugriff | 401 unauthenticated; Owner-GET | **PASS** (fremde Identität nicht live getestet) |
| Persistenz | Order/Status korrekt gespeichert | Live-POST/GET; Cleanup danach | **PASS** |
| Worker | Order erreicht Consumer | Live-Queue → ESM → Worker → CONFIRMED | **PASS** |
| Retry/DLQ | Fehlerbehandlung vertragsgemäß | Terraform-Redrive; unbeabsichtigter Cleanup-DLQ-Rest bereinigt | **PARTIAL** — kein absichtlicher DLQ-Test |
| Recovery/GSI3 | Wiederherstellung funktioniert | GSI3 ACTIVE; Recovery-Scan nicht ausgeführt | **NOT EXECUTED** |
| Privacy | Inspect/Export/Erase/RETAIN | Service-/RETAIN-Tests; Live-Secret fehlt | **BLOCKED** |
| Cleanup | Synthetische Daten sicher bereinigen | eigentümergebundener Delete; Tabelle/Queue/User verifiziert | **PASS** |
| RC3→RC4 | Verträge bleiben kompatibel | Live-Legacy-Body ohne `orderType` | **PASS** (begrenzter Live-Nachweis) |

---

## 6. Gefundenes Testbenutzer-/Gate-Verfahren

Das im Projekt vorhandene Verfahren wurde gefunden; es wurde **nicht ausgeführt**,
weil es AWS-Mutationen (Cognito-Benutzer, Passwort, Gruppe) erfordert.

### 6.1 Quellen

| Quelle | Inhalt |
|---|---|
| `docs/TEST-STRATEGY.md:162-170` | „Test User Setup“ mit `setup_test_user.py` |
| `scripts/tests/setup_test_user.py` | legt Cognito-Testbenutzer an, setzt Passwort, fügt `staff` hinzu, ist für bestehende Benutzer idempotent |
| `tests/test-results.md:109-121` | Setup + manueller `ACCESS_TOKEN`-Schritt |
| `docs/reports/MO-RC4-DEV-INSTALL-LIFECYCLE-TEST-01-EXECUTION_LOG.md:34` | historischer E2E-Cleanup entfernte Order, DLQ-Nachricht und Testbenutzer |
| `/tmp/opencode/MO-RC4-LIFECYCLE-ORCHESTRATION-01.md` §2.1/2.3 | historische E2E- und Cleanup-Evidenz (nicht im Repo) |

### 6.2 Ablauf laut vorhandenem Verfahren

```text
export AWS_PROFILE=mayaws
export COGNITO_USER_POOL_ID=eu-central-1_OZ7TK51EK
export COGNITO_CLIENT_ID=415t3lt2k1umrmoaibn4f302sn
export TEST_USER_PASSWORD=<approved test password>
python3 scripts/tests/setup_test_user.py
# -> TEST_USER_EMAIL (random test-user_<hex>@example.com)
# -> ACCESS_TOKEN via USER_PASSWORD_AUTH erforderlich
```

Historischer Cleanup laut Lifecycle-Evidenz:

- Order-Item des eigenen Tests löschen,
- DLQ-Testnachricht empfangen/löschen (kein Purge),
- Cognito-Testbenutzer per `AdminDeleteUser` entfernen,
- Main-Queue unverändert lassen.

### 6.3 Ausführung nach Freigabe

1. Synthetischer Testbenutzer `test-user_ebdc0eb2@example.com` im
   RC4-Pool angelegt; Passwort nur über Umgebung, nicht protokolliert.
2. Access Token über `USER_PASSWORD_AUTH` beschafft; `sub` als
   `E2E_SUBJECT` verwendet.
3. Live-Suite mit `MO_E2E_LIVE=1` und
   `MO_E2E_LIVE_CLEANUP=1` ausgeführt.
4. Cleanup: eigene Order-Items per exaktem `pk`/`sk` und geprüfter
   `subjectId` gelöscht; Testbenutzer per `AdminDeleteUser` entfernt.

Live-Ergebnis:

```text
Ran 4 tests in 13.776s
OK
```

Nach dem Lauf:

```text
Cognito users:       0
DynamoDB ItemCount:  0
Main queue visible:  0
Main queue in-flight:0
DLQ visible:         0
DLQ in-flight:       0
```

Ein durch die Cleanup-Race erzeugter DLQ-Rest der eigenen Test-Order
(`ord_2e20adfe1318be9947b708aa`, Sender RC4-Testhandler) wurde per
`ReceiveMessage` + `DeleteMessage` entfernt; kein Purge, keine fremde
Nachricht. Die Test-Order war danach nicht mehr in der Tabelle.

### 6.4 Aktuelles Cleanup-Verfahren

`tests/e2e_harness.py::LiveCleanupBackend` löscht nur:

- exakten Order-Key `ord_<orderId>` / `#ORDER`,
- nach `GetItem`-Prüfung der gespeicherten `subjectId == E2E_SUBJECT`,
- mit Conditional Delete; fremde/fehlende Items werden nicht gelöscht.

`MO_E2E_LIVE_CLEANUP=1` ist ein expliziter Freigabeschalter. Ohne ihn bleiben
die Live-Tests `BLOCKED`.

## 7. Was nicht ausgeführt wurde

- Kein absichtlicher DLQ-/Retry-Test (nur Cleanup-Race-Rest bereinigt).
- Kein Recovery-/GSI3-Scan mit echten Daten.
- Kein Privacy-Inspect/Export/Erase-Live-Test (Live-Secret nicht
  provisioniert).
- Kein Terraform Plan/Apply/Destroy.
- Keine Backup-/Restore-Operation.
- Keine Produktions-/RIS-Ressource verändert.

Die vier vorhandenen Live-Tests wurden ausgeführt; die darüber
hinausgehenden Matrix-Szenarien bleiben offen.

---

## 8. Wiederverwendete Modul-/Builder-Evidence

- Builder: `MO-BUILDER-UPGRADE-P2-01`, 128 PASS.
- Installer: 10A/11A, 669 PASS; SEC-01…05 behoben; SEC-06 separat.
- Order: P02/P02I + 10B-Komponentenpfad + G2-Tests.
- Testsuite: 13A/G2; 1.153 PASS + 28 Seed PASS.
- AWS: Apply-07 und Functional-Verify-08 als Infrastruktur-/Blocked-Snapshot.

---

## 9. Offene Release-Blocker

1. Absichtlicher DLQ-/Retry-Test mit definierter Fehlernachricht.
2. GSI3-/Recovery-Live-Nachweis mit echten Daten.
3. Privacy-Inspect/Export/Erase/RETAIN live (Secret-Provisionierung).
4. Produktiver Processing-Handler über `generic`.
5. API-Idempotenz-Vertrag.
6. P00-Scope KMS/Secrets/Retention.
7. Vollständiger RC3→RC4-Live-Flow inkl. Bestandsdaten.

---

## 10. Voraussetzungen für G4

- G3-Gate 1 erfüllt: Testidentität und Ownership-Nachweis sind belegt.
- Cleanup-Verfahren ist implementiert und verifiziert.
- Separate Freigabe für DLQ-/Recovery-/Privacy-Live-Tests.
- Testmanifest mit exakten Ressourcen, Reihenfolge, Abbruchkriterien und
  Cleanup.
- Keine Produktionsressourcen betroffen.
- Ergebnisdokumentation mit Test-ID, Run-ID, Cleanup-Status und Evidence.

---

## 11. Ergebnisstatus

```text
G3-A: PASS (read-only Vorbereitung)
Gate 1: PASS (nach ausdrücklicher Freigabe)
Live-E2E: 4/4 PASS
Cleanup: VERIFIED (Testtabelle 0, Queues 0, Cognito-User 0)
G3: PASS für die vorhandene Live-Suite; tiefere Matrix-Szenarien offen
```

Es wurden ausschließlich synthetische Testdaten im RC4-Teststack erzeugt
und vollständig bereinigt. Kein Terraform, kein Push, kein Merge.

---

## 12. Git-Abschluss

```text
G3-Gate-Doku (blocked): fb475c05da335b2cd4d21acd37cd76da3205fd69
Live-Cleanup-Test:      e422330bb98562a35f5f189a2ee89aa6b82a81bf
Doku-Abschluss:         (dieser Commit)
Dateien:                docs/reports/MO-RC3-RC4-G3-LIVE-E2E.md
                        docs/AI_AUDITLOG.md
```

Kein Push, kein Merge. Der finale CLEAN-Status wird nach dem Doku-Commit
verifiziert.
