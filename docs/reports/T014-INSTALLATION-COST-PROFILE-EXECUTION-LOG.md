# T014 INSTALLATION COST PROFILE — Execution Log

> **Task:** Installation decision — COST PROFILE (the second decision in the installation
> sequence, after T013 Identity).
> **Mode:** PLANNING / DOCUMENTATION ONLY — **no `terraform apply`, no `destroy`, no
> commit/push.**
> **Date:** 2026-09-02

---

## 1. Task / Status

**Status: COMPLETE** (cost-profile decision defined + documented; no Terraform variable
implemented — no consumer; nothing applied).

## 2. Environment snapshot (verified, read-only)

- Branch: `main`
- HEAD: `150f9d69ebc08589a1304c5b94935f5fdd1aaa9c` (feat: expose root infrastructure outputs)
- Terraform CLI: v1.15.8; AWS provider `~> 6.0` (lock 6.60.0)
- No AWS credentials used for this task (no `apply`; only provider-agnostic `validate`/`plan`).

## 3. Start state / repository verification (verified)

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
?? security/cloudtrail-design.md
?? terraform/modules/cloudtrail/
```

- Terraform root: `terraform/` (root orchestrator `main.tf`, `variables.tf`, `outputs.tf`,
  `monitoring.tf`, 7 child modules under `modules/`).

## 4. Comparison against T013 log

- Branch/HEAD match T013 (`main` @ `150f9d6`). ✅
- T013 identity layer present: `local.maker` + `Maker` tag, `project_name` validation
  (`terraform/variables.tf`), README §9. ✅
- Terraform baseline (T013): `plan` = **30 to add, 0 to change, 0 to destroy**. ✅ (re-confirmed,
  see §9.)

## 5. Pre-existing `docsMaysOrdersAws.zip` discrepancy

- `git status` shows ` D docsMaysOrdersAws.zip` (deleted, not staged).
- This deletion is **NOT documented in the T013 execution log**; it is a **pre-existing /
  unexplained worktree change**.
- **Not touched by this task:** not restored, not committed, not staged, not deleted again.
  Left exactly as found. Logged here for visibility; requires later explicit user instruction.

## 6. Relevant architecture / configuration inspection (verified)

Read:
- `docs/AI_AUDITLOG.md` (execution-log convention)
- `docs/reports/T013-INSTALLATION-IDENTITY-EXECUTION-LOG.md`
- `architecture/installation-concept.md` (contains §3 Cost Profiles + §7 decision matrix +
  §9 compatibility + §10 cost transparency + §12 Terraform impact)
- `cost/cost-analysis.md` (relative cost; free-tier-first)
- `terraform/main.tf`, `terraform/variables.tf`, `terraform/README.md`

Verified: **no `cost_profile` variable exists** anywhere in Terraform. The current
configuration's cost-relevant characteristics are all pinned to the LOWEST profile:
single Region (`aws_region` default `eu-central-1`), On-Demand DynamoDB
(`PAY_PER_REQUEST`, no PITR/stream), CloudTrail SSE-S3 (no KMS), HTTP app (no custom
domain/ACM), 7-day log retention, all optional hardening deferred.

## 7. Cost-profile decision (T014)

- **Taxonomy (canonical, 4 profiles):** `LOWEST / PROTOTYPE`, `STANDARD`, `HIGH AVAILABILITY`,
  `CUSTOM` (unchanged from `installation-concept.md` §3).
- **Selected/defined default profile: `LOWEST / PROTOTYPE`** — cost level `LOW`.
- The current Terraform configuration **already corresponds exactly to `LOWEST / PROTOTYPE`**.
- Architectural implication: single-region, no multi-region replication, no optional
  paid/hardening features. `HIGH AVAILABILITY` and `CUSTOM` may trigger materially higher
  cost/complexity and must require explicit user confirmation (§8 / concept §10).

## 8. Implementation decision

- **No Terraform variable added.** Reason: the installation workflow has **no consumer** for a
  `cost_profile` value; every cost-relevant option is already pinned to LOWEST. Introducing an
  unused variable would be dead configuration (explicitly discouraged by the task §7).
- **Recommended future representation (documented, not implemented):** a `cost_profile`
  variable (`type = string`, default `"lowest"`) with `validation {}` over
  `["lowest","standard","high_availability","custom"]`, which **gates** cost-increasing
  features without itself creating resources; to be introduced in the same task that first
  makes a feature profile-dependent (Availability/Data-Strategy or Optional-Features task).

Distinction made explicit:
- **(A) Conceptual installation decision** — defined (profiles + default = LOWEST).
- **(B) Terraform implementation** — deferred (no consumer; recommended design documented).
- **(C) Future architecture decisions** — multi-region, Global Tables, PITR, KMS, HTTPS, etc.
  remain separate later tasks; NOT assumed or implemented here.

## 9. Validation (actually executed)

| Check | Result |
|-------|--------|
| `terraform fmt -check -recursive` | PASS (exit 0 — no `.tf` changed this task) |
| `terraform validate` | PASS ("The configuration is valid.") |
| `terraform plan` | PASS — **30 to add, 0 to change, 0 to destroy** |

Plan is **identical** to the T013 baseline (30/0/0). No `.tf` files modified, so no resource
count change is expected or observed. `terraform apply`/`destroy` NOT run.

## 10. Files changed (this task)

- MOD `architecture/installation-concept.md` — header status (T014 note) + new §3.1
  (cost-profile decision, default profile table, recommended `cost_profile` variable design).
- MOD `terraform/README.md` — header "Stand T014" note + new §9.5 (Cost Profile, design-only).
- NEW `docs/reports/T014-INSTALLATION-COST-PROFILE-EXECUTION-LOG.md` (this file).

No `.tf` files changed.

## 11. Git status (after this task)

- Branch: `main`; HEAD: `150f9d6`.
- **Pre-existing (NOT introduced by this task), preserved:**
  - Modified (pre-existing): `docs/PROJECT_STATUS.md`,
    `docs/reports/T011-11-...EXECUTION-LOG.md`, `docs/roadmap/future-extensions.md`,
    `terraform/README.md`, `terraform/main.tf`, `terraform/variables.tf`.
  - Deleted (pre-existing): `docsMaysOrdersAws.zip`.
  - Untracked (pre-existing): `architecture/architecture-and-security.md`,
    `architecture/installation-concept.md`, `docs/AI_AUDITLOG.md`,
    `docs/reports/CURRENT-INFRA-AUDIT-EXECUTION-LOG.md`,
    `docs/reports/T011-CLOUDTRAIL-EXECUTION-LOG.md`,
    `docs/reports/T012-INSTALLATION-CONCEPT-EXECUTION-LOG.md`,
    `docs/reports/T013-INSTALLATION-IDENTITY-EXECUTION-LOG.md`,
    `security/cloudtrail-design.md`, `terraform/modules/cloudtrail/`.
- **New changes introduced by T014:** modifications to `architecture/installation-concept.md`
  and `terraform/README.md` (both already in the pre-existing modified/untracked set) +
  this new execution log.

## 12. AWS / Git actions

- `terraform apply` — NOT run.
- `terraform destroy` — NOT run.
- Commit / push / add / reset / stash / restore / checkout / clean — NONE.
- `docsMaysOrdersAws.zip` deletion left untouched.

## 13. Open questions

- Whether `cost_profile` should be introduced at the Availability/Data-Strategy task or the
  Optional-Features task (whichever first makes a feature profile-dependent).
- Final `LOWEST`-vs-`STANDARD` default for a future production cut (currently `LOWEST`).

## 14. Risks

- None introduced by this task (no `.tf` change, no deployment). Residual: `LOWEST` profile
  is prototype-grade only; upgrading to `STANDARD`/`HIGH AVAILABILITY`/`CUSTOM` is a future,
  human-confirmed decision.

## 15. Resume point

Cost-profile decision COMPLETE. Next installation decision in sequence:

```
COST PROFILE ✅ (T014)  →  REGION (next: T015)
```

Read `architecture/installation-concept.md` (§3/§3.1, §7) and `terraform/README.md` §9.5 first.

---

**FILES CHANGED:** `architecture/installation-concept.md`, `terraform/README.md`,
NEW `docs/reports/T014-INSTALLATION-COST-PROFILE-EXECUTION-LOG.md`
**AWS CHANGES: NONE** · **GIT CHANGES: NONE** (no commit/push)
**PRE-EXISTING DISCREPANCY:** `docsMaysOrdersAws.zip` deleted (unexplained, untouched)