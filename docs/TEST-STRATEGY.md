# Test Strategy — Mays Recruiting Intelligence Installer

## Overview

This document defines the test strategy for the Mays Recruiting Intelligence Installer, covering the Deployment Lifecycle Foundation (Milestone D0-D5) and future milestones.

## Test Pyramid

```
                    ┌─────────────────┐
                    │   E2E Tests     │  ← Few, high confidence
                    │   (4 tests)     │
                ┌───┴────────────────┴───┐
                │   Integration Tests    │  ← Medium, integration points
                │   (scripts/test_plan)  │
            ┌───┴────────────────────────┴───┐
            │      Unit Tests (98)           │  ← Many, fast, isolated
            │  • Context, Validation         │
            │  • Terraform Runner            │
            │  • Plan Analysis               │
            │  • Run Directory Manager       │
            └────────────────────────────────┘
```

## Test Categories

### 1. Unit Tests (Fast, Isolated, Many)
**Location:** `installer/tests/test_installer.py`, `lambda/tests/`, `scripts/tests/`

**Characteristics:**
- No external dependencies (mocked)
- Fast execution (< 1s total)
- Test single units in isolation
- Run on every commit

**Coverage Targets:**
- `InstallationContext`: 100%
- `ValidationLayer`: 90%+
- `TerraformRunner`: 90%+
- `PlanResult`: 100%
- `PlanResult`: 100%
- `RunDirectoryManager`: 90%+
- `PlanArtifactManager`: 100%
- `PlanAnalysis`: 90%+

### 2. Integration Tests (Medium, Real Dependencies)
**Location:** `scripts/test_plan.sh`, `tests/test_e2e_async_order.py`

**Characteristics:**
- Test component interactions
- Use real Terraform CLI (mocked or real)
- Use real AWS APIs (with test credentials)
- Run on PR/merge

**Scenarios:**
- Full D0-D5 lifecycle simulation
- E2E async order flow
- Seed data import/export
- Policy gate validation

### 3. E2E Tests (Slow, Real Infrastructure)
**Location:** `tests/test_e2e_async_order.py`

**Characteristics:**
- Full AWS deployment
- Real Cognito authentication
- Real API Gateway, Lambda, DynamoDB, SQS
- Run on release or manual trigger

**Current Status:**
- 4 tests, 2 pass, 2 skipped (test design limitation)
- Verified: Order creation → SQS → Worker → DynamoDB CONFIRMED

### 4. Contract Tests (Policy Gate)
**Location:** `terraform/policy/validate-plan.py`

**Characteristics:**
- Validates Terraform plan against policy
- Run on every plan
- Must pass before apply

## Test Data Strategy

### Unit Tests
- **No real AWS calls** - all mocked
- Use `unittest.mock` for AWS CLI, Terraform CLI
- In-memory fake clients for DynamoDB, SQS

### Integration Tests
- Use dedicated test AWS account/profile
- Unique resource names per run (UUID suffix)
- Cleanup in teardown

### E2E Tests
- Dedicated test Cognito user
- Unique order IDs per test
- Cleanup after test

### Seed Data Tests
- Use `database/seed/orders_seed_demo_50.json` (50 orders)
- Use `database/seed/orders_seed_1000.jsonl` (1000 orders)
- Idempotent import/export
- Fake DynamoDB client for unit tests

## Test Execution

### Local Development
```bash
# Unit tests
PYTHONPATH=lambda/src python3 -m pytest lambda/tests/ -v
PYTHONPATH=installer python3 -m pytest installer/tests/ -v
PYTHONPATH=scripts python3 -m pytest scripts/tests/ -v

# Integration (requires AWS credentials)
./scripts/test_plan.sh --dry-run
```

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: |
          PYTHONPATH=lambda/src python3 -m pytest lambda/tests/ -v
          PYTHONPATH=installer python3 -m pytest installer/tests/ -v
          PYTHONPATH=scripts python3 -m pytest scripts/tests/ -v

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-central-1
      - name: Run integration tests
        run: ./scripts/test_plan.sh --dry-run

  e2e-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    if: github.event_name == 'release'
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-central-1
      - name: Run E2E tests
        run: python3 -m pytest tests/test_e2e_async_order.py -v
```

## Test Data Management

### Test User Setup
```bash
# scripts/tests/setup_test_user.py
export AWS_PROFILE=mayaws
export TEST_USER_PASSWORD="TestPassword123!"
python3 scripts/tests/setup_test_user.py
```

### Seed Data
```bash
# Dry run
python3 scripts/seed_orders.py --table mays-orders --file database/seed/orders_seed_1000.jsonl --dry-run

# Actual import
python3 scripts/seed_orders.py --table mays-orders --file database/seed/orders_seed_demo_50.json
```

### Test Cleanup
```bash
# Delete demo seed orders
python3 scripts/delete_seed_orders.py --table mays-orders --file database/seed/orders_seed_demo_50.json
```

## Test Reporting

### Test Results Documentation
All test results documented in:
- `tests/test-results.md` - Test execution log
- `docs/reports/INSTALLER-D0-D5.md` - Milestone report
- `docs/AI_AUDITLOG.md` - AI audit log

### Test Result Format
```markdown
## Test Execution: <timestamp>
### Summary
- Total: 98
- Passed: 96
- Skipped: 2
- Failed: 0

### Details
| Suite | Tests | Passed | Skipped | Failed |
|-------|-------|--------|---------|--------|
| Unit | 51 | 51 | 0 | 0 |
| Seed | 28 | 28 | 0 | 0 |
| E2E | 4 | 2 | 2 | 0 |
| Installer | 15 | 15 | 0 | 0 |
| Total | 98 | 96 | 2 | 0 |
```

## Quality Gates

### Pre-commit
- `terraform fmt -check -recursive`
- `terraform validate`
- `git diff --check`
- Unit tests (all pass)

### Pre-merge
- All unit tests pass
- Integration tests pass (dry-run)
- Policy gate passes

### Pre-release
- All tests pass
- E2E tests pass
- Policy gate passes
- Security scan passes

## Test Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Unit test coverage | > 90% | ~95% |
| Integration test pass rate | 100% | 100% (dry-run) |
| E2E test pass rate | 100% | 50% (2/4, 2 skipped by design) |
| Flaky test rate | < 1% | 0% |
| Test execution time | < 5 min | ~3 min |

## Test Maintenance

### Adding New Tests
1. Identify test level (unit/integration/E2E)
2. Follow existing patterns
- Unit: `installer/tests/test_<component>.py`
- Integration: `scripts/test_<feature>.sh`
- E2E: `tests/test_<feature>.py`
3. Add to appropriate test suite
4. Update documentation

### Test Maintenance Rules
- No flaky tests - fix or remove
- Keep unit tests fast (< 100ms each)
- Mock external dependencies
- Clear test names describing behavior
- No test interdependencies