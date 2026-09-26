# Detaillierter Bericht: CI/CD Source, INSTALLER-LIFECYCLE, Parametrisierte Tests & Parallele Laufzeiten

**Erstellt:** 2026-09-26  
**Bezug:** AI_AUDITLOG.md – Execution Logs in `docs/reports/[NO.]-[TASK]-EXECUTION_LOG.md`  
**Umfang:** CI/CD Source & Aktivitäten, Dokumentation, Parametrisierte Tests, INSTALLER-LIFECYCLE, Upgrader/Parallel Runtime

---

## 1. CI/CD Source & Aktivitäten

### 1.1 Architekturübersicht

Pipeline basierend auf `docs/reports/INSTALLER-D8-CICD.md` und `docs/reports/CI-REPOSITORY-BOOTSTRAP-01.md`.

**Source:**
- GitHub Repository `maynowak/mays-order-aws`, Branch `main`
- CodePipeline Source Action `GitHub v1`
- OAuthToken aus Secrets Manager `github-token-xxxxx` → fine-grained PAT
- Artifact Format `CODE_ZIP`

**Stufen:**
1. **Validate** – CodeBuild `ci/buildspecs/validate.yml`
   - AWS Identity Resolution via STS
   - Account/Region/Project/Environment Validation
   - Terraform Validate, Unit Tests, Code Quality
   - Read-Only, keine Mutation

2. **Plan** – CodeBuild `ci/buildspecs/plan.yml`
   - Verbraucht `source_output` + `validate_output` mit `deployment_context.json`
   - Terraform Plan via Installer, erzeugt Plan mit H2 Identity
   - Artefakte: `.tfplan`, `.meta.json`, `.context.json`

3. **Approval** – Manual
   - Exponiert Project, Env, Account, Region, DeploymentId, Version, Phase/Step, Plan Seq, Safety, Policy

4. **Deploy** – CodeBuild `ci/buildspecs/deploy.yml`
   - Validiert DeploymentId + Plan Identity + Plan Integrity
   - Safety Analysis + Policy Gate
   - Wendet exaktes gespeichertes Plan an, nie neu generieren

5. **Verify** – CodeBuild `ci/buildspecs/verify.yml`
   - Read-Only Post-Deploy Checks

**Destroy Path separat:** Plan-Destroy → Safety → Approval → Destroy → Verify

### 1.2 Source Auth Problematik

**Quelle:** `docs/reports/GITHUB-AUTH-CI-INTEGRATION-01.md` vom 2026-09-22

**Klassifikation:** C) PAT_REQUIRED_FOR_SOURCE

**Befund:**
- CodePipeline Source Action benötigt gültigen GitHub fine-grained PAT
- Aktuelles Token invalid/revoked → Source Stage Fail mit `PermissionError: Could not access GitHub repository`
- Kaskadierender Fehler: Kein `source_output` → Plan Stage `YAML_FILE_ERROR: plan.yml not found`
- Validate Stage von vorherigem erfolgreichen Run beweist Downstream-Funktionalität

**Least Privilege:**
- PAT mit `repo:read` ausreichend
- Secret Access nur Pipeline Rolle, CodeBuild braucht es nicht

**Empfehlung:**
```bash
aws secretsmanager put-secret-value --secret-id github-token-xxxxx --secret-string "ghp_..."
aws codepipeline start-pipeline-execution --name mays-orders-development-ci-cd
```

### 1.3 Repository Bootstrap

**Quelle:** `docs/reports/CI-REPOSITORY-BOOTSTRAP-01.md` vom 2026-09-21

**Status:** COMPLETED — 10/10 Checks PASS

**Validierung:**
- Repository Root Detection
- Installer importierbar
- Alle 6 Buildspecs existieren und rufen Installer auf
- Terraform Verzeichnis vorhanden
- Pipeline Terraform referenziert korrekte Buildspec Pfade
- Keine direkte Terraform Umgehung

**Installer Authority:** Alle Buildspecs rufen `python3 -m installer.cli.main <command>` auf. Kein zweiter Deployment Pfad.

---

## 2. Dokumentation Status

### 2.1 INSTALLER-LIFECYCLE.md

**Umfang:** D0-D5 Foundation + D6-D8

**Abschnitte:**
- **D0 Discovery:** Inventory Python, Terraform, CLI, Docs, Tests
- **D1 Validation:** Pre-flight Checks AWS Profile, Identity, Account, Region, Terraform CLI/Version, Config
- **D2 Terraform Init:** Controlled Init mit Backend Option
- **D3 Terraform Validate:** Syntax/Reference Validation
- **D4 Deploy Plan:** Plan Generation, JSON Output, PlanResult Struktur
- **D5 Destroy Plan:** Destroy Plan Generation
- **D6 Approve & Apply:** Deploy/Destroy Commands mit Approval Gate, Safety Evaluation, Policy Gate
- **D7 Safety Gate Integration:** Policy Gate vor Mutation, Tests 100/100
- **H1 Security & Execution Hardening:** AWS Execution Boundary, Mutation Boundary, --yes Verhalten, Dry-Run, Plan Integrity, Policy Gate, Destroy Safety, Credentials, State Commands
- **H2 Versioned Deployment Identity:** DeploymentId `<account>:<project>:<environment>`, Versioned State, Plan Identity Filename Schema, Plan Discovery, Destroy Isolation, AWS Tagging, OwnershipAnalyzer
- **D8 CI/CD Deployment Pipeline:** CodePipeline 6 Stages, IAM Role Separation, Plan Artifact Identity, Verify Stage, Destroy Path, Tagging

**Aktualität:** Dokumentation beschreibt Terraform Workspace Isolation nicht explizit für parallele Deployments → siehe `09-05-DOCUMENTATION-REVIEW-EXECUTION_LOG.md` Klassifikation YELLOW.

### 2.2 Offene Dokumentationslücken

Aus `09-05-DOCUMENTATION-REVIEW-EXECUTION_LOG.md` 2026-09-26:
- `docs/INSTALLER-LIFECYCLE.md` Section H2 erwähnt Deployment Identity, aber nicht explizit Terraform Workspace Auto-Selection per `project_name`
- Architektur Dokumentation beschreibt kein Parallel Deployment Isolation Mechanismus
- `docs/PROJECT_STATUS.md` muss Upgrader Parallel Support reflektieren

**Gefordert:**
- Hinweis zu Terraform Workspace Auto-Selection in H2
- Architektur Note zu Workspace Isolation
- Projekt Status Update

---

## 3. Parametrisierte Tests

### 3.1 State Machine Tests

**Quelle:** `lambda/tests/test_state_machine.py`

Parametrisierung via `unittest.subTest`:

```python
ALLOWED = [("PENDING","CONFIRMED"), ...]
for from_status, to_status in ALLOWED:
    with self.subTest(from_status=from_status, to_status=to_status):
        self.assertTrue(can_transition(...))
```

Disallowed, Terminal States, Same Status ebenfalls subTest parametrisiert.

**Coverage:**
- 6 erlaubte Transitionen
- 6 verbotene Transitionen
- Terminal States DELIVERED/CANCELLED × alle Statuses
- Same Status Rejection

**Vorteil:** Ein Testmethod, viele Fälle, klare Fehlerzuordnung pro SubTest.

### 3.2 E2E Async Order Tests

**Quelle:** `tests/test_e2e_async_order.py`

Kein echter Parametrisierung, aber Environment-basierte Konfiguration:
- `API_BASE_URL`, `TEST_USER_EMAIL`, `TEST_USER_PASSWORD`, `COGNITO_CLIENT_ID`, `SQS_QUEUE_URL` aus Env
- Test Suite:
  - `test_01_post_order_sends_to_sqs` — POST erzeugt Order + SQS
  - `test_02_order_eventually_confirmed` — Polling bis CONFIRMED
  - `test_03_verify_order_data_integrity` — Datenintaktheit
  - `test_sqs_message_processed` — SQS Queue leer

**Problem:** Tests hard-coded auf `mays-orders`. Ausführung mit anderem `project_name` nicht parametrisiert.

Aus `09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG.md`:
> Tests hard-coded to `mays-orders` → parallel test may fail if project name changes
> Risiko YELLOW

**Empfehlung:** Parametrisierung via `PROJECT_NAME` Env Var und dynamische API/SQS URLs.

---

## 4. INSTALLER-LIFECYCLE & Upgrader & Parallele Laufzeiten

### 4.1 INSTALLER-LIFECYCLE – Aktueller Stand

**Milestones:**
- D0-D5 ✅ Complete
- D6 Apply ✅ Implemented
- D7 Safety ✅ Completed
- H1 Hardening ✅ Completed
- H2 Deployment Identity ✅ Completed
- D8 CI/CD ✅ Completed

**Sicherheitsgrenzen:**
- Mutation Boundary: VALIDATION → PLAN → SAFETY → POLICY GATE → APPROVAL → SAVED PLAN → APPLY → VERIFY
- --yes skippt nur interaktiven Approval, nicht Validierung/Safety/Policy
- Plan Integrity: File vorhanden, Run-Zugehörigkeit, Kontext Match

### 4.2 Upgrader Parallel Deployment Fix

**Quelle:** `09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG.md` 2026-09-26

**Problem:**
- Installer wählte Terraform Workspace nicht pro `project_name`
- `InstallationContext.terraform_workspace` defaultete auf `default`
- `TerraformRunner` kannte kein Project Workspace → State Kollisionen

**Änderungen:**
- `installer/core/context.py`: `InstallationContext.__post_init__` setzt `terraform_workspace` = `project_name` falls default, exportiert `TERRAFORM_WORKSPACE` Env Var
- `installer/terraform/runner.py`: `TerraformRunner.__init__` liest `TERRAFORM_WORKSPACE` Env Override
- `run_and_get_result` selektiert Workspace vor jedem Command, erstellt bei Bedarf

**Verifikation:** Parallel Projects `mays-orders` und `mays-order-par` koexistieren mit separatem Terraform State.

**Klassifikation:** GREEN

### 4.3 Parallele Laufzeiten – Testberichte

#### 09-01-PARALLEL-PROJECT-TEST
**Datum:** 2026-09-25 18:35 UTC
**Klassifikation:** GREEN

- Collision Assessment: `var.project_name` treibt Resource Namen
- Installer CLI `--project-name` propagiert nicht automatisch → Risiko
- Workspace Isolation Test erfolgreich:
  - `terraform workspace new mays-order-par` SUCCESS
  - Plan 37 to add, 0 change
  - Apply SUCCESS
  - Beide Projekte sichtbar in DynamoDB
  - Destroy SUCCESS, Workspace gelöscht
  - Default Workspace State intakt
- Default Infrastruktur Health: API GW `uq4ctntqp6`, SQS, Worker, Event Source Mapping ENABLED

**Risiken:**
- RED: Destroy default Projekt entfernt Ressourcen Account 240571105849
- YELLOW: Installer propagiert `--project-name` nicht
- YELLOW: Tests hard-coded

#### 09-02-PARALLEL-INSTALLER-UPGRADE
**Datum:** 2026-09-25 20:XX UTC
**Klassifikation:** GREEN

- Policy Gate vorher hard-coded `mays-orders` → jetzt Projekt aus Resource Tags abgeleitet
- Installer `_cmd_plan` auto-inject `project_name`
- Beide Projekte deployed, 37 Ressourcen je Projekt
- DynamoDB Tabellen `mays-orders` und `mays-order-par` parallel
- Beide zerstört, State leer

#### 09-03-FULL-PARALLEL-INSTALLER-AUDIT
**Datum:** 2026-09-26 07:XX UTC
**Klassifikation:** GREEN

- Infrastruktur mit ONLY Installer erstellt:
  - `mays-orders`: API https://23r27t1r96.execute-api.eu-central-1.amazonaws.com, DynamoDB `mays-orders`
  - `mays-order-par`: API https://toa785i52l.execute-api.eu-central-1.amazonaws.com, DynamoDB `mays-order-par`
- Tests `test_01_post_order_sends_to_sqs` PASSED für beide
- Keine Kollisionen
- Beide Infrastrukturen zerstört

**Befund:** Installer Auto-Injection + Policy Gate Projekt-Ableitung ermöglichen parallele Projekte.

### 4.4 Parallele Laufzeiten – Mechanismen

**Deployment Identity:** `<account>:<project>:<environment>`

**Plan Identity Filename:**
`<project>-<environment>-<version>-<phase>-<account>-<operation>-<seq>.tfplan`

**Terraform Workspace:**
- Auto-Selection per `project_name`
- Separate State pro Workspace
- Environment Var `TERRAFORM_WORKSPACE`

**Policy Gate:**
- Nutzt jetzt Resource Tags statt Hardcode
- Erlaubt beliebige `mays-*` Projekte

**OwnershipAnalyzer:**
- Klassifiziert Ressourcen: OWNED, FOREIGN, AMBIGUOUS, UNMANAGED
- Ambiguous Ownership wird surfaced, nicht still adoptiert

**Risiken bei parallelen Laufzeiten:**
- Destroy Default Projekt zerstört produktionsähnliche Ressourcen
- Tests nicht parametrisiert → könnten falsches Projekt ansprechen
- Installer CLI Mapping `--project-name` → `-var project_name` muss dokumentiert werden

---

## 5. Zusammenfassung & Empfehlungen

### Erledigt
- CI/CD Pipeline Architektur mit Installer Authority implementiert
- Repository Bootstrap validiert
- Installer Lifecycle D0-D8 komplett
- Upgrader Parallel Deployment Fix umgesetzt
- Parallele Projekte erfolgreich getestet und zerstört
- Parametrisierte State Machine Tests vorhanden

### Offene Punkte
1. **CI/CD Source:** GitHub PAT aktualisieren, Source Stage entsperren
2. **Dokumentation:** `INSTALLER-LIFECYCLE.md` H2 um Workspace Isolation ergänzen, Architektur Note hinzufügen
3. **Parametrisierte Tests:** E2E Tests auf `PROJECT_NAME` parametrisieren, API/SQS URLs dynamisch
4. **Parallel Runtime:** Installer CLI Mapping dokumentieren, Backend Key pro Projekt evaluieren

### Nächste Schritte laut AI_AUDITLOG Form
- Dokumentationsupdate PR erstellen
- Test-Parametrisierung implementieren
- GitHub Secret aktualisieren und Pipeline neu starten
- `docs/PROJECT_STATUS.md` aktualisieren

---

**Quellen:** `docs/AI_AUDITLOG.md`, `docs/INSTALLER-LIFECYCLE.md`, `docs/reports/INSTALLER-D8-CICD.md`, `docs/reports/CI-REPOSITORY-BOOTSTRAP-01.md`, `docs/reports/GITHUB-AUTH-CI-INTEGRATION-01.md`, `docs/reports/09-01/09-02/09-03/09-04/09-05-PARALLEL-*`, `lambda/tests/test_state_machine.py`, `tests/test_e2e_async_order.py`
