# BACKUP-03 — Multi-Project Backup Protection Foundation

**Datum:** 2026-09-26  
**Scope:** Foundation für Backup/Recovery kompatibel mit bestehendem Multi-Project-Modell  
**Keine Implementierung, nur Analyse + Design Foundation**

---

## 1. Scope

Sicherstellen, dass alle zukünftigen Backup/Restore/Recovery-Mechanismen mit dem bestehenden Multi-Project-Modell kompatibel sind.

Harte Architekturvorgabe:
`project_name` → Terraform Workspace → isolierter Terraform State → projektbezogene Ressourcen

---

## 2. Git Basis

- `git rev-parse --show-toplevel`: `/home/dci-student/projects/Mays-Orders-AWS`
- Branch: `main`
- HEAD: `2eee5f48d4e41a4bd5ba1105839299cf7371fe24`
- `git status --short`: clean
- BACKUP-02 Commit vorhanden: `2eee5f4`

---

## 3. Existing Multi-Project Model

Aus `docs/reports/KONSOLIDIERUNG-PARALLEL-PROJECT-MECHANISMUS.md`:

```
project_name
    ↓
Terraform Workspace = project_name
    ↓
TERRAFORM_WORKSPACE Env Var
    ↓
Workspace Selection vor jedem Terraform Command
    ↓
isolierter Terraform State
    ↓
Parallel Project Deployment
```

Validiert durch Execution Logs 09-01 bis 09-04, Status GREEN.

**DeploymentId Schema:** `<account>:<project>:<environment>`
**Plan Identity:** `<project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>.tfplan`
**OwnershipAnalyzer** klassifiziert Ressourcen als OWNED / FOREIGN / AMBIGUOUS / UNMANAGED

---

## 4. Project Identity

Zentrale Projektidentität im bestehenden System:

- **InstallationContext.project_name** `installer/core/context.py:56`
  Default `mays-orders`, über Env `PROJECT_NAME` überschreibbar
  Auto-Set von `terraform_workspace` wenn default: `__post_init__` Zeile 86-88

- **TERRAFORM_WORKSPACE** Env Var exportiert in `__post_init__` Zeile 90

- **DeploymentId** aus `InstallationContext.get_deployment_id()`:
  account_id + project_name + environment

- **Tags**: `Project = var.project_name` in allen Terraform Ressourcen

- **Resource Naming**: `${var.project_name}-...` für DynamoDB, Cognito, API, Lambda, IAM, SQS, CloudTrail Bucket

- **Terraform Workspace**: `project_name` wird als Workspace Name verwendet

**Eindeutige Zuordnung:** Kombination aus `project_name` + `environment` + Terraform Workspace + Tags.

Keine neue Project-ID erfinden.

---

## 5. Resource Classification

### 5.1 Multi-Project Klassifikation Schema

Für jede Ressource:
- PROJECT-SCOPED
- SHARED
- UNKNOWN / NEEDS DECISION

### 5.2 Klassifikationsergebnisse

**DynamoDB**
- Classification: PROJECT-SCOPED
- Identification: Table Name = `var.project_name`, Tag Project
- Terraform Resource: `aws_dynamodb_table.orders`
- Workspace Dependency: Ja, State isoliert
- Backup Scope: projektbezogen
- Restore Scope: projektbezogen
- Ownership Verification: Tag Project + Workspace

**S3 CloudTrail Bucket**
- Classification: PROJECT-SCOPED
- Identification: Bucket Name = `${var.project_name}-cloudtrail-${account_id}`, Tag Project
- Terraform Resource: `aws_s3_bucket.trail`
- Workspace Dependency: Ja
- Backup Scope: projektbezogen
- Restore Scope: projektbezogen
- Ownership Verification: Name + Tag

**Cognito User Pool**
- Classification: PROJECT-SCOPED
- Identification: Name = `${var.project_name}-users`, Tag Project
- Terraform Resource: `aws_cognito_user_pool.users`
- Workspace Dependency: Ja
- Backup Scope: projektbezogen Config, User Data projektbezogen
- Restore Scope: projektbezogen
- Ownership Verification: Tag Project

**API Gateway HTTP API**
- Classification: PROJECT-SCOPED
- Identification: Name = `${var.project_name}-api`, Tag Project
- Terraform Resource: `aws_apigatewayv2_api.orders`
- Workspace Dependency: Ja
- Backup Scope: Config projektbezogen
- Restore Scope: projektbezogen

**SQS Queue**
- Classification: PROJECT-SCOPED
- Identification: Name = `${var.project_name}-orders-queue`, Tag Project
- Terraform Resource: `aws_sqs_queue.orders`
- Workspace Dependency: Ja
- Backup Scope: Config projektbezogen, Daten transient
- Restore Scope: projektbezogen

**Lambda**
- Classification: PROJECT-SCOPED
- Identification: Function Name = `${var.project_name}-handler`, Tag Project
- Terraform Resource: `aws_lambda_function.handler`
- Workspace Dependency: Ja
- Backup Scope: Code in Git, Config projektbezogen
- Restore Scope: projektbezogen

**IAM Role**
- Classification: PROJECT-SCOPED
- Identification: Name = `${var.project_name}-handler-role`, Tag Project
- Terraform Resource: `aws_iam_role.handler`
- Workspace Dependency: Ja
- Backup Scope: Config projektbezogen
- Restore Scope: projektbezogen

**Terraform State**
- Classification: PROJECT-SCOPED
- Identification: Terraform Workspace = `project_name`
- Workspace Dependency: Ja, isoliert
- Backup Scope: projektbezogen
- Restore Scope: projektbezogen
- Ownership Verification: Workspace

**CloudWatch Logs**
- Classification: PROJECT-SCOPED
- Identification: Log Group Name = `/aws/lambda/${project_name}-handler`, Tag Project
- Terraform Resource: `aws_cloudwatch_log_group.handler`
- Workspace Dependency: Ja
- Backup Scope: projektbezogen

**CloudTrail Trail**
- Classification: PROJECT-SCOPED
- Identification: Name = `${var.project_name}-trail`, Bucket = `${var.project_name}-cloudtrail-${account_id}`
- Terraform Resource: `aws_cloudtrail.trail`
- Workspace Dependency: Ja

**Kein SHARED Ressourcen nachweisbar im aktuellen Terraform.**

Alle untersuchten Ressourcen sind projektbezogen benannt und getaggt.

---

## 6. Project-Scoped Resources

Alle oben gelisteten Ressourcen sind PROJECT-SCOPED.

Kein Shared Ressourcenbestand nachgewiesen.

Falls zukünftig Shared Ressourcen eingeführt werden, müssen sie explizit als SHARED markiert werden.

---

## 7. Shared Resources

Aktuell:
**Keine Shared Ressourcen identifiziert.**

CloudTrail könnte theoretisch account-weit sein, aber aktuelle Implementierung ist projektbezogen via Bucket Name `${project_name}-cloudtrail-${account_id}`.

---

## 8. Backup Isolation

Prinzip:
`project_name` → Resource Discovery → Resource → Backup Configuration → Project Ownership

Anforderungen:
- Backup Identifier muss `project_name` + `environment` enthalten
- Backup Metadaten müssen Project Tag enthalten
- Restore Destination muss explizit `project_name` + `environment` validieren
- Ownership Verification vor jedem Backup/Restore Vorgang via Tag + Name + Workspace

Sicherheitsregeln:
- Backup von Projekt A darf niemals Projekt B berühren
- Restore für Projekt A darf niemals Ressourcen von Projekt B überschreiben
- Shared Resources erfordern explizite Isolation Logik

---

## 9. Restore Isolation

Restore muss eindeutig kennen:
- TARGET PROJECT
- TARGET ENVIRONMENT
- TARGET RESOURCE

Pre-Checks vor Restore:
1. Validate `project_name` aus Backup Metadaten == Ziel Project
2. Validate `environment` aus Backup Metadaten == Ziel Environment
3. Validate Resource Ownership via Tag `Project`
4. Validate Terraform Workspace == `project_name`
5. Dry-Run / OwnershipAnalyzer Check

Beispiel Verbot:
`project_name = mays-order-par` Restore darf nicht `mays-orders` überschreiben.

---

## 10. DynamoDB PITR Foundation

Aktueller Stand:
- `terraform/modules/dynamodb/main.tf` definiert Tabelle ohne PITR
- Table Name = `var.project_name`
- Tags enthalten Project

Projektbezogene PITR Aktivierung:
- PITR Konfiguration kann projektbezogen auf Tabelle angewendet werden
- Table Name eindeutig pro Projekt
- Workspace Isolation sichert State
- Keine Shared Tabelle

**Erforderlich für sichere Multi-Project PITR:**
- `point_in_time_recovery { enabled = true }` im Terraform Modul
- Table Name bleibt `var.project_name`
- Keine Änderung am Naming/Workspace Mechanismus

Aktuelle Terraform Struktur erlaubt sichere projektbezogene PITR Aktivierung ohne Architekturänderung.

Keine produktive Änderung im Rahmen B3.

---

## 11. Backup Naming / Ownership Standard

Bestehendes System:
- `Project` Tag in allen Ressourcen
- Resource Names enthalten `project_name`
- DeploymentId Schema `<account>:<project>:<environment>`
- Plan Identity enthält `project_name`

Wiederverwenden:
- `project_name`
- `environment`
- `Project` Tag
- DeploymentId

**Open Design Gap:**
Kein zentraler Backup Naming Standard existiert.
Sollte später eindeutig zuordnen können:
`project_name`, `environment`, `resource`, `backup operation`

Momentan OPEN DESIGN GAP, keine Implementierung.

---

## 12. Cross-Project Safety

Identifizierte Risiken:

**RISK:** Falsches Terraform Workspace
**EVIDENCE:** Workspace wird per `TERRAFORM_WORKSPACE` Env gesetzt
**MITIGATION:** Workspace Selection vor jedem Terraform Command, Auto-Creation, OwnershipAnalyzer

**RISK:** Falsches project_name in Backup Metadaten
**EVIDENCE:** project_name aus InstallationContext
**MITIGATION:** Pre-Check Project Name == Ziel Project, Tag Verification

**RISK:** Restore Destination Kollision
**EVIDENCE:** Ressourcen Namen enthalten project_name
**MITIGATION:** Naming Konvention + Pre-Check

**RISK:** Shared Resource versehentlich projektbezogen behandelt
**EVIDENCE:** Aktuell keine Shared Ressourcen
**MITIGATION:** Klassifikation explizit dokumentieren

---

## 13. Open Design Gaps

- Backup Naming / Ownership Standard nicht definiert → OPEN DESIGN GAP
- Restore Runbook nicht vorhanden
- Restore Test Strategie nicht definiert
- AWS Backup vs native Recovery Entscheidung offen für zukünftige Ressourcen

---

## 14. Next Implementation Step

B4: Konkrete Recovery-Implementierungsstrategie mit Multi-Project Isolation.

B3 Foundation ist definiert.

---

**Ende BACKUP-03**
