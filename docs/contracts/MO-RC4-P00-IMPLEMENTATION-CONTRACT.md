# MO-RC4-P00 Implementation Contract

**Status:** DRAFTED / Q-02 + Q-04 + Q-08 + Q-09 + Q-10 OWNER-APPROVED / OTHER DECISIONS PENDING
**Scope:** P00 SecretProvider, AWS_MANAGED, APP_MANAGED, KMS/encryption,
rotation and retention integration
**Baseline:** `086a8bea4c608724d400de834c21df5456b7ccac`
**Branch:** `release/rc4-integration`
**Reference:** `docs/reports/MO-RC4-P00-A-SECURITY-ARCHITECTURE-DECISION.md`

> **Owner update 2026-11-13:** Q-02 (Secrets Manager), Q-04 (CMK
> default/external/opt-in), Q-08 (ARN/name reference + runtime fetch, no
> plaintext secret in Env), Q-09 (explicit Policy-Gate allowlist) and Q-10
> (ADR-008 after C-01…C-07) are approved. This is a
> contract/architecture decision only; no implementation is authorized.
> P00-B is integrated; P00-C still requires a separate package authorization.
> Remaining questions (Q-03, Q-05, Q-06, Q-07, Q-11…Q-14) remain open.
>
> **Q-09 limited amendment 2026-11-14:** `secretsmanager:DescribeSecret` is
> approved only for the same exact secret ARN(s), only for customer-CMK
> metadata verification. No wildcard, no implicit CMK, no DDB/SQS CMK. F-01
> remains `CONTRACT AMENDED / RE-REVIEW PENDING`.

> This is an implementation contract, not code. No field below is approved for
> implementation until the corresponding Owner Decision is closed.

---

## 1. Scope and Non-Goals

### In Scope

- Provider selection and resolution for privacy operations.
- AWS_MANAGED Secrets Manager integration.
- APP_MANAGED external key material and HMAC authentication.
- Optional KMS/CMK integration for Secrets Manager, DynamoDB and SQS.
- Rotation mechanics/cache invalidation.
- Retention/Privacy lifecycle contract.
- Terraform/Builder/Installer configuration contracts.
- Negative tests and acceptance criteria.

### Out of Scope

- Product implementation in P00-A.
- AWS/Terraform execution.
- Real secret values or secret retrieval.
- RIS/Jobsearch changes.
- Automatic CMK creation or rotation.
- Legal retention periods (Owner/legal decision).
- T011-14 backup-KMS stash.

---

## 2. Invariants

1. `env` remains the default provider; existing deployments do not silently
   change behavior.
2. No provider fallback. If a provider is selected, only that provider is used.
3. No secret material in Git, reports, logs, error messages, Terraform outputs
   or Terraform state.
4. Fail-closed on missing/invalid configuration.
5. No request/body/header value may select a secret reference or key.
6. Existing Privacy auth semantics (`compare_digest`) remain unchanged.
7. P00 defaults are additive and disabled.
8. CMK/Secret/KMS are separate capabilities; one does not imply another.

---

## 3. Provider Interface

### 3.1 Types

```text
SecretReference:
  provider: "env" | "secretsmanager" | "app_managed"
  reference: string          # env name, Secret ARN/name, or external key ref
  key_id: optional string
  key_version: optional string

SecretMaterial:
  value: string              # in-memory only
  key_id: optional string
  key_version: optional string
  provider: string
```

### 3.2 Responsibilities

| Component | Responsibility |
|---|---|
| Configuration resolver | Reads provider/reference from Lambda configuration; never from request data |
| Provider | Loads material from the selected backend |
| Cache | Process-local cache; keyed by reference + version; no cross-provider reuse |
| Privacy auth adapter | Uses material with existing constant-time comparison |
| APP-HMAC adapter | Uses `key_id`/`key_version` for canonical HMAC verification |
| Error mapper | Maps provider errors to fail-closed privacy errors |

### 3.3 Configuration Schema

```text
PRIVACY_SECRET_PROVIDER = "env" | "secretsmanager" | "app_managed"
# Default when unset: env

PRIVACY_INTERNAL_SECRET = <secret>     # env only; prohibited for other providers
PRIVACY_SECRET_ID       = <ARN or name> # secretsmanager only
PRIVACY_APP_KEY_ID      = <key id>      # app_managed only
PRIVACY_APP_KEY_VERSION = <version>     # app_managed only
PRIVACY_APP_KEY_REF     = <external ref># app_managed only
PRIVACY_KMS_KEY_ARN     = <key ARN>     # optional for AWS_MANAGED/KMS paths
```

### 3.4 Validation Matrix

| Provider | Required | Forbidden / invalid |
|---|---|---|
| `env` | `PRIVACY_INTERNAL_SECRET` | AWS/APP references are ignored? **No** — reject conflicting values to avoid silent mode confusion |
| `secretsmanager` | `PRIVACY_SECRET_ID` | `PRIVACY_INTERNAL_SECRET` must be unset |
| `app_managed` | external key ref + key id/version as required | `PRIVACY_INTERNAL_SECRET`/SecretsManager ref must not be used |
| unset | `env` default | — |
| unknown | — | fail-closed |

**Note:** Q-08 is owner-approved for the ARN/name-reference plus runtime-fetch
direction. Rejecting conflicting configuration remains the safety rule in this
contract to prevent silent mode confusion; any deviation requires an explicit
contract change.

---

## 4. Error Contract

| Error | Trigger | Result |
|---|---|---|
| `ProviderConfigurationError` | unknown provider, missing/conflicting fields | 400/fail-closed, no data access |
| `SecretNotConfigured` | env secret missing | 400/fail-closed |
| `SecretNotFound` | Secrets Manager `ResourceNotFound` | 400/fail-closed |
| `SecretAccessDenied` | IAM/KMS `AccessDenied` | 400/fail-closed |
| `SecretUnavailable` | network/throttling/timeout | 400/fail-closed |
| `SecretInvalid` | empty/invalid material | 400/fail-closed |
| `AppKeyInvalid` | bad key format/version | 400/fail-closed |
| `KeyVersionUnavailable` | requested APP key version absent | 400/fail-closed |

No raw provider exception, ARN, secret value or request body may be returned to
the caller. Logging may contain provider name/error code and a non-secret
reference suffix only.

---

## 5. Caching, Concurrency, Rotation

### Cache

- Scope: one Lambda execution environment.
- Key: provider + reference + key version/fingerprint.
- No persistence to disk, DynamoDB, S3 or environment.
- No cache of an error that could silently fall back.

### Concurrency

- Concurrent requests share an immutable loaded snapshot.
- No global mutable token.
- A failed refresh must not return stale material if the referenced version is
  no longer valid; fail-closed per contract.

### Rotation

- Secrets Manager rotation is a separate capability (Q-11).
- KMS key rotation is independent of secret-value rotation.
- APP_MANAGED uses explicit `keyId`/`keyVersion`.
- RC4 has **no automatic rotator and no automatic rotation**. A documented
  manual rotation procedure is permitted; scope, transition window and
  responsibility remain Q-11.
- Old material may remain valid only during an Owner-approved transition window.
- Cache invalidation requires a new Lambda environment/deployment or an
  explicitly designed refresh signal; no silent hot reload.
- No automatic deletion of old keys.

---

## 6. AWS_MANAGED Contract

| Item | Contract |
|---|---|
| Secret source | AWS Secrets Manager |
| Reference | Exact ARN/name, project-scoped |
| Provider IAM | `secretsmanager:GetSecretValue` on exact ARN |
| Metadata IAM | `secretsmanager:DescribeSecret` on the same exact ARN only when `PRIVACY_KMS_KEY_ARN` is set; CMK verification only |
| Secret encryption | AWS-managed default; optional CMK via separate decision |
| KMS IAM | `kms:Decrypt` only if CMK selected; exact key ARN; no wildcard |
| Value in Env | **No** plaintext; only provider/reference fields, including optional non-secret `PRIVACY_KMS_KEY_ARN` |
| Value in Terraform | **No** value in outputs/state |
| Cache | Module-scoped process-local; no TTL; controlled invalidation |
| Rotation | Manual/native later; not automatically enabled |
| Failure | fail-closed, no ENV fallback |

---

## 7. APP_MANAGED Contract

| Item | Contract |
|---|---|
| Material | Externally supplied 32-byte Base64 key |
| Authentication | HMAC-SHA256 over canonical internal payload |
| Comparison | `hmac.compare_digest`-equivalent |
| Key identity | `keyId` + `keyVersion` |
| Rotation | Manual/guided; old version only during approved window |
| Crypto | No custom cipher; no AES implementation |
| KMS | Not implied; KMS-envelope is a separate AWS_MANAGED-style choice |
| Failure | fail-closed on missing/invalid key/version |
| Audit | keyId/version and decision, never key value |

APP_MANAGED is not an AWS KMS key and not a variant of AWS_MANAGED.

---

## 8. KMS / Encryption Contract

### Capabilities

1. Secrets Manager default encryption.
2. Optional customer-managed CMK for Secrets Manager.
3. Optional DynamoDB SSE-KMS.
4. Optional SQS SSE-KMS.
5. Application-side key material for APP_MANAGED.

### Rules

- A CMK is not automatically created by any provider.
- KMS key-policy and IAM use exact ARNs; no wildcard resources.
- `enable_key_rotation` required for new CMKs.
- No key deletion without Owner decision and deletion window.
- DDB/SQS CMK activation is an explicit, separately approved change.
- AWS-owned encryption is not re-labelled as P00 CMK.
- T011-14 backup KMS is not part of P00.
- **Q-04 approved:** AWS-managed Secrets Manager encryption is the default;
  existing customer CMKs require an explicit ARN; a new CMK only by explicit
  opt-in and never implicitly. Provider activation does not alter existing
  encryption resources.
- **Q-09 approved:** Policy-Gate extension is allowlist-based, default-deny and
  least-privilege; no wildcard without a separate Owner decision.
- **Q-09 limited amendment approved 2026-11-14:**
  `secretsmanager:DescribeSecret` is allowed only on the same exact approved
  secret ARN(s), only for customer-CMK metadata verification. It is not a
  general metadata permission; no DDB/SQS CMK extension and no implicit CMK.

---

## 9. Terraform / Builder / Installer Contract

### Terraform

New optional resources only:

```text
privacy_secret_enabled = false
kms_enabled            = false
PRIVACY_SECRET_ID      = output of privacy_secret module (no value)
```

- Default plan must remain resource-identical to RC4 defaults.
- `privacy_secret` and `kms` are separately selectable.
- No secret value in state/plan/output.
- Key policy/IAM count-gated.
- Policy-Gate allowlist is Q-09-approved: explicit allowlist, default deny,
  exact Secret references and no wildcard without separate Owner approval.

### Module Builder

- Existing `orders-service` inputs and outputs remain unchanged.
- P00 modules offered only via explicit hardened preset/module selection
  (Q-03); the exact placement remains open.
- New optional variables must leave the default plan resource-identical.
- No secret values in builder manifest.
- Validation fail-closed; no silent stripping of security wiring.

### Installer

- Optional flags only; no secrets on CLI.
- Preflight: provider/secret/key consistency, expected account/region.
- Upgrade: no resource replacement; explicit plan review.
- Rollback: restore previous configuration and no secret leakage.
- Errors redacted.

---

## 10. Retention Contract

- `retentionUntil` and `ttl` are proposed, not approved.
- TTL is asynchronous and **not** a deletion guarantee.
- ERASE/ANONYMIZE/RETAIN remain separate operations.
- Backups/PITR are separate retention/erasure concerns.
- No legal period, TTL duration or automatic deletion is invented.
- **Orphan detection (ADR-008 D-2) is assigned to P00-G** for specification and
  fail-closed behavior. P00-G does not include automatic deletion, backfill or a
  RIS write path; execution remains separately Owner-gated. Q-14 governs legacy
  data, RIS coordination remains outside P00.
- Q-06/Q-14 remain Owner decisions.
- Existing Privacy auth and fail-closed behavior must not regress.

---

## 11. Test Contract

### Positive

- ENV default resolves existing token.
- AWS_MANAGED resolves from fake Secrets Manager.
- APP_MANAGED verifies valid key/version.
- Cache hit avoids second backend call.
- Redaction of logs/errors.
- No secret in Terraform outputs/plan/state.

### Negative

- Unknown provider.
- Missing secret/reference.
- `AccessDenied`, `ResourceNotFound`, timeout.
- Conflicting provider configuration.
- Wrong APP key/version.
- Invalid Base64/length.
- No fallback on provider failure.
- Secret absent from exception/log output.
- KMS key policy/IAM invalid.
- DDB/SQS plan with missing key policy must fail.
- TTL does not create a synchronous-delete assertion.

### Acceptance

- No product code in P00-A.
- Contract tests are mocks/fakes only.
- No AWS access.
- All negative paths fail-closed.
- Existing 1.174 local regression remains green when implementation starts.

---

## 12. Migration / Rollout

1. P00-B adds provider foundation with `env` default unchanged.
2. P00-C adds AWS_MANAGED behind explicit enablement.
3. P00-D adds APP_MANAGED only after Owner decision.
4. P00-E adds optional KMS/IaC after Q-04/Q-09.
5. P00-F adds rotation after Q-11.
6. P00-G adds retention after Q-06/Q-14.
7. P00-H wires Builder/Installer.
8. P00-I runs security/regression/release gates.

No fallback or automatic migration between ENV/AWS_MANAGED/APP_MANAGED.

---

## 13. Owner-Gated Fields

Implementation must not start on:

- ~~Q-02 (backend)~~ — **owner-approved 2026-11-13: Secrets Manager**;
- Q-03 (module placement),
- ~~Q-04 (CMK ownership)~~ — **owner-approved 2026-11-13: AWS default /
  existing ARN / opt-in only**;
- Q-05 (`tenantId`),
- Q-06 (retention duration),
- Q-07 (cancel semantics),
- ~~Q-08 (reference/fetch shape)~~ — **owner-approved 2026-11-13:
  ARN/name reference + runtime fetch**;
- ~~Q-09 (policy gate)~~ — **owner-approved 2026-11-13: explicit allowlist /
  default deny**;
- ~~Q-10 (ADR approval)~~ — **owner-approved 2026-11-13 after C-01…C-07**;
- Q-11 (rotation scope),
- Q-12 (release label),
- Q-13 (test account),
- Q-14 (legacy backfill).

Q-02/Q-04/Q-08/Q-09/Q-10 approval does not start P00-C. P00-B is integrated;
P00-C remains at **implementation authorization pending** and must satisfy
P00-C-M01 and the P00-C acceptance criteria. P00-A itself is documentation only.
