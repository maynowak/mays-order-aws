# MO-RC3-RC4-G3-LIVE-B2-PREP-01

**Privacy Live Readiness & Security Discovery**

**Datum:** 2026-11-13
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `a1d5c802467d9923d61f3d8bdf3e059079f614c9`
**Modus:** ausschließlich read-only AWS-/Repository-Analyse, lokale Tests und
Dokumentation; **keine AWS-Mutation**, keine Cognito-Benutzer, keine
Lambda-Invocation, kein API-Livetest, kein Secret-Wert gelesen, keine IAM-/
Terraform-Änderung, kein Push/Merge.

```text
Privacy Core Implementation:   IMPLEMENTED / DEPLOYED / LOCAL TESTED
GSI2 / F-PRV-01:               FIXED / DEPLOYED / LOCAL VERIFIED
B2 Privacy Live Readiness:     CONFIGURATION REQUIRED
AWS-managed Secret Lifecycle:  IMPLEMENTATION GAP (P00, separate scope)
Cross-Consumer Live Test:      CONFIGURATION REQUIRED
B2 Live Execution:             BLOCKED until secret + least-privilege invoker
```

**Kurzfassung:** Die drei Privacy-Operationen `inspect`, `export` und `erase`
sind im Produktcode vorhanden, im deployed G3-FIX-Artefakt enthalten und lokal
getestet. Der aktuelle AWS-Stack kann sie jedoch nicht sicher live ausführen:
`PRIVACY_INTERNAL_SECRET` fehlt in der Handler-Env, es gibt kein
least-privilege Test-Invoke-Prinzipal, und es existiert keine
Secrets-Manager-/KMS-Referenz. Der F-PRV-01-Fix ist nachweisbar deployed; die
Consumer-Isolation ist auf Code-/Testebene abgesichert, aber nicht live
verifiziert. B2 ist daher **CONFIGURATION REQUIRED**, nicht `READY`.

---

## 1. Executive Summary

### Implementiert und deployed

- `privacy/inspect`: subject-basierte GSI2-Query, vollständiger `GetItem`-
  Recheck, optionale Consumer-Scope-Filterung, datensparsame Ausgabe ohne PII.
- `privacy/export`: dieselbe Query-/Recheck-Basis, vollständige
  Exportfelder inklusive `customer.name`/`customer.email` und
  Verarbeitungs-/Ergebnisfeldern, keine internen Felder.
- `privacy/erase`: `PREVIEW`, `EXECUTE`, `ERASE`, `ANONYMIZE`, `RETAIN`,
  Subject-/Versions-Condition, Idempotenz bei Conditional-Fehler.
- Interner Dispatch ausschließlich über direktes Lambda-Invoke; **keine**
  öffentliche Privacy-API-Route.
- F-PRV-01: GSI2 liefert nur `orderId`; vor Scope-Prüfung wird das vollständige
  Item per `GetItem` (ConsistentRead) geladen, inklusive `consumerId`.

### Nicht live möglich

- `PRIVACY_INTERNAL_SECRET` fehlt in der Handler-Env.
- Keine Secret-Manager-/SSM-/KMS-Referenz für dieses Secret.
- Kein dediziertes least-privilege `lambda:InvokeFunction`-Testprinzipal.
- Die vorhandenen breiten Identitäten (`Mayaws` = AdministratorAccess,
  AI/Human Developer = `lambda:*`) sind kein sauberes Testmodell.
- Terraform Policy Gate erlaubt derzeit keine `aws_secretsmanager_secret`-/
  KMS-Ressourcen.

### Ergebnis

Die Privacy-Funktionen sind **implementiert, deployed und lokal getestet**.
B2-Live ist **blockiert durch fehlende Konfiguration**, nicht durch einen
fehlenden Privacy-Handler. Eine belastbare Live-Ausführung benötigt eine
ausdrücklich freigegebene, zeitlich begrenzte Secret-/Invoke-Konfiguration oder
eine separate P00-Produktivimplementierung.

---

## 2. Git- und AWS-Baseline

### Git

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD vor Analyse | `a1d5c802467d9923d61f3d8bdf3e059079f614c9` |
| Working Tree vor Analyse | CLEAN |
| Änderungen | nur Dokumentation/Manifest, danach committed |

### AWS (read-only)

| Parameter | Wert |
|---|---|
| Profil | `mayaws` |
| STS Account | `240571105849` |
| STS ARN | `arn:aws:iam::240571105849:user/Mayaws` |
| Region | `eu-central-1` |
| Teststack | `mays-orders-rc4-test` |
| Handler | `mays-orders-rc4-test-handler`, Python 3.14, `index.handler`, Active/Successful |
| Worker | `mays-orders-rc4-test-sqs-worker`, Python 3.14, `sqs_handler.handler`, Active/Successful |
| CodeSha256 beide | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| DynamoDB | ACTIVE, `ItemCount=0` |
| GSI2 | ACTIVE, `INCLUDE` ohne `consumerId` |
| GSI3 | ACTIVE, `KEYS_ONLY`, Count 0 |
| Main Queue / DLQ | 0/0 und 0/0 |
| API | `37fldhw7fi`, nur vier JWT-Routen |
| Cognito | Pool `eu-central-1_OZ7TK51EK`, 0 User, Testclient public |

Lokales Artefakt:

```text
lambda/dist/lambda.zip
SHA-256  1584ee0dcccd0b042277827184575a1876c159c75a7a0e95ccd29b4fe5a37e44
Base64   FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=
```

Das lokale ZIP enthält die F-PRV-01-Marker (`ProjectionExpression: orderId`,
`_load_order_item`, `consumerId`). Damit ist der deployte Code nicht nur
hash-identisch, sondern enthält den korrigierten Privacy-Pfad.

---

## 3. Privacy-Implementierungsmatrix

| Funktion | Einstiegspunkt | Auth | Datenzugriff | Lokaler Test | AWS-Live-Status |
|---|---|---|---|---|---|
| `privacy/inspect` | `index.handler` → `_handle_internal` → `OrderService.inspect_subject` | `_require_privacy_auth`: Projekt, `authorized`, `privacy_inspect`, Env-Secret + `internal_token` | GSI2 `SUBJECT#<subjectId>` → `orderId`; vollständiger `GetItem`; optionaler Consumer-Scope; Ausgabe nur Referenzen/Kategorien | `TestPrivacyInspect` (4), `TestPrivacyConsumerScopeP02B`, `TestProcessingResultPrivacyP02GA` | **BLOCKED** (Secret/Invoke) |
| `privacy/export` | `index.handler` → `_handle_internal` → `OrderService.export_subject` | dto. mit `privacy_export` | GSI2 → `GetItem`; Export von Order-/Kundendaten und Processing-Feldern; keine internen Felder | `TestPrivacyExport` (4), `TestPrivacyConsumerScopeP02B`, `TestProcessingResultPrivacyP02GA` | **BLOCKED** (Secret/Invoke) |
| `privacy/erase` | `index.handler` → `_handle_internal` → `OrderService.erase_subject` | dto. mit `privacy_erase` | GSI2 → vollständiger `GetItem` → optionaler Consumer-Scope → `DeleteItem`/`UpdateItem` | `TestPrivacyErase` (6), `TestPrivacyConsistency` (7), `TestPrivacyConsumerScopeP02B` (7) | **BLOCKED** (Secret/Invoke) |
| Interner Dispatch | `_INTERNAL_PRIVACY_ACTIONS`, `_handle_internal` | keine HTTP/JWT-Route; nur direkter Lambda-Invoke | `internalAction` + `payload` + `authContext` | `TestInternalPrivacyDispatch` (3) | **BLOCKED** (Invoke) |
| Öffentliche Privacy-Route | keine | — | — | API-Routen-Discovery | **NICHT VORHANDEN** (by design) |
| Consumer-Scope | `privacy_scope_consumer`, `item_in_privacy_scope` | optionaler `consumerId`/`consumer` im internen Kontext | filtert vollständige Items nach `consumerId`; Legacy ohne `consumerId` wird ausgeschlossen | `TestPrivacyScopeP02B` (4), F-PRV-01-Test | **LIVE NICHT VERIFIZIERT** |
| F-PRV-01 | `erase_subject` + `inspect/export` | dto. | GSI2 nur `orderId`; vollständiger Recheck inklusive `consumerId` | `test_erase_with_scope_loads_full_item_after_gsi2_projection` | **DEPLOYED / LOCAL PASS; LIVE OPEN** |

### Code-Referenzen

- Dispatch und interne Aktionen: `lambda/src/index.py:125-131`,
  `lambda/src/index.py:218-244`.
- Auth-Boundary: `lambda/src/order_service.py:146-170`.
- Inspect: `lambda/src/order_service.py:409-491`.
- Export: `lambda/src/order_service.py:492-577`.
- Erase: `lambda/src/order_service.py:579-780`.
- Consumer-Scope: `lambda/src/identity.py:387-405`.
- GSI2-Projektion: `terraform/modules/dynamodb/main.tf` (`gsi2` `INCLUDE`,
  keine `consumerId`).
- F-PRV-01-Marker im deployed ZIP: `order_service.py:609-633`.

### Statusabgrenzung

| Status | Bewertung |
|---|---|
| Implementiert | **JA** — Inspect/Export/Erase, Preview/Execute, ERASE/ANONYMIZE/RETAIN |
| Lokal getestet | **JA** — 345 Lambda-Tests PASS; 44 privacy-bezogene Tests |
| Deployed | **JA** — CodeSha `FYTu…`; F-PRV-01-Marker im ZIP |
| Live verifiziert | **NEIN** — keine B2-Ausführung |
| Blockiert | **JA** — Secret + least-privilege Invoke fehlen |

---

## 4. Bestehende Testabdeckung

### Gesamte Lambda-Suite

```bash
cd lambda
PYTHONPATH=src python3 -m unittest discover -s tests
```

```text
Ran 345 tests in 0.505s
OK
```

### Privacy-bezogene Klassen

| Datei / Klasse | Tests | Abdeckung |
|---|---:|---|
| `test_order_service.py::TestPrivacyInspect` | 4 | eigene Daten, Auth, leere Ergebnisse |
| `TestPrivacyExport` | 4 | Export, Auth, Pagination, keine internen Felder |
| `TestPrivacyErase` | 6 | Preview, Execute, Auth, Anonymize, Secret/Token |
| `TestPrivacyConsistency` | 7 | Pagination, Idempotenz, Subject-Condition, RETAIN |
| `TestPrivacyConsumerScopeP02B` | 7 | Scope, fremder Consumer, F-PRV-01, Legacy |
| `TestProcessingResultPrivacyP02GA` | 9 | Ergebnis-/Fehlerfelder, Anonymize, Public Projection |
| `test_identity.py::TestPrivacyScopeP02B` | 4 | Scope-Semantik, Consumer/legacy |
| `test_index.py::TestInternalPrivacyDispatch` | 3 | internes Dispatch, unbekannte Aktion, Auth-Fehler |
| **Summe privacy-bezogen** | **44** | davon F-PRV-01-Regression |

Wichtige PASS-Nachweise:

- `test_erase_with_scope_loads_full_item_after_gsi2_projection` — F-PRV-01.
- `test_erase_with_scope_does_not_touch_foreign_consumer` — Consumer-Isolation.
- `test_erase_is_idempotent_when_item_already_gone` — Wiederholbarkeit.
- `test_erase_guard_binds_subject_in_condition` — Subject-/Versionsschutz.
- `test_erase_retain_policy_does_not_mutate` — RETAIN.
- `test_inspect_returns_orders_for_subject` / `test_export_returns_orders_for_subject`.
- `test_privacy_requires_internal_secret` / `..._internal_token`.

Es wurde **kein** AWS-Test ausgeführt; die 345 Tests sind lokale Fakes.

---

## 5. AWS-Security-Readiness-Matrix

| Voraussetzung | Erwartet | Tatsächlich | Status |
|---|---|---|---|
| Handler-Env `PRIVACY_INTERNAL_SECRET` | vorhanden | **fehlt** | **GAP** |
| Handler-Env Secret-Referenz | Secrets Manager/SSM | keine | **GAP** |
| Handler-Rolle `secretsmanager:GetSecretValue` | exakt, falls Secret-Referenz | nicht vorhanden | **NICHT ERFORDERLICH für Env-Variante**, aber für P00 |
| Handler-Rolle `kms:Decrypt` | nur bei CMK | nicht vorhanden | **P00 offen** |
| Handler-Rolle `lambda:InvokeFunction` | nicht nötig | nicht vorhanden | **OK** (keine Selbst-Invoke-Rolle) |
| Worker-Rolle Privacy-Rechte | keine | keine | **OK** |
| Öffentliche Privacy-API-Route | nicht vorhanden | 4 Order-Routen, keine Privacy-Route | **OK / by design** |
| Lambda Function URL | nicht vorhanden | beide `ResourceNotFoundException` | **OK** |
| Resource-based Policy Handler | nur API GW | nur `apigateway.amazonaws.com`, Source-ARN `37fldhw7fi/*/*` | **OK** |
| Resource-based Policy Worker | keine | keine | **OK** |
| Least-privilege Test-Invoke-Prinzipal | dediziert | nur `Mayaws` (Admin) / AI/Human (`lambda:*`) | **GAP** |
| GSI2-Projektion `consumerId` | nicht projiziert, Recheck nötig | nicht projiziert; Code lädt vollständig | **OK (F-PRV-01)** |
| TTL / Retention | nicht erforderlich für B2? | TTL **DISABLED**, keine Retention-Felder | **P00 offen** |
| PITR / Backup | löscht Erasure nicht | PITR ENABLED, 35 Tage | **RISIKO** |
| DynamoDB SSE | AWS-owned Baseline | `SSEDescription=null` (AWS-owned), kein CMK | **PARTIAL/P00** |
| SQS SSE | vorhanden | `SqsManagedSseEnabled=true` | **OK** |
| Terraform Policy Gate für Secret/KMS | erlaubt, falls benötigt | Secret/KMS nicht in Allowlist | **GAP für P00** |

### Lambda-Konfiguration

```text
Handler Env Keys: ORDERS_TABLE, SQS_QUEUE_URL, ORDERS_PROJECT_NAME
Worker  Env Keys: ORDERS_TABLE
```

`ORDERS_PROJECT_NAME` ist `mays-orders-rc4-test`; die Privacy-Auth erwartet
exakt diesen Projektnamen.

### Secrets-Manager-/SSM-/KMS-Metadaten

Read-only geprüft, **keine Werte gelesen**:

- Secrets Manager: `github-token-xxxxx`, `ris-dev/applications/cursor-hmac`;
  **kein Privacy-Secret**.
- SSM: nur `/mays-installer/ci/{aws-profile,environment,project-name}`;
  **kein Privacy-Parameter**.
- KMS: nur AWS-managed Aliases (`alias/aws/dynamodb`, `alias/aws/lambda`,
  `alias/aws/secretsmanager` usw.); **kein projektspezifischer CMK**.

### IAM

- Handler-Rolle: DynamoDB Table CRUD/Query, GSI1/2/3 Query, Logs; **kein**
  `lambda:InvokeFunction`, **kein** Secrets Manager, **kein** KMS.
- Worker-Rolle: DynamoDB `GetItem`/`UpdateItem`, SQS Receive/Delete/Attributes,
  Logs; keine Privacy-Rechte.
- `Mayaws`: `AdministratorAccess` — für B2 nicht als sauberes Modell geeignet.
- `Mays-Orders-AI-Developer` und `Mays-Orders-Human-Developer`: breite
  `lambda:*`-Rechte, aber keine `secretsmanager`-Rechte; ebenfalls nicht
  least-privilege.
- Recovery-Scheduler-Rolle: **nicht vorhanden** (keine Schedules); nicht
  wiederverwendbar.

---

## 6. Secret- und IAM-Gaps

### Zwingend fehlend

1. **`PRIVACY_INTERNAL_SECRET` in der Handler-Env.**
   - `order_service.py:159-166` liest ausschließlich diese Env-Variable.
   - Fehlt sie, antwortet jede Privacy-Operation mit
     `400 VALIDATION_ERROR` / „Internal secret not configured“.
   - Aktuelle Handler-Env enthält nur `ORDERS_TABLE`, `SQS_QUEUE_URL`,
     `ORDERS_PROJECT_NAME`.

2. **Dediziertes Invoke-Prinzipal.**
   - Handler-Resource-Policy erlaubt nur API Gateway.
   - Kein Function URL.
   - Kein dediziertes Test-Prinzipal mit ausschließlich
     `lambda:InvokeFunction` auf den Handler.

3. **Secret-Referenz / Rotation.**
   - Kein Privacy-Eintrag in Secrets Manager oder SSM.
   - Kein projektspezifischer KMS-Key.
   - P00 (ADR-008) ist weiterhin `PROPOSED`; Secret-Provider/Retention nicht
     implementiert.

### Nicht zwingend, aber Risiko

- Secret in Lambda-Env ist für jeden mit `lambda:GetFunctionConfiguration`
  lesbar. `Mayaws`, AI- und Human-Developer haben `lambda:Get*`.
- Ein Secret in einer Terraform-Env-Variable würde im Plan/State erscheinen;
  das ist kein akzeptabler Produktivpfad.
- Der Terraform Policy Gate erlaubt `aws_secretsmanager_secret` und
  `aws_kms_key` derzeit nicht; eine IaC-Lösung würde eine Gate-Erweiterung
  erfordern.
- PITR ist 35 Tage aktiv; `privacy/erase` löscht das aktuelle Item, aber nicht
  PITR-Backups. Das ist ein Retention-/DSGVO-Risiko, kein B2-Ausführungsblocker,
  aber vor Produktion zu entscheiden.
- Erase/Anonymize schreibt kein dauerhaftes Erasure-Ledger; `operationId` ist
  nur in der Response. Ein Nachweis ist derzeit nur über Testreport/CloudWatch
  möglich, nicht über ein Produkt-Audit-Objekt.
- Der `erase`-Delete-Condition enthält `subjectId` und `version`, aber nicht
  `consumerId`; die Consumer-Prüfung erfolgt vorher im Speicher. Bei
  unveränderlichem `consumerId` ist das ausreichend; eine TOCTOU-Analyse für
  direkte Fremdschreibpfade bleibt offen.

---

## 7. GSI2- und F-PRV-01-Bewertung

### GSI2

Tatsächliche Projektion:

```text
gsi2: INCLUDE
orderId, subjectId, version, createdAt, status, updatedAt,
customer, totalAmount, currency
```

`consumerId` ist **nicht** projiziert. Genau deshalb war die frühere
Erase-Implementierung falsch: Sie las `consumerId` aus dem Index und verwarf
bei gesetztem Scope alle Treffer.

### F-PRV-01

Deployed und lokal verifiziert:

1. GSI2-Query liefert nur `orderId`.
2. Pro Treffer erfolgt `_load_order_item()` mit `ConsistentRead`.
3. Das vollständige Item enthält `consumerId`.
4. `privacy_scope_consumer(context)` filtert danach.
5. Fremde Consumer und Legacy-Items ohne `consumerId` werden nicht verarbeitet.
6. `erase` löscht nur nach `subjectId` + `version`; der Scope-Filter schützt
   vor fremden Consumer-Daten.

Bewertung:

```text
GSI2 Consumer Isolation:  IMPLEMENTED / LOCAL VERIFIED / DEPLOYED
F-PRV-01:                 FIXED / LOCAL VERIFIED / DEPLOYED
Live Evidence:            NOT EXECUTED (B2)
Residual:                 optionaler Scope; kein Index-Level-Tenanting
```

**Wichtige Einschränkung:** Ohne gesetzten `consumerId`-Scope bleibt das
Verhalten deployment-weit (nur nach `subjectId`). Für B2 muss jeder
Privacy-Aufruf explizit `consumerId` mitsenden. Cross-Consumer-Isolation auf
Indexebene ist nicht implementiert und würde einen zweiten Client/Pool oder
Schemaänderungen erfordern.

---

## 8. B2-Live-Testmatrix

Alle Tests sind derzeit **BLOCKED — CONFIGURATION REQUIRED**, weil weder
Secret noch least-privilege Invoke vorhanden sind. Die Matrix beschreibt die
spätere Ausführung; sie wurde **nicht** ausgeführt.

### A — Authentifizierung

| ID | Aktion | Erwartung | Status |
|---|---|---|---|
| G3X-PRV-X02 | falsches Projekt | 400 `VALIDATION_ERROR`, kein DDB-Read | **BLOCKED** |
| G3X-PRV-X03 | falsches `internal_token` | 400, kein DDB-Read | **BLOCKED** |
| G3X-PRV-X04 | `authorized=false` | 400, kein DDB-Read | **BLOCKED** |
| G3X-PRV-X13 | Secret fehlt | 400 „Internal secret not configured“, kein DDB-Read | **BLOCKED** (kein Invoker; X13 muss ggf. vor Secret-Aktivierung laufen) |
| — | unzulässige öffentliche Route | keine Privacy-Route; API liefert keinen internen Dispatch | **READ-ONLY BESTÄTIGT** |

### B — Inspect

| ID | Aktion | Erwartung | Status |
|---|---|---|---|
| G3X-PRV-X01 | Inspect Subject A | 200, `COMPLETED`, 2 Referenzen, keine PII | **BLOCKED** |
| G3X-PRV-X01-EMPTY | Inspect unbekanntes Subject | 200, `COMPLETED`, 0 | **BLOCKED** |
| G3X-PRV-X01-FOREIGN | A-Daten mit B-Daten gemischt, Scope A | nur A; B/legacy nicht enthalten | **BLOCKED** |
| G3X-PRV-X01-CONSUMER | A mit fremdem Consumer-Fixture, Scope A | fremder Consumer ausgeschlossen | **BLOCKED** |

### C — Export

| ID | Aktion | Erwartung | Status |
|---|---|---|---|
| G3X-PRV-X05 | Export A | `COMPLETED`, 2 Orders, definierte Felder, keine internen Felder | **BLOCKED** |
| G3X-PRV-X06 | Export B | nur B, A fehlt | **BLOCKED** |
| G3X-PRV-X05-CONSUMER | Export A mit Scope A | fremder Consumer/legacy fehlt | **BLOCKED** |
| — | Datenvollständigkeit | Customer, Items, Status, Processing-Felder soweit vorhanden; keine `pk`/`sk`/`consumerId`/`gsi*` | **BLOCKED** |

### D — Erasure

| ID | Aktion | Erwartung | Status |
|---|---|---|---|
| G3X-PRV-X07 | Erase PREVIEW A, Policy ERASE | `PREVIEW`, 2 geplant, keine Mutation | **BLOCKED** |
| G3X-PRV-X08 | Erase EXECUTE ohne Policy | `BLOCKED`, 0 Deletes | **BLOCKED** |
| G3X-PRV-X09 | Erase B, Policy ERASE | 1 gelöscht; Wiederholung 0, idempotent | **BLOCKED** |
| G3X-PRV-X10 | RETAIN A | `PARTIALLY_COMPLETED`, 2 retained, keine Mutation | **BLOCKED** |
| G3X-PRV-X11 | ANONYMIZE eine A-Order | 1 anonymisiert; Owner-GET danach 404; PII/Ergebnis entfernt | **BLOCKED** |
| G3X-PRV-X12 | Consumer-Scope-Erase | **F-PRV-01-Fix:** 1 eigener Consumer gelöscht; fremder Consumer/legacy unberührt | **BLOCKED** |
| — | Versionskonflikt/Pagination | lokale Verträge; kein deterministischer Live-Test ohne Parallel-Write | **COVERED LOCAL / LIVE NOT EXECUTED** |

`G3X-PRV-X12` wurde im Manifest von der veralteten Defect-Erwartung
(`0 affected`) auf das korrigierte F-PRV-01-Verhalten aktualisiert.

### E — Cleanup

| Aktion | Erwartung | Status |
|---|---|---|
| API-Order A1/A2 und B1 exakt löschen | Owner-Key `ord_<id>`, `sk=#ORDER`; keine fremden Keys | **PLAN READY** |
| ANONYMIZE-Order exakt löschen | Key bekannt; `subjectId` wurde entfernt, daher separater Key-Cleanup | **PLAN READY** |
| Fremder-Consumer-Fixture exakt löschen | run-präfixierter Key; keine fremden Daten | **PLAN READY** |
| Cognito-Testbenutzer A/B löschen | `AdminDeleteUser`; Pool 0 | **PLAN READY** |
| Queue/DLQ | 0/0; kein Purge | **PLAN READY** |
| Tabelle/GSI2/GSI3 | 0/0/0 | **PLAN READY** |

---

## 9. Minimale Konfigurationsoptionen

| Option | Änderungen | Sicherheitsrisiko | Rückbau | Empfehlung |
|---|---|---|---|---|
| **A — Keine Änderung** | keine | B2 nicht ausführbar | — | **nicht ausreichend** |
| **B — Ephemeres Env-Secret + dedizierte Test-Rolle** | `PRIVACY_INTERNAL_SECRET` temporär per `update-function-configuration`; IAM-Rolle nur `lambda:InvokeFunction` auf Handler; Secret-Ermittlung getrennt/out-of-band | Secret in Lambda-Env für `lambda:GetFunctionConfiguration` sichtbar; manueller Drift; kein Secret-Manager-Audit | Env-Key entfernen, Rolle löschen, Secret verwerfen; CodeSha unverändert | **für einen einmaligen B2-Lauf empfohlen, nur mit expliziter Freigabe** |
| **C — Secrets Manager + Provider + IAM + Terraform** | neues Secret, KMS/Provider, `PRIVACY_SECRET_ID`/Provider, Handler-Code, IAM, Policy-Gate-Allowlist | höherer Implementierungsaufwand; neue Abhängigkeiten; Gate-Erweiterung | Secret/Rolle/Env zurückbauen; Terraform-Plan/Apply separat | **Produktivziel, nicht B2-Prep** |
| **D — Öffentliche Privacy-API-Route** | neue API-Route | vergrößert Angriffsfläche; widerspricht bestehendem Vertrag | Route entfernen | **abgelehnt** |
| **E — Bestehende breite Identität (`Mayaws`/AI/Human)** | keine IAM-Neuentwicklung | Administrator-/`lambda:*`-Rechte; kein Least Privilege; Secret-lesbar | keine saubere Rückbaugrenze | **abgelehnt** |

### Empfohlenes Minimalmodell für einen späteren B2-Lauf

1. Einmaliges, zufälliges Secret außerhalb von Git/State erzeugen.
2. `PRIVACY_INTERNAL_SECRET` **nur für das Testfenster** in die Handler-Env
   setzen; keine dauerhafte Terraform-Variable, kein Klartext in Plan/State.
3. Eine temporäre IAM-Rolle mit ausschließlich:
   ```text
   lambda:InvokeFunction
   Resource: arn:aws:lambda:eu-central-1:240571105849:function:mays-orders-rc4-test-handler
   ```
   anlegen; keine `lambda:Get*`, keine `dynamodb:*`, keine `iam:*`.
4. Secret an den Operator out-of-band übergeben; nicht in argv, History, Logs
   oder Report.
5. Nach dem Lauf: Env-Key entfernen, Rolle löschen, Secret verwerfen, Cleanup
   verifizieren.
6. Kein `AdministratorAccess` als Test-Invoker.

**Wichtig:** Auch Option B ist eine AWS-/Lambda-Konfigurationsänderung und
benötigt eine neue ausdrückliche Live-Freigabe. Sie ist in diesem Prep-Task
nicht ausgeführt.

---

## 10. Risiko- und Rollback-Bewertung

| Risiko | Bewertung | Gegenmaßnahme |
|---|---|---|
| Secret fehlt | B2 blockiert | temporäre Env-Variable oder P00-Implementierung |
| Secret in Env lesbar | jeder mit `lambda:Get*` kann es lesen | dedizierte Rolle ohne Get; Secret nur kurz; Rotation |
| Broad Admin als Invoker | Umgehung des Least-Privilege-Modells | dedizierte Invoke-Rolle; kein `Mayaws` |
| Falsches Projekt/Token | fail-closed 400 | Negativtests X02/X03 |
| Consumer-Scope vergessen | deployment-weite Sicht/Löschung | Scope im Test immer setzen; X12 |
| `consumerId` nicht in Delete-Condition | TOCTOU-Restrisiko | Scope vorher; unveränderliche Consumer-Annahme dokumentieren |
| PITR/Backups | Erasure entfernt keine 35-Tage-Backups | Retention-/Backup-Entscheidung P00 |
| TTL/Retention fehlt | keine automatische Löschung | P00/P-08 |
| Kein Erasure-Ledger | kein dauerhafter Produkt-Audit-Trail | separates Ledger/Entscheidung |
| Secret in Terraform-Plan/State | Leak-Risiko | kein Klartext in IaC; Secrets Manager/Provider |
| Policy Gate blockiert Secret/KMS | IaC-Pfad nicht applybar | P-15-Gate-Erweiterung separat |
| Cleanup nach ANONYMIZE | `subjectId` entfernt; Owner-Cleanup greift nicht | exakter Key aus Testprotokoll |

### Rollback

- Env-Secret entfernen; Handler-Konfiguration auf vorherigen Stand prüfen.
- Temporäre Test-Rolle löschen.
- Testdaten exakt löschen; Queue/DLQ nicht purgen.
- Lambda-CodeSha muss unverändert `FYTu…` bleiben.
- Keine Terraform-Apply-/Destroy-Aktion im B2-Rollback ohne separate Freigabe.

---

## 11. Blocker und offene Fragen

### Harte Blocker

1. `PRIVACY_INTERNAL_SECRET` fehlt in der Handler-Env.
2. Kein dediziertes least-privilege Invoke-Prinzipal.
3. Kein Privacy-Secret in Secrets Manager/SSM/KMS.
4. Terraform Policy Gate erlaubt Secret/KMS-Ressourcen nicht.

### Offene Entscheidungen

- Soll B2 mit einem **ephemeren Env-Secret** (Option B) oder erst nach
  **P00-Secrets-Manager-Implementierung** (Option C) laufen?
- Welche Identität darf den einmaligen Test-Invoke ausführen?
- Darf das Secret für das Testfenster in der Lambda-Env stehen, oder ist das
  wegen `lambda:GetFunctionConfiguration` ausgeschlossen?
- Wie wird der Erasure-Nachweis über die Response hinaus dokumentiert?
- Wie werden PITR-Backups (35 Tage) bei Erasure behandelt?
- Bleibt `RETAIN` ohne Frist ein reiner No-op? (P00/P-08 offen)
- Cross-Consumer-Isolation: zweiter Client/Pool erforderlich; nicht Teil von B2.
- Sollen `inspect`/`export` standardmäßig einen Consumer-Scope verlangen?
  Aktuell ist er optional; das ist ein Contract-/Security-Entscheid.

---

## 12. Empfohlener nächster Schritt

**Nicht B2-Live sofort ausführen.** Zuerst eine separate, ausdrücklich
freigegebene Entscheidung:

1. **Option B** für einen einmaligen B2-Lauf: ephemeres Secret + dedizierte
   Invoke-Rolle, kein Admin, kein dauerhaftes Secret; **oder**
2. **Option C** als P00-Produktivpfad: Secrets Manager/Provider, IAM,
   Policy-Gate, Rotation, Retention; danach B2.

Für die eigentliche B2-Ausführung ist ein neues, enges Testmanifest mit
Run-ID, zwei Testidentitäten, A/B-Orders, fremdem Consumer-Fixture,
Owner-verifiziertem Cleanup und Abbruchregeln erforderlich. Die vorhandene
G3X-PRV-Matrix bleibt die Grundlage; X12 ist auf den F-PRV-01-Fix korrigiert.

**Keine automatische B2-Ausführung, keine Secret-Erstellung, kein Terraform,
keine G4-Freigabe.**

---

## 13. Auditlog-Nachweise

Vorgesehener Eintrag:

```text
MO-RC3-RC4-G3-LIVE-B2-PREP-01 → docs/reports/MO-RC3-RC4-G3-LIVE-B2-PREP-01.md
(read-only Privacy-Discovery: inspect/export/erase + interner Dispatch vorhanden,
lokal 345/44 PASS, deployed CodeSha FYTu… mit F-PRV-01; AWS: keine Privacy-Route,
kein Function URL, Handler-Env ohne PRIVACY_INTERNAL_SECRET, keine
Secrets-Manager-/SSM-/KMS-Referenz, Resource-Policy nur API GW, keine
least-privilege Invoke-Rolle, GSI2 ohne consumerId, TTL DISABLED, PITR 35 Tage;
B2 CONFIGURATION REQUIRED; keine AWS-Mutation/Invoke/Secret-Wert, kein
Terraform, kein Push; G3X-PRV-X12 auf F-PRV-01-Fix korrigiert)
```

---

## 14. Commit-SHA und Working-Tree-Status

| Feld | Wert |
|---|---|
| Dokumentations-Commit | `54bf6d82eb73bdcc165cdd501d35cbc67fe6d089` |
| Working Tree nach Commit | CLEAN |

Geänderte Dokumentation:

- `docs/reports/MO-RC3-RC4-G3-LIVE-B2-PREP-01.md` (neu)
- `docs/reports/MO-RC3-RC4-G3-EXT-LIVE-TEST-MANIFEST.md` (X12 korrigiert)
- `docs/AI_AUDITLOG.md` (Index)

Keine Produkt-, Test-Harness-, Terraform-, IAM-, Cognito- oder AWS-Änderung.
