# MO-GH-SEC-01 — GitHub Security Baseline Audit

## 1. Status

**`BASELINE AUDITED / READY FOR REMEDIATION`**

- **Datum:** 2026-11-28
- **Repository:** `maynowak/mays-order-aws` (public)
- **Branch:** `feature/mo-github-security-cleanup-01`
- **HEAD bei Audit-Beginn:** `8830da290e2960c1f319fb0a2b4a6724d00cbafd`
- **Scope:** GitHub Actions, CodeQL/SARIF, Code Scanning, Dependabot,
  Secret Scanning/Push Protection, Dependency Detector, Terraform-/IAM-/
  Python-/Shell-Coverage, Actions-Supply-Chain, Branches/Rulesets,
  Security-Dokumentation
- **Grenzen eingehalten:** keine funktionalen Codeänderungen, keine
  Alert-Dismissals, keine Branch-Löschungen, keine Änderung der GitHub-
  Security-Settings, kein Main-Merge, kein AWS-Deployment, keine
  Terraform-Operation.

**Gesamtklassifikation:** **ORANGE** — Baseline vollständig auditiert;
mehrere hohe Kontroll- und Konfigurationslücken, aber kein Nachweis einer
aktiven Kompromittierung. Remediation ist in MO-GH-SEC-02 bis 10 geschnitten.

## 2. Preflight

- `main` = `origin/main` = `8830da2`; Worktree vor dem Audit clean.
- Feature-Branch `feature/mo-github-security-cleanup-01` von `main` erstellt.
- Geschützte RC4-/RIS-Arbeiten nicht verändert:
  `release/rc4-integration`, `feature/mo-rc4-*`, `feature/mo-ris-*`,
  `fix/mo-ris-*`, `integration/mo-ris-*`, `test/mo-rc4-*`.
- GitHub-Auth: Account `maynowak`, Repo-Admin, Scopes `repo`, `workflow`,
  `read:org`; alle Abfragen read-only.
- Keine offenen PRs (`gh pr list --state open`: 0).

## 3. Durchgeführte Audit-Abschnitte

1. Workflows, Trigger und Berechtigungen inventarisiert.
2. CodeQL-Konfiguration, Kategorien, Analysen und SARIF-Uploads geprüft.
3. Doppelausführung durch `codeql.yml`, `dependency-check.yml`,
   `security.yml` nachgewiesen.
4. Security Gate gegen tatsächliche Findings geprüft.
5. Code-Scanning-Alerts, Dependabot-Alerts, Secret Scanning und
   Push Protection erfasst.
6. Dependency Detector, Versionsmanagement und Vulnerability-Coverage
   analysiert.
7. Terraform-, IAM-, Python- und Shell-Coverage bewertet.
8. Actions-Versionen, SHA-Pinning und Berechtigungen geprüft.
9. Offene PRs, Branches, Rulesets und Branch Protection geprüft.
10. Security-Dokumentation und `SECURITY.md` inventarisiert.
11. Findings, Prioritäten und Arbeitspakete MO-GH-SEC-02 bis 10 abgeleitet.

## 4. Baseline-Snapshot

### 4.1 GitHub Actions / Checks

| Punkt | Befund |
|---|---|
| Workflows | 3: `codeql.yml`, `dependency-check.yml`, `security.yml` |
| Trigger | push/PR `main`, Zeitpläne, `workflow_dispatch`; CodeQL/Dependency zusätzlich `workflow_call` |
| Checks auf `main` | 8/8 `success` |
| Letzte Fehlschläge | nur 2026-11-25 (GitHub-Incident); danach alle Runs grün |
| CodeQL | 143/143 Python-Dateien, 255 Results, 172 Rules; SARIF-Upload complete |
| Dependency-SARIF | Upload complete; 2 Results; Exit 1 wird toleriert |
| Security Gate | `success`, aber echo-only ohne Findings-Auswertung |

### 4.2 Code Scanning / Dependabot / Secret Scanning

| Punkt | Befund |
|---|---|
| Offene Code-Scanning-Alerts | **257** (255 CodeQL + 2 Dependency Detector) |
| Geschlossene Alerts | 74 |
| Dismissed Alerts | 0 |
| Schweregrad | **3 high**, 254 ohne Security-Severity (überwiegend Quality) |
| High-Alerts | #1 `py/clear-text-logging-sensitive-data`; #145/#146 `py/overly-permissive-file`; alle seit 2026-09-20 offen |
| Dependabot-Alerts | 0 |
| Secret-Scanning-Alerts | 0 |
| Push Protection | **enabled** |
| Secret-Scanning-Validity-Checks | **disabled** |
| Non-Provider-Patterns | **disabled** |
| Dependabot Security Updates | enabled |
| `.github/dependabot.yml` | **nicht vorhanden** |

### 4.3 Repository / Actions-Settings

| Punkt | Befund |
|---|---|
| Branch Protection `main` | **nicht vorhanden** (HTTP 404) |
| Rulesets | **keine** (`[]`) |
| Environments | **keine** (`0`) |
| Allowed Actions | `all` |
| SHA-Pinning erforderlich | **nein** (`sha_pinning_required=false`) |
| Default Workflow Token | `read` |
| PR-Review-Freigabe durch Actions | nein |
| Remote-Branches | 27 (inkl. `main`); 15 gemergte Nicht-Main-Branches; 11 unmerged |
| Älteste Branches | 7 Branches vom 2026-08-18 |
| `SECURITY.md` | **nicht vorhanden** |
| `.github/CODEOWNERS` | **nicht vorhanden** |

### 4.4 Coverage

| Bereich | Abdeckung |
|---|---|
| Python SAST | CodeQL `security-and-quality` (143 Dateien) |
| Terraform/IaC SAST | **keine** in GitHub Actions (kein Checkov/tfsec/Trivy) |
| IAM-Analyse | nur lokaler Policy Gate (`terraform/policy/validate-plan.py`) beim Installer-Plan; **nicht in CI** |
| Shell | 1 Script (`scripts/test_plan.sh`), **kein ShellCheck** |
| Dependency-Vulnerabilities | **keine** CVE-/Advisory-Prüfung; Detector prüft nur Terraform-Provider-Versionen |
| Actions-Supply-Chain | Tags statt SHA; kein actionlint/zizmor |
| Secret-Scanning in CI | nur GitHub-Plattform; kein gitleaks/trufflehog |
| Container/SBOM | keine Container; kein SBOM |

## 5. Findings

### 5.1 Scanner- und CI-Konfigurationsfehler

#### GH-SEC-01 — Doppelte CodeQL-Ausführung mit identischer Kategorie

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-02
- **Kategorie:** Scanner-/CI-Konfiguration
- **Ursache/Evidence:** `codeql.yml` triggert push/PR/schedule und wird
  zusätzlich von `security.yml` per `workflow_call` aufgerufen. Auf
  `8830da2` existieren **zwei CodeQL-Analysen** mit identischer Kategorie
  `/language:python` (IDs `2249689085`/`2249688916`, je 255 Results) sowie
  zwei Check-Runs (`Analyze (python)` und
  `CodeQL Analysis / Analyze (python)`). Die GitHub-API zeigt kein
  `error`-Feld in den Analysen; der reproduzierbare Konfigurationsdefekt ist
  die doppelte Analyse mit gleicher Kategorie — die konkrete Ursache für
  Doppel-Uploads/Alert-Churn und den wahrscheinlichen „Configuration
  Error“-Hinweis.
- **Korrektur:** Einen Orchestrator wählen (entweder Standalone-Workflows
  **oder** `security.yml` als einzigen Aufrufer), doppelte Trigger entfernen,
  `concurrency` ergänzen, Kategorie eindeutig halten.
- **Komponenten:** `.github/workflows/codeql.yml`,
  `.github/workflows/security.yml`

#### GH-SEC-02 — Doppelte Dependency-Ausführung und überlappende Zeitpläne

- **Severity:** Medium · **Priorität:** P1 · **WP:** MO-GH-SEC-02
- **Kategorie:** Scanner-/CI-Konfiguration
- **Ursache/Evidence:** `dependency-check.yml` läuft täglich um 06:00 UTC und
  wird zusätzlich von `security.yml` (montags 03:00 UTC) aufgerufen; bei
  push/PR laufen beide Wege. Auf `8830da2` existieren zwei Dependency-Check-
  Runs (`Dependency Change Detection` und
  `Security & Dependency Analysis / Dependency Change Detection`).
- **Korrektur:** Wie GH-SEC-01; zusätzlich Zeitpläne konsolidieren,
  `paths-ignore` für reine Doku-Änderungen prüfen.
- **Komponenten:** `.github/workflows/dependency-check.yml`,
  `.github/workflows/security.yml`

#### GH-SEC-03 — Security Gate ist echo-only und prüft keine Findings

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-03
- **Kategorie:** Scanner-/CI-Konfiguration
- **Ursache/Evidence:** `security.yml:35-50` führt nur `echo`-Schritte aus.
  Der Gate ist grün, obwohl 257 Alerts (3 high) offen sind. Es gibt keine
  API-Abfrage, keine SARIF-Auswertung und keinen Fail bei High/Critical.
- **Korrektur:** Code-Scanning-Alerts/SARIF auswerten; bei High/Critical
  fehlschlagen; Findings-Schwellen und Ausnahmen dokumentieren; Gate mit
  synthetischem Finding testen.
- **Komponenten:** `.github/workflows/security.yml`

#### GH-SEC-04 — Dependency-SARIF: absolute Pfade, Kategorie-Mismatch und stale Alerts

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-04
- **Kategorie:** Scanner-/CI-Konfiguration
- **Ursache/Evidence:**
  - `security/dependency_detector.py:294-302` nutzt `Path(__file__).resolve()`
    und `source=str(tf_file)`; die SARIF-Locations sind absolut
    (`/home/runner/work/.../terraform/main.tf`). Code Scanning erwartet
    repo-relative URIs.
  - `security/sarif_adapter.py` setzt `automationDetails.id =
    security-01-dependency-check`; der Workflow setzt
    `category: dependency-check`; die Analyses-API zeigt Kategorie `""`.
  - Es fehlen `partialFingerprints`; `CURRENT`-Status wird als `note`-Result
    hochgeladen (Alert #298 „time is current“).
  - Alert #296 (AWS `CONSTRAINT_UNSATISFIED`, Message `5.92.0`) wurde zuletzt
    am 2026-11-22 aktualisiert, obwohl danach weitere Dependency-Analysen
    liefen; #298 wurde am 2026-11-27 aktualisiert. Die Alerts spiegeln den
    aktuellen Detector-Output nicht konsistent.
- **Korrektur:** Repo-relative URIs; Kategorie/Automation-ID vereinheitlichen;
  `partialFingerprints` ergänzen; nur echte Findings (nicht `CURRENT`)
  hochladen; Alerts nach Re-Upload verifizieren.
- **Komponenten:** `security/dependency_detector.py`,
  `security/sarif_adapter.py`, `.github/workflows/dependency-check.yml`

#### GH-SEC-05 — `~>`-Semantik im Dependency Detector falsch; Tests zementieren den Fehler

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-04
- **Kategorie:** Scanner-/CI-Konfiguration
- **Ursache/Evidence:** `security/dependency_detector.py:106-115` behandelt
  `~> 0.11` wie `<0.12` und `~> 1.2.3` wie `<1.2.4`. Terraform erlaubt bei
  `~> 1.1` auch `1.2`/`1.10` (nicht `2.0`) und bei `~> 1.0.4` auch
  `1.0.5`/`1.0.10` (nicht `1.1.0`). `terraform/.terraform.lock.hcl:28-30`
  hat `time 0.14.2` unter `~> 0.11` — gültig, aber der Scanner meldet
  `CONSTRAINT_UNSATISFIED`.
  Die Tests `installer/tests/test_installer.py:1408` und `:1410` erwarten
  fälschlich `False` für `1.3.0`/`~> 1.2` bzw. `1.2.4`/`~> 1.2.3`; die
  9 fokussierten Tests laufen deshalb grün, obwohl die Semantik falsch ist.
- **Korrektur:** `~>` korrekt implementieren (`~> X.Y` → `>=X.Y.0, <(X+1).0.0`;
  `~> X.Y.Z` → `>=X.Y.Z, <X.(Y+1).0`); Tests korrigieren; Regressionstests
  für `0.14.2`/`~> 0.11` und `1.2.4`/`~> 1.2.3`.
- **Komponenten:** `security/dependency_detector.py`,
  `installer/tests/test_installer.py`

#### GH-SEC-06 — „Latest“-Ermittlung unsortiert/nicht deterministisch; Lock-Datei wird ignoriert

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-04
- **Kategorie:** Scanner-/CI-Konfiguration
- **Ursache/Evidence:** `security/dependency_detector.py:208-216` nimmt
  `stable_versions[0]` ohne semantische Sortierung. Beobachtete AWS-Werte:
  `5.92.0` (Alert #296), `6.54.0` (früherer Lauf), `3.24.1` (aktueller Lauf);
  Lock ist `6.65.0`. Der Scanner liest `.terraform.lock.hcl` nicht und
  vergleicht Registry-Werte gegen den Constraint-String
  (`compare_versions("3.24.1", ">= 6.0")` → Parse-Fehler → 0). Zusätzlich
  notiert die Lock-Datei für AWS `constraints = "~> 6.0"`, während
  `terraform/main.tf:7` `>= 6.0` deklariert — ein minor Drift.
- **Korrektur:** Semver-sortieren; Lock-Version als Quelle nutzen; Constraint
  gegen Lock prüfen; Registry-Latest nur informativ; Drift zwischen
  `main.tf` und Lock bereinigen.
- **Komponenten:** `security/dependency_detector.py`,
  `terraform/.terraform.lock.hcl`, `terraform/main.tf`

#### GH-SEC-07 — Kein Dependabot-Konfigurationsfile; keine automatischen Updates

- **Severity:** Medium · **Priorität:** P1 · **WP:** MO-GH-SEC-05
- **Kategorie:** Fehlende Abdeckung
- **Ursache/Evidence:** `.github/dependabot.yml` fehlt. Dependabot Security
  Updates sind zwar repo-weit enabled, aber es gibt keine Version-Updates für
  Actions, Terraform-Provider oder Python. 0 offene Dependabot-Alerts sind
  daher **kein** Nachweis von Coverage.
- **Korrektur:** Dependabot für `github-actions`, `terraform` und ggf.
  `pip` konfigurieren; Update-Strategie und Reviewer festlegen.
- **Komponenten:** `.github/dependabot.yml` (neu)

#### GH-SEC-08 — CodeQL-Rauschen: Tests/Doku, 255 Results, keine Triage

- **Severity:** Medium · **Priorität:** P1 · **WP:** MO-GH-SEC-06
- **Kategorie:** Scanner-/CI-Konfiguration
- **Ursache/Evidence:** CodeQL scannt alle Python-Dateien inkl. Tests
  (255 Results, 172 Rules); 254 der 257 offenen Alerts haben keine
  Security-Severity (überwiegend `py/unused-import`,
  `py/unused-local-variable`, `py/repeated-import`). Es gibt kein
  `codeql-config.yml`, keine `paths-ignore` für Doku, keine dokumentierte
  Triage-/Dismissal-Policy. Doku-Pushes lösen vollständige Scans aus.
- **Korrektur:** Query-Suite/Paths prüfen; Tests ggf. ausnehmen oder
  Quality-Findings separat behandeln; Triage-Prozess dokumentieren;
  Doku-Pfade ignorieren.
- **Komponenten:** `.github/workflows/codeql.yml`, Code-Scanning-Triage

#### GH-SEC-09 — Actions nicht SHA-gepinnt; alle Actions erlaubt; kein Workflow-Lint

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-07
- **Kategorie:** Supply Chain
- **Ursache/Evidence:** Alle `uses:` verwenden Major-Tags
  (`actions/checkout@v4`, `actions/setup-python@v5`,
  `actions/upload-artifact@v4`, `github/codeql-action/*@v4`). Repo-Settings:
  `allowed_actions=all`, `sha_pinning_required=false`. Kein actionlint/zizmor.
  `security.yml:21,26` nutzt `secrets: inherit`; `actions/checkout` nutzt
  default `persist-credentials: true`.
- **Korrektur:** Alle Actions auf volle SHA pinnen (Kommentar mit Version);
  `sha_pinning_required`/Allowed-Actions restriktiver; `secrets: inherit`
  entfernen, wenn ungenutzt; `persist-credentials: false`; actionlint/zizmor
  als CI-Job.
- **Komponenten:** alle drei Workflows, Repo-Actions-Settings

#### GH-SEC-10 — Keine `concurrency`/Timeouts; überlappende Runs möglich

- **Severity:** Low · **Priorität:** P2 · **WP:** MO-GH-SEC-02
- **Kategorie:** Scanner-/CI-Konfiguration
- **Ursache/Evidence:** Keiner der Workflows definiert `concurrency` oder
  `timeout-minutes`; bei push/PR/Schedule können mehrere identische Scans
  parallel laufen (siehe GH-SEC-01/02).
- **Korrektur:** `concurrency` pro Workflow/Ref; realistische Timeouts.
- **Komponenten:** alle drei Workflows

### 5.2 Governance und echte/hoch priorisierte Risiken

#### GH-SEC-11 — `main` ist ungeschützt; keine Rulesets, Required Checks oder Reviews

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-08
- **Kategorie:** Governance / Kontrolllücke
- **Ursache/Evidence:** `GET branches/main/protection` → HTTP 404
  („Branch not protected“); `GET rulesets` → `[]`; keine Environments.
  Das öffentliche Repo erlaubt direkte Pushes auf `main`; es gibt keine
  Required Status Checks, keine Review-Pflicht, keinen Force-Push-/Delete-
  Schutz.
- **Korrektur:** Ruleset/Branch Protection für `main`: PR-Pflicht,
  Required Checks (CodeQL, Security Gate, Tests), mindestens 1 Review,
  Force-Push/Deletion blockieren, Admin-Bypass dokumentieren; ggf.
  Signed Commits.
- **Komponenten:** GitHub Repo Settings/Rulesets

#### GH-SEC-12 — Kein `SECURITY.md`, kein `CODEOWNERS`

- **Severity:** Medium · **Priorität:** P1 · **WP:** MO-GH-SEC-08
- **Kategorie:** Governance / Dokumentation
- **Ursache/Evidence:** `SECURITY.md` und `.github/CODEOWNERS` fehlen.
  Security-Dokumentation existiert verteilt (`security/`,
  `docs/security/`, `docs/features/F009-iam-security.md`, Reports), aber
  ohne zentrale Vulnerability-Disclosure-/Ownership-Regel.
- **Korrektur:** `SECURITY.md` mit Meldeweg, Scope, SLA; `CODEOWNERS` für
  Security-kritische Pfade (`terraform/`, `lambda/`, `installer/`,
  `.github/`, `security/`).
- **Komponenten:** `SECURITY.md`, `.github/CODEOWNERS` (neu)

#### GH-SEC-13 — Secret-Scanning-Härtung unvollständig; kein CI-Secret-Scan

- **Severity:** Medium · **Priorität:** P1 · **WP:** MO-GH-SEC-09
- **Kategorie:** Fehlende Abdeckung / Konfiguration
- **Ursache/Evidence:** Secret Scanning und Push Protection sind enabled,
  aber `secret_scanning_validity_checks=disabled` und
  `secret_scanning_non_provider_patterns=disabled`; 0 offene Alerts.
  Es gibt keinen gitleaks/trufflehog-Job in CI.
- **Korrektur:** Validity Checks und Non-Provider-Patterns aktivieren;
  CI-Secret-Scan (z. B. gitleaks) ergänzen; Ausnahmen dokumentieren.
- **Komponenten:** GitHub Secret-Scanning-Settings, CI

#### GH-SEC-14 — Drei High-Alerts seit 2026-09-20 offen und untriaged

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-06
- **Kategorie:** Echte/hoch priorisierte Findings (ungeprüft)
- **Ursache/Evidence:**
  - #1 `py/clear-text-logging-sensitive-data`,
    `terraform/policy/validate-plan.py:465` — Logging von Fehlertexten, die
    Policy-Details enthalten können; potenziell sensibel, aber kein
    nachgewiesener Credential-Leak.
  - #145 `py/overly-permissive-file`,
    `installer/core/atomic_ops.py:383` — `os.open(..., 0o644)`.
  - #146 `py/overly-permissive-file`,
    `installer/core/lock_manager.py:122` — `os.open(..., 0o644)`.
  Alle drei sind seit 2026-09-20 offen, ohne Update/Triage.
- **Korrektur:** Einzeln triagieren: #145/#146 auf `0o600` prüfen (Lock-/
  State-Dateien), #1 Kontext prüfen (Policy-Details vs. Credentials);
  Fix oder begründete Dismissal mit Review; keine pauschale Dismissal.
- **Komponenten:** `installer/core/atomic_ops.py`,
  `installer/core/lock_manager.py`, `terraform/policy/validate-plan.py`

### 5.3 Fehlende Abdeckung

#### GH-SEC-15 — Keine IaC-/IAM-/Shell-/Container-/SBOM-Scans; Policy Gate nur lokal

- **Severity:** High · **Priorität:** P0 · **WP:** MO-GH-SEC-10
- **Kategorie:** Fehlende Abdeckung
- **Ursache/Evidence:** Kein Checkov/tfsec/Trivy, kein IAM-Analyzer, kein
  ShellCheck, kein Container-Scan, kein SBOM. `terraform/policy/
  validate-plan.py` prüft u. a. Wildcard-IAM-Actions und Secrets/KMS-
  Wildcard-Ressourcen, läuft aber nur im Installer-Plan/Apply, nicht in
  GitHub Actions. CodeQL scannt kein HCL und keine Shell.
- **Korrektur:** IaC-Scanner (Checkov/tfsec/Trivy) für Terraform;
  ShellCheck; Policy Gate als CI-Job; IAM-Policy-Analyse; SBOM bei Bedarf;
  Container-Scan nur falls Container eingeführt werden.
- **Komponenten:** `terraform/`, `scripts/`, `.github/workflows/`,
  `terraform/policy/`

#### GH-SEC-16 — Keine Dependency-Vulnerability-Prüfung (Python/Actions)

- **Severity:** Medium · **Priorität:** P1 · **WP:** MO-GH-SEC-05
- **Kategorie:** Fehlende Abdeckung
- **Ursache/Evidence:** Kein `pip-audit`, `safety`, `npm audit` oder
  Advisory-Scan; der Dependency Detector prüft nur Terraform-Provider-
  Versionen, keine CVEs. Es gibt keine `requirements.txt`/`pyproject.toml`;
  Lambda nutzt Runtime-`boto3`. Actions-Versionen werden nicht auf
  Vulnerabilities geprüft.
- **Korrektur:** Dependabot/Advisory-Scan für vorhandene Ökosysteme;
  `pip-audit` nur bei echten Python-Abhängigkeiten; Actions-SHA-Pinning +
  Dependabot; dokumentieren, was runtime-provided ist.
- **Komponenten:** Dependency-Management, CI

#### GH-SEC-17 — 257 offene Alerts ohne Triage-/Dismissal-Policy

- **Severity:** Medium · **Priorität:** P1 · **WP:** MO-GH-SEC-06
- **Kategorie:** Veraltete Findings / Prozess
- **Ursache/Evidence:** 257 offen, 74 geschlossen, 0 dismissed; 255 CodeQL-
  Alerts überwiegend Quality; 2 Dependency-Alerts stale (siehe GH-SEC-04).
  Kein dokumentierter Triage-Prozess, keine Owner, keine Fristen.
- **Korrektur:** Triage-Board/Policy; High zuerst; Quality-Findings
  kategorisieren; Fixed-Alerts automatisch schließen lassen; keine
  pauschalen Dismissals.
- **Komponenten:** Code-Scanning-Prozess

#### GH-SEC-18 — 27 Remote-Branches, davon 15 gemergt und 7 aus August

- **Severity:** Low · **Priorität:** P2 · **WP:** MO-GH-SEC-08
- **Kategorie:** Hygiene / Governance
- **Ursache/Evidence:** 27 Remote-Branches inkl. `main`; 15 gemergte
  Nicht-Main-Branches; 11 unmerged; 7 Branches vom 2026-08-18
  (`feature/cognito`, `feature/http-api`, `feature/lambda-python-314`,
  `feature/lambda-python-cleanup`, `feature/t011-07-plan-review`,
  `feature/presentation-qa`, `feature/lambda-runtime-doc-cleanup`).
- **Korrektur:** Nach Freigabe gemergte Branches löschen; unmerged Branches
  owner-seitig prüfen; Branch-Namens-/Lifecycle-Policy dokumentieren.
  **Keine Löschung in diesem Audit.**
- **Komponenten:** Git-Branches

## 6. Klassifikation

| Bereich | Status | Begründung |
|---|---|---|
| CodeQL/SARIF-Ausführung | **GREEN** | 143/143 Dateien; Uploads complete; Checks success |
| GitHub Actions Stabilität | **GREEN** | Letzte Fehler nur Incident 2026-11-25; danach grün |
| Dependency Detector | **RED** | `~>`-Bug, unsortierte Latest-Ermittlung, Lock ignoriert, stale Alerts |
| Security Gate | **RED** | echo-only; grün trotz 257 Alerts / 3 high |
| Code-Scanning-Alerts | **ORANGE** | 3 high seit September offen; 257 untriaged |
| Branch-/Repo-Governance | **RED** | `main` ungeschützt; keine Rulesets/Required Checks |
| Actions Supply Chain | **ORANGE** | Tags statt SHA; alle Actions erlaubt |
| Secret Scanning | **YELLOW** | Push Protection an; Validity/Non-Provider aus |
| Dependabot | **YELLOW** | 0 Alerts, aber keine Config/Version-Updates |
| Coverage Terraform/IAM/Shell | **RED** | Keine CI-SAST; Policy Gate nur lokal |
| Dokumentation | **YELLOW** | Viele Security-Docs, aber kein `SECURITY.md`/`CODEOWNERS` |
| **Gesamt** | **ORANGE** | Baseline auditiert; hohe Lücken, keine Kompromittierung belegt |

## 7. Terraform / AWS

- **Keine** Terraform-Kommandos ausgeführt (`init`, `validate`, `plan`,
  `apply` fanden nicht statt).
- **Keine** AWS-Operation; keine Credentials verwendet; kein Deployment.
- Nur gelesen: `terraform/main.tf`, `terraform/.terraform.lock.hcl`,
  `terraform/policy/validate-plan.py`, `terraform/policy/resource-policy.json`.

## 8. Git

- Audit-Branch: `feature/mo-github-security-cleanup-01`, basierend auf
  `main`/`origin/main` `8830da2`.
- Geänderte Dateien: dieser Report, `docs/AI_AUDITLOG.md`,
  `docs/PROJECT_STATUS.md` (Doku only).
- Keine Code-, Workflow-, Terraform-, IAM- oder Security-Setting-Änderung.
- Checkpoint: `git diff --check` → Secret-Audit → Commit → Push
  Feature-Branch; **kein** Main-Merge.

## 9. Offene Fragen

1. Soll `security.yml` der einzige Orchestrator sein, oder bleiben
   Standalone-Workflows mit entfernten `workflow_call`-Aufrufen?
2. Soll der Security Gate bei High/Critical **fehlschlagen** oder nur
   reporten? Werden Ausnahmen/Suppressions zugelassen?
3. Soll CodeQL Tests ausschließen oder Quality-Findings separat behandeln?
4. Soll der Dependency-Detector vor der Gate-Härtung repariert werden
   (empfohlen: WP04 vor WP03)?
5. Welche Branch-Protection-Anforderungen sind realistisch (Required Checks,
   Reviews, Admin-Bypass)?
6. Soll Dependabot Terraform/Actions/Python verwalten; gibt es bewusst keine
   Python-Manifeste?
7. Sollen Secret-Scanning-Validity-Checks und Non-Provider-Patterns aktiviert
   werden?
8. Werden die 3 High-Alerts gefixt oder begründet dismissed; wer ist Owner?

## 10. Risiken

- **Falsches Sicherheitsgefühl:** Grüner Security Gate bei 257 offenen Alerts.
- **False-Positive-Rauschen:** Dependency-Detector meldet gültige
  Lock-Versionen; stale Alerts verdecken echte Findings.
- **Supply-Chain:** Mutable Action-Tags und `allowed_actions=all`.
- **Unprotected Main:** Direkte Pushes/Force-Push auf öffentlichem Repo.
- **Fehlende IaC-Abdeckung:** Terraform-/IAM-Fehler werden in PRs nicht
  automatisch erkannt.
- **Alert-Fatigue:** 255 CodeQL-Results, überwiegend Quality, ohne Triage.
- **Kein Disclosure-Prozess:** Externe Sicherheitsmeldungen haben keinen
  dokumentierten Weg.

## 11. Arbeitspakete MO-GH-SEC-02 bis 10

| WP | Scope | Findings | Exit-Kriterien |
|---|---|---|---|
| **MO-GH-SEC-02** | CI-Orchestrierung konsolidieren | 01, 02, 10 | Genau ein CodeQL-/Dependency-Lauf pro Event; keine Doppel-Check-Runs; `concurrency`/Timeouts; `paths-ignore` für Doku |
| **MO-GH-SEC-03** | Security Gate erzwingen | 03 | Gate liest Code-Scanning-Alerts/SARIF; High/Critical → FAIL; synthetischer Test; dokumentierte Schwellen |
| **MO-GH-SEC-04** | Dependency Detector/SARIF reparieren | 04, 05, 06 | `~>` korrekt; Tests korrigiert; Semver-Sortierung; Lock-Vergleich; relative URIs; Kategorie/Fingerprints; keine `CURRENT`-Results; Alerts konsistent |
| **MO-GH-SEC-05** | Dependency-/Vulnerability-Management | 07, 16 | Dependabot-Config für Actions/Terraform/Python; Advisory-Scan; dokumentierte Runtime-Ausnahmen |
| **MO-GH-SEC-06** | CodeQL-Triage/Qualität | 08, 14, 17 | 3 High triagiert/gefixt; Triage-Policy; Quality-Findings klassifiziert; Doku-Pfade ignoriert |
| **MO-GH-SEC-07** | Actions-Supply-Chain | 09 | Alle Actions SHA-gepinnt; Allowed-Actions restriktiv; `secrets: inherit` entfernt; `persist-credentials: false`; actionlint/zizmor |
| **MO-GH-SEC-08** | Repo-Governance | 11, 12, 18 | Ruleset/Branch Protection; Required Checks/Review; `SECURITY.md`; `CODEOWNERS`; Environments; Branch-Cleanup nach Freigabe |
| **MO-GH-SEC-09** | Secret-Scanning-Härtung | 13 | Validity Checks/Non-Provider-Patterns an; CI-Secret-Scan; Push Protection dokumentiert |
| **MO-GH-SEC-10** | IaC-/IAM-/Shell-/SBOM-Coverage | 15 | Checkov/tfsec/Trivy für Terraform; ShellCheck; Policy Gate in CI; IAM-Analyse; SBOM-Entscheidung |

**Empfohlene Reihenfolge:** WP04 (Detector/SARIF) → WP02 (Orchestrierung) →
WP03 (Gate) → WP07/WP08 (Supply Chain/Governance) → WP06 (Triage) →
WP05/WP09/WP10 (Coverage/Härtung).

## 12. Resume Point

- Audit abgeschlossen; Report und Auditlog werden auf
  `feature/mo-github-security-cleanup-01` committet und gepusht.
- Nächster Schritt: **MO-GH-SEC-04** (Dependency Detector/SARIF) oder
  **MO-GH-SEC-02** (CI-Orchestrierung) nach Freigabe.
- Keine Änderung an `main`, keine Alert-Dismissals, keine Branch-Löschungen,
  keine GitHub-Security-Settings-Änderung, kein AWS-/Terraform-Einsatz.
