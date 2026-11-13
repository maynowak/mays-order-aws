# RC4 Integration Manifest

**Branch:** `release/rc4-integration`
**Worktree:** `/home/dci-student/projects/Mays-Orders-AWS-rc4-integration`
**Authorized baseline:** `086a8bea4c608724d400de834c21df5456b7ccac`
**Baseline subject:** `docs(release): package v0.5.0-rc.3 (Module Builder & RIS Integration)`
**Merge source:** `test/mo-rc4-testsuite-hardening-10a`
**Source HEAD:** `b49c59f2ca30b846477b4e0108720ff6708d899e`
**Integration merge:** `bb8edce81f67db4767f03528d1214e5b63247992`

> This manifest records the integration candidate, not a release approval,
> tag or deployment. P00 remains an open RC4 work package.

---

## 1. Integration Base

| Field | Value |
|---|---|
| Baseline commit | `086a8bea4c608724d400de834c21df5456b7ccac` |
| RC3 release tag | **not present**; explicitly authorized as baseline by Release Owner |
| Merge base | `086a8be` (verified) |
| Integration strategy | One controlled `--no-ff` merge of the canonical RC4 test branch |
| Source branch | `test/mo-rc4-testsuite-hardening-10a` |
| Source HEAD | `b49c59f2ca30b846477b4e0108720ff6708d899e` |
| Merge commit | `bb8edce81f67db4767f03528d1214e5b63247992` |
| First parent | baseline `086a8be` |
| Second parent | source `b49c59f` |

## 2. Commit Matrix

| Area | Source / commits | Integration |
|---|---|---|
| P00/P01 design and scope | `c40b695`, `62f6b19`, P00/P01 reports | **INCLUDED** as documentation only |
| Order ownership / identity | P02/P02A/P02B/P02C/P02E/P02F/P02G/P02H/P02I series | **INCLUDED** |
| Worker / SQS / DLQ / processing | `1bd7e8e`, `5af53dc`, `f5a3b03`, P02C/P02F/P02I | **INCLUDED** |
| GSI3 / recovery | P02I-B2, recovery/processing tests | **INCLUDED** |
| Privacy / owner-consumer isolation | P02/P02H, G3-FIX `7d82ad4`, `51094bf`, `75a32fc` | **INCLUDED** |
| B2 tests and live evidence | B2 integration/live reports, privacy harness/tests | **INCLUDED** |
| Installer / builder / upgrade gates | P0A/P0B/P0C/P1/P3A and related tests | **INCLUDED** |
| Security corrections | SEC-01…05 and approval contract docs | **INCLUDED** |
| Release documentation | RC4 gate/candidate/owner decision reports | **INCLUDED** |
| P00 implementation | AWS_MANAGED/APP_MANAGED | **NOT INCLUDED — P00 OPEN** |
| T011-14 KMS backup stash | `stash@{0}` | **NOT APPLIED / UNCHANGED** |

## 3. Non-Integrated Branches

| Branch | Reason |
|---|---|
| `test/mo-rc3-version-marker-01` | Instrumented **RC3-only** version marker; changes deployment-version semantics; not RC4 product scope. Retained for traceability. |
| `test/mo-rc4-teststack-deploy-01` | Historical teststack preflight docs; superseded by later teststack/live evidence. |
| `test/mo-rc4-teststack-workspace-plan-01` | Historical workspace/plan docs; superseded. |
| `test/mo-rc4-teststack-apply-01` | Historical apply docs; superseded. |
| `test/mo-rc4-p3a-backup-execute-01` | Includes RC3 marker + historical teststack evidence; test-only, not RC4 product code. |
| `feature/mo-rc4-aws-upgrade-plan-01` | Earlier blocked discovery; superseded by later plan/replan/apply reports. |
| `feature/mo-rc4-teststack-baseline-01` | Historical baseline prep; current test branch contains the later canonical state. |

These branches remain unchanged; no work was deleted.

## 4. Verification

| Check | Result |
|---|---|
| Installer | **669 PASS** |
| Module Builder | **128 PASS** |
| Lambda | **345 PASS** |
| E2E local (full discover: 36, 5 expected skips) | **32 PASS** |
| Seed tools | **28 PASS** |
| Terraform fmt | **PASS** |
| Terraform init `-backend=false` | **PASS** |
| Terraform validate | **PASS** |
| `git diff --check` | **PASS** |
| AWS mutations | **NONE** |
| Terraform apply | **NONE** |

## 5. P00 Status

```text
P00 — OPEN / NOT INCLUDED
AWS_MANAGED: MISSING / Q-02 + Q-08 + Q-10 APPROVED
APP_MANAGED: MISSING / Q-10 APPROVED, OTHER GATES OPEN
KMS backup stash: UNCHANGED, NOT APPLIED
P00-B: READY FOR AUTHORIZATION, NOT STARTED
```

P00 design/ADR documents are integrated; implementation remains a separate
RC4 work package. Q-02 (Secrets Manager), Q-08 (ARN/name reference + runtime
fetch) and Q-10 (ADR-008, C-01…C-07) are owner-approved; ADR-008 is `ACCEPTED`.
No P00 completion is claimed and no package is started.

## 6. Release Readiness

```text
Integration: COMPLETE
P00:          PENDING
RC4 release:  NOT RELEASED / NO TAG / NO PRODUCTION APPROVAL
```
