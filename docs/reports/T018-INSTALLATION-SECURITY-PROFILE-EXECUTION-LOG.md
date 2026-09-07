# T018 INSTALLATION SECURITY PROFILE — Execution Log

> **Task:** Installation decision — SECURITY PROFILE (sixth decision in the installation
> sequence, after T013–T017).
> **Mode:** PLANNING / DOCUMENTATION ONLY — **no `terraform apply`, no `destroy`, no
> commit/push.**
> **Date:** 2026-09-03

---

## 1. Task identification

T018 — Installation Decision: SECURITY PROFILE. Continues from T013/T014/T015/T016/T017
(COMPLETE).

## 2. Start state (verified)

- Branch: `main`
- HEAD: `4c4c4c27d0847b9169654ea0db35ad805e942da1` (policy-gate commit)
- Terraform CLI: v1.15.8; AWS provider `~> 6.0` (lock 6.60.0)
- No AWS credentials used (no `apply`; only provider-agnostic `validate`/`plan`).

## 3. T017 baseline

- T017 status COMPLETE; data strategy single-region DynamoDB, no replication, PITR/KMS/streams
  deferred. Terraform baseline: `fmt` PASS, `validate` PASS, `plan` 30/0/0. ✅

## 4. Repository verification (verified, read-only)

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
?? docs/reports/T017-INSTALLATION-DATA-STRATEGY-EXECUTION-LOG.md
?? security/cloudtrail-design.md
?? terraform/modules/cloudtrail/
```

## 5. Existing worktree state

- ` D docsMaysOrdersAws.zip` — deleted, not staged; pre-existing / unexplained; **not touched**.
- Policy-gate files now committed in `4c4c4c2` (no longer untracked); preserved, not touched.
- `main` has no upstream; ahead of `origin/main`. Not investigated/pushed (per task).

## 6. Authentication verification (verified, `modules/cognito/main.tf`)

- User pool `aws_cognito_user_pool.users`: `admin_create_user_only = true` (no open self-signup);
  password policy min 8 + require lowercase/uppercase/number/symbol; `mfa_configuration = "OFF"`.
- App client: `explicit_auth_flows = [ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH]`,
  `generate_secret = false` (public client).
- Group `staff` (`aws_cognito_user_group.staff`).

## 7. Authorization verification

- **API Gateway (verified, `modules/api/main.tf`):** JWT authorizer
  (`authorizer_type = "JWT"`, `identity_sources = $request.header.Authorization`, issuer =
  `https://<cognito endpoint>`, audience = app-client ID). All four routes have
  `authorization_type = "JWT"` + `authorizer_id` → **all protected**, no public routes.
- **Application/group authorization:** `cognito:groups` evaluation in the Lambda handler is
  **NOT implemented** (documented in `terraform/README.md` §2.5; A-09 → Week 3). Identified gap,
  not invented/implemented here.

## 8. IAM verification (verified, `modules/iam/main.tf`, `modules/api/main.tf`)

- Lambda execution role `aws_iam_role.handler` (trust `lambda.amazonaws.com`) + inline policy:
  `dynamodb:PutItem/GetItem/UpdateItem/Query` on table + GSI1 only; `logs:CreateLogGroup/
  CreateLogStream/PutLogEvents`. **No** `Scan/Delete/Batch/CreateTable`, no `s3:*`, no `iam:*`,
  **no `iam:PassRole`**, no `AdministratorAccess`.
- API GW → Lambda: `aws_lambda_permission` (principal `apigateway.amazonaws.com`, `source_arn`
  scoped to this API's execution ARN `/*/*`), separate from the execution role.
- Terraform developer permissions: not encoded in any Terraform module (external human/CI
  identity).

## 9. Permissions boundary verification

- `MaysOrders-Terraform-Developer-Boundary` is referenced in the Policy Gate docs
  (`docs/TERRAFORM_POLICY_GATE.md`), **not** in the Terraform modules. Treated as **optional
  security hardening** constraining the deployment identity; not a May's-Orders application
  requirement. Not redesigned.

## 10. Encryption verification

- DynamoDB: no `server_side_encryption` block → AWS-managed default at-rest encryption (no
  customer-managed KMS).
- CloudTrail S3: explicit `aws_s3_bucket_server_side_encryption_configuration` with
  `sse_algorithm = "AES256"` (SSE-S3), plus `BucketOwnerEnforced` + public-access-block (4 flags).
- No customer-managed KMS anywhere.

## 11. Transport security verification

- HTTP API V2 (`protocol_type = "HTTP"`). No `aws_apigatewayv2_domain_name`, no ACM cert, no
  custom domain. AWS-managed API-Gateway endpoint provides TLS/HTTPS at the AWS edge. Custom
  domain/ACM deferred/optional.

## 12. Audit / logging verification

- CloudWatch (lambda module): Lambda log group, 7-day retention (conditional on
  `monitoring_enabled`); dashboard + 6 alarms (T011-11).
- CloudTrail (`modules/cloudtrail/main.tf`): `is_multi_region_trail = true`,
  `include_global_service_events = true`, management events `read_write_type = "All"`,
  `enable_log_file_validation = true`, `enable_logging = true`; S3 destination with SSE-S3,
  public-access-block, least-privilege bucket policy (`PutObject` restricted to CloudTrail
  service + account/Region prefix + SourceArn).
- **Deferred CloudTrail hardening (→ T019):** SSE-KMS, DynamoDB data events, S3
  lifecycle/retention, SNS/EventBridge eventing, MFA Delete.

## 13. Network security verification

- No VPC/subnets/SG/NACL/NAT/IGW (see T016). Absence of VPC is not a security failure for
  managed serverless. No custom network layer; not introduced here.

## 14. Security profile decision

- **Profile: `LOW / PROTOTYPE`.** Baseline controls present (IAM least privilege, Cognito auth +
  JWT validation, managed encryption, CloudWatch + CloudTrail). Stronger controls deferred.
- "LOW" ≠ insecure: it is the deliberate prototype baseline consistent with `LOWEST/PROTOTYPE`.

## 15. Cost relationship

- `LOWEST/PROTOTYPE` → `LOW`. Deferred higher-cost/complexity controls (KMS, data events,
  WAF/GuardDuty/Security Hub, custom domain, longer retention) are not introduced. No existing
  control removed for cost reasons.

## 16. Deferred hardening (→ T019 Optional Features / later)

Group authorization (`cognito:groups`), customer-managed KMS, CloudTrail data events + SSE-KMS +
lifecycle + eventing + MFA Delete, custom domain/ACM (app TLS), WAF/GuardDuty/Security Hub,
extended log retention.

## 17. Terraform implementation decision

- **No Terraform change (outcome A).** Current architecture already represents `LOW/PROTOTYPE`
  security. No AdministratorAccess, no wildcards, no KMS, no VPC, no WAF/GuardDuty introduced.

## 18. Files changed (this task)

- MOD `architecture/installation-concept.md` — header status (T018 note) + new §3.5 (Security
  Profile decision).
- MOD `terraform/README.md` — header "Stand T018" note + §9.4 Future-Work list update
  (Security Profile moved to "Definiert") + new §9.9 (Security Profile).
- NEW `docs/reports/T018-INSTALLATION-SECURITY-PROFILE-EXECUTION-LOG.md` (this file).

No `.tf` files changed.

## 19. Validation (actually executed)

| Check | Result |
|-------|--------|
| `terraform fmt -check -recursive` | PASS (exit 0) |
| `terraform validate` | PASS ("The configuration is valid.") |
| `terraform plan` | PASS — **30 to add, 0 to change, 0 to destroy** |

## 20. Terraform plan result

- **30 to add, 0 to change, 0 to destroy** — identical to T017/T016/… baseline. No `.tf` change
  in T018 → count unchanged. `apply`/`destroy` NOT run.

## 21. Git status (after this task)

- Branch: `main`; HEAD: `4c4c4c2`.
- **T018-introduced:** modifications to `architecture/installation-concept.md` and
  `terraform/README.md` + this new execution log.
- **Pre-existing / unrelated (preserved):** ` D docsMaysOrdersAws.zip`; the modified/untracked
  set in §4; committed policy-gate work `4c4c4c2`.

## 22. Deployment status

- `terraform apply` — NOT EXECUTED.
- `terraform destroy` — NOT EXECUTED.
- Commit / push / add / reset / stash / restore / checkout / clean — NONE.

## 23. Final verified state

- Security profile defined: `LOW / PROTOTYPE`, IAM least privilege, Cognito + JWT on all routes,
  managed encryption, CloudWatch/CloudTrail audit; group authorization, KMS, data-events and
  hardening deferred to T019. No Terraform change; plan 30/0/0 unchanged.

## 24. Resume point

Security Profile decision COMPLETE. Next installation decision:

```
COST ✅ → REGION ✅ → AVAILABILITY ✅ → DATA ✅ → SECURITY ✅ (T018) → OPTIONAL FEATURES (T019)
```

Read `architecture/installation-concept.md` §3.5 and `terraform/README.md` §9.9 first.

---

**FILES CHANGED:** `architecture/installation-concept.md`, `terraform/README.md`,
NEW `docs/reports/T018-INSTALLATION-SECURITY-PROFILE-EXECUTION-LOG.md`
**AWS CHANGES: NONE** · **GIT CHANGES: NONE** (no commit/push)
**PRE-EXISTING DISCREPANCY:** `docsMaysOrdersAws.zip` deleted (unexplained, untouched);
`4c4c4c2` (policy-gate) preserved, not pushed.