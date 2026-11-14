# MO-RC4-P00 Execution Plan

**Status:** EXECUTION PLAN READY / Q-02 + Q-04 + Q-08 + Q-09 + Q-10 APPROVED / P00-B INTEGRATED / P00-C INTEGRATED / VERIFICATION PARTIAL (1 live test blocked)
**Base:** `release/rc4-integration` @ `8ddc0503a851533c71027fcb122fe9f62f89dc4f`
**Feature base:** `feature/mo-rc4-p00-b-secret-provider` branched from `8ddc0503a851533c71027fcb122fe9f62f89dc4f`
**RC3 Baseline:** `086a8bea4c608724d400de834c21df5456b7ccac`
**Reference:** `docs/release/MO-RC4-P00-DECISION-REGISTER.md`

> Q-02, Q-04, Q-08, Q-09 and Q-10 are owner-approved. P00-B is integrated on
> `release/rc4-integration` (merge `e71f3ed`) and post-merge verified.
> P00-C is integrated on `release/rc4-integration` (merges `e743170` and
> `442d296`). F-03/F-01 are verified fixed. All local code suites pass; one
> live AWS profile test is blocked by the no-AWS boundary. F-02/F-04/F-05 and
> all other deployment gates remain open. P00-D/E/G remain separately gated.

---

## 1. Agent Structure

| Agent | Role | Write access | Output |
|---|---|---|---|
| Commander | coordination, consolidation, docs, Git | docs only | reports/commits |
| Architecture Agent | contract consistency | read-only | decision review |
| Security Agent | secrets/KMS/IAM/threat model | read-only | security findings |
| Privacy Agent | retention/TTL/erase/cancel | read-only | privacy contract |
| Infrastructure Agent | Terraform/Installer/Builder | read-only | integration review |
| Compatibility Agent | RC3/RC4 contracts | read-only | compatibility report |
| QA Agent | test strategy/gates | read-only | test matrix |

Read-only agents do not commit. Commander serializes all writes and commits.

---

## 2. Global Preconditions

Before any implementation package:

```text
[ ] required Q decisions closed in Decision Register
[ ] ADR-008 status resolved
[ ] approved release/rc4-integration HEAD fixed
[ ] feature branch created from that HEAD
[ ] no unrelated uncommitted changes
[ ] no AWS/Terraform mutation unless separately authorized
[ ] auditlog entry created for the package
```

---

## 3. Package P00-B — SecretProvider Foundation

**Goal:** Provider abstraction with `env` default and fail-closed resolution.

**Status:** **INTEGRATED / POST-MERGE VERIFIED** — merge commit
`e71f3edcb146fb7b3943b4c23fa65e771cf4611e`; 1.208 local PASS + 28 Seed.

**Non-goals:** no Secrets Manager IaC, no KMS, no APP HMAC, no rotation, no
retention.

**Inputs:** Q-08 (approved 2026-11-13), Q-10 (approved 2026-11-13);
`MO-RC4-P00-IMPLEMENTATION-CONTRACT.md`.

**Affected files (actual):**

```text
lambda/src/secret_provider.py
lambda/src/order_service.py
lambda/tests/test_secret_provider.py
lambda/dist/lambda.zip
```

**Config contract:** provider selection, reference validation, no fallback,
no request-controlled reference.

**Acceptance:**

- `env` path bit-compatible.
- unknown/missing provider fails closed.
- no secret in logs/errors.
- cache behavior tested.
- no AWS dependency in unit tests.

**Negative tests:** missing secret, unknown provider, conflicting references,
provider failure, log redaction.

**Integration gate:** SG-01, SG-02, SG-06, SG-08; full local regression.

**STOP:** integration/merge approval missing; any owner decision missing; any
fallback required to pass tests.

---

## 4. Package P00-C — AWS_MANAGED / Secrets Manager

**Goal:** Optional Secrets Manager provider and reference-only configuration.

**Status:** **INTEGRATED / VERIFICATION PARTIAL** — merge commits `e743170` and
`442d296`; F-01/F-03 verified fixed; 1.233 local PASS + 1 live-profile test
blocked; 28 Seed.

**Re-Review 06:** F-03 is verified by `test_index_aws_managed.py` and a
mutation check; F-01 is verified against ADR/Contract/Q-09 and runtime.
F-02/F-04/F-05 remain documented deployment gates. No CRITICAL/HIGH finding.

**Dependencies:** P00-B; Q-02 (approved), Q-04 (approved: AWS default/existing
ARN/opt-in CMK), Q-08 (approved), Q-09 (approved: explicit allowlist/default
deny), Q-10 (approved; C-01…C-07 incorporated).

**Mandatory acceptance conditions:** `P00-C-M01` effective cache lifetime,
L-01 non-ASCII material handling, L-02 provider observability, L-03 KMS-ARN
runtime effect, L-04 test hardening, L-06 atomic provider rollout.

**Affected files (proposed):**

```text
terraform/modules/privacy_secret/{main.tf,variables.tf,outputs.tf}
terraform/main.tf; terraform/variables.tf; terraform/outputs.tf
terraform/modules/iam/main.tf
terraform/policy/resource-policy.json
lambda/src/secret_provider.py
lambda/src/order_service.py
lambda/tests/test_secret_provider.py
```

**Acceptance:**

- default plan unchanged;
- explicit provider uses exact Secret ARN;
- no plaintext in env/state/output;
- IAM `GetSecretValue` exact ARN;
- `kms:Decrypt` only for an actual customer CMK;
- explicit default-deny Policy-Gate allowlist;
- no implicit CMK creation; no change to existing encryption by activation;
- `AccessDenied`/not-found fail-closed;
- no ENV fallback;
- M-01/L-01…L-04/L-06 acceptance conditions evidenced;
- F-03 handler test and mutation proof evidenced;
- F-01 Owner decision pending; F-02/F-04/F-05 documented as deployment gates.

**Negative tests:** wrong ARN, missing secret, wrong IAM, missing provider,
secret value absent from plan/state/output/logs.

**Integration gate:** SG-01, SG-03, SG-06, SG-07, SG-08.

---

## 5. Package P00-D — APP_MANAGED / Versioned HMAC

**Goal:** External key material with explicit key ID/version and HMAC-SHA256.

**Dependencies:** P00-B; Q-10, Q-11.

**Affected files (proposed):**

```text
lambda/src/app_key_provider.py
lambda/src/order_service.py / identity adapter
lambda/tests/test_app_key_provider.py
```

**Acceptance:**

- no custom cipher;
- valid key/version accepted;
- wrong version/format fail-closed;
- HMAC comparison constant-time;
- key material never logged;
- old-version transition only after owner-approved window.

**Negative tests:** bad Base64/length, wrong key, missing version, expired
version, rollback/recovery.

**Integration gate:** SG-01, SG-02, SG-04, SG-08.

---

## 6. Package P00-E — KMS / Terraform / IAM

**Goal:** Optional CMK and encryption wiring for Secrets Manager/DDB/SQS.

**Dependencies:** Q-04, Q-09, Q-10.

**Affected files (proposed):**

```text
terraform/modules/kms/{main.tf,variables.tf,outputs.tf}
terraform/modules/dynamodb/main.tf
terraform/modules/sqs/main.tf
terraform/modules/iam/main.tf
terraform/modules/sqs-worker/iam.tf
terraform/policy/resource-policy.json
```

**Acceptance:**

- no CMK by default;
- key rotation enabled for new CMK;
- key policy least privilege/no wildcard;
- DDB/SQS changes are in-place, no replacement;
- existing AWS-owned encryption not relabelled as CMK.

**Negative tests:** missing key policy, wildcard IAM, external key ARN wrong,
SQS/DDB policy missing, deletion window invalid.

**Integration gate:** SG-03, SG-06, SG-07, SG-08.

---

## 7. Package P00-F — Rotation

**Goal:** Owner-approved rotation mechanics and cache invalidation.

**Dependencies:** P00-C/D/E; Q-11.

**Affected files (proposed):**

```text
lambda/src/rotation_handler.py (only if native rotation approved)
terraform/modules/privacy_secret/rotation.tf
runbooks rotation documentation
tests for transition/error/cache
```

**Acceptance:**

- rotation default off;
- old/new version window documented;
- provider cache invalidates correctly;
- failure leaves a safe, recoverable state;
- no old-key deletion without approval.

**Negative tests:** missing pending version, access denied, timeout, stale
cache, interrupted rotation.

**Integration gate:** SG-04, SG-07, SG-08.

---

## 8. Package P00-G — Retention / TTL

**Goal:** Define/implement retention mechanics without inventing legal periods.

**Dependencies:** Q-05, Q-06, Q-07, Q-14; P00-B serialization.

**Affected files (proposed):**

```text
lambda/src/order_types.py
lambda/src/order_service.py
lambda/src/validation.py
lambda/src/sqs_handler.py
database/ documentation
order-lifecycle/transition-rules.md
```

**Acceptance:**

- `retentionUntil`/TTL semantics explicitly documented;
- TTL not described as synchronous delete;
- cancel behavior matches Q-07;
- legacy data behavior matches Q-14;
- ERASE/ANONYMIZE/RETAIN unchanged;
- no legal period invented.

**Negative tests:** missing field, expired item, cancel, RETAIN, backup/restore
scenario, no implicit deletion.

**Integration gate:** SG-02, SG-05, SG-06, SG-08.

---

## 9. Package P00-H — Installer / Builder

**Goal:** Safe configuration of P00 modules for new and existing installs.

**Dependencies:** P00-C, P00-E, P00-G; Q-03, Q-08, Q-09.

**Affected files (proposed):**

```text
installer/cli/main.py
installer/core/context.py
installer/validation/*
installer/tests/*
module_builder/catalog.py
module_builder/spec.py
module_builder/tests/*
terraform/policy/*
```

**Acceptance:**

- default install unchanged;
- flags optional and validated;
- no secret values in CLI/manifest/state;
- module selection fail-closed;
- `orders-service` contract unchanged;
- no forced resource replacement.

**Negative tests:** incompatible flags, missing key/secret, bad upgrade plan,
module stripping, secret leakage.

**Integration gate:** SG-03, SG-06, SG-07, SG-08.

---

## 10. Package P00-I — Security / Regression / Release Gates

**Goal:** Verify the full P00 implementation and release boundaries.

**Dependencies:** all packages; Q-12, Q-13.

**Acceptance:**

- all local suites PASS;
- all SG-01…SG-08 pass;
- no secret/state/plan leakage;
- Terraform fmt/validate PASS;
- RC3 default compatibility;
- release dossier/evidence updated.

**Negative tests:** fail-closed paths, cross-provider fallback, state leak,
wildcard IAM, rotation failure, retention/TTL ambiguity.

**Integration gate:** SG-01…SG-08; final release review.

---

## 11. Security Gates

| Gate | Acceptance criterion |
|---|---|
| SG-01 Secret Safety | No secrets in Git/reports/logs/state/outputs; negative scan PASS |
| SG-02 Identity & Isolation | No tenant/owner value from request body; existing owner/consumer tests PASS |
| SG-03 KMS/IAM | Exact ARNs, no wildcard KMS, no implicit CMK |
| SG-04 Rotation | Explicit versions/windows/failure/cache tests |
| SG-05 Privacy | Retention/TTL/Erase/Backups separated; no false synchronous-delete claim |
| SG-06 Compatibility | RC3 defaults and existing RC4 contracts unchanged |
| SG-07 Deployment Safety | No unintended replacement; plan review PASS |
| SG-08 Release Evidence | Tests, auditlog, manifest, gates complete |

---

## 12. Feature Branch / Integration Protocol

```text
release/rc4-integration
  ├─ feature/mo-rc4-p00-b-secret-provider
  ├─ feature/mo-rc4-p00-c-aws-managed
  ├─ feature/mo-rc4-p00-d-app-managed
  ├─ feature/mo-rc4-p00-e-kms-terraform
  ├─ feature/mo-rc4-p00-f-rotation
  ├─ feature/mo-rc4-p00-g-retention
  └─ feature/mo-rc4-p00-h-installer-builder
```

Rules:

- Branch only from the current approved `release/rc4-integration` HEAD.
- No parallel writes to the same files.
- Tests and security gates before integration.
- Commander integrates one package at a time.
- No history rewrite, no force-push, no main merge.

---

## 13. Stop Conditions

Stop and request an Owner decision if:

- a required Q decision is still open;
- a security gate cannot be met without a contract change;
- a CMK would be created implicitly;
- a secret would land in Terraform state/output;
- a DDB/SQS replacement is planned;
- a retention period or deletion guarantee must be invented;
- a provider fallback is required;
- a P00 package would modify RIS/Jobsearch.

```text
MO-RC4-P00-ORCHESTRATION-01 — EXECUTION PLAN READY / OWNER APPROVAL PENDING
```
