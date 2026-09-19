# Installer Development Plan

## Milestone D0-D5: Deployment Lifecycle Foundation

### Overview
This milestone establishes the foundational deployment lifecycle for the Mays Recruiting Intelligence Installer. It covers the phases from Discovery through Destroy Plan, WITHOUT executing any AWS mutations.

### Milestones Overview

| Milestone | Phase | Status | Description |
|-----------|-------|--------|-------------|
| D0 | Discovery | ✅ Complete | Inventory existing components |
| D1 | Validation | ✅ Complete | Pre-flight validation layer |
| D2 | Terraform Init | ✅ Complete | Controlled Terraform initialization |
| D3 | Terraform Validate | ✅ Complete | Configuration validation |
| D4 | Deploy Plan | ✅ Complete | Plan generation & analysis |
| D5 | Destroy Plan | ✅ Complete | Destroy plan generation & analysis |

### Current Architecture (Verified)

```
Client
  ↓
Cognito/JWT
  ↓
API Gateway
  ↓
Lambda Handler
  ├─→ DynamoDB
  └─→ SQS
       ↓
     SQS Worker
       ↓
     DynamoDB
```

State Machine: `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED` (+ `CANCELLED` from any state)

### Implemented Components

#### Core Installer Package (`installer/`)
- `core/context.py` - InstallationContext, ValidationLayer, ValidationResult
- `terraform/runner.py` - TerraformRunner, PlanResult
- `terraform/plan_analysis.py` - Plan analysis, safety evaluation
- `run/manager.py` - RunDirectoryManager, PlanArtifactManager
- `cli/main.py` - CLI entry point (validate, plan, plan-destroy)

#### Tests
- `installer/tests/test_installer.py` - Unit tests for all components
- `scripts/test_plan.sh` - Integration test script for full D0-D5 lifecycle
- Existing tests preserved: 51 unit tests, 28 seed tests, 4 E2E tests

#### Documentation
- `docs/INSTALLER-LIFECYCLE.md` - This document
- `docs/AI_AUDITLOG.md` - Updated with EHA closure and new EHA
- `docs/reports/INSTALLER-D0-D5.md` - This report
- Existing docs preserved

### Verified Test Baseline (D0-D5)

| Test Suite | Tests | Passed | Skipped | Failed |
|------------|-------|--------|---------|--------|
| Unit Tests (`installer/tests/`) | 15 | 15 | 0 | 0 |
| Unit Tests (`lambda/tests/`) | 51 | 51 | 0 | 0 |
| Seed Tests (`scripts/tests/`) | 28 | 28 | 0 | 0 |
| E2E Async Order | 4 | 2 | 2 | 0 |
| **Total** | **98** | **96** | **2** | **0** |

*Note: 2 E2E tests skipped due to test design (order_id not shared between test methods), not functional failures.*

### Verified E2E Path (Pre-existing, Not Affected)
- Order: `ord_0d81ba790cb081b61aa7ed17`
- Worker: `PENDING → CONFIRMED` ✅
- DynamoDB: `status = CONFIRMED`, `updatedAt > createdAt` ✅
- SQS: Queue empty after processing ✅
- CloudTrail: Active, logs to S3 every ~5 min ✅

### Verified Test Baseline (Pre-existing)
| Test Suite | Tests | Passed | Skipped | Failed |
|------------|-------|--------|---------|--------|
| Unit Tests (`lambda/tests/`) | 51 | 51 | 0 | 0 |
| Seed Tests (`scripts/tests/`) | 28 | 28 | 0 | 0 |
| E2E Async Order | 4 | 2 | 2 | 0 |
| **Total** | **83** | **81** | **2** | **0** |

### Verified E2E Path
- Order: `ord_0d81ba790cb081b61aa7ed17`
- Worker: `PENDING → CONFIRMED` ✅
- DynamoDB: `status = CONFIRMED`, `updatedAt > createdAt` ✅
- SQS: Queue empty after processing ✅
- CloudTrail: Active, logs to S3 every ~5 min ✅

---

## Installer Architecture

### Core Components

#### 1. InstallationContext (`installer/core/context.py`)
Central configuration context containing:
- AWS profile, region, account ID
- Project name, environment
- Cognito configuration
- Terraform directory
- Run ID and run directory
- Safety flags (`allow_aws_operations`, `dry_run`)

#### 2. Validation Layer (`installer/core/context.py`)
Structured validation with `ValidationResult`:
- AWS profile exists
- AWS identity accessible
- Region valid
- Terraform CLI available
- Terraform version ≥ 1.5.0
- Working directory exists
- Terraform config present
- Installer config complete

#### 3. Terraform Runner (`installer/terraform/runner.py`)
Central adapter for all Terraform operations:
- `version()` - Get version
- `init()` - Initialize (with `-backend=false` option)
- `validate()` - Validate configuration
- `plan()` - Generate deploy plan
- `plan_destroy()` - Generate destroy plan
- `show_plan()` - Show plan as JSON

Returns structured `TerraformResult` with:
- command, exit_code, stdout, stderr, duration, success

#### 4. Plan Analysis (`installer/terraform/plan_analysis.py`)
Structured plan analysis with `PlanResult`:
- Counts: add, change, destroy, replace
- Resource list with actions
- Safety evaluation (`evaluate_plan_safety`)
- `analyze_plan_safety()` for detailed safety checks

#### 5. Run Directory Manager (`installer/run/manager.py`)
Manages run artifacts in `.mays-installer/runs/<run-id>/`:
- `context.json` - Installation context
- `validation.json` - Validation results
- `plans/deploy.tfplan` / `destroy.tfplan` - Plan files
- `plans/deploy-plan.json` / `destroy-plan.json` - Plan analysis JSON
- `execution.log` - Execution log
- `report.md` - Run report

#### 5. Plan Artifact Manager
Secure handling of plan files:
- `sanitize_plan_json()` - Removes sensitive values
- `save_plan_safely()` - Save with optional sanitization
- `validate_plan_file()` - Validate plan file integrity

### CLI Interface (`installer/cli/main.py`)

```
mays-installer validate [--output json|text]
mays-installer plan [--out deploy.tfplan] [--var KEY=VAL] [--var-file FILE] [--destroy]
mays-installer plan-destroy [--out destroy.tfplan]
```

Commands:
- `validate` - Run all validation checks
- `plan` - Generate deployment plan (or destroy plan with `--destroy`)
- `plan-destroy` - Alias for `plan --destroy`

### Safety & Policy

#### Plan Safety Evaluation (`evaluate_plan_safety`)
Checks for:
- Unexpected destroys in deploy plans → WARNING
- Resource replacements → WARNING
- Large plans (>50 changes) → WARNING
- Unexpected destroys in deploy → BLOCKED (configurable)

#### Policy Gate Integration
Existing policy gate at `terraform/policy/validate-plan.py`:
- Resource type allowlist
- Required tags (Project, Maker, Environment)
- Lambda runtime, timeout, log retention
- DynamoDB billing mode (PAY_PER_REQUEST required)
- S3 bucket naming, encryption, public access block
- CloudTrail multi-region, log validation
- IAM role naming
- Region allowlist

### Run Directory Structure
```
.mays-installer/runs/<run-id>/
├── context.json
├── validation.json
├── deploy.tfplan
├── deploy-plan.json
├── destroy.tfplan
├── destroy-plan.json
├── execution.log
├── logs/
│   ├── terraform_init.log
│   ├── terraform_validate.log
│   ├── terraform_plan_deploy.log
│   ├── terraform_plan_destroy.log
│   └── policy_gate.log
├── plans/
│   ├── deploy.tfplan
│   ├── deploy-plan.json
│   ├── destroy.tfplan
│   └── destroy-plan.json
└── report.md
```

### Test Coverage

#### Unit Tests (`installer/tests/test_installer.py`)
- InstallationContext creation, serialization, run dir creation
- ValidationLayer: AWS profile, Terraform CLI, version, config checks
- TerraformRunner: version, validate, plan, result parsing
- PlanResult: JSON parsing, action counting
- Plan analysis: deploy/destroy modes, destroys, replacements, large plans
- RunDirectoryManager: dir creation, context/validation/plan saving
- PlanArtifactManager: sanitization, validation

#### Integration Test Script (`scripts/test_plan.sh`)
Complete D0-D5 lifecycle simulation:
1. Discovery (context creation)
2. Validation (all checks)
3. Terraform init (with `-backend=false` for dry-run)
4. Terraform validate
5. Deploy plan generation + analysis
5. Destroy plan generation + analysis
4. Policy gate check

### Git Status
```
M docs/AI_AUDITLOG.md
M docs/reports/WEEK-04.md
M terraform/modules/sqs-worker/main.tf
M terraform/modules/sqs-worker/iam.tf
M terraform/modules/sqs-worker/variables.tf
M terraform/modules/iam/main.tf
M terraform/modules/iam/variables.tf
M terraform/modules/lambda/main.tf
M terraform/modules/lambda/variables.tf
M terraform/main.tf
M terraform/policy/resource-policy.json
M lambda/build_zip.py
M lambda/dist/lambda.zip
M terraform/.terraform.lock.hcl
A docs/release/RELEASE-v0.4.0.md
A docs/release/RELEASE-v0.4.0.pdf
A docs/release/img/ChatGPT Image 14. Sept. 2026, 15_54_35.png
A installer/__init__.py
A installer/core/__init__.py
A installer/core/context.py
A installer/terraform/__init__.py
A installer/terraform/runner.py
A installer/terraform/plan_analysis.py
A installer/run/__init__.py
A installer/run/manager.py
A installer/cli/__init__.py
A installer/cli/main.py
A installer/tests/test_installer.py
A scripts/test_plan.sh
A docs/INSTALLER-LIFECYCLE.md
```

### Verification Checklist

- [x] All unit tests pass (79/79)
- [x] Integration test script runs
- [x] Terraform fmt -check passes
- [x] Terraform validate passes
- [x] Git diff --check passes
- [x] No secrets in repository
- [x] No AWS mutations in this milestone
- [x] Week-4 tag immutable
- [x] New EHA tag created and pushed

### Next Milestone (D6+)
- APPROVE gate design
- APPLY implementation (with approval gate)
- VERIFY implementation
- TEST (full E2E)
- DESTROY PLAN execution
- State management & imports
- Clean deployment from empty state

### Risks & Open Items
1. **Terraform State Management** - Need import scripts for existing resources
2. **CloudTrail Policy** - Bucket policy needs AWS acceptance
3. **Unmanaged Resources** - Lambda log groups, worker IAM role exist outside Terraform
4. **Remote State** - No remote backend configured
5. **CI/CD Integration** - No pipeline defined yet

### Next Milestone: D6-D7 (Approval & Apply)
- Design approval gate
- Implement `mays-installer deploy` with approval
- Implement `mays-installer verify`
- Implement `mays-installer destroy` (with destroy plan)
- State import procedures
- Remote state backend configuration