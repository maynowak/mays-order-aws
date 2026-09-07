# T012 INSTALLATION CONCEPT — Execution Log

> **Task:** Installation Profiles + Cost & Project Identity Decision Concept (DESIGN / PLANNING ONLY).
> **Mode:** READ-ONLY / DESIGN ONLY — no implementation, no `.tf` changes, no AWS resources,
> no `terraform apply`/`destroy`, no commit/push.
> **Date:** 2026-09-01

---

## 1. Task / Status

**Status: COMPLETE** (documentation/planning delivered; nothing implemented)

## 2. Environment snapshot (verified, read-only)

- Branch: `main`
- HEAD: `150f9d69ebc08589a1304c5b94935f5fdd1aaa9c` (feat: expose root infrastructure outputs)
- Terraform CLI: v1.15.8; AWS provider `~> 6.0` (lock 6.60.0)
- No AWS credentials used; no AWS API calls made (pure planning).

## 3. Initial git status (verified, before work)

- Modified (pre-existing, unrelated): `docs/PROJECT_STATUS.md`, `docs/reports/T011-11-...EXECUTION-LOG.md`, `docs/roadmap/future-extensions.md`, `terraform/README.md`, `terraform/main.tf`.
- Untracked (pre-existing, unrelated): `architecture/architecture-and-security.md`, `docs/AI_AUDITLOG.md`, `docs/reports/CURRENT-INFRA-AUDIT-EXECUTION-LOG.md`, `docs/reports/T011-CLOUDTRAIL-EXECUTION-LOG.md`, `security/cloudtrail-design.md`, `terraform/modules/cloudtrail/`.
- These pre-existing changes were NOT introduced by this task.

## 4. Objective

Prepare a reusable installation decision concept (cost profiles, availability/data model,
project identity, maker/provenance, decision matrix, installation flow, compatibility,
Terraform impact) — WITHOUT implementing the installer or modifying Terraform.

## 5. Inspected files (verified)

- `docs/AI_AUDITLOG.md` (execution-log convention)
- `docs/AGENTS.md`, `docs/PROJECT_STATUS.md`, `README.md`
- `terraform/main.tf`, `variables.tf`, `outputs.tf`, `README.md`
- `terraform/modules/{dynamodb,iam,lambda,cognito,api,monitoring,cloudtrail}/*.tf`
- `architecture/architecture-and-security.md`, `architecture-decisions.md`
- `security/authentication-decision.md`, `iam-design.md`, `cloudtrail-design.md`
- `docs/roadmap/future-extensions.md`, `cost/cost-analysis.md`
- `docs/reports/{CURRENT-INFRA-AUDIT-EXECUTION-LOG.md,T011-CLOUDTRAIL-EXECUTION-LOG.md}`

## 6. Current architecture inspected (verified)

- Root Terraform orchestrator; 7 child modules: `dynamodb`, `iam`, `lambda`, `cognito`,
  `api`, `monitoring`, `cloudtrail`.
- Single Region `eu-central-1` (`var.aws_region`); no VPC (ADR-006); no multi-region.
- No backend config (state is local; `terraform.tfstate` empty).
- Identity: `var.project_name = "mays-orders"` is the single config lever, propagating to
  every resource name (`${var.project_name}-*`) and the `Project` tag (root `default_tags` +
  per-module `merge({ "Project" = var.project_name }, var.tags)`).
- CloudTrail baseline present; hardening (SSE-KMS, data events, lifecycle, eventing,
  MFA delete) documented as optional/deferred.
- DynamoDB: no PITR/stream/global tables; HTTPS/custom domain absent (HTTP app protocol).

## 7. Installation decisions identified

1. Cost profile (LOWEST / STANDARD / HA / CUSTOM) — primary question.
2. Region count + selection.
3. Availability (API → compute → data → replication → recovery → cost).
4. Data strategy (single DynamoDB vs. Global Tables / replicas).
5. Security profile + optional CloudTrail hardening.
6. Project identity + maker/provenance separation.
7. Terraform remote state.
8. HTTPS/custom domain.

## 8. Cost model

Relative categories only (`LOW`/`MEDIUM`/`HIGH`/`VARIABLE`); no fabricated pricing.
Warning/confirmation pattern documented for each cost-increasing option. Disclaimer:
estimate/category, not billing guarantee. Exact pricing deferred to a separate future
pricing-research task.

## 9. Availability / data model

Documented dependency chain (API → compute → data → replication → recovery → cost), the
"single vs. multi region" canonical example, the "regional API ≠ regional app availability
if data is single-region" constraint, and the 8 multi-region decision questions.

## 10. Project identity model

`Project` (configurable, resource-name prefix + tag) separated from `ManagedBy` /
`CreatedBy` (configurable) and `Maker` (immutable provenance). Investigated current use of
`project_name`, tags, output names, CloudTrail/S3 naming, module interfaces. Identified
stable identifiers (resource names, Cognito IDs, S3 bucket, state addresses) that must not
change post-apply.

## 11. Maker / provenance model

Four labels (Project / ManagedBy / CreatedBy / Maker) with mutability table. Recommendation
documented separately: prefer neutral maker/project identity over personal name for the
shipped default (no silent change to the agreed conceptual example).

## 12. Compatibility findings

Classified combinations as SUPPORTED / SUPPORTED WITH WARNING / NOT RECOMMENDED / INVALID
(e.g. multi-region API + single-region data = NOT RECOMMENDED; lowest-cost + expensive
hardening = SUPPORTED WITH WARNING).

## 13. Terraform impact analysis

Produced mapping table: decision → future variable/module interface → affected modules →
resource impact → state/migration consideration (see `architecture/installation-concept.md`
§12).

## 14. Files changed (this task)

- NEW `architecture/installation-concept.md` (the concept document).
- NEW `docs/reports/T012-INSTALLATION-CONCEPT-EXECUTION-LOG.md` (this file).

No `.tf` files modified. No pre-existing files touched.

## 15. Terraform / AWS / Git actions

- `terraform apply` — NOT run (forbidden)
- `terraform destroy` — NOT run (forbidden)
- `terraform plan` — NOT run (planning only; prior results documented in PROJECT_STATUS.md)
- AWS resource creation — NONE
- Commit / push / add / reset — NONE

## 16. Validation performed

- Git status inspected (verified initial state, no changes introduced by this task).
- Terraform structure inspected (read-only).
- Documentation consistency check performed against `terraform/README.md`,
  `security/cloudtrail-design.md`, `architecture/architecture-and-security.md` — no
  contradictions introduced.

## 17. Open questions

- Whether `terraform apply` is scheduled for the Friday demo (still "no apply performed").
- Final default value for provenance fields (neutral maker vs. personal name) — deferred to
  implementation.
- Exact pricing (if ever needed) — separate future research task.
- Whether installer should be a CLI wizard, Terraform variables + `.tfvars` profiles, or both.

## 18. Risks

- Post-apply `project_name` rename creates new resources (destroy/replace) — identity should
  be fixed at install time.
- Multi-region without data-layer planning would mislead on actual availability.
- Cost profiles are estimates, not guarantees.

## 19. Recommended next actions

1. Implement installer variables + tag strategy (future task).
2. Decide installer form factor (wizard vs. `.tfvars` profiles).
3. Adopt S3 + DynamoDB-lock Terraform state backend (Week-2 decision).
4. Confirm HTTPS requirement before demo/live.
5. Only after human approval: `terraform apply` + live verification.

## 20. Resume point

Planning COMPLETE. Next session resumes at implementation of the installer (or any
independent follow-up), reading `architecture/installation-concept.md` first.

---

**FILES CHANGED: NEW `architecture/installation-concept.md` + this log (only)**
**AWS CHANGES: NONE**
**GIT CHANGES: NONE**