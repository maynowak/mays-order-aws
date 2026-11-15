# MO-RC4-P00-B — SECURITY & INTEGRATION REVIEW

**Status:** `MO-RC4-P00-B — REVIEW PASS / MERGE AUTHORIZATION PENDING`

**Date:** 2026-11-13

**Feature branch:** `feature/mo-rc4-p00-b-secret-provider` @ `f0ea3b8b11a7387325f94bf09c8b4b4b2e12eaf8`

**Target:** `release/rc4-integration` @ `8ddc0503a851533c71027fcb122fe9f62f89dc4f`

**Review branch:** `review/mo-rc4-p00-b-integration-01`

**Review branch HEAD:** `9de9cfd15610eee7aeb2d795910736681b52ca14`
(a docs-only review commit; feature code remains at `f0ea3b8`)

**Scope:** Read-only security/integration review. No product code, merge, push,
Terraform, AWS, deployment or release-tag action was performed.

> **Multi-Agent-Update:** The initial committed review was extended after
> independent Security, Architecture/Compatibility and QA/Packaging review.
> The corrected findings are authoritative; one MEDIUM cache-scope deviation
> (M-01) is recorded below.

## 1. Git basis and ancestry

- Authorized RC4 integration HEAD: `8ddc0503a851533c71027fcb122fe9f62f89dc4f`.
- Feature HEAD: `f0ea3b8b11a7387325f94bf09c8b4b4b2e12eaf8`.
- `git merge-base --is-ancestor 8ddc050 f0ea3b8` returned success.
- Feature is based directly on the authorized integration HEAD.
- `git merge-tree --write-tree 8ddc050 f0ea3b8` returned a tree without
  conflicts.
- Diff scope: docs, `lambda/src/secret_provider.py`, `lambda/src/order_service.py`,
  `lambda/tests/test_secret_provider.py`, `lambda/dist/lambda.zip`. No
  Terraform, AWS, RIS, Jobsearch or unrelated product files.

## 2. R1 — ENV compatibility

**PASS.** With `PRIVACY_SECRET_PROVIDER` unset, the provider resolves
`PRIVACY_INTERNAL_SECRET` exactly as before. Existing `OrderService` and
`create_order_service` positional/keyword callers remain compatible; the new
provider argument is optional. The existing privacy tests and full Lambda suite
are green. Conflicting AWS/APP references are rejected only when a new provider
configuration is introduced, preventing silent mode confusion.

## 3. R2 — Secret safety

**PASS for the reviewed scope.**

- `SecretMaterial.__repr__` redacts `value`; the field is `repr=False`.
- Provider/backend exceptions are mapped to coarse public errors and raised
  `from None`; raw backend messages are not exposed.
- No fetcher exception text, ARN/reference or secret value is returned.
- `OrderService` resolves the provider from server configuration, never from the
  request body/header context.
- No logging of resolved material was found.
- Provider code performs no logging; the stdout/stderr test is a weak
  regression check, not proof of redaction in all future logging paths.
- Cache keys contain provider/reference/version metadata, not secret values.

**Not claimed:** debugger memory inspection, arbitrary third-party logging or
future code paths outside this diff. These are not merge blockers for P00-B.

## 4. R3 — Provider contract

**PASS.**

- Unknown provider, missing reference and conflicting provider fields fail
  closed.
- ENV is the unchanged default; no request-selected provider/reference.
- Secrets Manager accepts an exact ARN/name and optional validated KMS ARN.
- Missing runtime fetcher fails closed (`SecretUnavailable`); no boto3 client is
  created in P00-B.
- Error classes distinguish not-found, access-denied, unavailable, invalid and
  configuration errors.
- The `SecretCache` object is process-local and keyed by
  provider/reference/key version/KMS; failed loads are not cached.
- **M-01:** Effective cache scope is one `OrderService`/invocation, not one
  Lambda execution environment, because `index.py:252` constructs a new service
  per invocation. This is a P00-C must-fix before a real Secrets Manager fetcher
  is wired; it does not affect the current ENV default path.
- APP_MANAGED validates metadata but resolution fails closed until P00-D.
- HMAC and encryption are not mixed: `APP_MANAGED_AUTH_METHOD` is metadata only;
  no cipher/HMAC implementation is claimed in P00-B.

### Low/operational finding L1 — rotation requires a new process/environment

**Evidence:** `SecretsManagerProvider` holds a process-local `SecretCache` and
exposes no TTL/invalidation/refresh API (`lambda/src/secret_provider.py`).

**Impact:** After a manual secret rotation, a warm Lambda environment may keep
the old material until the process is replaced. The implementation contract
explicitly permits invalidation by a new Lambda environment/deployment or a
separately designed refresh signal; P00-B does not provide hot reload.

**Correction:** Document and enforce the approved manual rotation procedure
(redeploy/new environment or future explicit refresh) in P00-C/P00-D. Do not
add an unreviewed automatic rotator.

**Merge blocker:** NO for P00-B; operational gate for rotation/GO-live.

## 5. R4 — Packaging

**PASS.**

- `lambda/dist/lambda.zip`: 40.263 bytes.
- SHA-256: `c35e6c8b091a13252f3827bb4f08afd61e594b9b92d4471f7dd816e45e7785ec`.
- `secret_provider.py` is present in the ZIP.
- A fresh `python3 build_zip.py` produced the identical hash.
- The ZIP contains 12 Python entries and no cache/bytecode artifacts.
- Build was performed from the clean feature worktree at `f0ea3b8`.

No new runtime dependency was added; the Lambda runtime supplies boto3.

## 6. R5 — Test quality

**PASS with explicit mock boundary.**

New tests: **34** in `lambda/tests/test_secret_provider.py` (34 test methods
across provider/config/cache/security/integration classes). They cover:

- default ENV and missing/empty secret;
- conflicting/unknown provider fields;
- ARN/name/KMS validation and redaction;
- missing fetcher, backend error classification, invalid responses;
- cache hit and non-caching of errors;
- APP_MANAGED fail-closed boundary;
- request-context non-selection (happy path; negative/lazy-init gap L-04);
- log/stdout/stderr checks (weak assertion, see L-04);
- compatibility of `OrderService`/`create_order_service`.

The tests are mock/fake-only. No test is treated as an AWS-live proof.

They use injected fake fetchers/clients, not AWS. The report correctly labels
this as local verification; no mock test is treated as an AWS-live proof.

Full local regression reproduced at the feature HEAD:

```text
Lambda:       379 PASS
Installer:    669 PASS
Module Builder: 128 PASS
E2E local:     32 PASS
Total:       1208 PASS
Seed:          28 PASS (separate)
```

The claimed 1.208 PASS is therefore verified.

## 7. R6 — Integration ability

**PASS.**

- Feature is based on the authorized RC4 HEAD.
- No conflicts were found with `release/rc4-integration`.
- No Terraform/AWS/RIS/Jobsearch or unrelated changes were introduced.
- P00-B is additive; P00-C (Secrets Manager resource/IAM/fetcher) and P00-D
  (APP_MANAGED key loader/HMAC) remain unimplemented and are not claimed as
  delivered.

## 8. Findings

### M-01 — Effective cache scope is one invocation, not one execution environment

| Field | Content |
|---|---|
| Severity | **MEDIUM** |
| File/stelle | `lambda/src/secret_provider.py` (`SecretCache`, `SecretsManagerProvider`); `lambda/src/index.py:252` |
| Reproduktion | Two resolves on the same provider instance = **1 fetch**; three sequential handler invocations (new `OrderService` each time) = **3 fetches**. `git show 8ddc050:lambda/src/index.py` shows the service is constructed per invocation. |
| Auswirkung | Contract §5 says cache scope = one Lambda execution environment. Once P00-C injects the real fetcher, every internal privacy invocation performs `GetSecretValue`; cache benefit is lost, with latency/cost/throttling impact. Current ENV default has no fetcher and is unaffected. |
| Korrektur | P00-C must hold the provider/cache at module scope (or introduce an explicitly documented module-level cache), with a test that proves cross-invocation reuse. Do not change P00-B `index.py` in this review. |
| Merge-Blocker | **NO for P00-B; mandatory P00-C acceptance condition** |

### L-01 — Non-ASCII secret/token comparison can become HTTP 500

| Field | Content |
|---|---|
| Severity | **LOW** |
| File/stelle | `lambda/src/order_service.py:191` (`secrets.compare_digest(str(token), str(internal_secret))`) |
| Reproduktion | A non-ASCII token or secret produces `TypeError: comparing strings with non-ASCII characters is not supported`; `index.fail()` then returns HTTP 500 instead of the contract’s 400. No auth bypass and no secret value is logged. |
| Auswirkung | Wrong error class under unusual material; P00-B widens the material source surface for future AWS_MANAGED values. The comparison itself is pre-existing. |
| Korrektur | P00-C should validate resolved material (ASCII-printable, bounded length) and/or map `TypeError` to a fail-closed `validation_error`. |
| Merge-Blocker | **NO** |

### L-02 — Provider failures are not observable in CloudWatch

| Field | Content |
|---|---|
| Severity | **LOW** |
| File/stelle | `lambda/src/order_service.py:166-168`; `lambda/src/index.py:104-106` |
| Reproduktion | Provider errors become silent 400 responses; no structured log/metric is emitted. Different public messages distinguish configuration, access-denied and unavailable failures. |
| Auswirkung | Persistent IAM/throttling failures may be hard to detect; an authorized internal caller can distinguish provider failure classes. Contract-compliant, but operationally weak. |
| Korrektur | P00-C: emit one sanitized structured log (provider/error class only, no ARN/reference/value) and consider one opaque caller-facing message. |
| Merge-Blocker | **NO** |

### L-03 — `PRIVACY_KMS_KEY_ARN` is validated but has no runtime effect

| Field | Content |
|---|---|
| Severity | **LOW** |
| File/stelle | `lambda/src/secret_provider.py` config validation and `SecretsManagerProvider._load` |
| Reproduktion | The KMS ARN enters the cache key but is not passed to the fetcher; no `kms:Decrypt` path exists. |
| Auswirkung | A future configuration may look CMK-bound while the runtime does not enforce that path. P00-B does not create KMS resources. |
| Korrektur | P00-C must either wire the KMS/CMK decrypt path and test it, or reject/remove the variable until implemented. |
| Merge-Blocker | **NO** |

### L-04 — Two hardening tests are weaker than their names

| Field | Content |
|---|---|
| Severity | **LOW** |
| File/stelle | `lambda/tests/test_secret_provider.py` (`test_provider_error_does_not_log_secret`, `test_request_context_cannot_select_provider_or_reference`) |
| Reproduktion | The log test asserts absence of the substring `"secret"` while the provider logs nothing at all; the context test only exercises a successful call and bypasses `create_secret_provider()`. There is no negative test for lazy initialization or a wrong token while a provider is injected. |
| Auswirkung | Future regressions in log redaction or eager provider selection may not be caught. No current leak was demonstrated. |
| Korrektur | Add a negative context test (`secretsmanager` + context reference + no fetcher → 400/no fetch) and a construction/non-privacy test with invalid provider env; assert a unique secret value is absent rather than the word `secret`. |
| Merge-Blocker | **NO** |

### L-05 — Documented execution-plan base differs from authorized feature base

| Field | Content |
|---|---|
| Severity | **LOW** |
| File/stelle | `docs/release/MO-RC4-P00-EXECUTION-PLAN.md` base line (`dd48799`) vs. feature ancestry (`8ddc050`) |
| Reproduktion | `git merge-base --is-ancestor 8ddc050 f0ea3b8` succeeds; the plan names `dd48799` as base. |
| Auswirkung | Authorization/ancestry is still provable from Git, but the plan’s base line is stale. |
| Korrektur | Correct the base line or add “feature branched from 8ddc050” before merge; docs-only. |
| Merge-Blocker | **NO** |

### L-06 — Provider rollout sequence is not documented

| Field | Content |
|---|---|
| Severity | **LOW** |
| File/stelle | `lambda/src/secret_provider.py` ENV conflict checks; P00-C scope |
| Reproduktion | Setting a stale `PRIVACY_SECRET_ID`/`PRIVACY_KMS_KEY_ARN`/APP reference while provider remains `env` causes a fail-closed 400. |
| Auswirkung | A partial P00-C migration can disable privacy operations; fail-closed is correct but the atomic switch (set provider + remove plaintext) is not documented. |
| Korrektur | Make the rollout sequence a P00-C order/acceptance criterion. |
| Merge-Blocker | **NO** |

### INFO observations

| ID | Observation | Merge blocker |
|---|---|---|
| I-01 | `SecretMaterial.value` is redacted in `repr`/`str`, but `dataclasses.asdict()` / `vars()` would expose it; `SecretProviderConfig` repr prints the full secret ARN. No current serialization path. Avoid `asdict()`/logging config; consider masked repr in P00-C. | NO |
| I-02 | `ParamValidationError`, `DecryptionFailureException` and some other backend 4xx classes map to `SecretUnavailable`; fail-closed but alerting taxonomy is imprecise. | NO |
| I-03 | `AppManagedProvider.resolve()` raises `AppKeyInvalid` for “P00-D not implemented”, conflating missing implementation with a bad key. | NO |
| I-04 | `validate_secret_reference` accepts any valid-looking Secrets Manager name; “project-scoped” is not enforced by the pattern (P00-C IAM exact ARN remains the real control). | NO |
| I-05 | ZIP reproducibility is verified locally (same Python/zlib); cross-environment determinism is not proven. | NO |
| I-06 | `SecretCache` is check-then-set without a lock; no practical issue in current per-invocation Lambda path. | NO |
| I-07 | `KeyVersionUnavailable` and `to_reference()` are P00-D placeholders and not reachable in production paths. | NO |

No CRITICAL or HIGH finding was demonstrated. M-01 is a MEDIUM contract
deviation but not a P00-B merge blocker; all other findings are LOW/INFO.
No hypothetical finding is reported as a confirmed defect.

## 9. Review verdict

```text
MO-RC4-P00-B — REVIEW PASS / MERGE AUTHORIZATION PENDING
```

**A — READY, with conditions:**

1. M-01 is a **mandatory P00-C acceptance criterion**: module-scoped provider/
   cache or documented per-invocation fetching; test cross-invocation behavior.
2. L-05 doc base line is corrected before or with the merge checkpoint.
3. After merge, `RC4-INTEGRATION-MANIFEST` and `PROJECT_STATUS` are updated;
   P00-B remains P00-C/D-dependent.
4. No P00-B code correction is required for the ENV-default path; no Terraform/
   AWS/RIS/Jobsearch change is part of this merge.

Merge is technically clean, tests/build are verified, and the security boundary
is fail-closed. Merge still requires explicit human authorization; P00-C/P00-D
and live AWS verification remain separate gates.

## 10. Evidence

- Feature HEAD `f0ea3b8`.
- Review branch HEAD `9de9cfd` before the report update; docs-only commit.
- Integration HEAD `8ddc050`.
- Merge tree `3dc044648652fff21d431cd7d377c80b43abe48a` (no conflict).
- Lambda ZIP SHA-256 `c35e6c8b091a13252f3827bb4f08afd61e594b9b92d4471f7dd816e45e7785ec`.
- Local tests: Lambda 379, Installer 669, Builder 128, E2E 32, Seed 28.
- ZIP reproduction from `lambda/src` to `/tmp`: byte-identical, 12 modules,
  no source mismatch.
- No AWS call or mutation was made during this review.

## 11. Multi-Agent Review Evidence

| Agent | Result | Files / commands |
|---|---|---|
| Security (read-only) | No CRITICAL/HIGH; 4 LOW, 7 INFO; no secret value in repr/errors; no ENV fallback; no request-controlled reference; error classes match contract | `secret_provider.py`, `order_service.py`, tests, contract; 13 adversarial probes |
| Architecture/Compatibility (read-only) | R1 old/new behavior identical in 7/7 cases; R6 ancestry and scope PASS; M-01 MEDIUM cache-scope deviation; ADR-008/Q-02/Q-08/Q-10 consistent | `git merge-base`, contract/ADR comparison, diff review |
| QA/Packaging/Integration (read-only) | R4/R5/R6 PASS; ZIP 12 modules, source byte-identical, deterministic rebuild; 379/669/128/32 + 28 reproduced; mock-only boundary preserved | `build_zip.build()` to `/tmp`, `sha256sum`, ZIP byte comparison, test suites |
| Commander | Consolidated findings; no write to feature/integration; review report only | `git merge-tree`, diff/scope checks, `git diff --check` |

All agents were read-only for code and infrastructure. Their combined result is
one MEDIUM condition (M-01) and no P00-B merge blocker.

**STOP before integration.**
