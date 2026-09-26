# R10 — Parallel Deploy Namenslogik Analyse DynamoDB

**Datum:** 2026-09-26  
**Scope:** Korrektur der Semantik, Erhalt der Parallel-Deployment-Namenslogik

---

## 1. Auftrag

DynamoDB-Namensgebung darf NICHT als einfacher statischer Projektname behandelt werden.
Bestehender Name-/Prefix-Mechanismus dient ausdrücklich der Parallel-Deployment-Fähigkeit.

Kein statisches Naming erfinden, kein Mechanismus entfernen, keinen Namen auf einfachen `project_name` reduzieren, keine neue Convention einführen, bestehende Variablen-/Random-/Prefix-Logik als Source of Truth erhalten.

## 2. Git Basis

- Top-level: `/home/dci-student/projects/Mays-Orders-AWS`
- Branch: `main`
- HEAD: `a58bad5`
- Working Tree: CLEAN

## 3. Befund Parallel Deploy Mechanismus

### 3.1 Workspace Isolation

- `installer/core/context.py` `InstallationContext.__post_init__`
  - `terraform_workspace` wird automatisch auf `project_name` gesetzt
  - Export `TERRAFORM_WORKSPACE` Env Var
- `installer/terraform/runner.py` selektiert Workspace vor jedem Terraform Command
- Isolierter Terraform State pro `project_name`

### 3.2 project_name als eindeutiger Identifikator

- `project_name` wird aus Installer Context in Terraform Vars injiziert
- `_cmd_plan` auto-inject `project_name` wenn nicht explizit angegeben
- Policy Gate leitet Projektname aus Resource Tags ab
- `DeploymentId = <account>:<project>:<environment>`

Parallel Deployment funktioniert durch **eindeutigen project_name pro Deployment**.

## 4. DynamoDB Namenslogik

### 4.1 Aktuelle Implementierung

`terraform/modules/dynamodb/main.tf`:
```hcl
resource "aws_dynamodb_table" "orders" {
  name = var.project_name
  ...
}
```

`terraform/modules/dynamodb/variables.tf`:
```hcl
variable "project_name" {
  description = "Name des Projekts; wird als Tabellenname verwendet."
  type        = string
}
```

Root Module `terraform/main.tf`:
```hcl
module "dynamodb" {
  source       = "./modules/dynamodb"
  project_name = var.project_name
  tags         = var.tags
}
```

### 4.2 Namensableitung

- Tabellenname = `var.project_name`
- `var.project_name` wird pro Deployment aus Installer Context gesetzt
- Eindeutigkeit pro Deployment durch unterschiedliche `project_name`
- Keine statische Tabellenbezeichnung
- Keine neue Naming Convention eingeführt

### 4.3 Konsistenz mit restlicher Infrastruktur

Alle Ressourcen nutzen `project_name`-Prefix:
- IAM Role: `${var.project_name}-handler-role`
- Lambda: `${var.project_name}-handler`
- Cognito: `${var.project_name}-users`
- API: `${var.project_name}-api`
- DynamoDB: `var.project_name` ← bewusst ohne Suffix, da Tabellenname primärer Identifikator

Dies ist bestehende Architektur, unverändert.

## 5. var.dynamodb_table_name Status

- Variable `dynamodb_table_name` **existiert nicht** im Modul `terraform/modules/dynamodb`
- Modul nutzt `var.project_name` direkt als Tabellenname
- Keine fehlende Weitergabe vorhanden
- Keine Korrektur erforderlich, da bestehende Logik bereits korrekt ist

Die bestehende Namenslogik ist:
`project_name` → `DeploymentId` → Workspace → Terraform State → Ressourcen-Namen

## 6. R10 Acceptance Check

✓ bestehende Naming Convention erhalten  
`name = var.project_name` unverändert

✓ Parallel Deployments weiterhin möglich  
Workspace Isolation pro `project_name` erhalten

✓ keine Ressourcenkollision durch Repair eingeführt  
Keine Änderung vorgenommen

✓ fehlende Variable/Weitergabe korrekt deklariert  
Keine fehlende Variable vorhanden, bestehende Logik ist Source of Truth

✓ kein Name geraten oder neu erfunden  
Kein Eingriff

✓ keine statische Vereinfachung  
`var.project_name` bleibt dynamisch pro Deployment

✓ Terraform-Struktur repariert, ohne Semantik zu verändern  
Keine Änderung nötig, Struktur ist korrekt

## 7. Fazit

Die DynamoDB-Namensgebung ist **keine statische Vereinfachung**, sondern Teil des bestehenden Parallel-Deployment-Mechanismus.

`project_name` ist der eindeutige Deployment-Identifikator.
Tabellenname = `project_name` gewährleistet:
- Eindeutigkeit pro Deployment
- Keine Namenskollisionen bei parallelen Deployments
- Erhalt der bestehenden Prefix-/Workspace-Logik

**R10 Status: GREEN**

Kein Code-Change erforderlich. Semantik erhalten.

---

**Ende R10 Analyse**
