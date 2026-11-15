# MO-RC3-RC4-G3-EXT-ORCHESTRATION

**Orchestrated RC3/RC4 release verification preparation**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `8736dc88f571b95ed05e49b026865c4a38e3cf17`
**Modus:** Commander-Analyse und Testvorbereitung; **keine neuen mutierenden
AWS-Live-Tests**, keine Produktänderung, keine Terraform-Mutation, kein Push/Merge.

```text
STATUS: READY FOR LIVE APPROVAL
G4 RELEASE READINESS: NOT READY — OPEN DECISIONS / DEFECTS
```

---

## 1. Executive Summary

Die vier parallelen Read-only-Agenten haben den RC4-Stand konsolidiert:

- **Lokale Baseline:** 1.153 PASS (669 Installer, 128 Builder, 340 Lambda,
  16 E2E-Harness), zusätzlich 28 Seed-Tests.
- **Live-Basis:** 4/4 vorhandene Live-E2E-Tests PASS (G3), Cleanup verifiziert.
- **Nicht ausreichend für RC4-Gesamtfreigabe:**
  - DLQ-/Retry-Zustellung nicht absichtlich live getestet,
  - GSI3/Recovery nicht live ausgeführt,
  - Privacy live durch fehlendes Secret blockiert,
  - nur `generic` produktiv registriert,
  - API-Idempotenz fehlt,
  - P00 KMS/Secrets/Retention nicht implementiert/entschieden,
  - SEC-06 Approval-Bindung offen.

Zwei konkrete Produkt-/Sicherheitsbefunde wurden durch die Agenten bestätigt:

1. **F-PRV-01:** Consumer-scoped Erase ist im echten DynamoDB ein stiller
   No-op, weil GSI2 `consumerId` nicht projiziert; lokale FakeTests verdecken
   das. Fail-closed, aber funktional falsch, sobald Scope genutzt wird.
2. **GSI3-Recovery-GAPs:** Starvation durch `CANCELLED`/Budget-Einträge und
   `STALE`-Stranding bei Status `PROCESSING`/`SHIPPED` wurden lokal
   reproduziert.

G4 ist deshalb **nicht** freigabereif. Der Live-Testmanifest ist für eine
neue ausdrückliche Freigabe vorbereitet, aber nicht ausgeführt.

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `8736dc88f571b95ed05e49b026865c4a38e3cf17` |
| Working Tree | CLEAN |
| Basis | G1/G2/G3 abgeschlossen |
| Letzter Test-Commit | `e422330` |
| Letzter G3-Doku-Commit | `8736dc8` |

---

## 3. Agentenaufträge und Ergebnisse

### Agent A — DLQ & Retry

**Status:** COMPLETE (read-only), YELLOW.

**Befund:**

- `_SUCCESS_OUTCOMES` ackt `processed`, `noop`, `stale`, Processing-Success/
  -Failure und Claim-Skip; `rejected`, `missing`, `unknown_type`,
  `handler_failed` und Parse-Fehler führen zu `batchItemFailures`/Retry.
- `maxReceiveCount=1` → genau **ein** Verarbeitungsversuch, danach Redrive.
- Terraform: DLQ, Redrive, 60 s Visibility, 4 d/14 d Retention, DLQ-Alarm,
  ESM `batch_size=5`, `ReportBatchItemFailures`; Worker-IAM ohne DLQ/SendMessage.
- Lokale Tests: 27 SQS-Handler-Tests, 17 Safety-Tests, Component-Tests;
  keine absichtliche Live-DLQ-Zustellung.
- Die G3-Cleanup-Race-DLQ-Nachricht ist **kein bestandener DLQ-Test**.

**Minimaler Live-Plan:** DLQ-01 (malformed) und DLQ-02 (missing order) ohne
DDB-Write; optional DLQ-03 (invalid transition) / DLQ-04 control. Kein Purge;
Receive/Delete nur eigener Marker.

### Agent B — GSI3 & Recovery

**Status:** COMPLETE (read-only), ORANGE.

**Befund:**

- P02F pending recovery via GSI1; P02I processing recovery via GSI3.
- Processing recovery sendet nur SQS, schreibt nicht; Claim/Completion/
  Release/Anonymize pflegen GSI3.
- 340 Lambda-PASS, davon 55 Recovery-Tests; GSI3 read-only ACTIVE/0 Items.
- **GAP-01/02:** `CANCELLED`/budget-exhausted GSI3 entries können den
  `limit` verbrauchen und gültige Orders starren.
- **GAP-03:** Status `PROCESSING`/`SHIPPED` mit expired Claim erhält
  `CONFIRMED`, Worker klassifiziert `STALE`; Order bleibt gestrandet.
- Kein produktiver Processing-Handler; Live-Claim-Dedupe nicht nachweisbar.
- Geplanter Fixture-Test mit 10 synthetischen Items, 8 Kandidaten, 4 Sendungen,
  Duplikat-/Status-/Isolationsprüfung; keine Ausführung.

### Agent C — Privacy Toolkit

**Status:** COMPLETE (read-only), ORANGE.

**Befund:**

- Inspect/Export/Erase/ANONYMIZE/RETAIN und Scope-/Owner-Isolation sind
  implementiert; 36 Privacy-Tests + 340 Lambda lokal PASS.
- Live blockiert, weil `PRIVACY_INTERNAL_SECRET` nicht provisioniert ist;
  keine Secrets-Manager-/SSM-/KMS-Ressource, keine `lambda:InvokeFunction`-
  Testrolle, keine HTTP-Route.
- **F-PRV-01 (bestätigt):** `erase_subject` liest `consumerId` aus einer
  GSI2-Projektion, die `consumerId` nicht enthält. Bei gesetztem Scope wird
  daher kein Item als „in scope“ erkannt; `affectedRecords=0`, keine Löschung.
  Lokale FakeTests ignorieren `ProjectionExpression` und verdecken den Fehler.
- Weitere Befunde: PREVIEW ohne Policy zeigt `affectedRecords>0` aber
  `planned*=0`; BLOCKED-Payloads mit HTTP 200; ANONYMIZE zerstört die
  `subjectId`-Ownership für den bestehenden Live-Cleanup.
- Keine neuen DSGVO-Features wurden vorgeschlagen.

### Agent D — RC3/RC4 Compatibility & Release

**Status:** COMPLETE (read-only), ORANGE.

**Befund:**

- RC3-POST-Body ohne `orderType` ist kompatibel; RC4 ergänzt Identität,
  `orderType`, Worker-Härtung, Processing, GSI3, DLQ.
- **Breaking:** RC3-Bestandsorders ohne `subjectId`/`consumerId` sind über
  RC4-API nicht lesbar (404), Staff-Listen entfallen; keine Migration.
- Nur `generic` produktiv registriert; Processing/GSI3 ist Infrastruktur,
  nicht produktiv aktiviert.
- API-Idempotenz fehlt; identische POSTs erzeugen neue Orders.
- P00 KMS/Secrets/Retention ist **nicht implementiert** und nicht formell
  aus RC4 entfernt.
- SEC-06 Approval-Bindung bleibt CONTRACT GAP.
- Historische RIS-/RC3-Evidence ist **kein** aktueller RC4-Live-Nachweis.
- `deployment_version` default `0.1.0`; Release-Label/Version offen.
- Builder: `orders-service`-Komposition stabil, aber GSI3/DLQ/Queue-Änderungen
  und Legacy-Manifest-Blocks sind Consumer-relevant.
- Haupt-Pipeline `directAWSGit` Auto-Apply bleibt eigener Releaseblocker.

---

## 4. Konsolidierte RC3/RC4-Matrix

| Bereich | Lokal | Live | Nächste Aktion |
|---|---|---|---|
| DLQ/Retry | Mechanik + 27/17 Tests PASS | **Offen** | Gezielter DLQ-01/02-Test |
| GSI3/Recovery | 55 Recovery-Tests PASS | **Offen** | Fixture-Test; GAP-01/02/03 entscheiden |
| Privacy Toolkit | 36 Privacy-Tests PASS | **BLOCKED** (Secret) | Secret-/Invoke-Entscheidung |
| RC3→RC4 | Legacy-Body lokal PASS | **Teilweise** (G3 Basisflow) | Bestandsdatenfluss/Migration |
| Handler-Routing | Registry/Processing lokal PASS | **Nur generic** | Processing-Aktivierung entscheiden |
| API-Idempotenz | Worker idempotent | **API fehlt** | Vertrag entscheiden |
| P00 KMS/Secrets/Retention | **Nicht implementiert** | **Offen** | Formelle Scope-Entscheidung |
| SEC-06 | Contract Gap | **Offen** | Separat bewerten |

---

## 5. Wiederverwendete Evidence

- G1: Evidence-Discovery, P00/P02/P02I, AWS-Snapshot.
- G2: 1.153 lokale PASS + 28 Seed + RC3-Kompatibilitätstests.
- G3: 4/4 Live-PASS, Owner-Cleanup, Tabelle/Queues/User 0.
- Apply-07: State serial 8, 39 Ressourcen, `mo_version=0.2.0`, GSI3 ACTIVE.
- Functional-08: unauth 401, Auth/SQS/Worker/GSI3 blocked, DLQ not executed.
- Builder 128, Installer 669, Lambda 340, E2E 16.
- Historical RIS/RC3 evidence only as historical, not current RC4 proof.

---

## 6. Tatsächlich ausgeführte lokale Tests

| Ausführung | Ergebnis |
|---|---|
| G2-Gesamtbaseline | **1.153 PASS** |
| Agent B Lambda | **340 PASS** (davon 55 Recovery) |
| Agent C Lambda/Privacy | **340 PASS**, **36 Privacy PASS** |
| G3 Live | **4/4 PASS**, 13,776 s |
| Seed | **28 PASS** |
| Live-Erweiterung in G3-EXT | **NICHT AUSGEFÜHRT** |

Keine neuen Tests in G3-EXT implementiert; keine Produktdatei geändert.

---

## 7. Vorbereitete AWS-Live-Szenarien

Details: `docs/reports/MO-RC3-RC4-G3-EXT-LIVE-TEST-MANIFEST.md`.

| Test-ID | Ziel | Status |
|---|---|---|
| G3X-DLQ-01/02 | Malformed/missing order → DLQ, kein DDB-Write | **READY, not executed** |
| G3X-DLQ-03/04 | Invalid transition + control | **READY, not executed** |
| G3X-GSI3-01… | 10 Fixture-Items, Recovery/No-write/Duplicate | **READY, not executed** |
| G3X-PRV-X01… | Inspect/Export/Erase/ANONYMIZE/RETAIN | **BLOCKED** (Secret + F-PRV-01) |
| G3X-COMPAT-01/02 | RC3-Legacy, explicit/unknown orderType | **READY, not executed** |
| G3X-LIVE-01 | Existing 4-test suite | **ALREADY PASS (G3)** |

---

## 8. Sicherheits- und Cleanup-Konzept

- Nur Account `240571105849`, Region `eu-central-1`, Stack
  `mays-orders-rc4-test`.
- Keine Produktions-/RIS-Ressource.
- Live-Mutationen nur nach separater Freigabe:
  Cognito-Testbenutzer, API-Orders, SQS-Testnachricht, ggf. DDB-Fixtures,
  Lambda-Invoke.
- Cleanup ausschließlich eigener Daten:
  - Owner-verifizierte Order-Deletes (`subjectId == E2E_SUBJECT`),
  - Receive/Delete eigener DLQ-Nachrichten (kein Purge),
  - `AdminDeleteUser` für Testbenutzer,
  - danach Tabelle/Queues/User = 0.
- Keine Secrets in Reports, Logs oder Git.
- Keine Terraform-Apply-/Destroy-Operation.

---

## 9. Offene Produktdefekte

| ID | Befund | Status | Auswirkung |
|---|---|---|---|
| F-PRV-01 | Consumer-scoped Erase ist No-op (GSI2 projiziert `consumerId` nicht) | **CONFIRMED, not fixed** | Scope-Schutz unwirksam, fail-closed |
| GSI3-GAP-01/02 | CANCELLED/Budget-Einträge können Recovery-limit starren | **CONFIRMED local** | Recovery kann gültige Orders verpassen |
| GSI3-GAP-03 | Expired Claim bei Status PROCESSING/SHIPPED → `STALE`/gestrandet | **CONFIRMED local** | Order bleibt hängen |
| DLQ `maxReceiveCount=1` | nur ein Versuch, kein transienter Retry | **DESIGN/Review** | DLQ kann bei temporärem Fehler greifen |
| API-Idempotenz | API-Deduplizierung fehlt | **CONTRACT GAP** | Duplikate bei Client-Retry |
| SEC-06 | Approval nicht plan-/workspace-gebunden | **CONTRACT GAP** | Deployment-Freigabe separat |
| P00 | KMS/Secrets/Retention nicht implementiert | **NOT IMPLEMENTED/Scope offen** | Privacy/KMS/Retention |

Keine dieser Produktänderungen wurde in G3-EXT umgesetzt; Gate C erfordert
separate Freigabe.

---

## 10. Offene Releaseentscheidungen

1. **P00-Scope:** KMS/Secrets/Retention in RC4 oder formell auf RC5 verschieben.
2. **RC3-Bestandsdaten:** 404/keine Staff-Liste akzeptieren oder Migration.
3. **API-Idempotenz:** fehlende Dedupe dokumentieren oder Vertrag ergänzen.
4. **Processing/GSI3:** nur Infrastruktur oder produktiv aktivieren.
5. **DLQ-Policy:** `maxReceiveCount=1` beibehalten oder Retry-Strategie ändern.
6. **F-PRV-01:** Scope-Erase fixen vor Mehr-Consumer-Nutzung.
7. **GSI3-GAPs:** vor Aktivierung von `processing_recovery_enabled` beheben.
8. **SEC-06:** separat entscheiden, nicht in RC4-Order-Scope vermischen.
9. **Release-Version:** `v0.5.0-rc.4` vs `v0.6.0-rc.1`, `deployment_version` Default.
10. **Rollback/RIS-Pin:** RC3-Rollback und RIS-Handoff separat entscheiden.

---

## 11. G4-Readiness

**Nicht G4-ready.** Die lokale Testsuite und die generische Live-Suite sind
belastbar, aber die G4-Releaseentscheidung benötigt mindestens:

- P00-Scope-Entscheidung,
- RC3-Bestandsdaten-/Migrationsentscheidung,
- API-Idempotenz-Entscheidung,
- Produktentscheidung zu Processing/GSI3 und DLQ-Retry,
- F-PRV-01-Fix oder ausdrückliche Scope-Begrenzung,
- SEC-06-Entscheidung,
- freigegebenen und ausgeführten Live-Manifest-Test,
- Klärung des Main-Auto-Apply-Pipeline-Gates.

---

## 12. Commit- und Auditlog-Nachweise

Vorgesehen:

```text
Test-/Cleanup-Infrastruktur: e422330
G3-Doku:                     8736dc8
G3-EXT-Doku:                 (dieser Commit)
Dateien:                     docs/reports/MO-RC3-RC4-G3-EXT-ORCHESTRATION.md
                             docs/reports/MO-RC3-RC4-G3-EXT-LIVE-TEST-MANIFEST.md
                             docs/AI_AUDITLOG.md
```

Kein Push, kein Merge, keine AWS-/Terraform-Mutation.

---

## Appendix — Agenten-Auditnachweise

### Agent A — DLQ/Retry

Read-only; `sqs_handler`/SQS-/Worker-Konfiguration geprüft; 27 SQS-Tests,
17 Safety-Tests, Component-Pfad; DLQ-Live **NOT TESTED**; G3-Cleanup-Artefakt
ausdrücklich **kein** DLQ-Test; Plan DLQ-01/02 minimum, DLQ-03/04 optional;
keine Datei/AWS-Änderung.

### Agent B — GSI3/Recovery

Read-only; 340 Lambda + 55 Recovery-Tests PASS; GSI3 ACTIVE/0 Items;
GAP-01/02/03 lokal reproduziert; geplanter 10-Fixture-Test; keine
AWS-/Terraform-/Dateiänderung.

### Agent C — Privacy

Read-only; 340 Lambda + 36 Privacy-Tests PASS; Live durch fehlendes Secret
und Invoke-Recht blockiert; F-PRV-01 confirmed; Tier-A/B/C-Manifest;
keine Secret-/AWS-/Dateiänderung.

### Agent D — Compatibility/Release

Read-only; RC3-Objekte aus `086a8be` geprüft; RC4-Matrix und Releaseentscheidungen;
P00/SEC-06/Idempotenz/Processing/Builder/Rollback offen; keine Tests/AWS/
Terraform/Dateiänderung.

---

**STOP:** Keine neuen mutierenden AWS-Live-Tests ohne separate Freigabe.
