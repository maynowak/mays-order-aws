# CURRENT INFRASTRUCTURE AUDIT — EXECUTION LOG

> May's Orders — Reality-Based Infrastructure & Documentation Audit
> Mode: READ-ONLY / ANALYSIS ONLY (no apply, no destroy, no resource changes, no commit/push)

## 1. Current Status

**Status: COMPLETE (initial full pass)**

## 2. Audit Date / Time

- Date: 2026-08-31
- Mode: Read-only analysis

## 3. Git Branch & HEAD

- Branch: `main`
- HEAD: `150f9d6` feat(terraform): expose root infrastructure outputs
- Note: uncommitted modification present before audit began:
  `docs/reports/T011-11-CLOUDWATCH-MONITORING-EXECUTION-LOG.md` (pre-existing, NOT touched by this audit)

## 4. Audit Scope

Everything in the audit brief (sections 1–18). Inspected only; no redesign, no changes.

## 5. Toolchain Actually Executed (read-only)

| Check | Result |
|-------|--------|
| `terraform fmt -check -recursive` | PASS (exit 0) |
| `terraform validate` | PASS ("The configuration is valid.") |
| `terraform version` | v1.15.8 (installed) |
| git branch/HEAD/status | main @ 150f9d6; 1 pre-existing modified file |

- `terraform apply` — NOT run (forbidden)
- `terraform destroy` — NOT run (forbidden)
- `terraform plan` — NOT run during audit (state confirmed empty; prior plan results documented in PROJECT_STATUS.md)

## 6. Completed Audit Sections

1. Architecture Inventory — DONE
2. Dependency / Connection Audit — DONE
3. Network Audit — DONE
4. Variable Network Configuration — DONE
5. Security Audit — DONE
6. CloudTrail — DONE
7. Monitoring Audit — DONE
8. Error Handling — DONE
9. Reliability — DONE
10. Scaling — DONE
11. Disaster Recovery — DONE
12. Root Outputs — DONE
13. Terraform / Configuration Audit — DONE
14. Installation / How-To Audit — DONE
15. Documentation / Evidence Audit — DONE
16. Week 1–4 Structure — DONE
17. Gap Matrix — DONE
18. Final Report — DONE

## 7. Key Findings (verified)

### Confirmed PRESENT (GREEN / YELLOW / ORANGE)
- Root Terraform orchestrator (`terraform/main.tf`) — modularized.
- 6 child modules: `dynamodb`, `iam`, `lambda`, `cognito`, `api`, `monitoring`.
- DynamoDB: `aws_dynamodb_table.orders`, PAY_PER_REQUEST, primary key pk/sk, GSI1 (INCLUDE projection), NO PITR, NO stream, NO SSE config.
- IAM: Lambda execution role + inline policy (Least Privilege; PutItem/GetItem/UpdateItem/Query on table+GSI1; logs:*) — no Scan/Delete/Batch.
- Lambda: `aws_lambda_function.handler` (python3.14, timeout 10s), env `ORDERS_TABLE`; log group w/ 7-day retention (conditional on monitoring_enabled).
- Cognito: user pool (admin-create-only, password policy, MFA OFF), app client (USER_PASSWORD_AUTH + refresh, no secret), group `staff`.
- API Gateway: HTTP API v2, $default stage auto_deploy, JWT authorizer (Cognito issuer/audience), AWS_PROXY lambda integration (payload 2.0), 4 routes (all JWT), lambda invoke permission scoped to API.
- Monitoring: CloudWatch dashboard + 6 metric alarms (no SNS), using real AWS namespaces.
- Root outputs re-exported; monitoring outputs intentionally not re-exported.
- 0 `moved` blocks (confirmed via grep).
- terraform fmt/validate PASS.

### Confirmed ABSENT (RED)
- **CloudTrail** — none anywhere (grep found zero matches).
- **VPC** — none (no aws_vpc/subnet/sg/nat/igw/route_table).
- **Subnets / AZ / network variables** — none.
- **Backend config** — none; state is local. `terraform.tfstate` is 0 bytes (empty). `.terraform.lock.info` present (init only).
- **Explicit encryption config** — none (no KMS/SSE). AWS-managed defaults only.
- **DynamoDB PITR / backups / streams** — none (stream output exists but stream_enabled not set).
- **`terraform.example.tfvars`** — referenced in README/.gitignore but DOES NOT EXIST on disk.
- **Screenshots (PNG/JPG/etc.)** — none; only `architecture/architecture-diagram.svg`.

### Confirmed PARTIAL
- Transport: API Gateway uses HTTP protocol (`protocol_type = "HTTP"`) — HTTP, not HTTPS custom domain/TLS (no `aws_apigatewayv2_domain_name`). JWT issuer is HTTPS (Cognito) but API endpoint is plain HTTP.
- Error handling: strong in Lambda (validation/not-found/conflict/transition errors), but no DynamoDB throttling/retry/timeout-specific handling.

## 8. Files Changed

**NONE** (audit is read-only). This execution log is the only new file created, per the audit brief's mandatory execution-log requirement.

## 9. AWS Changes

**NONE** (no apply/destroy/resource create/delete).

## 10. Git Changes

**NONE** (no commit, no push, no add, no revert).

## 11. Open Questions

- Whether a `terraform apply` is scheduled for the Friday demo (currently "no apply performed").
- Desired HTTPS vs HTTP for the demo (HTTP currently; converting needs domain + ACM cert).

## 12. Risks

- No CloudTrail → API activity not auditable (WHO/WHAT/WHEN/WHERE unanswered).
- Local-only Terraform state → no remote state with locking; DR risk.
- State file empty → a fresh deployment will recreate everything from scratch (expected for first deploy).
- No network layer → relies entirely on AWS-managed serverless security.

## 13. Recommended Next Actions

1. Add CloudTrail (management + data events) — RED gap, security/audit.
2. Decide/adopt S3 backend + DynamoDB lock for Terraform state (DR/reproducibility).
3. Document HTTPS vs HTTP decision for demo; add custom domain if HTTPS required.
4. Add DynamoDB PITR if data recovery is a requirement.
5. Perform live `terraform apply` + AWS verification (needs human approval).
6. Produce AWS Console evidence/screenshots for Friday demo.

## 14. Resume Point

Audit complete. Next session can start from section 18 (Final Report) + gap remediation planning, or directly with a human-approved `terraform apply`.

---

**FILES CHANGED: NONE (except this log)**
**AWS CHANGES: NONE**
**GIT CHANGES: NONE**

---

# MILESTONE — AWS ARCHITECTURE + SECURITY DEFINITION (FULL EXECUTION)

> This is the FIRST full execution of the original AWS Architecture + Security Definition.
> Read-only assessment + documentation. No Terraform redesign, no apply/destroy, no commit/push.

## 1. Plan (initial)

Assess the actual project against the full architecture/security definition, capturing:
inventory, network topology, public/private classification, encryption, monitoring/audit,
DynamoDB security, DR, scaling, Terraform mapping — and document in a consolidated form.

## 2. Recovery / pre-state (verified)

- Branch `main`, HEAD `150f9d6`; `origin/main` = `e1d80e6` (local ahead by uncommitted work).
- Working tree already contained prior uncommitted work: CloudTrail module + docs (T011),
  and pre-existing `T011-11-CLOUDWATCH-MONITORING-EXECUTION-LOG.md` modification.
- CloudTrail already implemented (T011) and production-hardening planned (deferred) — NOT repeated here.

## 3. Key architecture/security findings (verified against repo)

- **VPCs = 0**; **public subnets = 0**; **private subnets = 0**. No IGW/NAT/VPC endpoints/
  security groups/NACLs/EC2. (ADR-006 explicitly excludes VPC/NAT.)
- **Region = eu-central-1** (`var.aws_region`), single region; **no multi-Region**.
- **Lambda** NOT in any VPC (no `vpc_config`); runs in AWS-managed execution env.
- **DynamoDB**: AWS-managed regional service; On-Demand (`PAY_PER_REQUEST`); reached via AWS SDK/TLS (not a VPC endpoint); AWS-managed SSE (no explicit config); **no PITR/backups/streams**.
- **API Gateway HTTP API** (`protocol_type = "HTTP"`): application protocol is HTTP; JWT authorizer (Cognito). No custom domain/ACM → application served over HTTP (prototype). AWS service transport is TLS (AWS edge).
- **Cognito**: user pool (admin-create, password policy, MFA OFF), public client `USER_PASSWORD_AUTH`, group `staff`.
- **CloudWatch** = operational monitoring (Lambda log group 7-day retention, dashboard, 6 alarms).
- **CloudTrail** = audit trail: multi-region, management events read+write, global service events, log-file validation, S3 destination (SSE-S3 AES256, public-access-block, BucketOwnerEnforced, least-privilege policy). Data events NOT enabled.
- **IAM**: single least-privilege execution role (`PutItem/GetItem/UpdateItem/Query` on table+GSI1; `logs:*`), plus API-GW→Lambda resource-based invoke permission. No user IAM/access-keys.
- **Encryption at rest** (persisted data): DynamoDB (AWS-managed default SSE), CloudTrail S3 (explicit SSE-S3), CloudWatch logs (AWS-managed). Deemed sufficient for prototype; KMS = deferred/optional.
- **Encryption in transit**: AWS service/API endpoints TLS (SigV4 + HTTPS). Application (API GW) = HTTP (documented, not redesigned).

## 4. Actions (this milestone)

- Created consolidated document `architecture/architecture-and-security.md`.
- Ran safe Terraform checks: `fmt -check`, `validate`, `plan` (read-only).

## 5. Result

Documentation produced; validation PASS; no infrastructure changed.

## 6. Screenshot evidence

**NOT AVAILABLE** — reason: no `terraform apply` performed; zero AWS resources exist
(state empty; all services CONFIGURED but NOT CREATED). Required later (after human-approved apply).

## 7. Files changed (this milestone)

- NEW `architecture/architecture-and-security.md` (consolidated A–L sections)
- MOD `docs/reports/CURRENT-INFRA-AUDIT-EXECUTION-LOG.md` (this file)

## 8. Git / AWS actions

NONE (no apply/destroy/commit/push). Only docs added.

## 9. Deferred / optional items (NOT implemented)

KMS/SSE-KMS, DynamoDB data events, S3 lifecycle, SNS/EventBridge eventing, MFA Delete (CloudTrail hardening);
DynamoDB PITR; S3 state backend + DynamoDB lock; HTTPS/custom domain; group authorization in Lambda.

## 10. Open gaps / follow-up tasks (documented in `architecture-and-security.md` §J)

1. Human-approved `terraform apply` + live verification.
2. S3 state backend + DynamoDB lock.
3. HTTPS/custom domain + ACM (if demo needs TLS).
4. DynamoDB PITR (if recovery required).
5. CloudTrail production hardening (KMS → data events → lifecycle → eventing → MFA Delete).
6. Lambda group authorization (cognito:groups, Week-3 scope).
7. Screenshot evidence after apply.

## 11. Resume point

Full architecture/security assessment complete. Next = execute follow-up tasks §10 in listed order.