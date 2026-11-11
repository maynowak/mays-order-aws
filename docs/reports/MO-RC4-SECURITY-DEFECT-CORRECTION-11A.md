# MO-RC4-SECURITY-DEFECT-CORRECTION-11A

**Korrektur der in 10E-A gemeldeten Installer-Sicherheitsdefekte**

**Datum:** 2026-11-11
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**Ausgangs-HEAD:** `f7f3ffe73c00d732c4bd532b5b785c40f2f0f19b`
**Korrektur-Commit:** `0138e601395dfbcba0945befff8fed95aed33284`
**Modus:** lokale Codeanalyse, lokale Tests, keine AWS-/Cognito-/HTTP-Aufrufe,
keine Terraform-Prozesse, kein Push/Merge.

```text
MO-RC4-SECURITY-DEFECT-CORRECTION-11A — VERIFIED
```

**Scope-Hinweis:** SEC-01 bis SEC-05 wurden als bestätigte
Implementierungsfehler korrigiert. SEC-06 ist kein Implementierungsfehler,
sondern eine **Vertragslücke / NEEDS DECISION**; sie wurde gemäß Auftrag
ausdrücklich aus dem Implementierungsumfang ausgeklammert.

---

## 1. Ausgangsbaseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD vor Korrektur | `f7f3ffe73c00d732c4bd532b5b785c40f2f0f19b` |
| 10A–10E-A | VERIFIED/PARTIAL dokumentiert |
| Installer vorher | 664 PASS |
| Builder | 128 PASS |
| Lambda | 337 PASS |
| E2E-Harness | 16 PASS |
| Gesamt vorher | **1.145 PASS** |

---

## 2. Reproduktion aller sechs Befunde

| ID | Befund | Klassifikation | Reproduktion |
|---|---|---|---|
| SEC-01 | `ApprovalGate` doppelt definiert; zweite Definition ruft sich selbst auf | **CONFIRMED / REACHABLE** | `ApprovalGate(context)` → `RecursionError` |
| SEC-02 | `_has_valid_deployment_id` fehlt | **CONFIRMED / NOT REACHABLE** | `FailClosedValidator.validate_deployment_context()` → `AttributeError` |
| SEC-03 | Undefinierte Variablen in Planintegritätsprüfung | **CONFIRMED / NOT REACHABLE** | `validate_plan_integrity()` → `NameError` |
| SEC-04 | `require_plan_match()` blockiert auch passende Pläne | **CONFIRMED / NOT REACHABLE** | identische Plan-/Erwartungsdaten → `PlanIntegrityError` |
| SEC-05 | `validate_workspace_path()` ignoriert den übergebenen Root | **CONFIRMED / NOT REACHABLE** | fremder Pfad außerhalb des Roots wird akzeptiert |
| SEC-06 | Keine Plan-/Workspace-Bindung im Approval-Kontext | **CONTRACT GAP / NEEDS DECISION** | `verify_approval_context()` akzeptiert Deploy-Kontext mit fremdem Plan |

„Nicht erreichbar“ bedeutet: kein produktiver Aufrufer im aktuellen
CLI-Pfad gefunden. Die Module bleiben dennoch öffentliche
Sicherheitsbausteine; ein späterer Aufrufer würde die Defekte auslösen.

### SEC-01 — ApprovalGate

Die erste `ApprovalGate`-Klasse enthielt die Safety-Checks und
`request_approval`; eine zweite Definition überschrieb sie und rief im
Konstruktor erneut `ApprovalGate(context)` auf. Minimale Reproduktion:

```text
RecursionError: maximum recursion depth exceeded
```

### SEC-02 — Deployment-Validierung

`FailClosedValidator.validate_deployment_context()` rief die nicht
definierte Methode `_has_valid_deployment_id()` auf.

### SEC-03 — Planintegrität

`validate_plan_integrity()` verwendete nicht definierte Namen
`expected_deployment_id`, `expected_operation`, `expected_version`.

### SEC-04 — Plan-Match

`FailClosedGuard.require_plan_match()` rief `_should_fail(True, ...)`
unbedingt auf und blockierte damit auch identische Pläne.

### SEC-05 — Workspace-Root

`validate_workspace_path()` konstruierte `WorkspaceIntegrity` aus dem
Zielpfad statt aus dem übergebenen `workspace_root`. Ein fremder Pfad wurde
dadurch als „innerhalb“ akzeptiert.

### SEC-06 — Approval-Bindung

`ApprovalContext` enthält Deployment-ID, Operation, Plan-Dateiname und
Run-ID, aber keine Prüfung gegen Plan-Fingerprint und Workspace. Die
CLI-Kette prüft Planmanifest, Plan-Kontext, Version, State und Workspace
vor dem Approval-Prompt; der Approval-Kontext selbst ist jedoch nicht
kryptografisch an diese Werte gebunden. Eine neue Bindung wäre eine
Vertragsentscheidung, keine stille Korrektur.

---

## 3. Sicherheitsvertrag / Erreichbarkeit

- `ApprovalGate` wird von `installer/cli/gui.py` importiert, dort aber nicht
  aufgerufen; die Klasse ist dennoch öffentliche Schnittstelle.
- `FailClosedValidator` und `require_plan_match` haben aktuell keinen
  produktiven Aufrufer; sie sind Sicherheitsbausteine für nachgelagerte
  Integrationen.
- `WorkspaceIntegrity` wird von GUI/Subprocess-Safety verwendet;
  `validate_workspace_path` ist ein öffentlicher Convenience-Helper.
- Die CLI prüft vor Approval bereits Planmanifest, Plan-Kontext,
  Deployment-ID, Operation, Version, State, Backup und Workspace. Eine
  zusätzliche Approval-Bindung an Fingerprint/Workspace ist im bestehenden
  Datenmodell nicht spezifiziert.

---

## 4. Durchgeführte Produktkorrekturen

### SEC-01 — ApprovalGate

- Die doppelte Klassendefinition entfernt.
- `evaluate()` in die bestehende `ApprovalGate`-Klasse integriert.
- `request_approval()` verwendet jetzt korrekt `self.context.auto_approve`.
- Öffentliche `ApprovalGate`-Schnittstelle bleibt erhalten.

### SEC-02 — Deployment-Validierung

- `_has_valid_deployment_id()` ergänzt.
- Akzeptiert `DeploymentId` oder eine parsebare kanonische ID.
- Ungültige/fehlende IDs werden abgelehnt.

### SEC-03 — Planintegrität

- Fehlende Werte werden aus `expected_context` gelesen.
- Deployment-ID, Operation, Version und Plan-Fingerprint werden verglichen.
- Fehlende Daten oder fehlender Fingerprint → `ValidationFailedError`.
- Deployment-Mismatch → `DeploymentMismatchError`.

### SEC-04 — Plan-Match

- `require_plan_match()` vergleicht jetzt tatsächlich Deployment-ID,
  Operation, Version und Fingerprint (`plan_sha256`/`plan_fingerprint`/
  `sha256`).
- Identische Werte werden akzeptiert.
- Mismatch oder fehlender Fingerprint → `PlanIntegrityError`.

### SEC-05 — Workspace-Root

- `validate_workspace_path()` verwendet jetzt den expliziten
  `workspace_root`.
- Pfade außerhalb des Roots werden abgelehnt.
- Workspace-Isolation bleibt fail-closed.

### SEC-06 — Approval-Bindung

**Nicht implementiert (NEEDS DECISION).** Keine Vertragsänderung ohne
Entscheidung. Vorschlag siehe Abschnitt 9.

---

## 5. Regressionstests

Neu/erweitert in `installer/tests/test_security_gates_10ea.py`:

- ApprovalGate-Konstruktion und `evaluate()`.
- Interaktive Ablehnung (`input` → `n`).
- Fehlende/ungültige Approval-Felder.
- Workspace-Root-Enforcement und Symlink-/Traversal-Schutz.
- Deployment-Kontext: valide, fehlende/ungültige ID.
- Planintegrität: Match, Deployment-Mismatch, fehlende Daten/Fingerprint.
- Plan-Match: Match, Mismatch, fehlender Fingerprint.
- Fail-Closed-Guard: alle Pflichtprüfungen.

Fokussierte Ausführung:

```bash
python3 -m unittest installer.tests.test_security_gates_10ea
```

```text
Ran 48 tests in 0.016s
OK
```

### Vorher/Nachher

Vor der Korrektur schlugen die korrigierten Erwartungstests erwartungsgemäß
fehl (u. a. `RecursionError`, `AttributeError`, `NameError`,
`WorkspaceError not raised`). Nach den Korrekturen: **48 PASS**.

---

## 6. Mutationstests

Vier Mutationen wurden ausschließlich in temporären Kopien durchgeführt.

### Mutation A — Approval-Ablehnung entfernt

```text
FAIL: test_missing_deployment_id_is_rejected
AssertionError: True is not false
```

### Mutation B — Plan-Mismatch-Prüfung entfernt

```text
FAIL: test_plan_mismatch_and_missing_fingerprint_are_denied
AssertionError: PlanIntegrityError not raised
```

### Mutation C — Workspace-Grenzprüfung entfernt

```text
FAIL: test_path_outside_workspace_is_rejected
AssertionError: WorkspaceError not raised
```

### Mutation D — Fail-Closed-Fehlerpfad neutralisiert

```text
FAIL: test_validation_failure_is_denied
AssertionError: ValidationFailedError not raised
```

Alle vier Mutationen wurden von den zuständigen Tests erkannt. Keine
Mutation wurde in den Arbeitsbranch übernommen.

---

## 7. Coverage-Vergleich

Messung wie 10D/10E-A: coverage.py 7.4.4, `--branch`,
`--source=installer,terraform/policy`, `--omit='installer/tests/*'`.

| Kennzahl | 10E-A | 11A | Bewertung |
|---|---:|---:|---|
| Installer Statements | 73,13 % | **74,08 %** | Korrektur + neue Tests |
| Installer Branches | 62,43 % | **64,04 %** | Korrektur + neue Tests |
| Approval | 53,73 % / 27,08 % | **83,08 % / 62,50 %** | Duplikat entfernt, Gate-Pfad ausgeführt |
| Workspace | 84,62 % / 75,00 % | **84,62 % / 75,00 %** | unverändert |
| Fail-Closed | 74,88 % / 43,42 % | **79,54 % / 64,00 %** | Plan-/Deployment-Pfade korrigiert |

**Scope-Hinweis:** Die Produktkorrektur hat 44 Statements und 24 Branches
hinzugefügt (Validierungs-/Fingerprint-Logik). Die Gesamtwerte sind daher
nicht ausschließlich Testverbesserung.

Bereinigter Vergleich ohne die drei neu importierten Sicherheitsmodule:

```text
10D:   4.008 / 5.458 = 73,43 % Statements; 1.369 / 2.144 = 63,85 % Branches
11A:   4.012 / 5.458 = 73,51 % Statements; 1.373 / 2.144 = 64,04 % Branches
```

Die leichte Erhöhung stammt aus zusätzlich ausgeführten
Deployment-Identity-Konstruktoren in den neuen Tests.

### Verbleibende Coverage-Lücken

- `ApprovalGate`: Safety-Check-Methoden sind weiterhin überwiegend
  Platzhalter (`return True`); kein AWS-/Policy-Kontext wird tatsächlich
  geprüft.
- `FailClosedValidator`: einige Rand-/Konfigurationspfade bleiben offen.
- Die 10D-Liste nicht importierter Module bleibt bestehen:
  `atomic_ops.py`, `command_result.py`, `command_service.py`,
  `lock_manager.py`, `logging_hardening.py`, `plan_integrity.py`,
  `recovery.py`, `subprocess_safety.py`, `cli/gui.py`.

---

## 8. Vollständige Regression

```text
Installer:      669 PASS   (664 + 5 neue Tests)
Builder:        128 PASS
Lambda:         337 PASS
E2E-Harness:     16 PASS
Gesamt:       1.150 PASS
Live-E2E:         4 BLOCKED (nicht Teil der Regression)
```

Keine neuen Skips. Alle Tests lokal, ohne AWS/Terraform/Netzwerk.

---

## 9. SEC-06 — Entscheidungsvorlage

**Klassifikation:** `CONTRACT GAP / NEEDS DECISION`

**Vorschlag für einen späteren Vertrag:**

- `ApprovalContext` um `plan_sha256` und `workspace` erweitern.
- Approval an `deployment_id`, `operation`, `plan_sha256`, `workspace` und
  eine kurzlebige `approval_id`/Nonce binden.
- Ablaufzeit und Einmalverwendung definieren.
- Beim Apply erneut Manifest, Fingerprint und Workspace vergleichen.
- Migrationsfolge: bestehende CLI-Prompts bleiben kompatibel; neue Felder
  optional für Altpfade, verpflichtend für neue Approval-Tokens.
- Keine stille Einführung; separate Architektur-/Security-Entscheidung und
  Freigabe erforderlich.

**Nicht umgesetzt.** Bestehende Sicherheitsanforderungen wurden nicht
abgeschwächt.

---

## 10. Sicherheitsnachweise

| Prüfung | Ergebnis |
|---|---|
| AWS-/Cognito-/HTTP-Aufruf | **NEIN** |
| Terraform-Prozess | **NEIN** |
| Echte Deploy-/Destroy-Ausführung | **NEIN** |
| Produktcodeänderung | **JA, nur SEC-01–05** |
| Änderung außerhalb des Sicherheitsbereichs | **NEIN** |
| Credentials in Logs | **NEIN** |
| Push/Merge | **NEIN** |

---

## 11. Git-Abschluss

```text
Korrektur-Commit: 0138e601395dfbcba0945befff8fed95aed33284
Message: fix(rc4): repair installer approval plan and fail-closed gates
```

Der Bericht und der Auditlog-Eintrag werden in einem separaten Doku-Commit
festgehalten. Kein Push, kein Merge. Der finale Working-Tree-Status wird nach
dem Doku-Commit verifiziert.
