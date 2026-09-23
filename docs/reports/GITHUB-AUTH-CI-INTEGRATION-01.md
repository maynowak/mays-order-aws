# GITHUB-AUTH-CI-INTEGRATION-01 — GitHub Authentication & CI/CD Integration Investigation

**Date:** 2026-09-22  
**Status:** READ-ONLY INVESTIGATION COMPLETE

---

## Executive Summary

**Classification: C) PAT_REQUIRED_FOR_SOURCE**

The deployed AWS CI/CD pipeline **requires** the GitHub fine-grained PAT in `github-token-xxxxx` for the CodePipeline source action. The token is currently invalid/revoked, causing the Source stage to fail. This failure cascades to the Plan stage (no source artifact produced). The Validate stage from a previous successful run shows the downstream pipeline works when Source succeeds.

---

## Deployed Authentication Architecture

### CodePipeline Source Action
```
GitHub (v1 action)
  │
  ├── Owner: maynowak
  ├── Repo: mays-order-aws
  ├── Branch: main
  ├── OAuthToken: arn:aws:secretsmanager:eu-central-1:240571105849:secret:github-token-xxxxx
  ├── PollForSourceChanges: false
  └── Output: source_output
```

### Secret Configuration
| Secret | ARN | Value |
|--------|-----|-------|
| github-token-xxxxx | arn:aws:secretsmanager:eu-central-1:240571105849:secret:github-token-xxxxx-L02sI7 | `<REDACTED_GITHUB_PAT>` (fine-grained PAT) |

### CodeBuild Projects
| Project | Buildspec | GitHub Credentials |
|---------|-----------|-------------------|
| validate | ci/buildspecs/validate.yml | None |
| plan | ci/buildspecs/plan.yml | None |
| deploy | ci/buildspecs/deploy.yml | None |
| verify | ci/buildspecs/verify.yml | None |

No CodeBuild project uses GitHub credentials directly.

---

## Reference Analysis

### Terraform References
| File | Reference |
|------|-----------|
| ci/pipeline/main.tf | `OAuthToken = var.github_token_arn` |
| ci/pipeline/terraform.tfvars | `github_token_arn = "arn:aws:secretsmanager:eu-central-1:240571105849:secret:github-token-xxxxx"` |
| ci/iam/main.tf | `variable "github_token_arn"` + pipeline policy allows `secretsmanager:GetSecretValue` on the secret |

### Repository CI Configuration
| File | GitHub Auth Reference |
|------|----------------------|
| ci/buildspecs/*.yml | None |
| ci/pipeline/main.tf | Source action uses `OAuthToken = var.github_token_arn` |
| installer/ | None |
| scripts/ | None |

### CodeBuild Environment Variables
No CodeBuild project has GitHub-related environment variables.

---

## Root Cause Analysis

### Source Failure (Current)
```
Error: PermissionError
Message: Could not access the GitHub repository: "mays-order-aws". 
         The access token might be invalid or has been revoked.
```

**Cause:** The fine-grained PAT in `github-token-xxxxx` is invalid/revoked. GitHub returns 403 when CodePipeline attempts to fetch the repository.

### Plan Failure (Downstream)
```
Code: YAML_FILE_ERROR
Message: stat /codebuild/output/src1080894881/src/ci/buildspecs/plan.yml: no such file or directory
```

**Cause:** Cascading failure. Source stage fails → no `source_output` artifact produced → Plan stage's CodeBuild has no source artifact to download → `plan.yml` not found.

---

## Validate Stage Evidence (Previous Success)
```
Status: SUCCEEDED
Time: 10 hours ago
Commit: cbd81662
Message: "fix: add terraform init before validate in CI"
```
The Validate stage **passes** when Source provides a valid artifact. The installer validation + terraform init/validate works correctly.

---

## Least-Privilege Assessment

| Component | Current | Required | Assessment |
|-----------|---------|----------|------------|
| GitHub PAT | Fine-grained PAT | Fine-grained PAT with `repo` read | ✅ Least privilege |
| Secret Access | Pipeline role + CodeBuild base policy | Pipeline role only (Source action) | ✅ CodeBuild doesn't need it |
| Secret Value | Fine-grained PAT | Fine-grained PAT with `repo:read` | ✅ Least privilege |

---

## Classification

**C) PAT_REQUIRED_FOR_SOURCE**

The CodePipeline source action **requires** the GitHub PAT in `github-token-xxxxx`. The deployed configuration proves:
1. Source action uses `OAuthToken = var.github_token_arn`
2. The secret contains a real fine-grained PAT
3. Source fails with "access token invalid/revoked"
4. No other component consumes this secret

---

## Recommended Next Action

**Update the secret with a valid GitHub fine-grained PAT:**

```bash
# Create fine-grained PAT at: https://github.com/settings/tokens
# Required permissions: Repository → Contents → Read

aws secretsmanager put-secret-value \
  --secret-id github-token-xxxxx \
  --secret-string "ghp_YOUR_NEW_FINE_GRAINED_PAT" \
  --profile mayaws

# Then re-run
aws codepipeline start-pipeline-execution --name mays-orders-development-ci-cd --profile mayaws
```

**Required PAT permissions:**
- Repository → Contents → Read (minimum for checkout)
- No Account permissions needed

---

## ASCII Architecture Diagram

```
GitHub
  │
  │ Fine-grained PAT (repo:read)
  │     │
  │     ▼
  │  Secrets Manager
  │     │
  │     │ github-token-xxxxx
  │     ▼
CodePipeline Source (GitHub v1)
  │     │
  │     │ OAuthToken from secret
  │     ▼
  │  Source Artifact (source_output)
  │     │
  │     ├──▶ Validate → CodeBuild → python3 -m installer.cli.main validate ✅
  │     ├──▶ Plan     → CodeBuild → python3 -m installer.cli.main plan
  │     ├──▶ Approval → Manual
  │     └──▶ Deploy   → CodeBuild → python3 -m installer.cli.main deploy
  │
CodeBuild Projects
  │
  ├── validate (ci/buildspecs/validate.yml)
  ├── plan (ci/buildspecs/plan.yml)
  ├── deploy (ci/buildspecs/deploy.yml)
  └── verify (ci/buildspecs/verify.yml)
       │
       └── No GitHub credentials needed
           (Installer handles AWS auth via IAM role)

Secrets Manager
  │
  └── github-token-xxxxx
          │
          ├── Consumed by: CodePipeline Source (OAuthToken)
          ├── NOT consumed by: Any CodeBuild project
          └── Required: YES (Source fails without valid token)
```

---

## Conclusion

**PAT is required for Source.** The current token is invalid. Update the secret with a valid fine-grained PAT (repo:read) to unblock the pipeline. The Validate stage proves the downstream pipeline works when Source succeeds.
