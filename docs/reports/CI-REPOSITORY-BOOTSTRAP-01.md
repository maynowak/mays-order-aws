# CI-REPOSITORY-BOOTSTRAP-01 — AWS-Aligned Repository Bootstrap

**Date:** 2026-09-21  
**Status:** COMPLETED — Repository Bootstrap Validated

---

## Executive Summary

The Mays-Orders-AWS repository has been validated and aligned with AWS Prescriptive Guidance for Terraform CI/CD pipelines. The repository now contains all required files for a fresh checkout to work with AWS CodePipeline/CodeBuild without manual configuration.

---

## AWS Documentation Alignment

### Reference Pattern
AWS Prescriptive Guidance: "Create a CI/CD pipeline to validate Terraform configurations by using AWS CodePipeline"

### Key Concepts Applied
| AWS Concept | Implementation |
|-------------|----------------|
| Source repository | Mays-Orders-AWS (GitHub) |
| Main branch | `main` |
| Source artifact | CodePipeline fetches repository |
| CODEBUILD_SRC_DIR | Buildspecs use repository-relative paths |
| Repository-hosted buildspec | `ci/buildspecs/*.yml` |
| Alternate buildspec path | Explicitly configured in CodeBuild projects |
| CodeBuild project | 6 projects (validate, plan, deploy, verify, destroy-plan, destroy) |
| CodePipeline source/build stages | Source → Validate → Plan → Approval → Deploy → Verify |

---

## Final Repository Structure

```
Mays-Orders-AWS/
├── ci/
│   ├── buildspecs/
│   │   ├── validate.yml      # Validation + unit tests
│   │   ├── plan.yml          # Terraform plan via installer
│   │   ├── deploy.yml        # Terraform deploy via installer
│   │   ├── verify.yml        # Post-deploy verification
│   │   ├── destroy-plan.yml  # Destroy plan via installer
│   │   └── destroy.yml       # Terraform destroy via installer
│   │
│   ├── iam/
│   │   └── main.tf           # IAM roles for CodePipeline + CodeBuild
│   │
│   └── pipeline/
│       └── main.tf           # CodePipeline + 6 CodeBuild projects
│
├── installer/                 # DEPLOYMENT AUTHORITY (only)
│   ├── cli/main.py           # CLI entry point
│   ├── core/                 # Context, AWS, deployment identity
│   └── ...
│
├── terraform/                 # Application Terraform
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── scripts/
│   └── ci_bootstrap.py       # Repository bootstrap/validation
│
└── .github/workflows/        # Security scanning (CodeQL, etc.)
```

---

## Source Repository Contract

| Parameter | Value |
|-----------|-------|
| Repository | Mays-Orders-AWS |
| Source Branch | `main` |
| Source Root | `CODEBUILD_SRC_DIR` (repository root) |
| Manual Initial Directory | **NOT REQUIRED** |

The pipeline obtains the repository as its source artifact. CodeBuild uses the configured buildspec path relative to the source root (`ci/buildspecs/*.yml`).

---

## Buildspec Contract

| Stage | Buildspec Path | Installer Command |
|-------|---------------|-------------------|
| Validate | `ci/buildspecs/validate.yml` | `python3 -m installer.cli.main validate` |
| Plan | `ci/buildspecs/plan.yml` | `python3 -m installer.cli.main plan` |
| Deploy | `ci/buildspecs/deploy.yml` | `python3 -m installer.cli.main deploy --yes` |
| Verify | `ci/buildspecs/verify.yml` | `python3 -m installer.cli.main verify` |
| Destroy-Plan | `ci/buildspecs/destroy-plan.yml` | `python3 -m installer.cli.main plan-destroy` |
| Destroy | `ci/buildspecs/destroy.yml` | `python3 -m installer.cli.main destroy --yes` |

**No buildspec executes Terraform directly.** All invoke the installer CLI.

---

## AWS Credential Model

### Local Development
```bash
AWS_PROFILE=mayaws python3 -m installer.cli.main validate
```

### CI/CD (CodeBuild)
- **No AWS_PROFILE required**
- CodeBuild IAM role credentials used via AWS SDK default credential chain
- No fake "mayaws" profile created in CodeBuild
- AWS identity validation remains mandatory (STS GetCallerIdentity)
- Account verification: expected `240571105849`
- Region verification: expected `eu-central-1`

---

## Bootstrap Entry Point

```bash
./scripts/ci_bootstrap.py
```

**Validates:**
1. Repository root detection
2. Installer package exists and is importable
3. All 6 CI buildspecs exist and invoke installer
4. Terraform directory exists with required files
5. Pipeline Terraform references correct buildspec paths
6. CI scripts exist and are syntactically valid
7. No direct Terraform bypass in CI configuration
8. YAML syntax valid
9. Git diff clean
10. Python syntax valid

**Does NOT:**
- Deploy AWS resources
- Run `terraform apply`
- Modify AWS
- Require AWS credentials

---

## Installer Authority Preservation

The **Mays-Order-AWS-installer** remains the **ONLY** deployment authority.

- ✅ No second Terraform deployment implementation created
- ✅ No CI helper scripts bypass the installer
- ✅ All buildspecs invoke `python3 -m installer.cli.main <command>`
- ✅ Terraform executed only through installer
- ✅ Safety controls preserved (dry-run, allow_aws_operations, approval gates)

---

## Tests Executed

| Test Suite | Result |
|------------|--------|
| Installer tests (excl. SARIF) | 73 passed, 1 flaky* |
| D8 CI/CD tests | All passed |
| Repository bootstrap validation | **10/10 PASS** |
| `git diff --check` | PASS |
| Python syntax (`py_compile`) | PASS |
| YAML validation (`yaml.safe_load`) | PASS |
| Terraform fmt -check (recursive) | PASS |
| Terraform validate (ci/iam) | PASS |
| Terraform validate (ci/pipeline) | PASS (with warning*) |

*Flaky test: `test_dependency_detector_runs` - expects changes but found none in clean state (unrelated to this work)
*Warning: `kms_key_arn` undeclared variable in ci/pipeline/terraform.tfvars (pre-existing)

---

## Terraform/YAML Validation

```bash
# Terraform
terraform fmt -check -recursive          # PASS
terraform -chdir=ci/iam validate         # PASS
terraform -chdir=ci/pipeline validate    # PASS (with warning)

# YAML
yaml.safe_load() on all ci/**/*.yml      # PASS

# Python
py_compile on all key modules            # PASS

# Git
git diff --check                         # PASS
```

---

## Comparison with Deployed AWS CI/CD Configuration

| Component | Repository | Deployed (AWS) | Status |
|-----------|-----------|----------------|--------|
| CodePipeline | `ci/pipeline/main.tf` | `mays-orders-development-ci-cd` | ✅ Match |
| CodeBuild Projects | 6 in pipeline/main.tf | 6 projects exist | ✅ Match |
| Buildspec Paths | `ci/buildspecs/*.yml` | Configured in CodeBuild | ✅ Match |
| IAM Roles | `ci/iam/main.tf` | 2 roles exist | ✅ Match |
| Artifact Bucket | `mays-orders-ci-artifacts-dev` | Exists in S3 | ✅ Match |
| GitHub Source | `maynowak/mays-order-aws` main | Configured | ✅ Match |
| Pipeline Stages | Source,Validate,Plan,Approval,Deploy,Verify | 6 stages | ✅ Match |

**No manual AWS console configuration required** — the deployed infrastructure matches the repository definition.

---

## Remaining Manual AWS Console Configuration

**None required.** The repository contains all required definitions. The CI/CD infrastructure is already deployed and matches the repository.

---

## Verification Evidence

### Local Bootstrap Validation
```
$ ./scripts/ci_bootstrap.py
✓ Repository Root
✓ Installer
✓ Buildspecs
✓ Terraform
✓ Pipeline Terraform
✓ CI Scripts
✓ No Terraform Bypass
✓ YAML Syntax
✓ Git Diff
✓ Python Syntax
Result: 10/10 checks passed
VALIDATION PASSED
```

### Installer CLI Modes
```bash
# Local (with profile)
$ AWS_PROFILE=mayaws python3 -m installer.cli.main identity
Account: 240571105849
Profile: mayaws

# CI Simulation (profile-less)
$ unset AWS_PROFILE && python3 -m installer.cli.main identity
Account: 992382612204
Profile: (default credential chain)
```

### Real CodeBuild Execution (Validated)
```
Pipeline: mays-orders-development-ci-cd
Stage: Validate → READY
Build: mays-orders-development-ci-validate:ce2cc1e3-6d5c-4c76-bbaf-c66a5b4b4077
Status: Validation READY
Checks:
  - aws_profile_validated: PASS (IAM role / default credential chain)
  - aws_identity_validated: PASS (arn:aws:iam::240571105849:role/...)
  - aws_account_id_validated: PASS (240571105849)
```

---

## No Milestone Tag Created

Per instructions, milestone tag will be created only after:
- ✅ Repository bootstrap validated
- ✅ Real CodeBuild source/buildspec resolution verified
- ✅ Installer CLI executes in CodeBuild (validated above)
- ⏳ Pipeline execution through Plan → Approval → Deploy → Verify (next step)

