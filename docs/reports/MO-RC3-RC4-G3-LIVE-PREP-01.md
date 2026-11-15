# MO-RC3-RC4-G3-LIVE-PREP-01

**AWS Deployment Verification & Live-Test Readiness**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `39c5feef9d49aec767cc639a00eae12f7a394f1c`
**Modus:** ausschließlich lesende AWS-/Repository-Prüfung; keine Mutation,
kein Terraform, keine SQS-Nachricht, kein Lambda-Invoke, kein Deployment,
kein Push/Merge.

```text
STATUS: DEPLOYMENT UPDATE REQUIRED
LOCAL G3-FIX CODE != DEPLOYED AWS CODE
```

---

## 1. Executive Summary

Die AWS-Testumgebung ist erreichbar und konsistent, aber sie läuft **nicht**
mit dem lokal korrigierten G3-FIX-Stand.

Zentrale Erkenntnis:

- Lokales G3-FIX-Artefakt: SHA-256 `1584ee0d…`, Lambda-Base64 `FYTuDcz…`.
- Deployed Handler/Worker: CodeSha256 `vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=`.
- Dieses AWS-Artefakt entspricht exakt dem **alten** ZIP vor dem G3-FIX-Build
  (`75a32fc^`, SHA `bd6f2795…`), nicht dem lokalen korrigierten ZIP.
- F-PRV-01 und GSI3-GAP-01/02/03 sind daher **lokal implementiert, aber nicht
  deployed**.
- Privacy ist zusätzlich durch fehlendes `PRIVACY_INTERNAL_SECRET` und fehlende
  Invoke-Berechtigung blockiert.
- DLQ/Recovery-Infrastruktur ist vorhanden, aber die Recovery-/Privacy-Fixes
  können gegen den aktuellen Stack nicht nachgewiesen werden.

**Daher: `DEPLOYMENT UPDATE REQUIRED` — nicht `READY FOR G3-LIVE APPROVAL`.**

Es wurden keine AWS-Mutationen ausgeführt.

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `39c5feef9d49aec767cc639a00eae12f7a394f1c` |
| Working Tree | CLEAN |
| G3-FIX | `7d82ad4`, `51094bf`, `75a32fc`, `39c5fee` |
| Lokale Baseline | 1.158 PASS (669 Installer, 128 Builder, 345 Lambda, 16 E2E) |
| Seed | 28 PASS separat |
| Live-Basis | G3 4/4 PASS gegen den **alten** deployed Code |

---

## 3. Agentenstatus

| Agent | Ergebnis |
|---|---|
| A — Lambda Deployment & Artifact Identity | **MISMATCH**: lokales G3-FIX-ZIP ≠ AWS CodeSha; Deployment Update Required |
| B — DLQ & Recovery Infrastructure | Infrastruktur read-only PASS; keine Recovery-Schedules; korrigierter Code nicht deployed |
| C — Privacy Infrastructure | **BLOCKED**: kein Secret, kein Invoke-Recht, GSI2 ohne `consumerId`, Fix nicht deployed |
| D — Compatibility & Release Boundaries | Read-only; RC3/RC4-Grenzen und offene Releaseentscheidungen dokumentiert |

Die AWS-Prüfungen wurden ausschließlich lesend durchgeführt. Es gab keine
Agenten-Schreibzugriffe.

## 4. AWS-Account-/Ressourcenidentität

| Feld | Wert |
|---|---|
| Profil | `mayaws` |
| Account | `240571105849` |
| Region | `eu-central-1` |
| Caller | `arn:aws:iam::240571105849:user/Mayaws` |
| Teststack | `mays-orders-rc4-test` |
| Lambda Handler | `mays-orders-rc4-test-handler` |
| Lambda Worker | `mays-orders-rc4-test-sqs-worker` |
| API | `37fldhw7fi` (`https://37fldhw7fi.execute-api.eu-central-1.amazonaws.com`) |
| DynamoDB | `mays-orders-rc4-test`, ACTIVE, 0 Items |
| Queue | `mays-orders-rc4-test-orders-queue` |
| DLQ | `mays-orders-rc4-test-orders-queue-dlq` |
| Cognito-Pool | `eu-central-1_OZ7TK51EK` (`mays-orders-rc4-test-users`) |

Keine anderen Profile oder Ressourcen wurden verwendet. Keine Produktions-/
RIS-Ressource wurde berührt.

---

## 5. Lambda-Artefaktvergleich

### 4.1 Vergleichsmatrix

| Komponente | Lokal | AWS | Ergebnis |
|---|---|---|---|
| API-Lambda | ZIP SHA-256 `1584ee0d…`; Base64 `FYTuDcz…` | CodeSha `vW8nlTjAd9b+…` | **MISMATCH** |
| Worker-Lambda | derselbe ZIP | CodeSha `vW8nlTjAd9b+…` | **MISMATCH** |
| Recovery-Code | G3-FIX lokal | deployed alter Code | **UNVERIFIED / nicht deployed** |
| Privacy-Code | G3-FIX lokal | deployed alter Code | **UNVERIFIED / nicht deployed** |
| DynamoDB GSI2 | Codefix lädt vollständiges Item | Projektion ohne `consumerId` | **kein Infra-Update nötig**, Deploy nötig |
| DynamoDB GSI3 | KEYS_ONLY erwartet | ACTIVE, KEYS_ONLY | **PASS** |

### 4.2 Eindeutige Zuordnung des AWS-Artefakts

```text
Lokales G3-FIX-ZIP (75a32fc/39c5fee):
  SHA-256 1584ee0dcccd0b042277827184575a1876c159c75a7a0e95ccd29b4fe5a37e44
  Base64  FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=

AWS Lambda Handler + Worker:
  CodeSha256 vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=
  LastModified 2026-11-11T17:52:19Z / 17:52:25Z

Altes ZIP vor G3-FIX (75a32fc^):
  SHA-256 bd6f279538c077d6fe1778d8a7ed67b0a6760314416030429de5e14a69dcd323
  Base64  vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=  (MATCH)
```

Damit ist die Deployment-Identität **eindeutig verifiziert als alt**:
Der Stack läuft mit `bd6f2795…`, nicht mit dem G3-FIX-Artefakt.

### 4.3 Enthaltene Fixes

Im lokalen G3-FIX-ZIP nachweisbar:

- `order_service.py`: GSI2-Query nur `orderId`, anschließendes vollständiges
  `GetItem` für `consumerId` (F-PRV-01).
- `recovery.py`: `scan_limit`, Skip-/Limit-Trennung, aktueller Zielstatus
  (GSI3-GAP-01/02/03).
- `index.py`: `_send_processing_recovery(order_id, status=...)`.

Im deployed Code sind diese Marker nicht enthalten; der alte `erase_subject`
verwendet weiterhin die nicht projizierte `consumerId`-Quelle, Recovery sendet
weiterhin fix `CONFIRMED`.

---

## 6. DLQ-/Recovery-Infrastruktur

### 5.1 SQS

| Feld | Wert |
|---|---|
| Main Queue sichtbar/in-flight | 0 / 0 |
| DLQ sichtbar/in-flight | 0 / 0 |
| Visibility | 60 s |
| Main Retention | 345600 s (4 Tage) |
| DLQ Retention | 1209600 s (14 Tage) |
| Redrive | DLQ `mays-orders-rc4-test-orders-queue-dlq`, `maxReceiveCount=1` |

### 5.2 ESM / Worker

| Feld | Wert |
|---|---|
| Event Source Mapping | `dbde8c61-c116-42f1-97e6-782edd900c3d` |
| State | `Enabled` |
| Batch Size | 5 |
| FunctionResponseTypes | `ReportBatchItemFailures` |
| Worker Timeout | 10 s |
| Worker IAM | `sqs:ReceiveMessage/DeleteMessage/GetQueueAttributes` nur Main-Queue; kein DLQ-Zugriff |

**Konsequenz:** DLQ-Redrive ist vorhanden; der Worker kann die DLQ nicht selbst
bereinigen. Cleanup muss durch eine freigegebene Operator-Identität erfolgen
(Receive/Delete eigener Nachrichten; kein Purge).

### 5.3 GSI3 / Recovery

| Feld | Wert |
|---|---|
| GSI3 | `ACTIVE`, `KEYS_ONLY` |
| GSI3 Query `PROCESSING#RUNNING` | Count 0 |
| Recovery Schedules | **keine** |
| Handler/Worker State | `Active`, LastUpdate `Successful` |
| Handler-Env | `ORDERS_TABLE`, `SQS_QUEUE_URL`, `ORDERS_PROJECT_NAME` |
| Worker-Env | `ORDERS_TABLE` |

**Konsequenz:** Recovery-Infrastruktur ist vorhanden, aber die korrigierte
Recovery-Logik ist nicht deployed. Ein Live-Recovery-Test gegen den aktuellen
Stack würde den **alten** Code prüfen.

### 5.4 IAM

Handler-Rolle:

- DynamoDB `PutItem/GetItem/UpdateItem/DeleteItem/Query` auf Tabelle,
- `dynamodb:Query` auf GSI1/GSI2/GSI3,
- `sqs:SendMessage` auf Main Queue,
- Logs.

Worker-Rolle:

- DynamoDB `GetItem/UpdateItem` auf Tabelle,
- SQS Receive/Delete/GetAttributes auf **Main Queue only**,
- Logs.

Nicht vorhanden:

- `lambda:InvokeFunction` für einen Privacy-Test-Principal,
- DLQ-Receive/Delete für Worker,
- `PRIVACY_INTERNAL_SECRET`-Provisionierung.

---

## 7. Privacy-Infrastruktur

| Prüfung | Ergebnis |
|---|---|
| `PRIVACY_INTERNAL_SECRET` in Handler-Env | **NEIN** |
| Secrets-Manager/SSM/KMS-Referenz | **NEIN** (keine IaC-Ressource) |
| Privacy-Handler | vorhanden (`privacy/inspect|export|erase`), aber ohne Secret nur Blocked |
| Lambda-Invoke-Recht | **NEIN** für Testprinzip |
| GSI2-Projektion | ohne `consumerId` |
| Code-Fix F-PRV-01 | lokal vorhanden, **nicht deployed** |

**Live-Privacy bleibt doppelt blockiert:** fehlende Secret-Provisionierung und
fehlende Invoke-Berechtigung; zusätzlich ist der korrigierte Code nicht im
AWS-Stack. Es wurden keine Secret-Werte gelesen oder protokolliert.

---

## 8. Compatibility-Grenzen

| Bereich | Status |
|---|---|
| RC3-Body ohne `orderType` | lokal/G3 live PASS gegen alten Code; G3-FIX ändert Body nicht |
| RC4-`orderType` | lokal getestet; expliziter Live-Test nicht ausgeführt |
| JWT-Owner-Isolation | G3 live Owner-Pfad PASS; fremde Identität nicht live |
| Statusmaschine | unverändert |
| SQS/Worker | alter Code deployed; Fixes nicht aktiv |
| API-Idempotenz | **nicht implementiert**; Vertrag offen |
| Processing-Handler | produktiv nur `generic` |
| GSI3/Recovery | Infrastruktur; korrigierter Code nicht deployed |
| P00 KMS/Secrets/Retention | **nicht implementiert / Scope offen** |
| SEC-06 | `CONTRACT GAP / NEEDS DECISION` |
| RIS-Pin / Auto-Apply | unverändert; `directAWSGit` bleibt Risiko |

---

## 9. G3-LIVE-Freigabematrix

### B1 — DLQ / Recovery / Compatibility

| Testgruppe | Ressourcen | Voraussetzungen | Erforderliche Mutationen | Erwartung | Cleanup | Abbruch | Deployment-Abhängigkeit | Status |
|---|---|---|---|---|---|---|---|---|
| G3X-DLQ-01/02 | Main Queue, DLQ, Worker | Test-Run-ID, Sender-Recht | SendMessage; Receive/Delete eigene DLQ-Nachricht | malformed/missing → DLQ, kein DDB-Write | eigene Receive/Delete, kein Purge | Baseline/Deploy/Fremdmarker | **G3-FIX Deploy erforderlich** | **BLOCKED** |
| G3X-DLQ-03/04 | Main Queue, DLQ, API/Worker | Testidentität, Order | SendMessage, ggf. eigene Order | invalid transition → DLQ; control CONFIRMED | Order/Message cleanup | Status/Version/Queue | **G3-FIX Deploy erforderlich** | **BLOCKED** |
| GSI3-Recovery-Live | DDB, GSI3, Lambda | Invoke-Recht, Testfixtures | DDB Put/Delete, processing/scan Invoke | 8 Kandidaten/4 sends, no writes | exakte Keys, GSI3/Queue 0 | GAP-01/02/03, fremde Daten | **G3-FIX Deploy erforderlich** | **BLOCKED** |
| Compatibility | API, Cognito, DDB | Testidentität, Cleanup | POST/GET/PATCH, optional 2. User | RC3/RC4 contract, owner isolation | eigene Orders/User | Deploy/Queue/Status | teils alter Code; G3-FIX Deploy empfohlen | **BLOCKED/PARTIAL** |

### B2 — Privacy

| Testgruppe | Ressourcen | Voraussetzungen | Erforderliche Mutationen | Erwartung | Cleanup | Abbruch | Deployment-Abhängigkeit | Status |
|---|---|---|---|---|---|---|---|---|
| G3X-PRV-X01…X13 | DDB, GSI2, Lambda Invoke | Secret provisioniert, Invoke-Rolle, Testuser, orders | Seed orders, internal invoke, erase/anonymize | inspect/export/erase/RETAIN, no foreign | owner/key cleanup, User delete | Secret/Projekt/Ownership/Invoke | **G3-FIX Deploy + Secret/IAM-Entscheidung** | **BLOCKED** |

**Kernaussage:** Keine neuen Live-Tests sind gegen den aktuellen AWS-Stack
sinnvoll, solange der korrigierte G3-FIX-Code nicht deployed ist. DLQ-Tests
würden den alten Worker prüfen; Recovery-/Privacy-Tests die alten Defekte.

---

## 10. Benötigte AWS-Mutationen für einen späteren Lauf

Nur nach separater Freigabe:

1. **Lambda-Update** von Handler + Worker auf das G3-FIX-Artefakt
   (`1584ee0d…`, Base64 `FYTuDcz…`).

   **Nicht in diesem Auftrag ausgeführt.**
2. Testbenutzer/Token über das dokumentierte Verfahren (nur bei freigegebenem
   Live-Lauf).
3. Test-Orders / SQS-Testnachrichten / GSI3-Fixtures.
4. Für Privacy zusätzlich:
   - Secret-Provisionierung (Entscheidung: Env/Secrets Manager/SSM),
   - `lambda:InvokeFunction`-Testrolle,
   - danach Testdaten und Secret-Lebenszyklus.

Keine automatische Terraform-/Deployment-Ausführung.

---

## 11. Cleanup- und Abbruchplan

- Nur Teststack `mays-orders-rc4-test`.
- Testbenutzer exakt löschen; `list-users` = 0.
- Eigene Orders exakt per `pk`/`sk` + `subjectId`/Run-Marker löschen.
- DLQ nur markierte eigene Nachrichten per Receive/Delete; **kein Purge**.
- GSI3-Fixtures nur exakt run-präfixiert löschen; keine Fremddaten.
- Nachweis: Tabelle 0, Main Queue 0/0, DLQ 0/0, GSI3 0.
- Abbruch bei fremden Daten, unerwartetem Lambda-Code, fehlender Ownership,
  fehlender Freigabe oder abweichendem Account/Region.
- Keine Secrets/Tokens/Passwörter in Reports.

---

## 12. Auditlog-Nachweis

Vorgesehener Eintrag:

```text
MO-RC3-RC4-G3-LIVE-PREP-01 → docs/reports/MO-RC3-RC4-G3-LIVE-PREP-01.md
(read-only AWS: Account/Stack bestätigt; lokales G3-FIX-ZIP 1584ee0d… ≠
AWS CodeSha vW8nl…; AWS entspricht altem ZIP bd6f2795…; GSI2 ohne consumerId,
GSI3 ACTIVE, DLQ/Redrive/ESM 0/0, keine Schedules, Privacy-Secret/Invoke fehlt;
G3-FIX nicht deployed → DEPLOYMENT UPDATE REQUIRED; keine AWS-/Terraform-
Mutation, kein Push)
```

---

## 13. Ergebnisstatus

```text
STATUS: DEPLOYMENT UPDATE REQUIRED
Ready for G3-Live: NO
Mutation in this run: NONE
```

Der aktuelle Teststack ist **infrastrukturell** für DLQ/Recovery vorbereitet,
aber der **korrigierte G3-FIX-Code ist nicht deployed**. Privacy bleibt
zusätzlich durch Secret- und Invoke-Voraussetzungen blockiert.

**Keine automatische Live-Ausführung. STOP nach Bericht und Commit.**
