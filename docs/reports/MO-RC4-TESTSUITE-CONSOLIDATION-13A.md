# MO-RC4-TESTSUITE-CONSOLIDATION-13A

**Konsolidierung der RC4-Testsuite und Priorisierung offener Nachweise**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor Analyse:** `a0dec8161960a0375928acd0f7753c54f9f89d3f`
**Modus:** Analyse, Testinventur und Dokumentation; keine Produktcodeänderung,
keine AWS-/Cognito-/HTTP-Aufrufe, keine Terraform-Mutation, kein Push/Merge.

---

## 1. Executive Summary

Die aktuelle lokale Testsuite ist umfangreich und für die **lokale**
Order-Verarbeitung deutlich belastbarer als der alte Stand:

- **1.150 lokale Tests PASS** in der konsolidierten Baseline,
- zusätzlich **28 Seed-Tool-Tests PASS** (separat, nicht in der Baseline),
- **4 Live-E2E-Tests BLOCKED**,
- Coverage: Lambda **90,15 % / 82,22 %**, Builder **91,22 % / 84,93 %**,
  Installer **74,08 % / 64,04 %**, E2E-Harness separat **91,58 % / 88,46 %**
  (Statement/Branch).

Die Suite ist aber **kein Nachweis einer produktiven AWS-Integration**:

- Nahezu alle Order-Tests verwenden Fakes/Mocks; echte Cognito-, API-Gateway-,
  SQS-, DynamoDB- und GSI3-Interaktionen fehlen.
- Die authentifizierte Live-E2E-Suite ist ohne Testidentität und ohne sichere
  Bereinigung **BLOCKED**.
- DLQ, reale Worker-Retries, reale GSI3-Nutzung und Live-Cleanup sind nicht
  funktional nachgewiesen.
- Der ursprüngliche RC4-Plan (P00) enthält KMS-, Secrets-Manager-,
  Retention- und Cancel-Lifecycle-Pakete, die im aktuellen Order-Code **nicht
  implementiert** sind. Ob sie zum RC4-Order-Releaseumfang gehören, ist eine
  offene Scope-/Release-Entscheidung.
- Die Dokumentation ist teilweise veraltet: `PROJECT_STATUS`, README und
  `phase2-async-order-ingest.md` beschreiben einen älteren Stand als Code und
  letzte RC4-Reports.

**Gesamturteil:** Die RC4-Testsuite ist für den **lokal implementierten
Order-Kern** weitgehend belastbar, aber für einen **RC4-Gesamtfreigabe** nicht
vollständig. Die kritischen offenen Nachweise liegen bei Live-Integration,
DLQ/Retry, Processing-Aktivierung, Authentifizierungs-/Cleanup-Voraussetzungen
und der Klärung des ursprünglichen RC4-Scopes.

---

## 2. Verwendete Quellen

### Code

- `lambda/src/index.py`
- `lambda/src/order_service.py`
- `lambda/src/sqs_handler.py`
- `lambda/src/order_handlers.py`
- `lambda/src/identity.py`
- `lambda/src/state_machine.py`
- `lambda/src/validation.py`
- `lambda/src/recovery.py`
- `lambda/src/processing_result.py`
- `terraform/modules/api/main.tf`
- `terraform/modules/dynamodb/main.tf`
- `terraform/modules/sqs/main.tf`
- `terraform/modules/sqs-worker/main.tf`
- `terraform/modules/lambda/main.tf`
- `installer/core/*.py`, `installer/cli/main.py`

### Fachliche Dokumente

- `docs/reports/MO-RC4-P00-BASELINE.md`
- `docs/reports/MO-RC4-P00-MODULE-PLAN.md`
- `docs/reports/MO-RC4-P00-OPEN-QUESTIONS.md`
- `docs/reports/MO-RC4-P01-CONTRACT-INVENTORY.md`
- `docs/reports/MO-RC4-P02-ORDER-OWNERSHIP.md`
- `docs/reports/MO-RC4-P02A-*`, `P02C-*`, `P02E-*`, `P02F-*`,
  `P02G-*`, `P02H-*`, `P02I-*`
- `api/endpoints.md`
- `order-lifecycle/state-machine.md`
- `order-lifecycle/transition-rules.md`
- `docs/phase1-order-message-status-model.md`
- `docs/phase2-async-order-ingest.md`
- `docs/PROJECT_STATUS.md`
- `docs/INSTALLER-LIFECYCLE.md`
- `docs/reports/MO-RC4-AWS-TEST-FUNCTIONAL-VERIFY-08.md`
- `docs/reports/MO-RC4-TESTSUITE-HARDENING-10A…10E-A.md`
- `docs/reports/MO-RC4-SECURITY-DEFECT-CORRECTION-11A.md`
- `docs/reports/MO-RC4-SECURITY-APPROVAL-CONTRACT-12A.md`

### Testbaseline

- Installer: `installer/tests/` — 30 Dateien
- Builder: `module_builder/tests/` — 2 Dateien
- Lambda: `lambda/tests/` — 15 Dateien
- E2E lokal/live: `tests/` — 2 Dateien
- Seed-Tools: `scripts/tests/` — 1 Datei (separat)
- Cognito-Backup: `cognito_backup/tests/` — 2 Plain-Function-Dateien,
  **nicht** als `unittest.TestCase` gesammelt

---

## 3. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `a0dec8161960a0375928acd0f7753c54f9f89d3f` |
| Working Tree | CLEAN |
| 10A–10D | VERIFIED |
| 10E-A | PARTIAL (SEC-01…06) |
| 11A | SEC-01…05 korrigiert; SEC-06 offen |
| 12A/12A-1 | Vertrag/Entscheidung dokumentiert; ADR PROPOSED |

---

## 4. Ursprünglicher RC4-Funktionsumfang

### 4.1 Order-Fachvertrag

Quellen: `api/endpoints.md`, `order-lifecycle/state-machine.md`,
`docs/phase1-order-message-status-model.md`, `docs/phase2-async-order-ingest.md`.

Kernfunktionen:

- Benutzer erstellt Order über `POST /orders` mit JWT/Cognito.
- Order-Felder: `orderId`, `customer`, `items`, `currency`, `totalAmount`,
  `createdAt`, `updatedAt`, Status.
- Validierung: Pflichtfelder, E-Mail, Mengen/Preise, Währung, unbekannte
  Felder.
- Persistenz in DynamoDB (Single-Table, GSI1 für Listing, GSI2 für Subject).
- Statusmodell: `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED`,
  `CANCELLED` aus `PENDING`/`CONFIRMED`.
- Asynchroner Pfad: Producer → SQS → Worker → DynamoDB.
- Handler-Registry/`orderType` (RC4 P02E), Processing-Claim/Result
  (P02G), Recovery/GSI3 (P02F/P02I).
- Owner/Consumer-Autorisierung (P02H), Privacy inspect/export/erase
  (P02), Legacy-RC3-Kompatibilität.

### 4.2 Ursprünglicher RC4-Plan (P00)

`MO-RC4-P00-MODULE-PLAN.md` plant 15 Pakete:

| Paket | Inhalt | Aktueller Stand |
|---|---|---|
| P-01 | SecretProvider (Env/Secrets Manager) | **NICHT IMPLEMENTIERT** |
| P-02 | AWS Secrets Manager | **NICHT IMPLEMENTIERT** |
| P-03 | Secret-Rotation | **NICHT IMPLEMENTIERT** |
| P-04 | KMS CMK | **NICHT IMPLEMENTIERT** |
| P-05 | DynamoDB SSE-KMS | **NICHT IMPLEMENTIERT** |
| P-06 | SQS SSE-KMS | **NICHT IMPLEMENTIERT** |
| P-07 | IAM KMS-Rechte | **NICHT IMPLEMENTIERT** |
| P-08 | Retention/TTL | **NICHT IMPLEMENTIERT** |
| P-09 | Cancel-Retention | **NICHT IMPLEMENTIERT** |
| P-10 | Installer-Flags | **NICHT IMPLEMENTIERT** |
| P-11 | Builder KMS/Secret-Module | **NICHT IMPLEMENTIERT** |
| P-12 | RIS-Kompatibilität | teilweise historisch belegt |
| P-13 | Security-Tests | teilweise vorhanden, aber nicht P00-spezifisch |
| P-14 | RC4-Release-Gates | nicht abgeschlossen |
| P-15 | Policy-Gate KMS/Secrets | **NICHT IMPLEMENTIERT** |

**Befund:** Der P00-Plan und der implementierte Order-Schwerpunkt sind nicht
deckungsgleich. Die aktuellen RC4-Reports und der Code implementieren vor
allem P02/P02A/P02C/P02E/P02F/P02G/P02H/P02I (Order Ownership, Worker,
Processing, Recovery). KMS/Secrets/Retention bleiben **PLANNED /
NOT IMPLEMENTED**. Ob sie für den RC4-Order-Release verbindlich sind, ist eine
offene Scope-Entscheidung; die P00-Open-Questions sind teilweise blockierend.

### 4.3 Dokumentationsabweichungen

| Quelle | Aussage | Aktueller Code/Stand |
|---|---|---|
| `docs/phase2-async-order-ingest.md` | kein DLQ, keine Idempotenz, Worker minimal | DLQ/Redrive und Worker-Condition/Idempotenz sind implementiert |
| `docs/PROJECT_STATUS.md` | RC4-Branch „P00 dokumentiert, keine Implementierung“ | P02/P02I-Code und RC4-Teststack existieren |
| `README.md` | Release `v0.5.0-rc.2` | Release Notes/RC3-Stand und RC4-Arbeiten sind weiter |
| `docs/PROJECT_STATUS.md` | AWS Resources NONE | RC4-Teststack wurde laut 08 mit 39 Ressourcen betrieben |

Diese Abweichungen sind Dokumentationsdrift, kein Order-Produktdefekt.

---

## 5. Aktueller Implementierungsstand

### 5.1 Was implementiert ist

- JWT-Identität aus Autorizer-Claims, Owner/Consumer-Isolation.
- Order-Erstellung mit strikter Validierung, `PENDING`, `version=1`,
  `subjectId`, GSI2.
- Statusmaschine und PATCH-Conditional-Update.
- SQS-Producer, SQS-Worker, Conditional Status Update, `batchItemFailures`.
- DLQ/Redrive und Retention in Terraform (P02C).
- Handler-Registry/`orderType`; **produktiv registriert ist nur `generic`**.
- Processing-Claim/Result-/Recovery-Infrastruktur (P02G/P02I), im Code
  vorhanden; produktive Processing-Handler sind nicht registriert.
- Privacy inspect/export/erase, aber Secret-/KMS-Betrieb ist nicht
  provisioniert (P01/P02-P00).
- Installer-Sicherheitsgates (separater Scope) inklusive 11A-Korrekturen.

### 5.2 Was nicht implementiert ist

- API-Idempotency-Key / Deduplizierung.
- KMS/Secrets-Manager/Retention/Cancel-Retention aus P00.
- Produktive Processing-Handler über `generic` hinaus.
- Live-Testidentität und sichere Live-Testdatenbereinigung.
- Funktionale DLQ-/Retry-Live-Nachweise.
- Produktive Live-Verifikation der GSI3/Processing-Recovery.

### 5.3 Handler-Registry

`lambda/src/order_handlers.py` registriert produktiv nur:

```python
register(DEFAULT_ORDER_TYPE, _generic_handler)   # generic, processing=False
```

Die in P02G/P02I getesteten Processing-Handler werden in Tests dynamisch
registriert (`processing=True`), nicht im Produktivpfad. Das ist für die
aktuelle `generic`-Order korrekt, aber Processing-Funktionen sind damit
**nicht produktiv aktiviert**.

---

## 6. Vollständige Testinventur

### 6.1 Aktuell ausgeführt

| Suite | Testdateien | Tests | Ergebnis | Laufzeit | Typ | Abhängigkeiten |
|---|---:|---:|---|---:|---|---|
| Installer | 30 | **669** | PASS | 25,8 s | Unit/Component, teils lokale Terraform-CLI | Mocks, temp dirs |
| Builder | 2 | **128** | PASS | 2,5 s | Unit/Component | temp dirs |
| Lambda | 15 | **337** | PASS | 0,9 s | Unit/Component | Fake-DynamoDB, Fake-SQS, Mock-boto3 |
| E2E-Harness lokal | 1 | **16** | PASS | 0,003 s | Local Component/Harness | Fake-HTTP/Fake-AWS |
| **Konsolidierte Baseline** | | **1.150** | **PASS** | | | |
| E2E Live | 1 | **4** | **BLOCKED/SKIP** | 0,0 s | Live E2E | Cognito/API/SQS/DDB, nicht verfügbar |
| Seed-Tools | 1 | **28** | PASS (separat) | 0,17 s | Unit/Tooling | boto3 optional/mock |
| Cognito-Backup | 2 | 2 Plain-Function-Tests | **nicht gesammelt** | — | Legacy/Tooling | boto3 optional |

Historic baseline **1.150 PASS** ist im aktuellen Checkout bestätigt. Die
Live-Tests zählen nicht als PASS.

### 6.2 Testdateien (Pfade)

```text
installer/tests/test_*.py                   30 Dateien
module_builder/tests/test_*.py               2 Dateien
lambda/tests/test_*.py                      15 Dateien
tests/test_e2e_harness.py                    1 Datei (16 lokal)
tests/test_e2e_async_order.py                1 Datei (4 live, BLOCKED)
scripts/tests/test_seed_orders.py            1 Datei (28 separat)
cognito_backup/tests/test_*.py               2 Plain-Function-Dateien, nicht gesammelt
```

### 6.3 Testtypen

- **Unit:** Lambda-Service/-Handler, Installer-Core, Builder, Validation.
- **Component:** 10B Order-Flow mit gemeinsamem Fake-DynamoDB und Fake-SQS;
  16 E2E-Harness-Tests.
- **Integration:** keine echte AWS-Integration; lokale Fakes nur.
- **E2E Live:** 4 Tests vorhanden, 4 BLOCKED.
- **Historische Live-Evidenz:** separate Reports, nicht aktueller Stack.

### 6.3 Testqualität

Belegt:

- Keine `assertTrue(True)`-Platzhalter mehr in den aktiven Tests
  (`installer`, `lambda`, `builder`, `tests`).
- Viele Negativtests: 401/404/409, Owner-/Consumer-Isolation, Conditional
  Conflict, invalid transitions, Handler-Fehler, SQS-Batchfehler.
- Konkrete Mutationstests aus 10B/10C/11A haben Fehler erkannt.
- Die lokale E2E-Suite ist run-scoped und hat Fake-Transport.

Grenzen:

- Viele Tests prüfen Mock-Aufrufe oder exakte Expressions; sie ersetzen keine
  reale Integration.
- Live-E2E-Suite ist vollständig blockiert.
- DLQ/Retry, GSI3, SQS-Redrive, echte Cognito-JWT-Ausstellung und
  API-Gateway-Verhalten sind nicht live geprüft.
- Coverage ist kein Funktionsnachweis; hohe Lambda-Coverage entsteht auch
  durch Fakes.
- `cognito_backup/tests` werden nicht als `unittest` gesammelt; das ist eine
  Inventarlücke, kein Order-Problem.

---

## 7. Coverage-Bewertung

Aktuellster gemessener Stand (11A; danach nur Doku-Änderungen):

| Komponente | Statement | Branch | Bewertung |
|---|---:|---:|---|
| Lambda | **90,15 %** | **82,22 %** | lokal gut, Live nicht abgedeckt |
| Installer (inkl. Policy) | **74,08 %** | **64,04 %** | Sicherheitsmodule teilweise, CLI-Pfade schwach |
| Builder | **91,22 %** | **84,93 %** | lokal gut |
| E2E-Harness separat | **91,58 %** | **88,46 %** | Harness, kein Produktcode |

Wichtige Lücken:

- Installer `cli/main.py` 44,8 %/33,7 %; `plan_analysis.py` 44,9 %/27,5 %;
  `run/manager.py` 40,7 %/38,0 %; `remote_state_lifecycle` 56,1 %/25,0 %.
- Nicht instrumentierte Installer-Module: u. a. `atomic_ops.py`,
  `command_result.py`, `command_service.py`, `lock_manager.py`,
  `logging_hardening.py`, `plan_integrity.py`, `recovery.py`,
  `subprocess_safety.py`, `cli/gui.py`.
- Lambda: `index.py` 82,3 %/70,5 %, `order_service.py` 88,7 %/76,6 %,
  `sqs_handler.py` 88,7 %/78,3 %, `recovery.py` 82,6 %/74,2 %.
- Builder: `validation.py` 40,0 %/0,0 %; `__main__.py` 0 %.
- Function-Coverage: mit coverage.py nicht separat ausgewiesen.

---

## 8. RC4-Traceability-Matrix

| ID | RC4-Anforderung | Implementierung | Vorhandener Test | Nachweisqualität | Offene Lücke | Risiko |
|---|---|---|---|---|---|---|
| R-01 | Order-Erstellung durch verifizierten Benutzer | `index.handler` POST; `OrderService.create_order`; `subjectId`/GSI2 | `test_index.py`, `test_order_service.py`, `test_order_processing_component.py` | Lokal **TESTED**; Live **BLOCKED** | keine echte API/Cognito-Ausführung | P1 |
| R-02 | Eingabevalidierung / API-Vertrag | `validation.py`; `api/endpoints.md` | `test_validation.py`, `test_index.py` | **TESTED** (Unit) | Live-API-Statuscodes nicht geprüft | P2 |
| R-03 | Persistenz / Owner / GSI2 / Version | `create_order`, `put_item`; Fake-DDB | Service-/Component-Tests | **TESTED mit Fakes**; Live **BLOCKED** | echte DynamoDB-Condition/GSI2 nicht live | P1 |
| R-04 | Handler-Auswahl / orderType | `order_handlers.py`; produktiv nur `generic` | `test_order_handlers.py`, Processing-Tests mit Testhandlern | **PARTIAL** | kein produktiver Processing-Handler | P1 |
| R-05 | Statusübergänge | `state_machine.py`, API/Worker | State-/Service-/Component-Tests | **TESTED** lokal | Live-Statusübergang fehlt | P1 |
| R-06 | SQS-Publish / Worker | `index._send_to_sqs`, `sqs_handler` | `test_sqs_handler.py`, 10B Component | **TESTED mit Fake-SQS** | echte Queue/Worker-Integration fehlt | P1 |
| R-07 | Idempotenz / Duplikate | Worker-Condition + Statuscheck; API **kein Idempotency-Key** | Worker-Duplicate/Conflict-Tests; API-Repeat-Charakterisierung | **PARTIAL** | API-Replays erzeugen neue Orders; DLQ/Retry live fehlt | P1 |
| R-08 | Fehler / Retry / DLQ | Worker `batchItemFailures`; Terraform Redrive/DLQ | Worker-Fehler-/Batch-Tests; Redrive-Terraform-Test | **PARTIAL / LIVE BLOCKED** | keine funktionale DLQ-Zustellung | P0/P1 |
| R-09 | Authentifizierung / Owner-Isolation | `identity.py`, `authorize_order_access`, API/Worker | 401/404/foreign-owner-Tests | **TESTED** lokal; Live **BLOCKED** | echte JWT-Claim-/API-Gateway-Prüfung fehlt | P1 |
| R-10 | Privacy inspect/export/erase | `order_service.py` | Privacy-Service-/Index-Tests | **PARTIAL** | Secret/KMS nicht provisioniert; Live fehlt; Bestandsdaten unauffindbar | P0/P1 (falls RC4-Scope) |
| R-11 | Processing-Claim/Result | `sqs_handler`, `processing_result`, Test-Handler | Processing-Lifecycle-Tests | **TESTED lokal**; produktiv nicht aktiviert | kein produktiver Processing-Handler | P1 |
| R-12 | Pending-/Processing-Recovery / GSI3 | `index` internal, `recovery.py`, Terraform GSI3 | Recovery-Tests, Infra read-only | **PARTIAL**; Live **BLOCKED** | GSI3/Recovery nicht mit echten Daten | P1 |
| R-13 | RC3-Kompatibilität | Legacy-Felder, API-Verträge, RIS-Historie | Identity-/Legacy-/API-Tests | **PARTIAL** | kein aktueller RC3→RC4-Live-E2E | P1 |
| R-14 | KMS/Secrets/Retention/Cancel-Retention (P00) | **nicht implementiert** | keine | **NOT TESTED / NOT IMPLEMENTED** | P00-Entscheidungen; Code fehlt | P0/P1 je Scope |
| R-15 | Live-E2E / Betriebsnachweis | Live-Suite | 4 Live-Tests vorhanden | **BLOCKED** | keine Testidentität, kein Cleanup | **P0** |
| R-16 | Installer-Sicherheitsgates (separat) | Installer-Code | 669 Tests; SEC-01…05 behoben | **PARTIAL/VERIFIED lokal** | SEC-06 V2 nicht implementiert | separat |

### 8.1 Vollständig lokal nachgewiesen (Tabelle 1)

- Order-Erstellung mit JWT-Owner (lokal, Fake-DDB).
- Eingabevalidierung und zentrale Fehlercodes (lokal).
- Owner-/Consumer-Isolation und 401/404 (lokal).
- Statusmatrix und Conditional Update (lokal).
- Worker-Idempotenz/Batch-Fehler (lokal, Fake-SQS).
- Processing-Claim/Result-Pfad (lokal, Testhandler).
- Installer-Sicherheitsgates SEC-01…05 (lokal).

### 8.2 Teilweise nachgewiesen (Tabelle 2)

- SQS-Publish/Worker (Fake, keine Live-Queue).
- Persistenz/GSI2 (Fake, keine echte Tabelle).
- Recovery/GSI3 (Fake, Infra read-only).
- RC3-Kompatibilität (lokale Verträge, kein aktueller Live-Flow).
- P00 Privacy/KMS/Retention (nur Design/Planung, Code fehlt).
- API-Idempotenz (Worker ja, API nein).
- DLQ (Konfiguration, keine Zustellung).

### 8.3 Fehlend/blockiert (Tabelle 3)

- Live-E2E authentifiziert (4 Tests, BLOCKED).
- Live-DLQ/Retry/Worker-Redrive.
- Live-GSI3/Recovery.
- Live-Cleanup und Testidentität.
- Produktive Processing-Handler.
- KMS/Secrets/Retention (falls RC4-Scope).

### 8.4 Bestätigte Defekte (Tabelle 4)

| ID | Befund | Status |
|---|---|---|
| SEC-01 | ApprovalGate-RecursionError | **FIXED** in 11A |
| SEC-02 | `_has_valid_deployment_id` fehlte | **FIXED** |
| SEC-03 | Undefinierte Planvariablen | **FIXED** |
| SEC-04 | Plan-Match blockierte gültige Pläne | **FIXED** |
| SEC-05 | Workspace-Root ignoriert | **FIXED** |
| SEC-06 | Approval ohne Plan-/Workspace-Bindung | **CONTRACT GAP / NEEDS DECISION**, nicht implementiert |
| DOC-01 | `PROJECT_STATUS`/README/phase2 veraltet | **CONFIRMED docs drift**, kein Order-Code-Defekt |
| API-IDEM | Kein API-Idempotency-Key | **CONTRACT GAP**, kein bestätigter Codefehler |
| LIVE-CLEANUP | Keine sichere Live-Testdatenlöschung | **BLOCKED**, kein Workaround |

Es wurden **keine neuen bestätigten Order-Code-Defekte** in 13A gefunden.

---

## 9. Priorisierte offene Nachweise

| Rang | RC4-Funktion | Fehlender Nachweis | Risiko | Priorität | Aufwand |
|---:|---|---|---|---|---|
| 1 | Authentifizierter Live-Order-Flow | Echte Cognito/JWT/API/DDB/SQS/Worker-Kette | Kein Produktionsnachweis | **P0** | L |
| 2 | Live-Testdaten/Cleanup | Testidentität + sichere, eigentümergebundene Bereinigung | Daten-/Compliance-Risiko | **P0** | M/L |
| 3 | DLQ/Retry | Funktionale DLQ-Zustellung, Redrive, Batch-Retry | Verlorene/blockierte Orders | **P0/P1** | M |
| 4 | GSI3/Processing-Recovery | Echte GSI3-Abfrage/Recovery mit Daten | Hängende `PROCESSING`-Orders | **P1** | M |
| 5 | Processing-Handler-Aktivierung | Produktiver Handler über `generic` hinaus | P02G-Funktion nur Test | **P1** | M |
| 6 | API-Idempotenz | Idempotency-Key/Vertrag + Tests | Doppel-Orders bei Retry | **P1** | M |
| 7 | Privacy/KMS/Retention (P00) | Implementierung/Entscheidung P-01…P-09 | Produktions-Privacy/Retention | **P0/P1 je Scope** | L |
| 8 | RC3→RC4-Live-Kompatibilität | Echter Bestands-/Upgrade-/Consumer-Flow | Kompatibilitätsrisiko | **P1** | M/L |
| 9 | Installer SEC-06 | ApprovalEvidence V2 Entscheidung/Implementierung | Deployment-Freigabe | **P1** separat | M |
| 10 | Coverage/Testqualität | CLI-/Privacy-/Validation-Coverage, Doc-Sync | Blind spots | **P2** | S/M |

---

## 10. Empfohlene nächste Arbeitspakete (max. 10) — Tabelle 5

| Task-ID | Ziel | Betroffene Dateien | Geplante Tests | Abhängigkeiten | Aufwand | Risiko | Abschlusskriterium |
|---|---|---|---|---|---|---|---|
| RC4-13A-01 | Live-Order-E2E mit vorab provisionierter Testidentität | `tests/test_e2e_async_order.py`, `tests/e2e_harness.py` | 401, POST, GET, Worker-Status | Cognito-Testidentität, API-Endpunkt, Freigabe | L | **P0** | Ein autorisierter Lauf PASS, Cleanup dokumentiert |
| RC4-13A-02 | Sichere Live-Cleanup-Fähigkeit | E2E-Harness/Cleanup-Vertrag | Eigentums-, Fehler-, Fremddaten-Tests | Produkt-Entscheidung/Delete-API | M/L | **P0** | Fremddaten unberührt, Cleanup bei Fehler |
| RC4-13A-03 | DLQ/Retry-Nachweis | `sqs_handler.py`, Terraform SQS, Tests | Redrive/DLQ/Batch-Retry | isolierte Testqueue + Freigabe | M | **P0/P1** | Nachricht erreicht DLQ, kein Datenverlust |
| RC4-13A-04 | GSI3/Recovery-Live-Nachweis | `recovery.py`, `index.py`, Terraform | Claim/Recovery/Pagination | Testdaten + Freigabe | M | **P1** | Recovery-Report + Status konsistent |
| RC4-13A-05 | Processing-Handler produktiv definieren | `order_handlers.py`, Handler-Modul | Processing-Claim/Result/Fehler | fachliche Entscheidung | M | **P1** | registrierter Processing-Handler + Tests |
| RC4-13A-06 | API-Idempotenz-Vertrag | `index.py`, `order_service.py`, API-Doku | Repeat/Key/Conflict | Vertragsfreigabe | M | **P1** | gleicher Request → definierte Semantik |
| RC4-13A-07 | P00-Scope-Entscheidung KMS/Secrets/Retention | P00 P-01…P-09 | Design/Contract | Release-Entscheidung | L | **P0/P1** | Scope freigegeben oder aus RC4 entfernt |
| RC4-13A-08 | RC3→RC4-Live-Kompatibilität | E2E/Consumer-Vertrag | Bestandsorder, Status, API | Teststack/Consumer | M/L | **P1** | RC3-Order lesbar/verarbeitbar |
| RC4-13A-09 | Installer SEC-06 V2 | `installer/core/approval*`, CLI | V2-01…V2-16 | 12A-1-Entscheidungen | M/L | **P1** separat | Evidence-Gate + Tests |
| RC4-13A-10 | Coverage/Doku-Konsolidierung | `docs/PROJECT_STATUS.md`, README, tests | Coverage + Docs | keine | S | **P2** | Status konsistent, Lücken dokumentiert |

Keine neuen Produktfeatures ohne fachliche Scope-Entscheidung.

---

## 11. Release-relevante Blocker

**P0 für eine RC4-Gesamtfreigabe:**

1. Authentifizierter Live-Order-E2E-Nachweis fehlt.
2. Sichere Live-Testdatenbereinigung/Testidentität fehlt.
3. DLQ/Retry funktional nicht live nachgewiesen.
4. Wenn der P00-Plan verbindlich ist: KMS/Secrets/Retention sind nicht
   implementiert und nicht entschieden.

**P1:**

- GSI3/Processing-Recovery live.
- Produktiver Processing-Handler.
- API-Idempotenz-Vertrag.
- RC3→RC4-Live-Kompatibilität.
- Installer SEC-06 (separater Deployment-Scope).

**P2:**

- Coverage-/Doku-Lücken, nicht Release-blockierend für Order-Kern.

---

## 12. Bestätigte Defekte

- **SEC-01…SEC-05** aus 10E-A sind in 11A behoben und mit 48 fokussierten
  Tests abgesichert.
- **SEC-06** ist kein bestätigter Codefehler, sondern ein
  Vertragsgap/Entscheidungsbedarf; V2 ist **PROPOSED**, nicht implementiert.
- **DOC-01**: `PROJECT_STATUS`, README und `phase2` sind gegenüber dem
  aktuellen Code/den RC4-Reports veraltet.
- **Kein neuer Order-Code-Defekt** wurde in 13A nachgewiesen.

---

## 13. Grenzen der Untersuchung

- Keine AWS-Live-Ausführung; keine echte Cognito-Identität.
- Keine echten SQS-/DynamoDB-/GSI3-Aufrufe.
- Keine aktuellen Live-E2E-Ergebnisse; historische E2E-Nachweise sind
  getrennt und nicht auf den aktuellen Teststack übertragbar.
- Coverage wurde aus 10D/11A übernommen; der Produktcode ist seit 11A
  unverändert, nur Dokumentation kam hinzu.
- Der P00-Plan ist ein Plan, keine freigegebene RC4-Produktentscheidung;
  Scope bleibt offen.
- Function-Coverage wurde nicht separat gemessen.

---

## 14. Git-Abschluss

Vorgesehen:

```text
Commit: docs(rc4): consolidate order testsuite coverage and open evidence
Dateien: docs/reports/MO-RC4-TESTSUITE-CONSOLIDATION-13A.md
         docs/AI_AUDITLOG.md
```

Kein Push, kein Merge. Commit-SHA und CLEAN-Status werden nach dem Commit
verifiziert.
