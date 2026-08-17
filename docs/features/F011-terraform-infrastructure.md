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
| T011-02 | DynamoDB-Tabelle + GSI1 | ✅ COMPLETE |
| T011-03 | IAM-Rolle + Policy | ✅ COMPLETE |
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
T011-03 — IAM-Rolle + Policy (COMPLETE)

Completed Tasks:
- T011-01 Terraform-Gerüst             ✅
- T011-02 DynamoDB-Tabelle + GSI1       ✅
- T011-03 IAM-Rolle + Policy            ✅

In Progress:
None (nächster Task T011-04 wird separat gestartet)

Pending Tasks:
- T011-04 Lambda (Zip-Build) + Permission
- T011-05 Cognito (Pool, Client, Gruppe)
- T011-06 HTTP API + Routen + Authorizer
- T011-07 terraform validate + plan (Review)
- T011-08 terraform apply (nach Freigabe)
- T011-09 (Optional) S3-Backend-Entscheidung

Changes Made:
- (T011-01) terraform/main.tf erstellt (terraform-Block, AWS-Provider, Region, Default-Tags)
- (T011-01) terraform/variables.tf erstellt (project_name, aws_region, tags)
- (T011-01) terraform/outputs.tf erstellt (leer; Outputs folgen je Ressource ab T011-02)
- (T011-01) terraform/README.md aktualisiert (Struktur auf T011-01-Stand)
- (T011-01) terraform/.terraform.lock.hcl committet
- (T011-02) terraform/main.tf: `aws_dynamodb_table.orders` ergänzt (Name, On-Demand,
  PK `pk`/`sk`, GSI1 `gsi1pk`/`gsi1sk` mit INCLUDE-Projection)
- (T011-02) terraform/outputs.tf: `dynamodb_table_name`, `dynamodb_table_arn` ergänzt
- (T011-02) terraform/README.md: DynamoDB-Design (T011-02) dokumentiert
- (PROVIDER-UPGRADE) terraform/main.tf: AWS-Provider `~> 5.0` → `~> 6.0`
- (PROVIDER-UPGRADE) terraform/main.tf: GSI1 von `hash_key`/`range_key` auf `key_schema`-Blocks umgestellt
- (PROVIDER-UPGRADE) terraform/.terraform.lock.hcl: aws provider 5.100.0 → 6.60.0
- (PROVIDER-UPGRADE) terraform/README.md: Provider-Hinweis aktualisiert
- (T011-03) terraform/main.tf: `data.aws_iam_policy_document.handler_trust` (lambda.amazonaws.com)
  + `data.aws_iam_policy_document.handler` (DynamoDB auf Tabelle+GSI1, Logs)
  + `aws_iam_role.handler` (${var.project_name}-handler-role) + `aws_iam_role_policy.handler`
- (T011-03) terraform/outputs.tf: `iam_handler_role_name`, `iam_handler_role_arn` ergänzt
- (T011-03) terraform/README.md: IAM-Design (T011-03) mit Least-Privilege-Tabelle dokumentiert
- (KORREKTUR-CHECK) Gemeldeter Fehler `Required attribute "hash_key" not specified` auf
  `aws_dynamodb_table.orders` verifiziert: Tabelle hat `hash_key = "pk"` + `range_key = "sk"`,
  GSI1 nutzt weiterhin `key_schema`-Blocks (nicht deprecated), `terraform validate` PASS →
  keine Code-Änderung erforderlich

Tests:
- Terraform init: PASS (aws provider v6.60.0, `~> 6.0`)
- Terraform validate: PASS (ohne Warnungen)
- Terraform plan: NOT RUN (gehört zu T011-07)

Validation:
- Terraform plan: NOT RUN (gehört zu T011-07)
- Terraform apply: NOT RUN (Freigabe erforderlich)
- git diff --check: PASS
- Secret-Audit: PASS

Known Issues:
- None

Blockers:
- None

Current Checkpoint:
21ed0f4 (T011-03 — IAM Lambda Execution Role + Least-Privilege Policy)

Next Step:
T011-04 — Lambda (Zip-Build) + Permission (separater Prompt / Task)
```

## GSI1 — Begründung (T011-02)

```text
Access Pattern AP3 (GET /orders, Listing)
       ↓
Key Structure: gsi1pk = LIST (konstant), gsi1sk = createdAt (ISO-8601)
       ↓
Global Secondary Index "gsi1" (Projection INCLUDE: orderId, status, customer,
totalAmount, createdAt, updatedAt)
       ↓
Query(gsi1, gsi1pk = :LIST, ScanIndexForward = false, Limit, ExclusiveStartKey)
```

- **Warum GSI1 vorhanden:** Ohne Index wäre `GET /orders` ein `Scan` der gesamten
  Tabelle — linear wachsend mit der Datenmenge (siehe `database/dynamodb-design.md` §5).
- **Welches Access Pattern:** AP3 (Order Listing, paginiert, neueste zuerst).
- **Key-Struktur:** konstanter PK `LIST`, SK `createdAt` → alle Orders in einer
  GSI-Partition, sortiert nach Erstellzeit, lexikografisch korrekt absteigend.
- **Warum kein Scan:** Der Index liefert exakt die gewünschten Items als partitionierten
  `Query` mit nativem `LastEvaluatedKey`-Pagination — kein Scan, kosten- und
  latenzstabil bei wachsender Datenmenge (ADR-002).

Keine weiteren GSIs; keine weitere Index-Struktur (keine Architekturerweiterung).

## IAM-Lernbezug (T011-03, wiederverwendbar für Vortrag/Zertifizierung)

```text
IAM Role
→ IAM-Rolle
→ Identität mit Berechtigungsrahmen, die ein AWS-Service (Lambda) zur Ausführung übernehmen kann

IAM Policy
→ Berechtigungsrichtlinie
→ beschreibt erlaubte Aktionen (Actions) und Ziel-Ressourcen (Resources)

Trust Policy
→ Vertrauensrichtlinie (Assume Role)
→ bestimmt, welcher AWS-Service/Principal die Rolle übernehmen darf (hier: lambda.amazonaws.com)

Least Privilege
→ Prinzip der minimal erforderlichen Berechtigungen
→ Lambda erhält nur DynamoDB-Aktionen für Tabelle+GSI1 und Log-Rechte — kein Scan/DeleteItem, keine s3/sqs/iam-Rechte
```

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform init | PASS (aws provider v6.60.0) |
| Terraform validate | PASS (ohne Warnungen) |
| Terraform plan | NOT RUN (zu T011-07) |
| Terraform apply | NOT RUN (Freigabe erforderlich) |
| Terraform destroy (Cleanup) | NOT RUN |
| `git diff --check` | PASS |
| Secret-Audit | PASS |

## Git Checkpoint

- Branch: `main` · Commit: `21ed0f4` · Push: SUCCESS

## Next Step

T011-04 — Lambda (Zip-Build) + Permission (nach Checkpoint T011-03).