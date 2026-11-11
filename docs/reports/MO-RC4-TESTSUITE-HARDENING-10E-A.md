# MO-RC4-TESTSUITE-HARDENING-10E-A

**Lokale Tests für Installer-Approval, Workspace-Isolation und Fail-Closed**

**Datum:** 2026-11-11
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD bei Beginn:** `cb149920896f37a08d24451690b6c39b6ea6ef70`
**Modus:** ausschließlich lokale Tests; keine AWS-/Cognito-/HTTP-Aufrufe,
keine Terraform-Prozesse, keine Produktcodeänderung, kein Push/Merge.

```text
MO-RC4-TESTSUITE-HARDENING-10E-A — PARTIAL
```

**Begründung:** Die Tests laufen vollständig lokal und decken die vorhandenen
Sicherheitsentscheidungen ab. Die tatsächliche `ApprovalGate`-Klasse sowie
mehrere `FailClosedValidator`-Pfade sind im Produktcode jedoch derzeit nicht
ausführbar (duplizierte Klasse bzw. undefinierte Namen). Diese Defekte wurden
durch Tests dokumentiert, dürfen aber ohne Produktcodeänderung nicht behoben
werden. Deshalb ist eine vollständige Approval-/Fail-Closed-Verifikation nicht
möglich.

---

## 1. Ausgangsbaseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `cb149920896f37a08d24451690b6c39b6ea6ef70` |
| 10A–10D | VERIFIED |
| Working Tree | CLEAN |
| Regression vor 10E-A | Installer 621, Builder 128, Lambda 337, E2E 16 = **1.102 PASS** |
| Installer-Coverage 10D | 73,43 % Statements, 63,85 % Branches |

---

## 2. Tatsächliche Sicherheitsmodule und Schnittstellen

### `installer/core/approval.py`

Tatsächliche Schnittstellen:

- `ApprovalContext` — Deployment-ID, Operation, Plan, Run-ID, `auto_approve`,
  `skip_approval`; `__post_init__` lehnt `skip_approval` ohne
  `auto_approve` ab.
- `verify_approval_context()` — prüft Pflichtfelder und Operation.
- `create_approval_context()` — Factory.
- `ApprovalGate` — Sicherheitschecks und interaktive Freigabe.

**Befund:** `ApprovalGate` ist im Modul **zweimal definiert**. Die zweite
Definition überschreibt die erste; ihr `__init__` ruft
`ApprovalGate(context)` erneut auf und läuft in eine `RecursionError`.
Die produktive Klasse ist damit nicht instanziierbar. `verify_approval_context`
ist dagegen ausführbar.

### `installer/core/workspace.py`

Tatsächliche Schnittstellen:

- `WorkspaceIntegrity` — validiert Pfade gegen Workspace-Root, `runs/` und
  `terraform/`; `validate_path`, `validate_relative_path`,
  `ensure_within_workspace`, `is_within_workspace`.
- `validate_workspace_path()` — Convenience-Funktion.
- `create_workspace_integrity()` — Factory.

**Befund:** `WorkspaceIntegrity` selbst verhindert Pfad-Traversal und
Symlink-Escapes korrekt. `validate_workspace_path()` ignoriert jedoch den
übergebenen `workspace_root` und leitet den Root aus dem Zielpfad ab; der
Helper ist damit kein eigenständiger Boundary-Guard.

### `installer/core/fail_closed.py`

Tatsächliche Schnittstellen:

- `FailClosedConfig` / `FailClosedPolicy`
- `FailClosedGuard` — `require_valid`, `require_known_state`,
  `require_deployment_match`, `require_lock`, `require_aws_state`,
  `require_plan_match`.
- `FailClosedValidator` — Deployment-/Plan-/AWS-Kontext.
- `fail_closed()`-Decorator, `fail_closed_context`, `fail_closed_scope`.

**Befund:**

- `FailClosedGuard.require_plan_match()` ruft `_should_fail(True, ...)`
  unbedingt auf und blockiert daher auch einen passenden Plan.
- `FailClosedValidator.validate_deployment_context()` verwendet die nicht
  definierte Methode `_has_valid_deployment_id` → `AttributeError`.
- `FailClosedValidator.validate_plan_integrity()` verwendet nicht definierte
  Variablen `expected_deployment_id`, `expected_operation`, `expected_version`
  → `NameError`.
- Die Guard-/Decorator-Grundfunktionen sind ausführbar und fail-closed.

### Vorherige Verwendung

`approval.py` und `workspace.py` wurden vor 10E-A von der Testsuite **nicht
importiert**. `fail_closed.py` ebenfalls nicht. Die Coverage aus 10D enthielt
diese Module daher nicht.

---

## 3. Neue Testdatei

`installer/tests/test_security_gates_10ea.py`

**43 neue Tests**, keine Produktcodeänderung, keine externen Prozesse.

---

## 4. Approval-Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Gültiger Approval-Kontext | PASS |
| Fehlende `deployment_id` | PASS — abgelehnt |
| Fehlender Plan | PASS — abgelehnt |
| Fehlende Run-ID | PASS — abgelehnt |
| Ungültige Operation (`Deploy`, `APPLY`, leer) | PASS — abgelehnt |
| `skip_approval` ohne `auto_approve` | PASS — `ValueError` |
| `skip_approval` mit `auto_approve` | PASS |
| Operation-/Plan-/Workspace-Bindung | **PARTIAL** — `verify_approval_context` prüft keine Plan- oder Workspace-Bindung; dokumentiert |
| Echte `ApprovalGate`-Instanziierung | **BLOCKED** — `RecursionError` durch doppelte Klassendefinition |

---

## 5. Workspace-Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Pfad innerhalb Workspace | PASS |
| Pfad außerhalb Workspace | PASS — `WorkspaceError` |
| Relativer `../`-Traversal | PASS — `WorkspaceError` |
| Symlink-Escape | PASS — `WorkspaceError` |
| `is_within_workspace()` | PASS |
| Explizite `runs/terraforming`-Roots | PASS |
| Factory mit explizitem Root | PASS |
| `validate_workspace_path()` mit fremdem Root | **PARTIAL** — Helper ignoriert den übergebenen Root; als Defekt dokumentiert |
| Terraform-Workspace-Auswahl | **PASS** — bereits in 10A über `TerraformRunner`/`subprocess.run`-Fake geprüft; keine neuen Terraform-Prozesse |

---

## 6. Fail-Closed-Prüfungen

| Prüfung | Ergebnis |
|---|---|
| `require_valid(False)` | PASS — `ValidationFailedError` |
| Unbekannter Zustand (`None`) | PASS — `UncertainStateError` |
| Deployment-Mismatch | PASS — `DeploymentMismatchError` |
| Fehlender Lock | PASS — `LockFailureError` |
| Unbekannter AWS-State | PASS — `UnknownAWSStateError` |
| Lenient Policy | PASS — definierte Ausnahmen |
| Strict Policy | PASS — alle Switches aktiv |
| Decorator/Context/Scope wandeln unerwartete Fehler um | PASS |
| AWS-Kontextvalidierung | PASS für unvalidiert/fehlendes Konto/valide |
| `require_plan_match()` | **PARTIAL** — blockiert auch passende Pläne |
| `validate_deployment_context()` | **BLOCKED** — `AttributeError` |

---

## 7. Mutationstest-Nachweise

Alle Mutationen wurden ausschließlich in temporären Kopien außerhalb des
Arbeitsworktrees durchgeführt.

### Mutation A — Approval-Ablehnung entfernt

`verify_approval_context()` wurde so verändert, dass die fehlende
`deployment_id` nicht mehr geprüft wird.

```text
FAIL: test_missing_deployment_id_is_rejected
AssertionError: True is not false
Ran 1 test — FAILED (failures=1)
```

### Mutation B — Workspace-Mismatch entfernt

`WorkspaceIntegrity.validate_path()` wurde so verändert, dass Pfade außerhalb
des Workspace akzeptiert werden.

```text
FAIL: test_path_outside_workspace_is_rejected
AssertionError: WorkspaceError not raised
Ran 1 test — FAILED (failures=1)
```

### Mutation C — Fail-Closed-Fehler verschluckt

`FailClosedGuard._should_fail()` wurde so verändert, dass Bedingungen nicht
mehr zu einer Exception führen.

```text
FAIL: test_validation_failure_is_denied
AssertionError: ValidationFailedError not raised
Ran 1 test — FAILED (failures=1)
```

Alle drei zuständigen Tests erkennen die Mutation.

---

## 8. Coverage vorher/nachher

Messumfang wie 10D: `--branch --source=installer,terraform/policy
--omit='installer/tests/*'`, coverage.py 7.4.4.

### Vergleich

| Kennzahl | 10D | 10E-A | Bewertung |
|---|---:|---:|---|
| Installer Statements | 73,43 % | **73,13 %** | Scope erweitert um 397 zuvor nicht importierte Statements |
| Installer Branches | 63,85 % | **62,43 %** | Scope erweitert um 312 zuvor nicht importierte Branches |
| Approval | nicht erfasst | **53,73 % / 27,08 %** | jetzt erfasst |
| Workspace | nicht erfasst | **84,62 % / 75,00 %** | jetzt erfasst |
| Fail-Closed | nicht erfasst | **74,88 % / 43,42 %** | jetzt erfasst |

**Gleicher Scope wie 10D, ohne die drei neu importierten Module:**

```text
Statements: 4.008 / 5.458 = 73,43 %  (unverändert)
Branches:   1.369 / 2.144 = 63,85 %  (unverändert)
```

Die Gesamtwerte sinken daher **nicht durch Regression**, sondern weil 10D
`approval.py`, `workspace.py` und `fail_closed.py` überhaupt nicht im
Nenner hatte. Die neuen Tests erhöhen die Abdeckung dieser drei Module, nicht
die bereits gemessenen Module.

### Neue Sicherheitsmodule

| Datei | Statements | Branch |
|---|---:|---:|
| `installer/core/approval.py` | 72/134 = 53,73 % | 13/48 = 27,08 % |
| `installer/core/workspace.py` | 44/52 = 84,62 % | 6/8 = 75,00 % |
| `installer/core/fail_closed.py` | 158/211 = 74,88 % | 33/76 = 43,42 % |

Wichtige fehlende Approval-Zweige: erste, von der zweiten Definition
überschriebene `ApprovalGate`-Implementierung sowie die Check-Methoden.
Wichtige fehlende Fail-Closed-Zweige: `FailClosedDecorator`,
`validate_deployment_context`, `validate_plan_integrity` und Teile der
AWS-Kontextvalidierung.

Weiterhin nicht importiert: `atomic_ops.py`, `command_result.py`,
`command_service.py`, `lock_manager.py`, `logging_hardening.py`,
`plan_integrity.py`, `recovery.py`, `subprocess_safety.py`, `cli/gui.py`.

---

## 9. Regressionsergebnisse

```text
Installer:      664 PASS   (621 + 43 neue)
Builder:        128 PASS
Lambda:         337 PASS
E2E-Harness:     16 PASS
Gesamt:       1.145 PASS
Live-E2E:         4 BLOCKED (nicht Teil der Regression)
```

Keine neuen Skips. Alle neuen Tests sind deterministisch, lokal und ohne
AWS-/Terraform-/Netzwerkzugriff.

---

## 10. Sicherheitsnachweise

| Prüfung | Ergebnis |
|---|---|
| AWS-/Cognito-/HTTP-Aufruf | **NEIN** |
| Terraform-Prozess | **NEIN** |
| Produktcodeänderung | **NEIN** |
| Echte Deploy-/Destroy-Ausführung | **NEIN** |
| Credentials in Logs | **NEIN** |
| Fremde Dateien/Workspaces verändert | **NEIN** — temporäre Verzeichnisse |
| Push/Merge | **NEIN** |

`subprocess` wurde in den neuen Tests nicht aufgerufen. Workspace-Tests
arbeiten ausschließlich in `tempfile.TemporaryDirectory()`.

---

## 11. Verbleibende Lücken und Blocker

1. **ApprovalGate ist nicht instanziierbar** — doppelte Klassendefinition,
   `RecursionError`; echte Approval-Entscheidungen der Klasse sind nicht
   prüfbar.
2. **Keine Plan-/Workspace-Bindung im Approval-Kontext** — eine
   Deploy-Freigabe enthält keine Bindung an einen bestimmten Plan oder
   Workspace.
3. **FailClosedValidator ist teilweise nicht ausführbar** —
   `AttributeError`/`NameError` durch fehlende Namen.
4. **`require_plan_match()` blockiert auch passende Pläne.**
5. **`validate_workspace_path()` ignoriert den übergebenen Root.**
6. Weitere Sicherheitsmodule bleiben nicht importiert (siehe oben).
7. Live-AWS-Approval, echte Terraform-Ausführung und Destroy bleiben
   **LIVE BLOCKED**.

Eine Behebung dieser Produktdefekte ist ausdrücklich **nicht** Teil dieses
Auftrags.

---

## 12. Git-Abschluss

Vorgesehen:

```text
Commit: test(rc4): cover installer approval workspace and fail-closed gates
Branch: test/mo-rc4-testsuite-hardening-10a
```

Kein Push, kein Merge. Commit-SHA und CLEAN-Status werden nach dem Commit
verifiziert.
