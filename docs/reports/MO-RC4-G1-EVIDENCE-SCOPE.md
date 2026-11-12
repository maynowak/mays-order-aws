# MO-RC4-G1-EVIDENCE-SCOPE

**Konsolidierung des RC4-Entwicklungsstands anhand vorhandener Nachweise**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `12939e57a2f1b54c5ab130eeac764d1c2910ffc1`
**Modus:** read-only Evidence-Discovery und Dokumentation; keine AWS-/Terraform-
Mutation, keine Produktänderung, keine neuen Tests, kein Push/Merge.

---

## 1. Executive Summary

RC4 ist **nicht ein einzelner, vollständig abgeschlossener Nachweis**, sondern
eine Sammlung unterschiedlich belastbarer Evidenzstände:

- **Lokaler Order-Kern:** 337 Lambda-Tests, 669 Installer-Tests, 128
  Builder-Tests, 16 lokale E2E-Harness-Tests = **1.150 PASS**.
- **Seed-Tools:** zusätzlich **28 PASS** (nicht in der 1.150er-Baseline).
- **Live-E2E:** **4 BLOCKED**; keine authentifizierte Live-Ausführung.
- **AWS-Testinfrastruktur:** RC4-Teststack wurde auf Code `00125ee` applied
  (State serial 8, 39 Ressourcen, `mo_version=0.2.0`, GSI3 ACTIVE); die
  funktionale Live-Verifikation blieb blockiert.
- **P00-Plan vs. Implementierung:** Der ursprüngliche P00-Plan (KMS,
  Secrets Manager, Retention, Cancel-Lifecycle) ist **überwiegend nicht
  implementiert**. Der implementierte RC4-Schwerpunkt liegt auf
  P02/P02A/P02C/P02E/P02F/P02G/P02H/P02I (Order Ownership, Worker,
  Processing, Recovery).
- **Dokumentation:** `PROJECT_STATUS`, README und
  `docs/phase2-async-order-ingest.md` sind gegenüber Code und späteren
  Reports veraltet.

**G1-Ergebnis:** Wiederverwendbar sind vor allem lokale Test-/Coverage-
Nachweise und die AWS-Infrastruktur-Snapshots. Für eine RC4-Gesamtfreigabe
fehlen weiterhin authentifizierte Live-E2E-, DLQ-, GSI3-/Recovery-,
Processing-Aktivierungs- und Testdaten-Cleanup-Nachweise sowie eine
verbindliche P00-Scope-Entscheidung.

---

## 2. Verwendete Quellen

### 2.1 Aktuelle Git-Identität

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `12939e57a2f1b54c5ab130eeac764d1c2910ffc1` |
| Working Tree | CLEAN |
| Letzter RC4-Bericht | `docs/reports/MO-RC4-TESTSUITE-CONSOLIDATION-13A.md` |
| Letzter Code-Commit | `0138e60` (Installer SEC-01…05) |
| Letzter Doku-Commit | `12939e5` |

### 2.2 Berichte / Nachweise

- `docs/reports/MO-RC4-P00-BASELINE.md`
- `docs/reports/MO-RC4-P00-MODULE-PLAN.md`
- `docs/reports/MO-RC4-P00-OPEN-QUESTIONS.md`
- `docs/reports/MO-RC4-P01-CONTRACT-INVENTORY.md`
- `docs/reports/MO-RC4-P02-ORDER-OWNERSHIP.md`
- `docs/reports/MO-RC4-P02A-*`, `P02C-*`, `P02E-*`, `P02F-*`,
  `P02G-*`, `P02H-*`, `P02I-*`
- `docs/reports/MO-BUILDER-UPGRADE-P2-01.md`
- `docs/reports/MO-RC4-AWS-TEST-UPGRADE-APPLY-07.md`
- `docs/reports/MO-RC4-AWS-TEST-FUNCTIONAL-VERIFY-08.md`
- `docs/reports/MO-RC4-TESTSUITE-HARDENING-10D.md`
- `docs/reports/MO-RC4-TESTSUITE-HARDENING-10E-A.md`
- `docs/reports/MO-RC4-SECURITY-DEFECT-CORRECTION-11A.md`
- `docs/reports/MO-RC4-TESTSUITE-CONSOLIDATION-13A.md`
- `docs/reports/MO-RC3-P06-RIS-E2E-EVIDENCE-VERIFICATION.md`
- `docs/release/RELEASE-GATES-v0.5.0-rc.3.md`
- `docs/INSTALLER-LIFECYCLE.md`, `api/endpoints.md`,
  `order-lifecycle/state-machine.md`
- `docs/phase1-order-message-status-model.md`,
  `docs/phase2-async-order-ingest.md`

---

## 3. A — Evidence-Discovery

### 3.1 Übersicht

| # | Evidence | Quelle | Datum / Commit | Umfang / Ergebnis | Bezug zum aktuellen Code | Gültigkeit |
|---|---|---|---|---|---|---|
| E-01 | P00 RC4-Baseline | `MO-RC4-P00-BASELINE.md` | 2026-11-01; Basis `086a8be` | Baseline, Architektur-Inventar; keine AWS-Operation | Ausgangspunkt RC4 | **HISTORISCH**, als Ausgangspunkt gültig |
| E-02 | P00 RC4-Plan | `MO-RC4-P00-MODULE-PLAN.md` | 2026-11-01 | 15 Pakete P-01…P-15, ~18,5 PT | teilweise umgesetzt, Scope offen | **PLANUNG**, nicht automatisch verbindlich |
| E-03 | P00 offene Fragen | `MO-RC4-P00-OPEN-QUESTIONS.md` | 2026-11-01 | 14 Entscheidungen, P0 blockierend | P00-Scope weiterhin ungeklärt | **OFFEN** |
| E-04 | P01 Vertragsinventar | `MO-RC4-P01-CONTRACT-INVENTORY.md` | 2026-11-01; `c40b695` | Ist-Verträge, fehlende subjectId/Retention/DLQ | Ausgangsbefunde; teilweise durch P02/P02I überholt | **HISTORISCH/teilweise überholt** |
| E-05 | P02 Order Ownership | `MO-RC4-P02-ORDER-OWNERSHIP.md` | 2026-11-01; `766f56e` | 93/93 Lambda; Ownership/GSI2/Privacy | Codebasis älter als HEAD; Kern weiter vorhanden | **LOKAL HISTORISCH**, nicht aktueller Lauf |
| E-06 | P02I Recovery | `MO-RC4-P02I-B2-AUTOMATIC-PROCESSING-RECOVERY.md` | 2026-11-01; `f5a3b03` | 321/321 Lambda; GSI3/Recovery | Kern im aktuellen Code | **LOKAL HISTORISCH**, nicht live |
| E-07 | Builder Upgrade P2 | `MO-BUILDER-UPGRADE-P2-01.md` | 2026-11-03; `f567669` | Builder 128 PASS; Upgrade-Manifest/Diff | aktueller Builder 128 PASS | **AKTUELL bestätigt** |
| E-08 | RC4 AWS Test-Apply | `MO-RC4-AWS-TEST-UPGRADE-APPLY-07.md` | 2026-11-11; `1e7b838`, Code `00125ee` | 2 create/7 update/0 delete/0 replace; State serial 8, 39 Ressourcen, `mo_version=0.2.0`, GSI3 ACTIVE | aktueller Stack; Installer-Delta seit `00125ee` betrifft nur lokale Sicherheitsmodule | **INFRA-SNAPSHOT gültig**, keine funktionale Live-Verifikation |
| E-09 | RC4 Functional Verify | `MO-RC4-AWS-TEST-FUNCTIONAL-VERIFY-08.md` | 2026-11-11; `ab62250` | unauth. GET 401 PASS; auth. Handler/SQS/Worker/GSI3 BLOCKED; DLQ NOT EXECUTED; 7 Alarme OK, Queue 0 | Teststack aktuell; keine Testidentität | **GÜLTIG als BLOCKED-Nachweis** |
| E-10 | RC4 Testsuite 10D | `MO-RC4-TESTSUITE-HARDENING-10D.md` | 2026-11-11; `cb14992` | Coverage: Lambda 90,15 %/82,22 %, Builder 91,22 %/84,93 %, Installer 73,43 %/63,85 % (10D-Scope), E2E-Harness 91,58 %/88,46 % | Code später nur Installer-Fixes | **MESSUNG historisch**, Scope beachten |
| E-11 | 10E-A Security Tests | `MO-RC4-TESTSUITE-HARDENING-10E-A.md` | 2026-11-11; `f7f3ffe` | 43/664 PASS; Approval/Workspace/Fail-Closed; 3 Mutationen | SEC-01…06-Befunde; durch 11A teilweise überholt | **HISTORISCH/SUPERSEDED** |
| E-12 | 11A Security Correction | `MO-RC4-SECURITY-DEFECT-CORRECTION-11A.md` | 2026-11-11; `b3bcc3c` | SEC-01…05 fixed; 669 Installer PASS; Coverage 74,08 %/64,04 % | aktueller Code | **AKTUELL** |
| E-13 | 13A Consolidation | `MO-RC4-TESTSUITE-CONSOLIDATION-13A.md` | 2026-11-12; `12939e5` | 1.150 PASS + 28 Seed; 4 Live BLOCKED; Traceability | aktueller HEAD | **AKTUELL** |
| E-14 | RC3 RIS-E2E | `MO-RC3-P06-RIS-E2E-EVIDENCE-VERIFICATION.md` | historisch (RC3) | RIS-MO-RC-01 7/7, Plan 169, Apply/No-Op/Destroy | separates Testkonto/Consumer | **HISTORISCH**, nicht RC4-Teststack |
| E-15 | RC3 Release Gates | `docs/release/RELEASE-GATES-v0.5.0-rc.3.md` | RC3 | 18 Gates; RC3 GO, Produktion BLOCKED | Baseline-Referenz | **HISTORISCH** |
| E-16 | Aktuelle Testausführung | lokal, 2026-11-12 | HEAD `12939e5` | 669/128/337/16 = 1.150 PASS; 28 Seed PASS; 4 Live BLOCKED | aktueller Code | **AKTUELL** |
| E-17 | P00-KMS/Secrets/Retention | P00 Plan + Code-Grep | 2026-11-12 | kein `kms`, kein SecretProvider, keine Retention/TTL | aktueller Code | **NICHT IMPLEMENTIERT** |

### 3.2 Evidence-Gültigkeit

- **CURRENT:** E-07, E-12, E-13, E-16.
- **INFRASTRUCTURE SNAPSHOT:** E-08, E-09 (State/AWS read-only, keine Live-Funktion).
- **HISTORISCH / nur Referenz:** E-01, E-04, E-05, E-06, E-10, E-11, E-14, E-15.
- **PLANUNG:** E-02, E-03.
- **NICHT IMPLEMENTIERT:** E-17.

Wichtig: E-08/E-09 sind **keine** Nachweise für eine erfolgreiche authentifizierte
Order-Verarbeitung. E-09 belegt ausdrücklich die BLOCKED-Situation.

---

## 4. B — P00-Scope vs. tatsächlicher RC4-Umfang

### 4.1 P00-Pakete

| P00-Paket | Ursprünglicher Inhalt | Status im aktuellen Code | Klassifikation |
|---|---|---|---|
| P-01 | SecretProvider (env/Secrets Manager) | kein `secret_provider.py`; `_require_privacy_auth` liest weiter Env | **NICHT IMPLEMENTIERT** |
| P-02 | AWS Secrets Manager | keine Ressource | **NICHT IMPLEMENTIERT** |
| P-03 | Secret-Rotation | nicht vorhanden | **NICHT IMPLEMENTIERT** |
| P-04 | KMS CMK | kein `aws_kms_key`/Alias | **NICHT IMPLEMENTIERT** |
| P-05 | DynamoDB SSE-KMS | kein SSE-Block mit CMK | **NICHT IMPLEMENTIERT** |
| P-06 | SQS SSE-KMS | kein KMS-Master-Key | **NICHT IMPLEMENTIERT** |
| P-07 | IAM KMS | keine KMS-Rechte | **NICHT IMPLEMENTIERT** |
| P-08 | Retention/TTL | kein `retentionUntil`/`ttl` | **NICHT IMPLEMENTIERT** |
| P-09 | Cancel-Retention | keine Retention-Folgen | **NICHT IMPLEMENTIERT** |
| P-10 | Installer KMS/Retention-Flags | keine entsprechenden Flags | **NICHT IMPLEMENTIERT** |
| P-11 | Builder KMS/Secret-Module | Katalog ohne KMS/Secret | **NICHT IMPLEMENTIERT** |
| P-12 | RIS-Kompatibilität | historisch belegt (RC3), aktueller RC4-Flow nicht live | **PARTIAL / HISTORISCH** |
| P-13 | Security-Tests | breite lokale Tests, aber nicht P00-spezifisch | **PARTIAL** |
| P-14 | RC4 Release-Gates | kein RC4-Dossier/Gate-Abschluss | **NICHT ABGESCHLOSSEN** |
| P-15 | Policy-Gate KMS/Secrets | Allowlist ohne KMS/Secrets | **NICHT IMPLEMENTIERT** |

### 4.2 Implementierter RC4-Order-Schwerpunkt

Die tatsächlich implementierten RC4-Order-Pakete sind nicht die P00-Pakete,
sondern:

- P02: Order Ownership / Privacy-Konsistenz
- P02A: Identity Resolution / Legacy-Kompatibilität
- P02C: SQS-/Worker-Sicherheit
- P02E: Handler-Routing/`orderType`
- P02F: Pending-Recovery
- P02G-A/B: Processing-Ergebnis/Lifecycle
- P02H-A: Owner-/Consumer-Autorisierung
- P02I-A/B2/C1/C2: Recovery-Safety, GSI3, Artefakt-/CI-Gates

**Bewertung:** Der P00-Plan und der implementierte Order-Schwerpunkt sind
nicht deckungsgleich. Eine ausdrückliche, dokumentierte Scope-Änderung
(z. B. „P00 KMS/Retention wird auf später verschoben“) wurde in den geprüften
Quellen nicht gefunden. Damit ist der RC4-Gesamtumfang **nicht eindeutig
verbindlich**.

### 4.3 Entscheidung erforderlich

Nicht eigenmächtig entscheiden:

1. Ist P00 (KMS/Secrets/Retention) Teil des RC4-Releaseumfangs?
2. Falls nein: formale Scope-Reduktion dokumentieren.
3. Falls ja: P-01…P-09/P-15 sind Release-Blocker; Implementierung ist nicht
   Teil von G1.
4. Release-Bezeichnung/Version (`v0.5.0-rc.4` vs. andere) bleibt offen.

---

## 5. C — RC4-Zielmatrix

| RC4-Ziel | Modulnachweis | Buildernachweis | Testsuite | AWS-Evidence | Offene Lücke | Priorität |
|---|---|---|---|---|---|---|
| Order-Erstellung mit JWT-Owner | P02/P02A Reports; `index.py`, `order_service.py` | indirekt (Modulvertrag) | Lambda 337; 10B Component | 08: auth. POST **BLOCKED** | Live POST/Cognito fehlt | **P0** |
| Eingabevalidierung/API-Vertrag | `validation.py`; `api/endpoints.md` | n/a | `test_validation`, `test_index` | 08: unauth. GET 401 PASS | Live-Statuscodes fehlen | **P2** |
| Persistenz/GSI2/Version | P02, `order_service.py`, DDB TF | indirekt | Service-/Component-Tests | 07: DDB/GSI3 Infra; 08 keine Daten | echte DDB-Condition/GSI2 | **P1** |
| Statusmodell/Übergänge | `state_machine.py`; P02H | n/a | State-/Service-/Component-Tests | 08 Infra only | Live-Übergang fehlt | **P1** |
| Handler-Routing/orderType | P02E; `order_handlers.py` | indirekt | Handler-/Processing-Tests | keine | produktiv nur `generic` | **P1** |
| SQS-Publish/Worker | P02C; `index.py`, `sqs_handler.py` | indirekt | 337 + 10B Component | 08 Queue 0; keine Live-Nachricht | echte SQS/Worker-Kette | **P0/P1** |
| Idempotenz/Duplikate | Worker-Condition; **API kein Key** | n/a | Duplicate/Conflict-Tests | keine | API-Replay-Vertrag | **P1** |
| DLQ/Retry | Terraform Redrive/DLQ; Worker batch failures | indirekt | Batch-/Fehlertests | 08 DLQ NOT EXECUTED | funktionale DLQ-Zustellung | **P0/P1** |
| Owner-/Consumer-Autorisierung | P02H; `identity.py` | n/a | 401/404/foreign-owner-Tests | 08 keine Auth-Identität | echte JWT-Claim-/API-Prüfung | **P1** |
| Privacy inspect/export/erase | P02; `order_service.py` | indirekt | Privacy-Tests | keine | Secret/KMS nicht provisioniert | **P0/P1 je Scope** |
| Processing-Claim/Result | P02G; Test-Handler | n/a | Processing-Lifecycle-Tests | keine | kein produktiver Processing-Handler | **P1** |
| GSI3/Recovery | P02F/P02I; `recovery.py` | indirekt | Recovery-Tests | 07 GSI3 ACTIVE; keine Daten | Live-Recovery/GSI3 | **P1** |
| RC3-Kompatibilität | P02A Legacy; RIS-Historie | RC3 Builder-Vertrag | Legacy-/API-Tests | RIS-MO-RC-01 historisch | aktueller RC3→RC4-Live-Flow | **P1** |
| P00 KMS/Secrets/Retention | **nicht implementiert** | nein | keine P00-spezifischen Tests | keine | Scope-/Implementierungsentscheidung | **P0/P1** |
| Live-E2E/Cleanup | E2E-Suite | n/a | 4 Live BLOCKED; 16 lokal PASS | 08 blocked | Testidentität + sichere Bereinigung | **P0** |
| Installer-Sicherheitsgates | 10A/11A; `installer/core/*` | n/a | 669 PASS | keine AWS | SEC-06 V2 separat | **P1 separat** |

---

## 6. D — Ergebnis

### 6.1 Konsolidierte RC4-Ziele

1. Authentifizierte Order-Erstellung und -Abruf.
2. Strikte Validierung und API-Fehlerverträge.
3. Owner-/Consumer-Isolation, 401/404 ohne Offenlegung.
4. DynamoDB-Persistenz mit Version/GSI2.
5. Statusübergänge und Conditional Updates.
6. SQS-Publish/Worker und Batch-Retry.
7. Idempotenz auf Worker-Ebene; API-Idempotenz noch offen.
8. DLQ/Redrive.
9. Processing-Claim/Result (Produktivaktivierung offen).
10. GSI3-/Recovery-Pfad.
11. RC3-Legacy-Kompatibilität.
12. P00-KMS/Secrets/Retention (Scope offen).
13. Sichere Live-Testidentität und Datenbereinigung.
14. Installer-/Upgrade-Sicherheitsgates (separater Scope).

### 6.2 Wiederverwendbare Evidence

- **Aktuell:** 11A-Installer-Korrekturen, 13A-Testinventur, lokale
  1.150 PASS + 28 Seed PASS, Coverage 11A/10D.
- **Infrastruktur:** Apply-07 (State/GSI3/Version), Functional-Verify-08
  (401 PASS, Blocked-Status, Infra/Alarme/Queue).
- **Historisch:** P02/P02I-Reports, RC3/RIS-E2E, RC3-Release-Gates;
  nur mit klarer Datums-/Commit-Abgrenzung verwenden.
- **Builder:** P2-Report und aktuelle 128 PASS.

### 6.3 Veraltete/widersprüchliche Nachweise

| Nachweis | Problem | Umgang |
|---|---|---|
| `MO-RC4-TESTSUITE-HARDENING-10E-A` | meldet SEC-01…06 als offen; durch 11A teilweise überholt | als historischen Befund kennzeichnen |
| `PROJECT_STATUS` | RC4 „keine Implementierung“, AWS Resources NONE | nicht als aktuellen Stand verwenden |
| `README.md` | Release `v0.5.0-rc.2` | Release Notes/RC3-Berichte getrennt prüfen |
| `docs/phase2-async-order-ingest.md` | kein DLQ/keine Idempotenz/Worker minimal | veraltet; aktueller Code P02C/P02G |
| 10D-Coverage | anderer Scope als 11A (drei Module nicht importiert) | 11A-Werte für aktuellen Stand verwenden |
| RC3/RIS-E2E | separates Konto/Consumer, nicht RC4-Teststack | nur historische Kompatibilitätsreferenz |

### 6.4 Tatsächlich offene Punkte

1. Authentifizierter Live-Order-E2E-Nachweis.
2. Live-Testidentität und sichere Testdatenbereinigung.
3. DLQ/Retry funktional.
4. GSI3/Recovery live.
5. Produktiver Processing-Handler.
6. API-Idempotenz-Vertrag.
7. P00-Scope KMS/Secrets/Retention.
8. RC3→RC4-Live-Kompatibilität.
9. Installer SEC-06/V2 (separat).
10. Doku-/Release-Version-Synchronisierung.

### 6.5 Verbindliche Voraussetzungen für G2

- P00-Scope-Entscheidung: KMS/Secrets/Retention verbindlich oder ausdrücklich
  aus RC4 entfernt.
- Bestätigung des RC4-Releaseumfangs und der Version.
- Freigabe eines Live-Testplans mit **vorab provisionierter Testidentität**.
- Geklärte, sichere Testdatenbereinigung; keine direkte DynamoDB-Löschung als
  Workaround.
- Akzeptanz der Evidence-Grenzen: lokale Mocks sind kein Live-Nachweis.
- Festlegung, ob DLQ/Processing/GSI3 live geprüft werden müssen.

### 6.6 Verbindliche Voraussetzungen für G3

- G2-Entscheidungen dokumentiert und freigegeben.
- Autorisierte Testidentität und API-Endpunkt.
- Getrennter, nicht-produktiver Teststack.
- Explizite Freigabe für jede AWS-Mutation.
- Cleanup-/Ownership-Nachweis vor dem Lauf.
- Testmatrix für Order, Worker, SQS/DLQ, GSI3, Auth und RC3.
- Keine Produkt-/Terraform-Änderung ohne separaten Auftrag.

### 6.7 Offene Entscheidungen (nicht eigenmächtig treffen)

- P00-Scope und Releasebezeichnung.
- API-Idempotenz-Semantik.
- Produktiver Processing-Handler/`orderType`.
- Live-Testidentität und Cleanup-Verfahren.
- DLQ-/Retry-Testfreigabe.
- SEC-06 ApprovalEvidence V2 (separater Installer-Scope).
- Aufbewahrung/Version der Evidence.

---

## 7. Git-Abschluss

Vorgesehen:

```text
Commit: docs(rc4): consolidate g1 evidence and scope
Dateien: docs/reports/MO-RC4-G1-EVIDENCE-SCOPE.md
         docs/AI_AUDITLOG.md
```

Kein Push, kein Merge. Commit-SHA und CLEAN-Status werden nach dem Commit
verifiziert.
