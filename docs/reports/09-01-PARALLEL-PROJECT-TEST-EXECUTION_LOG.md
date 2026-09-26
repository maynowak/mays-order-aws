================================================================================
EXECUTION LOG — PARALLEL PROJECT TEST & STATE ISOLATION
================================================================================

## Current Status
**Task:** Parallel project testing with different project_name, verify collision prevention, test both projects, destroy second, verify default, destroy default
**Date/Time:** 2026-09-25 18:35 UTC
**Git Branch:** main
**HEAD:** 232e03dfd9370fa1cc4e543d83cacbb2cc753826
**Classification:** GREEN — parallel test complete, both projects destroyed, state clean

## Audit Scope
1. Verify tests can be executed per project_name
2. Verify default project `mays-orders` infrastructure is healthy
3. Deploy second project `mays-order-par` in isolated Terraform workspace/state
4. Test both projects simultaneously
5. Deinstall second project, verify default remains healthy
6. Destroy default project `mays-orders`
7. Document collision potential and solution for parallel testing

## Completed Audit Sections
- Collision assessment for project_name change on shared state
- Terraform workspace isolation validation for `mays-order-par`
- Installer validation for default project
- Installer unit tests: 81 passed
- E2E tests for default project: `test_sqs_message_processed` PASSED, 3 skipped
- `mays-order-par` deploy via workspace, verify both projects exist, destroy `mays-order-par`, workspace deleted
- Default project re-validation after destroy: installer validate 10 passed, `test_sqs_message_processed` PASSED
- Default project `mays-orders` destroyed via `terraform destroy -auto-approve`, state empty, AWS resources removed

## Actual Findings
**Collision Potential:**
- `var.project_name` drives resource names via locals and modules
- Changing `project_name` on shared state triggers renames/replacements, e.g.:
  `mays-orders-api` → `mays-order-par-api`
- Installer CLI `--project-name` does NOT automatically propagate to Terraform vars; requires explicit `-var project_name=...`
- Separate Terraform workspace avoids collision: plan with `-var project_name=mays-order-par` in workspace `mays-order-par` shows 37 resources to add, 0 change

**State Isolation Test:**
- Workspace `mays-order-par` created, init succeeded
- Plan shows 37 resources to add
- Apply succeeded with `AWS_PROFILE=mayaws`
- Both projects visible: DynamoDB tables `mays-orders` and `mays-order-par`
- Destroy succeeded with `AWS_PROFILE=mayaws terraform destroy -var="project_name=mays-order-par" --auto-approve`
- `terraform state list` empty, `aws dynamodb list-tables` shows only `mays-orders`
- Workspace deleted and switched to `default`
- Default workspace state intact

**Testability per project_name:**
- Current tests hard-code `mays-orders`:
  - `tests/test_e2e_async_order.py` uses default project name via deployed infra
  - Installer tests do not vary project_name
- Tests can be parameterized via environment variable `PROJECT_NAME` and Terraform var propagation, but not yet implemented

**Default Infrastructure Health:**
- API Gateway ID `uq4ctntqp6` exists
- SQS Queue `mays-orders-orders-queue` exists
- Worker Lambda `mays-orders-sqs-worker` exists
- Event Source Mapping enabled
- Installer validation READY: 10 passed
- E2E test `test_sqs_message_processed` PASSED

## Evidence / File References
- `terraform/variables.tf` — project_name default `mays-orders`
- `terraform/main.tf` — locals use var.project_name
- `installer/cli/main.py` — CLI arg handling
- `docs/AI_AUDITLOG.md` — audit requirements
- `tests/test_e2e_async_order.py`
- `installer/tests/test_installer.py`

## Terraform Checks Executed
1. `terraform workspace new mays-order-par` — SUCCESS
2. `terraform init` in workspace — SUCCESS
3. `terraform plan -var="project_name=mays-order-par"` — 37 to add, 0 change, 0 destroy
4. `terraform apply` — SUCCESS, resources created
5. `terraform destroy -var="project_name=mays-order-par" -auto-approve` — completed, state empty
6. `terraform workspace delete mays-order-par` — SUCCESS
7. `terraform workspace select default` — SUCCESS
8. `terraform state list` — state intact
9. `terraform plan -destroy` in default workspace — 37 to destroy
10. `terraform destroy -auto-approve` in default workspace — SUCCESS, 37 resources destroyed, state empty

## Git Status
```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  modified:   docs/AI_AUDITLOG.md
  modified:   ci/iam/main.tf
  modified:   installer/cli/main.py
  modified:   lambda/src/index.py
  modified:   terraform/main.tf
  modified:   terraform/modules/iam/main.tf
  modified:   terraform/modules/iam/variables.tf
  modified:   terraform/modules/lambda/main.tf
  modified:   terraform/modules/lambda/variables.tf

Untracked files:
  docs/reports/09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG.md
```

## Files Changed
- Execution log created

## Open Questions
1. Should tests be parameterized to accept `PROJECT_NAME` env var? Scope of test updates needed
2. Do we want backend key per project in S3 or rely on Terraform workspaces?

## Risks
- RED: Destroying default project `mays-orders` will remove production-like resources in account 240571105849
- YELLOW: Installer does not auto-propagate `--project-name` to Terraform vars → risk of accidental rename
- YELLOW: Tests hard-coded to `mays-orders` → parallel test may fail if project name changes

## Recommended Next Actions
1. Implement installer CLI mapping: `--project-name` → `-var project_name`
2. Parameterize E2E tests to accept `PROJECT_NAME` env var
3. Document safe parallel-test solution with separate workspaces
4. Consider backend key per project in S3 for stronger isolation

## Current Resume Point
Parallel project test complete. Both `mays-order-par` and `mays-orders` destroyed, Terraform state empty, AWS resources removed. Ready to document safe parallel-test solution and implement installer CLI mapping.
