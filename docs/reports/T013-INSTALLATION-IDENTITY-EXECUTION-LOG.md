# T013 INSTALLATION IDENTITY — Execution Log

> **Task:** Implement the First Safe Installation-Configuration Layer — PROJECT IDENTITY.
> **Mode:** IMPLEMENTATION (identity/tagging only) — **no `terraform apply`, no `destroy`, no commit/push.**
> **Priority:** LOW-RISK, INCREMENTAL (first implementation step from T012 concept).
> **Date:** 2026-09-01

---

## 1. Task / Status

**Status: COMPLETE** (identity layer implemented + validated; nothing applied)

## 2. Environment snapshot (verified, read-only)

- Branch: `main`
- HEAD: `150f9d69ebc08589a1304c5b94935f5fdd1aaa9c` (feat: expose root infrastructure outputs)
- Terraform CLI: v1.15.8; AWS provider `~> 6.0` (lock 6.60.0)
- No AWS credentials used for this task (no `apply`, no API calls besides provider-agnostic `plan`).

## 3. Initial git status (verified before work)

Pre-existing uncommitted changes (NOT introduced by this task, preserved):
- Modified: `docs/PROJECT_STATUS.md`, `docs/reports/T011-11-...EXECUTION-LOG.md`,
  `docs/roadmap/future-extensions.md`, `terraform/README.md`, `terraform/main.tf`.
- Untracked: `architecture/architecture-and-security.md`, `architecture/installation-concept.md`,
  `docs/AI_AUDITLOG.md`, `docs/reports/CURRENT-INFRA-AUDIT-EXECUTION-LOG.md`,
  `docs/reports/T011-CLOUDTRAIL-EXECUTION-LOG.md`, `docs/reports/T012-...EXECUTION-LOG.md`,
  `security/cloudtrail-design.md`, `terraform/modules/cloudtrail/`.

Note: `terraform/main.tf` already carried a pre-existing uncommitted change adding
`module "cloudtrail"` (T011). This task added the identity `locals` + `default_tags`
change on top, without disturbing the CloudTrail block.

## 4. Identity architecture inspected (verified)

- `project_name` (`terraform/variables.tf`, default `"mays-orders"`) is the single central
  naming/identity lever: it flows into every module as `project_name` and is used as
  `${var.project_name}-*` resource-name prefix in all 7 modules; DynamoDB table name ==
  `project_name` (`modules/dynamodb/main.tf:4`).
- Tags: root `provider.default_tags` (main.tf) merges `Project` + `var.tags`; each module
  independently sets `tags = merge({ "Project" = var.project_name }, var.tags)` —
  pre-existing redundancy, left unchanged.
- Hard-coded "May's Orders" texts in `.tf`: only cosmetic `outputs.tf` descriptions and
  the API Gateway resource `description` field (`modules/api/main.tf:10`). No identity
  change required for these (they are human-readable, not name-forming).

## 5. Current project_name usage (verified)

- Resource **names** (identity-affecting): DynamoDB table, IAM role/policy, Lambda function,
  Log group, Cognito pool/client, API + authorizer, monitoring dashboard + 6 alarms,
  CloudTrail trail + S3 bucket.
- **Tag** `Project`: propogated via `default_tags` and per-module tags.
- **Outputs**: descriptive labels only (not name-forming).

## 6. Naming constraints (assessed)

- DynamoDB table name == `project_name` (min 3, `[a-zA-Z0-9_.-]`).
- Lambda/IAM names `${project_name}-handler` / `-handler-role` (≤ 64).
- S3 bucket `${project_name}-cloudtrail-<account-id>` (lowercase only, no underscore, ≤ 63).
- Conclusion: lowercase + hyphen `[a-z0-9-]`, min 3 chars, is safe across all resources.

## 7. Implementation decision

Minimal, safe identity layer — **no new module interfaces, no resource-name model change:**

1. `project_name` — kept as the configurable identity lever (adds a `validation {}` block
   for predictability/safety only).
2. `maker` — new `local.maker = "mays-orders"` (immutable provenance), surfaced only as a
   `Maker` tag via `provider.default_tags`. Neutral project slug, NOT a personal name.
3. `ManagedBy` / `CreatedBy` — deliberately NOT introduced as dedicated variables; they are
   expressible through the existing `var.tags` map (minimal interface).
4. No identity outputs added (provenance is a constant tag, not an operational interface).

## 8. Files changed (this task)

- MOD `terraform/main.tf` — added `locals { maker = "mays-orders" }`; extended `default_tags`
  to include `"Maker" = local.maker`.
- MOD `terraform/variables.tf` — added `validation {}` to `project_name` (min 3, `[a-z0-9-]`).
- MOD `terraform/README.md` — header note (T013) + new §9 "Projekt-Identität (Installation Layer, T013)".
- MOD `architecture/installation-concept.md` — status header updated (identity layer implemented).
- NEW `docs/reports/T013-INSTALLATION-IDENTITY-EXECUTION-LOG.md` (this file).

## 9. Terraform validation (actually executed)

| Check | Result |
|-------|--------|
| `terraform fmt` | PASS |
| `terraform fmt -check -recursive` | PASS (exit 0) |
| `terraform validate` | PASS ("The configuration is valid.") |
| `terraform plan` | PASS — **30 to add, 0 to change, 0 to destroy** |

`Maker` tag visible in `tags_all` on planned resources (e.g. `{"Maker" = "mays-orders",
"Project" = "mays-orders"}`). No unexpected changes/replacements introduced.

## 10. Plan summary vs. expectation

- EXPECTED: no resource replacement/destruction; additive tag only.
- ACTUAL: 30 to add, 0 to change, 0 to destroy (fresh-empty state; identical resource count
  to pre-T013). No rename → no destroy/create.
- RECOMMENDED: proceed as normal; identity re-brand is safe only BEFORE first apply.

## 11. AWS / Git actions

- `terraform apply` — NOT run.
- `terraform destroy` — NOT run.
- Commit / push / add / reset — NONE.

## 12. Open questions

- Whether future task adds dedicated `managed_by`/`created_by` variables (currently `var.tags`).
- Whether the API Gateway `description` "May's Orders" should be parameterized later (cosmetic).

## 13. Risks

- Post-apply `project_name` change → destroy/create (documented warning, no auto-migration).

## 14. Resume point

Identity layer complete and validated. Next = other installation decisions (cost profile,
Region, availability, data strategy, security profile, optional features, user confirmation)
as separate future tasks. Read `terraform/README.md` §9 + `architecture/installation-concept.md`.

---

**FILES CHANGED:** `terraform/main.tf`, `terraform/variables.tf`, `terraform/README.md`,
`architecture/installation-concept.md` + NEW `docs/reports/T013-INSTALLATION-IDENTITY-EXECUTION-LOG.md`
**AWS CHANGES: NONE** · **GIT CHANGES: NONE** (no commit/push)