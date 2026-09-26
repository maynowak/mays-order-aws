# Konsolidierung: Parallele Projekt-Mechanismus – Dokumentation bereits implementierter Funktionalität

**Datum:** 2026-09-26  
**Status:** Dokumentation bestehender, auditierter Funktionalität  
**Kein Code-Change, keine Architekturänderung**

Dieser Bericht dokumentiert den bereits implementierten und durch Audits validierten Mechanismus für parallele Projekte. Alle Aussagen basieren auf vorhandenen Execution Logs und Code-Stand.

## Quellen

- `docs/reports/09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG.md`
- `docs/reports/09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG.md`
- `docs/reports/09-03-FULL-PARALLEL-INSTALLER-AUDIT-EXECUTION_LOG.md`
- `docs/reports/09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG.md`
- `docs/reports/09-05-DOCUMENTATION-REVIEW-EXECUTION_LOG.md`
- `docs/INSTALLER-LIFECYCLE.md` H2 Deployment Identity / Plan Identity
- `installer/core/context.py` / `installer/terraform/runner.py`

## Mechanismus Übersicht

```
project_name
    ↓
Terraform Workspace = project_name  [falls default]
    ↓
TERRAFORM_WORKSPACE Env Var
    ↓
Workspace Selection vor jedem Terraform Command
    ↓
isolierter Terraform State
    ↓
Parallel Project Deployment
```

## 1. project_name → Terraform Workspace

**Implementiert in:** `installer/core/context.py` `InstallationContext.__post_init__`

- `project_name` wird aus InstallationContext übernommen
- Wenn `terraform_workspace` default ist, wird es automatisch auf `project_name` gesetzt
- Export als Env Var `TERRAFORM_WORKSPACE`

**Quelle:** `09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG.md`
> InstallationContext.terraform_workspace defaulted to "default" for all projects → Fixed by auto-set to project_name

## 2. Workspace Selection vor Terraform Commands

**Implementiert in:** `installer/terraform/runner.py` `TerraformRunner`

- `__init__` liest `TERRAFORM_WORKSPACE` Env Override
- `run_and_get_result` selektiert Workspace vor jedem Command
- Workspace wird erstellt falls `select` fehlschlägt

**Quelle:** `09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG.md`
> TerraformRunner... run_and_get_result now selects Terraform workspace before each command, creates workspace if select fails

## 3. Isolierter Terraform State

**Verifikation durch Audits:**

- `09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG.md`:
  - `terraform workspace new mays-order-par` SUCCESS
  - Plan 37 to add, 0 change
  - Apply SUCCESS
  - Beide Projekte sichtbar: DynamoDB `mays-orders` und `mays-order-par`
  - Destroy `mays-order-par` SUCCESS, State leer, Workspace gelöscht
  - Default Workspace State intakt

- `09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG.md`:
  - Workspace `mays-order-par` erstellt
  - Deploy via Installer: validate 10 passed, plan, deploy, policy gate PASSED
  - Beide Projekte koexistieren ohne Kollision
  - Destroy zweites Projekt, DynamoDB bestätigt nur `mays-orders` bleibt

- `09-03-FULL-PARALLEL-INSTALLER-AUDIT-EXECUTION_LOG.md`:
  - `mays-orders` und `mays-order-par` jeweils mit Installer deployed
  - API Endpoints unterschiedlich, DynamoDB Tabellen getrennt
  - Tests PASSED für beide
  - Beide zerstört, State leer

## 4. Automatische project_name Ableitung / Injection

**Implementiert in:** `installer/cli/main.py` `_cmd_plan`

- Auto-Injection von `project_name` in Terraform Vars falls nicht explizit angegeben
- Verhindert manuelles `-var project_name=...`

**Quelle:** `09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG.md`
> installer/cli/main.py _cmd_plan upgraded to auto-inject project_name into Terraform vars if not explicitly provided

## 5. Policy Gate Projekt-Ableitung über Tags

**Implementiert in:** `terraform/policy/validate-plan.py`

- Policy Gate leitet Projektname aus Resource Tags ab statt Hardcode
- Erlaubt beliebige `mays-*` Projekte

**Quelle:** `09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG.md`
> Policy gate previously rejected parallel projects because it enforced hardcoded project name mays-orders
> Fixed by deriving project name from resource tags at runtime

## 6. DeploymentId Schema

**Definiert in:** `docs/INSTALLER-LIFECYCLE.md` H2

`DeploymentId = <account>:<project>:<environment>`

Beispiel: `240571105849:mays-orders:development`

- Version ist NICHT Teil der Deployment Identity
- Validierung vor Mutation

## 7. Plan Identity Filename Schema

**Definiert in:** `docs/INSTALLER-LIFECYCLE.md` H2

Format: `<project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>.tfplan`

Beispiel Deploy: `mays-orders-development-0.1.0-H2-240571105849-deploy-0002.tfplan`

- Monotonisch steigende Sequenz pro Deployment+Operation
- Plan Metadata als `.meta.json` und Deployment Context als `.context.json`

## 8. OwnershipAnalyzer

**Definiert in:** `docs/INSTALLER-LIFECYCLE.md` H2

Klassifiziert existierende Ressourcen:
- `OWNED` — gehört zu aktuellem Deployment
- `FOREIGN` — gehört zu anderem Projekt/Environment/Account
- `AMBIGUOUS` — selbe Deployment ID aber andere Version/Phase
- `UNMANAGED` — keine Deployment Metadaten

Ambiguous Ownership wird surfaced, nicht still adoptiert.

## 9. CLI Mapping

**Bestehender Stand:**
- Installer CLI `--project-name` wird nicht automatisch an Terraform vars propagiert laut `09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG.md`
- Auto-Injection erfolgt im `_cmd_plan` für `project_name`
- Empfehlung aus Log: Implementiere Installer CLI Mapping `--project-name` → `-var project_name`

Dies ist Dokumentation des Ist-Stands, keine Änderung.

## 10. Upgrader-Verhalten bei Parallel Projects

**Fix dokumentiert in:** `09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG.md`

- Vor Fix: Installer wählte keinen Workspace per `project_name` → State Kollisionen
- Nach Fix: Workspace Auto-Selection aktiv, parallele Projekte koexistieren
- Installer validate/plan/deploy/destroy operiert im korrekten Workspace

## Audit Status

**Klassifikationen aus Execution Logs:**
- `09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG.md` — GREEN
- `09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG.md` — GREEN
- `09-03-FULL-PARALLEL-INSTALLER-AUDIT-EXECUTION_LOG.md` — GREEN
- `09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG.md` — GREEN
- `09-05-DOCUMENTATION-REVIEW-EXECUTION_LOG.md` — YELLOW (Dokumentation hinkt hinter Code)

**Fazit:** Mechanismus ist implementiert, auditiert und funktioniert. Dokumentationslücke besteht.

## Verbleibende Dokumentationslücken

Aus `09-05-DOCUMENTATION-REVIEW-EXECUTION_LOG.md`:
- `docs/INSTALLER-LIFECYCLE.md` Section H2 beschreibt Deployment Identity und Plan Identity, erwähnt Terraform Workspace Isolation per Project für Parallel Deployments nicht explizit
- Architektur Dokumentation beschreibt Parallel Deployment Isolation Mechanismus nicht
- `docs/PROJECT_STATUS.md` muss Upgrader Parallel Support reflektieren

Diese Lücken wurden in diesem Dokument adressiert.

## Tests / Checks

- Keine Code-Änderungen durchgeführt
- Dokumentation basiert auf bestehenden Execution Logs
- Git Status vor Commit geprüft

## Git Status

Clean nach Erstellung der Dokumentation

---

**Hinweis:** Keine neue Funktionalität implementiert. Reine Konsolidierung und Dokumentation bereits vorhandener, auditierter Mechanismen.
