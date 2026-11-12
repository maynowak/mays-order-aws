# MO-RC3-RC4-G3-LIVE-E2E

**RC3/RC4 Live-E2E-Vorbereitung und Gate-1-Prüfung**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `9484d1dc723f44dfef8de04e757aeff3cce7a86a`
**Modus:** Read-only AWS-/Repository-Prüfung; **keine mutierenden Live-Tests**,
keine Testdaten, keine SQS-Nachrichten, keine Cognito-Änderungen, keine
Terraform-Mutation, kein Push/Merge.

```text
G3 STATUS: BLOCKED — GATE 1 NICHT ERFÜLLT
STOP NACH G3-A
```

---

## 1. Executive Summary

Die G3-A-Voraussetzungsprüfung wurde durchgeführt. Der RC4-Teststack ist
weiterhin vorhanden und konsistent, aber die **Live-Ausführung ist nicht
freigegeben**:

- Keine autorisierte Cognito-Testidentität vorhanden
  (`list-users` liefert eine leere Liste).
- Keine `ACCESS_TOKEN`/`TEST_USER_*`-Werte in der Umgebung.
- Keine sichere, öffentliche, eigentümergebundene Order-Delete-/Cleanup-Route
  (API hat nur GET/POST/PATCH; kein DELETE).
- Keine ausdrückliche G3-Live-Freigabe für mutierende AWS-Aufrufe.

Damit ist **Gate 1** nicht erfüllt. Es wurden keine mutierenden Live-Tests
ausgeführt. Die vier Live-E2E-Tests bleiben **BLOCKED**.

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
| Autorisierte Testidentität | **FAIL** | Cognito-Pool leer, keine Env-Tokens |
| Ownership-Nachweis | **BLOCKED** | ohne Identität nicht prüfbar |
| Sichere Cleanup-Fähigkeit | **FAIL** | keine DELETE-/Cleanup-API; keine direkte DDB-Löschung erlaubt |
| Betroffene Ressourcen abgegrenzt | **PASS** | Teststack `mays-orders-rc4-test`, Account/Region/Queues/API bestätigt |
| Explizite G3-Live-Freigabe | **FAIL** | keine separate Freigabe für mutierende AWS-Aufrufe |
| Keine Produktionsressourcen betroffen | **PASS** | ausschließlich RC4-Teststack read-only geprüft |

**Gate 1 = BLOCKED.** Gate 2 (AWS-Mutationsfreigabe) wurde nicht beantragt.

---

## 5. G3-B — RC3/RC4-Testmatrix

Alle Zeilen sind vorbereitet; mutierende Live-Ausführung bleibt bis Gate 1/2
gesperrt.

| Test | Erwartung | Vorbereitung | Live-Ergebnis |
|---|---|---|---|
| RC3-Legacy-Order | Body ohne `orderType` funktioniert | G2-Test `test_rc3_legacy_payload_without_order_type_keeps_contract` | **BLOCKED** |
| RC4-Order | Order mit Modulzuordnung wird verarbeitet | 10B-Komponentenpfad; G2-Unknown-Type-Test | **BLOCKED** |
| Auth/Owner | Nur berechtigte Identitäten erhalten Zugriff | Identity-/Owner-Tests; Testidentität fehlt | **BLOCKED** |
| Persistenz | Order/Status korrekt gespeichert | Fake-DDB; Live-DDB leer | **BLOCKED** |
| Worker | Order erreicht Consumer | Fake-SQS/Worker; Live-Queue 0 | **BLOCKED** |
| Retry/DLQ | Fehlerbehandlung vertragsgemäß | 10B Batch-Fehler; Terraform-Redrive | **BLOCKED** |
| Recovery/GSI3 | Wiederherstellung funktioniert | P02I-Tests; GSI3 ACTIVE, keine Daten | **BLOCKED** |
| Privacy | Inspect/Export/Erase/RETAIN | Service-/RETAIN-Tests; Live-Secret/Identität fehlt | **BLOCKED** |
| Cleanup | Synthetische Daten sicher bereinigen | E2E-Harness-Ownership; keine Delete-API | **BLOCKED** |
| RC3→RC4 | Verträge bleiben kompatibel | G2-Legacy/Contract-Tests; kein Live-Flow | **BLOCKED** |

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

### 6.3 Warum das Gate trotzdem blockiert bleibt

1. Das Verfahren erzeugt einen **neuen Cognito-Benutzer und Credentials**; dafür
   fehlt die ausdrückliche G3-Mutationsfreigabe.
2. `setup_test_user.py` setzt `COGNITO_USER_POOL_ID` erst **nach** dem
   `admin_create_user`; ohne explizit gesetzte Pool-ID würde es den
   Platzhalter `eu-central-1_XXXXXXXX` verwenden.
3. Das Skript erzeugt keinen Token; `ACCESS_TOKEN` muss separat über
   `USER_PASSWORD_AUTH` beschafft werden.
4. Der aktuelle E2E-Harness verlangt zusätzlich `MO_E2E_LIVE=1`,
   `API_BASE_URL` und `LIVE_CLEANUP_AVAILABLE=True`. Letzteres ist derzeit
   bewusst `False`, weil keine sichere API-Cleanup-Route existiert.
5. Der historische Cleanup nutzt direkte DynamoDB-Löschung für das eigene
   Order-Item. Das ist mit der in 10C/G2 beschlossenen Cleanup-Sicherheit
   nicht ohne ausdrückliche Freigabe vereinbar.

**Gate 1 bleibt daher BLOCKED.** Das Verfahren ist dokumentiert, aber nicht
autorisiert und nicht ausgeführt.

## 7. Was nicht ausgeführt wurde

- Kein `POST /orders`.
- Kein `GET`/`PATCH` gegen die Live-API.
- Keine SQS-Nachricht gesendet.
- Keine Cognito-Anlage/-Authentifizierung.
- Kein DynamoDB-Write/Delete.
- Kein Terraform Plan/Apply/Destroy.
- Keine Backup-/Restore-Operation.
- Keine Live-E2E-Ausführung.

Die vier Live-Tests wurden lokal ohne Opt-in ausgeführt und blieben
erwartungsgemäß **4 SKIP/BLOCKED**.

---

## 8. Wiederverwendete Modul-/Builder-Evidence

- Builder: `MO-BUILDER-UPGRADE-P2-01`, 128 PASS.
- Installer: 10A/11A, 669 PASS; SEC-01…05 behoben; SEC-06 separat.
- Order: P02/P02I + 10B-Komponentenpfad + G2-Tests.
- Testsuite: 13A/G2; 1.153 PASS + 28 Seed PASS.
- AWS: Apply-07 und Functional-Verify-08 als Infrastruktur-/Blocked-Snapshot.

---

## 9. Offene Release-Blocker

1. Autorisierte, vorab provisionierte Testidentität.
2. Sichere, eigentümergebundene Live-Cleanup-Fähigkeit.
3. Explizite AWS-Mutationsfreigabe für einen definierten Testlauf.
4. Funktionale DLQ-/Retry-Zustellung.
5. GSI3-/Recovery-Live-Nachweis.
6. Produktiver Processing-Handler über `generic`.
7. API-Idempotenz-Vertrag.
8. P00-Scope KMS/Secrets/Retention.
9. Aktueller RC3→RC4-Live-Kompatibilitätsnachweis.

---

## 10. Voraussetzungen für G4

- G3-Gate 1 erfüllt: autorisierte Testidentität und Ownership-Nachweis.
- G3-Gate 2 erfüllt: schriftliche Freigabe für konkrete AWS-Mutationen.
- Definiertes, getestetes Cleanup-/Ownership-Verfahren.
- Testmanifest mit exakten Ressourcen, Reihenfolge, Abbruchkriterien und
  Cleanup.
- Keine Produktionsressourcen betroffen.
- Separate Freigabe für DLQ-/Recovery-/Privacy-Live-Tests.
- Ergebnisdokumentation mit Test-ID, Run-ID, Cleanup-Status und Evidence.

---

## 11. Ergebnisstatus

```text
G3-A: PASS (read-only Vorbereitung)
Gate 1: BLOCKED
Gate 2: NOT REQUESTED
Live-E2E: NOT EXECUTED
G3: BLOCKED — STOP nach G3-A
```

Es wurden keine AWS-Mutationen, keine Testdaten und keine Live-Requests
erzeugt. Kein Push, kein Merge.

---

## 12. Git-Abschluss

Vorgesehen:

```text
Commit: docs(rc3,rc4): record g3 live e2e gate status
Dateien: docs/reports/MO-RC3-RC4-G3-LIVE-E2E.md
         docs/AI_AUDITLOG.md
```

Commit-SHA und CLEAN-Status werden nach dem Commit verifiziert.
