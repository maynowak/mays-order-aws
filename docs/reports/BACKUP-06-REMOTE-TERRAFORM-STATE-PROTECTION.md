# BACKUP-06 — Remote Terraform State Protection

**Datum:** 2026-09-26  
**Scope:** Design & Schutzgrundlage für Remote Terraform State im Multi-Project System  
**Keine Migration, keine Apply, keine Backend-Aktivierung**

---

## 1. Scope

Entwicklung und Implementierung der Grundlage für einen geschützten Remote Terraform State für das bestehende Multi-Project-System.

`project_name`-Semantik bleibt unverändert und ist Source of Truth.

```
project_name
    ↓
Terraform Workspace
    ↓
State Isolation
    ↓
Resource Naming
```

Backup/Recovery darf keinen eigenen Project-Identifier erfinden.

## 2. Current State

### 2.1 Git Basis

- Top-level: `/home/dci-student/projects/Mays-Orders-AWS`
- Branch: `main`
- HEAD: `4b5b032f57398dc7c40b98c458f89b49fe0cfc15`
- Working Tree: CLEAN
- B5 Commit 99e80b1 vorhanden
- R10 Commit 4b5b032 vorhanden

### 2.2 Backend

- Kein `backend.tf` vorhanden
- Kein Remote Backend konfiguriert
- Lokaler State aktiv

### 2.3 Lokaler State

- `terraform/terraform.tfstate` — default workspace
- `terraform/terraform.tfstate.backup`
- `terraform/terraform.tfstate.d/mays-order-par/terraform.tfstate`
- `terraform/terraform.tfstate.d/mays-order-par/terraform.tfstate.backup`
- State Dateien in `.gitignore`
- Kein Backup, keine Versionierung, kein Locking

### 2.4 Workspace Mechanismus

- `installer/core/context.py` → `terraform_workspace = project_name`
- `TERRAFORM_WORKSPACE` Env Var exportiert
- `installer/terraform/runner.py` selektiert Workspace vor jedem Command
- Workspace wird erstellt falls fehlend

### 2.5 Installer / CI/CD

- Terraform Init wird via Installer Runner ausgeführt
- Project Name wird auto-inject in Terraform Vars
- CI/CD nutzt aktuell lokalen/temporären State
- Keine Backend-Abhängigkeit vorhanden

## 3. Existing Multi-Project Model

Aktuelles Modell:

```
mays-orders
    ↓
Workspace mays-orders
    ↓
State A — terraform/terraform.tfstate.d/mays-orders/

mays-order-par
    ↓
Workspace mays-order-par
    ↓
State B — terraform/terraform.tfstate.d/mays-order-par/
```

Isolation erfolgt über Terraform Workspaces + project_name.

Ziel Remote State muss dieselbe Isolation erhalten.

## 4. Remote Backend Architecture

### 4.1 Zielarchitektur

S3 Remote Backend mit:

- Server-Side Encryption AES256
- Versionierung aktiv
- State Isolation via Key Prefix + Workspace
- IAM Access Control
- DynamoDB Locking
- Auditierbarkeit via CloudTrail

### 4.2 Terraform Version

- Required Version >= 1.5.0
- S3 Backend unterstützt seit Terraform 0.12
- `workspace_key_prefix` verfügbar ab Terraform 0.12

### 4.3 Locking Variante

- DynamoDB Lock Table
- Tabelle Name: `mays-orders-terraform-locks`
- Partition Key: `LockID`
- Keine neue Tabelle automatisch erstellen, Design nur

## 5. State Bucket

### 5.1 Naming

Vorschlag zentral:
`mays-orders-tfstate-central-240571105849`

Alternative pro Projekt:
`mays-orders-terraform-state-240571105849`

Empfehlung: Zentrales Bucket mit Isolation via Key Prefix.

### 5.2 Konfiguration

- Region: `eu-central-1`
- Encryption: SSE-S3 AES256
- Versionierung: Aktiv
- Public Access Block: Alle vier Flags true
- Tags:
  - Project = `mays-orders`
  - ManagedBy = `Terraform`
  - Environment = `Development`

State Bucket ist keine project_name-DynamoDB-artige Ressource.
Isolation erfolgt über State Structure, nicht Bucket pro Projekt.

## 6. State Key / Workspace Isolation

### 6.1 Terraform S3 Backend Verhalten

Standard S3 Backend:
- Default Workspace: `key`
- Nicht-Default Workspace: `<key_prefix>/<workspace>/<key>` falls `workspace_key_prefix = true`

Beispiel mit `key = "terraform.tfstate"` und `workspace_key_prefix = true`:

- Default: `terraform.tfstate`
- Workspace mays-orders: `env/mays-orders/terraform.tfstate`
- Workspace mays-order-par: `env/mays-order-par/terraform.tfstate`

### 6.2 Key Convention Vorschlag

```
<environment>/<project_name>/terraform.tfstate
```

Beispiel:
```
development/mays-orders/terraform.tfstate
development/mays-order-par/terraform.tfstate
```

Mit `workspace_key_prefix = true` wird Workspace automatisch in Key eingebettet.

**Wichtig:** Projekt A darf niemals State von Projekt B verwenden.
Isolation durch Key Prefix + Workspace Name.

## 7. Encryption

- S3 Server-Side Encryption AES256
- Optionale KMS Integration für höhere Security Profile
- Aktuell LOWEST/PROTOTYPE → SSE-S3 ausreichend

## 8. Versioning

- S3 Versionierung aktiv
- Ermöglicht Recovery zu vorherigen State Versionen
- Lifecycle Policy optional, nicht für State empfohlen

## 9. Locking

- DynamoDB Lock Table
- Name: `mays-orders-terraform-locks`
- Keine automatische Erstellung im Rahmen B6
- Locking verhindert concurrent Änderungen

## 10. IAM

### 10.1 Local Development

- AWS_PROFILE bestehende Credentials
- IAM User/Rolle mit S3 Get/Put/List/Versioning
- DynamoDB Get/Put/Delete auf Lock Table

### 10.2 CI/CD

- CodeBuild IAM Role mit minimalen Rechten
- S3: GetObject, PutObject, DeleteObject, ListBucket, GetObjectVersion
- DynamoDB: GetItem, PutItem, DeleteItem
- Kein AdministratorAccess

Trennung Local vs CI/CD erfordern separate IAM Policies.

## 11. State Backup

Backup vor Migration erforderlich:

```
LOCAL STATE
    ↓
READ-ONLY BACKUP
    ↓
INTEGRITY CHECK
    ↓
REMOTE BACKUP MIGRATION
```

Für jedes Workspace State:
- Identifizieren: `terraform/terraform.tfstate.d/<workspace>/terraform.tfstate`
- Sichern nach sicherem Ort
- Checksum prüfen
- Zuordnung `project_name ↔ Workspace` dokumentieren

Keine State-Inhalte in Auditlog.

## 12. Migration Plan

**KEINE MIGRATION DURCHFÜHREN IN B6**

Planung nur:

PHASE 0 — Pre-flight
- Git Basis prüfen
- State Inventar erstellen
- Backup Strategie validieren

PHASE 1 — State Backup
- Lokale State Dateien sichern
- Integrität prüfen

PHASE 2 — Remote Backend Infrastructure
- S3 Bucket Design finalisieren
- DynamoDB Lock Table Design finalisieren
- IAM Policies designen

PHASE 3 — IAM Permissions
- Local Dev Rechte definieren
- CI/CD Rechte definieren

PHASE 4 — Backend Configuration
- `terraform/backend.tf` vorbereiten, NICHT aktivieren
- `workspace_key_prefix = true`

PHASE 5 — Migration eines kontrollierten Projekts
- Nur nach Freigabe

PHASE 6 — Validation
- `terraform plan` zeigt kein Diff
- State in S3 vorhanden

PHASE 7 — Migration weiterer Projekte
- Nach erfolgreicher Validation

PHASE 8 — CI/CD Validation
- Buildspec Anpassung prüfen

PHASE 9 — Rollback / Recovery
- Verfahren dokumentieren

## 13. Rollback

Rollback Szenarien:

- S3 Backend nicht erreichbar → lokaler State wiederherstellen
- Falscher State Key → Key Korrektur, State aus Versionierung wiederherstellen
- Falscher Workspace → Workspace Selection prüfen
- Migration abbricht → Backup wiederherstellen
- Locking fehlschlägt → Lock Table prüfen
- CI/CD kann State nicht lesen → IAM prüfen
- Projekt A sieht State von Projekt B → Key Prefix + Workspace Isolation prüfen

Rollback muss verhindern, dass bestehende lokale State-Basis verloren geht.

## 14. Multi-Project Test Plan

Vor Migration definieren:

Projekt A: `mays-orders`
Projekt B: `mays-order-par`

Tests:
1. `terraform init` mit Backend Config
2. Workspace Selection korrekt
3. `terraform plan` ohne Diff
4. State Isolation verifiziert
5. Project Resource Resolution korrekt
6. Parallel Plan ohne Kollision
7. Kein Cross-Project State
8. CI/CD Zugriff funktioniert
9. Recovery aus State-Version möglich
10. Rollback funktioniert

Keine produktive Migration durchführen.

## 15. CI/CD Impact

- `terraform init` wird Backend konfigurieren
- State Pfad ändert sich von lokal zu S3
- IAM Rolle für CodeBuild muss S3/DynamoDB Zugriff haben
- Buildspecs müssen `TERRAFORM_WORKSPACE` setzen
- Keine Änderung der Installer Logik nötig

## 16. Open Decisions

- Zentrales Bucket vs pro Projekt Bucket
- State Key Convention final
- Bucket Name final
- Lock Table Name final
- Migration Zeitpunkt
- IAM Policy Details

## 17. Next Implementation Step

B7: Konkrete Backend Konfiguration vorbereiten nach Freigabe.
Keine Migration in B6.

---

**Ende BACKUP-06**
