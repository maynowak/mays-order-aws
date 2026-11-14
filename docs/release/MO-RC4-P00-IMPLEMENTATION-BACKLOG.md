# MO-RC4-P00 Implementation Backlog

**Status:** DRAFTED / Q-02 + Q-04 + Q-08 + Q-09 + Q-10 APPROVED / P00-B INTEGRATED / P00-C LOCALLY INTEGRATED / CODE VERIFIED / AWS LIVE TEST DEFERRED / P00-D PLANNING READY
**Reference:** `docs/contracts/MO-RC4-P00-IMPLEMENTATION-CONTRACT.md`
**Baseline:** `086a8be`
**Branch:** `release/rc4-integration`

> **Owner update 2026-11-13:** Q-02 (Secrets Manager), Q-04 (CMK
> default/external/opt-in), Q-08 (ARN/name reference + runtime fetch), Q-09
> (explicit Policy-Gate allowlist) and Q-10 (ADR-008 after C-01…C-07) are
> approved. ADR-008 is `ACCEPTED`. P00-B is integrated via merge `e71f3ed` and
> post-merge verified. P00-C is ready for a separate implementation
> authorization; P00-C-M01 and the L-findings remain mandatory acceptance
> criteria. No other package may begin production implementation.

---

## Dependency Graph

```text
P00-A (this contract)
  ├─ P00-B SecretProvider Foundation
  │    ├─ P00-C AWS_MANAGED / Secrets Manager
  │    │    └─ P00-F Rotation (after Q-11)
  │    └─ P00-D APP_MANAGED / Versioned HMAC
  ├─ P00-E KMS / Terraform / IAM
  │    └─ depends on Q-04, Q-09, Q-10, P-15
  ├─ P00-G Retention / TTL
  │    └─ depends on Q-06, Q-07, Q-14
  └─ P00-H Installer / Builder
       └─ depends on P00-B/C/E and Q-03
P00-I Security / Regression / Release Gates
  └─ depends on all implemented packages
```

Recommended implementation order:

```text
P00-B → P00-C → P00-E → P00-H → P00-D → P00-F → P00-G → P00-I
```

The order may change only with documented dependency justification.

---

## P00-B — SecretProvider Foundation

| Field | Content |
|---|---|
| Goal | Provider abstraction with `env` default and fail-closed resolution |
| Dependencies | P00-A; Q-08 (configuration shape), Q-10 (ADR approval) |
| Components | `lambda/src/secret_provider.py` (proposed), privacy auth adapter |
| Config contract | `PRIVACY_SECRET_PROVIDER`, references, no fallback |
| Acceptance | ENV bit-compatible; provider selection tested; no secrets in logs/errors |
| Negative tests | unknown provider, missing ref, conflicting refs, provider failure |
| Migration risk | accidental behavior change; mitigate with default-off and regression tests |
| Security boundary | no secret values in response/log; no request-controlled reference |
| Commit boundary | provider foundation + tests + docs only |
| Owner approval | Q-08 approved; Q-10 approved |
| Package status | **INTEGRATED / POST-MERGE VERIFIED** — merge `e71f3ed`; 1.208 local PASS + 28 Seed |
| Actual components | `lambda/src/secret_provider.py`, provider wiring in `order_service.py`, 34 provider/security tests, rebuilt ZIP |

**Do not include:** Secrets Manager IAM/IaC, APP HMAC, rotation, retention.

---

## P00-C — AWS_MANAGED / Secrets Manager

| Field | Content |
|---|---|
| Goal | Secrets Manager-backed provider with optional CMK reference |
| Dependencies | P00-B; Q-02, Q-04, Q-08, Q-09, Q-10 |
| Components | `terraform/modules/privacy_secret`, handler env references, IAM |
| Config contract | `PRIVACY_SECRET_ID`, no plaintext env secret |
| Acceptance | exact-ARN access; default-off; no secret in state/output; fail-closed |
| Negative tests | ResourceNotFound, AccessDenied, timeout, wrong ARN/project |
| Migration risk | secret in state/plan if ephemeral misuse; DDB/SQS not touched |
| Security boundary | least privilege, exact ARN, no fallback to ENV |
| Commit boundary | IaC + provider tests + contract docs; no APP/rotation |
| Owner approval | Q-02/Q-04/Q-08/Q-09/Q-10 approved |
| Package status | **LOCALLY INTEGRATED / CODE VERIFIED / AWS LIVE TEST DEFERRED** — F-01/F-03 verified fixed; deployment gates open |

### P00-C-M01 — Effective SecretProvider Cache Lifetime

| Field | Content |
|---|---|
| Status | **IMPLEMENTED / TESTED / HANDLER-TEST VERIFIED — F-02 deployment gate open** |
| Source | `MO-RC4-P00-B-INTEGRATION-REVIEW-01` finding M-01 |
| Problem | P00-B `SecretCache` was owned by a per-invocation `OrderService`; effective scope was one invocation. |
| Implemented scope | Module-level `get_default_secret_provider()` shared by `OrderService`; provider/cache survives invocations in one execution environment. |
| Identity isolation | Cache key includes provider, exact reference, key ID/version, KMS ARN and injected-fetcher identity; cross-identity tests pass. |
| Rotation | `SecretCache.invalidate()` and `reset_default_secret_provider()` provide controlled invalidation; rollout is documented. |
| Tests | Cross-invocation hit, config replacement, identity isolation, invalidation and error non-caching tests pass. |
| Gate | Implemented/tested and independently re-reviewed; F-02 remains a deployment gate. |

### P00-C review acceptance criteria

| ID | Criterion | Status |
|---|---|---|
| L-01 | Non-ASCII resolved material/token must not produce an unhandled `TypeError`/500; validate or map fail-closed. | **IMPLEMENTED / TESTED** |
| L-02 | Provider failures need sanitized observability without ARN/reference/secret values. | **IMPLEMENTED / TESTED** |
| L-03 | `PRIVACY_KMS_KEY_ARN` must have a tested runtime effect when CMK is selected, or be rejected until implemented. | **IMPLEMENTED / TESTED** — `DescribeSecret` required for CMK |
| L-04 | Add negative tests for lazy provider initialization, request-context isolation and actual redaction. | **IMPLEMENTED / TESTED** |
| L-06 | Document/test the atomic provider switch (set provider + remove plaintext env/reference). | **DOCUMENTED / LOCAL TESTS** |

These criteria are not P00-B merge blockers, but must be evidenced before
P00-C integration.

### Security Review 03 conditions — correction status

| ID | Severity | Status | Merge blocker |
|---|---|---|---|
| F-01 | MEDIUM | **VERIFIED FIXED**; Q-09 limited amendment approved; ADR/Contract/Policy-Gate spec updated; runtime matches (DescribeSecret only with `PRIVACY_KMS_KEY_ARN`) | NO |
| F-02 | MEDIUM | **DOCUMENTED** in rollout: cache lifetime, forced environment recycle, parallel-generation risk; no auto rotation | NO (deployment gate) |
| F-03 | MEDIUM | **VERIFIED FIXED** by `test_index_aws_managed.py` (5 handler-level tests) and mutation proof | NO |
| F-04 | MEDIUM | **DOCUMENTED** exact SecretString payload: ASCII, 1…1024, no JSON | NO (activation gate) |
| F-05 | MEDIUM | **DOCUMENTED** two rollback paths (forward-fix / owner-approved ENV) | NO (activation gate) |
| F-06 | LOW | **OPEN** — timeout values require Owner/Infra decision | NO |
| F-07 | LOW | **OPEN** — pre-existing type coercion; no realistic bypass demonstrated | NO |
| F-08 | LOW | **OPEN** — sanitized AWS error code is observability follow-up | NO |
| F-09 | LOW | **INTEGRATED — P00-E** — Policy-Gate allowlist/inline-IAM wildcard check; verification follows P00-E integration | NO (P00-E gate) |
| F-10 | LOW | **OPEN/INFO** — single-thread Lambda assumption documented | NO |
| F-11 | LOW | **OPEN/INFO** — `id()` is production-None; test-only risk | NO |
| F-12 | LOW | **DOCUMENTED** — P00-C runtime scope vs P00-E IaC/IAM | NO |

---

## P00-D — APP_MANAGED / Versioned HMAC

| Field | Content |
|---|---|
| Goal | External key material with HMAC-SHA256 and explicit key version |
| Dependencies | P00-B; Q-10; Q-11 if rotation/versions included |
| Components | APP key adapter, canonical HMAC payload, keyId/keyVersion |
| Config contract | external key reference; key ID/version; no AWS KMS implied |
| Acceptance | valid/invalid HMAC fail-closed; old version only in approved window |
| Negative tests | wrong key, bad Base64/length, missing version, rollback |
| Migration risk | key loss or version mismatch; require dual-version transition |
| Security boundary | no custom cipher; no key in data/items/logs |
| Commit boundary | APP adapter + tests + docs |
| Owner approval | Q-10 approved; Q-11 P00-D contract approved; P00-F rotation pending |
| Package status | **LOCALLY INTEGRATED / POST-MERGE VERIFIED / DEFAULT-OFF** — not deployed/activated |
| Implemented components | `lambda/src/hmac_contract.py`, additive `AppManagedProvider.resolve_key/verifier`, local injected loader |
| Key contract | 32-byte Base64, HMAC-SHA256, unique `keyId`/`keyVersion`; no custom cipher |
| Payload | `MOAPP` + version/alg + length-prefixed keyId/keyVersion/messageType/payload |
| Rotation | P00-F only; max active + one previous, max 24h explicit window |
| Open readiness items | production key transport; P00-F rotation/revocation; existing signatures; R6-L01 dependency-test harness; installer live test deferred |
| Review follow-up | R5-L01 wrong-key test **FIXED** by `73bd07c` |

---

## P00-E — KMS / Terraform / IAM

| Field | Content |
|---|---|
| Status | **LOCALLY INTEGRATED / VERIFICATION INCOMPLETE** — merge `3b0de2f`; known installer harness exceptions + deferred live test; no plan/apply/deployment |
| Goal | Optional AWS_MANAGED Secrets Manager container with least privilege; optional existing CMK reference only |
| Dependencies | Q-04, Q-09, Q-10; P00-C for secret option |
| Components | `terraform/modules/privacy_secret`, count-gated IAM/Lambda wiring, Q-09 Policy Gate |
| Config contract | `privacy_secret_enabled=false` default; optional exact `privacy_kms_key_arn`; no secret value in Terraform |
| Acceptance (minimal) | no resource by default; no KMS key created; exact Secret/KMS ARNs; no wildcard; static validate PASS |
| Negative tests | foreign secret name, wildcard KMS ARN, inline IAM wildcard actions/resources |
| Migration risk | only opt-in resource creation; no DDB/SQS/API/Cognito/CloudFront changes |
| Security boundary | exact ARN; no secret value/version in Terraform; no CMK for unrelated services; APP_MANAGED unchanged |
| Commit boundary | module + wiring + policy tests + local validation; no plan/apply |
| Owner approval | Q-04, Q-09; Q-10 approved; integration and deployment gates separate |
| Excluded | DDB/SQS CMK activation, KMS key creation/rotation, P00-F rotation/revocation |

---

## P00-F — Rotation

| Field | Content |
|---|---|
| Status | **LOCALLY IMPLEMENTED** — `dad5b16`; APP_MANAGED rotation/revocation mechanics, default-off; operational activation remains Owner-gated |
| Goal | Documented, owner-controlled rotation and cache invalidation |
| Dependencies | P00-C/D/E; Q-11 |
| Components | Secrets Manager rotation or manual runbook; cache invalidation |
| Config contract | rotation flag/default off; transition window decision |
| Acceptance | old/new version semantics documented; failed rotation fail-closed |
| Negative tests | missing pending version, stale cache, concurrent read |
| Migration risk | breaking active Lambda sessions if cache not invalidated |
| Security boundary | no automatic old-key deletion; audit without secret values |
| Commit boundary | rotation adapter/runbook + tests |
| Owner approval | Q-11; transition window and responsibility |

---

## P00-G — Retention / TTL

| Field | Content |
|---|---|
| Status | **BLOCKED BY OWNER DECISION / SAFELY DISABLED** — Q-05/Q-06/Q-07/Q-14 open; no retention fields, TTL, deletion or backfill implemented |
| Goal | Define and implement retention mechanics without inventing legal periods |
| Dependencies | P00-A; Q-05, Q-06, Q-07, Q-14 |
| Components | `retentionUntil`, optional TTL, cancel semantics, docs |
| Config contract | retention fields/flags; default decision required |
| Acceptance | fachliche Frist and TTL clearly separated; no synchronous-delete claim |
| Negative tests | missing field, expired item, cancel, RETAIN, backup restore scenario |
| Migration risk | legacy items have no field; no implicit default deletion |
| Security boundary | PII minimization; ERASE/ANONYMIZE/RETAIN unchanged |
| Commit boundary | model/validation/tests/docs; no backfill unless separately approved |
| Owner approval | Q-05, Q-06, Q-07, Q-14 |

---

## P00-H — Installer / Builder

| Field | Content |
|---|---|
| Status | **LOCALLY COMPLETE** — Installer stabilized; complete preset includes `privacy_secret`; deterministic builder tree and generated Terraform validate PASS |
| Goal | Safe configuration of provider/KMS/retention modules for new and existing installs |
| Dependencies | P00-B/C/E/G; Q-03, Q-08, Q-09 |
| Components | installer flags/validation, builder catalog/preset, manifest |
| Config contract | defaults off; no secrets in CLI/manifest/state |
| Acceptance | existing installs unchanged; no forced replacement; errors redacted |
| Negative tests | incompatible flags, missing key/secret, bad upgrade plan |
| Migration risk | flag combinations; module stripping; state drift |
| Security boundary | no secret values in argv/state/plan; no implicit CMK |
| Commit boundary | installer/builder code + tests + docs |
| Owner approval | Q-03, Q-08, Q-09 |

---

## P00-I — Security / Regression / Release Gates

| Field | Content |
|---|---|
| Status | **LOCAL REGRESSION PASSED** — 440 Lambda / 674 Installer (1 skipped) / 129 Builder / 23 Policy / 36 E2E (5 skipped) / 28 Seed; Terraform validate PASS; deployment gates open |
| Goal | Verify full P00 implementation and release boundaries |
| Dependencies | all implemented packages |
| Components | secret/HMAC/KMS tests, log/state audits, installer/builder gates |
| Acceptance | no secret leakage; default-off compatibility; full local regression |
| Negative tests | every fail-closed path, cross-provider fallback, state leak |
| Migration risk | residual migration/drift; must be explicit in release notes |
| Security boundary | no AWS mutation during local verification |
| Commit boundary | test/evidence/docs only |
| Owner approval | Q-12, release gate |

---

## Cross-Package Acceptance

- `env` default unchanged.
- No provider fallback.
- No secret in Git, logs, reports, Terraform outputs/state.
- No automatic CMK creation.
- No automatic rotation.
- No legal retention periods invented.
- No DDB/SQS resource replacement.
- No RIS/Jobfront/Jobsearch changes.
- Existing 1.174 local regression remains green at every package boundary.

---

## Commit / Review Boundaries

Each package must be a separate commit (or small, logically bounded series)
with:

1. contract diff,
2. implementation diff,
3. focused tests,
4. negative tests,
5. auditlog update,
6. `git diff --check`,
7. no AWS/Terraform mutation,
8. working tree clean.

No package may bundle unrelated RC4 changes or a release tag.
