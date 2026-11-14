# AWS_MANAGED Provider Rollout — ENV → Secrets Manager

**Status:** DOCUMENTED / LOCAL TESTS ONLY
**Scope:** P00-C operator sequence. No live switch, no AWS mutation.

The switch is **atomic at the configuration boundary** and has **no automatic
ENV fallback**. A failed Secrets Manager resolution must fail closed.

## 1. Preconditions

- Secret exists in AWS Secrets Manager with the **exact approved payload**:
  `SecretString` contains the internal token only — ASCII, 1…1024 characters,
  no JSON wrapper, no trailing payload. Invalid/empty/non-ASCII → fail-closed.
- The Lambda execution role has `secretsmanager:GetSecretValue` on the exact
  secret ARN.
- Only when a customer CMK is selected: `kms:Decrypt` on the exact CMK ARN.
- `DescribeSecret` for CMK metadata verification is required **only if F-01 is
  approved**; it is not part of the current Q-09/ADR contract and remains open.
- Policy-Gate allowlist for `aws_secretsmanager_*`/`aws_kms_*` and inline-IAM
  wildcard validation must be extended in P00-E before provisioning.
- No `PRIVACY_INTERNAL_SECRET` remains in the target Lambda environment.
- The secret reference is an exact ARN/name, not a request-provided value.
- P00-C-M01 and the L-findings are evidenced in the target package.

## 2. Activation sequence

```text
1. Owner approves F-01/Q-09 amendment or removes the DescribeSecret dependency
2. Provision/validate secret              (separate infra approval)
3. Provision IAM/KMS permissions          (separate infra approval)
4. Validate Policy-Gate allowlist/inline IAM (P00-E)
5. Validate target configuration locally:
     PRIVACY_SECRET_PROVIDER=secretsmanager
     PRIVACY_SECRET_ID=<exact ARN/name>
     [PRIVACY_KMS_KEY_ARN=<exact CMK ARN>]   # only if CMK selected
     PRIVACY_INTERNAL_SECRET removed
6. Validate no conflicting ENV/APP references
7. Deploy code + configuration           (separate deployment approval)
8. Observe sanitized secret_provider_failure events
9. Run approved privacy smoke checks     (separate live approval)
```

The provider is resolved from server configuration only. Request/body/header
fields cannot select a provider or reference.

## 3. Cache lifetime and rotation (F-02)

- The provider/cache is module-scoped and survives invocations in one Lambda
  execution environment.
- The cache has no TTL. `SecretCache.invalidate()` and
  `reset_default_secret_provider()` exist, but are not runtime hot-reload
  triggers; a deployment/environment recycle is the approved invalidation path.
- A manual secret rotation is effective in a warm environment only after a
  forced environment recycle (new deployment/version or equivalent operator
  action). Parallel old/new execution environments can briefly accept the old
  token.
- No automatic rotation or hot reload is implemented; Q-11 remains separate.
- A compromise response must force environment recycling; the old token is not
  assumed revoked instantly.

## 4. Rollback (F-05)

Two distinct paths are required:

### Path A — forward-fix in AWS_MANAGED (preferred)

- Keep the provider selected; restore/repair the exact secret ARN and
  IAM/KMS permissions; redeploy or force an environment recycle to clear cache.
- No plaintext ENV secret is introduced.

### Path B — controlled ENV rollback

- Requires **separate Owner approval** and explicit re-provisioning of
  `PRIVACY_INTERNAL_SECRET` out-of-band.
- Deploy the previous code/configuration only with the secret provisioned
  before activation; never place the value in Git, Terraform, logs, CLI args or
  plan manifests.
- After rollback, remove the AWS_MANAGED configuration or retain it only as a
  documented staged state; no automatic fallback.
- Force environment recycle to clear the module provider/cache.

There is no silent ENV fallback, no automatic secret rotation, and no automatic
key/secret deletion.

## 5. Local evidence

`lambda/tests/test_secret_provider.py` and
`lambda/tests/test_index_aws_managed.py` cover:

- conflicting `PRIVACY_INTERNAL_SECRET` with `secretsmanager` → fail-closed;
- missing/invalid reference, payload, non-ASCII → fail-closed;
- no ENV fallback after a provider failure;
- module-wide cache reuse across two `index.handler` invocations;
- cross-reference identity isolation and cache invalidation;
- CMK binding verification/mismatch;
- no secret values in structured failure events;
- missing handler-level secretsmanager regression now covered.

This document does not perform the switch.
