# MO-RC4-B2-TESTSUITE-INTEGRATION-01

**Integration der RC4-Privacy-Testfälle in die bestehende E2E-Suite**

**Datum:** 2026-11-13
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor Integration:** `264635e9542a29a4dab404d1ed419a14f7d2170b`
**Modus:** lokale Testentwicklung und lokale Tests; **keine AWS-Mutation**,
keine Privacy-Live-Invocation, keine IAM-/Secret-Änderung, kein Terraform,
kein Push/Merge, keine RC4-Release-Freigabe.

```text
B2 TESTSUITE INTEGRATED — READY FOR LIVE CONFIGURATION
```

Die Privacy-Livetests sind integriert, standardmäßig deaktiviert und ohne
vollständige Gates ohne AWS-Verbindung. Die Suite ist lokal verifiziert. Die
AWS-Live-Ausführung bleibt **CONFIGURATION REQUIRED**; RC4 insgesamt ist
**noch nicht releasefähig**.

---

## 1. Baseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD vor Integration | `264635e9542a29a4dab404d1ed419a14f7d2170b` |
| Working Tree vor Integration | CLEAN |
| AWS | nicht kontaktiert, keine Mutation |
| Live-Tests | nicht ausgeführt |

Gelesen: `docs/AI_AUDITLOG.md`, `tests/README.md`,
`tests/e2e_harness.py`, `tests/test_e2e_harness.py`,
`tests/test_e2e_async_order.py`, `scripts/tests/setup_test_user.py`,
G3-Live-Manifest und B2-PREP-01.

---

## 2. Wiederverwendete Komponenten

| Komponente | Verwendung |
|---|---|
| `E2ERun` | run-scoped Run-ID, synthetische Order-Marker, Cleanup-Ledger |
| `ApiClient` | A/B-API-Orders, Owner-GET für ANONYMIZE-Prüfung |
| `Diagnostic` | Privacy-Diagnostik über `PrivacyInvokeClient.diagnostic` |
| `LiveCleanupBackend` | normale A-/B-Orders, subject-/owner-verifiziert |
| `ExactKeyCleanupBackend` | **neu, minimal**: exakte Keys für ANONYMIZE und Consumer-Fixtures |
| `CleanupOwnershipError` | Fremd-/Marker-Schutz beim exakten Cleanup |
| `redact` | Secret-Redaktion in Diagnostik |
| `resolve_auth` | **nicht** für Privacy-Invoke verwendet: HTTP-Token-Gate passt nicht zum internen Lambda-Invoke und zu zwei Identitäten |
| `scripts/tests/setup_test_user.py` | nicht automatisch ausgeführt; Testidentitäten bleiben Operator-Schritt |

Es wurde keine zweite allgemeine Harness-Implementierung erstellt. Die
Privacy-spezifischen Bausteine liegen in `tests/privacy_e2e_harness.py`.

---

## 3. Neue Testdateien

| Datei | Zweck |
|---|---|
| `tests/privacy_e2e_harness.py` | Gates, `PrivacyLiveConfig`, Lambda-Invoke-Adapter, Privacy-Kontext, JWT-Subject, `boto3_invoker` (lazy) |
| `tests/test_privacy_e2e_harness.py` | 15 lokale Tests: Gates, Redaktion, Invoke-Payload, exakte Cleanup-Sicherheit |
| `tests/test_privacy_e2e.py` | 15 opt-in Live-Tests für G3X-PRV-X01…X13; standardmäßig BLOCKED |
| `tests/e2e_harness.py` | additive `ExactKeyCleanupBackend`-Klasse und Secret-Key-Erweiterung |
| `tests/README.md` | Privacy-Gates, Umgebungsvariablen, Cleanup und X13-Grenze |

---

## 4. Live-Gates

`resolve_privacy_config()` prüft ohne AWS-Zugriff:

```text
MO_PRIVACY_LIVE=1
MO_E2E_LIVE_CLEANUP=1
PRIVACY_E2E_INVOKER_APPROVED=1
AWS_PROFILE=mayaws
AWS_REGION=eu-central-1
PRIVACY_E2E_ACCOUNT_ID=240571105849
PRIVACY_E2E_TABLE=mays-orders-rc4-test
PRIVACY_E2E_HANDLER=mays-orders-rc4-test-handler
PRIVACY_E2E_CODE_SHA256=FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=
PRIVACY_E2E_PROJECT=mays-orders-rc4-test
PRIVACY_E2E_CONSUMER_ID=<test consumer>
PRIVACY_E2E_QUEUE_URL=<main queue>
PRIVACY_E2E_DLQ_URL=<dlq>
API_BASE_URL=<test api>
PRIVACY_E2E_SUBJECT_A=<sub A>
PRIVACY_E2E_SUBJECT_B=<sub B>
PRIVACY_E2E_ACCESS_TOKEN_A=<token A>
PRIVACY_E2E_ACCESS_TOKEN_B=<token B>
PRIVACY_E2E_INTERNAL_TOKEN=<handler privacy secret>
```

Bei fehlendem Gate:

- `PrivacyLiveE2E.setUpClass` ruft `unittest.SkipTest` auf.
- Kein `boto3`-Import, keine AWS-Verbindung, keine Mutation.
- Der Blocked-Reason nennt nur fehlende Variablennamen, niemals Werte.

Zusätzlich prüft der Live-Preflight nach Freigabe:

- STS Account und Region,
- Lambda `Active`/`Successful` und CodeSha256,
- Tabelle ACTIVE/0 und Queue/DLQ 0/0,
- JWT-`sub` von Token A/B gegen die konfigurierten Subjects.

---

## 5. Integrierte Testfälle

| ID | Test | Integration |
|---|---|---|
| X01 | Inspect Subject A | eigene 2 Orders; keine PII |
| X01-EMPTY | Inspect unbekannt | 0 Referenzen |
| X01-CONSUMER | Inspect mit Consumer-Scope | fremder Consumer/legacy ausgeschlossen |
| X02 | falsches Projekt | 400 `VALIDATION_ERROR` |
| X03 | falscher interner Token | 400 |
| X04 | `authorized=false` | 400 |
| X05 | Export A | 2 Orders, keine internen Felder |
| X06 | Export B | nur B, A fehlt |
| X07 | Erase PREVIEW A | `PREVIEW`, keine Mutation |
| X08 | Erase EXECUTE ohne Policy | `BLOCKED`, keine Mutation |
| X09 | Erase B | 1 gelöscht; Wiederholung 0 |
| X10 | RETAIN A | `PARTIALLY_COMPLETED`, 2 retained, keine Mutation |
| X11 | ANONYMIZE eine Order | eigener One-Order-Subject; 1 anonymisiert, `subjectId` entfernt |
| X12 | Consumer-Scope-Erase | **1 eigener Consumer gelöscht; fremder Consumer unberührt** |
| X13 | fehlendes Secret | **BLOCKED/SKIP** in secret-fähigem Lauf; lokaler Test deckt fail-closed Branch |

`X11` nutzt einen dedizierten One-Order-Subject, weil `erase_subject` immer
subjektweit arbeitet. `X12` nutzt einen separaten Scope-Subject mit einem
eigenen und einem fremden Consumer-Fixture, damit exakt „1 gelöscht, fremd
unberührt“ geprüft wird.

`X13` ist nicht in einem Lauf reproduzierbar, in dem das Secret bereits
konfiguriert ist; dafür wäre eine zweite Lambda-Konfigurationsänderung nötig.
Der Live-Test bleibt explizit blockiert; `test_privacy_requires_internal_secret`
in der Lambda-Suite deckt den Code-Branch ab.

---

## 6. Cleanup-Semantik

| Fixture | Cleanup |
|---|---|
| A1/A2/B1 (API) | `LiveCleanupBackend` mit Subject A/B und exaktem `ord_*`/`#ORDER`-Key |
| ERASE-Order | bereits durch `privacy/erase` entfernt; Cleanup no-op |
| RETAIN/PREVIEW-Order | unverändert; Owner-Cleanup |
| ANONYMIZE-Order | `ExactKeyCleanupBackend`; `subjectId` fehlt, Marker in `items[].sku` |
| fremder Consumer | exakter Key; Markerprüfung; nie über Subject-Cleanup |
| fremde Daten | `CleanupOwnershipError` bei Run-/Marker-Mismatch |

Es gibt keine `PurgeQueue`-Operation, keinen Tabellenscan und keine
Massenlöschung. Cleanup-Fehler werden nicht unterdrückt.

---

## 7. Lokale Verifikation

### Gesamtergebnis

```text
Installer:            669 PASS
Builder:              128 PASS
Lambda:               345 PASS
E2E lokal:             31 PASS   (16 bestehende Harness + 15 neue Privacy)
Gesamt:             1.173 PASS
Live:                   4 bestehende Order-Tests BLOCKED/SKIP
Privacy live:           1 Klasse BLOCKED/SKIP (15 Tests nicht ausgeführt)
```

### Ausgeführte Befehle

```bash
cd /tmp/opencode/rc4-upgrade-plan
python3 -m unittest discover -s tests -v
# Ran 35 tests, OK (skipped=5)

python3 -m unittest tests.test_e2e_harness tests.test_privacy_e2e_harness -v
# Ran 31 tests, OK

python3 -m unittest discover -s installer/tests
# Ran 669 tests, OK

python3 -m unittest discover -s module_builder/tests
# Ran 128 tests, OK

cd lambda
PYTHONPATH=src python3 -m unittest discover -s tests
# Ran 345 tests, OK
```

### Erfüllte Prüfpunkte

| Prüfpunkt | Ergebnis |
|---|---|
| Ohne Freigabe keine AWS-Verbindung | **PASS** — Gate vor boto3; Live-Klasse skipped |
| Ohne Secret kein Privacy-Livetest | **PASS** — `PRIVACY_E2E_INTERNAL_TOKEN` erforderlich |
| Ohne Invoker kein Privacy-Livetest | **PASS** — `PRIVACY_E2E_INVOKER_APPROVED=1` erforderlich |
| Ohne Cleanup-Freigabe keine Mutation | **PASS** — `MO_E2E_LIVE_CLEANUP=1` erforderlich |
| Fremde Fixtures nicht entfernt | **PASS** — Marker-/Run-Guard, lokale Tests |
| ANONYMIZE-Cleanup exakt | **PASS** — `ExactKeyCleanupBackend` |
| Diagnostik ohne Secrets | **PASS** — `redact`, `PrivacyResponse.__repr__` nur Keys |
| Bestehende Order-E2E-Tests unverändert | **PASS** — 16 Harness-Tests, 4 Live-Tests unverändert |

Es wurde **keine** AWS-Verbindung und keine Live-Invocation ausgeführt.

---

## 8. Verbleibende AWS-Voraussetzungen

Vor einer späteren B2-Live-Ausführung:

1. `PRIVACY_INTERNAL_SECRET` in der Handler-Env (zeitlich begrenzt oder
   P00-Produktivpfad).
2. Dediziertes least-privilege Test-Invoke-Recht auf genau den Handler.
3. Keine `AdministratorAccess`-Identität als Test-Invoker.
4. Zwei vorab bereitgestellte Testidentitäten A/B mit gültigen Tokens/Subjects.
5. Bestätigter Consumer-Scope (`PRIVACY_E2E_CONSUMER_ID`).
6. Explizite **B2-Live-Freigabe** und **Cleanup-Freigabe**.
7. Leerer Ausgangszustand: Tabelle/GSI3/Queues 0.
8. Separate Testbenutzer-Löschung durch den Operator (Suite legt keine User an
   und löscht keine User).

Die Tests selbst erzeugen keine IAM-Rollen, Secrets oder Lambda-Konfiguration.

---

## 9. RC4-Release-Matrix

| Bereich | Status | Evidenz / Grenze |
|---|---|---|
| G3-FIX | **PASS** | Lokal 345 Lambda, deployed `FYTu…`, F-PRV/GSI3-Fixes im ZIP |
| G3-LIVE-B1 | **PASS (reconciled)** | DLQ-01/02, GSI3-Sends/Skips, GAP-01/02/03; Candidate-Mismatch in CLOSE-01 als Manifestfehler geschlossen |
| Owner-Isolation | **VERIFIED** | B1-IDENTITY-01: A 201/200, B 404/404, Liste/Status/Version unverändert |
| Privacy B2 | **CONFIGURATION REQUIRED** | Suite integriert; Live ohne Secret/Invoker nicht ausführbar |
| RC3/RC4-Kompatibilität | **PASS (begrenzt)** | G3-B1 RC3-Body/PATCH/Legacy-404; Bestandsmigration offen |
| DLQ / Retry | **PASS** | G3X-DLQ-01/02 live; maxReceiveCount=1; kein DDB-Write |
| GSI3 / Recovery | **PASS** | B1 10-Fixture-Recovery, GAP-01/02, GAP-03; Manifest korrigiert |
| SEC-06 | **CONTRACT GAP / NEEDS DECISION** | Approval-/Plan-Bindung nicht implementiert; separater Installer-Scope |
| Idempotency-Key | **NOT IMPLEMENTED** | API-Deduplizierung fehlt; Worker-Idempotenz nur teilweise |
| Legacy-Order-Migration | **OPEN** | RC3-Bestand ohne `subjectId` → 404; keine Migration |
| Produktive Handler-Registry | **PARTIAL** | Nur `generic` produktiv; Processing/GSI3 nicht aktiviert |
| P00 KMS/Secrets/Retention | **IMPLEMENTATION GAP** | Kein CMK, kein Secret-Provider, kein TTL/Retention; Scope offen |
| Terraform-Artefakt-Drift | **OPEN** | Read-only Plan: 0 add / 2 change (`source_code_hash`); kein Apply |
| RIS-Pin / Release-Version | **OPEN / PARTIAL** | RIS-Kompatibilität historisch; Release-Label `v0.5.0-rc.4` vs. `v0.6.0-rc.1` offen |
| CI/CD-Release-Gates | **BLOCKED / OPEN** | `directAWSGit` Auto-Apply-Risiko; kein RC4-Gate-Abschluss |
| **RC4-Gesamtfreigabe** | **NOT READY** | B2-Live, P00, SEC-06, Idempotenz, Migration, Drift und Release-Gates offen |

Es wurden keine bereits bestandenen Live-Tests wiederholt und keine offenen
Punkte ohne Nachweis als PASS markiert.

---

## 10. Verbleibende Risiken

- B2-Live ist ohne Secret/Invoker weiterhin nicht ausführbar.
- Ein Secret in der Lambda-Env ist für `lambda:Get*`-Prinzipale lesbar; ein
  dauerhafter Env-Ansatz ist kein Produktivmodell.
- PITR (35 Tage) und fehlende Retention/TTL bleiben Privacy-Risiken.
- Consumer-Scope ist optional; ohne Scope ist das Verhalten deployment-weit.
- Der `erase`-Delete-Condition enthält `consumerId` nicht; das ist bei
  unveränderlichem Consumer akzeptabel, aber ein TOCTOU-Restrisiko.
- Kein dauerhaftes Erasure-Ledger.
- `X13` ist live nur in einer secret-absenten Konfiguration reproduzierbar.
- RC4-Release bleibt durch P00, SEC-06, Idempotenz, Migration, Drift und
  CI/CD-Gates blockiert.

---

## 11. Auditlog / Commit

Der Auditlog-Eintrag wird nach dem Commit ergänzt. Es wurden ausschließlich
Test-/Doku-Dateien geändert; keine AWS-/Produkt-/Terraform-Änderung.

---

## 12. Commit-SHA und Working-Tree-Status

| Feld | Wert |
|---|---|
| Test-Integrations-Commit | `59c275db4a3ca6bde0e225bd4e21061c1654b79d` |
| Test-Nachtrag (Diagnostic) | `f0f96b3ff046d06df2fc40a125273063d93dbb3e` |
| Dokumentations-Commit | `f5f6392781e7cbb8eea9713daf1a131d95da5f60` |
| Working Tree nach Commit | CLEAN |

**STOP — keine automatische AWS-Live-Ausführung, keine Secret-/IAM-Änderung,
keine RC4-Release-Freigabe.**
