# MO-RC4-P00-C — F-01 Q-09 AMENDMENT PROPOSAL

**Status:** PROPOSED / OWNER DECISION PENDING
**Date:** 2026-11-14
**Scope:** Contract-only proposal. No approval, no product code, no IaC.

## 1. Proposed Owner Decision

Expand the approved Q-09 action set for the exact same approved Secrets Manager
secret ARN(s):

```text
secretsmanager:GetSecretValue   # existing
secretsmanager:DescribeSecret   # proposed: CMK metadata verification only
kms:Decrypt                     # only when the secret actually uses a customer CMK
```

Conditions:

- Exact secret ARN(s), no resource wildcard.
- `DescribeSecret` only for the exact same secret ARN(s).
- `kms:Decrypt` only when a customer CMK is explicitly selected; the
  AWS-managed Secrets Manager key must not require it.
- No implicit CMK creation.
- No extension to DynamoDB or SQS CMK.
- Default Deny and least privilege remain mandatory.
- No wildcard action/resource without separate Owner approval.

**This is not approved by this proposal. F-01 remains OPEN until the Release
Owner accepts or rejects it.**

## 2. ADR-008 Proposed Change

### D-5 — AWS_MANAGED (proposed text)

> Secrets Manager; Env contains only non-secret references. IAM is least
> privilege: `secretsmanager:GetSecretValue` on the exact secret ARN. When a
> customer-managed CMK is explicitly configured, the provider may additionally
> call `secretsmanager:DescribeSecret` on the same exact secret ARN to verify
> the `KmsKeyId` binding, and requires `kms:Decrypt` on the exact key ARN.
> AWS-managed Secrets Manager encryption requires neither DescribeSecret nor
> an application KMS call. No wildcard. No implicit CMK creation.

### C-03 Proposed Change

Add `DescribeSecret` as conditional metadata verification; do not turn it into
a blanket permission.

## 3. Decision Register Proposed Change

In Q-09, extend the owner decision row with:

```text
secretsmanager:DescribeSecret only for the same exact approved secret ARN(s),
conditional on explicit customer-CMK metadata verification; no wildcard; no
DDB/SQS CMK.
```

Q-09 remains subject to the Owner's explicit acceptance.

## 4. Implementation Contract Proposed Change

### §6 AWS_MANAGED IAM row

```text
GetSecretValue: exact secret ARN (always)
DescribeSecret: exact same secret ARN, only when PRIVACY_KMS_KEY_ARN is set
kms:Decrypt: exact key ARN, only when a customer CMK is actually used
```

### §8 KMS rules

Add: CMK binding may be verified through `DescribeSecret`; a mismatch is
fail-closed. The AWS-managed default path performs no `DescribeSecret` call.

## 5. Policy-Gate Specification Proposal

Add to the explicit allowlist (P00-E scope, not implemented here):

```text
aws_secretsmanager_secret
aws_secretsmanager_secret_version
aws_kms_key
aws_kms_alias
```

Validator rules:

- `aws_secretsmanager_secret` must be project-scoped and reference an approved
  exact name/ARN; no `*`.
- Secret version must not expose a plaintext `secret_string` in plan/state.
- `aws_kms_key` only when explicit opt-in; no implicit key.
- Inline `aws_iam_role_policy` must be checked for wildcard actions/resources,
  not only standalone `aws_iam_policy`.
- `secretsmanager:GetSecretValue` and `DescribeSecret` only on exact approved
  secret ARNs; `kms:Decrypt` only on the exact CMK ARN.
- No DynamoDB/SQS CMK resource types in this amendment.

## 6. Approval Gate

- Status: **PROPOSED, NOT APPROVED**
- Required: Release Owner explicit approval of the Q-09 amendment.
- Until approval: F-01 remains OPEN; no ADR/Contract/Policy-Gate change is
  effective; no P00-E Terraform.
- If rejected: remove the `DescribeSecret` CMK verification from runtime and
  rely on the secret’s IAM/KMS binding, or defer CMK verification to P00-E.

**STOP before contract or infrastructure changes.**
