# AWS_MANAGED Provider Rollout — ENV → Secrets Manager

**Status:** DOCUMENTED / LOCAL TESTS ONLY
**Scope:** P00-C operator sequence. No live switch, no AWS mutation.

The switch is **atomic at the configuration boundary** and has **no automatic
ENV fallback**. A failed Secrets Manager resolution must fail closed.

## 1. Preconditions

- Secret exists in AWS Secrets Manager with the approved payload format
  (`SecretString`, no payload contract change).
- The Lambda execution role has `secretsmanager:GetSecretValue` on the exact
  secret ARN.
- Only when a customer CMK is selected: `kms:Decrypt` on the exact CMK ARN and
  `secretsmanager:DescribeSecret` for the configured CMK verification.
- No `PRIVACY_INTERNAL_SECRET` remains in the target Lambda environment.
- The secret reference is an exact ARN/name, not a request-provided value.
- P00-C-M01 and the L-findings are evidenced in the target package.

## 2. Activation sequence

```text
1. Provision/validate secret              (separate infra approval)
2. Provision IAM/KMS permissions          (separate infra approval)
3. Validate target configuration locally:
     PRIVACY_SECRET_PROVIDER=secretsmanager
     PRIVACY_SECRET_ID=<exact ARN/name>
     [PRIVACY_KMS_KEY_ARN=<exact CMK ARN>]   # only if CMK selected
     PRIVACY_INTERNAL_SECRET removed
4. Validate no conflicting ENV/APP references
5. Deploy code + configuration           (separate deployment approval)
6. Observe sanitized secret_provider_failure events
7. Run approved privacy smoke checks     (separate live approval)
```

The provider is resolved from server configuration only. Request/body/header
fields cannot select a provider or reference.

## 3. Rollback boundaries

- Restore the previous Lambda configuration and, if applicable, the previous
  deployment; do not re-introduce a plaintext secret unless separately approved.
- Never copy a secret value into Git, Terraform state, logs, CLI arguments or a
  plan manifest.
- Do not enable a silent ENV fallback as a rollback shortcut.
- Do not rotate or delete keys/secrets automatically.
- A CMK creation or DDB/SQS CMK change is still P00-E and requires separate
  approval.

## 4. Local evidence

`lambda/tests/test_secret_provider.py` covers:

- conflicting `PRIVACY_INTERNAL_SECRET` with `secretsmanager` → fail-closed;
- missing reference/invalid reference → fail-closed;
- no ENV fallback after a provider failure;
- module-wide cache invalidation and cross-identity isolation;
- CMK binding verification/mismatch;
- no secret values in structured failure events.

This document does not perform the switch.
