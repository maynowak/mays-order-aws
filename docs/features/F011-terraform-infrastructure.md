# F011 — Terraform Infrastructure

| Feld | Wert |
|------|------|
| **ID** | F011 |
| **Name** | Terraform Infrastructure |
| **Status** | 🔵 IN PROGRESS |
| **Week** | 2 |
| **Abhängigkeiten** | F001 |
| **Fachquelle** | `terraform/README.md`, `architecture/architecture-decisions.md` |

## Beschreibung

IaC für DynamoDB, IAM, Lambda, Cognito, HTTP API, CloudWatch. `terraform validate`/`plan`
vor jedem Apply; `apply` nur nach menschlicher Freigabe. Keine manuell erzeugte Infrastruktur.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T011-01 | Terraform-Gerüst (main/variables/outputs/README) | ✅ COMPLETE |
| T011-02 | DynamoDB-Tabelle + GSI1 | ⏳ PLANNED |
| T011-03 | IAM-Rolle + Policy | ⏳ PLANNED |
| T011-04 | Lambda (Zip-Build) + Permission | ⏳ PLANNED |
| T011-05 | Cognito (Pool, Client, Gruppe) | ⏳ PLANNED |
| T011-06 | HTTP API + Routen + Authorizer | ⏳ PLANNED |
| T011-07 | `terraform validate` + `plan` (Review) | ⏳ PLANNED |
| T011-08 | `terraform apply` (nach Freigabe) + Outputs dokumentieren | ⏳ PLANNED |
| T011-09 | (Optional) S3-Backend-Entscheidung | ⏳ PLANNED |

## Progress — laufender Arbeitsstand (Persistent Feature Progress)

```text
Feature:
F011 — Terraform Infrastructure

Status:
🔵 IN PROGRESS

Current Task:
T011-02 — DynamoDB-Tabelle + GSI1 (PLANNED — wird separat gestartet)

Completed Tasks:
- T011-01 Terraform-Gerüst             ✅

In Progress:
None (T011-01 abgeschlossen; nächster Task wird separat gestartet)

Pending Tasks:
- T011-02 DynamoDB-Tabelle + GSI1
- T011-03 IAM-Rolle + Policy
- T011-04 Lambda (Zip-Build) + Permission
- T011-05 Cognito (Pool, Client, Gruppe)
- T011-06 HTTP API + Routen + Authorizer
- T011-07 terraform validate + plan (Review)
- T011-08 terraform apply (nach Freigabe)
- T011-09 (Optional) S3-Backend-Entscheidung

Changes Made:
- terraform/main.tf erstellt (terraform-Block, AWS-Provider, Region, Default-Tags)
- terraform/variables.tf erstellt (project_name, aws_region, tags)
- terraform/outputs.tf erstellt (leer; Outputs folgen je Ressource ab T011-02)
- terraform/README.md aktualisiert (Struktur auf T011-01-Stand)
- terraform/.terraform.lock.hcl committet

Tests:
- Terraform init: PASS (aws provider v5.100.0)
- Terraform validate: PASS

Validation:
- Terraform plan: NOT RUN (gehört zu T011-07; keine Ressourcen im Gerüst)
- Terraform apply: NOT RUN (Freigabe erforderlich)
- git diff --check: PASS
- Secret-Audit: PASS

Known Issues:
- None

Blockers:
- None

Current Checkpoint:
67f02a3

Next Step:
T011-02 — DynamoDB-Tabelle + GSI1 (separater Prompt / Task)
```

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform init | PASS (aws provider v5.100.0) |
| Terraform validate | PASS |
| Terraform plan | NOT RUN (zu T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Terraform destroy (Cleanup) | NOT RUN |
| `git diff --check` | PASS |
| Secret-Audit | PASS |

## Git Checkpoint

- Branch: `main` · Commit: `67f02a3` · Push: SUCCESS

## Next Step

T011-02 — DynamoDB-Tabelle + GSI1 (nach Checkpoint T011-01).