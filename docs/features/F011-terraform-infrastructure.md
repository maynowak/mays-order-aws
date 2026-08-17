# F011 — Terraform Infrastructure

| Feld | Wert |
|------|------|
| **ID** | F011 |
| **Name** | Terraform Infrastructure |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 2 |
| **Abhängigkeiten** | F001 |
| **Fachquelle** | `terraform/README.md`, `architecture/architecture-decisions.md` |

## Beschreibung

IaC für DynamoDB, IAM, Lambda, Cognito, HTTP API, CloudWatch. `terraform validate`/`plan`
vor jedem Apply; `apply` nur nach menschlicher Freigabe. Keine manuell erzeugte Infrastruktur.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T011-01 | Terraform-Gerüst (main/variables/outputs/providers) | ⏳ PLANNED |
| T011-02 | DynamoDB-Tabelle + GSI1 | ⏳ PLANNED |
| T011-03 | IAM-Rolle + Policy | ⏳ PLANNED |
| T011-04 | Lambda (Zip-Build) + Permission | ⏳ PLANNED |
| T011-05 | Cognito (Pool, Client, Gruppe) | ⏳ PLANNED |
| T011-06 | HTTP API + Routen + Authorizer | ⏳ PLANNED |
| T011-07 | `terraform validate` + `plan` (Review) | ⏳ PLANNED |
| T011-08 | `terraform apply` (nach Freigabe) + Outputs dokumentieren | ⏳ PLANNED |
| T011-09 | (Optional) S3-Backend-Entscheidung | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform validate | NOT RUN |
| Terraform plan | NOT RUN |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Terraform destroy (Cleanup) | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T011-01 (Terraform-Gerüst) — nach Freigabe. Erster konkreter Woche-2-Schritt.