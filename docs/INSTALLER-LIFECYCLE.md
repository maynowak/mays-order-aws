# Installer Lifecycle Documentation

## Overview

This document describes the complete deployment lifecycle for the Mays Recruiting Intelligence Installer, covering Milestone D0-D5 and future milestones.

## Lifecycle Overview

```
DISCOVER
    ↓
VALIDATE
    ↓
PLAN
    ↓
APPROVE
    ↓
APPLY
    ↓
VERIFY
    ↓
TEST
    ↓
DESTROY PLAN
```

### Current Milestone: D0-D5 (Foundation)

| Phase | Status | Description |
|-------|--------|-------------|
| D0 - Discovery | ✅ Complete | Inventory existing components |
| D1 - Validation | ✅ Complete | Pre-flight validation layer |
| D2 - Terraform Init | ✅ Complete | Controlled initialization |
| D3 - Terraform Validate | ✅ Complete | Configuration validation |
| D4 - Deploy Plan | ✅ Complete | Plan generation & analysis |
| D5 - Destroy Plan | ✅ Complete | Destroy plan generation |

### Future Milestones

| Milestone | Phase | Status | Description |
|-----------|-------|--------|-------------|
| D6 | Approve | 📋 Planned | Approval gate design |
| D7 | Apply | 📋 Planned | Terraform apply with approval |
| D8 | Verify | 📋 Planned | Post-apply verification |
| D9 | Test | 📋 Planned | Full E2E test execution |
| D10 | Destroy Plan | 📋 Planned | Destroy plan execution |

---

## Phase Details

### D0 - Discovery
**Status:** ✅ Complete

**Objective:** Inventory all existing components and document current state.

**Activities:**
- Inventory Python structure (`lambda/src/`, `installer/`, `scripts/`)
- Inventory Terraform modules (`terraform/modules/*`)
- Inventory existing CLI/scripts (`scripts/`, `tests/`)
- Inventory documentation (`docs/`, `architecture/`)
- Inventory existing tests (`lambda/tests/`, `scripts/tests/`, `tests/`)

**Deliverables:**
- Component inventory (this document)
- Dependency map

---

### D1 - Validation
**Status:** ✅ Complete

**Objective:** Implement pre-flight validation layer.

**Component:** `installer/core/context.py` → `ValidationLayer`

**Checks Implemented:**
1. **AWS Profile** - Profile exists in `~/.aws/config`
2. **AWS Identity** - `sts:get-caller-identity` succeeds
3. **Account ID** - Retrieved and stored
4. **Region** - Valid AWS region
5. **Terraform CLI** - `terraform` in PATH
6. **Terraform Version** - ≥ 1.5.0
7. **Working Directory** - `terraform/` exists
8. **Terraform Config** - `main.tf`, `variables.tf`, `outputs.tf` present
9. **Installer Config** - Project name, environment set

**Output:** `ValidationResult` with structured checks:
```python
ValidationResult:
  status: READY | BLOCKED | WARNING
  checks[]: {name, status, message, details}
  errors[]
  warnings[]
```

**CLI:** `Mays-Order-AWS-installer validate [--output json|text]`

---

### D2 - Terraform Init
**Status:** ✅ Complete

**Objective:** Controlled Terraform initialization.

**Component:** `installer/terraform/runner.py` → `TerraformRunner.init()`

**Features:**
- Configurable backend initialization (`-backend=false` for dry-run)
- Provider upgrade support (`-upgrade`)
- Backend reconfiguration (`-reconfigure`)
- Structured result with timing

**Implementation:**
```python
runner = TerraformRunner("terraform")
result = runner.init(backend=False)  # dry-run
result = runner.init(upgrade=True)   # upgrade providers
```

**CLI:** Integrated in `mays-installer plan` (automatic)

---

### D3 - Terraform Validate
**Status:** ✅ Complete

**Objective:** Validate Terraform configuration.

**Component:** `installer/terraform/runner.py` → `TerraformRunner.validate()`

**Implementation:**
```python
runner = TerraformRunner("terraform")
result = runner.validate()
# Returns TerraformResult with exit_code, stdout, stderr
```

**Validation Checks:**
- Syntax validation
- Reference validation
- Provider compatibility

**CLI:** Integrated in `mays-installer plan` (automatic)

---

### D4 - Deploy Plan
**Status:** ✅ Complete

**Objective:** Generate and analyze deployment plan.

**Component:** `installer/terraform/runner.py` → `TerraformRunner.plan()`

**Features:**
- Generate plan file: `terraform plan -out=deploy.tfplan`
- JSON output: `terraform show -json deploy.tfplan`
- Structured analysis: `PlanResult` with counts
- Safety evaluation: `evaluate_plan_safety()`

**PlanResult Structure:**
```python
PlanResult:
  mode: "deploy" | "destroy"
  plan_file: str
  add: int
  change: int
  destroy: int
  replace: int
  resources: []
  warnings: []
  success: bool
```

**CLI:** `Mays-Order-AWS-installer plan [--out deploy.tfplan] [--var KEY=VAL] [--var-file FILE] [--destroy]`

---

### D5 - Destroy Plan
**Status:** ✅ Complete

**Objective:** Generate destroy plan for lifecycle completeness.

**Component:** `installer/terraform/runner.py` → `TerraformRunner.plan_destroy()`

**Implementation:**
```python
runner = TerraformRunner("terraform")
result = runner.plan_destroy(out_file="destroy.tfplan")
```

**Output:** `PlanResult` with destroy counts

**CLI:** `Mays-Order-AWS-installer plan-destroy [--out destroy.tfplan]`

---

## Future Milestones

### D6 - Approve & Apply (✅ IMPLEMENTED)

**Objective:** Implement `mays-installer deploy` with approval gate and `mays-installer destroy`.

**Components Implemented:**

#### Deploy Command (`Mays-Order-AWS-installer deploy`)
- **Approval Gate**: Human approval required (default NO)
- **Plan File**: Uses saved deploy plan (`deploy.tfplan`)
- **Safety Evaluation**: Automatic safety analysis before approval
- **Profile Binding**: Uses validated AWSExecutionContext
- **Post-Apply Verification**: Terraform state check + AWS identity verification
- **CLI Options**: `--plan` (default: auto-detect latest from `.mays-installer/runs/*/plans/deploy.tfplan`), `--yes` (skip approval)

**CLI Options:**
```
Mays-Order-AWS-installer deploy [--plan <path>] [--yes]
```

**Example Output:**
```
=== DEPLOYMENT APPROVAL ===
Profile: mayaws
Account: 240571105849
Region: eu-central-1
Plan file: deploy.tfplan
Plan: 37 to add, 0 to change, 0 to destroy, 0 to replace

Safety Analysis: PASS
  ✓ Plan validity: PASS
  ✓ No unexpected destroys: PASS
  ✓ No replacements: PASS

Proceed with deployment? [y/N]: 
```

#### Destroy Command (`Mays-Order-AWS-installer destroy`)
**Objective:** Apply a saved destroy plan with safety evaluation.

**CLI Options:**
```
Mays-Order-AWS-installer destroy [--plan <path>] [--yes]
```

**Note:** If `--plan` is omitted, the latest destroy plan is auto-detected from `.mays-installer/runs/*/plans/destroy.tfplan`.

**Features:**
- **Approval Gate**: Explicit confirmation required (default NO)
- **Safety Evaluation**: Evaluates destroy plan for safety
- **Profile Binding**: Uses validated AWSExecutionContext
- **Post-Destroy Verification**: Terraform state accessibility check

#### Policy Gate Integration
**File:** `terraform/policy/validate-plan.py`

**Rules Enforced During Apply:**
- Allowed resource types
- Required tags (Project, Maker, Environment)
- Lambda runtime, timeout, log retention
- DynamoDB billing mode (PAY_PER_REQUEST)
- S3 bucket naming, encryption, public access
- CloudTrail multi-region, log validation
- IAM role naming
- Region allowlist

**Exit Codes:**
- `0` - PASS
- `1` - FAIL (policy violations)
- `2` - Usage/config error

---

### D7 - Safety Gate Integration & Testing (✅ COMPLETED)

**Status:** ✅ **COMPLETED**

**Objective:** Policy gate integration, tests for new commands, documentation.

**Components Implemented:**

#### Policy Gate Integration (✅ COMPLETED)
- Policy gate check integrated into `mays-installer deploy` command
- Runs before approval gate, blocks deployment on policy violations
- Skipped in dry-run mode (providers not initialized)
- Uses existing `terraform/policy/validate-plan.py` policy gate
- Clear error messages on policy violation

**CLI Flow:**
```
Mays-Order-AWS-installer deploy
→ Validation → Init → Validate → Plan → Safety Analysis
→ Policy Gate Check → Approval Gate → Apply → Post-Apply Verification
```

#### Tests for New Commands (✅ COMPLETED)
- All 100 unit tests pass (100/100)
- Integration test script passes (D0-D5 + deploy/destroy)
- Policy gate integration tested

---

### H1 — Security & Execution Hardening (✅ COMPLETED)

**Status:** ✅ **COMPLETED**

**Objective:** Perform a hardening review and implementation pass over the existing installer.

**Components Implemented:**

#### 1. AWS Execution Boundary
- Every Terraform operation uses validated `AWSExecutionContext`
- `AWS_PROFILE` and `AWS_REGION` explicitly passed to Terraform via environment
- No silent fallback to ambient AWS credentials
- `TerraformRunner` constructor requires validated `AWSExecutionContext`
- CLI commands call `context.validate_aws_context()` before any Terraform operation

#### 2. Mutation Boundary
**Required Path:** VALIDATION → PLAN → SAFETY → POLICY GATE → APPROVAL → SAVED PLAN → APPLY → VERIFY

**Mutation Operations (require full path):**
- `mays-installer deploy` — applies deployment plan
- `mays-installer destroy` — applies destroy plan
- `mays-installer state push` — pushes state to remote

**Read-Only Operations (validation + profile binding only):**
- `mays-installer validate` — validation only
- `mays-installer plan` / `plan-destroy` — plan generation only
- `mays-installer state list|show|pull` — state inspection
- `mays-installer output` — output values
- `mays-installer identity` — AWS identity info

No mutation may bypass the required path.

#### 3. --Yes Flag Behavior
The `--yes` flag skips **only** the interactive human approval prompt.

**It MUST NOT bypass (and does not):**
- AWS identity validation (`validate_aws_context()`)
- Account validation (STS caller identity)
- Region validation
- Plan integrity verification (`verify_plan_integrity()`)
- Safety evaluation (`evaluate_plan_safety()`)
- Policy gate check (unless in dry-run mode)
- Saved-plan requirement
- Plan context matching (`verify_plan_context_match()`)

#### 4. Dry-Run Behavior
**Environment Variables:**
- `DRY_RUN=true` (default) — enables dry-run mode
- `ALLOW_AWS_OPERATIONS=false` (default) — blocks all mutations
- `--dry-run` CLI flag — controls Terraform backend initialization

**Behavior Matrix:**

| Command | DRY_RUN=true | DRY_RUN=false + ALLOW_AWS_OPS=false | DRY_RUN=false + ALLOW_AWS_OPS=true |
|---------|--------------|-------------------------------------|-------------------------------------|
| validate | ✅ Runs validation | ✅ Runs validation | ✅ Runs validation |
| plan | ✅ Plan (no backend) | ✅ Plan (with backend) | ✅ Plan (with backend) |
| deploy | ❌ Blocked (no ALLOW_AWS_OPS) | ❌ Blocked (no ALLOW_AWS_OPS) | ✅ Apply (with policy gate) |
| destroy | ❌ Blocked (no ALLOW_AWS_OPS) | ❌ Blocked (no ALLOW_AWS_OPS) | ✅ Destroy (with safety) |
| state push | ❌ Blocked (no ALLOW_AWS_OPS) | ❌ Blocked (no ALLOW_AWS_OPS) | ✅ Push state |

**No ambiguity:** "Plan without mutation" = plan command; "Apply disabled" = blocked by ALLOW_AWS_OPERATIONS.

#### 5. Plan Integrity
Apply can only use a plan that:
- ✅ Exists (file presence check)
- ✅ Belongs to current run (run directory check)
- ✅ Has successful generation (valid plan file)
- ✅ Passed analysis (safety evaluation)
- ✅ Passed policy gate (before apply)
- ✅ Matches current AWS execution context (region check via `verify_plan_context_match()`)

**If context changes:** BLOCKED with clear error message.

#### 6. Policy Gate
- Executed before mutation (in `deploy` command)
- `--yes` cannot bypass it
- Policy failure prevents apply (returns exit code 1)
- Uses existing `terraform/policy/validate-plan.py` — no second policy engine

#### 7. Destroy Safety
Destroy requires:
- ✅ Destroy plan (`plan-destroy` command)
- ✅ Safety analysis (`evaluate_plan_safety` with mode="destroy")
- ✅ Policy evaluation (where applicable)
- ✅ Approval unless explicitly skipped (`--yes`)
- ✅ Validated AWS identity
- ✅ Exact saved destroy plan (plan integrity + context match)
- ✅ No automatic retry
- ✅ No automatic destroy after failed deployment

#### 8. Credentials & Secrets
- ✅ AWS credentials never logged (validated via STS, not stored)
- ✅ Secret values never logged (plan output shows resource attributes only)
- ✅ Plan JSON sanitization active (`PlanArtifactManager.sanitize_plan_json()`)
- ✅ State files not committed (`.gitignore` excludes `*.tfstate`, `.terraform/`)
- ✅ `.terraform` directories ignored
- ✅ No secrets in test fixtures

#### 9. State Command Classification

| Command | Classification | AWS Context Required | ALLOW_AWS_OPERATIONS Required |
|---------|---------------|---------------------|-------------------------------|
| `state list` | READ_ONLY | Yes | No |
| `state show` | READ_ONLY | Yes | No |
| `state pull` | READ_ONLY | Yes | No |
| `state push` | MUTATING | Yes | **Yes** |
| `output` | READ_ONLY | Yes | No |
| `identity` | READ_ONLY | Yes | No |

All commands use validated `AWSExecutionContext`.

---

### H2 — Versioned Deployment Identity, Plan Isolation & AWS Tagging (✅ COMPLETED)

**Status:** ✅ **COMPLETED**

**Objective:** Extend the installer so that multiple projects can safely coexist inside the same AWS account and region without interfering with each other.

**Components Implemented:**

#### 1. Deployment Identity
- Canonical `DeploymentId` derived from: `<account>:<project>:<environment>`
- Example: `240571105849:mays-orders:development`
- Version is NOT part of deployment identity - it's an upgrade of the same deployment
- Available through central `DeploymentContext` / `AWSExecutionContext`
- Installer validates current AWS account, project, environment match expected Deployment ID before any mutation

#### 2. Versioned Development State
- Semantic versioning: `major.minor.patch` (e.g., `0.3.0`)
- Development phase/step: `H2`, `H217`, `D8`, etc.
- Development status: `development`, `testing`, `staging`, `production`, `archived`
- Comparison model distinguishes:
  - `SAME` — identical version and phase
  - `DEVELOPMENT_UPDATE` — same version, different step
  - `PATCH_UPDATE` — patch version change
  - `MINOR_UPGRADE` — minor version change
  - `MAJOR_UPGRADE` — major version change
  - `MIGRATION_REQUIRED` / `INCOMPATIBLE` — incompatible changes

#### 3. Plan Identity
- Structured plan filenames with all identity metadata:
  - Format: `<project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>.tfplan`
  - Deploy example: `mays-orders-development-0.3.0-H2-240571105849-deploy-0042.tfplan`
  - Destroy example: `mays-orders-development-0.3.0-H2-240571105849-destroy-0043.tfplan`
- Monotonically increasing sequence number per deployment+operation
- Plan metadata stored as JSON alongside plan file (`.meta.json`)
- Deployment context saved alongside plan (`.context.json`)

#### 4. Plan Discovery / Auto-Selection
- Hardened automatic plan discovery using `PlanDiscovery` class
- Plans filtered by: Deployment ID, Version, Development Phase, Operation
- Filename is NOT the sole security mechanism - metadata/context validated
- Mismatch results in hard stop
- `--yes` CANNOT bypass context/version/phase mismatch validation

#### 5. Destroy Isolation
- Destroy explicitly scoped to current deployment identity
- Resources belonging to another Deployment ID are not destroyable
- Resources with ambiguous ownership surfaced, not silently adopted
- H1 destroy safety mechanisms remain intact

#### 6. AWS Resource Tagging
- Canonical tagging model (`TagSet`):
  - **Required identity tags:** Project, Environment, DeploymentId
  - **Version/development tags:** Version, DevelopmentPhase, DevelopmentStep
  - **Governance tags:** ManagedBy, Owner, Maker
  - **System/component tags:** System, Component
  - **Custom tags:** Prefixed with `Custom:` to avoid conflicts
- Merges with existing tags preserving unrelated tags
- Canonical tags take precedence for identity/version metadata

#### 7. Existing Resource / Upgrade Awareness
- `OwnershipAnalyzer` classifies existing resources:
  - `OWNED` — belongs to current deployment
  - `FOREIGN` — belongs to different project/environment/account
  - `AMBIGUOUS` — same deployment ID but different version/phase
  - `UNMANAGED` — no deployment metadata
- Ambiguous ownership surfaced, not silently adopted
- Existing resources considered in future upgrade planning

#### 8. Configuration / Context Separation
- **INSTALLER CONTEXT:** installer name, version, commit
- **TARGET CONTEXT:** AWS account, region, project, environment, deployment ID, version, development phase/step
- Installer repository never confused with target project

---

### 📋 REMAINING TASKS

| Task | Priority | Status |
|------|----------|--------|
| Final documentation review | Medium | Pending |

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Installer CLI                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  validate   │  │    plan     │  │    plan-destroy     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼─────────────────────┼─────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Validation Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ AWS Profile │  │  Terraform  │  │   Installer Config  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Terraform Runner                           │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌───────┐ │
│  │ version │ │   init   │ │ validate │ │  plan  │ │ show  │ │
│  └─────────┘ └──────────┘ └──────────┘ └────────┘ └───────┘ │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Plan Analysis & Safety                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ PlanResult   │ │ Safety Eval  │ │ Policy Gate          │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Run Directory Manager                      │
│  ┌──────────┐ ┌────────────┐ ┌─────────┐ ┌────────────────┐ │
│  │ context  │ │ validation │ │  plans  │ │   artifacts    │ │
│  └──────────┘ └────────────┘ └─────────┘ └────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Safety & Policy

### Plan Safety Evaluation

**File:** `installer/terraform/plan_analysis.py`

**Checks:**
1. **Unexpected destroys in deploy** → WARNING/BLOCKED
2. **Resource replacements** → WARNING
3. **Large plans** (>50 changes) → WARNING
4. **Policy gate** → BLOCKED on violations

**Safety Levels:**
- `PASS` - All checks pass
- `WARNING` - Proceed with caution
- `BLOCKED` - Must resolve before proceeding

### Policy Gate

**File:** `terraform/policy/validate-plan.py`

**Rules Enforced:**
- Allowed resource types
- Required tags (Project, Maker, Environment)
- Lambda runtime, timeout, log retention
- DynamoDB billing mode (PAY_PER_REQUEST)
- S3 bucket naming, encryption, public access
- CloudTrail multi-region, log validation
- IAM role naming
- Region allowlist

**Exit Codes:**
- `0` - PASS
- `1` - FAIL (policy violations)
- `2` - Usage/config error

---

## Run Directory Structure

```
.mays-installer/runs/<run-id>/
├── context.json              # InstallationContext
├── validation.json           # ValidationResult
├── deploy.tfplan             # Terraform plan file (binary)
├── deploy-plan.json          # PlanResult JSON
├── destroy.tfplan            # Destroy plan file
├── destroy-plan.json         # Destroy plan analysis
├── execution.log             # Execution log
├── report.md                 # Run report
├── logs/
│   ├── terraform_init.log
│   ├── terraform_validate.log
│   ├── terraform_plan_deploy.log
│   ├── terraform_plan_destroy.log
│   └── policy_gate.log
└── plans/
    ├── deploy.tfplan
    ├── deploy-plan.json
    ├── destroy.tfplan
    └── destroy-plan.json
```

### Plan Artifact Sanitization

Plan files can contain sensitive data. The `PlanArtifactManager` sanitizes:

```python
PlanArtifactManager.sanitize_plan_json(plan_json)
# Removes: password, secret, key, token, credential from all resource attributes
```

---

## CLI Reference

### `Mays-Order-AWS-installer validate`

```bash
Mays-Order-AWS-installer validate [--output json|text]
```

**Options:**
- `--output json|text` - Output format (default: text)

**Exit Codes:**
- `0` - All checks passed
- `1` - Validation blocked

---

### `Mays-Order-AWS-installer plan`

```bash
Mays-Order-AWS-installer plan [--out deploy.tfplan] [--var KEY=VAL] [--var-file FILE] [--destroy]
```

**Options:**
- `--out FILE` - Output plan file (default: deploy.tfplan)
- `--var KEY=VAL` - Set variable (repeatable)
- `--var-file FILE` - Variable file
- `--destroy` - Generate destroy plan

**Exit Codes:**
- `0` - Plan generated successfully
- `1` - Plan generation failed or blocked

---

### `Mays-Order-AWS-installer plan-destroy`

```bash
Mays-Order-AWS-installer plan-destroy [--out destroy.tfplan]
```

**Alias for:** `mays-installer plan --destroy --out destroy.tfplan`

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_PROFILE` | `mayaws` | AWS CLI profile |
| `AWS_REGION` | `eu-central-1` | AWS region |
| `AWS_ACCOUNT_ID` | - | AWS account ID (auto-detected) |
| `AWS_IDENTITY_ARN` | - | Caller identity ARN (auto-detected) |
| `PROJECT_NAME` | `mays-orders` | Project name |
| `ENVIRONMENT` | `Development` | Environment name |
| `COGNITO_MODE` | `user_pool` | Cognito mode |
| `COGNITO_USER_POOL_ID` | - | Cognito user pool ID |
| `COGNITO_CLIENT_ID` | - | Cognito client ID |
| `TERRAFORM_DIR` | `terraform` | Terraform directory |
| `TERRAFORM_WORKSPACE` | `default` | Terraform workspace |
| `ALLOW_AWS_OPERATIONS` | `false` | Allow AWS mutations |
| `DRY_RUN` | `true` | Dry-run mode |

### Configuration File (Optional)

Create `.mays-installer/config.json`:
```json
{
  "aws_profile": "mayaws",
  "aws_region": "eu-central-1",
  "project_name": "mays-orders",
  "environment": "Development",
  "terraform_dir": "terraform",
  "dry_run": true
}
```

---

## Usage Examples

### Quick Validation
```bash
Mays-Order-AWS-installer validate
```

### Generate Deploy Plan
```bash
Mays-Order-AWS-installer plan --out deploy.tfplan
```

### Generate Destroy Plan
```bash
Mays-Order-AWS-installer plan-destroy --out destroy.tfplan
```

### Full Dry-Run Cycle
```bash
# Using the test script
./scripts/test_plan.sh --dry-run

# Or using the installer directly
Mays-Order-AWS-installer validate
Mays-Order-AWS-installer plan
Mays-Order-AWS-installer plan-destroy
```

### With Custom Variables
```bash
Mays-Order-AWS-installer plan --out deploy.tfplan \
  --var project_name=my-project \
  --var aws_region=us-east-1 \
  --var-file prod.tfvars
```

### Complete H1 Hardened Deployment Workflow
```bash
# 1. Validation (read-only, no mutations)
Mays-Order-AWS-installer validate

# 2. Generate deploy plan (read-only)
Mays-Order-AWS-installer plan
# Output shows: "Deploy with: ./Mays-Order-AWS-installer deploy --plan .mays-installer/runs/.../plans/deploy.tfplan"

# 3. Enable AWS mutations for deployment
export ALLOW_AWS_OPERATIONS=true
export DRY_RUN=false

# 4. Deploy (auto-detects latest plan, no --plan needed)
Mays-Order-AWS-installer deploy --yes

# 5. Generate destroy plan (read-only)
Mays-Order-AWS-installer plan-destroy

# 6. Destroy (auto-detects latest destroy plan)
Mays-Order-AWS-installer destroy --yes
```

### Plan Auto-Detection
If `--plan` is omitted from `deploy` or `destroy`, the installer automatically finds the latest plan in `.mays-installer/runs/*/plans/`:

| Command | Auto-Detect Pattern |
|---------|---------------------|
| `deploy` | `.mays-installer/runs/*/plans/deploy.tfplan` |
| `destroy` | `.mays-installer/runs/*/plans/destroy.tfplan` |

This eliminates manual path copying and ensures the correct plan is always used.

---

## Security Considerations

### Plan File Sensitivity
- Plan files contain resource attributes
- May contain sensitive values (passwords, keys)
- Always sanitize before sharing: `PlanArtifactManager.sanitize_plan_json()`

### Credentials
- Never store AWS credentials in repo
- Use AWS CLI profiles (`aws configure --profile mayaws`)
- Use IAM roles in CI/CD

### State Management
- Local state for development
- Remote state (S3 + DynamoDB) for production
- Never commit `.terraform/` or `*.tfstate`

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `terraform init` fails | Backend config missing | Use `-backend=false` for dry-run |
| `terraform validate` fails | Syntax error | Run `terraform fmt` first |
| `plan` shows unexpected destroys | Resource replacement | Check for `replace` actions |
| `validate` fails on AWS profile | Profile not configured | Run `aws configure --profile mayaws` |

### Debugging

```bash
# Enable debug logging
export TF_LOG=DEBUG
export TF_LOG_PATH=terraform.log

# Verbose Terraform
terraform plan -out=plan.tfplan -verbose
```

---

## Next Steps

See [DEVELOPMENT-PLAN.md](DEVELOPMENT-PLAN.md) for:
- Milestone D6-D10 roadmap
- Open items
- Risk assessment
- Architecture protection rules