# MO-RC3-RC4-G2-TEST-COMPLETION

**RC3/RC4-Testabschluss: Kompatibilität, Order-Tests, Privacy und Release-Evidenz**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor G2:** `224a1e606385cf7d909f4dd0919083c7d49c7e6a`
**Modus:** lokale Tests und Dokumentation; keine AWS-/Terraform-Mutation,
keine Produktänderung, keine Live-E2E-Ausführung, kein Push/Merge.

---

## 1. Executive Summary

G2 schließt drei lokale Testlücken und bestätigt die vorhandene RC3-/RC4-
Kompatibilität:

- **RC3-Order-Body ohne `orderType`** bleibt gültig und wird als `generic`
  verarbeitet; RC4-Felder bleiben additiv.
- **RC4-namespaced `orderType` ohne registrierten Handler** wird fail-closed
  mit Batch-Failure behandelt; kein Statuswrite.
- **Privacy-Policy `RETAIN`** verändert weder Item noch Status und wird
  korrekt als `PARTIALLY_COMPLETED` ausgewiesen.

Es wurden **keine neuen Produktdefekte** gefunden und **keine Produktänderung**
durchgeführt. Die drei neuen Tests verwenden die produktiven Handler/Services
mit lokalen Fakes.

Aktuelle lokale Baseline:

```text
Installer:      669 PASS
Builder:        128 PASS
Lambda:         340 PASS
E2E-Harness:     16 PASS
Gesamt:       1.153 PASS
Seed-Tools:      28 PASS (separat)
Live-E2E:         4 BLOCKED
```

Gegenüber 13A: **+3 Lambda-Tests** (RC3-Kompatibilität, Unknown-Type-Fail-
Closed, RETAIN-No-Mutation).

---

## 2. Ausgangsbasis und Git

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD vor G2 | `224a1e606385cf7d909f4dd0919083c7d49c7e6a` |
| Testbaseline 13A | 669 / 128 / 337 / 16 = **1.150 PASS**, 28 Seed, 4 Live BLOCKED |
| Working Tree | CLEAN |
| Neue Tests | 3 (2 Order-Kompatibilität, 1 Privacy-Retention) |
| Produktcode | unverändert |

---

## 3. RC3-/RC4-Kompatibilität

### 3.1 Verträge

| Bereich | RC3 | RC4 | Ergebnis |
|---|---|---|---|
| `POST /orders` Body | `customer`, `items`, `currency` | optional `orderType`, sonst unverändert | **kompatibel** |
| `orderType` | nicht vorhanden | Default `generic`, namespace-fähig | **additiv** |
| Owner | kein gespeicherter JWT-Owner | `subjectId`/`consumerId`/GSI2 aus JWT | **RC4-Vertrag**; unautorisierte Aufrufe fail-closed |
| `subjectId` im Body | nicht erlaubt | weiterhin unbekanntes Feld → 400 | **kompatibel/strenger** |
| Statusmodell | PENDING…DELIVERED/CANCELLED | unverändert | **kompatibel** |
| Worker-Nachricht | `{orderId, status}` | unverändert; `orderType` aus Item, nicht Nachricht | **kompatibel** |
| Worker-Update | einfacher Statuswrite | Condition/Version, Batch-Fehler | **RC4-Härtung**, kompatibel |
| SQS | ursprünglich keine DLQ | DLQ/Redrive additiv | **RC4-Erweiterung** |
| API-Antwort | Order-Felder | interne Identity-/Processing-Felder gefiltert | **kompatibel** |
| Module/Build | RC3-Vertrag | Builder 128, Installer 669 unverändert | **keine Regression im lokalen Test** |

### 3.2 RC3-Legacy-Verhalten

- Legacy-Orders ohne `subjectId`/`consumerId` sind über die API **nicht lesbar**
  (404, fail-closed) — bestehender RC4-P02H-Vertrag; kein Fremdzugriff.
- Der Worker kann eine generische Legacy-Nachricht weiterhin verarbeiten.
- Ein RC3-Body ohne `orderType` wird als `generic` gespeichert und verarbeitet.
- Das `orderBody` bleibt Eigentum des Order-/Ressourcenmoduls; es wurde keine
  neue Privacy-/DSGVO-Fachlogik eingeführt.

### 3.3 Neue Kompatibilitätstests

In `lambda/tests/test_order_processing_component.py`:

1. `test_rc3_legacy_payload_without_order_type_keeps_contract`
   - echter `index.handler` + `OrderService` + Fake-DynamoDB/Fake-SQS,
   - `orderType=generic`, PENDING, Owner/GSI2, RC3-Antwortfelder,
   - keine internen Felder in der Response.

2. `test_rc4_namespaced_unknown_type_fails_closed_without_status_write`
   - gültiger namespaced `orderType` ohne registrierten Handler,
   - Worker liefert `batchItemFailures`, Status bleibt PENDING, Version 1.

---

## 4. Privacy-Werkzeugkasten

Geprüft wurden die vorhandenen Funktionen, ohne neue DSGVO-Logik:

- Inspect: Subject-/Consumer-/Scope-Isolation, Pagination.
- Export: Subject-/Scope-Isolation, keine internen Felder, Pagination.
- Erase: PREVIEW, EXECUTE, ERASE, ANONYMIZE, RETAIN, Idempotenz.
- Retention-Regeln: explizite Policy erforderlich; fehlende Policy blockiert.

Bereits vorhandene Tests decken Auth-Boundary, Scope-Isolation, Fremddaten-
Schutz, idempotentes Erase und `ANONYMIZE` ab.

### Neuer RETAIN-Test

`test_erase_retain_policy_does_not_mutate` in
`lambda/tests/test_order_service.py`:

- nutzt den produktiven `OrderService.erase_subject`,
- verbietet Delete/Update im Fake-Table,
- erwartet `PARTIALLY_COMPLETED`, `retainedRecords=1`,
- `deletedRecords=0`, `anonymizedRecords=0`.

Damit ist die bisher fehlende explizite RETAIN-No-Mutation-Evidenz lokal
geschlossen.

---

## 5. Tatsächlich ausgeführte Tests

| Suite | Kommando | Ergebnis | Laufzeit |
|---|---|---|---:|
| Installer | `python3 -m unittest discover -s installer/tests` | **669 PASS** | 18,2 s |
| Builder | `python3 -m unittest discover -s module_builder/tests` | **128 PASS** | 1,6 s |
| Lambda | `PYTHONPATH=src python3 -m unittest discover -s tests` | **340 PASS** | 0,4 s |
| E2E-Harness lokal | `python3 -m unittest discover -s tests -p 'test_e2e_harness.py'` | **16 PASS** | 0,002 s |
| Seed-Tools | `cd scripts && python3 -m unittest discover -s tests` | **28 PASS** | 0,17 s |
| Live-E2E | `python3 -m unittest tests.test_e2e_async_order` ohne Opt-in | **4 SKIP/BLOCKED** | 0,0 s |

Keine unerwarteten Skips in der lokalen Baseline. Die vier Live-Skips sind
beabsichtigt und nicht als PASS gewertet.

### Fokussierte neue Tests

```bash
cd lambda
PYTHONPATH=src python3 -m unittest \
  tests.test_order_processing_component \
  tests.test_order_service
```

```text
Ran 85 tests — OK
```

---

## 6. Coverage

| Komponente | Statement | Branch | Stand |
|---|---:|---:|---|
| Lambda | **90,34 %** | **82,56 %** | neu gemessen nach G2 |
| Installer (inkl. Policy) | **74,08 %** | **64,04 %** | 11A, Produktcode unverändert |
| Builder | **91,22 %** | **84,93 %** | 10D/128 Tests |
| E2E-Harness separat | **91,58 %** | **88,46 %** | 10D/16 Tests |

Hinweis: Coverage ist ein lokaler Code-Indikator, kein Live-Nachweis. Die neuen
Tests erhöhen die Lambda-Coverage leicht (+0,19 % Statement/+0,34 % Branch).

---

## 7. Wiederverwendete Modul-/Builder-Nachweise

- **Builder:** `MO-BUILDER-UPGRADE-P2-01`; 128 PASS; keine Änderung.
- **Installer:** 10A/11A-Nachweise; 669 PASS; SEC-01…05 korrigiert; SEC-06
  bleibt separater Vertragsentscheid.
- **Order-Modul:** P02/P02I-Reports sowie 10B-Komponentenpfad.
- **Test-/Coverage-Basis:** 10D, 11A, 13A.
- **AWS:** Apply-07 und Functional-Verify-08 als Infrastruktur-/Blocked-
  Nachweise; keine erneute AWS-Ausführung in G2.

---

## 8. Korrigierte Defekte

| Defekt | Status in G2 |
|---|---|
| SEC-01 ApprovalGate-RecursionError | bereits in 11A behoben |
| SEC-02 `_has_valid_deployment_id` | bereits in 11A behoben |
| SEC-03 Planintegritäts-Namen | bereits in 11A behoben |
| SEC-04 Plan-Match | bereits in 11A behoben |
| SEC-05 Workspace-Root | bereits in 11A behoben |
| SEC-06 Approval-Bindung | **CONTRACT GAP / NEEDS DECISION**, nicht Teil G2 |
| Neue G2-Defekte | **keine bestätigt** |

G2 hat ausschließlich Tests ergänzt; keine Produktdatei wurde geändert.

---

## 9. Verbleibende Live-E2E-Blocker

1. Keine autorisierte, vorab provisionierte Testidentität.
2. Keine sichere, eigentümergebundene Live-Cleanup-Fähigkeit.
3. Keine echte SQS-/DLQ-Zustellung.
4. Keine echte GSI3-/Recovery-Ausführung mit Daten.
5. Kein produktiver Processing-Handler über `generic`.
6. Kein aktueller RC3→RC4-Live-Flow.
7. P00-Scope KMS/Secrets/Retention weiterhin offen.

Live-Tests bleiben **BLOCKED**; keine AWS-Mutation in G2.

---

## 10. RC3-/RC4-Testmatrix

| Testbereich | RC3-Nachweis | RC4-Nachweis | Status |
|---|---|---|---|
| Legacy Order-Body | API/Validation-Doku + Tests | neuer Legacy-Body-Test | **PASS lokal** |
| Owner/Identity | historischer P01-Befund | P02/P02A/Index/Service-Tests | **PASS lokal**, Live BLOCKED |
| Status/API | State-Machine-Tests | API/State/Component-Tests | **PASS lokal** |
| Worker/SQS | Phase-2-Vertrag | 10B/SQS-Tests | **PASS lokal**, Live BLOCKED |
| Idempotenz/Retry | Phase-2-Befund | Worker-/Conflict-Tests | **PARTIAL** (API-Key offen) |
| DLQ | historisch nicht vorhanden | Terraform + Batch-Failure-Tests | **PARTIAL/LIVE BLOCKED** |
| Privacy inspect/export/erase | P02-Design | Service-Tests + RETAIN neu | **PASS lokal**, Secret/Live blockiert |
| GSI3/Recovery | nicht RC3 | P02I/Recovery-Tests | **PASS lokal**, Live BLOCKED |
| Modul-Builder | RC3-Vertrag | 128 PASS | **PASS lokal** |
| Installer/Upgrade | RC3-Gates | 669 PASS, 11A-Fixes | **PASS lokal**, SEC-06 separat |
| P00 KMS/Secrets/Retention | P00-Plan | nicht implementiert | **NOT IMPLEMENTED/OPEN** |

---

## 11. Release-Relevanz

**Lokal abgeschlossen:**

- RC3-Body/`orderType`-Kompatibilität.
- Owner-/Status-/API-/Worker-Verträge im lokalen Fake-Pfad.
- Privacy-RETAIN-No-Mutation.
- Builder 128, Installer 669, Lambda 340, E2E 16.

**Weiterhin nicht ausreichend für eine RC4-Gesamtfreigabe:**

- authentifizierter Live-Order-Flow,
- Live-Cleanup/Testidentität,
- DLQ/Retry live,
- GSI3/Recovery live,
- produktiver Processing-Handler,
- API-Idempotenz,
- P00-Scope KMS/Secrets/Retention.

---

## 12. Git

Vorgesehen:

```text
Test-Commit: test(rc4): add rc3 compatibility and retention coverage
Commit bereits: be77bf4a1d928cb8ba4c7f1e16c35aac47289ff6
Doku-Commit: docs(rc3,rc4): complete g2 test evidence
```

Kein Push, kein Merge, keine AWS-/Terraform-Mutation. Der finale HEAD/Status
wird nach dem Doku-Commit verifiziert.
