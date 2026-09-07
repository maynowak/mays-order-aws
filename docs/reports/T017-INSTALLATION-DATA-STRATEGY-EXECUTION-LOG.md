# T017 INSTALLATION DATA STRATEGY — Execution Log

> **Task:** Installation decision — DATA STRATEGY (fifth decision in the installation
> sequence, after T013 Identity, T014 Cost Profile, T015 Region, T016 Availability).
> **Mode:** PLANNING / DOCUMENTATION ONLY — **no `terraform apply`, no `destroy`, no
> commit/push.**
> **Date:** 2026-09-03

---

## 1. Task identification

T017 — Installation Decision: DATA STRATEGY. Continues from T013/T014/T015/T016 (COMPLETE).

## 2. Start state (verified)

- Branch: `main`
- HEAD: `4c4c4c27d0847b9169654ea0db35ad805e942da1` (commit: "Das Gate verlangt Environment …")
- Terraform CLI: v1.15.8; AWS provider `~> 6.0` (lock 6.60.0)
- No AWS credentials used (no `apply`; only provider-agnostic `validate`/`plan`).

## 3. T016 baseline

- T016 status COMPLETE; availability `LOW / PROTOTYPE`, single region, no VPC/failover. ✅
- Terraform baseline: `fmt -check` PASS, `validate` PASS, `plan` 30/0/0. ✅

## 4. HEAD discrepancy (important — documented, not modified)

- The T017 brief baseline states HEAD `150f9d6`. **Actual HEAD is `4c4c4c2`** — a new commit
  ("Das Gate verlangt Environment deshalb als Pflicht-Tag …") that landed on `main` on top of
  `150f9d6` between T016 and T017. It contains the Terraform Policy Gate work
  (`docs/TERRAFORM_POLICY_GATE.md`, `docs/reports/TERRAFORM-COST-RESOURCE-POLICY-GATE.md`,
  `terraform/policy/`).
- This commit is now tracked (not untracked) and is **not** part of T017 work. Left untouched.
- Note: `origin/main` is at `e1d80e6`; `main` has no upstream configured and is ahead. No
  push/commit performed here.

## 5. Repository verification (verified, read-only)

`git status --short` at start:

```
 M docs/PROJECT_STATUS.md
 M docs/reports/T011-11-CLOUDWATCH-MONITORING-EXECUTION-LOG.md
 M docs/roadmap/future-extensions.md
 D docsMaysOrdersAws.zip
 M terraform/README.md
 M terraform/main.tf
 M terraform/variables.tf
?? architecture/architecture-and-security.md
?? architecture/installation-concept.md
?? docs/AI_AUDITLOG.md
?? docs/reports/CURRENT-INFRA-AUDIT-EXECUTION-LOG.md
?? docs/reports/T011-CLOUDTRAIL-EXECUTION-LOG.md
?? docs/reports/T012-INSTALLATION-CONCEPT-EXECUTION-LOG.md
?? docs/reports/T013-INSTALLATION-IDENTITY-EXECUTION-LOG.md
?? docs/reports/T014-INSTALLATION-COST-PROFILE-EXECUTION-LOG.md
?? docs/reports/T015-INSTALLATION-REGION-EXECUTION-LOG.md
?? docs/reports/T016-INSTALLATION-AVAILABILITY-EXECUTION-LOG.md
?? security/cloudtrail-design.md
?? terraform/modules/cloudtrail/
```

(Note: `docs/TERRAFORM_POLICY_GATE.md`, `docs/reports/TERRAFORM-COST-RESOURCE-POLICY-GATE.md`,
and `terraform/policy/` are no longer untracked — they were committed in `4c4c4c2`.)

## 6. Existing worktree discrepancies

- ` D docsMaysOrdersAws.zip` — deleted, not staged; pre-existing / unexplained; **not touched**.
- All other modified/untracked entries above are pre-existing across T013–T016; preserved.

## 7. DynamoDB configuration verification (verified, `terraform/modules/dynamodb/main.tf`)

| Aspect | Verified value |
|---|---|
| Resource | `aws_dynamodb_table.orders` (name = `var.project_name`) |
| Billing | `billing_mode = "PAY_PER_REQUEST"` (On-Demand) |
| Primary key | `pk` (HASH, S) / `sk` (RANGE, S) |
| GSI1 | `gsi1pk`(HASH)/`gsi1sk`(RANGE), `projection_type = "INCLUDE"`, `non_key_attributes` = orderId, status, customer, totalAmount, createdAt, updatedAt |
| PITR | **absent** (no `point_in_time_recovery` block) → NOT enabled |
| Encryption | **no `server_side_encryption` block** → DynamoDB default at-rest encryption (AWS-owned KMS), NOT customer-managed KMS |
| Deletion protection | absent |
| TTL | absent |
| Streams | absent (no `stream` block; `outputs.tf` exposes `table_stream_arn` which resolves empty) |
| Replication / Global Tables | absent |

## 8. Primary data strategy

- **Primary data store:** DynamoDB (single table) in `eu-central-1`.
- **Single-region.** No Global Tables, no cross-region replicas.
- AWS-managed durability within the selected region; no additional data infrastructure.

## 9. Region relationship

- Data placement is tied to the selected region `eu-central-1` (T015). Statement is purely
  architectural: "regional resources are provisioned in the selected AWS region." No
  legal/compliance (e.g. GDPR) claim made.

## 10. Replication decision

- **No cross-region replication.** Single region. Deferred to future multi-region decision
  (only under `HIGH AVAILABILITY`/`CUSTOM`).

## 11. Backup / PITR decision

- **PITR NOT enabled** (verified). Deliberate `LOWEST/PROTOTYPE` trade-off: lower cost/simplicity
  vs. recovery capability. Revisit as Optional Feature (T019) / later hardening. No backups.

## 12. Encryption decision

- **AWS-managed default at-rest encryption** (DynamoDB always encrypts; no explicit
  `server_side_encryption` → AWS-owned KMS). **Not** customer-managed KMS. Customer-managed KMS
  is a later Security-Profile / Optional-Feature decision — not claimed to be present.

## 13. Consistency considerations (verified at code level)

- Lambda uses default DynamoDB reads (GetItem/Query); grep found **no** `ConsistentRead`/
  `transact`/`TransactWrite` usage → default eventually-consistent reads.
- Strongly-consistent / transactional requirements, if any, are Week-3 business-rule work; not
  introduced here.

## 14. Cost relationship

- `LOWEST/PROTOTYPE` → `LOW`. No Global Tables, cross-region replication, duplicate storage,
  KMS, or complex backup infrastructure. Existing managed-service durability retained (no
  removal of security/durability to save cost).

## 15. Terraform implementation decision

- **No Terraform change (outcome A).** Current DynamoDB configuration already represents the
  selected single-region LOWEST/PROTOTYPE data strategy. No dead variables, no unused
  abstractions. No Global Tables / replication / KMS / PITR added.

## 16. Files changed (this task)

- MOD `architecture/installation-concept.md` — header status (T017 note, HEAD `4c4c4c2`) +
  new §3.4 (Data Strategy decision).
- MOD `terraform/README.md` — header "Stand T017" note + §9.4 Future-Work list update
  (Data Strategy moved to "Definiert") + new §9.8 (Data Strategy).
- NEW `docs/reports/T017-INSTALLATION-DATA-STRATEGY-EXECUTION-LOG.md` (this file).

No `.tf` files changed.

## 17. Validation (actually executed)

| Check | Result |
|-------|--------|
| `terraform fmt -check -recursive` | PASS (exit 0) |
| `terraform validate` | PASS ("The configuration is valid.") |
| `terraform plan` | PASS — **30 to add, 0 to change, 0 to destroy** |

## 18. Terraform plan result

- **30 to add, 0 to change, 0 to destroy** — identical to T016/T015/T014/T013 baseline. No
  `.tf` change in T017 → count unchanged. `apply`/`destroy` NOT run.

## 19. Git status (after this task)

- Branch: `main`; HEAD: `4c4c4c2`.
- **T017-introduced:** modifications to `architecture/installation-concept.md` and
  `terraform/README.md` + this new execution log.
- **Pre-existing / unrelated (preserved):** ` D docsMaysOrdersAws.zip`; the modified/untracked
  set listed in §5; the already-committed policy-gate work in `4c4c4c2`.

## 20. Deployment status

- `terraform apply` — NOT EXECUTED.
- `terraform destroy` — NOT EXECUTED.
- Commit / push / add / reset / stash / restore / checkout / clean — NONE.

## 21. Final verified state

- Data strategy defined: single-region DynamoDB (`eu-central-1`), no replication, PITR/KMS/
  streams deferred. No Terraform change; plan 30/0/0 baseline unchanged.

## 22. Resume point

Data Strategy decision COMPLETE. Next installation decision:

```
COST ✅ → REGION ✅ → AVAILABILITY ✅ → DATA STRATEGY ✅ (T017) → SECURITY PROFILE (T018)
```

Read `architecture/installation-concept.md` §3.4 and `terraform/README.md` §9.8 first.

---

**FILES CHANGED:** `architecture/installation-concept.md`, `terraform/README.md`,
NEW `docs/reports/T017-INSTALLATION-DATA-STRATEGY-EXECUTION-LOG.md`
**AWS CHANGES: NONE** · **GIT CHANGES: NONE** (no commit/push)
**HEAD NOTE:** `4c4c4c2` (policy-gate commit) — newer than the `150f9d6` baseline in the brief;
not introduced by T017.
**PRE-EXISTING DISCREPANCY:** `docsMaysOrdersAws.zip` deleted (unexplained, untouched).