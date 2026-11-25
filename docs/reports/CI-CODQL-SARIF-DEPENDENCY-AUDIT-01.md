# CI-CODQL-SARIF-DEPENDENCY-AUDIT-01 — CODEQL, SARIF-UPLOAD UND DEPENDENCY-SCANNER

## 1. Status

- **Ergebnis:** `REVIEW COMPLETE` · **CI-Infrastruktur GREEN nach Re-Run** ·
  **Dependency-Scanner-Fehlalarm OPEN**
- **Datum:** 2026-11-25
- **Repository:** `maynowak/mays-order-aws`
- **Branch/HEAD:** `main` `2ef1fd6ec875e5772d2fb3e530ba5376a286837e`
- **Scope:** CodeQL-/SARIF-Upload, Dependency-Check, Security Gate,
  Scanner-Fehlalarm `hashicorp/time ~> 0.11`; keine Produkt-/AWS-/Terraform-/
  RIS-Änderung

## 2. Anlass

Nach dem Wiki-Doku-Commit waren die GitHub-Checks rot. Eine erste Erklärung war
der GitHub-Incident `qn8mfv6q5hlx`. Zusätzlich wurde ein Befund des
repository-eigenen Dependency-Scanners gemeldet. Dieser Report trennt beide
Ursachen und prüft den SARIF-/CodeQL-Pfad.

## 3. Durchgeführte Abschnitte

1. GitHub-Status und Incident-Lage geprüft.
2. Fehlgeschlagene Jobs auf `2ef1fd6` erneut ausgeführt.
3. CodeQL-Log, SARIF-Upload und Coverage geprüft.
4. Dependency-Log, SARIF-Konvertierung und Detector-Ausgabe geprüft.
5. Scanner-Quellcode, Terraform-Constraints und Lock-Datei abgeglichen.
6. HashiCorp-Dokumentation zu `~>` geprüft.
7. Tests/Test-Erwartungen des Scanners geprüft.
8. Report/Auditlog/Wiki ergänzt; Checkpoint folgt.

## 4. Befunde

### F1 — GitHub-Incident (behoben)

- Status am 25.11.2026: „Partial System Outage", Actions `partial_outage`,
  Git Operations `partial_outage`, Incident `qn8mfv6q5hlx` (seit 15:55Z).
- Später: **„All Systems Operational"**; Actions/Git Operations operational.
- Die ersten roten Checks (SARIF-Upload, Rerun HTTP 500) sind damit als
  **externer Incident** erklärt, nicht als Wiki-/Code-Defekt.

### F2 — CodeQL und SARIF (grün)

- Re-Run `45651651020`: **success**.
- Log: `CodeQL scanned 143 out of 143 Python files` und
  `Analysis upload status is complete.`
- Check-Run `CodeQL Analysis / Analyze (python)`: **success**.
- Keine CodeQL-Anpassung erforderlich.

### F3 — Dependency-SARIF (grün hochgeladen, Befund bleibt)

- Re-Run `45651651059`: **success**; `Analysis upload status is complete.`
- Detector-Status: `DEPENDENCY_CHANGE_DETECTED` (Exit 1; Workflow behandelt nur
  Exit 2 als Fehler).
- SARIF-Regel: `SEC01-TERRAFORM_PROVIDER-CONSTRAINT_UNSATISFIED` (Level
  `error`) für `hashicorp/time`.
- Der Security Gate (`45651650996`) ist **success**, evaluiert aber keine
  SARIF-Findings; er führt nur Echo-/Status-Schritte aus. Ein grüner Gate ist
  daher kein Nachweis, dass keine Findings existieren.

### F4 — Scanner-Fehlalarm `hashicorp/time`

- Constraint: `terraform/main.tf:10-11` → `hashicorp/time`, `~> 0.11`.
- Lock: `terraform/.terraform.lock.hcl:28-30` → `version = "0.14.2"`,
  `constraints = "~> 0.11"`.
- HashiCorp-Semantik: `~> 1.1` erlaubt `1.2` und `1.10`, aber nicht `2.0`;
  `~> 1.0.4` erlaubt `1.0.5`/`1.0.10`, aber nicht `1.1.0`. Für `~> 0.11`
  ist `0.14.2` daher **gültig** (`>=0.11, <1.0`).
- Scanner-Implementierung (`security/dependency_detector.py`, `~>`-Zweig)
  behandelt `~> 0.11` jedoch wie `<0.12` und meldet `0.14.0` als
  `CONSTRAINT_UNSATISFIED`. Das ist ein **False Positive**.
- Die Unit-Tests kodieren dieselbe falsche Semantik:
  `installer/tests/test_installer.py` erwartet, dass `1.3.0` `~> 1.2` und
  `1.2.4` `~> 1.2.3` **nicht** erfüllen. Laut Terraform-Doku ist beides
  erfüllt. Ein Fix muss daher auch die Tests korrigieren.

### F5 — AWS-Vergleich ist kein Lock-Drift-Nachweis

- Scanner meldet für `hashicorp/aws`: Constraint `>= 6.0`, „available“ `6.54.0`,
  Status `CURRENT`.
- Lock: `terraform/.terraform.lock.hcl:4-6` → `version = "6.65.0"`.
- Der Scanner liest die Lock-Datei **nicht**; er vergleicht den
  Registry-Latest gegen den Constraint-String. `compare_versions("6.54.0",
  ">= 6.0")` kann nicht sinnvoll vergleichen (Parse-Fehler → 0 → CURRENT).
- Die in einer externen Notiz genannte Zahl `5.39.0` konnte im aktuellen Lauf
  **nicht reproduziert** werden; aktuell wird `6.54.0` gemeldet. Der Kernbefund
  (Constraint statt Lock) bleibt unabhängig davon gültig.
- Ergebnis: Der AWS-Eintrag ist **kein** belastbarer Drift-/Kompatibilitäts-
  Nachweis; die Lock-Datei ist die relevante Quelle.

### F6 — Kein Wiki-/Produktdefekt

- Die Wiki-Änderungen sind reine Markdown-/Bild-/AGENTS-Änderungen.
- CodeQL analysierte 143/143 Python-Dateien und lud SARIF erfolgreich hoch.
- Die Scanner-Findings betreffen die CI-Tooling-Logik, nicht die Wiki.

## 5. Klassifikation

| Bereich | Status |
|---|---|
| GitHub-Incident/SARIF-Upload | **GREEN** (behoben, Re-Runs grün) |
| CodeQL | **GREEN** (143/143, Upload complete) |
| Dependency-Workflow | **GREEN** (Upload complete; Exit 1 toleriert) |
| Dependency-Scanner-Semantik | **YELLOW/OPEN** (False Positive `~> 0.11`) |
| Security Gate | **YELLOW** (echo-only, keine SARIF-Auswertung) |
| Wiki/Produkt | **GREEN** (keine Änderung) |

## 6. Terraform / AWS

- Keine Terraform-/AWS-Operation ausgeführt; keine `.tf`-Änderung.
- Nur gelesen: `terraform/main.tf`, `.terraform.lock.hcl`, Scanner-/Testcode.
- Kein Apply, kein Deployment, keine RIS-Änderung.

## 7. Git

- Basis: `main`/`origin/main` `2ef1fd6`; Worktree clean.
- Dieser Report + Auditlog + Wiki-Hinweis werden als Doku-Commit gepusht.
- Der Push löst erwartungsgemäß nur den bekannten D8-Source-Fail aus
  (kein Build/Plan/Deploy).

## 8. Dateien/Belege

- `security/dependency_detector.py` (`~>`-Zweig)
- `installer/tests/test_installer.py` (`TestDependencyDetector`)
- `terraform/main.tf`, `terraform/.terraform.lock.hcl`
- CodeQL-Run `45651651020`, Dependency-Run `45651651059`,
  Security-Run `45651650996`
- HashiCorp Version Constraints:
  <https://developer.hashicorp.com/terraform/language/expressions/version-constraints>

## 9. Offene Fragen

1. Wird der Scanner-Fehlalarm kurzfristig gefixt (Semantik + Tests + Lock-
   Vergleich) oder zunächst nur dokumentiert?
2. Soll der Security Gate echte SARIF-Findings auswerten und bei
   `error`-Level fehlschlagen? Das wäre eine Verhaltensänderung.
3. Soll der Scanner künftig `.terraform.lock.hcl` als Quelle nutzen (statt
   Registry-Latest gegen Constraint-String)?

## 10. Risiken

- **False-Positive-Rauschen:** Ein `error`-Level-SARIF-Alert für eine gültige
  Lock-Version kann echte Findings verdecken.
- **Falsches Sicherheitsgefühl:** Der Security Gate ist grün, obwohl ein
  error-Level-Finding im SARIF steht.
- **Kein Lock-Drift-Nachweis:** AWS 6.54.0 vs. Lock 6.65.0 wird nicht erkannt.
- **Test-Konservierung:** Die aktuellen Tests zementieren die falsche
  `~>`-Semantik; ein Fix ohne Testanpassung würde fehlschlagen.

## 11. Empfohlene nächste Aktionen

1. Separaten Fix-Auftrag für `version_satisfies_constraint`:
   - `~> X.Y` → `>= X.Y.0, < (X+1).0.0`
   - `~> X.Y.Z` → `>= X.Y.Z, < X.(Y+1).0`
   - Tests für `0.14.2`/`~> 0.11` und `1.2.4`/`~> 1.2.3` korrigieren.
2. Lock-Datei als Vergleichsbasis verwenden (oder `terraform providers`
   auswerten); Registry-Latest nur als Informationsquelle.
3. Security Gate optional um SARIF-/Exit-Auswertung erweitern (separate
   Entscheidung).
4. Nach dem Fix CI erneut ausführen; keine AWS-/Produktionsoperation.

## 12. Resume Point

CI-Audit abgeschlossen. Re-Runs grün; Scanner-Fehlalarm dokumentiert und als
separater Fix empfohlen. Keine Produkt-/AWS-/Terraform-/RIS-Mutation.
