# MO-RC4-TESTSUITE-HARDENING-10D

**Statement- und Branch-Coverage der lokalen RC4-Testsuite**

**Datum:** 2026-11-11
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `5623aee25a87e42f302fb9f58733587d7b8d0d15`
**Modus:** ausschließlich lokale Messung; keine AWS-/Cognito-/Live-HTTP-Aufrufe,
keine Terraform-Mutation, keine Produktcodeänderung, kein Push/Merge.

```text
MO-RC4-TESTSUITE-HARDENING-10D — VERIFIED
```

---

## 1. Ausgangsbaseline und Git-Identität

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `5623aee25a87e42f302fb9f58733587d7b8d0d15` |
| 10A | `e703f96` — VERIFIED |
| 10B | `7922bae` — VERIFIED |
| 10C | `5623aee` — VERIFIED |
| Working Tree vor Messung | CLEAN |
| Lokale Regression | Installer 621, Builder 128, Lambda 337, E2E-Harness 16 = **1.102 PASS** |
| Live-E2E | 4 BLOCKED, nicht Teil der lokalen Regression |

---

## 2. Coverage-Werkzeug und Messkonfiguration

`coverage.py` war nicht lokal installiert. Für die Messung wurde die gepinnte
Version **7.4.4** isoliert nach `/tmp/opencode/mo10d-cov` installiert. Es wurden
keine Repo-Dateien, keine `requirements.txt`, keine System-Python-Pakete und
keine Coverage-Konfiguration verändert.

```bash
python3 -m pip install --target /tmp/opencode/mo10d-cov coverage==7.4.4
```

Verwendete Einstellungen:

- Branch Coverage: `--branch`
- Kein `.coveragerc`; Messumfang explizit über `--source`
- Testdateien ausgeschlossen (`--omit='*/tests/*'` bei Installer/Builder)
- Daten- und JSON-Artefakte ausschließlich unter
  `/tmp/opencode/mo10d-coverage/` — **nicht im Repository**
- Coverage-Version: `7.4.4`

### Messkommandos

```bash
# Lambda
cd lambda
COVERAGE_FILE=/tmp/opencode/mo10d-coverage/lambda.coverage \
PYTHONPATH=/tmp/opencode/mo10d-cov:src \
python3 -m coverage run --branch --source=src \
  -m unittest discover -s tests

# Installer inkl. Policy-Gate-Skript
COVERAGE_FILE=/tmp/opencode/mo10d-coverage/installer.coverage \
PYTHONPATH=/tmp/opencode/mo10d-cov \
python3 -m coverage run --branch \
  --source=installer,terraform/policy \
  --omit='installer/tests/*' \
  -m unittest discover -s installer/tests

# Module Builder
COVERAGE_FILE=/tmp/opencode/mo10d-coverage/builder.coverage \
PYTHONPATH=/tmp/opencode/mo10d-cov \
python3 -m coverage run --branch \
  --source=module_builder --omit='module_builder/tests/*' \
  -m unittest discover -s module_builder/tests

# E2E-Harness separat, nicht mit Produktcode vermischt
COVERAGE_FILE=/tmp/opencode/mo10d-coverage/e2e-harness.coverage \
PYTHONPATH=/tmp/opencode/mo10d-cov \
python3 -m coverage run --branch --source=tests.e2e_harness \
  -m unittest discover -s tests -p 'test_e2e_harness.py'
```

Die Auswertung erfolgte aus `coverage json`; die kombinierte
„Cover“-Zahl von `coverage report` ist **nicht** die Statement- oder
Branch-Quote. Die Tabellen unten weisen beide getrennt aus.

---

## 3. Ergebnis je Komponente

| Komponente | Statements | Statement-Coverage | Branches | Branch-Coverage | Coverage.py kombiniert |
|---|---:|---:|---:|---:|---:|
| Lambda | 1.418 / 1.573 | **90,15 %** | 481 / 585 | **82,22 %** | 88,00 % |
| Installer inkl. Policy-Gate | 4.008 / 5.458 | **73,43 %** | 1.369 / 2.144 | **63,85 %** | 70,73 % |
| Module Builder | 987 / 1.082 | **91,22 %** | 389 / 458 | **84,93 %** | 89,35 % |
| E2E-Harness (separat) | 174 / 190 | **91,58 %** | 46 / 52 | **88,46 %** | 90,91 % |

Die E2E-Harness-Zahl ist **keine** Produktcode-Coverage und geht nicht in die
Lambda-/Installer-/Builder-Werte ein.

### Lambda-Dateien

| Datei | Statement | Branch | Kombiniert |
|---|---:|---:|---:|
| `src/index.py` | 135/164 = 82,3 % | 31/44 = 70,5 % | 79,8 % |
| `src/order_service.py` | 321/362 = 88,7 % | 128/167 = 76,6 % | 84,9 % |
| `src/sqs_handler.py` | 290/327 = 88,7 % | 90/115 = 78,3 % | 86,0 % |
| `src/identity.py` | 171/175 = 97,7 % | 72/77 = 93,5 % | 96,4 % |
| `src/recovery.py` | 161/195 = 82,6 % | 49/66 = 74,2 % | 80,5 % |
| `src/processing_result.py` | 107/113 = 94,7 % | 55/56 = 98,2 % | 95,9 % |
| `src/validation.py` | 96/99 = 97,0 % | 45/48 = 93,8 % | 95,9 % |
| `src/state_machine.py` | 7/7 = 100 % | 2/2 = 100 % | 100 % |
| `src/order_handlers.py` | 43/43 = 100 % | 6/6 = 100 % | 100 % |

### Installer-Dateien mit Sicherheitsbezug

| Datei | Statement | Branch | Kombiniert |
|---|---:|---:|---:|
| `installer/cli/main.py` | 484/1.080 = 44,8 % | 118/350 = 33,7 % | 42,1 % |
| `installer/core/approval.py` | **kein Datensatz** | **kein Datensatz** | **nicht importiert** |
| `installer/core/workspace.py` | **kein Datensatz** | **kein Datensatz** | **nicht importiert** |
| `installer/core/plan_integrity.py` | **kein Datensatz** | **kein Datensatz** | **nicht importiert** |
| `installer/core/fail_closed.py` | **kein Datensatz** | **kein Datensatz** | **nicht importiert** |
| `installer/core/subprocess_safety.py` | **kein Datensatz** | **kein Datensatz** | **nicht importiert** |
| `installer/terraform/plan_analysis.py` | 61/136 = 44,9 % | 14/51 = 27,5 % | 40,1 % |
| `installer/terraform/runner.py` | 229/315 = 72,7 % | 78/125 = 62,4 % | 69,8 % |
| `installer/run/manager.py` | 66/162 = 40,7 % | 19/50 = 38,0 % | 40,1 % |
| `installer/core/remote_state_lifecycle.py` | 55/98 = 56,1 % | 11/44 = 25,0 % | 46,5 % |
| `installer/core/backup_gate.py` | 155/174 = 89,1 % | 58/69 = 84,1 % | 87,7 % |
| `installer/core/order_backup.py` | 367/393 = 93,4 % | 113/138 = 81,9 % | 90,4 % |
| `installer/core/cleanup_contract.py` | 21/21 = 100 % | 6/6 = 100 % | 100 % |
| `installer/core/upgrade_safety.py` | 188/198 = 94,9 % | 51/60 = 85,0 % | 92,6 % |
| `terraform/policy/validate-plan.py` | 192/261 = 73,6 % | 130/183 = 71,0 % | 73,0 % |

**Wichtig:** `approval.py`, `workspace.py`, `plan_integrity.py`,
`fail_closed.py`, `subprocess_safety.py`, `atomic_ops.py`, `lock_manager.py`,
`logging_hardening.py`, `recovery.py`, `command_service.py`,
`command_result.py` und `cli/gui.py` wurden von der Testsuite nicht importiert.
Coverage.py liefert für diese Dateien deshalb keinen Datensatz; sie sind
**effektiv ungetestet**, nicht „0 von 0“.

### Builder-Dateien

| Datei | Statement | Branch | Kombiniert |
|---|---:|---:|---:|
| `module_builder/validation.py` | 8/20 = 40,0 % | 0/8 = 0,0 % | 28,6 % |
| `module_builder/__main__.py` | 0/4 = 0,0 % | 0/2 = 0,0 % | 0,0 % |
| `module_builder/cli.py` | 146/177 = 82,5 % | 47/60 = 78,3 % | 81,4 % |
| `module_builder/upgrade.py` | 352/373 = 94,4 % | 129/152 = 84,9 % | 91,6 % |
| `module_builder/builder.py` | 387/407 = 95,1 % | 178/198 = 89,9 % | 93,4 % |
| `module_builder/catalog.py` | 75/82 = 91,5 % | 33/36 = 91,7 % | 91,5 % |
| `module_builder/spec.py` | 18/18 = 100 % | 2/2 = 100 % | 100 % |

### E2E-Harness

`tests/e2e_harness.py`: 174/190 Statements = 91,58 %,
46/52 Branches = 88,46 %, kombiniert 90,91 %.

Die fehlenden Harness-Zeilen betreffen insbesondere den realen
`Urllib3Transport`-Pfad und einzelne Fehler-/Redaktionszweige. Der reale
Transport wurde absichtlich nicht ausgeführt; die lokale Validierung verwendet
`FakeTransport`.

---

## 4. Nicht abgedeckte Dateien und Funktionen

### Lambda

- `src/index.py`: `_send_to_sqs`-Fehlerpfad, interne Privacy-/Recovery-Aktionen,
  Teile von `_handle_internal`, `route_key`, Base64-/Body-Fehlerpfade.
- `src/order_service.py`: Privacy-Pfade `inspect_subject`, `export_subject`,
  `erase_subject`, Teile von `_require_privacy_auth`, Listen-Paginierung und
  einzelne Validierungs-/Recovery-Zweige.
- `src/sqs_handler.py`: technische Processing-Fehler, Claim-Klassifikation,
  `_release_claim`, `_to_dynamodb`-Randfälle, einzelne Batch-Fehlerpfade.
- `src/recovery.py`: große Teile von `run_recovery` und
  `run_processing_recovery`, Parsing-/Grenzfälle.
- `src/identity.py`: interner Identitätskontext und einzelne Validierungszweige.

### Installer

Nicht importiert und damit ohne Coverage-Datensatz:

- `installer/core/approval.py`
- `installer/core/workspace.py`
- `installer/core/plan_integrity.py`
- `installer/core/fail_closed.py`
- `installer/core/subprocess_safety.py`
- `installer/core/atomic_ops.py`
- `installer/core/lock_manager.py`
- `installer/core/logging_hardening.py`
- `installer/core/recovery.py`
- `installer/core/command_service.py`
- `installer/core/command_result.py`
- `installer/cli/gui.py`

Teilweise abgedeckt, aber mit großen Lücken:

- `installer/cli/main.py`: `_cmd_plan` (209 fehlende Zeilen),
  `_cmd_destroy` (88), `_cmd_deploy` (85), `_cmd_backup` (41),
  `_cmd_state` (40), `_cmd_identity` (33).
- `installer/terraform/runner.py`: `verify_plan_integrity`, `apply`,
  `_run`, `_ensure_workspace`-Randpfade.
- `installer/run/manager.py`: Run-Persistenz, Plan-Speicherung und
  Cleanup alter Runs.
- `installer/terraform/plan_analysis.py`: große Teile der
  Plan-Sicherheitsanalyse.
- `installer/core/remote_state_lifecycle.py`: Remote-State-/Lifecycle-Pfade.
- `terraform/policy/validate-plan.py`: mehrere Policy- und Fehlerzweige.

### Builder

- `module_builder/validation.py`: `validate_generated_project` ist nahezu
  vollständig ungetestet; der `--validate`-Pfad hat 0 % Branch-Coverage.
- `module_builder/__main__.py`: Einstiegspunkt nicht ausgeführt.
- `module_builder/cli.py`: Upgrade-/Fehlerpfade.
- `module_builder/builder.py` und `upgrade.py`: einzelne Fehler-,
  Report- und Dateisystem-Randpfade.

---

## 5. Qualitätsanalyse nach Sicherheitsbereichen

| Bereich | Status | Begründung |
|---|---|---|
| Authentifizierung / Owner-Isolation | **PARTIALLY VERIFIED** | Identity 97,7 % Statement, Order-Service 88,7 %; Privacy-Pfade und Live-Auth fehlen |
| Approval-/Destroy-Schutz | **PARTIALLY VERIFIED** | 10A testet Denial/`--yes`, aber `approval.py` ist nicht importiert; Deploy/Destroy-Gates in `main.py` größtenteils nicht ausgeführt |
| Conditional Writes / Versionskonflikte | **LOCAL VERIFIED** | Lambda- und 10B-Komponententests decken Bedingungen, Konflikte und Versionierung ab |
| Worker-Idempotenz | **LOCAL VERIFIED** | 10B-Tests für Doppelzustellung, Versionsstabilität und Conditional Conflict |
| API-Fehlerbehandlung | **PARTIALLY VERIFIED** | `index.py` 82,3 %; SQS-Fehler-, interne und Recovery-Zweige ungetestet |
| SQS-Retry / DLQ | **LIVE BLOCKED** | Batch-Retry lokal getestet; echte SQS-/DLQ-Zustellung nicht ausgeführt |
| DynamoDB-GSI3 | **LIVE BLOCKED** | Infrastruktur read-only verifiziert; keine Live-Abfrage/Processing unter AWS |
| Backup-/Restore-Sicherheit | **PARTIALLY VERIFIED** | Backup-Gate 89,1 %, Order-Backup 93,4 %; Restore/Live-AWS nicht ausgeführt |
| Policy Gate | **PARTIALLY VERIFIED** | Policy-Skript 73,6 % Statement/71,0 % Branch; Fehlerpfade offen |

**Hohe Coverage ist kein Nachweis für AWS-Integration.** Die lokale Suite
verwendet Fakes und Mocks; echte Cognito-, API-Gateway-, SQS-, DynamoDB- und
Terraform-Interaktionen bleiben Live-Blocks.

---

## 6. Priorisierter Test-Gap-Report

| Priorität | Komponente | Fehlender Pfad | Risiko | Empfohlener Test |
|---|---|---|---|---|
| **P0** | `installer/core/approval.py` | gesamte Datei nicht importiert | Approval-/`--yes`-Sicherheit nur indirekt geprüft | Direkte Unit-Tests für alle `NON_BYPASABLE_CHECKS` |
| **P0** | `installer/core/workspace.py` | gesamte Datei nicht importiert | Pfad-/Workspace-Isolation ungetestet | Path-Traversal- und Boundary-Tests |
| **P0** | `installer/core/plan_integrity.py` | gesamte Datei nicht importiert | Plan-Integritätsprüfung ohne direkte Abdeckung | Hash-/Manifest-/Tamper-Tests |
| **P0** | `installer/cli/main.py` | `_cmd_plan`, Deploy/Destroy-Gates, Backup/State | reale CLI-Sicherheitsgates nur gemockt | Tests mit gepatchten Runner-Grenzen, echte Gate-Methoden |
| **P0** | `installer/terraform/plan_analysis.py` | Sicherheitsanalyse-Zweige | falsche Planfreigabe möglich | Plan-JSON-Fixtures für Destroy/Replace/Grenzen |
| **P1** | `lambda/src/index.py` | SQS-Sendefehler, interne Recovery/Privacy-Routen | Delivery-Fehlerpfad und interne Auth nicht lokal verifiziert | Fehler-/Privacy-Routentests mit Fake-SQS |
| **P1** | `lambda/src/order_service.py` | Inspect/Export/Erase, Privacy-Auth | Owner-/Privacy-Isolation unvollständig | Privacy-Scope-, Auth- und Löschtests |
| **P1** | `lambda/src/sqs_handler.py` | Processing-Claim-Fehler, technische Fehler | Recovery-/Retry-Verhalten unvollständig | Claim-/Lease-/Technical-Error-Tests |
| **P1** | `installer/terraform/runner.py` | `apply`, `verify_plan_integrity`, Workspace-Fehler | echte Runner-Sicherheitschecks ungetestet | Subprocess-Fake-Tests für Fehler und Workspace-Mismatch |
| **P1** | `installer/run/manager.py` | Run-/Plan-Persistenz und Cleanup | Testartefakt-/State-Hygiene unklar | Temporäre Run-Directory-Tests |
| **P1** | `module_builder/validation.py` | `validate_generated_project` | `--validate` kann fehlerhafte Projekte nicht sicher prüfen | Fehlendes Terraform, fmt/validate-Fehler, Erfolgsfall |
| **P1** | `terraform/policy/validate-plan.py` | Fehler-/Policy-Zweige | Policy-Gate umgehungsanfällig | Negative Plan-JSONs und Exit-Code-Tests |
| **P2** | `module_builder/cli.py` / `__main__.py` | CLI-Fehlerpfade, Entrypoint | Bedienfehler weniger sichtbar | CLI-Argument-/Exit-Code-Tests |
| **P2** | E2E-Harness | `Urllib3Transport`, einzelne Redaktionszweige | Kein Live-Nachweis, aber lokale Fake-Abdeckung gut | Opt-in-Live-Test erst nach Freigabe |

### Architekturthemen (keine Coverage-Fixes)

- **Fehlender API-Idempotency-Key:** RC4 dedupliziert wiederholte POSTs nicht;
  dokumentiert in `docs/phase2-async-order-ingest.md:154-162`. Kein
  Test-Gap, sondern eine Produktvertragslücke.
- **Fehlende sichere Live-Testdatenbereinigung:** keine öffentliche,
  eigentümergebundene Order-Delete-Route. Live-Cleanup bleibt **BLOCKED**;
  keine DynamoDB-Direktlöschung als Workaround.

---

## 7. Grenzen lokaler Tests gegenüber AWS-Live-E2E

Nicht abgedeckt und weiterhin **LIVE BLOCKED**:

- echte Cognito-Tokenausstellung/Autorisierung,
- API Gateway HTTP-Verhalten und echte 401/201/404-Antworten,
- echte SQS-Zustellung, Visibility, Retries und DLQ,
- echte DynamoDB-Conditional-Writes und GSI1/GSI2/GSI3,
- Terraform Apply/Plan gegen AWS,
- Live-Cleanup und Live-Testdatenverwaltung.

Die 4 Live-E2E-Tests wurden nicht ausgeführt; sie sind ohne Opt-in und ohne
sichere Cleanup-Fähigkeit `BLOCKED`. Lokale 401-Coverage stammt aus dem
Fake-Transport.

---

## 8. Regression

```text
Installer:      621 PASS
Builder:        128 PASS
Lambda:         337 PASS
E2E-Harness:     16 PASS
Gesamt:       1.102 PASS
Live-E2E:         4 BLOCKED/SKIP (nicht Teil der Regression)
```

Keine neuen Skips in der lokalen Regression. Die Live-Skips sind erwartet und
werden nicht als PASS gezählt.

Coverage-Artefakte:

- `.coverage`-Dateien: nur unter `/tmp/opencode/mo10d-coverage/`
- JSON/Report: nur unter `/tmp/opencode/mo10d-coverage/`
- **keine** Coverage-Artefakte im Repository
- **keine** Änderung an `requirements.txt`, `.coveragerc` oder System-Python

---

## 9. Sicherheitsnachweise

| Prüfung | Ergebnis |
|---|---|
| AWS-/Cognito-Live-Aufruf | **NEIN** |
| Echter HTTP-Request aus Tests | **NEIN** |
| Terraform Apply/Destroy/Import | **NEIN** |
| Produktcodeänderung | **NEIN** |
| Testdatenbank-/SQS-Schreibzugriff | **NEIN** |
| Credentials in Reports | **NEIN** |
| Coverage-Artefakte versioniert | **NEIN** |
| Push/Merge | **NEIN** |

Die Coverage-Messung verwendete ausschließlich lokale Testläufe und
Fake-/Mock-Grenzen.

---

## 10. Git-Abschluss

Vorgesehen:

```text
Commit: test(rc4): measure coverage and document test quality gaps
Branch: test/mo-rc4-testsuite-hardening-10a
```

Der Commit enthält nur den Bericht und den Auditlog-Eintrag; keine
Coverage-Artefakte und keine Produktdateien. Commit-SHA und CLEAN-Status werden
nach dem Commit verifiziert.
