# MO-RC4-P00 Implementation Contract

**Status:** DRAFTED / OWNER DECISIONS PENDING
**Scope:** P00 SecretProvider, AWS_MANAGED, APP_MANAGED, KMS/encryption,
rotation and retention integration
**Baseline:** `086a8bea4c608724d400de834c21df5456b7ccac`
**Branch:** `release/rc4-integration`
**Reference:** `docs/reports/MO-RC4-P00-A-SECURITY-ARCHITECTURE-DECISION.md`

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

**Note:** Rejecting conflicting configuration is a proposed safety rule; Q-08
must confirm the exact configuration surface.

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
| Secret encryption | AWS-managed default; optional CMK via separate decision |
| KMS IAM | `kms:Decrypt` only if CMK selected; exact key ARN |
| Value in Env | **No** plaintext; only provider/reference fields |
| Value in Terraform | **No** value in outputs/state |
| Cache | Process-local |
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
- Policy-Gate allowlist change requires Q-09.

### Module Builder

- `orders-service` contract remains unchanged.
- P00 modules offered only via explicit hardened preset/module selection
  (Q-03).
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

- Q-02 (backend),
- Q-03 (module placement),
- Q-04 (CMK ownership),
- Q-05 (`tenantId`),
- Q-06 (retention duration),
- Q-07 (cancel semantics),
- Q-08 (reference/fetch shape),
- Q-09 (policy gate),
- Q-10 (ADR approval),
- Q-11 (rotation scope),
- Q-12 (release label),
- Q-13 (test account),
- Q-14 (legacy backfill).

P00-A itself is documentation only.
