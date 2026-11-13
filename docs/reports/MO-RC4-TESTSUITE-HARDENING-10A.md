# MO-RC4-TESTSUITE-HARDENING-10A

**Ersatz der sechs Installer-Sicherheitsplatzhalter durch deterministische Tests**

**Datum:** 2026-11-11
**Referenz:** `test/mo-rc4-aws-test-functional-verify-08` @ `ab62250`
**Arbeitsbranch:** `test/mo-rc4-testsuite-hardening-10a`
**Modus:** Lokale Teständerungen; keine AWS-Mutation, kein Terraform-Apply/Destroy,
kein Backup/Restore, keine Cognito-/IAM-/RIS-/CloudFront-Änderung, kein Push/Merge.

```text
MO-RC4-TESTSUITE-HARDENING-10A — VERIFIED
```

---

## 1. Git-Baseline

| Feld | Wert |
|---|---|
| Referenzbranch | `test/mo-rc4-aws-test-functional-verify-08` |
| Referenz-HEAD | `ab62250` |
| Arbeitsbranch | `test/mo-rc4-testsuite-hardening-10a` |
| Ausgangs-Working-Tree | CLEAN |
| Änderungsumfang | zwei Testdateien, dieser Bericht und der Auditlog-Index |

---

## 2. Identifizierte Testmethoden

Die Audit-Zeilennummern wurden vor der Änderung gegen die tatsächlichen
Methoden geprüft:

| Audit-Zeile | Methode | Vorher |
|---:|---|---|
| 465 | `TestDeployCommand.test_deploy_requires_approval` | `self.assertTrue(True)` |
| 491 | `TestDeployCommand.test_deploy_requires_plan_file` | `self.assertTrue(True)` |
| 511 | `TestDeployCommand.test_destroy_requires_approval` | `self.assertTrue(True)` |
| 649 | `TestYesFlagBehavior.test_yes_flag_skips_approval_prompt` | `self.assertTrue(True)` |
| 669 | `TestYesFlagBehavior.test_without_yes_requires_approval` | `self.assertTrue(True)` |
| 22 | `TestParallelIsolation.test_two_projects_different_workspace` | `self.assertTrue(True)` |

---

## 3. Neues Testverhalten

### 3.1 Deploy-Approval (`test_deploy_requires_approval`)

Der Test ruft den echten `InstallerCLI._cmd_deploy`-Pfad auf, ersetzt aber alle
AWS-/Terraform-Grenzen durch Mocks. Bei Eingabe `n` wird geprüft:

- Rückgabewert `0` und Meldung `Deployment cancelled.`
- `runner.apply` wurde **nicht** aufgerufen.
- `runner.state_list` und `runner.version` wurden **nicht** aufgerufen.
- `subprocess.run` wurde **nicht** aufgerufen.
- Der Prompt wurde exakt einmal mit
  `Proceed with deployment? [y/N]: ` aufgerufen.

### 3.2 Fehlender Deploy-Plan (`test_deploy_requires_plan_file`)

- Rückgabewert `1`.
- `_make_runner` wurde nicht aufgerufen.
- `runner.apply` und `subprocess.run` wurden nicht aufgerufen.
- Ausgabe enthält `Plan file not found`; `Applying plan` fehlt.

### 3.3 Destroy-Approval (`test_destroy_requires_approval`)

Der echte `_cmd_destroy`-Pfad wird mit gemockter Backend-/Cleanup-Grenze
ausgeführt. Bei Eingabe `n` wird geprüft:

- Rückgabewert `0` und Meldung `Destruction cancelled.`
- `runner.destroy`, `runner.apply` und `runner.state_list` wurden nicht aufgerufen.
- `subprocess.run` wurde nicht aufgerufen.
- Keine Methode aus `{destroy, apply, state_list, backup, restore}` erscheint in
  den Runner-Aufrufen.
- Der Destroy-Prompt wurde exakt einmal aufgerufen.

### 3.4 `--yes` (`test_yes_flag_skips_approval_prompt`)

- `input()` wird mit einer `AssertionError`-Side-Effect gepatcht; ein Aufruf
  würde den Test sofort fehlschlagen lassen.
- `runner.apply`, `runner.state_list` und `runner.version` werden exakt einmal
  aufgerufen.
- `subprocess.run` bleibt ungenutzt; es findet kein echter Terraform-Aufruf statt.
- Erfolgsmeldung `Deployment completed successfully!` wird geprüft.

### 3.5 Default-Deny (`test_without_yes_requires_approval`)

- Leere Eingabe am Approval-Prompt führt zu `Deployment cancelled.`
- Kein Apply, kein State-/Versionszugriff, kein `subprocess.run`.
- Der Prompt wird exakt einmal aufgerufen.

### 3.6 Workspace-Isolation (`test_two_projects_different_workspace`)

Der Test prüft jetzt die tatsächlichen Aufrufe von `_ensure_workspace()`:

- Exakte Reihenfolge:
  `workspace select mays-orders`, `workspace show`,
  `workspace select mays-orders-privacy-test`, `workspace show`.
- Kein `default`-Wert in irgendeinem Workspace-Kommando.
- Konstruktor lehnt `workspace="default"` und `workspace=""` bei
  `require_explicit_workspace=True` mit `ValueError` ab.
- Ein `workspace show`-Mismatch führt zu `TerraformError`, kein stiller Fallback.

---

## 4. Ausgeführte Testkommandos

### Schritt A — Fokussierte Tests

```bash
python3 -m unittest -v \
  installer.tests.test_installer.TestDeployCommand.test_deploy_requires_approval \
  installer.tests.test_installer.TestDeployCommand.test_deploy_requires_plan_file \
  installer.tests.test_installer.TestDeployCommand.test_destroy_requires_approval \
  installer.tests.test_installer.TestYesFlagBehavior.test_yes_flag_skips_approval_prompt \
  installer.tests.test_installer.TestYesFlagBehavior.test_without_yes_requires_approval \
  installer.tests.test_parallel_isolation.TestParallelIsolation.test_two_projects_different_workspace
```

Ergebnis:

```text
Ran 6 tests in 0.043s
OK
```

### Schritt B — Installer-Regression

```bash
python3 -m unittest discover -s installer/tests
```

Ergebnis:

```text
Ran 621 tests in 21.506s
OK
```

### Schritt C — Gesamte lokale Regression

```bash
python3 -m unittest discover -s module_builder/tests
```

```text
Ran 128 tests in 1.321s
OK
```

```bash
cd lambda && PYTHONPATH=src python3 -m unittest discover -s tests
```

```text
Ran 326 tests in 0.427s
OK
```

Gesamt: **1.075 PASS**, keine Skips.

---

## 5. Sicherheitsnachweise

| Prüfung | Ergebnis |
|---|---|
| Produktcode geändert | **NEIN** — nur `installer/tests/` und Doku |
| AWS-Credentials benötigt | **NEIN** |
| AWS-API-Aufruf | **NEIN** — Runner und `subprocess.run` gemockt |
| Terraform apply/destroy real | **NEIN** — nur Mock-Aufrufe |
| Backup/Restore | **NEIN** |
| Cognito-/IAM-/RIS-/CloudFront-Änderung | **NEIN** |
| Externe Netzwerkaufrufe | **NEIN** |
| Unbeabsichtigte Dateisystemmutation | **NEIN** — nur temporäre Plan-Dateien |
| Neue Platzhalter-Assertions | **NEIN** — `assertTrue(True)` in `installer/tests` entfernt |

**Erkennung eines entfernten Approval-Checks:** Würde `if not parsed.yes` im
Deploy- oder Destroy-Pfad entfernt, würden `runner.apply` bzw. `runner.destroy`
aufgerufen; die `assert_not_called`-Assertions schlagen dann fehl. Würde der
`--yes`-Pfad wieder einen Prompt verlangen, löst die gepatchte
`input()`-Side-Effect-Assertion den Testfehler aus.

Zusätzlich wurde ein lokaler Mutationstest in einer **temporären Kopie**
außerhalb des Repositories durchgeführt: Beide Approval-Blöcke wurden aus der
Kopie entfernt, danach die beiden Denial-Tests ausgeführt. Erwartetes Ergebnis:

```text
FAIL: test_deploy_requires_approval
AssertionError: Expected 'apply' to not have been called. Called 1 times.

FAIL: test_destroy_requires_approval
AssertionError: Expected 'destroy' to not have been called. Called 1 times.

FAILED (failures=2)
```

Damit ist belegt, dass die Tests einen entfernten Approval-Check erkennen.
Die temporäre Kopie wurde nicht in das Repository übernommen.

---

## 6. Verbleibende Risiken

- Die Tests prüfen den Command-Pfad mit gemockten Grenzen, nicht den vollständigen
  CLI-Prozess inklusive `_create_context`/Run-Directory-Erzeugung.
- Die Destroy-Denial-Prüfung bestätigt, dass der aktuelle `_cmd_destroy`-Pfad
  keine Backup-/Restore-Methode erreicht; es wird keine separate Backup-Komponente
  instanziiert, weil der Produktpfad sie nicht aufruft.
- Reale Terraform-/AWS-Interaktionen bleiben absichtlich außerhalb dieser Tests.
- Der Workspace-Test prüft das Runner-Verhalten; er ersetzt keinen Live-Test
  gegen einen AWS-Backend-Workspace.

---

## 7. Git-Diff-Zusammenfassung

```text
 installer/tests/test_installer.py          | 346 ++++++++++++++++++-----------
 installer/tests/test_parallel_isolation.py |  58 ++++-
 2 files changed, 262 insertions(+), 142 deletions(-)
```

- Keine Änderungen außerhalb der beiden Testdateien, dieses Berichts und des
  Auditlog-Index.
- `git diff --check` ohne Befund.
- Kein Push, kein Merge.
